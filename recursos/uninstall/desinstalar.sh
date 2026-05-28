#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "============================================"
echo -e "${RED}  Desinstalador — Asistente de Voz${NC}"
echo "  $PROJECT_DIR"
echo "============================================"
echo ""

# ── Detener procesos activos ──────────────────────────────────────────
if pgrep -f "python.*main.py" &>/dev/null; then
    echo -e "${YELLOW}[0/4]${NC} Deteniendo procesos activos..."
    pkill -f "python.*main.py" 2>/dev/null || true
    sleep 1
    echo "  ✓ Procesos detenidos"
    echo ""
fi

# ── Confirmación ──────────────────────────────────────────────────────
echo -e "${YELLOW}⚠  Esto eliminará la instalación del Asistente de Voz.${NC}"
read -r -p "¿Continuar? [s/N] " confirmacion
if [[ "${confirmacion,,}" != "s" && "${confirmacion,,}" != "si" && "${confirmacion,,}" != "y" && "${confirmacion,,}" != "yes" ]]; then
    echo "  • Cancelado"
    exit 0
fi

comando_trash() {
    if command -v gio &>/dev/null; then
        gio trash "$1" 2>/dev/null && return 0
    fi
    local basename
    basename="$(basename "$1")"
    local trash_dir="$HOME/.local/share/Trash/files"
    mkdir -p "$trash_dir"
    mv "$1" "$trash_dir/$basename" 2>/dev/null && return 0
    echo -e "${RED}  ✗ No se pudo mover a la papelera: $1${NC}"
    return 1
}

# ── 1. Modelo Ollama ─────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[1/4]${NC} Eliminando modelo Ollama..."

if command -v ollama &>/dev/null && ollama list 2>/dev/null | grep -q "asistente_voz"; then
    ollama rm asistente_voz:latest || true
    echo "  ✓ Modelo asistente_voz:latest eliminado"
else
    echo "  • Modelo no encontrado, omitiendo"
fi

# ── 2. Accesos directos ──────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[2/4]${NC} Moviendo accesos directos a la papelera..."

DESKTOP_FILE="$HOME/.local/share/applications/asistente-voz.desktop"
AUTOSTART_FILE="$HOME/.config/autostart/asistente-voz.desktop"

if [ -f "$DESKTOP_FILE" ] || [ -L "$DESKTOP_FILE" ]; then
    comando_trash "$DESKTOP_FILE" && echo "  ✓ $DESKTOP_FILE"
else
    echo "  • Acceso directo no encontrado"
fi

if [ -f "$AUTOSTART_FILE" ] || [ -L "$AUTOSTART_FILE" ]; then
    comando_trash "$AUTOSTART_FILE" && echo "  ✓ $AUTOSTART_FILE"
else
    echo "  • Auto-inicio no encontrado"
fi

# ── 3. Proyecto ──────────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[3/4]${NC} Proyecto"

if [ -d "$PROJECT_DIR" ]; then
    echo "  Ruta: $PROJECT_DIR"
    echo "  Esto incluye: código fuente, entorno virtual, voces descargadas, iconos..."
    read -r -p "  ¿Mover el proyecto a la papelera? [s/N] " borrar_proyecto
    if [[ "${borrar_proyecto,,}" == "s" || "${borrar_proyecto,,}" == "si" || "${borrar_proyecto,,}" == "y" || "${borrar_proyecto,,}" == "yes" ]]; then
        if [ "$(pwd)" = "$PROJECT_DIR" ] || [[ "$(pwd)" = "$PROJECT_DIR"/* ]]; then
            echo -e "${YELLOW}  ⚠  Estás dentro del directorio del proyecto.${NC}"
            echo "  Cambiando a HOME antes de mover..."
            cd "$HOME"
        fi
        comando_trash "$PROJECT_DIR" && echo "  ✓ Proyecto enviado a la papelera"
        # Salir después de borrar el proyecto — ya no hay nada más que hacer
        echo ""
        echo "============================================"
        echo -e "${GREEN}  Desinstalación completada.${NC}"
        echo "============================================"
        exit 0
    else
        echo "  • Proyecto conservado"
    fi
fi

# ── 4. Dependencias del sistema ──────────────────────────────────────
echo ""
echo -e "${YELLOW}[4/4]${NC} Dependencias del sistema"

if dpkg -l portaudio19-dev &>/dev/null || dpkg -l python3-pyaudio &>/dev/null; then
    echo -e "  ${YELLOW}⚠  Otras aplicaciones podrían necesitar estos paquetes.${NC}"
    read -r -p "  ¿Desinstalar portaudio19-dev y python3-pyaudio? [s/N] " borrar_paquetes
    if [[ "${borrar_paquetes,,}" == "s" || "${borrar_paquetes,,}" == "si" || "${borrar_paquetes,,}" == "y" || "${borrar_paquetes,,}" == "yes" ]]; then
        sudo apt remove -y portaudio19-dev python3-pyaudio 2>/dev/null || true
        echo "  ✓ Paquetes desinstalados"
    else
        echo "  • Paquetes conservados"
    fi
else
    echo "  • Paquetes no encontrados"
fi

# ── Final ────────────────────────────────────────────────────────────
echo ""
echo "============================================"
echo -e "${GREEN}  Desinstalación completada.${NC}"
echo ""
echo "  Puedes recuperar archivos de la papelera si cambias de opinión."
echo "============================================"
