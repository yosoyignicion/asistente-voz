#!/usr/bin/env bash
# Diagnostico rapido del Asistente de Voz — verifica GPU, Ollama, audio, modelos.
# Uso: bash scripts/diagnostico.sh

set -eu

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

pass=0
fail=0

ok()  { echo -e "  ${GREEN}OK${NC}   $*"; pass=$((pass + 1)); }
warn(){ echo -e "  ${YELLOW}WARN${NC} $*"; fail=$((fail + 1)); }
err() { echo -e "  ${RED}FAIL${NC} $*"; fail=$((fail + 1)); }

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "============================================"
echo "  Diagnostico — Asistente de Voz"
echo "============================================"
echo ""

# ── GPU y Vulkan ──────────────────────────────────────────────────
echo -e "${YELLOW}[GPU]${NC}"

if command -v vulkaninfo &>/dev/null; then
    gpu_name=$(vulkaninfo --summary 2>/dev/null | { grep deviceName || true; } | head -1 | cut -d= -f2 | xargs)
    if [ -n "${gpu_name:-}" ]; then
        ok "GPU: $gpu_name"
    else
        warn "vulkaninfo no detecta GPU (drivers Vulkan no instalados?)"
    fi
else
    warn "vulkaninfo no instalado. Instala: sudo apt install vulkan-tools"
fi

if command -v glxinfo &>/dev/null; then
    vram=$(glxinfo -B 2>/dev/null | { grep "Video memory" || true; } | awk '{print $3}' | head -1)
    if [ -n "${vram:-}" ]; then
        ok "VRAM: ${vram}"
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
    ollama_ver=$(timeout 5 ollama --version 2>/dev/null || echo "?")
    ok "Ollama instalado ($ollama_ver)"

    if [ -n "${OLLAMA_VULKAN:-}" ]; then
        ok "OLLAMA_VULKAN=${OLLAMA_VULKAN} (entorno)"
    fi

    if ! timeout 10 ollama list &>/dev/null 2>&1; then
        warn "Servidor Ollama no responde. Inicia con: OLLAMA_VULKAN=1 ollama serve"
    else
        ok "Servidor Ollama corriendo"

        if timeout 10 ollama list 2>/dev/null | { grep -q "asistente_voz" || true; }; then
            ok "Modelo asistente_voz:latest presente"
        else
            warn "Modelo asistente_voz:latest no encontrado. Crear: ollama create asistente_voz:latest -f Modelfile"
        fi

        gpu_line=$(timeout 10 ollama ps 2>/dev/null | { grep -i "gpu\|vulkan" || true; })
        if [ -n "$gpu_line" ]; then
            ok "Backend GPU activo (Vulkan/CUDA)"
        else
            running_models=$(timeout 10 ollama ps 2>/dev/null | wc -l || echo 0)
            if [ "$running_models" -gt 1 ]; then
                warn "Backend GPU NO detectado. Ejecuta: OLLAMA_VULKAN=1 ollama serve"
            fi
        fi
    fi
fi

# ── Audio ──────────────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[Audio]${NC}"

py_exit=1
audio_info=""

_python_bin="python3"
if [ -x "$PROJECT_DIR/env_asistente/bin/python" ]; then
    _python_bin="$PROJECT_DIR/env_asistente/bin/python"
fi

if command -v "$_python_bin" &>/dev/null; then
    set +e
    audio_info=$("$_python_bin" << 'PYEOF' 2>/dev/null
import sounddevice as sd
devs = sd.query_devices()
in_count = sum(1 for d in devs if d["max_input_channels"] > 0)
out_count = sum(1 for d in devs if d["max_output_channels"] > 0)
default_in = sd.query_devices(kind="input")
default_out = sd.query_devices(kind="output")
print(f"{len(devs)}:{in_count}:{out_count}:{default_in['name']}:{default_out['name']}")
PYEOF
)
    py_exit=$?
    set -e
fi

if [ $py_exit -eq 0 ] && [ -n "${audio_info:-}" ]; then
    IFS=':' read -r total in_count out_count def_in def_out <<< "$audio_info" || true
    ok "Dispositivos: ${total} total (${in_count} entrada, ${out_count} salida)"
    ok "Micro: $def_in"
    ok "Altavoces: $def_out"
else
    warn "sounddevice no disponible o sin dispositivos. Instala: pip install sounddevice"
fi

# ── Disco ──────────────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[Disco]${NC}"

if command -v df &>/dev/null; then
    espacio=$(df -h "$PROJECT_DIR" 2>/dev/null | tail -1 | awk '{print $4}')
    if [ -n "${espacio:-}" ]; then
        ok "Espacio libre en disco: $espacio"
    fi
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

echo ""
echo "  Proyecto: $PROJECT_DIR"
if command -v git &>/dev/null && git -C "$PROJECT_DIR" rev-parse --git-dir &>/dev/null 2>&1; then
    commit=$(git -C "$PROJECT_DIR" rev-parse --short HEAD 2>/dev/null || echo "?")
    rama=$(git -C "$PROJECT_DIR" branch --show-current 2>/dev/null || echo "?")
    echo "  Git: $rama @ $commit"
fi
echo "────────────────────────────────────────"
