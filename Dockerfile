FROM cgr.dev/chainguard/python:latest

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    OLLAYA_BASE_URL=http://host.docker.internal:11435

WORKDIR /app

COPY questions.json questions.telecom.json questions.futebol.json ./
COPY --chown=nonroot:nonroot web/ ./web/

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD ["/usr/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/config', timeout=2)"]

ENTRYPOINT ["/usr/bin/python"]
CMD ["web/server.py"]
