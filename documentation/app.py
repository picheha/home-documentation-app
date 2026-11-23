"""Ingress-only static documentation, with authenticated GitHub artifact updates.

Options and downloaded content live in /data. Only validated documentation is
served. The optional MQTT listener connects out to a configured broker.
"""

import hashlib
import html
import io
import json
import logging
import os
from pathlib import Path, PurePosixPath
import random
import re
import shutil
import ssl
import stat
import tempfile
import threading
from time import monotonic
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import zipfile

LOG = logging.getLogger("documentation")
WORKFLOW = "build-docs.yml"
ARTIFACT = "documentation-html"
MAX_ZIP = 64 * 1024 * 1024
MAX_EXPANDED = 256 * 1024 * 1024
SUPERVISOR_IP = "172.30.32.2"
USER_AGENT = "home-assistant-documentation/0.1.7"
NOTIFICATION_TOPIC = "piche/documentation/ready"
RETRY_DELAYS = (5, 15, 30, 60)


def next_check_delay():
    # Spread requests from different homes over a minute.
    return random.randint(240, 300)


class UpdateError(Exception):
    """A safe-to-log administrative message; never include credentials or URLs."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def bounded_read(response, limit):
    value = response.read(limit + 1)
    if len(value) > limit:
        raise UpdateError("GitHub response exceeds the package size limit.")
    return value


class GitHub:
    def __init__(self, repository, token):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise UpdateError("Set Documentation repository to owner/repository.")
        if not token or any(c.isspace() for c in token):
            raise UpdateError("Set a valid GitHub read token in Configuration, then restart.")
        self.repository = repository
        self.token = token
        # Redirects are handled explicitly so Authorization never reaches storage/CDN hosts.
        self.api_opener = build_opener(NoRedirect())
        self.download_opener = build_opener(NoRedirect())
        self.cached_workflow = None
        self.latest_package = None

    def api(self, suffix, binary=False, *, cache_workflow=False):
        request = Request(
            "https://api.github.com/repos/" + self.repository + suffix,
            headers={
                "Authorization": "Bearer " + self.token,
                # The artifact API returns a redirect, not a release-asset body.
                # It requires GitHub's JSON media type even for ZIP downloads.
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2026-03-10",
                "User-Agent": USER_AGENT,
            },
        )
        cached = self.cached_workflow if cache_workflow else None
        if cached and cached[0] == suffix:
            request.add_header("If-None-Match", cached[1])
        else:
            cached = None
        try:
            with self.api_opener.open(request, timeout=45) as response:
                data = bounded_read(response, MAX_ZIP if binary else 4 * 1024 * 1024)
                if binary:
                    return data
                result = json.loads(data)
                if cache_workflow:
                    etag = response.headers.get("ETag")
                    self.cached_workflow = (suffix, etag, result) if etag else None
                return result
        except HTTPError as error:
            if binary and error.code == 302:
                location = error.headers.get("Location", "")
                error.close()
                return self.download(location)
            code = error.code
            error.close()
            if code == 304 and cached:
                return cached[2]
            if code in (401, 403, 404):
                raise UpdateError("GitHub access denied or repository unavailable. Check repository, token expiry, organization approval, and Actions: Read-only permission.") from None
            if code == 410:
                raise UpdateError("Website package expired. Run Build private documentation again in GitHub Actions.") from None
            raise UpdateError(f"GitHub returned HTTP {code}; keeping the saved website.") from None

    def download(self, location):
        for _ in range(4):
            parsed = urlsplit(location)
            host = (parsed.hostname or "").lower()
            allowed = host.endswith((".blob.core.windows.net", ".githubusercontent.com", ".github.com"))
            if parsed.scheme != "https" or not allowed or parsed.username or parsed.password or parsed.port not in (None, 443):
                raise UpdateError("GitHub supplied an unexpected package download destination.")
            # Deliberately omit Authorization, even if GitHub redirects back to its own domain.
            request = Request(location, headers={"User-Agent": USER_AGENT})
            try:
                with self.download_opener.open(request, timeout=60) as response:
                    return bounded_read(response, MAX_ZIP)
            except HTTPError as error:
                if error.code in (301, 302, 303, 307, 308):
                    location = error.headers.get("Location", "")
                    error.close()
                    continue
                error.close()
                raise UpdateError("Package download failed; keeping the saved website.") from None
        raise UpdateError("Too many package download redirects.")

    def latest(self, active_artifact_id=None):
        query = urlencode({"branch": "main", "status": "success", "per_page": 1})
        result = self.api(f"/actions/workflows/{quote(WORKFLOW, safe='')}/runs?{query}", cache_workflow=True)
        runs = result.get("workflow_runs", [])
        if not runs:
            raise UpdateError("No successful documentation build found on main. Run Build private documentation in GitHub Actions.")
        run = runs[0]
        if (run.get("head_branch") != "main" or run.get("conclusion") != "success"
                or run.get("status") != "completed"
                or run.get("event") not in ("push", "workflow_dispatch", "schedule")
                or run.get("head_repository", {}).get("full_name", "").lower() != self.repository.lower()
                or run.get("path") != ".github/workflows/" + WORKFLOW):
            raise UpdateError("Build does not match the trusted documentation workflow.")
        run_id = int(run["id"])
        build = (run_id, run.get("run_attempt"), run["head_sha"])
        if self.latest_package and self.latest_package[0] == build:
            last_artifact = self.latest_package[1]
            if str(last_artifact["id"]) == active_artifact_id:
                return last_artifact, run
        result = self.api(f"/actions/runs/{run_id}/artifacts?per_page=100")
        artifacts = [a for a in result.get("artifacts", []) if a.get("name") == ARTIFACT and not a.get("expired")]
        if not artifacts:
            raise UpdateError("Website package is missing or expired. Run Build private documentation again in GitHub Actions.")
        artifact = max(artifacts, key=lambda a: int(a["id"]))
        self.latest_package = build, artifact
        return artifact, run


def unpack_website(data, destination, digest, run):
    if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise UpdateError("Package checksum missing. Rebuild using the current GitHub upload-artifact action.")
    if "sha256:" + hashlib.sha256(data).hexdigest() != digest:
        raise UpdateError("Package checksum did not match; keeping the saved website.")
    destination = Path(destination)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if len(entries) > 10000 or sum(item.file_size for item in entries) > MAX_EXPANDED:
            raise UpdateError("Website exceeds the extraction size limit.")
        seen = set()
        for item in entries:
            path = PurePosixPath(item.filename)
            mode = item.external_attr >> 16
            if (not item.filename or "\\" in item.filename or ":" in item.filename
                    or path.is_absolute() or ".." in path.parts
                    or stat.S_ISLNK(mode) or path.as_posix() in seen):
                raise UpdateError("Website archive contains an unsafe or duplicate path.")
            if mode and stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise UpdateError("Website archive contains a non-file entry.")
            seen.add(path.as_posix())
        archive.extractall(destination)
    if not (destination / "index.html").is_file():
        raise UpdateError("Website package does not contain index.html.")
    index = json.loads((destination / "search/search_index.json").read_text(encoding="utf-8"))
    if not index.get("docs"):
        raise UpdateError("Website search index is empty.")
    version = json.loads((destination / "version.json").read_text(encoding="utf-8"))
    if version.get("commit") != run["head_sha"] or str(version.get("run_id")) != str(run["id"]):
        raise UpdateError("Website version does not match the successful GitHub build.")


class Website:
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.packages = self.data_dir / "packages"
        self.packages.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.active = None
        self.artifact_id = None
        try:
            marker = json.loads((self.data_dir / "active.json").read_text(encoding="utf-8"))
            identifier = str(marker["artifact_id"])
            if not re.fullmatch(r"[0-9]+", identifier):
                raise ValueError("Invalid marker")
            candidate = self.packages / identifier
            if (candidate / "index.html").is_file():
                self.active, self.artifact_id = candidate, identifier
        except (OSError, ValueError, KeyError):
            pass

    def sync(self, github, *, minimum_run_id=0):
        artifact, run = github.latest(self.artifact_id)
        if int(run["id"]) < minimum_run_id:
            raise UpdateError("The announced build is not visible on GitHub yet. Keeping the saved website.")
        identifier = str(int(artifact["id"]))
        if identifier == self.artifact_id:
            return False
        if int(artifact.get("size_in_bytes", MAX_ZIP + 1)) > MAX_ZIP:
            raise UpdateError("Website package is too large.")
        data = github.api(f"/actions/artifacts/{identifier}/zip", binary=True)
        staging = Path(tempfile.mkdtemp(prefix="staging-", dir=self.data_dir))
        try:
            unpack_website(data, staging, artifact.get("digest"), run)
            target = self.packages / identifier
            # Clean an incomplete activation left by a previous interrupted attempt.
            if target.exists():
                shutil.rmtree(target)
            staging.rename(target)
            marker = self.data_dir / "active.next.json"
            marker.write_text(json.dumps({"artifact_id": identifier}), encoding="utf-8")
            with self.lock:
                os.replace(marker, self.data_dir / "active.json")
                self.active, self.artifact_id = target, identifier
            # Keep the current and previous packages, so a failed update never removes the current site.
            saved = sorted((p for p in self.packages.iterdir() if p.is_dir() and p.name.isdigit()),
                           key=lambda p: int(p.name), reverse=True)
            for old in saved[2:]:
                if old != target:
                    shutil.rmtree(old, ignore_errors=True)
            LOG.info("Documentation updated successfully (build %s).", run["id"])
            return True
        finally:
            shutil.rmtree(staging, ignore_errors=True)


def handler_for(website):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            with website.lock:
                directory = website.active
            self.ready = directory is not None
            super().__init__(*args, directory=str(directory or website.data_dir), **kwargs)

        def allowed(self):
            if self.client_address[0] != SUPERVISOR_IP:
                self.send_error(403)
                return False
            return True

        def do_GET(self):
            if not self.allowed():
                return
            super().do_GET()

        def do_HEAD(self):
            if not self.allowed():
                return
            super().do_HEAD()

        def themed_html(self, body, prefix="", page=None):
            language = "en"
            targets = {}
            if page is not None:
                relative = page.relative_to(Path(self.directory))
                if relative.parts[0] in ("lv", "ru"):
                    language = relative.parts[0]
                    relative = Path(*relative.parts[1:])
                for code in ("en", "lv", "ru"):
                    target = Path(self.directory) / ("" if code == "en" else code) / relative
                    if target.is_file():
                        targets[code] = os.path.relpath(target, page.parent).replace(os.sep, "/")
            language_data = html.escape(json.dumps(targets), quote=True)
            resources = (
                '<link data-ha-doc-theme rel="stylesheet" href="'
                + prefix + '__documentation_theme__/theme.css">'
                '<script src="' + prefix + '__documentation_theme__/theme.js" defer></script>'
                '<script data-doc-language="' + language + '" data-doc-targets="'
                + language_data + '" src="' + prefix + '__documentation_theme__/language.js" defer></script>'
            )
            document = body.decode("utf-8")
            if "data-ha-doc-theme" not in document:
                if re.search(r"</head\s*>", document, flags=re.I):
                    document = re.sub(r"</head\s*>", lambda match: resources + match.group(), document, count=1, flags=re.I)
                else:
                    document = resources + document
            return document.encode("utf-8")

        def response_file(self, body, content_type, status=200):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            if status == 503:
                self.send_header("Retry-After", "15")
            self.end_headers()
            return io.BytesIO(body)

        def send_head(self):
            # Fixed allowlist: never expose other app files or configuration.
            assets = {
                "/__documentation_theme__/theme.css": ("theme.css", "text/css; charset=utf-8"),
                "/__documentation_theme__/theme.js": ("theme.js", "text/javascript; charset=utf-8"),
                "/__documentation_theme__/language.js": ("language.js", "text/javascript; charset=utf-8"),
            }
            asset = assets.get(urlsplit(self.path).path)
            if asset:
                body = Path(__file__).with_name(asset[0]).read_bytes()
                return self.response_file(body, asset[1])
            if not self.ready:
                body = self.themed_html(Path(__file__).with_name("waiting.html").read_bytes())
                return self.response_file(body, "text/html; charset=utf-8", 503)
            candidate = Path(self.translate_path(self.path))
            if candidate.is_dir() and urlsplit(self.path).path.endswith("/"):
                candidate = candidate / "index.html"
            if candidate.is_file() and candidate.suffix.lower() in (".html", ".htm"):
                depth = len(candidate.parent.relative_to(Path(self.directory)).parts)
                body = self.themed_html(candidate.read_bytes(), "../" * depth, candidate)
                return self.response_file(body, "text/html; charset=utf-8")
            return super().send_head()

        def list_directory(self, path):
            self.send_error(404)
            return None

        def end_headers(self):
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "same-origin")
            super().end_headers()

        def log_message(self, format, *args):
            pass  # Avoid recording private article paths or request headers.

    return Handler


def try_sync(website, github, minimum_run_id=0):
    try:
        website.sync(github, minimum_run_id=minimum_run_id)
        return True
    except UpdateError as error:
        LOG.warning("%s", error)
    except (OSError, ValueError, KeyError, URLError, zipfile.BadZipFile, RuntimeError):
        LOG.warning("Update unavailable. Keeping the saved documentation; check Configuration, internet access, and the latest GitHub build.")
    return False


class UpdateNotices:
    """Keep the most recent pending run without growing a queue during a download."""

    def __init__(self):
        self.condition = threading.Condition()
        self.pending = None

    def request(self, run_id):
        with self.condition:
            self.pending = max(self.pending or 0, run_id)
            self.condition.notify()

    def next(self, timeout):
        with self.condition:
            self.condition.wait_for(lambda: self.pending is not None, timeout)
            run_id, self.pending = self.pending, None
            return run_id


def listen_for_updates(client, topic, notices):
    """Callbacks only queue notices. Downloads run on the update thread."""
    last_notice = 0

    def connected(client, _userdata, _flags, result):
        if result == 0:
            client.subscribe(topic, qos=1)
        else:
            LOG.warning("Documentation notification broker rejected the connection.")

    def subscribed(_client, _userdata, _message_id, granted_qos):
        if not granted_qos or any(qos >= 128 for qos in granted_qos):
            LOG.warning("Documentation notification subscription was rejected. Check the broker permissions.")
            return
        LOG.info("Document update notifications connected.")
        notices.request(0)  # Reconcile once after connecting, even without a retained notice.

    def received(_client, _userdata, message):
        nonlocal last_notice
        if message.topic != topic or not re.fullmatch(rb"[1-9][0-9]{0,17}", message.payload):
            return
        run_id = int(message.payload)
        if run_id > last_notice:
            last_notice = run_id
            notices.request(run_id)

    client.on_connect = connected
    client.on_connect_fail = lambda _client, _userdata: LOG.warning(
        "Cannot reach the documentation notification broker. Retrying the connection."
    )
    client.on_subscribe = subscribed
    client.on_message = received


def notification_loop(website, github, options, stop):
    # Alpine 3.24 ships Paho 1.x. Select the same callback API under Paho 2.x.
    import paho.mqtt.client as mqtt

    host = (options.get("mqtt_host") or "").strip()
    if host:
        port = options.get("mqtt_port", 8883)
        use_tls = options.get("mqtt_tls", True)
    else:
        # Older versions saved remote-broker defaults even on installations
        # with no host configured. Use the same-device listener in that case.
        host, port, use_tls = "core-mosquitto", 1883, False
    topic = options.get("mqtt_topic") or NOTIFICATION_TOPIC
    if not re.fullmatch(r"[A-Za-z0-9.-]+", host) or not re.fullmatch(r"[A-Za-z0-9_/-]{1,128}", topic):
        raise UpdateError("Enter a broker hostname or IPv4 address and a single MQTT topic.")
    client_args = (
        {"callback_api_version": mqtt.CallbackAPIVersion.VERSION1}
        if hasattr(mqtt, "CallbackAPIVersion") else {}
    )
    client = mqtt.Client(**client_args)
    username = options.get("mqtt_username")
    password = options.get("mqtt_password")
    if password and not username:
        raise UpdateError("Enter the broker username for this MQTT password.")
    if username:
        client.username_pw_set(username, password)
    if use_tls:
        client.tls_set_context(ssl.create_default_context())
    client.reconnect_delay_set(min_delay=2, max_delay=60)
    notices = UpdateNotices()
    listen_for_updates(client, topic, notices)
    client.connect_async(host, port, keepalive=60)
    client.loop_start()
    try:
        # Populate an empty cache even if the relay is down during startup.
        notices.request(0)
        next_check = monotonic() + next_check_delay()
        while not stop.is_set():
            requested_run = notices.next(timeout=1)
            if stop.is_set():
                break
            if requested_run is None:
                if monotonic() < next_check:
                    continue
                try_sync(website, github)
            else:
                for delay in (*RETRY_DELAYS, None):
                    if stop.is_set() or try_sync(website, github, requested_run):
                        break
                    if delay is None or stop.wait(delay):
                        break
            next_check = monotonic() + next_check_delay()
    finally:
        client.disconnect()
        client.loop_stop()


def update_loop(website, stop):
    try:
        options = json.loads((website.data_dir / "options.json").read_text(encoding="utf-8"))
        github = GitHub(options.get("repository", ""), options.get("github_token", ""))
    except UpdateError as error:
        LOG.warning("%s", error)
        return
    except (ImportError, OSError, ValueError, TypeError, AttributeError):
        LOG.warning("Could not start documentation updates. Check the app configuration.")
        return
    has_mqtt_login = options.get("mqtt_username") and options.get("mqtt_password")
    if (options.get("mqtt_host") or "").strip() or has_mqtt_login:
        try:
            notification_loop(website, github, options, stop)
            return
        except UpdateError as error:
            LOG.warning("%s Automatic GitHub checks are still enabled.", error)
        except (ImportError, OSError, ValueError, TypeError, AttributeError):
            LOG.warning("Could not start MQTT notifications. Automatic GitHub checks are still enabled.")
    while not stop.is_set():
        try_sync(website, github)
        stop.wait(next_check_delay())


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    website = Website("/data")
    stop = threading.Event()
    threading.Thread(target=update_loop, args=(website, stop), daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", 8099), handler_for(website))
    LOG.info("Documentation is available through Home Assistant Ingress.")
    try:
        server.serve_forever()
    finally:
        stop.set()
        server.server_close()


if __name__ == "__main__":
    main()
