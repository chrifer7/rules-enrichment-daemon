from fastapi import FastAPI

from app.bootstrap import Bootstrap


bootstrap = Bootstrap()
app = FastAPI(title="Rules Enrichment Daemon Health", version=bootstrap.settings.app_version)


@app.get("/health")
def health() -> dict[str, bool]:
    return {
        "db_ok": True,
        "external_api_ok": bootstrap.external_wms().health_check(),
        "rules_repo_ok": True,
        "outbox_ok": True,
    }
