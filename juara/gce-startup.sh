#!/bin/bash
# GCE startup-script (solo primer arranque de instancia nueva): git, uv, clone del repo.
set -euo pipefail

MARKER="/var/lib/dmeyf2026-gce-bootstrap.done"
REPO_URL="https://github.com/jgjuara/dmeyf2026.git"
REPO_DIRNAME="dmeyf2026"

log() { logger -t gce-startup "$*"; }

if [ -f "$MARKER" ]; then
  exit 0
fi

ensure_git() {
  if command -v git >/dev/null 2>&1; then
    return 0
  fi
  log "instalando git"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq git ca-certificates curl
}

ensure_uv() {
  local uv_bin="/usr/local/bin/uv"
  if command -v uv >/dev/null 2>&1; then
    return 0
  fi
  if [ -x "$uv_bin" ]; then
    return 0
  fi
  # Instalador flat: UV_INSTALL_DIR es el directorio del binario, no el prefijo tipo /usr/local.
  log "instalando uv en ${uv_bin}"
  export UV_INSTALL_DIR=/usr/local/bin
  export UV_NO_MODIFY_PATH=1
  if ! curl -fsSL https://astral.sh/uv/install.sh | sh; then
    log "error: install.sh de uv falló"
    exit 1
  fi
  if [ ! -x "$uv_bin" ]; then
    log "error: uv no ejecutable en ${uv_bin}"
    exit 1
  fi
  log "uv ok: $("$uv_bin" --version)"
}

clone_repo() {
  local login_user repo_dir
  login_user="$(getent passwd | awk -F: '$3 >= 1000 && $3 < 65534 && $6 ~ /^\/home\// { print $1; exit }')"
  if [ -z "$login_user" ]; then
    log "error: no hay usuario con home (imagen no soportada)"
    exit 1
  fi
  repo_dir="/home/${login_user}/${REPO_DIRNAME}"
  if [ -d "${repo_dir}/.git" ]; then
    log "repo ya presente en ${repo_dir}"
    return 0
  fi
  log "clonando ${REPO_URL} → ${repo_dir}"
  sudo -u "${login_user}" git clone --depth 1 "${REPO_URL}" "${repo_dir}"
}

ensure_git
ensure_uv
clone_repo

touch "$MARKER"
log "bootstrap completado"
