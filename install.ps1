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
    # Use C:\zgrc-tmp to avoid Windows MAX_PATH (260 char) issues with deeply nested files
    $tmpDir  = "C:\zgrc-tmp"

    Write-Info "Downloading from $url"
    try {
        Invoke-WebRequest -Uri $url -OutFile $tmpZip -UseBasicParsing
    } catch {
        Write-Err "Download failed: $_"
    }

    Write-Info "Extracting bundle..."
    if (Test-Path $tmpDir) { Remove-Item -Recurse -Force $tmpDir }
    New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null

    # Extract without overwriting to avoid Remove-Item errors inside the archive
    try {
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [System.IO.Compression.ZipFile]::ExtractToDirectory($tmpZip, $tmpDir)
    } catch {
        Write-Err "Extraction failed: $_"
    }

    # Wipe any prior install so _internal\ doesn't accumulate stale files
    if (Test-Path $InstallDir) { Remove-Item -Recurse -Force $InstallDir }
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null

    # Move the inner folder contents into $InstallDir
    $extractedRoot = Join-Path $tmpDir $BundleSubdir
    if (-not (Test-Path $extractedRoot)) {
        Write-Err "Bundle structure unexpected - could not find $BundleSubdir inside archive"
    }

    Get-ChildItem -Path $extractedRoot | Move-Item -Destination $InstallDir -Force

    Remove-Item $tmpZip -Force -ErrorAction SilentlyContinue
    Remove-Item $tmpDir -Recurse -Force -ErrorAction SilentlyContinue

    Write-Info "Installed to: $InstallDir"
}

# Add to PATH if not already there
function Add-ToPath {
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -notlike "*$InstallDir*") {
        Write-Info "Adding $InstallDir to your PATH..."
        [Environment]::SetEnvironmentVariable(
            "Path",
            "$userPath;$InstallDir",
            "User"
        )
        $env:Path = "$env:Path;$InstallDir"
        Write-Info "PATH updated. You may need to restart your shell."
    } else {
        Write-Info "Already in PATH."
    }
}

# Main execution
$version = Get-LatestVersion
Write-Info "Installing Z-GRC Proxy $version..."
Install-Bundle $version
Add-ToPath
Write-Info "Installation complete! Run 'z-grc-proxy --help' to get started."
