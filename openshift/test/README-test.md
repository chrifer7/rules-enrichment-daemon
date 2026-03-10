# Deploy rules-enrichment-daemon (test)

## Build
oc project <namespace>
oc apply -f .\openshift\test\01-rules-enrichment-daemon-is-test.yaml
oc apply -f .\openshift\test\02-rules-enrichment-daemon-bc-test.yaml
oc start-build rules-enrichment-daemon-test-bc --from-dir=. --follow

## Deploy
oc apply -f .\openshift\test
oc wait --for=condition=complete --timeout=300s job/rules-daemon-migrate-test

## Validate
oc get pods
oc get svc
oc get route
oc logs deployment/rules-enrichment-daemon-test-d -c daemon

