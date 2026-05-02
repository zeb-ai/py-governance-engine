#!/usr/bin/env bash
set -euo pipefail

# Governance Engine Proxy - Unix Installer
# Usage: curl -fsSL https://raw.githubusercontent.com/zeb-ai/z-grc/main/install.sh | bash

REPO="zeb-ai/z-grc"
BINARY_NAME="z-grc-proxy"
INSTALL_DIR="${INSTALL_DIR:-/usr/local/bin}"

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
            PLATFORM="macos-arm64"
            ;;
        Linux)
            if [ "$ARCH" = "x86_64" ]; then
                PLATFORM="linux-x86_64"
            elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
                PLATFORM="linux-arm64"
            else
                error "Unsupported Linux architecture: $ARCH"
            fi
            ;;
        *)
            error "Unsupported OS: $OS. Use install.ps1 for Windows."
            ;;
    esac

    ASSET_NAME="${BINARY_NAME}-${PLATFORM}"
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

# Download and install
install_binary() {
    DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/${ASSET_NAME}"
    TMP_FILE="$(mktemp)"

    info "Downloading from $DOWNLOAD_URL"
    if ! curl -fsSL -o "$TMP_FILE" "$DOWNLOAD_URL"; then
        error "Download failed. Asset may not exist for your platform."
    fi

    chmod +x "$TMP_FILE"

    # Check if we need sudo
    if [ -w "$INSTALL_DIR" ]; then
        mv "$TMP_FILE" "$INSTALL_DIR/$BINARY_NAME"
    else
        warn "Need sudo to write to $INSTALL_DIR"
        sudo mv "$TMP_FILE" "$INSTALL_DIR/$BINARY_NAME"
    fi

    info "Installed to $INSTALL_DIR/$BINARY_NAME"
}

# Verify installation
verify() {
    if command -v "$BINARY_NAME" >/dev/null 2>&1; then
        info "Installation successful!"
        info "Run: $BINARY_NAME --api-key=grc_xxx"
    else
        warn "Binary installed but not on PATH. Add $INSTALL_DIR to your PATH."
    fi
}

main() {
    detect_platform
    get_latest_version
    install_binary
    verify
}

main