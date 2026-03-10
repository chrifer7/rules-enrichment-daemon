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
    throw "Comando fallido: oc $($Args -join ' ')"
  }
}

if (-not (Get-Command oc -ErrorAction SilentlyContinue)) {
  throw 'No se encontro `oc` en el PATH. Instala OpenShift CLI antes de continuar.'
}

Invoke-Oc whoami | Out-Null

if ($Namespace) {
  Invoke-Oc project $Namespace | Out-Null
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$EnvDir = Join-Path $ScriptDir $Environment

if (-not (Test-Path $EnvDir)) {
  throw "No existe el directorio de entorno: $EnvDir"
}

$appBase = "rules-enrichment-daemon-$Environment"
$bcName = "$appBase-bc"
$isFile = Join-Path $EnvDir "01-rules-enrichment-daemon-is-$Environment.yaml"
$bcFile = Join-Path $EnvDir "02-rules-enrichment-daemon-bc-$Environment.yaml"
$migrateFile = Join-Path $EnvDir "12-rules-daemon-migrate-job-$Environment.yaml"

Write-Host "[1/7] Validacion dry-run (client/server)..." -ForegroundColor Cyan
Invoke-Oc apply --dry-run=client -f $EnvDir | Out-Null
Invoke-Oc apply --dry-run=server -f $EnvDir | Out-Null

Write-Host "[2/7] Aplicando ImageStream y BuildConfig..." -ForegroundColor Cyan
Invoke-Oc apply -f $isFile
Invoke-Oc apply -f $bcFile

if (-not $SkipBuild) {
  Write-Host "[3/7] Ejecutando build binario desde el repo..." -ForegroundColor Cyan
  Invoke-Oc start-build $bcName --from-dir=$RepoRoot --follow
} else {
  Write-Host "[3/7] Build omitido por parametro -SkipBuild" -ForegroundColor Yellow
}

Write-Host "[4/7] Aplicando manifiestos del entorno $Environment..." -ForegroundColor Cyan
Invoke-Oc apply -f $EnvDir

Write-Host "[5/7] Esperando despliegues..." -ForegroundColor Cyan
Invoke-Oc rollout status deployment/daemon-postgres-$Environment-d --timeout=300s
Invoke-Oc rollout status deployment/rules-enrichment-daemon-$Environment-d --timeout=300s

if (-not $SkipMigrate) {
  Write-Host "[6/7] Ejecutando migraciones Alembic..." -ForegroundColor Cyan
  Invoke-Oc delete job rules-daemon-migrate-$Environment --ignore-not-found=true
  Invoke-Oc apply -f $migrateFile
  Invoke-Oc wait --for=condition=complete --timeout=300s job/rules-daemon-migrate-$Environment
  Invoke-Oc logs job/rules-daemon-migrate-$Environment
} else {
  Write-Host "[6/7] Migraciones omitidas por parametro -SkipMigrate" -ForegroundColor Yellow
}

Write-Host "[7/7] Validacion final..." -ForegroundColor Cyan
Invoke-Oc get pods
Invoke-Oc get svc
Invoke-Oc get route

try {
  $routeHost = (& oc get route rules-enrichment-daemon-health-$Environment -o jsonpath='{.spec.host}')
  if ($LASTEXITCODE -eq 0 -and $routeHost) {
    Write-Host "Health URL: https://$routeHost/health" -ForegroundColor Green
  }
} catch {
  Write-Host 'No se pudo obtener la route de health.' -ForegroundColor Yellow
}

Write-Host "Despliegue de rules-enrichment-daemon ($Environment) completado." -ForegroundColor Green
