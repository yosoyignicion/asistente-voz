# AGENTS.md — Asistente-Voz

## Stack
Python 3.12+, venv `env_asistente/`. Ollama + `gemma2:2b` (GPU Vulkan, Modelfile). STT: `faster-whisper` (base) + Silero VAD. TTS: Kokoro 82M (primario, `ef_dora`) + Piper (fallback, 7 voces `es_*`). Audio: `sounddevice`. GUI: customtkinter. Hotkey: `pynput` (Ctrl+.). Pre-vuelo: `scripts/preparar_entorno.sh`. GPU: `OLLAMA_VULKAN=1` para backend Vulkan.

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
La fuente de verdad es el código + `Modelfile`.

## Checklist de pruebas manuales
Tras cada modificación, verificar:
- [ ] Arranca sin errores (`python main.py`)
- [ ] Hotkey Ctrl+. activa/desactiva la grabación (beep al soltar)
- [ ] El botón del panel toggle también activa/desactiva la grabación
- [ ] La respuesta se sintetiza en voz (TTS audible)
- [ ] La respuesta es en español, sin preguntas, sin emojis
- [ ] El beep de 660Hz suena al finalizar la grabación
- [ ] El selector de voz ⚙ muestra las 10 voces (3 Kokoro + 7 Piper) y "Probar" reproduce audio
- [ ] ✕ minimiza la ventana, no cierra la app
- [ ] "Salir del asistente" en ⚙ cierra la app correctamente (verificar con `ps aux | grep python`)

## Arquitectura

