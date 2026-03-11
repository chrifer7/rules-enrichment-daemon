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

Authentication options (optional):
- `-OcServer` and `-OcToken` for `oc login` inside the script
- `-OcInsecureSkipTlsVerify` if your corporate cluster requires it
- `-BuildSource Binary|Git` (default: `Binary`)
- `-GitSecretName` only required when `-BuildSource Git`

You can also provide these as environment variables:
- `OPENSHIFT_SERVER`, `OPENSHIFT_TOKEN`
- `GIT_SOURCE_SECRET_NAME` (only for Git builds)
- Build quota tuning: `-BuildCpuLimit`, `-BuildMemoryLimit`, `-BuildCpuRequest`, `-BuildMemoryRequest`

