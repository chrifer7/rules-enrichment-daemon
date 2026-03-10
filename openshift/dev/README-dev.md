# Deploy rules-enrichment-daemon (dev)

## Build
oc project <namespace>
oc apply -f .\openshift\dev\01-rules-enrichment-daemon-is-dev.yaml
oc apply -f .\openshift\dev\02-rules-enrichment-daemon-bc-dev.yaml
oc start-build rules-enrichment-daemon-dev-bc --from-dir=. --follow

## Deploy
oc apply -f .\openshift\dev
oc wait --for=condition=complete --timeout=300s job/rules-daemon-migrate-dev

## Validate
oc get pods
oc get svc
oc get route
oc logs deployment/rules-enrichment-daemon-dev-d -c daemon

