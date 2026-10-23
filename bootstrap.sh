#!/usr/bin/env bash
# bootstrap.sh — deja una MV Rocky/RHEL 9 x86_64 lista para el agente de Star-CCM+.
#
# Uso (como usuario con sudo, no como root):
#   STARCCM_TGZ=~/Simcenter_STAR-CCM+_2606.0002-Linux-x86_64-double.tar.gz \
#   PODKEY=XXXXXXXX \
#   bash bootstrap.sh
#
# Idempotente: se puede volver a correr sin romper nada.
set -euo pipefail

STARCCM_TGZ="${STARCCM_TGZ:?Falta STARCCM_TGZ=ruta al .tar.gz de Star-CCM+}"
PODKEY="${PODKEY:?Falta PODKEY=clave Power-on-Demand}"
LICPATH="${LICPATH:-1999@flex.cd-adapco.com}"
INSTALL_DIR="${INSTALL_DIR:-/opt/Siemens}"
PROJECT_DIR="${PROJECT_DIR:-$HOME/starccm-agent}"
ENV_FILE="$HOME/.starccm-agent.env"

log() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }

# ---------------------------------------------------------------- checks
[[ "$(uname -m)" == "x86_64" ]] || { echo "Esta MV no es x86_64 ($(uname -m)). El paquete x86_64 no sirve aquí."; exit 1; }
[[ -f "$STARCCM_TGZ" ]] || { echo "No existe $STARCCM_TGZ"; exit 1; }
command -v sudo >/dev/null || { echo "Necesito sudo"; exit 1; }

# ---------------------------------------------------------------- paquetes
log "Paquetes del sistema"
# Las libs X/GL hacen falta aunque no haya escritorio: Star-CCM+ las carga para renderizar escenas a imagen.
sudo dnf install -y git python3 python3-pip tar gzip which curl \
  libXext libXrender libXtst libXi libXt libSM libICE libGLU mesa-libGL mesa-libEGL \
  fontconfig freetype

# ---------------------------------------------------------------- Claude Code
if ! command -v claude >/dev/null; then
  log "Instalando Claude Code"
  curl -fsSL https://claude.ai/install.sh | bash
  export PATH="$HOME/.local/bin:$PATH"
fi
claude --version

# ---------------------------------------------------------------- Star-CCM+
if ! ls "$INSTALL_DIR"/*/STAR-CCM+*/star/bin/starccm+ >/dev/null 2>&1; then
  log "Descomprimiendo Star-CCM+"
  WORK="$(mktemp -d)"
  tar -xzf "$STARCCM_TGZ" -C "$WORK"
  INSTALLER="$(find "$WORK" -name 'STAR-CCM+*.sh' | head -1)"
  [[ -n "$INSTALLER" ]] || { echo "No encontré el instalador .sh dentro del tar"; exit 1; }
  chmod +x "$INSTALLER"
  log "Instalando Star-CCM+ en $INSTALL_DIR (silencioso)"
  # ponytail: flags de instalación silenciosa estándar de Siemens. Si el instalador se queja,
  # correrlo a mano sin -i silent y aceptar los defaults.
  sudo "$INSTALLER" -i silent \
    -DINSTALLDIR="$INSTALL_DIR" \
    -DINSTALLFLEX=false \
    -DADDSYSTEMPATH=true \
    -DCOMPUTE_NODE=false \
    -DNODOC=false
  rm -rf "$WORK"
fi
STARCCM_BIN="$(ls "$INSTALL_DIR"/*/STAR-CCM+*/star/bin/starccm+ | sort | tail -1)"
STARCCM_HOME="$(dirname "$(dirname "$(dirname "$STARCCM_BIN")")")"
sudo ln -sf "$STARCCM_BIN" /usr/local/bin/starccm+
log "Star-CCM+ en $STARCCM_HOME"
starccm+ -version | head -3

# ---------------------------------------------------------------- licencia PoD
log "Probando licencia Power-on-Demand"
LICTEST="$(mktemp -d)"
cat > "$LICTEST/LicenseCheck.java" <<'EOF'
import star.common.*;
public class LicenseCheck extends StarMacro {
  public void execute() { getActiveSimulation().println("LICENSE_OK"); }
}
EOF
if ( cd "$LICTEST" && starccm+ -batch LicenseCheck.java -power -podkey "$PODKEY" -licpath "$LICPATH" 2>&1 | tee lic.log | grep -q LICENSE_OK ); then
  log "Licencia OK"
else
  echo "La licencia no respondió. Revisa $LICTEST/lic.log, la clave, y que salga tráfico a $LICPATH"; exit 1
fi
rm -rf "$LICTEST"

# ---------------------------------------------------------------- proyecto
log "Proyecto en $PROJECT_DIR"
mkdir -p "$PROJECT_DIR"/{recipes,cases,sims}
if [[ -d "$(dirname "$0")/recipes" && "$(cd "$(dirname "$0")" && pwd)" != "$PROJECT_DIR" ]]; then
  cp -n "$(dirname "$0")"/{CLAUDE.md,PRIMER-PROMPT.md,.gitignore} "$PROJECT_DIR"/ 2>/dev/null || true
  cp -rn "$(dirname "$0")"/recipes/. "$PROJECT_DIR"/recipes/ 2>/dev/null || true
fi
cd "$PROJECT_DIR"
[[ -d .git ]] || git init -q
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q "mcp[cli]" anthropic

# ---------------------------------------------------------------- env
cat > "$ENV_FILE" <<EOF
export STARCCM_HOME="$STARCCM_HOME"
export STARCCM_PODKEY="$PODKEY"
export STARCCM_LICPATH="$LICPATH"
export STARCCM_PORT=47827
export STARCCM_NP=$(( $(nproc) > 2 ? $(nproc) - 2 : 1 ))
export STARCCM_AGENT_DIR="$PROJECT_DIR"
EOF
chmod 600 "$ENV_FILE"
grep -q starccm-agent.env "$HOME/.bashrc" || echo "source $ENV_FILE" >> "$HOME/.bashrc"

log "Listo"
cat <<EOF

Siguiente:
  source $ENV_FILE
  cd $PROJECT_DIR
  claude            # login la primera vez
  # pega el contenido de PRIMER-PROMPT.md

Doc de la API Java (para la tool docs_search): $STARCCM_HOME/doc
EOF
