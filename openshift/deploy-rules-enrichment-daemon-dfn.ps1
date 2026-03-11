param(
  [Parameter(Mandatory = $false)]
  [ValidateSet('test', 'prod')]
  [string]$Environment = 'test',

  [Parameter(Mandatory = $false)]
  [string]$Namespace = 'dsc-dhl-fulfillment-network-mida',

  [Parameter(Mandatory = $false)]
  [string]$OcServer = '',

  [Parameter(Mandatory = $false)]
  [string]$OcToken = '',

  [Parameter(Mandatory = $false)]
  [switch]$OcInsecureSkipTlsVerify,

  [Parameter(Mandatory = $false)]
  [string]$GitUri = 'https://git.dhl.com/EU-FFN/rules-enrichment-daemon.git',

  [Parameter(Mandatory = $false)]
  [string]$GitRef = 'main',

  [Parameter(Mandatory = $false)]
  [ValidateSet('Binary', 'Git')]
  [string]$BuildSource = 'Binary',

  [Parameter(Mandatory = $false)]
  [string]$GitSecretName = '',

  [Parameter(Mandatory = $false)]
  [string]$BuildCpuLimit = '500m',

  [Parameter(Mandatory = $false)]
  [string]$BuildMemoryLimit = '512Mi',

  [Parameter(Mandatory = $false)]
  [string]$BuildCpuRequest = '300m',

  [Parameter(Mandatory = $false)]
  [string]$BuildMemoryRequest = '256Mi',

  [Parameter(Mandatory = $false)]
  [string]$BuildBaseImage = 'redhat-docker-remote.artifactory.dhl.com/ubi8/python-312:sha256__47056fa31a255ebd2b08c469b25e6ee5f516280937c024c40372de9e9cc492d5',

  [Parameter(Mandatory = $false)]
  [bool]$BuildForcePull = $true,

  [Parameter(Mandatory = $false)]
  [bool]$BuildNoCache = $true,

  [Parameter(Mandatory = $false)]
  [int]$BuildTimeoutSeconds = 1800,

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

function Ensure-OcSession {
  $resolvedToken = if ($OcToken) { $OcToken } elseif ($env:OPENSHIFT_TOKEN) { $env:OPENSHIFT_TOKEN } else { '' }
  $resolvedServer = if ($OcServer) { $OcServer } elseif ($env:OPENSHIFT_SERVER) { $env:OPENSHIFT_SERVER } else { '' }

  if ($resolvedToken -and $resolvedServer) {
    Write-Host "Authenticating to OpenShift server..." -ForegroundColor Cyan
    if ($OcInsecureSkipTlsVerify) {
      Invoke-Oc login --token=$resolvedToken --server=$resolvedServer --insecure-skip-tls-verify=true | Out-Null
    } else {
      Invoke-Oc login --token=$resolvedToken --server=$resolvedServer | Out-Null
    }
  } else {
    Invoke-Oc whoami | Out-Null
  }

  Invoke-Oc project $Namespace | Out-Null
}

function Ensure-GitSourceSecret {
  param(
    [Parameter(Mandatory = $true)][string]$BuildConfigName
  )

  $secretName = if ($GitSecretName) { $GitSecretName } elseif ($env:GIT_SOURCE_SECRET_NAME) { $env:GIT_SOURCE_SECRET_NAME } else { '' }
  if (-not $secretName) {
    throw "Git source secret name is required. Provide -GitSecretName or set GIT_SOURCE_SECRET_NAME."
  }

  Invoke-Oc -n $Namespace get secret $secretName | Out-Null

  $sourcePatch = '{"spec":{"source":{"sourceSecret":{"name":"{0}"}}}}' -f $secretName
  Invoke-Oc @('-n', $Namespace, 'patch', 'bc', $BuildConfigName, '--type=merge', '-p', $sourcePatch)
  Write-Host "Git source secret linked to BuildConfig: $secretName" -ForegroundColor Green
}

function Invoke-BuildAndWait {
  param(
    [Parameter(Mandatory = $true)][string]$BuildConfigName,
    [Parameter(Mandatory = $true)][string]$Mode,
    [string]$FromDir,
    [Parameter(Mandatory = $true)][int]$TimeoutSeconds
  )

  if ($Mode -eq 'Binary') {
    if (-not $FromDir) {
      throw "Binary build requires -FromDir."
    }
    $buildName = (& oc start-build $BuildConfigName --from-dir=$FromDir -o name)
  } else {
    $buildName = (& oc start-build $BuildConfigName -o name)
  }
  if ($LASTEXITCODE -ne 0 -or -not $buildName) {
    throw "Could not start build for BuildConfig '$BuildConfigName'."
  }
  $buildName = $buildName.Trim()
  Write-Host "Build started: $buildName" -ForegroundColor Cyan

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    $phase = (& oc get $buildName -o jsonpath='{.status.phase}' 2>$null)
    if ($LASTEXITCODE -ne 0) { $phase = '' }
    $phase = ($phase | Out-String).Trim()

    switch ($phase) {
      'Complete' {
        Write-Host "Build completed: $buildName" -ForegroundColor Green
        & oc logs $buildName --tail=200
        return
      }
      'Failed' {
        & oc logs $buildName --tail=400
        throw "Build failed: $buildName"
      }
      'Error' {
        & oc logs $buildName --tail=400
        throw "Build errored: $buildName"
      }
      'Cancelled' {
        & oc logs $buildName --tail=400
        throw "Build was cancelled: $buildName"
      }
      default {
        Write-Host "Waiting for build phase... current='$phase'" -ForegroundColor DarkGray
        Start-Sleep -Seconds 10
      }
    }
  }

  & oc logs $buildName --tail=400
  throw "Timed out waiting for build to complete after $TimeoutSeconds seconds: $buildName"
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

function Convert-BuildConfigToGitSource {
  param(
    [Parameter(Mandatory = $true)][string]$Content,
    [Parameter(Mandatory = $true)][string]$RepoUri,
    [Parameter(Mandatory = $true)][string]$Ref
  )

  $sourceBlock = @"
  source:
    type: Git
    git:
      uri: $RepoUri
      ref: $Ref
"@

  return [regex]::Replace(
    $Content,
    '(?ms)^\s{2}source:\r?\n\s{4}type:\s*Binary\s*$',
    $sourceBlock
  )
}

function Ensure-BuildConfigResources {
  param([Parameter(Mandatory = $true)][string]$BuildConfigName)

  $patch = @{
    spec = @{
      resources = @{
        limits = @{
          cpu = $BuildCpuLimit
          memory = $BuildMemoryLimit
        }
        requests = @{
          cpu = $BuildCpuRequest
          memory = $BuildMemoryRequest
        }
      }
    }
  } | ConvertTo-Json -Depth 10 -Compress

  Invoke-Oc @('-n', $Namespace, 'patch', 'bc', $BuildConfigName, '--type=merge', '-p', $patch)
  Write-Host "BuildConfig resources set (limits/requests) for quota compliance." -ForegroundColor Green
}

function Ensure-BuildConfigBaseImage {
  param([Parameter(Mandatory = $true)][string]$BuildConfigName)

  if (-not $BuildBaseImage) {
    Write-Host "Build base image override not set; BuildConfig will use Dockerfile FROM as-is." -ForegroundColor Yellow
    return
  }

  $patch = @{
    spec = @{
      strategy = @{
        dockerStrategy = @{
          from = @{
            kind = 'DockerImage'
            name = $BuildBaseImage
          }
          forcePull = $BuildForcePull
          noCache = $BuildNoCache
          dockerfilePath = 'Dockerfile'
        }
      }
    }
  } | ConvertTo-Json -Depth 10 -Compress

  Invoke-Oc @('-n', $Namespace, 'patch', 'bc', $BuildConfigName, '--type=merge', '-p', $patch)
  Write-Host "BuildConfig base image set to: $BuildBaseImage" -ForegroundColor Green
}

if (-not (Get-Command oc -ErrorAction SilentlyContinue)) {
  throw 'Could not find `oc` in PATH. Install OpenShift CLI before continuing.'
}

Ensure-OcSession

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
  if ($BuildSource -eq 'Git' -and $file.Name -like '02-*-bc-*.yaml') {
    $rendered = Convert-BuildConfigToGitSource -Content $rendered -RepoUri $GitUri -Ref $GitRef
  }
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
Ensure-BuildConfigResources -BuildConfigName $bcName
Ensure-BuildConfigBaseImage -BuildConfigName $bcName
if ($BuildSource -eq 'Git') {
  Ensure-GitSourceSecret -BuildConfigName $bcName
}

if (-not $SkipBuild) {
  if ($BuildSource -eq 'Git') {
    Write-Host "[3/7] Running Git build from $GitUri (ref: $GitRef)..." -ForegroundColor Cyan
    Invoke-BuildAndWait -BuildConfigName $bcName -Mode 'Git' -TimeoutSeconds $BuildTimeoutSeconds
  } else {
    Write-Host "[3/7] Running Binary build from local repository..." -ForegroundColor Cyan
    Invoke-BuildAndWait -BuildConfigName $bcName -Mode 'Binary' -FromDir $RepoRoot -TimeoutSeconds $BuildTimeoutSeconds
  }
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
