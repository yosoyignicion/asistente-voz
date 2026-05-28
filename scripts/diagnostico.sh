#!/usr/bin/env bash
# Diagnostico rapido del Asistente de Voz — verifica GPU, Ollama, audio, modelos.
# Uso: bash scripts/diagnostico.sh

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

pass=0
fail=0

ok()  { echo -e "  ${GREEN}OK${NC}   $*"; ((pass++)); }
warn(){ echo -e "  ${YELLOW}WARN${NC} $*"; ((fail++)); }
err() { echo -e "  ${RED}FAIL${NC} $*"; ((fail++)); }

echo "============================================"
echo "  Diagnostico — Asistente de Voz"
echo "============================================"
echo ""

# ── GPU y Vulkan ──────────────────────────────────────────────────
echo -e "${YELLOW}[GPU]${NC}"

if command -v vulkaninfo &>/dev/null; then
    gpu_name=$(vulkaninfo --summary 2>/dev/null | grep deviceName | head -1 | cut -d= -f2 | xargs)
    if [ -n "${gpu_name:-}" ]; then
        ok "GPU: $gpu_name"
    else
        warn "vulkaninfo no detecta GPU (drivers Vulkan no instalados?)"
    fi
else
    warn "vulkaninfo no instalado. Instala: sudo apt install vulkan-tools"
fi

if command -v glxinfo &>/dev/null; then
    vram=$(glxinfo -B 2>/dev/null | grep "Video memory" | awk '{print $4}' | head -1)
    if [ -n "${vram:-}" ]; then
        ok "VRAM: ${vram} MB"
    else
        warn "No se pudo detectar VRAM"
    fi
else
    warn "glxinfo no instalado. Instala: sudo apt install mesa-utils"
fi

# ── Ollama ─────────────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[Ollama]${NC}"

if ! command -v ollama &>/dev/null; then
    err "Ollama no instalado. Descarga: https://ollama.com/download/linux"
else
    ok "Ollama instalado ($(ollama --version 2>/dev/null || echo '?'))"

    if ! ollama list &>/dev/null 2>&1; then
        warn "Servidor Ollama no responde. Inicia con: OLLAMA_VULKAN=1 ollama serve"
    else
        ok "Servidor Ollama corriendo"

        # Modelo asistente_voz
        if ollama list 2>/dev/null | grep -q "asistente_voz"; then
            ok "Modelo asistente_voz:latest presente"
        else
            warn "Modelo asistente_voz:latest no encontrado. Crear: ollama create asistente_voz:latest -f Modelfile"
        fi

        # Backend GPU
        gpu_line=$(ollama ps 2>/dev/null | grep -i "gpu\|vulkan" || true)
        if [ -n "$gpu_line" ]; then
            ok "Backend GPU activo (Vulkan/CUDA)"
        else
            running_models=$(ollama ps 2>/dev/null | wc -l)
            if [ "$running_models" -gt 1 ]; then
                warn "Backend GPU NO detectado. Ejecuta: OLLAMA_VULKAN=1 ollama serve"
            fi
        fi
    fi
fi

# ── Audio ──────────────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[Audio]${NC}"

if command -v python3 &>/dev/null; then
    SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

    audio_info=$(python3 -c "
import sounddevice as sd
devs = sd.query_devices()
in_count = sum(1 for d in devs if d['max_input_channels'] > 0)
out_count = sum(1 for d in devs if d['max_output_channels'] > 0)
default_in = sd.query_devices(kind='input')
default_out = sd.query_devices(kind='output')
print(f'{len(devs)}:{in_count}:{out_count}:{default_in[\"name\"]}:{default_out[\"name\"]}')
" 2>/dev/null)
    if [ $? -eq 0 ] && [ -n "${audio_info:-}" ]; then
        IFS=':' read -r total in_count out_count def_in def_out <<< "$audio_info"
        ok "Dispositivos: ${total} total (${in_count} entrada, ${out_count} salida)"
        ok "Micro: $def_in"
        ok "Altavoces: $def_out"
    else
        warn "sounddevice no disponible o sin dispositivos. Instala: pip install sounddevice"
    fi
else
    warn "Python3 no encontrado"
fi

# ── Archivos clave ─────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[Recursos]${NC}"

check_file() {
    if [ -f "$PROJECT_DIR/$1" ]; then
        ok "$1"
    else
        warn "$1 no encontrado"
    fi
}

check_file "recursos/silero_vad.onnx"
check_file "recursos/voces_disponibles.json"
check_file "Modelfile"
check_file "requirements.txt"

if [ -d "$PROJECT_DIR/env_asistente" ]; then
    ok "env_asistente/ presente"
else
    warn "env_asistente/ no encontrado. Ejecuta: bash instalar.sh"
fi

# ── Resumen ────────────────────────────────────────────────────────
echo ""
echo "────────────────────────────────────────"
echo -e "  Listo: ${GREEN}${pass}${NC}  |  Avisos: ${YELLOW}${fail}${NC}"

if [ "$fail" -eq 0 ]; then
    echo -e "  ${GREEN}Todo OK. Ejecuta: bash bin/asistente-voz${NC}"
elif [ "$fail" -le 3 ]; then
    echo -e "  ${YELLOW}Algunos avisos. Revisa los WARN arriba.${NC}"
else
    echo -e "  ${RED}Varios problemas. Revisa los FAIL arriba.${NC}"
fi
echo "────────────────────────────────────────"
