FROM ghcr.io/home-assistant/base:3.24

RUN apk add --no-cache python3 ca-certificates py3-paho-mqtt
WORKDIR /app
COPY app.py waiting.html theme.css theme.js language.js /app/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
CMD ["python3", "/app/app.py"]
