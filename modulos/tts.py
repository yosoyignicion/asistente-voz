import json
import pathlib
import queue
import subprocess
import threading
import tempfile
from typing import ClassVar

import numpy as np
import onnxruntime
from piper.config import PiperConfig
from piper.download_voices import download_voice
from piper.voice import PiperVoice

VOICE_CACHE_DIR = pathlib.Path(__file__).resolve().parent.parent / "piper_voices"

KOKORO_VOICES = {"ef_dora", "em_alex", "em_santa"}
ESPEAK_VOICES = {"espeak_es"}


class SintetizadorVoz:
    """Sintetizador TTS triple: Kokoro 82M + Piper + espeak-ng (ultraligero)."""

    VOZ_POR_DEFECTO: ClassVar[str] = "ef_dora"
    _instances: ClassVar[dict[str, "SintetizadorVoz"]] = {}
    _lock: ClassVar[threading.Lock] = threading.Lock()
    _kokoro_pipeline: ClassVar[object | None] = None
    _kokoro_lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, voice_name: str | None = None):
        self.voice_name = voice_name or self.VOZ_POR_DEFECTO
        if self.voice_name in KOKORO_VOICES:
            self._engine = "kokoro"
        elif self.voice_name in ESPEAK_VOICES:
            self._engine = "espeak"
        else:
            self._engine = "piper"
        self._voice: PiperVoice | None = None
        self._sample_rate: int = 22050
        self._ready = threading.Event()

    @classmethod
    def obtener(cls, voice_name: str | None = None) -> "SintetizadorVoz":
        name = voice_name or cls.VOZ_POR_DEFECTO
        with cls._lock:
            if name not in cls._instances:
                instance = cls(name)
                cls._instances[name] = instance
            return cls._instances[name]

    @classmethod
    def _get_kokoro_pipeline(cls):
        with cls._kokoro_lock:
            if cls._kokoro_pipeline is None:
                import torch as _torch
                if not hasattr(_torch.nn.Module, "device"):
                    _torch.nn.Module.device = property(
                        lambda self: next(self.parameters()).device)
                from kokoro import KPipeline
                cls._kokoro_pipeline = KPipeline(lang_code="e", device="cpu")
        return cls._kokoro_pipeline

    def _ensure_voice(self) -> None:
        if self._ready.is_set():
            return
        if self._engine == "kokoro":
            self._get_kokoro_pipeline()
            self._sample_rate = 24000
            self._ready.set()
        elif self._engine == "espeak":
            self._sample_rate = 22050
            self._ready.set()
        else:
            VOICE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            model_path = VOICE_CACHE_DIR / f"{self.voice_name}.onnx"
            config_path = VOICE_CACHE_DIR / f"{self.voice_name}.onnx.json"
            if not model_path.exists() or not config_path.exists():
                download_voice(self.voice_name, VOICE_CACHE_DIR)
            with open(config_path) as f:
                raw = json.load(f)
            pipe_version = raw.get("piper_version")
            if pipe_version is not None:
                piper_config = PiperConfig.from_dict(raw)
                self._sample_rate = piper_config.sample_rate
            else:
                num_symbols = len(raw.get("phoneme_id_map", {}))
                piper_config = PiperConfig(
                    num_symbols=max(num_symbols, 1),
                    num_speakers=raw.get("num_speakers", 1),
                    sample_rate=raw["audio"]["sample_rate"],
                    espeak_voice=raw["espeak"]["voice"],
                    phoneme_id_map=raw.get("phoneme_id_map", {}),
                    phoneme_type=raw.get("phoneme_type", "espeak"),
                    speaker_id_map=raw.get("speaker_id_map", {}),
                )
                self._sample_rate = piper_config.sample_rate
            session = onnxruntime.InferenceSession(str(model_path))
            self._voice = PiperVoice(session, piper_config)
            self._ready.set()

    def sintetizar(self, texto: str) -> np.ndarray:
        """Convierte texto a array de audio float32. Bloquea hasta terminar."""
        self._ensure_voice()
        if self._engine == "kokoro":
            pipeline = self._get_kokoro_pipeline()
            generator = pipeline(
                texto, voice=self.voice_name, speed=1.0,
                split_pattern=r"(?<=[.!?])\s+",
            )
            chunks = []
            for _, _, audio in generator:
                if hasattr(audio, "cpu"):
                    audio = audio.cpu().numpy()
                chunks.append(np.asarray(audio, dtype=np.float32))
            if not chunks:
                return np.array([], dtype=np.float32)
            return np.concatenate(chunks)
        elif self._engine == "espeak":
            import soundfile as sf
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name
            try:
                subprocess.run(
                    ["espeak-ng", "-v", "es", "-w", tmp_path, texto],
                    capture_output=True, timeout=10,
                )
                audio, sr = sf.read(tmp_path)
                if audio.ndim > 1:
                    audio = audio[:, 0]
                self._sample_rate = sr
                return audio.astype(np.float32)
            finally:
                import os
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
        else:
            chunks = list(self._voice.synthesize(texto))
            if not chunks:
                return np.array([], dtype=np.float32)
            return np.concatenate([chunk.audio_float_array for chunk in chunks])

    def reproducir(self, texto: str) -> None:
        """Sintetiza y reproduce el texto. Bloquea hasta terminar la reproduccion."""
        import sounddevice as sd
        audio = self.sintetizar(texto)
        if audio.size == 0:
            return
        sd.play(audio, self._sample_rate)
        sd.wait()

    def reproducir_async(self, texto: str) -> None:
        """Reproduce en un hilo separado. No bloquea."""
        threading.Thread(target=self.reproducir, args=(texto,),
                         daemon=True).start()

    def reproducir_streaming(self, cola_frases: queue.Queue) -> None:
        """Reproduce frases de una cola en tiempo real via OutputStream.

        La cola recibe str (frase a sintetizar) o None (fin de stream).
        Usa OutputStream.write() para playback sin gaps entre frases.
        """
        import sounddevice as sd
        self._ensure_voice()
        stream = sd.OutputStream(
            samplerate=self._sample_rate, channels=1, dtype="float32",
            blocksize=0, latency="low",
        )
        stream.start()
        try:
            while True:
                texto = cola_frases.get()
                if texto is None:
                    break
                audio = self.sintetizar(texto)
                if audio.size > 0:
                    stream.write(audio)
        finally:
            stream.stop()
            stream.close()

    @property
    def sample_rate(self) -> int:
        self._ensure_voice()
        return self._sample_rate
