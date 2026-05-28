<!-- ─────────────────────────────────────────────────── -->
<!--   Asistente de Voz · 100% local · hecho en España   -->
<!-- ─────────────────────────────────────────────────── -->

<p align="center">
  <img src="recursos/asistente-voz.svg" width="96" alt="Micrófono azul">
</p>

<p align="center">
  <strong>
    Tu asistente de voz privado, offline y que habla&nbsp;español&nbsp;de&nbsp;verdad 🇪🇸<br>
    Sin nube. Sin telemetría. Sin excusas.
  </strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Ollama-llama3.2:3b-orange?logo=ollama" alt="Ollama">
  <img src="https://img.shields.io/badge/TTS-Kokoro_82M-hotpink" alt="Kokoro">
  <img src="https://img.shields.io/badge/STT-faster--whisper_+_Silero_VAD-green" alt="STT">
  <img src="https://img.shields.io/badge/license-MIT-lightgrey" alt="MIT">
</p>

---

```
 █████╗ ███████╗██╗███████╗████████╗███████╗███╗   ██╗████████╗███████╗
██╔══██╗██╔════╝██║██╔════╝╚══██╔══╝██╔════╝████╗  ██║╚══██╔══╝██╔════╝
███████║███████╗██║███████╗   ██║   █████╗  ██╔██╗ ██║   ██║   █████╗
██╔══██║╚════██║██║╚════██║   ██║   ██╔══╝  ██║╚██╗██║   ██║   ██╔══╝
██║  ██║███████║██║███████║   ██║   ███████╗██║ ╚████║   ██║   ███████╗
╚═╝  ╚═╝╚══════╝╚═╝╚══════╝   ╚═╝   ╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝

  ██╗   ██╗ ██████╗ ███████╗
  ██║   ██║██╔═══██╗╚══███╔╝
  ██║   ██║██║   ██║  ███╔╝
  ╚██╗ ██╔╝██║   ██║ ███╔╝
   ╚████╔╝ ╚██████╔╝███████╗
    ╚═══╝   ╚═════╝ ╚══════╝
```

<p align="center">
  <sup>Habla · Escucha · Piensa · Responde · <strong>Todo en tu máquina</strong></sup>
</p>

---

## ✨ ¿Qué es?

Un asistente de voz que corre **100% en local** sobre Linux. Pulsas `Ctrl+.`, hablas, y una voz natural te responde. Sin enviar tus conversaciones a ninguna nube. Sin latencia de red. Sin suscripciones.

- **Motor de IA** — Ollama con `llama3.2:3b` (configurable)
- **Reconocimiento de voz** — faster-whisper `small` + Silero VAD
- **Síntesis de voz** — Kokoro 82M (`ef_dora`, `em_alex`, `em_santa`) + 7 voces Piper de respaldo + espeak-ng ultraligero
- **Interfaz** — Panel minimalista con customtkinter, esquinas redondeadas y animaciones sutiles
- **Hotkey** — `Ctrl+.` para toggle de grabación (sin wake words que fallen)

---

## 🚀 Instalación

### Método rápido (recomendado)

```bash
git clone <repo-url>
cd Asistente-Voz
bash instalar.sh
```

Se abre un **wizard gráfico de 5 pasos** (customtkinter, modo oscuro) que te guía para:

1. ✅ Verificar/instalar dependencias del sistema
2. 🧠 Elegir modelo Ollama (plantilla o personalizado)
3. 🎤 Seleccionar y **probar** tu voz TTS favorita
4. ⚙️ Instalar, crear acceso directo y configurar auto-inicio
5. 🎉 ¡Listo!

### Instalación silenciosa (terminal pura)

```bash
bash instalar.sh --no-gui
bash instalar.sh --no-gui --voice ef_dora --model mi_asistente
```

### Manual (paso a paso)

```bash
# 1. Sistema
sudo apt install -y portaudio19-dev python3-pyaudio espeak-ng

# 2. Entorno virtual
python3 -m venv env_asistente
source env_asistente/bin/activate
pip install -r requirements.txt

# 3. Ollama
ollama serve &>/dev/null &
ollama pull llama3.2:3b
ollama create asistente_voz:latest -f Modelfile

# 4. ¡A volar!
python main.py
```

---

## 🎮 Uso

```bash
# Lanzador rápido (arranca Ollama + crea modelo si faltan)
bash bin/asistente-voz

# Directo (con el venv ya activo)
python main.py

# Con otra voz o modelo
python main.py --voice em_alex
python main.py --model qwen2.5:3b
```

