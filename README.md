# rules-enrichment-daemon

`rules-enrichment-daemon` is a background Python service that polls fulfillment orders from an external API, evaluates enrichment rules, and submits the resulting enrichment back to that external system.

This README is written as a practical guide for developers and operators who need to:

- run the daemon locally
- deploy it to OpenShift
- stop, start, or restart the workload safely
- understand the temporary Elasticsearch log shipping pattern used in restricted OpenShift clusters
- reuse that pattern in other Python services

## What the Service Does

Main responsibilities:

1. poll orders in `READY_FOR_ENRICHMENT`
2. load active enrichment rules from its own database
3. evaluate rules against each order
4. build a deterministic enrichment payload
5. submit enrichment to the external API
6. store processing attempts and audit data
7. maintain idempotency and checkpoint state
8. emit structured logs for operational analysis

## High-Level Flow

1. poll external API
2. load or refresh cached rules
3. evaluate matching rules
4. call enrichment submission endpoint
5. persist processing result and attempt history
6. continue in a loop

## Repository Layout

```text
rules-enrichment-daemon/
  README.md
  src/app/
    application/
    config/
    domain/
    infrastructure/
    interfaces/
    shared/
  migrations/
  tests/
  openshift/
    dev/
    test/
    deploy-rules-enrichment-daemon-dfn.ps1
    deploy-rules-enrichment-daemon.ps1
```

## Local Development

### Install dependencies

```bash
pip install -e .[dev]
```

### Run database migrations

```bash
alembic upgrade head
```

### Seed baseline rules

```bash
seed-rules
```

### Start the daemon locally

```bash
run-daemon
```

### Run the health API locally

```bash
uvicorn app.interfaces.health.api:app --host 0.0.0.0 --port 8080
```

## Important CLI Commands

The following commands are available through the CLI entrypoint:

- `run-daemon`
- `publish-outbox`
- `seed-rules`
- `replay-dead-letter`
- `health-check`
- `validate-rules`
- `forward-log-file`

### What `forward-log-file` does

This is the temporary in-pod log shipper used in restricted OpenShift environments.

It:

1. tails a shared log file
2. parses JSON or plain-text log lines
3. builds Elasticsearch bulk requests
4. sends those logs to namespace-local Elasticsearch

## Configuration

The most important runtime settings are:

- `EXTERNAL_API_BASE_URL`
- `EXTERNAL_API_TIMEOUT_SECONDS`
- `POLL_INTERVAL_SECONDS`
- `POLL_BATCH_SIZE`
- `DATABASE_URL`
- `USE_SQLITE`
- `SQLITE_DATABASE_URL`
- `OUTBOX_SINK_MODE`

### Logging configuration

Relevant logging settings:

- `LOG_LEVEL`
- `LOG_ECS_ENABLED`
- `LOG_TO_STDOUT`
- `LOG_TO_FILE`
- `LOG_FILE_PATH`

### Log shipper configuration

The following settings are now supported:

- `LOG_SHIPPER_ELASTICSEARCH_URL`
- `LOG_SHIPPER_ELASTICSEARCH_USERNAME`
- `LOG_SHIPPER_ELASTICSEARCH_PASSWORD`
- `LOG_SHIPPER_INDEX_PREFIX`
- `LOG_SHIPPER_FLUSH_INTERVAL_SECONDS`

## OpenShift Deployment

### Deployment scripts

Main DFN script:

- [deploy-rules-enrichment-daemon-dfn.ps1](/C:/Users/ebb901/repo/sandbox/rules-enrichment-daemon/openshift/deploy-rules-enrichment-daemon-dfn.ps1)

Legacy script:

- [deploy-rules-enrichment-daemon.ps1](/C:/Users/ebb901/repo/sandbox/rules-enrichment-daemon/openshift/deploy-rules-enrichment-daemon.ps1)

### Deploy to OpenShift test namespace

Run from `C:\Users\ebb901\repo\sandbox\rules-enrichment-daemon\openshift`.

```powershell
.\deploy-rules-enrichment-daemon-dfn.ps1 -Environment test -Namespace dsc-dhl-fulfillment-network-mida -BuildSource Binary
```

### Deploy to OpenShift prod namespace

```powershell
.\deploy-rules-enrichment-daemon-dfn.ps1 -Environment prod -Namespace dsc-dhl-fulfillment-network-mida -BuildSource Binary
```

### Deploy from Git source instead of binary upload

```powershell
.\deploy-rules-enrichment-daemon-dfn.ps1 -Environment test -Namespace dsc-dhl-fulfillment-network-mida -BuildSource Git -GitUri https://git.example/repo.git -GitRef main -GitSecretName <SECRET_NAME>
```

### Typical post-deploy validation

```powershell
oc -n dsc-dhl-fulfillment-network-mida get deployment,pods,svc,route | Select-String rules-enrichment-daemon
```

```powershell
oc -n dsc-dhl-fulfillment-network-mida logs deployment/rules-enrichment-daemon-dfn-d-test --all-containers=true --tail=200
```

## Start, Stop, and Restart in OpenShift

### Restart the daemon deployment

```powershell
oc -n dsc-dhl-fulfillment-network-mida rollout restart deployment/rules-enrichment-daemon-dfn-d-test
oc -n dsc-dhl-fulfillment-network-mida rollout status deployment/rules-enrichment-daemon-dfn-d-test --timeout=600s
```

### Stop the daemon for a weekend or maintenance window

```powershell
oc -n dsc-dhl-fulfillment-network-mida scale deployment/rules-enrichment-daemon-dfn-d-test --replicas=0
```

### Start it again

```powershell
oc -n dsc-dhl-fulfillment-network-mida scale deployment/rules-enrichment-daemon-dfn-d-test --replicas=1
```

