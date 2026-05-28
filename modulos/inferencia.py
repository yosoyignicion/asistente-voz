from collections.abc import Iterator

import ollama


class MotorInferencia:
    """Cliente Ollama con streaming de respuestas."""

    def __init__(self, model: str = "asistente_voz:latest", host: str | None = None):
        self.model = model
        self._client = ollama.Client(host=host) if host else ollama

    def generar(self, messages: list[dict[str, str]]) -> str:
        """Genera una respuesta completa (no streaming)."""
        response = self._client.chat(
            model=self.model,
            messages=messages,
        )
        return response["message"]["content"].strip()

    def generar_stream(self,
                       messages: list[dict[str, str]]) -> Iterator[str]:
        """Genera tokens según se producen. Cede fragmentos de texto."""
        stream = self._client.chat(
            model=self.model,
            messages=messages,
            stream=True,
        )
        for chunk in stream:
            content = chunk.get("message", {}).get("content", "")
            if content:
                yield content

    def generar_desde_stream(self,
                             messages: list[dict[str, str]]) -> str:
        """Genera streaming y devuelve el texto completo concatenado."""
        partes: list[str] = []
        for fragmento in self.generar_stream(messages):
            partes.append(fragmento)
        return "".join(partes).strip()
