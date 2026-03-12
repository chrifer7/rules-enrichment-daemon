# -----------------------------------------------------------------------------
# Rules Enrichment Daemon DFN deployment script
# -----------------------------------------------------------------------------
# What this script does:
# 1) Validates and renders manifests for the selected environment.
# 2) Applies ImageStream + BuildConfig.
# 3) Builds the image (Binary upload or Git source).
# 4) Applies runtime manifests (Deployment/Service/Route/Config/Secret).
# 5) Stabilizes rollout by scaling old ReplicaSets to zero (if needed).
# 6) Waits for deployment with diagnostics/recovery on timeout.
# 7) Runs migration job and final checks.
#
# Typical execution:
# .\deploy-rules-enrichment-daemon-dfn.ps1 -Environment test -Namespace <project> -BuildSource Binary
# -----------------------------------------------------------------------------
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
  [int]$RolloutTimeoutSeconds = 900,

  [Parameter(Mandatory = $false)]
  [int]$MigrateTimeoutSeconds = 900,

  [Parameter(Mandatory = $false)]
  [switch]$SkipBuild,

  [Parameter(Mandatory = $false)]
  [switch]$SkipMigrate
)

$ErrorActionPreference = 'Stop'

function Invoke-Oc {
  # Thin wrapper around `oc` that turns CLI errors into terminating script errors.
  param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
  & oc @Args
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed: oc $($Args -join ' ')"
  }
}

