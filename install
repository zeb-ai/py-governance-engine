#!/usr/bin/env bash
set -euo pipefail

# Z-GRC Governance Engine Proxy - Unix Installer
# Usage: curl -fsSL https://raw.githubusercontent.com/zeb-ai/z-grc/main/install.sh | bash

REPO="zeb-ai/z-grc"
BINARY_NAME="z-grc-proxy"
# Where the unpacked one-dir bundle lives (binary + _internal/ siblings)
BUNDLE_DIR="${BUNDLE_DIR:-$HOME/.local/share/z-grc}"
# Where we symlink the launcher so it lands on PATH
INSTALL_DIR="${INSTALL_DIR:-$HOME/.local/bin}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}==>${NC} $1"; }
warn()  { echo -e "${YELLOW}==>${NC} $1"; }
error() { echo -e "${RED}==>${NC} $1" >&2; exit 1; }

# Detect OS and architecture
detect_platform() {
    OS="$(uname -s)"
    ARCH="$(uname -m)"

    case "$OS" in
        Darwin)
            case "$ARCH" in
                arm64|aarch64) PLATFORM="macos-arm64" ;;
                *) error "Unsupported macOS architecture: $ARCH (only Apple Silicon is supported)" ;;
            esac
            ;;
        Linux)
            case "$ARCH" in
                x86_64|amd64) PLATFORM="linux-x86_64" ;;
                aarch64|arm64) PLATFORM="linux-arm64" ;;
                *) error "Unsupported Linux architecture: $ARCH" ;;
            esac
            ;;
        *)
            error "Unsupported OS: $OS. Use install.ps1 for Windows."
            ;;
    esac

    ASSET_NAME="${BINARY_NAME}-${PLATFORM}.tar.gz"
}

# Check required tools
check_dependencies() {
    for cmd in curl tar; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            error "Required command not found: $cmd"
        fi
    done
}

# Get the latest release version from GitHub
get_latest_version() {
    info "Fetching latest release..."
    VERSION=$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" \
        | grep '"tag_name"' \
        | head -1 \
        | sed -E 's/.*"([^"]+)".*/\1/')

    if [ -z "$VERSION" ]; then
        error "Could not determine latest version. Check your internet connection."
    fi
    info "Latest version: $VERSION"
}

# Download archive, extract bundle, symlink launcher
install_binary() {
    DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/${ASSET_NAME}"
    TMP_DIR="$(mktemp -d)"
    trap 'rm -rf "$TMP_DIR"' EXIT
    TMP_ARCHIVE="${TMP_DIR}/${ASSET_NAME}"

    info "Downloading from $DOWNLOAD_URL"
    if ! curl -fsSL -o "$TMP_ARCHIVE" "$DOWNLOAD_URL"; then
        error "Download failed. Asset may not exist for your platform."
    fi

    info "Extracting bundle..."
    # Archive contents look like: z-grc-proxy-<platform>/{z-grc-proxy,_internal/...}
    # Wipe any old bundle so we don't leave stale _internal files behind.
    if [ -d "$BUNDLE_DIR" ]; then
        rm -rf "$BUNDLE_DIR"
    fi
    mkdir -p "$BUNDLE_DIR"
    # --strip-components=1 drops the top-level z-grc-proxy-<platform>/ folder
    tar -xzf "$TMP_ARCHIVE" -C "$BUNDLE_DIR" --strip-components=1

    if [ ! -f "${BUNDLE_DIR}/${BINARY_NAME}" ]; then
        error "Bundle layout unexpected: ${BUNDLE_DIR}/${BINARY_NAME} not found after extract."
    fi
    chmod +x "${BUNDLE_DIR}/${BINARY_NAME}"

    # Symlink launcher onto PATH
    mkdir -p "$INSTALL_DIR"
    ln -sf "${BUNDLE_DIR}/${BINARY_NAME}" "${INSTALL_DIR}/${BINARY_NAME}"

    info "Bundle installed at:  $BUNDLE_DIR"
    info "Launcher symlinked at: $INSTALL_DIR/$BINARY_NAME"
}

# Verify installation
verify() {
    if command -v "$BINARY_NAME" >/dev/null 2>&1; then
        info "Installation successful!"
        info "Run: $BINARY_NAME --api-key=zgrc_xxx"
    else
        warn "Installed but $INSTALL_DIR is not on PATH."
        warn "Add this to your shell config (~/.zshrc or ~/.bashrc):"
        warn "    export PATH=\"$INSTALL_DIR:\$PATH\""
    fi
}

main() {
    check_dependencies
    detect_platform
    get_latest_version
    install_binary
    verify
}

main
