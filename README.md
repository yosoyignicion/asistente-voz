# ⚠️ Proyecto adaptado a hardware específico

Este proyecto está optimizado para una **AMD Radeon RX 580 (8 GB VRAM)** con aceleración GPU vía **Ollama + Vulkan** y modelo **gemma2:2b**. El backend Vulkan está compilado para esta GPU concreta. Si tu hardware es diferente (otra GPU, sin GPU, NVIDIA, Apple Silicon), necesitarás investigar y adaptar la configuración de Ollama, el modelo y los parámetros de VRAM. **No es plug-and-play universal.**

---

<p align="center">
  <img src="recursos/asistente-voz.svg" width="96" alt="Micrófono azul">
</p>

<p align="center">
  <strong>
    Tu asistente de voz privado, offline y que habla español de verdad<br>
    Sin nube. Sin telemetría. Sin excusas.
  </strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Ollama-gemma2:2b_GPU_Vulkan-orange?logo=ollama" alt="Ollama">
  <img src="https://img.shields.io/badge/TTS-Kokoro_82M-hotpink" alt="Kokoro">
  <img src="https://img.shields.io/badge/STT-faster--whisper_base_+_Silero_VAD-green" alt="STT">
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

## Que es esto

Un asistente de voz que funciona **100% en tu ordenador, sin internet**. Pulsas `Ctrl+.`, hablas, y una voz natural te responde. Tus conversaciones nunca salen de tu disco duro. No necesitas cuenta, no hay suscripcion, no hay latencia de red.

**Como funciona (en lenguaje llano):**

1. **Escucha** — El microfono captura tu voz mientras mantienes pulsado `Ctrl+.`
2. **Transcribe** — Un modelo de IA (faster-whisper) convierte el audio en texto, recortando los silencios automaticamente
3. **Piensa** — Otro modelo de IA (gemma2:2b, ejecutandose en tu GPU) lee tu pregunta y genera una respuesta en español
4. **Habla** — Un sintetizador de voz (Kokoro) convierte la respuesta en audio y lo reproduce por tus altavoces

Todo esto ocurre en **~3 segundos** (0.9s transcribir + 0.5s pensar + 1.6s hablar).

---

## Que necesitas (requisitos de hardware)

Este proyecto esta probado con esta configuracion. Con otro hardware podria funcionar, pero no esta garantizado:

| Componente | Minimo recomendado | Este proyecto usa |
|---|---|---|
| **GPU** | AMD/NVIDIA con soporte Vulkan, 4+ GB VRAM | AMD Radeon RX 580 (8 GB) |
| **RAM** | 8 GB | 16 GB |
| **CPU** | x86_64, 2+ nucleos | AMD Athlon 3000G (2C/4T) |
| **Disco** | ~5 GB libres (modelos + dependencias) | SSD |
| **Sistema** | Linux con Vulkan (`mesa-vulkan-drivers`) | Ubuntu/Debian |
| **Microfono** | Cualquier microfono reconocido por PulseAudio | Integrado/USB |

**Sin GPU**: gemma2:2b funciona en CPU pero es ~5 veces mas lento (2-3s por respuesta en vez de 0.5s).

**Como saber si tu GPU soporta Vulkan**:

```bash
vulkaninfo --summary 2>/dev/null | grep deviceName
# Deberia mostrar el nombre de tu GPU
```

---

## Instalacion (no necesitas saber de programacion)

### El metodo facil: wizard grafico

```bash
git clone https://github.com/yosoyignicion/asistente-voz.git
cd Asistente-Voz
bash scripts/preparar_entorno.sh   # prepara Ollama + modelo base
bash instalar.sh
```

Se abrira una ventana que te guia paso a paso:

1. **Bienvenida** — Verifica que Ollama esta instalado y funcionando
2. **Modelo IA** — Elige la configuracion del cerebro del asistente (viene una por defecto que funciona)
3. **Voz** — Escucha y elige entre 10 voces diferentes (3 naturales + 7 roboticas)
4. **Instalar** — El programa descarga lo necesario, crea accesos directos y configura el auto-inicio
5. **Listo** — Ya puedes usar el asistente

> El instalador te ofrece ejecutar `scripts/preparar_entorno.sh` primero para dejar Ollama listo. Si ya tienes Ollama y gemma2:2b descargado, puedes saltarlo.

### Metodo manual (si prefieres la terminal)

```bash
# 1. Dependencias del sistema
sudo apt install -y portaudio19-dev python3-pyaudio espeak-ng

# 2. Entorno virtual Python
python3 -m venv env_asistente
source env_asistente/bin/activate
pip install -r requirements.txt

# 3. Ollama con aceleracion GPU (Vulkan)
OLLAMA_VULKAN=1 ollama serve &>/dev/null &
sleep 3
ollama pull gemma2:2b
ollama create asistente_voz:latest -f Modelfile

# 4. Arrancar
python main.py
```

### Activar GPU (critico para velocidad)

Ollama necesita arrancar con la variable `OLLAMA_VULKAN=1` para usar tu GPU. Sin esto, el modelo corre en CPU y es mucho mas lento.

