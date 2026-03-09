.PHONY: install test run-daemon run-health publish-outbox seed-rules migrate

install:
	pip install -e .[dev]

run-daemon:
	run-daemon

run-health:
	uvicorn app.interfaces.health.api:app --host 0.0.0.0 --port 8080

publish-outbox:
	publish-outbox

seed-rules:
	seed-rules

migrate:
	alembic upgrade head

test:
	$env:USE_SQLITE="true"
	pytest -q