### Cómo interactuar

| Acción | Resultado |
|--------|-----------|
| `Ctrl+.` (o clic en el botón) | Empieza a grabar 🔊 → habla |
| `Ctrl+.` otra vez | Termina grabación 🔔 → transcribe → IA responde |
| ✕ en el panel | Minimiza a la barra de tareas |
| ⚙ en el panel | Abre ajustes (voz, micrófono, auto-inicio) |
| ⚙ → Salir del asistente | Cierra la app completamente |

**Flujo típico**: `Ctrl+.` → *"¿Qué tiempo hace en Madrid?"* → `Ctrl+.` → beep → unos segundos → respuesta hablada 🎙️

### Acciones del sistema

Si tu petición lo requiere, el asistente ejecuta comandos en tu equipo:

| El modelo dice... | El asistente hace... |
|-------------------|----------------------|
| `[ACCION:ABRIR_NAVEGADOR]` | Abre el navegador |
| `[ACCION:ABRIR_TERMINAL]` | Abre una terminal |
| `[ACCION:ABRIR_CODE]` | Abre VS Code |
| `[ACCION:APAGAR_PANTALLA]` | Apaga la pantalla |
| `[ACCION:ABRIR_BUSQUEDA]` | Abre búsqueda web |

---

## 🎤 Voces disponibles (11 voces · 3 motores)

| Motor | Voces | Calidad | Peso |
|-------|-------|---------|------|
| **Kokoro 82M** | `ef_dora` ⭐, `em_alex`, `em_santa` | 🟢 Natural, expresiva | ~300 MB |
| **Piper** | `es_ES-sharvard-medium`, `es_ES-carlfm-x_low`, `es_ES-davefx-medium`, `es_ES-mls_10246-low`, `es_MX-ald-medium`, `es_MX-claude-high`, `es_AR-daniela-high` | 🟡 Robótica, funcional | ~50 MB c/u |
| **espeak-ng** | `espeak_es` | 🔴 Muy robótica, instantánea | ~5 MB |

> ⭐ `ef_dora` es la voz por defecto. Suena natural, cálida y cercana.

Cambia de voz en ⚙ → Ajustes → probar → aplicar. El cambio es inmediato.

### Probar voces desde terminal

```bash
source env_asistente/bin/activate
python scripts/probar_voces.py --listar
python scripts/probar_voces.py ef_dora
```

---

## 🧠 Modelos compatibles

Cualquier modelo de Ollama funciona. Probados y recomendados (~2 GB VRAM):

| Modelo | Tamaño | Ideal para... |
|--------|--------|---------------|
| `llama3.2:3b` ⭐ | 2.0 GB | Equilibrio velocidad/calidad |
| `llama3.2:1b` | 0.8 GB | Hardware muy limitado |
| `qwen2.5:3b` | 1.9 GB | Mejor español |
| `qwen2.5:1.5b` | 1.0 GB | Máxima velocidad |
| `phi3:3.8b` | 2.3 GB | Siguiendo instrucciones complejas |
| `gemma2:2b` | 1.6 GB | Alternativa sólida de Google |

> 💡 `num_ctx 4096` consume ~2.5 GB VRAM. Si tu GPU va justa, baja a `2048` en `Modelfile`.

---

## 🏗️ Arquitectura

```
main.py                     ← Orquestador (hotkey + proc-loop)
├── gui/
│   └── panel.py            ← Ventana customtkinter (Ctrl+., ⚙, ✕)
├── modulos/
│   ├── cerebro.py          ← Historial FIFO (6 interacciones)
│   ├── stt.py              ← Grabación + Silero VAD + faster-whisper
│   ├── tts.py              ← Kokoro | Piper | espeak-ng (auto-detecta)
│   ├── inferencia.py       ← Ollama chat con streaming
│   ├── acciones.py         ← [ACCION:XXX] → subprocess
│   └── vad.py              ← Silero VAD (onnxruntime, sin torch)
├── recursos/
│   ├── voces_disponibles.json
│   ├── silero_vad.onnx
│   ├── asistente-voz.{svg,png,desktop}
│   └── generar_icono.py
├── scripts/
│   ├── probar_voces.py
│   └── desinstalar.sh
├── bin/asistente-voz        ← Lanzador bash (auto-arranca Ollama)
├── instalar.sh              ← Instalador del sistema
├── instalar_gui.py          ← Wizard 5 pasos (customtkinter)
├── Modelfile                ← Configuración del modelo Ollama
└── config.json              ← Preferencias (gitignored)
```