El script `bin/asistente-voz` ya lo hace automaticamente. Si arrancas Ollama manualmente:

```bash
# Parar el servidor actual
pkill ollama

# Arrancar con GPU Vulkan
OLLAMA_VULKAN=1 ollama serve &>/dev/null &

# Verificar que la GPU esta activa
ollama ps
# Debe mostrar: gemma2:2b  ...  100% GPU
```

---

## Como se usa

```bash
# Lanzador recomendado (arranca Ollama con GPU + crea el modelo si falta)
bash bin/asistente-voz

# Directo con Python (si el venv ya esta activo)
python main.py

# Con otra voz
python main.py --voice em_alex
```

### Controles

| Accion | Resultado |
|---|---|
| **Mantener pulsado `Ctrl+.`** | Empieza a grabar. Habla mientras lo mantienes |
| **Soltar `Ctrl+.`** | Termina grabacion, suena un beep, y el asistente responde |
| Clic en el boton del panel | Alternativa al atajo de teclado (toggle) |
| **X** en la esquina | Minimiza a la bandeja del sistema (no cierra) |
| **Engranaje** | Abre ajustes: elegir voz, cambiar microfono, salir |

**Consejos para que funcione bien:**
- Habla cerca del microfono
- Haz frases claras y concretas (funciona mejor que peticiones muy complejas)
- Si hay ruido de fondo, acercate mas al micro
- La primera respuesta tarda ~5s (el modelo se carga en la GPU). Las siguientes son instantaneas (~0.5s)

---

## Voces disponibles (10 voces, 2 motores)

| Motor | Voces | Como suena | Lo que ocupa |
|---|---|---|---|
| **Kokoro 82M** | `ef_dora`, `em_alex`, `em_santa` | Natural, expresiva, calida | ~300 MB |
| **Piper** | `es_ES-*` (4), `es_MX-*` (2), `es_AR-*` (1) | Robotica pero funcional | ~50 MB cada una |

La voz por defecto es `ef_dora` (femenina, natural, en español). Para cambiar de voz: `Engranaje > Ajustes`, selecciona una, pulsa "Probar" para escucharla, y "Aplicar" para usarla.

---

## Arquitectura (por si quieres entender como va por dentro)

```
main.py                    ← Orquestador: hotkey + bucle de procesamiento
├── gui/
│   └── panel.py           ← Ventana: boton toggle, animacion, ajustes
├── modulos/
│   ├── cerebro.py         ← Memoria de conversacion (recuerda 6 interacciones)
│   ├── stt.py             ← Microfono + Silero VAD + faster-whisper (transcripcion)
│   ├── tts.py             ← Kokoro (principal) + Piper (respaldo)
│   ├── inferencia.py      ← Ollama: envia el texto y recibe respuesta por streaming
│   └── vad.py             ← Deteccion de voz: recorta silencios del audio
├── recursos/
│   ├── voces_disponibles.json
│   ├── silero_vad.onnx     ← Modelo de deteccion de voz (ONNX, sin torch)
│   └── asistente-voz.{svg,png,desktop}
├── scripts/
│   ├── preparar_entorno.sh ← Configura Ollama + descarga modelo base
│   └── probar_voces.py    ← Prueba voces desde terminal
├── bin/asistente-voz       ← Lanzador: arranca Ollama con GPU + main.py
├── instalar.sh             ← Instalador del sistema
├── instalar_gui.py         ← Wizard grafico de instalacion (5 pasos)
├── Modelfile               ← Personalidad y parametros del modelo Ollama
└── config.json             ← Tus preferencias (voz, microfono, auto-inicio)
```

### Que pasa cuando hablas (el pipeline)

```
Mantienes Ctrl+. →  Graba audio  →  Sueltas Ctrl+. →  Beep
  →  Silero VAD recorta silencios  →  faster-whisper transcribe  →  texto
  →  Ollama (gemma2:2b en GPU) genera respuesta  →  Kokoro sintetiza voz  →  Altavoces
```

El asistente empieza a hablar en cuanto Ollama genera la primera frase. No espera a tener la respuesta completa.

### Por que es rapido: GPU Vulkan

La GPU procesa el modelo de IA ~5 veces mas rapido que la CPU:

| Sin GPU (CPU Athlon 3000G) | Con GPU (RX 580 Vulkan) |
|---|---|
| ~12 tokens/segundo | ~61 tokens/segundo |
| ~6s por respuesta | ~0.5s por respuesta |
| 0% GPU | ~25% VRAM usada (~2 GB) |

---

## Solucion de problemas

