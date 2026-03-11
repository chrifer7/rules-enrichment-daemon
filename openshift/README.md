# OpenShift Manifests - rules-enrichment-daemon

Structure:
- `dev/`: manifests for development
- `test/`: manifests for testing

Naming convention:
- `is` = ImageStream
- `bc` = BuildConfig
- `d` = Deployment
- environment suffixes: `dev` and `test`

Examples:
- `rules-enrichment-daemon-dev-is`
- `rules-enrichment-daemon-dev-bc`
- `rules-enrichment-daemon-dev-d`

## Corporate single-project deployment (`dfn`)

Use this script when your OpenShift platform only allows a single existing project:

- `deploy-rules-enrichment-daemon-dfn.ps1`

This script:
- uses `test` manifests as source templates,
- renders runtime resources with `-test-dfn` or `-prod-dfn` suffixes,
- deploys into one namespace (default: `dsc-dhl-fulfillment-network-mida`),
- keeps the standard `is`, `bc`, `d` suffixes,
- runs in SQLite mode (no Postgres/PVC resources in DFN deployments).

Examples:

```powershell
.\deploy-rules-enrichment-daemon-dfn.ps1 -Environment test -Namespace dsc-dhl-fulfillment-network-mida
.\deploy-rules-enrichment-daemon-dfn.ps1 -Environment prod -Namespace dsc-dhl-fulfillment-network-mida
```