| Módulo | Función | Cuidado |
|--------|---------|---------|
| `modulos/cerebro.py` | Historial FIFO (6 interacciones) | System prompt duplicado con `Modelfile` |
| `modulos/stt.py` | Grabación + faster-whisper + Silero VAD | `_cancel` Event controla el flujo; `preload()` carga modelo y VAD en background; `device_index` (None = default) selecciona micrófono; `silence_threshold=0.025` y `max_record_s=15`; `_vad_trim()` aplica Silero VAD post-grabación para corte preciso; `vad_filter=False` en Whisper (audio ya recortado). **`_record_audio()` no se usa en el pipeline principal** — `main.py` tiene su propio `_grabar_worker()` con `sd.InputStream` |
| `modulos/vad.py` | Silero VAD via ONNX (sin torch) | Path al modelo ONNX usa `importlib` para fallback dinámico — evita hardcodear paths de usuario |
| `modulos/tts.py` | TTS dual: Kokoro 82M + Piper | Voces Kokoro: `ef_dora`, `em_alex`, `em_santa` (24000Hz). Voces Piper: las 7 `es_*` (22050Hz). Motor auto-detectado por nombre de voz (`ef_`/`em_` → Kokoro, `es_` → Piper). Usar `reproducir_async()` para no bloquear el pipeline |
| `modulos/inferencia.py` | Ollama chat streaming | `num_predict 80` en Modelfile limita tokens de salida |
| `gui/panel.py` | Ventana customtkinter nativa: botón toggle "Ctrl + .", status animado, ✕ minimiza, ⚙ ajustes, icono en barra de tareas | **Nunca bloquear el hilo principal**; `set_grabando(bool)` cambia estado visual del botón |
| `main.py` | Orquestador: 3 daemon threads (tts-init, hotkey, proc), hotkey Ctrl+. vía pynput, grabación toggle, shutdown limpio | TTS init en background para que la GUI aparezca instantánea; `_beep_feedback()` emite tono 660Hz al finalizar grabación; `_grabar_worker()` graba en streaming con timeout `max_record_s`; `_mostrar_ajustes()` singleton vía `after(0)` (hilo principal); `_root_after()` envuelve tkinter para thread-safety; `_manejar_signal` minimalista (solo flag + `_exit`), lock liberado por `atexit` |
| `bin/asistente-voz` | Lanzador bash de conveniencia | Auto-arranca ollama con `OLLAMA_VULKAN=1` si no está corriendo; auto-crea el modelo si falta con `ollama create asistente_voz:latest -f Modelfile`; luego ejecuta `python main.py "$@"` |
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
| Respuestas muy lentas | `num_ctx 1024` demasiado alto o GPU no activada. Verificar `OLLAMA_VULKAN=1` y backend GPU con `ollama ps`. Sin GPU, gemma2:2b corre ~4× más lento en CPU |
| GUI se congela | Código bloqueante ejecutado en el callback de tkinter |
| Modelo da error | `ollama create asistente_voz:latest -f Modelfile` no ejecutado |
| GPU no se activa | Ollama arrancó sin `OLLAMA_VULKAN=1`. Reiniciar con `OLLAMA_VULKAN=1 ollama serve`. Verificar con `ollama ps` (debe mostrar GPU) |
| Proceso no muere al cerrar | Hilos daemon no se limpian; `_do_quit` llama `_release_lock()` + `os._exit(0)`. Verificar con `ps aux | grep python` |
| Modelo desvaría o alucina | `temperature` muy alto (usar 0.5) o Modelfile editado sin recrear (`ollama create -f Modelfile`) |
| Voz no cambia tras instalar | `config.json` no se generó; pasar `--voice` explícitamente o reinstalar |
| Kokoro no sintetiza | `espeak-ng` no instalado (`sudo apt-get install espeak-ng`) o primera ejecución sin internet (descarga ~300MB de HuggingFace) |
| Kokoro da error `device` o `last_hidden_state` | `transformers<4.0` instalado; necesita `transformers>=4.0`. También verifica que `torch.nn.Module.device` esté monkey-patcheado (ver `_get_kokoro_pipeline()` en `tts.py`) |
| Piper/Kokoro no descargan voces | Primera ejecución requiere internet. Kokoro descarga ~300MB de HuggingFace. Piper descarga modelo `.onnx` por voz (~50MB c/u). Si falla, verificar `VOICE_CACHE_DIR` en `tts.py` |
| Beep no suena al detectar wake word | `portaudio19-dev` no instalado; verificar con `python -c "import sounddevice; print(sd.query_devices())"` |
| VAD no encuentra modelo | `recursos/silero_vad.onnx` no existe. El fallback usa `importlib` para encontrar el modelo en site-packages. Si falla: `pip install --no-deps silero-vad` |
| ⚙ no abre ajustes o crashea | `_mostrar_ajustes` usa `_load_voice_catalog()` con fallback a `{}` (ya no crashea si falta voces_disponibles.json) |
| Voz no persiste tras reiniciar | `config.json` no se está escribiendo (permisos); verificar con `python main.py --voice es_MX-ald-medium` |
| Push-to-talk se cuelga en "Procesando audio..." | Grabación empieza al pulsar (no al soltar); si el stream no abre, verificar micrófono en ⚙ > Ajustes |
| Respuesta alucinada o sin sentido | VAD activo en transcripción de comandos (`vad_filter=True` en `_transcribe` con `fast=True`); si persiste, verificar silencio al soltar el botón |
| Se abre una segunda instancia | `/tmp/asistente-voz.lock` previene duplicados; incluye timestamp (locks >1h se invalidan automáticamente); si falla, `rm /tmp/asistente-voz.lock` |

## Threading — restricciones

- Hilo principal: `customtkinter.mainloop()` (bloqueante)
- 3 daemon threads: `tts-init`, `hotkey`, `proc-loop`
- **Nunca ejecutar `tts.reproducir()` en el hilo GUI** — bloquea la interfaz
- `_procesando` (threading.Lock) serializa el pipeline; si un comando cuelga, todo se detiene
- `stt._cancel` Event interrumpe grabaciones; no hacer `wait()` sin timeout
- `_bucle_procesamiento` protegido con try/except — el hilo proc-loop nunca muere por excepción
- GUI callbacks delegan trabajo a `_ejecutar_en_hilo` en `gui/panel.py:205` (nuevo daemon thread por evento)
- Las operaciones largas (STT, inferencia, TTS) van en hilos daemon — nunca en el hilo GUI
- `/tmp/asistente-voz.lock` (PID file) previene instancias duplicadas; se borra en `_do_quit` y `_manejar_signal`
- Ollama debe arrancar con `OLLAMA_VULKAN=1` para usar GPU. El binario de ollama tiene backend Vulkan en `/usr/local/lib/ollama/vulkan/libggml-vulkan.so`
