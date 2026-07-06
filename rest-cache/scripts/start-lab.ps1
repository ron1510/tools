param(
    [string]$ClusterName = "rest-cache-lab",
    [string]$Namespace = "default",
    [int]$LocalPort = 8080,
    [string]$ImageTag = "e2e",
    [switch]$SkipBuild,
    [switch]$ForegroundPortForward
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RepoRoot "lab\backend"
$StateDir = Join-Path $RepoRoot ".lab"
$LogPath = Join-Path $StateDir "port-forward.log"
$ErrPath = Join-Path $StateDir "port-forward.err.log"
$PidPath = Join-Path $StateDir "port-forward.pid"
$Image = "rest-cache-lab-backend:$ImageTag"
$Context = "kind-$ClusterName"

function Require-Command {
    param([string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found on PATH."
    }
}

function Write-Step {
    param([string]$Message)

    Write-Host ""
    Write-Host "==> $Message"
}

Require-Command "docker"
Require-Command "kind"
Require-Command "kubectl"
Require-Command "helm"

New-Item -ItemType Directory -Force -Path $StateDir | Out-Null

Write-Step "Ensuring kind cluster '$ClusterName' exists"
$clusters = kind get clusters
if ($clusters -notcontains $ClusterName) {
    kind create cluster --name $ClusterName
} else {
    kubectl config use-context $Context | Out-Null
}

Write-Step "Checking Kubernetes API"
kubectl cluster-info --context $Context | Out-Null
kubectl config use-context $Context | Out-Null

if (-not $SkipBuild) {
    Write-Step "Building lab backend image '$Image'"
    docker build -t $Image $BackendDir
}

Write-Step "Loading lab backend image into kind"
kind load docker-image $Image --name $ClusterName

Write-Step "Installing lab backend chart"
helm upgrade --install rest-cache-lab "$RepoRoot\charts\rest-cache-lab" `
    --namespace $Namespace `
    --set image.repository=rest-cache-lab-backend `
    --set image.tag=$ImageTag `
    --set image.pullPolicy=IfNotPresent

Write-Step "Installing Varnish REST cache chart"
helm upgrade --install rest-cache "$RepoRoot\charts\rest-cache" `
    --namespace $Namespace `
    --set varnish.backend.host=rest-cache-lab.$Namespace.svc.cluster.local `
    --set varnish.backend.port=8080

Write-Step "Waiting for deployments"
kubectl rollout status deployment/rest-cache-lab --namespace $Namespace --timeout=120s
kubectl rollout status deployment/rest-cache-varnish --namespace $Namespace --timeout=120s

Write-Step "Starting port-forward localhost:$LocalPort -> svc/rest-cache:80"
if (Test-Path $PidPath) {
    $oldPid = Get-Content $PidPath -ErrorAction SilentlyContinue
    if ($oldPid -and (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) {
        Write-Host "Existing port-forward is already running with PID $oldPid."
        Write-Host "URL: http://127.0.0.1:$LocalPort"
        exit 0
    }
}

if ($ForegroundPortForward) {
    Write-Host "Press Ctrl+C to stop the port-forward."
    kubectl port-forward svc/rest-cache "$LocalPort`:80" --namespace $Namespace
} else {
    $process = Start-Process `
        -FilePath "kubectl" `
        -ArgumentList @("port-forward", "svc/rest-cache", "$LocalPort`:80", "--namespace", $Namespace) `
        -WindowStyle Hidden `
        -RedirectStandardOutput $LogPath `
        -RedirectStandardError $ErrPath `
        -PassThru

    Set-Content -Path $PidPath -Value $process.Id
    Start-Sleep -Seconds 3

    if ($process.HasExited) {
        Get-Content $ErrPath -ErrorAction SilentlyContinue
        throw "Port-forward exited early. See $ErrPath"
    }

    Write-Host "Port-forward PID: $($process.Id)"
    Write-Host "URL: http://127.0.0.1:$LocalPort"
    Write-Host "Logs: $LogPath"
}

Write-Host ""
Write-Host "Try:"
Write-Host "  curl.exe -i http://127.0.0.1:$LocalPort/api/v1/resources/123"
Write-Host "  curl.exe -i http://127.0.0.1:$LocalPort/api/v1/resources/123"
