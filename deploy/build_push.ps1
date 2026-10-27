# Builds the AIBAL image and pushes it to the e-INFRA (CERIT-SC) Harbor registry.
# Needs Docker Desktop and a prior "docker login cerit.io" (user name + CLI secret from https://hub.cerit.io).
#   powershell -ExecutionPolicy Bypass -File deploy\build_push.ps1 -User <your-harbor-user>
# Prints the image name to put into deploy/k8s/app.yaml (or to use with kubectl set image).
param(
    [Parameter(Mandatory = $true)][string]$User,
    [string]$Registry = "cerit.io",
    [string]$Tag = ""
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Push-Location $repo
try {
    if (-not $Tag) {
        # the commit the image is built from; "-dirty" when there are uncommitted changes
        $Tag = (git rev-parse --short HEAD).Trim()
        if (git status --porcelain) { $Tag = "$Tag-dirty" }
    }
    $image = "$Registry/$($User.ToLower())/aibal:$Tag"
    docker build -t $image .
    if ($LASTEXITCODE -ne 0) { throw "docker build failed" }
    docker push $image
    if ($LASTEXITCODE -ne 0) { throw "docker push failed (did you run 'docker login $Registry'?)" }
    Write-Host ""
    Write-Host "Pushed $image"
    Write-Host "Deploy it with:  kubectl set image deployment/aibal app=$image"
}
finally {
    Pop-Location
}
