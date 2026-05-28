"""Silero VAD — Voice Activity Detection via ONNX (sin torch)."""

import importlib.util
import logging
import os
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort

logger = logging.getLogger(__name__)

_SPEC = importlib.util.find_spec("silero_vad")
if _SPEC and _SPEC.origin and not _SPEC.origin.endswith("__init__.py"):
    _SITE_PKGS_FALLBACK = Path(_SPEC.origin).parent / "data" / "silero_vad.onnx"
else:
    _SITE_PKGS_FALLBACK = None

_ONNX_PATHS = [
    (Path(__file__).resolve().parent.parent / "recursos" / "silero_vad.onnx"),
] + ([_SITE_PKGS_FALLBACK] if _SITE_PKGS_FALLBACK else [])


def _find_model() -> str:
    for p in _ONNX_PATHS:
        if p.exists():
            return str(p)
    raise FileNotFoundError(
        "Modelo Silero VAD no encontrado. Copia silero_vad.onnx a recursos/ "
        "o instala: pip install --no-deps silero-vad"
    )


class SileroVAD:
    """Wrapper puro numpy + onnxruntime del modelo Silero VAD."""

    def __init__(self, model_path: str | None = None, force_cpu: bool = True):
        path = model_path or _find_model()
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        providers = (["CPUExecutionProvider"] if force_cpu
                     else ort.get_available_providers())
        self.session = ort.InferenceSession(path, providers=providers,
                                            sess_options=opts)
        self._h = np.zeros((2, 1, 128), dtype=np.float32)
        self._c = np.zeros((1, 64), dtype=np.float32)
        self._context_size = 64

    def reset_states(self) -> None:
        self._h = np.zeros((2, 1, 128), dtype=np.float32)
        self._c = np.zeros((1, 64), dtype=np.float32)

    def _validate(self, x: np.ndarray, sr: int) -> np.ndarray:
        if x.ndim == 1:
            x = x.reshape(1, -1)
        if x.ndim > 2:
            raise ValueError(f"Demasiadas dimensiones: {x.ndim}")
        if sr != 16000 and (sr % 16000 == 0):
            step = sr // 16000
            x = x[:, ::step]
        if sr not in (8000, 16000):
            raise ValueError(f"Sample rate no soportado: {sr}")
        return x.astype(np.float32)

    def process(self, x: np.ndarray, sr: int = 16000) -> float:
        """Procesa chunk de audio y devuelve probabilidad de voz [0,1]."""
        x = self._validate(x, sr)
        num_samples = 512 if sr == 16000 else 256
        if x.shape[-1] != num_samples:
            raise ValueError(
                f"Chunk debe tener {num_samples} samples, tiene {x.shape[-1]}")

        inp = np.concatenate([self._c, x], axis=1)
        ort_in = {
            "input": inp,
            "state": self._h,
            "sr": np.array(sr, dtype=np.int64),
        }
        out, state = self.session.run(None, ort_in)
        self._h = state
        self._c = inp[:, -self._context_size:]
        return float(out[0, 0])

    def process_full(self, audio: np.ndarray,
                     sr: int = 16000) -> np.ndarray:
        """Procesa audio completo, devuelve probabilidades por chunk."""
        audio = audio.astype(np.float32)
        if audio.ndim == 1:
            audio = audio.reshape(1, -1)
        sr_eff = 16000
        if sr > 16000 and sr % 16000 == 0:
            step = sr // 16000
            audio = audio[:, ::step]
            sr_eff = 16000
        self.reset_states()
        num_samples = 512 if sr_eff == 16000 else 256
        total = audio.shape[1]
        probs = []
        for i in range(0, total, num_samples):
            chunk = audio[:, i:i + num_samples]
            if chunk.shape[1] < num_samples:
                pad = num_samples - chunk.shape[1]
                chunk = np.pad(chunk, ((0, 0), (0, pad)))
            prob = self.process(chunk, sr_eff)
            probs.append(prob)
        return np.array(probs, dtype=np.float32)


class VADStreamIterator:
    """Iterador de estado para streaming: consume chunks y emite eventos."""

    def __init__(self, vad: SileroVAD, threshold: float = 0.5,
                 min_silence_ms: int = 300, speech_pad_ms: int = 30,
                 sampling_rate: int = 16000):
        self.vad = vad
        self.threshold = threshold
        self.sr = sampling_rate
        self.min_silence_samples = int(sampling_rate * min_silence_ms / 1000)
        self.speech_pad_samples = int(sampling_rate * speech_pad_ms / 1000)
        self.num_samples = 512 if sampling_rate == 16000 else 256
        self.reset()

    def reset(self) -> None:
        self.vad.reset_states()
        self.triggered = False
        self.temp_end = 0
        self.current_sample = 0

    def process(self, chunk: np.ndarray) -> dict | None:
        """Procesa un chunk de audio.

        Returns:
            None: sin evento
            {'start': N}: inicio de voz detectado
            {'end': N}: fin de voz detectado
        """
        window_size = len(chunk) if chunk.ndim == 1 else chunk.shape[1]
        if window_size != self.num_samples * (self.sr // 16000):
            raise ValueError(
                f"Chunk size mismatch: {window_size} != {self.num_samples}")
        if chunk.ndim == 1:
            chunk = chunk.reshape(1, -1)

        self.current_sample += window_size
        prob = self.vad.process(chunk, self.sr)

        if prob >= self.threshold and self.temp_end:
            self.temp_end = 0

        if prob >= self.threshold and not self.triggered:
            self.triggered = True
            start = max(0, self.current_sample - self.speech_pad_samples
                        - window_size)
            return {"start": start}

        if prob < self.threshold - 0.15 and self.triggered:
            if not self.temp_end:
                self.temp_end = self.current_sample
            if self.current_sample - self.temp_end < self.min_silence_samples:
                return None
            else:
                end = self.temp_end + self.speech_pad_samples - window_size
                self.temp_end = 0
                self.triggered = False
                return {"end": end}

        return None


def is_speech(audio: np.ndarray, sr: int = 16000, threshold: float = 0.5) -> bool:
    """Detecta si hay voz en un array de audio (batch)."""
    vad = SileroVAD()
    probs = vad.process_full(audio, sr)
    if len(probs) == 0:
        return False
    return float(np.max(probs)) >= threshold
