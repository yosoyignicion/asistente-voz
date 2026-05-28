import threading
import time
from dataclasses import dataclass

import numpy as np
import sounddevice as sd

from modulos.vad import SileroVAD


@dataclass
class STTConfig:
    sample_rate: int = 16000
    block_duration_ms: int = 200
    silence_threshold: float = 0.025
    silence_duration_s: float = 1.2
    max_record_s: float = 15.0
    device_index: int | None = None


class SpeechToText:
    """Captura de audio con Silero VAD + faster-whisper."""

    def __init__(self, config: STTConfig | None = None):
        self.config = config or STTConfig()
        self._model = None
        self._model_lock = threading.Lock()
        self._vad: SileroVAD | None = None
        self._vad_lock = threading.Lock()
        self._cancel = threading.Event()

    def _load_model(self):
        if self._model is not None:
            return
        with self._model_lock:
            if self._model is None:
                from faster_whisper import WhisperModel
                self._model = WhisperModel(
                    "base", device="cpu", compute_type="int8"
                )

    def _load_vad(self) -> SileroVAD:
        with self._vad_lock:
            if self._vad is None:
                self._vad = SileroVAD()
        return self._vad

    def preload(self) -> None:
        threading.Thread(target=self._load_model, daemon=True).start()
        threading.Thread(target=self._load_vad, daemon=True).start()

    def _record_audio(self, max_seconds: float = 30.0) -> np.ndarray:
        sr = self.config.sample_rate
        block_size = int(sr * self.config.block_duration_ms / 1000)
        blocks: list[np.ndarray] = []
        silence_blocks = 0
        silence_needed = int(
            self.config.silence_duration_s
            / (self.config.block_duration_ms / 1000)
        )
        max_blocks = int(max_seconds / (self.config.block_duration_ms / 1000))

        def callback(indata, _frames, _time_info, status):
            if status:
                return
            blocks.append(indata.copy()[:, 0] if indata.ndim > 1
                          else indata.copy())

        self._cancel.clear()
        with sd.InputStream(
            samplerate=sr, channels=1, dtype=np.float32,
            blocksize=block_size, callback=callback,
            device=self.config.device_index,
        ):
            while not self._cancel.is_set():
                time.sleep(0.05)
                current = len(blocks)
                if current > 0:
                    last_block = blocks[-1]
                    rms = float(np.sqrt(np.mean(last_block ** 2)))
                    if rms < self.config.silence_threshold:
                        silence_blocks += 1
                    else:
                        silence_blocks = 0
                if current >= max_blocks:
                    break
                if current > silence_needed and silence_blocks >= silence_needed:
                    break

        if not blocks:
            return np.array([], dtype=np.float32)
        return np.concatenate(blocks)

    def _vad_trim(self, audio: np.ndarray) -> np.ndarray:
        if audio.size < self.config.sample_rate * 0.2:
            return audio
        try:
            vad = self._load_vad()
            probs = vad.process_full(audio, self.config.sample_rate)
        except Exception:
            return audio

        if len(probs) == 0:
            return audio

        chunk_samples = 512 if self.config.sample_rate == 16000 else 256
        threshold = 0.35

        speech_chunks = [i for i, p in enumerate(probs) if p >= threshold]
        if not speech_chunks:
            return audio

        first_speech = speech_chunks[0]
        last_speech = speech_chunks[-1]

        pad_chunks = max(1, int(0.1 * self.config.sample_rate / chunk_samples))
        start_chunk = max(0, first_speech - pad_chunks)
        end_chunk = min(len(probs), last_speech + pad_chunks + 1)

        start_sample = start_chunk * chunk_samples
        end_sample = min(audio.size, end_chunk * chunk_samples)

        if end_sample - start_sample < self.config.sample_rate * 0.2:
            return audio

        return audio[start_sample:end_sample]

    def _transcribe(self, audio: np.ndarray) -> str:
        self._load_model()
        segments, _ = self._model.transcribe(
            audio, beam_size=2, language="es",
            vad_filter=False, without_timestamps=True,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()

    def capture_command(self) -> str:
        self._cancel.clear()
        audio = self._record_audio(max_seconds=self.config.max_record_s)
        if audio.size < self.config.sample_rate * 0.3:
            return ""
        audio = self._vad_trim(audio)
        if audio.size < self.config.sample_rate * 0.2:
            return ""
        return self._transcribe(audio)

    def transcribe_audio(self, audio: np.ndarray) -> str:
        audio = self._vad_trim(audio)
        if audio.size < self.config.sample_rate * 0.2:
            return ""
        return self._transcribe(audio)

    def transcribe_file(self, path: str) -> str:
        self._load_model()
        segments, _ = self._model.transcribe(
            path, beam_size=5, language="es",
            vad_filter=False, without_timestamps=True,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()
