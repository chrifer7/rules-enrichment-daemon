FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /tmp/app

COPY pyproject.toml README.md ./
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./

USER 0
RUN pip install --no-cache-dir .
USER 1001

HEALTHCHECK --interval=20s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health')"

CMD ["uvicorn", "app.interfaces.health.api:app", "--host", "0.0.0.0", "--port", "8080"]
