#!/usr/bin/env bash
# Pre-vuelo: verifica Ollama, pregunta modelo base, crea asistente_voz:latest.
# Uso: bash scripts/preparar_entorno.sh

PROJECT_DIR="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo "============================================"
echo "  Preparador del entorno Ollama"
echo "============================================"
echo ""

if ! command -v ollama &>/dev/null; then
    echo -e "${RED}Error:${NC} Ollama no está instalado."
    echo "Instálalo desde: https://ollama.com/download/linux"
    echo "Después vuelve a ejecutar este script."
    exit 1
fi
echo -e "${GREEN}✓${NC} Ollama instalado"

echo "→ Verificando servidor Ollama..."
if ! ollama list &>/dev/null; then
    echo "  Iniciando ollama serve en segundo plano..."
    ollama serve &>/dev/null &
    for i in $(seq 1 20); do
        if ollama list &>/dev/null; then
            echo -e "  ${GREEN}✓${NC} Servidor Ollama listo (esperé ${i}s)"
            break
        fi
        sleep 1
    done
fi

if ! ollama list &>/dev/null; then
    echo -e "${RED}Error:${NC} Ollama no responde después de 20s."
    echo "Inícialo manualmente con 'ollama serve' en otra terminal y vuelve a intentarlo."
    exit 1
fi

echo ""
echo "Modelos disponibles en Ollama:"
ollama list 2>/dev/null || echo "  (ninguno)"

echo ""
DEFAULT_MODEL="llama3.2:1b"
read -r -p "¿Instalar $DEFAULT_MODEL como modelo base? [S/n]: " respuesta
if [[ -z "$respuesta" || "$respuesta" =~ ^[Ss]$ ]]; then
    BASE_MODEL="$DEFAULT_MODEL"
    if ollama list 2>/dev/null | grep -q "^$BASE_MODEL "; then
        echo -e "${GREEN}✓${NC} $BASE_MODEL ya está descargado"
    else
        echo "→ Descargando $BASE_MODEL..."
        ollama pull "$BASE_MODEL"
    fi
else
    read -r -p "Nombre del modelo base a usar: " BASE_MODEL
    if [ -z "$BASE_MODEL" ]; then
        echo -e "${RED}Cancelado.${NC}"
        exit 0
    fi
    if ! ollama list 2>/dev/null | grep -q "^$BASE_MODEL "; then
        echo "→ Descargando $BASE_MODEL..."
        ollama pull "$BASE_MODEL"
    fi
fi

echo ""
echo "→ Creando modelo asistente_voz:latest desde $PROJECT_DIR/Modelfile..."
ollama create asistente_voz:latest -f "$PROJECT_DIR/Modelfile"

VOICE="${VOICE:-ef_dora}"
python3 -c "
import json, os
config_path = os.environ['CONFIG_PATH']
config = {}
if os.path.exists(config_path):
    try:
        with open(config_path) as f:
            config = json.load(f)
    except Exception:
        pass
config['base_model'] = os.environ['BASE_MODEL']
config.setdefault('voice', os.environ.get('VOICE', 'ef_dora'))
config.setdefault('model', 'asistente_voz:latest')
config.setdefault('autostart', False)
with open(config_path + '.tmp', 'w') as f:
    json.dump(config, f, indent=2)
os.replace(config_path + '.tmp', config_path)
" CONFIG_PATH="$PROJECT_DIR/config.json" BASE_MODEL="$BASE_MODEL" VOICE="$VOICE"

echo ""
echo -e "${GREEN}✓ Entorno preparado correctamente${NC}"
echo "  Modelo base:   $BASE_MODEL"
echo "  Modelo activo: asistente_voz:latest"
echo "  Voz TTS:       $VOICE"
echo ""
echo "Ya puedes ejecutar: bash instalar.sh"
