from collections import deque
from typing import Any

SYSTEM_PROMPT = (
    "Eres un asistente de voz casero que habla español. "
    "Respondes siempre con una afirmacion breve y amable, "
    "nunca con preguntas. "
    "Intenta ayudar siempre, aunque no estes seguro. "
    "Solo texto plano, sin signos de interrogacion ni emojis."
)

DEFAULT_MODEL = "asistente_voz:latest"

DEFAULT_VOICE = "ef_dora"


class Cerebro:
    """Gestiona el historial de conversación con límite FIFO."""

    def __init__(self, max_interacciones: int = 8,
                 system_prompt: str | None = None,
                 model: str | None = None,
                 voice: str | None = None):
        self.max_interacciones = max_interacciones
        self.system_prompt = system_prompt or SYSTEM_PROMPT
        self.model = model or DEFAULT_MODEL
        self.voice = voice or DEFAULT_VOICE
        self._historial: list[dict[str, str]] = [
            {"role": "system", "content": self.system_prompt}
        ]

    @property
    def historial(self) -> list[dict[str, str]]:
        return list(self._historial)

    def agregar_usuario(self, texto: str) -> None:
        self._historial.append({"role": "user", "content": texto.strip()})
        self._recortar()

    def agregar_asistente(self, texto: str) -> None:
        self._historial.append({"role": "assistant", "content": texto.strip()})
        self._recortar()

    def _recortar(self) -> None:
        mensajes_sin_system = [m for m in self._historial
                               if m["role"] != "system"]
        max_mensajes = self.max_interacciones * 2
        if len(mensajes_sin_system) > max_mensajes:
            excedente = len(mensajes_sin_system) - max_mensajes
            system_msg = self._historial[0]
            preservados = self._historial[1 + excedente:]
            self._historial = [system_msg] + preservados

    def reiniciar(self) -> None:
        self._historial = [{"role": "system", "content": self.system_prompt}]

    def __len__(self) -> int:
        return len(self._historial)

    def __repr__(self) -> str:
        interacciones = (len(self._historial) - 1) // 2
        return (f"Cerebro(model={self.model!r}, voice={self.voice!r}, "
                f"interacciones={interacciones}/{self.max_interacciones})")

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "voice": self.voice,
            "max_interacciones": self.max_interacciones,
            "historial": self._historial,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Cerebro":
        instance = cls(
            max_interacciones=data["max_interacciones"],
            model=data["model"],
            voice=data["voice"],
        )
        instance._historial = data["historial"]
        return instance