function Ensure-OcSession {
  # Ensures we are authenticated and switched to the target OpenShift project.
  # Priority: explicit params -> OPENSHIFT_* env vars -> current logged session.
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
  # Reuses an existing Git secret for BuildConfig source cloning.
  # This script intentionally does not create secrets.
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
  # Starts build and polls until completion/failure/timeout.
  # Supports Binary and Git BuildConfig source modes.
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
  # Rewrites base test manifests to DFN naming + selected environment.
  # Also enforces SQLite mode and points daemon to simulator service URL.
  param(
    [Parameter(Mandatory = $true)][string]$Content,
    [Parameter(Mandatory = $true)][string]$Env
  )

  $updated = $Content
  $updated = $updated -replace 'rules-enrichment-daemon-test-is', "rules-enrichment-daemon-dfn-is-$Env"
  $updated = $updated -replace 'rules-enrichment-daemon-test-bc', "rules-enrichment-daemon-dfn-bc-$Env"
  $updated = $updated -replace 'rules-enrichment-daemon-test-d', "rules-enrichment-daemon-dfn-d-$Env"
  $updated = $updated -replace 'rules-enrichment-daemon-test-config', "rules-enrichment-daemon-dfn-config-$Env"
  $updated = $updated -replace 'rules-enrichment-daemon-test-secret', "rules-enrichment-daemon-dfn-secret-$Env"
  $updated = $updated -replace 'rules-daemon-migrate-test', "rules-daemon-dfn-migrate-$Env"
  $updated = $updated -replace 'rules-enrichment-daemon-health-test', "rules-daemon-health-dfn-$Env"
  $updated = $updated -replace 'rules-enrichment-daemon-test\b', "rules-enrichment-daemon-dfn-$Env"
  $updated = [regex]::Replace($updated, '(^\s*app\.kubernetes\.io/environment:\s*)test(\s*$)', "`${1}$Env`${2}", 'Multiline')
  $updated = [regex]::Replace($updated, '(^\s*APP_ENV:\s*)test(\s*$)', "`${1}$Env`${2}", 'Multiline')
  # Use Kubernetes service DNS + explicit port 8000 used by simulator Service.
  $updated = [regex]::Replace(
    $updated,
    '(^\s*EXTERNAL_API_BASE_URL:\s*).*(\s*$)',
    "`${1}http://manhattan-simulator-dfn-$Env.$Namespace.svc:8000`${2}",
    'Multiline'
  )

  # Force SQLite in DFN mode to avoid PVC quota and Postgres dependencies.
  $updated = [regex]::Replace(
    $updated,
    '(?m)^(\s*USE_SQLITE:\s*).*$',
    { param($m) "$($m.Groups[1].Value)`"true`"" }
  )
  $updated = [regex]::Replace(
    $updated,
    '(?m)^(\s*DATABASE_URL:\s*).*$',
    { param($m) $m.Groups[1].Value + 'sqlite+pysqlite:////tmp/rules_enrichment_daemon.db' }
  )

  if ($updated -match '(?m)^\s*kind:\s*ConfigMap\s*$' -and
      $updated -match '(?m)^\s*USE_SQLITE:\s*' -and
      $updated -notmatch '(?m)^\s*SQLITE_DATABASE_URL:\s*') {
    $updated = [regex]::Replace(
      $updated,
      '(?m)^(\s*USE_SQLITE:\s*.*)$',
      { param($m) $m.Groups[1].Value + [Environment]::NewLine + '  SQLITE_DATABASE_URL: sqlite+pysqlite:////tmp/rules_enrichment_daemon.db' }
    )
  }

  return $updated
}

function Convert-BuildConfigToGitSource {
  # Converts BuildConfig source block from Binary to Git.
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
  # Ensures BuildConfig has requests/limits required by namespace quotas.
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
  # Forces use of an internal corporate base image for Docker strategy builds.
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

function Wait-DeploymentRolloutWithRecovery {
  # Waits for deployment rollout.
  # If rollout fails, prints diagnostics, force-deletes terminating pods,
  # retries rollout once, then prints pod logs before failing definitively.
  param(
    [Parameter(Mandatory = $true)][string]$DeploymentName,
    [Parameter(Mandatory = $true)][string]$AppName,
    [Parameter(Mandatory = $true)][string]$Env,
    [Parameter(Mandatory = $true)][int]$TimeoutSeconds
  )

  $labelSelector = "app.kubernetes.io/name=$AppName,app.kubernetes.io/environment=$Env"

  & oc rollout status "deployment/$DeploymentName" --timeout="$($TimeoutSeconds)s"
  if ($LASTEXITCODE -eq 0) {
    return
  }

  Write-Host "Rollout did not complete within timeout. Collecting diagnostics..." -ForegroundColor Yellow
  & oc -n $Namespace get deployment $DeploymentName -o wide
  & oc -n $Namespace describe deployment $DeploymentName
  & oc -n $Namespace get pods -l $labelSelector -o wide

  $podsJson = (& oc -n $Namespace get pods -l $labelSelector -o json 2>$null)
  $terminatingPods = @()
  if ($LASTEXITCODE -eq 0 -and $podsJson) {
    $pods = ($podsJson | ConvertFrom-Json).items
    foreach ($pod in $pods) {
      if ($pod.metadata.deletionTimestamp) {
        $terminatingPods += $pod.metadata.name
      }
    }
  }

  if ($terminatingPods.Count -gt 0) {
    Write-Host "Found terminating pods blocking rollout. Force-deleting..." -ForegroundColor Yellow
    foreach ($podName in $terminatingPods) {
      & oc -n $Namespace delete pod $podName --grace-period=0 --force --ignore-not-found=true
    }
  }

  Write-Host "Retrying deployment rollout..." -ForegroundColor Cyan
  & oc rollout status "deployment/$DeploymentName" --timeout="$($TimeoutSeconds)s"
  if ($LASTEXITCODE -ne 0) {
    $podsList = & oc -n $Namespace get pods -l $labelSelector -o name 2>$null
    if ($LASTEXITCODE -eq 0 -and $podsList) {
      foreach ($podRef in $podsList) {
        Write-Host "Recent logs for $podRef" -ForegroundColor Yellow
        & oc -n $Namespace logs $podRef --all-containers=true --tail=120
      }
    }
    throw "Deployment rollout failed after recovery attempt: $DeploymentName"
  }
}

function Ensure-OnlyLatestReplicaSetActive {
  # Scales old ReplicaSets owned by this Deployment down to zero.
  # This prevents old crash-looping revisions from blocking rollout progress.
  param(
    [Parameter(Mandatory = $true)][string]$DeploymentName
  )

  $rsJson = (& oc -n $Namespace get rs -l "app.kubernetes.io/name=rules-enrichment-daemon,app.kubernetes.io/environment=$Environment" -o json 2>$null)
  if ($LASTEXITCODE -ne 0 -or -not $rsJson) {
    return
  }

  $items = ($rsJson | ConvertFrom-Json).items
  if (-not $items -or $items.Count -lt 2) {
    return
  }

  $owned = @()
  foreach ($rs in $items) {
    $hasOwner = $false
    if ($rs.metadata.ownerReferences) {
      foreach ($owner in $rs.metadata.ownerReferences) {
        if ($owner.kind -eq 'Deployment' -and $owner.name -eq $DeploymentName) {
          $hasOwner = $true
          break
        }
      }
    }
    if ($hasOwner) { $owned += $rs }
  }

  if (-not $owned -or $owned.Count -lt 2) {
    return
  }

  $latest = $owned |
    Sort-Object { [int]($_.metadata.annotations.'deployment.kubernetes.io/revision') } -Descending |
    Select-Object -First 1

  foreach ($rs in $owned) {
    if ($rs.metadata.name -ne $latest.metadata.name) {
      $current = 0
      if ($null -ne $rs.spec.replicas) {
        $current = [int]$rs.spec.replicas
      }
      if ($current -gt 0) {
        Write-Host "Scaling down old ReplicaSet $($rs.metadata.name) (replicas=$current)..." -ForegroundColor Yellow
        Invoke-Oc -n $Namespace scale rs/$($rs.metadata.name) --replicas=0
      }
    }
  }
}

if (-not (Get-Command oc -ErrorAction SilentlyContinue)) {
  throw 'Could not find `oc` in PATH. Install OpenShift CLI before continuing.'
}

# Authenticate and select project/namespace.
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
  # Render each manifest into a temp folder for this environment run.
  $raw = Get-Content -Path $file.FullName -Raw
  $rendered = Convert-ManifestContent -Content $raw -Env $Environment
  if ($BuildSource -eq 'Git' -and $file.Name -like '02-*-bc-*.yaml') {
    $rendered = Convert-BuildConfigToGitSource -Content $rendered -RepoUri $GitUri -Ref $GitRef
  }
  $targetName = $file.Name -replace '-test\.yaml$', "-$Environment.yaml"
  Set-Content -Path (Join-Path $renderDir $targetName) -Value $rendered -NoNewline
}

$appBase = "rules-enrichment-daemon-dfn"
$bcName = "$appBase-bc-$Environment"
$isFile = Join-Path $renderDir "01-rules-enrichment-daemon-is-$Environment.yaml"
$bcFile = Join-Path $renderDir "02-rules-enrichment-daemon-bc-$Environment.yaml"
$migrateFile = Join-Path $renderDir "12-rules-daemon-migrate-job-$Environment.yaml"
$coreManifestFiles = Get-ChildItem -Path $renderDir -Filter *.yaml | Where-Object { $_.FullName -ne $migrateFile } | Sort-Object Name

Write-Host "[1/7] Running dry-run validation (client/server)..." -ForegroundColor Cyan
foreach ($manifest in $coreManifestFiles) {
  # Validate both client-side and server-side before real apply.
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
# Keep only latest ReplicaSet active to avoid rollout deadlocks.
Ensure-OnlyLatestReplicaSetActive -DeploymentName "rules-enrichment-daemon-dfn-d-$Environment"

Write-Host "[5/7] Waiting for deployments..." -ForegroundColor Cyan
# Run rollout with built-in diagnostics and one recovery attempt.
Wait-DeploymentRolloutWithRecovery -DeploymentName "rules-enrichment-daemon-dfn-d-$Environment" -AppName "rules-enrichment-daemon" -Env $Environment -TimeoutSeconds $RolloutTimeoutSeconds

if (-not $SkipMigrate) {
  Write-Host "[6/7] Running Alembic migrations..." -ForegroundColor Cyan
  Invoke-Oc delete job rules-daemon-dfn-migrate-$Environment --ignore-not-found=true
  Invoke-Oc apply -f $migrateFile
  Invoke-Oc wait --for=condition=complete --timeout="$($MigrateTimeoutSeconds)s" job/rules-daemon-dfn-migrate-$Environment
  Invoke-Oc logs job/rules-daemon-dfn-migrate-$Environment
} else {
  Write-Host "[6/7] Migrations skipped via -SkipMigrate parameter" -ForegroundColor Yellow
}

Write-Host "[7/7] Running final validation..." -ForegroundColor Cyan
Invoke-Oc get pods
Invoke-Oc get svc
Invoke-Oc get route

try {
  $routeHost = (& oc get route rules-daemon-health-dfn-$Environment -o jsonpath='{.spec.host}')
  if ($LASTEXITCODE -eq 0 -and $routeHost) {
    Write-Host "Health URL: https://$routeHost/health" -ForegroundColor Green
  }
} catch {
  Write-Host 'Could not fetch the health route.' -ForegroundColor Yellow
}

Write-Host "rules-enrichment-daemon ($Environment-dfn) deployment completed in namespace $Namespace." -ForegroundColor Green
