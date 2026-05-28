#!/usr/bin/env python3
"""Asistente de Voz — Orquestador principal.

Uso: python main.py [--model NAME] [--voice NAME]
"""

import argparse
import atexit
import json
import logging
import os
import queue
import signal
import sys
import threading
import time
from pathlib import Path

import numpy as np
import sounddevice as sd

from modulos.cerebro import Cerebro
from modulos.inferencia import MotorInferencia
from modulos.stt import SpeechToText, STTConfig
from modulos.tts import SintetizadorVoz
from modulos.acciones import extraer_accion, ejecutar_accion

PROJECT_DIR = Path(__file__).resolve().parent
VOICES_JSON = PROJECT_DIR / "recursos" / "voces_disponibles.json"
LOCK_FILE = Path("/tmp/asistente-voz.lock")

def _load_voice_catalog():
    try:
        with open(VOICES_JSON) as f:
            return json.load(f)
    except Exception:
        logger.error("No se pudo cargar %s", VOICES_JSON)
        return {}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("asistente")


class AsistenteOrquestador:
    """Asistente de voz con hotkey Ctrl+. y TTS streaming."""

    def __init__(self, model: str = "asistente_voz:latest",
                 voice: str = "ef_dora",
                 device_index: int | None = None):
        self.model_name = model
        self.voice_name = voice
        self._device_index = device_index

        self.cerebro = Cerebro(max_interacciones=6, model=model, voice=voice)
        self.inferencia = MotorInferencia(model=model)
        self.stt = SpeechToText(STTConfig(device_index=device_index))
        self.stt.preload()
        self.tts: SintetizadorVoz | None = None

        self._cola_comandos: queue.Queue[str] = queue.Queue()
        self._vivo = threading.Event()
        self._vivo.set()
        self._procesando = threading.Lock()
        self._grabando = False
        self._grabando_lock = threading.Lock()

        self._panel = None
        self._ajustes_dialog = None

    def iniciar(self) -> None:
        signal.signal(signal.SIGINT, self._manejar_signal)
        signal.signal(signal.SIGTERM, self._manejar_signal)
        signal.signal(signal.SIGUSR1, self._mostrar_panel_signal)

        logger.info("Iniciando Asistente de Voz...")
        logger.info("Modelo: %s | Voz TTS: %s", self.model_name, self.voice_name)

        self.tts = SintetizadorVoz.obtener(self.voice_name)
        threading.Thread(target=self.tts._ensure_voice, daemon=True,
                         name="tts-init").start()
        threading.Thread(target=self._bucle_procesamiento, daemon=True,
                         name="proc-loop").start()
        threading.Thread(target=self._iniciar_hotkeys, daemon=True,
                         name="hotkey").start()

        self._iniciar_gui()

    # ── Hotkey ──────────────────────────────────────────────────

    def _iniciar_hotkeys(self) -> None:
        try:
            from pynput import keyboard
        except ImportError:
            logger.warning("pynput no instalado. Hotkey Ctrl+. no disponible.")
            return

        def on_activate():
            self._toggle_grabacion()

        try:
            listener = keyboard.GlobalHotKeys({"<ctrl>+.": on_activate})
            listener._hotkey_thread = True
            listener.start()
            while self._vivo.is_set():
                time.sleep(0.5)
            listener.stop()
        except Exception as e:
            logger.error("Error al iniciar hotkey: %s", e)

    # ── GUI ─────────────────────────────────────────────────────

    def _iniciar_gui(self) -> None:
        from gui.panel import PanelFlotante

        self._panel = PanelFlotante(model_name=self.model_name)
        self._panel.callbacks.on_toggle_record = self._toggle_grabacion
        self._panel.callbacks.on_close_panel = self._minimizar_panel
        self._panel.callbacks.on_quit = self._salir
        self._panel.callbacks.on_settings = self._mostrar_ajustes

        self._panel.mostrar()

    def _salir(self) -> None:
        logger.info("Cerrando asistente...")
        self._vivo.clear()
        self.stt._cancel.set()
        if self._panel and self._panel._root:
            self._panel._root.after(0, self._do_quit)
            self._panel._root.after(3000, self._do_quit)

    def _do_quit(self) -> None:
        if self._panel:
            self._panel.cerrar()
        _release_lock()
        os._exit(0)

    def _manejar_signal(self, signum, _frame) -> None:
        self._vivo.clear()
        self.stt._cancel.set()
        os._exit(0)

    def _mostrar_panel_signal(self, signum, _frame) -> None:
        if self._panel and self._panel._root:
            self._panel._root.after(0, self._panel.mostrar_panel)

    def _minimizar_panel(self) -> None:
        self._panel.ocultar()

    def _mostrar_ajustes(self) -> None:
        if self._panel is None or self._panel._root is None:
            return
        if self._ajustes_dialog is not None:
            try:
                if self._ajustes_dialog.winfo_exists():
                    self._ajustes_dialog.lift()
                    return
            except Exception:
                pass
            self._ajustes_dialog = None

        import tkinter as tk

        root = self._panel._root

        voices = self._flat_voices()
        voice_display = []
        voice_map = {}
        for v in voices:
            engine = v.get("engine", "piper").capitalize()
            label = f"{v['name']} ({engine})"
            voice_display.append(label)
            voice_map[label] = v["name"]
        default_label = next(
            (l for l, n in voice_map.items() if n == self.voice_name),
            voice_display[0] if voice_display else self.voice_name,
        )

        dialog = tk.Toplevel(root)
        self._ajustes_dialog = dialog
        dialog.title("Ajustes")
        dialog.geometry("340x540")
        dialog.configure(bg="#1a1d27")
        dialog.resizable(False, False)
        dialog.transient(root)

        def _on_destroy(_event):
            self._ajustes_dialog = None
        dialog.bind("<Destroy>", _on_destroy)

        FG = "#c8ccd4"
        ACC = "#242736"
        DIM = "#6e7380"
        BLUE = "#6c8cff"

        tk.Label(
            dialog, text="Ajustes del Asistente",
            font=("Cantarell", 13, "bold"),
            bg="#1a1d27", fg=FG,
        ).pack(pady=(14, 6))

        sep = tk.Frame(dialog, bg="#2d3140", height=1)
        sep.pack(fill=tk.X, padx=16)

        info_frame = tk.Frame(dialog, bg=ACC, padx=14, pady=12)
        info_frame.pack(fill=tk.X, padx=16, pady=(10, 4))

        tk.Label(
            info_frame, text=f"Modelo: {self.model_name}",
            font=("Cantarell", 10), bg=ACC, fg=FG,
        ).pack(anchor=tk.W, pady=2)

        voice_label = tk.Label(
            info_frame, text=f"Voz TTS: {self.voice_name}",
            font=("Cantarell", 10), bg=ACC, fg=FG,
        )
        voice_label.pack(anchor=tk.W, pady=(6, 2))

        voice_var = tk.StringVar(value=default_label)

        def _on_voice_change(choice: str) -> None:
            actual = voice_map.get(choice, choice)
            voice_label.config(text=f"Voz TTS: {actual}")
            status.config(text="")

        voice_menu = tk.OptionMenu(
            info_frame, voice_var, default_label, *voice_display,
            command=_on_voice_change,
        )
        voice_menu.config(
            font=("Cantarell", 9), bg="#2d3140", fg=FG,
            activebackground=BLUE, activeforeground="#ffffff",
            relief=tk.FLAT, bd=0, highlightthickness=0,
        )
        voice_menu["menu"].config(
            font=("Cantarell", 9), bg="#2d3140", fg=FG,
            activebackground=BLUE, activeforeground="#ffffff",
        )
        voice_menu.pack(anchor=tk.W, pady=(2, 0), ipadx=4)

        status = tk.Label(
            info_frame, text="", font=("Cantarell", 8),
            bg=ACC, fg=DIM,
        )
        status.pack(anchor=tk.W, pady=(4, 0))

        def _probar_voz() -> None:
            label = voice_var.get()
            name = voice_map.get(label, label)
            status.config(text="Reproduciendo prueba...")
            threading.Thread(
                target=self._play_voice_sample, args=(name, status),
                daemon=True).start()

        def _aplicar_voz() -> None:
            label = voice_var.get()
            name = voice_map.get(label, label)
            config_path = Path(__file__).resolve().parent / "config.json"
            config = {}
            if config_path.exists():
                try:
                    config = json.loads(config_path.read_text())
                except Exception:
                    pass
            config["voice"] = name
            config["model"] = self.model_name
            tmp = config_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(config, indent=2))
            os.replace(tmp, config_path)
            self.voice_name = name
            self.tts = SintetizadorVoz.obtener(name)
            voice_label.config(text=f"Voz TTS: {name}")
            status.config(
                text="Voz aplicada. Cambio inmediato en\nproximas respuestas.")

        btn_row = tk.Frame(info_frame, bg=ACC)
        btn_row.pack(fill=tk.X, pady=(8, 0))
        tk.Button(
            btn_row, text="Probar", font=("Cantarell", 9),
            bg="#2d3140", fg=FG, relief=tk.FLAT,
            activebackground=BLUE, activeforeground="#ffffff",
            cursor="hand2", bd=0, padx=12, pady=4,
            command=_probar_voz,
        ).pack(side=tk.LEFT, padx=(0, 4))
        tk.Button(
            btn_row, text="Aplicar", font=("Cantarell", 9, "bold"),
            bg=BLUE, fg="#ffffff", relief=tk.FLAT,
            activebackground="#8199ff", activeforeground="#ffffff",
            cursor="hand2", bd=0, padx=12, pady=4,
            command=_aplicar_voz,
        ).pack(side=tk.LEFT)

        autostart_dir = Path.home() / ".config" / "autostart"
        autostart_file = autostart_dir / "asistente-voz.desktop"
        config_autostart = _load_config().get("autostart", None)
        if config_autostart is not None:
            auto_value = config_autostart
        else:
            auto_value = autostart_file.exists()
        auto_var = tk.BooleanVar(value=auto_value)

        def _toggle_autostart():
            config_path = Path(__file__).resolve().parent / "config.json"
            config = {}
            if config_path.exists():
                try:
                    config = json.loads(config_path.read_text())
                except Exception:
                    pass
            if auto_var.get():
                autostart_dir.mkdir(parents=True, exist_ok=True)
                desktop_src = (Path.home() / ".local" / "share"
                               / "applications" / "asistente-voz.desktop")
                if desktop_src.exists():
                    if autostart_file.is_symlink():
                        autostart_file.unlink()
                    try:
                        autostart_file.symlink_to(desktop_src)
                    except OSError:
                        pass
                config["autostart"] = True
            else:
                if autostart_file.exists():
                    autostart_file.unlink()
                config["autostart"] = False
            tmp = config_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(config, indent=2))
            os.replace(tmp, config_path)

        tk.Checkbutton(
            info_frame, text="Iniciar al arrancar el sistema",
            variable=auto_var, font=("Cantarell", 9),
            bg=ACC, fg=FG, selectcolor=ACC,
            activebackground=ACC, activeforeground=FG,
            command=_toggle_autostart,
        ).pack(anchor=tk.W, pady=(12, 0))

        mic_sep = tk.Frame(dialog, bg="#2d3140", height=1)
        mic_sep.pack(fill=tk.X, padx=16, pady=(12, 0))

        mic_frame = tk.Frame(dialog, bg=ACC, padx=14, pady=12)
        mic_frame.pack(fill=tk.X, padx=16, pady=(8, 4))

        tk.Label(
            mic_frame, text="Microfono",
            font=("Cantarell", 10, "bold"), bg=ACC, fg=FG,
        ).pack(anchor=tk.W, pady=2)

        input_devices = self._obtener_dispositivos_entrada()
        default_label_mic = "Sistema (por defecto)"
        device_labels = [default_label_mic] + [
            d["label"] for d in input_devices]

        current_idx = self._device_index
        if current_idx is not None:
            matching = [d for d in input_devices
                        if d["index"] == current_idx]
            current_label = matching[0]["label"] if matching else default_label_mic
        else:
            current_label = default_label_mic

        mic_var = tk.StringVar(value=current_label)

        def _on_mic_change(choice: str) -> None:
            mic_status.config(text="")

        mic_menu = tk.OptionMenu(
            mic_frame, mic_var, current_label, *device_labels,
            command=_on_mic_change,
        )
        mic_menu.config(
            font=("Cantarell", 9), bg="#2d3140", fg=FG,
            activebackground=BLUE, activeforeground="#ffffff",
            relief=tk.FLAT, bd=0, highlightthickness=0,
        )
        mic_menu["menu"].config(
            font=("Cantarell", 9), bg="#2d3140", fg=FG,
            activebackground=BLUE, activeforeground="#ffffff",
        )
        mic_menu.pack(anchor=tk.W, pady=(2, 0), ipadx=4)

        mic_status = tk.Label(
            mic_frame, text="", font=("Cantarell", 8),
            bg=ACC, fg=DIM,
        )
        mic_status.pack(anchor=tk.W, pady=(4, 0))

        def _aplicar_mic() -> None:
            choice = mic_var.get()
            config_path = Path(__file__).resolve().parent / "config.json"
            config = {}
            if config_path.exists():
                try:
                    config = json.loads(config_path.read_text())
                except Exception:
                    pass
            if choice == default_label_mic:
                device_idx = None
            else:
                matching = [d for d in input_devices
                            if d["label"] == choice]
                device_idx = matching[0]["index"] if matching else None
            config["device_index"] = device_idx
            config["voice"] = self.voice_name
            config["model"] = self.model_name
            tmp = config_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(config, indent=2))
            os.replace(tmp, config_path)
            self._device_index = device_idx
            self.stt.config.device_index = device_idx
            mic_status.config(
                text="Microfono aplicado. Efectivo en\nla proxima grabacion.")

        btn_mic_row = tk.Frame(mic_frame, bg=ACC)
        btn_mic_row.pack(fill=tk.X, pady=(8, 0))
        tk.Button(
            btn_mic_row, text="Aplicar microfono",
            font=("Cantarell", 9, "bold"),
            bg=BLUE, fg="#ffffff", relief=tk.FLAT,
            activebackground="#8199ff", activeforeground="#ffffff",
            cursor="hand2", bd=0, padx=12, pady=4,
            command=_aplicar_mic,
        ).pack(side=tk.LEFT)

        btn_final_row = tk.Frame(dialog, bg="#1a1d27")
        btn_final_row.pack(fill=tk.X, padx=16, pady=(12, 14))
        tk.Button(
            btn_final_row, text="Salir del asistente",
            font=("Cantarell", 9),
            bg="#5e2a2a", fg=FG, relief=tk.FLAT,
            activebackground="#8e3a3a", activeforeground="#ffffff",
            cursor="hand2", bd=0, padx=16, pady=5,
            command=lambda: [dialog.destroy(), self._salir()],
        ).pack(side=tk.RIGHT)
        tk.Button(
            btn_final_row, text="Cerrar",
            font=("Cantarell", 10, "bold"),
            bg="#2d3140", fg=FG, relief=tk.FLAT,
            activebackground=BLUE, activeforeground="#ffffff",
            cursor="hand2", padx=24, pady=5,
            command=dialog.destroy,
        ).pack(side=tk.RIGHT, padx=(0, 8))

    @staticmethod
    def _flat_voices() -> list[dict]:
        result: list[dict] = []
        for _region, voces in _load_voice_catalog().items():
            for v in voces.values():
                result.append(v)
        return result

    @staticmethod
    def _obtener_dispositivos_entrada() -> list[dict]:
        devices: list[dict] = []
        for d in sd.query_devices():
            if d["max_input_channels"] > 0:
                label = (d["name"] if d["index"] is None
                         else f'{d["name"]} [{d["index"]}]')
                devices.append({
                    "index": d["index"],
                    "name": d["name"],
                    "label": label,
                })
        return devices

    def _play_voice_sample(self, name: str, status_label) -> None:
        try:
            tts = SintetizadorVoz.obtener(name)
            tts._ensure_voice()
            audio = tts.sintetizar(
                "Hola, soy tu asistente de voz.")
            if audio.size > 0:
                sd.play(audio, tts.sample_rate)
                sd.wait()
            self._panel._root.after(
                0, lambda: status_label.config(
                    text="Prueba completada"))
        except Exception as e:
            self._panel._root.after(
                0, lambda msg=str(e): status_label.config(
                    text=f"Error: {msg}"))

    # ── Grabacion ──────────────────────────────────────────────

    def _toggle_grabacion(self) -> None:
        with self._grabando_lock:
            if self._grabando:
                self._grabando = False
                self.stt._cancel.set()
                self._root_after(
                    lambda: self._panel.set_grabando(False))
                self._root_after(
                    lambda: self._panel.actualizar_estado(
                        "Procesando audio..."))
            else:
                self._grabando = True
                self._root_after(
                    lambda: self._panel.set_grabando(True))
                self._root_after(
                    lambda: self._panel.actualizar_estado(
                        "Grabando..."))
                self.stt._cancel.clear()
                threading.Thread(
                    target=self._grabar_worker, daemon=True).start()

    def _root_after(self, fn) -> None:
        if self._panel and self._panel._root:
            self._panel._root.after(0, fn)

    def _grabar_worker(self) -> None:
        sr = self.stt.config.sample_rate
        block_size = int(sr * self.stt.config.block_duration_ms / 1000)
        buffer: list[np.ndarray] = []

        def callback(indata, _frames, _time_info, status):
            if status:
                return
            buffer.append(indata.copy()[:, 0] if indata.ndim > 1
                          else indata.copy())

        try:
            with sd.InputStream(
                samplerate=sr, channels=1, dtype=np.float32,
                blocksize=block_size, callback=callback,
                device=self.stt.config.device_index,
            ):
                while not self.stt._cancel.is_set():
                    time.sleep(0.1)
                    max_blocks = int(self.stt.config.max_record_s * 1000 / self.stt.config.block_duration_ms)
                    if len(buffer) >= max_blocks:
                        self.stt._cancel.set()
                        break
        except Exception as e:
            logger.error("Error en grabacion: %s", e)
            self._root_after(
                lambda: self._panel.actualizar_estado(
                    "Error de microfono"))
            with self._grabando_lock:
                self._grabando = False
            self._root_after(
                lambda: self._panel.set_grabando(False))
            return

        with self._grabando_lock:
            self._grabando = False
        self._root_after(
            lambda: self._panel.set_grabando(False))

        if not buffer:
            return

        audio = np.concatenate(buffer)
        if audio.size < sr * 0.5:
            self._root_after(
                lambda: self._panel.actualizar_estado(
                    "Audio demasiado corto"))
            return

        self._beep_feedback()
        self._root_after(
            lambda: self._panel.actualizar_estado(
                "Procesando audio..."))
        texto = self.stt.transcribe_audio(audio)
        if texto:
            logger.info("Comando: %s", texto)
            self._cola_comandos.put(texto)
        else:
            self._root_after(
                lambda: self._panel.actualizar_estado(
                    "No se entendio"))

    def _beep_feedback(self) -> None:
        try:
            sr = 22050
            duration = 0.1
            freq = 660
            t = np.linspace(0, duration, int(sr * duration),
                            endpoint=False)
            tone = np.sin(2 * np.pi * freq * t) * 0.3
            envelope = np.linspace(0, 1, len(tone) // 8)
            tone[:len(envelope)] *= envelope
            tone[-len(envelope):] *= envelope[::-1]
            sd.play(tone, sr)
        except Exception:
            pass

    # ── Procesamiento ─────────────────────────────────────────

    def _bucle_procesamiento(self) -> None:
        logger.info("Bucle de procesamiento iniciado")
        while self._vivo.is_set():
            try:
                texto = self._cola_comandos.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self._procesar_comando(texto)
            except Exception as e:
                logger.error("Error en procesamiento: %s", e, exc_info=True)
                self._root_after(
                    lambda: self._panel.actualizar_estado("Error de procesamiento"))

    def _procesar_comando(self, texto: str) -> None:
        with self._procesando:
            self._root_after(
                lambda: self._panel.actualizar_estado("Pensando..."))
            logger.info("Procesando: %s", texto)

            try:
                stream = self.inferencia.generar_stream(
                    self.cerebro.historial
                )
                self.cerebro.agregar_usuario(texto)
            except Exception as e:
                logger.error("Error inferencia: %s", e)
                respuesta = ("Lo siento, ha ocurrido un error al "
                             "procesar tu solicitud.")
                self._root_after(
                    lambda: self._panel.actualizar_estado(
                        "Error de inferencia"))
                self.cerebro.agregar_asistente(respuesta)
                self.tts.reproducir_async(respuesta)
                self._root_after(
                    lambda: self._panel.actualizar_estado(
                        "Esperando..."))
                return

            SEP_SENTENCE = (".", "!", "?", "\n")
            buf = ""
            frase_buffer = ""
            cola_tts = None
            modo_sincrono = False

            for fragmento in stream:
                buf += fragmento

                if cola_tts is None:
                    stripped = buf.lstrip()
                    if (stripped.startswith("[ACCION:")
                            and ("] " in stripped
                                 or stripped.endswith("]"))):
                        modo_sincrono = True
                        cola_tts = queue.Queue()
                    elif stripped and not stripped.startswith(
                            "[ACCION:"):
                        cola_tts = queue.Queue()
                        threading.Thread(
                            target=self.tts.reproducir_streaming,
                            args=(cola_tts,), daemon=True,
                        ).start()

                if cola_tts is not None and not modo_sincrono:
                    frase_buffer += fragmento
                    while True:
                        found = False
                        for sep in SEP_SENTENCE:
                            idx = frase_buffer.find(sep)
                            if idx != -1:
                                frase = frase_buffer[
                                    :idx + 1].strip()
                                frase_buffer = frase_buffer[
                                    idx + 1:]
                                acc = extraer_accion(frase)
                                if acc:
                                    _ = ejecutar_accion(acc)
                                    frase = frase.split(
                                        "]", 1)[-1].strip()
                                if frase:
                                    cola_tts.put(frase)
                                found = True
                                break
                        if not found:
                            break

            respuesta = buf.strip()
            if not respuesta:
                if cola_tts is not None and not modo_sincrono:
                    cola_tts.put(None)
                return

            if modo_sincrono:
                accion = extraer_accion(respuesta)
                if accion:
                    logger.info("Accion detectada: %s",
                                accion.tag.value)
                    self._root_after(
                        lambda a=accion.tag.value: (
                            self._panel.actualizar_estado(
                                f"Ejecutando: {a}")))
                    resultado = ejecutar_accion(accion)
                    respuesta_limpia = (
                        respuesta.split("]", 1)[-1].strip()
                        if "]" in respuesta else ""
                    )
                    texto_tts = (
                        resultado if not respuesta_limpia
                        else respuesta_limpia
                    )
                else:
                    texto_tts = respuesta

                self.cerebro.agregar_asistente(respuesta)

                if texto_tts:
                    self._root_after(
                        lambda: self._panel.actualizar_estado(
                            "Hablando..."))
                    try:
                        self.tts.reproducir_async(texto_tts)
                    except Exception as e:
                        logger.error("Error TTS: %s", e)
            else:
                self.cerebro.agregar_asistente(respuesta)
                if frase_buffer.strip():
                    acc = extraer_accion(frase_buffer)
                    if acc:
                        _ = ejecutar_accion(acc)
                        frase_buffer = frase_buffer.split(
                            "]", 1)[-1].strip()
                    if frase_buffer.strip():
                        cola_tts.put(frase_buffer.strip())
                cola_tts.put(None)
                self._root_after(
                    lambda: self._panel.actualizar_estado(
                        "Hablando..."))

            self._root_after(
                lambda: self._panel.actualizar_estado(
                    "Esperando..."))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Asistente de Voz Local — Hotkey Ctrl+. + TTS")
    parser.add_argument("--model", default=None,
                        help="Modelo Ollama (default: asistente_voz:latest)")
    parser.add_argument("--voice", default=None,
                        help="Voz TTS (default: ef_dora)")
    return parser.parse_args()


def _load_config() -> dict:
    config_path = Path(__file__).resolve().parent / "config.json"
    if config_path.exists():
        try:
            with open(config_path) as f:
                return json.load(f)
        except Exception as e:
            logger.warning("No se pudo leer config.json, usando valores por defecto: %s", e)
    return {}


def _acquire_lock() -> bool:
    if LOCK_FILE.exists():
        try:
            old_pid = int(LOCK_FILE.read_text().strip().split()[0])
            mtime = LOCK_FILE.stat().st_mtime
            if time.time() - mtime > 3600:
                LOCK_FILE.unlink()
                raise ProcessLookupError()
            os.kill(old_pid, 0)
            os.kill(old_pid, signal.SIGUSR1)
            logger.info("Mostrando ventana de instancia existente (PID %s).", old_pid)
            return False
        except (ValueError, ProcessLookupError, OSError):
            pass
    LOCK_FILE.write_text(f"{os.getpid()} {int(time.time())}")
    return True


def _release_lock() -> None:
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def main() -> None:
    if not _acquire_lock():
        print("Restaurando ventana del asistente...")
        return
    atexit.register(_release_lock)

    args = parse_args()
    config = _load_config()

    model = args.model or config.get("model") or "asistente_voz:latest"
    voice = args.voice or config.get("voice") or "ef_dora"
    device_index = config.get("device_index")
    if device_index is not None and not isinstance(device_index, int):
        device_index = None

    asistente = AsistenteOrquestador(
        model=model,
        voice=voice,
        device_index=device_index,
    )
    asistente.iniciar()


if __name__ == "__main__":
    main()
