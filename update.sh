#!/bin/bash
#
# Proxmox Lab GUI / Netlab Tools - One-Command Updater
# Usage: curl -sSL https://raw.githubusercontent.com/Snappieuk/netlab-tools/main/update.sh | sudo bash
#

set -Eeuo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SERVICE_NAME="${SERVICE_NAME:-proxmox-gui}"

on_error() {
    local exit_code=$?
    local line_no=${1:-unknown}
    echo -e "${RED}[ERROR] Update failed (line ${line_no}, exit ${exit_code})${NC}"
    echo -e "${YELLOW}  Re-run with tracing:${NC}"
    echo -e "${YELLOW}  bash -x update.sh${NC}"
    exit "$exit_code"
}
trap 'on_error $LINENO' ERR

echo -e "${BLUE}========================================================${NC}"
echo -e "${BLUE}      Proxmox Lab GUI - Automated Updater${NC}"
echo -e "${BLUE}========================================================${NC}"
echo ""

if [[ "$(uname -s)" != "Linux" ]]; then
    echo -e "${RED}[ERROR] This updater supports Linux only${NC}"
    exit 1
fi

if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}[ERROR] This script must be run as root${NC}"
    echo -e "${YELLOW}  Please run with sudo${NC}"
    exit 1
fi

if ! command -v systemctl >/dev/null 2>&1 || [ ! -d /run/systemd/system ]; then
    echo -e "${RED}[ERROR] systemd is required${NC}"
    exit 1
fi

if ! command -v git >/dev/null 2>&1; then
    echo -e "${RED}[ERROR] git is not installed${NC}"
    exit 1
fi

if ! systemctl list-unit-files | grep -q "^${SERVICE_NAME}\.service"; then
    echo -e "${RED}[ERROR] Service '${SERVICE_NAME}' not found${NC}"
    echo -e "${YELLOW}  Install first using install.sh, then run this updater.${NC}"
    exit 1
fi

echo -e "${GREEN}[OK] Found service: ${SERVICE_NAME}${NC}"

APP_DIR="${APP_DIR:-}"
if [[ -z "${APP_DIR}" ]]; then
    APP_DIR="$(systemctl show -p WorkingDirectory --value "${SERVICE_NAME}" 2>/dev/null || true)"
fi
if [[ -z "${APP_DIR}" ]]; then
    APP_DIR="/opt/proxmox-lab-gui"
fi

if [[ ! -d "${APP_DIR}" ]]; then
    echo -e "${RED}[ERROR] App directory not found: ${APP_DIR}${NC}"
    echo -e "${YELLOW}  If installed elsewhere, run with:${NC}"
    echo -e "${YELLOW}  APP_DIR=/your/path bash update.sh${NC}"
    exit 1
fi

if [[ ! -d "${APP_DIR}/.git" ]]; then
    echo -e "${RED}[ERROR] ${APP_DIR} is not a git repository${NC}"
    exit 1
fi

VENV_PIP="${APP_DIR}/venv/bin/pip"
VENV_PYTHON="${APP_DIR}/venv/bin/python3"

if [[ ! -x "${VENV_PIP}" || ! -x "${VENV_PYTHON}" ]]; then
    echo -e "${RED}[ERROR] Virtual environment not found at ${APP_DIR}/venv${NC}"
    exit 1
fi

echo -e "${BLUE}-> Updating repository in ${APP_DIR}...${NC}"
cd "${APP_DIR}"

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "${CURRENT_BRANCH}" == "HEAD" || -z "${CURRENT_BRANCH}" ]]; then
    CURRENT_BRANCH="main"
fi

echo -e "${BLUE}[INFO] Fetching latest code from origin/${CURRENT_BRANCH}...${NC}"
git fetch origin
git pull --ff-only origin "${CURRENT_BRANCH}"

echo -e "${BLUE}-> Installing Python dependencies...${NC}"
"${VENV_PIP}" install -r requirements.txt

if [[ -f "migrate_db.py" ]]; then
    echo -e "${BLUE}-> Running database migrations...${NC}"
    "${VENV_PYTHON}" migrate_db.py
fi

echo -e "${BLUE}-> Restarting service...${NC}"
systemctl daemon-reload
systemctl restart "${SERVICE_NAME}"

echo -e "${GREEN}[OK] Update complete${NC}"
echo -e "${BLUE}-> Service status:${NC}"
systemctl status "${SERVICE_NAME}" --no-pager

echo ""
echo -e "${GREEN}Done. Health check:${NC} curl -fsS http://127.0.0.1:8080/health"
