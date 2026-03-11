param(
  [Parameter(Mandatory = $false)]
  [ValidateSet('dev', 'test')]
  [string]$Environment = 'dev',

  [Parameter(Mandatory = $false)]
  [string]$Namespace,

  [Parameter(Mandatory = $false)]
  [switch]$SkipBuild,

  [Parameter(Mandatory = $false)]
  [switch]$SkipMigrate
)

$ErrorActionPreference = 'Stop'

function Invoke-Oc {
  param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
  & oc @Args
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed: oc $($Args -join ' ')"
  }
}

if (-not (Get-Command oc -ErrorAction SilentlyContinue)) {
  throw 'Could not find `oc` in PATH. Install OpenShift CLI before continuing.'
}

Invoke-Oc whoami | Out-Null

if ($Namespace) {
  Invoke-Oc project $Namespace | Out-Null
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$EnvDir = Join-Path $ScriptDir $Environment

if (-not (Test-Path $EnvDir)) {
  throw "Environment directory not found: $EnvDir"
}

$appBase = "rules-enrichment-daemon-$Environment"
$bcName = "$appBase-bc"
$isFile = Join-Path $EnvDir "01-rules-enrichment-daemon-is-$Environment.yaml"
$bcFile = Join-Path $EnvDir "02-rules-enrichment-daemon-bc-$Environment.yaml"
$migrateFile = Join-Path $EnvDir "12-rules-daemon-migrate-job-$Environment.yaml"
$coreManifestFiles = Get-ChildItem -Path $EnvDir -Filter *.yaml | Where-Object { $_.FullName -ne $migrateFile }

Write-Host "[1/7] Running dry-run validation (client/server)..." -ForegroundColor Cyan
foreach ($manifest in $coreManifestFiles) {
  Invoke-Oc apply --dry-run=client -f $manifest.FullName | Out-Null
  Invoke-Oc apply --dry-run=server -f $manifest.FullName | Out-Null
}

Write-Host "[2/7] Applying ImageStream and BuildConfig..." -ForegroundColor Cyan
Invoke-Oc apply -f $isFile
Invoke-Oc apply -f $bcFile

if (-not $SkipBuild) {
  Write-Host "[3/7] Running binary build from repository..." -ForegroundColor Cyan
  Invoke-Oc start-build $bcName --from-dir=$RepoRoot --follow
} else {
  Write-Host "[3/7] Build skipped via -SkipBuild parameter" -ForegroundColor Yellow
}

Write-Host "[4/7] Applying manifests for environment $Environment..." -ForegroundColor Cyan
foreach ($manifest in $coreManifestFiles) {
  Invoke-Oc apply -f $manifest.FullName
}

Write-Host "[5/7] Waiting for deployments..." -ForegroundColor Cyan
Invoke-Oc rollout status deployment/daemon-postgres-$Environment-d --timeout=300s
Invoke-Oc rollout status deployment/rules-enrichment-daemon-$Environment-d --timeout=300s

if (-not $SkipMigrate) {
  Write-Host "[6/7] Running Alembic migrations..." -ForegroundColor Cyan
  Invoke-Oc delete job rules-daemon-migrate-$Environment --ignore-not-found=true
  Invoke-Oc apply -f $migrateFile
  Invoke-Oc wait --for=condition=complete --timeout=300s job/rules-daemon-migrate-$Environment
  Invoke-Oc logs job/rules-daemon-migrate-$Environment
} else {
  Write-Host "[6/7] Migrations skipped via -SkipMigrate parameter" -ForegroundColor Yellow
}

Write-Host "[7/7] Running final validation..." -ForegroundColor Cyan
Invoke-Oc get pods
Invoke-Oc get svc
Invoke-Oc get route

try {
  $routeHost = (& oc get route rules-enrichment-daemon-health-$Environment -o jsonpath='{.spec.host}')
  if ($LASTEXITCODE -eq 0 -and $routeHost) {
    Write-Host "Health URL: https://$routeHost/health" -ForegroundColor Green
  }
} catch {
  Write-Host 'Could not fetch the health route.' -ForegroundColor Yellow
}

Write-Host "rules-enrichment-daemon ($Environment) deployment completed." -ForegroundColor Green
