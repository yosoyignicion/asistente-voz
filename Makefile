.PHONY: run test install clean diagnose help

VENV_DIR := env_asistente

help:
	@echo "Asistente de Voz — comandos disponibles:"
	@echo ""
	@echo "  make run         Lanzar el asistente (recomendado)"
	@echo "  make test        Ejecutar tests del nucleo"
	@echo "  make install     Instalacion guiada (wizard grafico)"
	@echo "  make clean       Limpiar temporales (pycache, lock, logs)"
	@echo "  make diagnose    Diagnosticar GPU, Ollama, audio, modelos"

run:
	bash bin/asistente-voz

test:
	@source $(VENV_DIR)/bin/activate && python test/test_core.py

install:
	bash instalar.sh

diagnose:
	bash scripts/diagnostico.sh

clean:
	@echo "Limpiando temporales..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -f /tmp/asistente-voz.lock /tmp/asistente-voz.log
	@echo "Limpio."
