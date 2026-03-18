FROM python:3.12-slim

# Disable bytecode files and force unbuffered stdout so container logs appear
# immediately in Docker/OpenShift log streams.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /tmp/app

# Copy only the files needed to install and run the application image.
COPY pyproject.toml README.md ./
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./

USER 0
# Install the package into the image itself. OpenShift containers will then execute
# commands from the installed package rather than from a bind-mounted source tree.
RUN pip install --no-cache-dir .
USER 1001

# The base image defaults to the lightweight health API. OpenShift deployments override
# the command per container when they need the daemon or the log shipper behavior.
HEALTHCHECK --interval=20s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health')"

CMD ["uvicorn", "app.interfaces.health.api:app", "--host", "0.0.0.0", "--port", "8080"]
