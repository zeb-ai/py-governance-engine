# Z-GRC Governance Engine Proxy - Windows Installer
# Usage: irm https://raw.githubusercontent.com/zeb-ai/z-grc/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

$Repo        = "zeb-ai/z-grc"
$BinaryName  = "z-grc-proxy"
$AssetName   = "z-grc-proxy-windows-x64.zip"
# Where the unpacked one-dir bundle lives
$InstallDir  = "$env:LOCALAPPDATA\Programs\z-grc"
# Inside the zip, contents are under z-grc-proxy-windows-x64\
$BundleSubdir = "z-grc-proxy-windows-x64"

function Write-Info($msg) { Write-Host "==> $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "==> $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "==> $msg" -ForegroundColor Red; exit 1 }

# Get latest release tag from GitHub API
function Get-LatestVersion {
    Write-Info "Fetching latest release..."
    try {
        $release = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest"
        return $release.tag_name
    } catch {
        Write-Err "Could not fetch latest version: $_"
    }
}

# Download zip, extract, surface launcher
function Install-Bundle($version) {
    $url     = "https://github.com/$Repo/releases/download/$version/$AssetName"
    $tmpZip  = Join-Path $env:TEMP "$AssetName"
    $tmpDir  = Join-Path $env:TEMP "z-grc-extract-$([Guid]::NewGuid().ToString('N'))"

    Write-Info "Downloading from $url"
    try {
        Invoke-WebRequest -Uri $url -OutFile $tmpZip -UseBasicParsing
    } catch {
        Write-Err "Download failed: $_"
    }

    Write-Info "Extracting bundle..."
    if (Test-Path $tmpDir) { Remove-Item -Recurse -Force $tmpDir }
    New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null
    Expand-Archive -Path $tmpZip -DestinationPath $tmpDir -Force

    # Wipe any prior install so _internal\ doesn't accumulate stale files
    if (Test-Path $InstallDir) { Remove-Item -Recurse -Force $InstallDir }
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null

    # Move the inner folder contents into $InstallDir
    $extractedRoot = Join-Path $tmpDir $BundleSubdir
    if (-not (Test-Path $extractedRoot)) {
        Write-Err "Bundle
