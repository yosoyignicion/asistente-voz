# AGENTS.md — Asistente-Voz

## Stack
Python 3.12+, venv `env_asistente/`. Ollama + `llama3.2:3b` (Modelfile). STT: `faster-whisper` (small) + Silero VAD. TTS: Kokoro 82M (primario, `ef_dora`) + Piper (fallback, 7 voces `es_*`) + espeak-ng (ultraligero, `espeak_es`). Audio: `sounddevice`. GUI: customtkinter. Hotkey: `pynput` (Ctrl+.).

## Verificación
No tiene linter ni type checker. Los únicos comandos de verificación:

```bash
source env_asistente/bin/activate
python main.py                    # ventana nativa + hotkey Ctrl+.
python main.py --voice es_MX-ald-medium

# Tests del núcleo (sin Ollama, sin audio, sin display)
python test/test_core.py
```

Cada cambio debe probarse manualmente con la checklist de abajo.
`compact.md` y `PLAN.md` contienen valores desactualizados (max_interacciones=8, voces=8, `temperature=0.75`). La fuente de verdad es el código + `Modelfile`.

## Checklist de pruebas manuales
Tras cada modificación, verificar:
- [ ] Arranca sin errores (`python main.py`)
- [ ] Hotkey Ctrl+. activa/desactiva la grabación (beep al soltar)
- [ ] El botón del panel toggle también activa/desactiva la grabación
- [ ] La respuesta se sintetiza en voz (TTS audible)
- [ ] Las acciones `[ACCION:XXX]` se ejecutan sin congelar la GUI
- [ ] El beep de 660Hz suena al finalizar la grabación
- [ ] El selector de voz ⚙ muestra las 11 voces (3 Kokoro + 7 Piper + 1 Espeak) y "Probar" reproduce audio
- [ ] ✕ minimiza la ventana, no cierra la app
- [ ] "Salir del asistente" en ⚙ cierra la app correctamente (verificar con `ps aux | grep python`)

## Arquitectura

| Módulo | Función | Cuidado |
|--------|---------|---------|
| `modulos/cerebro.py` | Historial FIFO (6 interacciones) | System prompt duplicado con `Modelfile` |
| `modulos/acciones.py` | `[ACCION:XXX]` → subprocess | Si el tag va al inicio, la respuesta TTS queda vacía |
| `modulos/stt.py` | Grabación + faster-whisper + Silero VAD | `_cancel` Event controla el flujo; `preload()` carga modelo y VAD en background; `device_index` (None = default) selecciona micrófono; `silence_threshold=0.025` y `max_record_s=15`; `_vad_trim()` aplica Silero VAD post-grabación para corte preciso; `vad_filter=False` en Whisper (audio ya recortado) |
| `modulos/tts.py` | TTS triple: Kokoro 82M + Piper + espeak-ng | Voces Kokoro: `ef_dora`, `em_alex`, `em_santa` (24000Hz). Voces Piper: las 7 `es_*` (22050Hz). Espeak: `espeak_es` (22050Hz, subprocess). Motor auto-detectado por nombre de voz (`ef_`/`em_` → Kokoro, `es_` → Piper, `espeak_` → Espeak). Usar `reproducir_async()` para no bloquear el pipeline |
| `modulos/inferencia.py` | Ollama chat streaming | `num_predict 150` en Modelfile limita tokens de salida |
| `gui/panel.py` | Ventana customtkinter nativa: botón toggle "Ctrl + .", status animado, ✕ minimiza, ⚙ ajustes, icono en barra de tareas | **Nunca bloquear el hilo principal**; `set_grabando(bool)` cambia estado visual del botón |
| `main.py` | Orquestador: 2 daemon threads (hotkey, proc), hotkey Ctrl+. vía pynput, grabación toggle, shutdown limpio | `_beep_feedback()` emite tono 660Hz al finalizar grabación; `_grabar_worker()` graba en streaming hasta siguiente toggle; `_mostrar_ajustes()` singleton (no abre múltiples ventanas); `_root_after()` envuelve tkinter para thread-safety |
| `bin/asistente-voz` | Lanzador bash de conveniencia | Auto-arranca ollama si no está corriendo; auto-crea el modelo si falta con `ollama create asistente_voz:latest -f Modelfile`; luego ejecuta `python main.py "$@"` |
| `instalar_gui.py` | Wizard de instalación 5 pasos con customtkinter | Sistema de pasos con indicadores ●/○; instala modelo Ollama + voz TTS + acceso directo; modo `--no-gui` disponible |

## System prompt sincronizado (regla de oro)

