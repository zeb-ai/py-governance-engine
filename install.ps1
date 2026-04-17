# Governance Engine Proxy - Windows Installer
# Usage: irm https://raw.githubusercontent.com/zeb-ai/py-governance-engine/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

$Repo = "zeb-ai/py-governance-engine"
$BinaryName = "governance-engine-proxy"
$AssetName = "governance-engine-proxy-windows-x64.exe"
$InstallDir = "$env:LOCALAPPDATA\Programs\GovernanceEngine"

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

# Download and install
function Install-Binary($version) {
    $url = "https://github.com/$Repo/releases/download/$version/$AssetName"
    $targetPath = Join-Path $InstallDir "$BinaryName.exe"

    if (-not (Test-Path $InstallDir)) {
        New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    }

    Write-Info "Downloading from $url"
    try {
        Invoke-WebRequest -Uri $url -OutFile $targetPath -UseBasicParsing
    } catch {
        Write-Err "Download failed: $_"
    }

    Write-Info "Installed to $targetPath"
    return $targetPath
}

# Add install directory to user PATH if missing
function Add-ToPath {
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -notlike "*$InstallDir*") {
        Write-Info "Adding $InstallDir to PATH"
        [Environment]::SetEnvironmentVariable("Path", "$userPath;$InstallDir", "User")
        Write-Warn "Restart your terminal for PATH changes to take effect."
    }
}

function Main {
    $version = Get-LatestVersion
    Write-Info "Latest version: $version"
    $path = Install-Binary $version
    Add-ToPath
    Write-Info "Installation complete!"
    Write-Info "Run: $BinaryName --help (after restarting your terminal)"
}

Main