| Sintoma | Causa probable | Que hacer |
|---|---|---|
| No arranca | Ollama no esta corriendo | Ejecuta `ollama serve` en otra terminal o usa `bash bin/asistente-voz` |
| No graba | Microfono equivocado | `Engranaje > Ajustes > seleccionar dispositivo > Aplicar` |
| No se escucha la voz | Falta `portaudio19-dev` | `sudo apt install portaudio19-dev` |
| Va muy lento | GPU no activada | `OLLAMA_VULKAN=1 ollama serve`. Verifica con `ollama ps` (debe mostrar GPU) |
| Kokoro falla | Falta `espeak-ng` | `sudo apt install espeak-ng` |
| La primera respuesta tarda mucho | El modelo se esta cargando en VRAM | Normal, tarda ~4s la primera vez. Las siguientes son instantaneas |
| Dice cosas raras | Ruido de fondo o VAD activo | Habla claro y cerca del micro, sin ruido de fondo |
| Segunda instancia no abre | El programa ya esta corriendo | Solo puede haber una. Cierra la anterior o `rm /tmp/asistente-voz.lock` |
| Proceso no muere al cerrar | Hilos bloqueados | `pkill -f "python main.py"` y `rm /tmp/asistente-voz.lock` |

---

## Preguntas frecuentes (FAQ)

### Necesito internet?

**Solo la primera vez**, para descargar los modelos de IA (~2.5 GB en total). Una vez descargados, el asistente funciona completamente offline. No se envia nada a la nube.

### Funciona con cualquier acento de español?

Si. Whisper base entiende variedades de español (España, Mexico, Argentina, Chile...). Cuanto mas claro y despacio hables, mejor funciona. En entornos con mucho ruido de fondo, acerca el microfono.

### Puedo usarlo sin GPU?

Si, pero mas lento. En CPU, el modelo tarda ~2-3 segundos en generar la respuesta (vs 0.5s con GPU). Si no tienes GPU, el asistente funciona igual — solo necesitas paciencia.

### Cuanto ocupa en disco?

Aproximadamente **5 GB** en total:

| Que | Cuanto |
|---|---|
| Entorno virtual Python (env_asistente/) | ~1 GB |
| Modelo gemma2:2b (Ollama) | ~1.6 GB |
| Kokoro (voz natural) | ~300 MB |
| Piper (voces de respaldo, 50 MB c/u) | ~50-100 MB |
| Whisper base (transcripcion) | ~100 MB |
| Resto (codigo, iconos, VAD) | ~20 MB |

### Que hago si el asistente no me entiende?

1. Habla mas claro y mas cerca del microfono
2. Usa frases cortas y concretas (ej: "que hora es" en vez de "me podrias decir por favor que hora es ahora mismo")
3. Evita ruido de fondo (ventiladores, television, calle)
4. Si el problema persiste, prueba otro microfono desde `Ajustes > seleccionar dispositivo > Aplicar`

### Se puede cambiar el atajo de teclado?

Si. Edita `main.py`, busca `"<ctrl>+."` y cambialo. Por ejemplo, `"<ctrl>+<alt>+a"` activaria con Ctrl+Alt+A.

### Puedo cambiar de voz sin reiniciar?

Si, desde `Ajustes > seleccionar voz > Aplicar`. El cambio es inmediato, no necesitas reiniciar nada.

### Que tan privado es realmente?

**100% local.** Todo el procesamiento ocurre en tu maquina:
- El audio de tu voz se procesa y se descarta (nunca se guarda)
- El modelo de IA (gemma2:2b) corre en tu GPU, no en un servidor
- No hay cuentas, inicios de sesion, ni telemetria
- Sin conexion a internet, el asistente funciona igual

### Puedo hacer que ejecute comandos en mi ordenador?

No. Esta version es solo conversacion: preguntas, ideas, explicaciones, curiosidades. No abre programas, no ejecuta comandos, no accede a archivos.

### Cuantas conversaciones recuerda?

Las ultimas **6 interacciones** (cada interaccion = tu pregunta + su respuesta). Si le preguntas tu nombre y 7 mensajes despues se lo vuelves a preguntar, lo habra olvidado. Al cerrar el asistente, se olvida todo.

### Por que la primera respuesta tarda mas?

La primera vez que hablas, el modelo gemma2:2b se carga desde el disco a la memoria de la GPU (VRAM). Esto tarda ~4 segundos. Las siguientes respuestas son instantaneas (~0.5s) porque el modelo ya esta en VRAM. Si cierras Ollama, al volver a abrirlo tendra que cargar el modelo otra vez.

---

## Para desarrolladores

```bash
source env_asistente/bin/activate

# Ejecutar tests del nucleo (sin Ollama, sin audio, sin ventana)
python test/test_core.py

# Ver que dispositivos de audio tienes
python -c "import sounddevice as sd; print(sd.query_devices())"
```

### Reglas importantes

- **System prompt sincronizado**: Si editas la personalidad del asistente, tienes que copiar el mismo texto en 3 sitios: `Modelfile`, `modulos/cerebro.py`, `instalar_gui.py`.
- **Nunca bloquees el hilo principal**: Las operaciones de TTS, STT e inferencia van en hilos separados.
- **Usa `bin/asistente-voz` para lanzar**: Se encarga de arrancar Ollama con GPU, crear el modelo si falta, y lanzar `main.py`.

El archivo `AGENTS.md` tiene la documentacion tecnica completa (threading, errores comunes, arquitectura detallada).

---

<p align="center">
  <sub>Hecho para Linux. Sin nube, sin telemetria, sin ataduras.</sub>
</p>
