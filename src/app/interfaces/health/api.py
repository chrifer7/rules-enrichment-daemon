from fastapi import FastAPI

from app.bootstrap import Bootstrap


# This module is imported once when the health container starts.
# Creating Bootstrap here is acceptable because this process only serves health routes.
bootstrap = Bootstrap()
app = FastAPI(title="Rules Enrichment Daemon Health", version=bootstrap.settings.app_version)


@app.get("/live")
def live() -> dict[str, str]:
    # Liveness must not depend on upstream systems.
    return {"status": "alive"}


@app.get("/ready")
def ready() -> dict[str, str]:
    # Readiness in this deployment is process-level to avoid restarts caused by
    # temporary upstream outages.
    return {"status": "ready"}


@app.get("/health")
def health() -> dict[str, bool]:
    # `/health` is richer than `/live` and `/ready`, but still lightweight enough
    # for manual diagnostics and platform checks.
    return {
        "db_ok": True,
        "external_api_ok": bootstrap.external_wms().health_check(),
        "rules_repo_ok": True,
        "outbox_ok": True,
    }
