#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_DIR/build/appimage"
DIST_DIR="$PROJECT_DIR/dist"

APP_NAME="AsistenteVoz"
APP_DIR="$BUILD_DIR/$APP_NAME.AppDir"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

clean() {
    rm -rf "$BUILD_DIR" "$DIST_DIR"
    mkdir -p "$APP_DIR" "$DIST_DIR"
}

install_pyinstaller() {
    if ! python -c "import PyInstaller" &>/dev/null; then
        echo "→ Instalando pyinstaller..."
        pip install pyinstaller -q
    fi
}

build_binary() {
    echo ""
    echo -e "${YELLOW}[1/4]${NC} Compilando binario con PyInstaller..."

    cd "$PROJECT_DIR"

    pyinstaller \
        --onefile \
        --name "$APP_NAME" \
        --add-data "modulos:modulos" \
        --add-data "gui:gui" \
        --hidden-import=pystray \
        --hidden-import=PIL \
        --hidden-import=PIL.Image \
        --hidden-import=PIL.ImageDraw \
        --hidden-import=sounddevice \
        --hidden-import=faster_whisper \
        --hidden-import=piper \
        --hidden-import=piper.voice \
        --hidden-import=piper.config \
        --hidden-import=piper.download_voices \
        --hidden-import=onnxruntime \
        --hidden-import=ollama \
        --hidden-import=numpy \
        --clean \
        --noconfirm \
        main.py 2>&1 | tail -5

    echo "  ✓ Binario generado en dist/$APP_NAME"
}

create_appdir() {
    echo ""
    echo -e "${YELLOW}[2/4]${NC} Creando estructura AppDir..."

    cp "$PROJECT_DIR/dist/$APP_NAME" "$APP_DIR/"

    cat > "$APP_DIR/AppRun" << 'APPRUN'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "$0")")"

if ! command -v ollama &>/dev/null; then
    zenity --error --text "Ollama no está instalado.\nInstálalo desde https://ollama.com/download" 2>/dev/null || \
        echo "Error: Ollama no está instalado"
    exit 1
fi

exec "$HERE/AsistenteVoz" "$@"
APPRUN
    chmod +x "$APP_DIR/AppRun"

    cp "$PROJECT_DIR/recursos/asistente-voz.desktop" "$APP_DIR/"
    sed -i "s|##PROJECT_DIR##|.|g" "$APP_DIR/asistente-voz.desktop"
    sed -i "s|/bin/asistente-voz|/AppRun|g" "$APP_DIR/asistente-voz.desktop"

    cp "$PROJECT_DIR/recursos/asistente-voz.png" "$APP_DIR/"

    echo "  ✓ AppDir creada en $APP_DIR"
}

download_appimagetool() {
    if command -v appimagetool &>/dev/null; then
        return
    fi

    local tool_path="$BUILD_DIR/appimagetool"
    if [ -f "$tool_path" ]; then
        export PATH="$BUILD_DIR:$PATH"
        return
    fi

    echo "→ Descargando appimagetool..."
    local url="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    wget -q "$url" -O "$tool_path" || curl -sL "$url" -o "$tool_path"
    chmod +x "$tool_path"
    export PATH="$BUILD_DIR:$PATH"
}

package_appimage() {
    echo ""
    echo -e "${YELLOW}[3/4]${NC} Generando AppImage..."

    download_appimagetool

    cd "$BUILD_DIR"
    ARCH=x86_64 appimagetool "$APP_DIR" "$DIST_DIR/AsistenteVoz-x86_64.AppImage" 2>&1 | tail -3

    echo "  ✓ AppImage generada en $DIST_DIR/AsistenteVoz-x86_64.AppImage"
}

cleanup() {
    echo ""
    echo -e "${YELLOW}[4/4]${NC} Limpiando archivos temporales..."
    rm -rf "$PROJECT_DIR/build/AsistenteVoz" "$PROJECT_DIR/build/AsistenteVoz"*.spec 2>/dev/null || true
    echo "  ✓ Limpieza completada"
}

main() {
    echo "============================================"
    echo "  Construir AppImage — Asistente de Voz"
    echo "============================================"

    if ! command -v python3 &>/dev/null; then
        echo -e "${RED}Error: python3 no encontrado${NC}"
        exit 1
    fi

    clean
    install_pyinstaller
    build_binary
    create_appdir
    package_appimage
    cleanup

    echo ""
    echo "============================================"
    echo -e "${GREEN}  ¡AppImage construida!${NC}"
    echo ""
    echo "  Archivo: $DIST_DIR/AsistenteVoz-x86_64.AppImage"
    echo ""
    echo "  Uso:"
    echo "    chmod +x $DIST_DIR/AsistenteVoz-x86_64.AppImage"
    echo "    $DIST_DIR/AsistenteVoz-x86_64.AppImage"
    echo ""
    echo "  Requisitos en la máquina destino:"
    echo "    - Ollama instalado y corriendo"
    echo "    - Modelo asistente_voz:latest creado"
    echo "    - portaudio (libportaudio2)"
    echo "============================================"
}

main
