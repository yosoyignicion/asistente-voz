#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
VENV_DIR="$INSTALL_DIR/env_asistente"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

NO_GUI=false
for arg in "$@"; do
    case "$arg" in
        --no-gui) NO_GUI=true ;;
        --voice=*) VOICE_ARG="${arg#*=}" ;;
        --model=*) MODEL_ARG="${arg#*=}" ;;
        --help|-h)
            echo "Uso: bash instalar.sh [opciones]"
            echo "  --no-gui        Instalacion silenciosa (sin interfaz grafica)"
            echo "  --voice=NOMBRE  Voz TTS (default: ef_dora)"
            echo "  --model=NOMBRE  Nombre del modelo Ollama (default: asistente_voz)"
            exit 0
            ;;
    esac
done

echo "============================================"
echo "  Asistente de Voz Local — Instalador"
if $NO_GUI; then
    echo "  Modo: silencioso"
else
    echo "  Modo: interactivo"
fi
echo "============================================"
echo ""

# ── 0. Preparacion del entorno Ollama ────────────────────────────────────
echo -e "${YELLOW}[0/3]${NC} Preparacion del entorno Ollama..."
echo "Este paso verifica Ollama, descarga el modelo base y crea asistente_voz."
echo "Puedes saltarlo si ya tienes todo configurado."
read -r -p "¿Ejecutar preparador de entorno? [S/n]: " run_prep
if [[ -z "$run_prep" || "$run_prep" =~ ^[Ss]$ ]]; then
    if [ -f "$INSTALL_DIR/scripts/preparar_entorno.sh" ]; then
        bash "$INSTALL_DIR/scripts/preparar_entorno.sh" || echo -e "${YELLOW}  ⚠ Preparacion cancelada o fallida.${NC}"
    else
        echo -e "${YELLOW}  ⚠ scripts/preparar_entorno.sh no encontrado${NC}"
    fi
fi

# ── 1. Dependencias del sistema ──────────────────────────────────────────
echo -e "${YELLOW}[1/3]${NC} Dependencias del sistema..."

MISSING=""
for pkg in portaudio19-dev python3-pyaudio espeak-ng; do
    if ! dpkg -l "$pkg" &>/dev/null; then
        MISSING="$MISSING $pkg"
    else
        echo "  ✓ $pkg"
    fi
done

if [ -n "$MISSING" ]; then
    echo "→ Instalando: $MISSING"
    sudo apt-get install -y $MISSING 2>/dev/null || {
        echo -e "${YELLOW}  ⚠ No se pudo instalar. Instala manualmente:${NC}"
        echo "    sudo apt install $MISSING"
    }
fi

# ── 2. Entorno virtual Python ───────────────────────────────────────────
echo ""
echo -e "${YELLOW}[2/3]${NC} Entorno virtual Python..."

if [ ! -d "$VENV_DIR" ]; then
    echo "→ Creando venv..."
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
echo "→ Instalando dependencias Python..."
pip install --upgrade pip -q 2>/dev/null
pip install -r "$INSTALL_DIR/requirements.txt" -q 2>&1 | tail -1
echo "  ✓ Dependencias Python instaladas"

# ── 3. Configuracion interactiva ─────────────────────────────────────────
echo ""
echo -e "${YELLOW}[3/3]${NC} Configuracion..."

GUI_ARGS=""
if $NO_GUI; then
    GUI_ARGS="--no-gui"
fi
if [ -n "${VOICE_ARG:-}" ]; then
    GUI_ARGS="$GUI_ARGS --voice $VOICE_ARG"
fi
if [ -n "${MODEL_ARG:-}" ]; then
    GUI_ARGS="$GUI_ARGS --model $MODEL_ARG"
fi

# shellcheck disable=SC2086
if ! python "$INSTALL_DIR/instalar_gui.py" $GUI_ARGS; then
    echo ""
    echo -e "${RED}Error:${NC} El instalador encontro un problema."
    echo "Verifica que Ollama este corriendo y vuelve a intentarlo."
    echo ""
    echo "Alternativa sin interfaz grafica:"
    echo "  bash $INSTALL_DIR/instalar.sh --no-gui"
    exit 1
fi

if $NO_GUI; then
    echo ""
    echo "============================================"
    echo -e "${GREEN}  Instalacion completada.${NC}"
    echo "  Lanzar: bash $INSTALL_DIR/bin/asistente-voz"
    echo "============================================"
fi
