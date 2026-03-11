param(
  [Parameter(Mandatory = $false)]
  [ValidateSet('test', 'prod')]
  [string]$Environment = 'test',

  [Parameter(Mandatory = $false)]
  [string]$Namespace = 'dsc-dhl-fulfillment-network-mida',

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

function Convert-ManifestContent {
  param(
    [Parameter(Mandatory = $true)][string]$Content,
    [Parameter(Mandatory = $true)][string]$Env
  )

  $nameSuffix = "$Env-dfn"
  $updated = $Content -replace '-test\b', "-$nameSuffix"
  $updated = [regex]::Replace($updated, '(^\s*app\.kubernetes\.io/environment:\s*)test(\s*$)', "`${1}$Env`${2}", 'Multiline')
  $updated = [regex]::Replace($updated, '(^\s*APP_ENV:\s*)test(\s*$)', "`${1}$Env`${2}", 'Multiline')
  $updated = [regex]::Replace($updated, '(^\s*EXTERNAL_API_BASE_URL:\s*).*(\s*$)', "`${1}http://manhattan-simulator-$nameSuffix`${2}", 'Multiline')

  # Force SQLite in DFN mode to avoid PVC quota and Postgres dependencies.
  $updated = [regex]::Replace(
    $updated,
    '(?m)^(\s*USE_SQLITE:\s*).*$',
    { param($m) "$($m.Groups[1].Value)`"true`"" }
  )
  $updated = [regex]::Replace(
    $updated,
    '(?m)^(\s*DATABASE_URL:\s*).*$',
    { param($m) $m.Groups[1].Value + 'sqlite+pysqlite:///tmp/rules_enrichment_daemon.db' }
  )

  if ($updated -match '(?m)^\s*kind:\s*ConfigMap\s*$' -and
      $updated -match '(?m)^\s*USE_SQLITE:\s*' -and
      $updated -notmatch '(?m)^\s*SQLITE_DATABASE_URL:\s*') {
    $updated = [regex]::Replace(
      $updated,
      '(?m)^(\s*USE_SQLITE:\s*.*)$',
      { param($m) $m.Groups[1].Value + [Environment]::NewLine + '  SQLITE_DATABASE_URL: sqlite+pysqlite:///tmp/rules_enrichment_daemon.db' }
    )
  }

  return $updated
}

if (-not (Get-Command oc -ErrorAction SilentlyContinue)) {
  throw 'Could not find `oc` in PATH. Install OpenShift CLI before continuing.'
}

Invoke-Oc whoami | Out-Null
Invoke-Oc project $Namespace | Out-Null

$ScriptDir = Split-Path -Parent $PSCommandPath
$RepoRoot = Split-Path -Parent $ScriptDir
$SourceEnvDir = Join-Path $ScriptDir 'test'

if (-not (Test-Path $SourceEnvDir)) {
  throw "Source environment directory not found: $SourceEnvDir"
}

$renderDir = Join-Path $env:TEMP "rules-enrichment-daemon-$Environment-dfn-rendered"
if (Test-Path $renderDir) {
  Remove-Item -Path $renderDir -Recurse -Force
}
New-Item -ItemType Directory -Path $renderDir | Out-Null

$sourceFiles = Get-ChildItem -Path $SourceEnvDir -Filter *.yaml |
  Where-Object { $_.Name -notmatch 'postgres' } |
  Sort-Object Name
foreach ($file in $sourceFiles) {
  $raw = Get-Content -Path $file.FullName -Raw
  $rendered = Convert-ManifestContent -Content $raw -Env $Environment
  $targetName = ($file.Name -replace '-test\b', "-$Environment-dfn")
  Set-Content -Path (Join-Path $renderDir $targetName) -Value $rendered -NoNewline
}

$appBase = "rules-enrichment-daemon-$Environment-dfn"
$bcName = "$appBase-bc"
$isFile = Join-Path $renderDir "01-rules-enrichment-daemon-is-$Environment-dfn.yaml"
$bcFile = Join-Path $renderDir "02-rules-enrichment-daemon-bc-$Environment-dfn.yaml"
$migrateFile = Join-Path $renderDir "12-rules-daemon-migrate-job-$Environment-dfn.yaml"
$coreManifestFiles = Get-ChildItem -Path $renderDir -Filter *.yaml | Where-Object { $_.FullName -ne $migrateFile } | Sort-Object Name

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

Write-Host "[4/7] Applying manifests for environment $Environment (dfn)..." -ForegroundColor Cyan
foreach ($manifest in $coreManifestFiles) {
  Invoke-Oc apply -f $manifest.FullName
}

Write-Host "[5/7] Waiting for deployments..." -ForegroundColor Cyan
Invoke-Oc rollout status deployment/rules-enrichment-daemon-$Environment-dfn-d --timeout=300s

if (-not $SkipMigrate) {
  Write-Host "[6/7] Running Alembic migrations..." -ForegroundColor Cyan
  Invoke-Oc delete job rules-daemon-migrate-$Environment-dfn --ignore-not-found=true
  Invoke-Oc apply -f $migrateFile
  Invoke-Oc wait --for=condition=complete --timeout=300s job/rules-daemon-migrate-$Environment-dfn
  Invoke-Oc logs job/rules-daemon-migrate-$Environment-dfn
} else {
  Write-Host "[6/7] Migrations skipped via -SkipMigrate parameter" -ForegroundColor Yellow
}

Write-Host "[7/7] Running final validation..." -ForegroundColor Cyan
Invoke-Oc get pods
Invoke-Oc get svc
Invoke-Oc get route

try {
  $routeHost = (& oc get route rules-enrichment-daemon-health-$Environment-dfn -o jsonpath='{.spec.host}')
  if ($LASTEXITCODE -eq 0 -and $routeHost) {
    Write-Host "Health URL: https://$routeHost/health" -ForegroundColor Green
  }
} catch {
  Write-Host 'Could not fetch the health route.' -ForegroundColor Yellow
}

Write-Host "rules-enrichment-daemon ($Environment-dfn) deployment completed in namespace $Namespace." -ForegroundColor Green