El system prompt está **triplicado** en tres sitios y deben ser idénticos:
- `Modelfile:3-5` — comportamiento al ejecutar `ollama run` directamente
- `modulos/cerebro.py:4-10` — enviado en cada petición por la app
- `instalar_gui.py:32-33` — plantilla usada al reinstalar

**Si editas uno, copia y pega en los otros dos.**

## Errores comunes

| Síntoma | Causa probable |
|---------|---------------|
| `main.py` no arranca | Ollama no está corriendo (`ollama serve` o usa `bash bin/asistente-voz`) |
| TTS no suena | `portaudio19-dev` no instalado o voz no descargada |
| No reconoce voz | Micrófono mal configurado: usar ⚙ > Ajustes para seleccionar el dispositivo correcto y pulsar "Aplicar microfono". Verificar con `python -c "import sounddevice as sd; print(sd.query_devices())"` |
| Respuestas muy lentas | `num_ctx 4096` demasiado alto; reducir en `Modelfile` |
| GUI se congela | Código bloqueante ejecutado en el callback de tkinter |
| Modelo da error | `ollama create asistente_voz:latest -f Modelfile` no ejecutado |
| `[ACCION:XXX]` no se ejecuta | Tag mal formado o `xdg-open`/`xset` no disponible |
| Proceso no muere al cerrar | Hilos daemon no se limpian; `_do_quit` llama `_release_lock()` + `os._exit(0)`. Verificar con `ps aux | grep python` |
| Icono tray no responde a clics | Falta `python3-gi gir1.2-ayatanaappindicator3-0.1`; usar ⚙ del panel |
| Modelo desvaría o alucina | `temperature` muy alto (usar 0.5) o Modelfile editado sin recrear (`ollama create -f Modelfile`) |
| Voz no cambia tras instalar | `config.json` no se generó; pasar `--voice` explícitamente o reinstalar |
| Kokoro no sintetiza | `espeak-ng` no instalado (`sudo apt-get install espeak-ng`) o primera ejecución sin internet (descarga ~300MB de HuggingFace) |
| Kokoro da error `device` o `last_hidden_state` | `transformers<4.0` instalado; necesita `transformers>=4.0`. También verifica que `torch.nn.Module.device` esté monkey-patcheado (ver `_get_kokoro_pipeline()` en `tts.py`) |
| Beep no suena al detectar wake word | `portaudio19-dev` no instalado; verificar con `python -c "import sounddevice; print(sd.query_devices())"` |
| ⚙ no abre ajustes o crashea | `_mostrar_ajustes` espera `VOICE_CATALOG` en main.py y `recursos/voces_disponibles.json` presente |
| Voz no persiste tras reiniciar | `config.json` no se está escribiendo (permisos); verificar con `python main.py --voice es_MX-ald-medium` |
| Panel no responde a clic en tray | Si usas AppIndicator (Ubuntu/GNOME), el clic izq no funciona — usar menú derecho. En GTK/Cinnamon, el ítem "Mostrar / Ocultar panel" tiene `default=True` y responde al clic izq |
| Micrófono equivocado o no graba | Seleccionar en ⚙ > Ajustes el dispositivo de entrada correcto. El índice se guarda en `config.json` como `device_index` |
| Push-to-talk se cuelga en "Procesando audio..." | Grabación empieza al pulsar (no al soltar); si el stream no abre, verificar micrófono en ⚙ > Ajustes |
| Respuesta alucinada o sin sentido | VAD activo en transcripción de comandos (`vad_filter=True` en `_transcribe` con `fast=True`); si persiste, verificar silencio al soltar el botón |
| Se abre una segunda instancia | `/tmp/asistente-voz.lock` previene duplicados; si falla, eliminar el lock manualmente (`rm /tmp/asistente-voz.lock`) |

## Threading — restricciones

- Hilo principal: `customtkinter.mainloop()` (bloqueante)
- 2 daemon threads: `hotkey`, `proc-loop`
- **Nunca ejecutar `tts.reproducir()` en el hilo GUI** — bloquea la interfaz
- `_procesando` (threading.Lock) serializa el pipeline; si un comando cuelga, todo se detiene
- `stt._cancel` Event interrumpe grabaciones; no hacer `wait()` sin timeout
- GUI callbacks delegan trabajo a `_ejecutar_en_hilo` en `gui/panel.py:197` (nuevo daemon thread por evento)
- Las acciones del sistema ejecutan subprocess en el hilo de procesamiento, no en la GUI
- `/tmp/asistente-voz.lock` (PID file) previene instancias duplicadas; se borra en `_do_quit` y `_manejar_signal`