### Pipeline de procesamiento (streaming)

```
Ctrl+.  →  🎙️ grabar  →  Ctrl+.  →  🔔 beep
  →  Silero VAD trim  →  faster-whisper  →  texto
  →  Ollama stream  →  [frase 1]  →  Kokoro TTS  →  🔊
                    →  [frase 2]  →  Kokoro TTS  →  🔊
                    →  [frase 3]  →  Kokoro TTS  →  🔊
```

> El TTS empieza a hablar en cuanto Ollama suelta la primera frase. No espera a que termine la respuesta completa.

---

## 🛠️ Entorno de desarrollo

```bash
source env_asistente/bin/activate
pip install -r requirements.txt

# Tests del núcleo (sin Ollama, sin audio, sin display)
python test/test_core.py

# Verificar dispositivos de audio
python -c "import sounddevice as sd; print(sd.query_devices())"
```

### Buenas prácticas

- **System prompt sincronizado**: `Modelfile`, `modulos/cerebro.py` e `instalar_gui.py` contienen el mismo system prompt. Si editas uno, copia en los otros dos.
- **Thread-safety**: Nunca llames a widgets tkinter/customtkinter desde hilos. Usa `_root_after()` o `self._panel._root.after(0, fn)`.
- **TTS async**: Usa `reproducir_async()` o `reproducir_streaming(cola)` — nunca `reproducir()` en el hilo principal.
- **Lock file**: `/tmp/asistente-voz.lock` previene instancias duplicadas.
- **Voces auto-descargables**: Piper y Kokoro descargan sus modelos al primer uso. Solo necesitas internet la primera vez.
- **Dependencias del sistema no negociables**: `portaudio19-dev`, `espeak-ng`, `python3-pyaudio`.

### Dependencias clave

| Paquete | Versión | Para qué |
|---------|---------|----------|
| `faster-whisper` | 1.2.1 | STT (modelo `small`, CPU, int8) |
| `kokoro` | 0.9.4 | TTS primario (82M params, `ef_dora`) |
| `piper-tts` | 1.4.2 | TTS fallback (7 voces español) |
| `customtkinter` | 5.2.2 | GUI moderna con esquinas redondeadas |
| `pynput` | 1.8.2 | Hotkey global `Ctrl+.` |
| `silero-vad` | 6.2.1 | Voice Activity Detection (solo ONNX) |
| `sounddevice` | 0.5.5 | Captura y reproducción de audio |
| `ollama` | 0.6.2 | Cliente Python para Ollama |
| `transformers` | ≥5.9.0 | Requerido por kokoro (compatibilidad) |

---

## 🩺 Solución de problemas

| Síntoma | Causa probable | Solución |
|---------|---------------|----------|
| No arranca | Ollama no está corriendo | `ollama serve` o usa `bash bin/asistente-voz` |
| No graba / error mic | Micrófono equivocado | ⚙ → Ajustes → seleccionar dispositivo → Aplicar |
| No se escucha TTS | `portaudio19-dev` o voz no descargada | `sudo apt install portaudio19-dev` o probar voz en ⚙ |
| Kokoro falla | `espeak-ng` no instalado o `transformers` obsoleto | `sudo apt install espeak-ng` + `pip install transformers>=5.9.0` |
| Respuesta lenta | `num_ctx` muy alto o modelo pesado | Baja `num_ctx` a 2048 o usa `llama3.2:1b` |
| Proceso zombie | Lock no liberado | `rm /tmp/asistente-voz.lock` |
| Segunda instancia | Lock previene duplicados | Cierra la primera o `rm /tmp/asistente-voz.lock` |
| Alucinaciones | VAD o ruido | Habla claro, en silencio, cerca del micro |

---

## 🙌 Aportaciones

¿Ideas? ¿Encontraste un bug? ¿Quieres añadir una voz nueva o un motor TTS?

- El sistema de motores TTS es **pluggable**: añadir un motor nuevo es una clase que implemente `sintetizar(texto) → np.ndarray`
- Las voces se registran en `recursos/voces_disponibles.json`
- Los modelos de Ollama se configuran en `Modelfile`

**PRs bienvenidos.** El archivo `AGENTS.md` contiene la guía para desarrolladores que quieran contribuir.

---

<p align="center">
  <sub>Hecho con ❤️ para Linux. Sin nube, sin telemetría, sin ataduras.</sub>
</p>
