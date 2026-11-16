FROM ghcr.io/home-assistant/base:3.24

RUN apk add --no-cache python3 ca-certificates
WORKDIR /app
COPY app.py /app/app.py
COPY waiting.html /app/waiting.html
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
CMD ["python3", "/app/app.py"]
