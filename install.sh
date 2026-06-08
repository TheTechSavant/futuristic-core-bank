#!/bin/bash
# install.sh - One-click installer for Futuristic Core Banking Platform
# Usage: curl -fsSL https://raw.githubusercontent.com/TheTechSavant/futuristic-core-bank/main/install.sh | sudo bash

set -e

# Must run as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root or with sudo:"
    echo "  curl ... | sudo bash"
    exit 1
fi

# --- Configuration (change these or pass as env vars) ---
DOMAIN="${DOMAIN:-example.com}"
EMAIL="${EMAIL:-admin@example.com}"
REPO_URL="https://github.com/TheTechSavant/futuristic-core-bank.git"
APP_DIR="/opt/core-bank"

echo "=========================================="
echo "  One-Click Installer for Core Banking"
echo "=========================================="
echo "Domain: $DOMAIN"
echo "Email:  $EMAIL"
echo ""

# If domain/email are still defaults, ask interactively
if [ "$DOMAIN" = "example.com" ]; then
    read -p "Enter your domain (e.g., bank.mydomain.com): " DOMAIN
fi
if [ "$EMAIL" = "admin@example.com" ]; then
    read -p "Enter your email for Let's Encrypt: " EMAIL
fi

# 1. Install git if missing
apt-get update
apt-get install -y git

# 2. Clone repository
echo "Cloning repository..."
if [ -d "$APP_DIR" ]; then
    echo "Removing existing $APP_DIR..."
    rm -rf "$APP_DIR"
fi
git clone "$REPO_URL" "$APP_DIR"
cd "$APP_DIR"

# 3. Export variables and run deploy.sh
export DOMAIN
export EMAIL
chmod +x deploy.sh
echo "Starting deployment..."
./deploy.sh