### Can this be done from the OpenShift UI?

Yes.

Use:

- `Workloads > Deployments`
- open `rules-enrichment-daemon-dfn-d-test`
- choose `Scale`
- set replicas to `0` or `1`

If your objective is to keep the service stopped, always scale to zero instead of deleting the pod.

## Current OpenShift Pod Design

The pod contains multiple containers:

1. `daemon`
   - runs the main processing loop
2. `log-shipper`
   - reads the shared log file and forwards logs to Elasticsearch
3. `health`
   - exposes the health API

## Temporary Elasticsearch Log Shipping Pattern

Because this OpenShift environment does not allow the team to use `ClusterLogForwarder`, the daemon now uses a temporary application-level shipping pattern.

### How it works

1. the main `daemon` container writes ECS-style logs to stdout
2. the same logs are also written to a shared file
3. the shared file lives in an `emptyDir` volume mounted into the pod
4. the `log-shipper` sidecar tails that file
5. the sidecar sends logs to the in-namespace Elasticsearch service

### Why `/tmp` is used instead of `/var/log`

The current cluster uses OpenShift security constraints with arbitrary UIDs.

Using `/tmp/rules-enrichment-daemon/...` is more reliable than `/var/log/...` because:

- it avoids permission issues with non-root users
- it works better under `restricted-v2`
- it does not require elevated privileges

### Current test Elasticsearch target

```text
http://elasticsearch-test-dfn.dsc-dhl-fulfillment-network-mida.svc:9200
```

### Current index prefix

```text
rules-enrichment-daemon-logs
```

This produces indices such as:

```text
rules-enrichment-daemon-logs-2026.03.13
```

## How to View the Daemon Logs in Kibana

### 1. Create a Data View

In Kibana:

1. go to `Stack Management > Data Views`
2. click `Create data view`
3. use:
   - Name: `Rules daemon logs`
   - Index pattern: `rules-enrichment-daemon-logs-*`
   - Timestamp field: `@timestamp`
4. save the Data View

### 2. Open Discover

1. go to `Discover`
2. select `Rules daemon logs`
3. choose a broad enough time range, for example `Last 24 hours`
4. start without any search term
5. then try queries such as:

```text
message:*polling*
```

or:

```text
message:"Polling cycle started"
```

## How to Add the Same Log Shipper Pattern to Another Python Service

This is the reusable recipe for other services in this workspace.

### Step 1. Add settings

Add these environment-driven settings to the service configuration:

- `LOG_TO_FILE`
- `LOG_FILE_PATH`
- `LOG_SHIPPER_ELASTICSEARCH_URL`
- `LOG_SHIPPER_ELASTICSEARCH_USERNAME`
- `LOG_SHIPPER_ELASTICSEARCH_PASSWORD`
- `LOG_SHIPPER_INDEX_PREFIX`
- `LOG_SHIPPER_FLUSH_INTERVAL_SECONDS`

### Step 2. Make the service able to write to a file

Update the logging setup so it can write to:

- stdout
- a file under `/tmp/<service-name>/...`

This file is the handoff point to the sidecar.

### Step 3. Implement a simple shipper process

The shipper should:

1. open the log file
2. track the current offset
3. read only new lines
4. parse JSON when possible
5. generate Elasticsearch `_bulk` payloads
6. send them to the internal Elasticsearch service
7. loop forever with a small sleep interval

### Step 4. Add a CLI command

Expose a dedicated command such as:

```text
forward-log-file
```

This makes it easy to run the shipper in a sidecar container.

### Step 5. Update the OpenShift ConfigMap

Add entries such as:

- `LOG_TO_FILE=true`
- `LOG_FILE_PATH=/tmp/<service-name>/<file>.log`
- `LOG_SHIPPER_ELASTICSEARCH_URL=http://elasticsearch-test-dfn.<namespace>.svc:9200`
- `LOG_SHIPPER_INDEX_PREFIX=<service-name>-logs`
- `LOG_SHIPPER_FLUSH_INTERVAL_SECONDS=5`

### Step 6. Update the Deployment

Add:

- an `emptyDir` volume
- a volume mount in the main container
- a sidecar container that runs the shipper command
- secret-based environment variables for Elasticsearch credentials

### Step 7. Protect the health container

If the pod has a health container, do not let it try to write to the shared file unless that is really needed.

A safe override is:

```yaml
env:
  - name: LOG_TO_FILE
    value: "false"
  - name: LOG_TO_STDOUT
    value: "true"
```

## Troubleshooting

### Rollout fails after the new log shipper was added

Check all containers, not only the main daemon:

```powershell
oc -n dsc-dhl-fulfillment-network-mida get pods
oc -n dsc-dhl-fulfillment-network-mida logs deployment/rules-enrichment-daemon-dfn-d-test --all-containers=true --tail=200
```

### Health container fails with file permission errors

Typical symptom:

```text
PermissionError: [Errno 13] Permission denied
```

This usually means the health container inherited file logging settings that it should not use.

### The daemon runs but does not process orders

Check:

1. `EXTERNAL_API_BASE_URL`
2. simulator availability
3. database migrations and connectivity
4. daemon logs in Kibana or pod logs in OpenShift

### The shipper is not sending logs to Elasticsearch

Look for logs such as:

- `log_shipper_start`
- `log_shipper_bulk_success`
- `log_shipper_bulk_partial_failure`
- `log_shipper_iteration_failed`

## Operational Summary

For day-to-day work:

- deploy with `deploy-rules-enrichment-daemon-dfn.ps1`
- restart with `oc rollout restart`
- stop with `oc scale --replicas=0`
- inspect logs in Kibana through the `rules-enrichment-daemon-logs-*` Data View
- reuse the sidecar shipping pattern for other Python services when cluster-level forwarding is unavailable
