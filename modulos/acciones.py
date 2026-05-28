import logging
import shlex
import subprocess
import threading
from enum import Enum
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


class AccionTag(Enum):
    ABRIR_NAVEGADOR = "abrir_navegador"
    ABRIR_TERMINAL = "abrir_terminal"
    ABRIR_CODE = "abrir_code"
    APAGAR_PANTALLA = "apagar_pantalla"
    ABRIR_BUSQUEDA = "abrir_busqueda"


MARCAS = {
    AccionTag.ABRIR_NAVEGADOR: "[ACCION:ABRIR_NAVEGADOR]",
    AccionTag.ABRIR_TERMINAL: "[ACCION:ABRIR_TERMINAL]",
    AccionTag.ABRIR_CODE: "[ACCION:ABRIR_CODE]",
    AccionTag.APAGAR_PANTALLA: "[ACCION:APAGAR_PANTALLA]",
    AccionTag.ABRIR_BUSQUEDA: "[ACCION:ABRIR_BUSQUEDA]",
}

TAG_PREFIX = "[ACCION:"


class AccionContexto:
    __slots__ = ("tag", "argumento")

    def __init__(self, tag: AccionTag, argumento: str | None = None):
        self.tag = tag
        self.argumento = argumento


def extraer_accion(texto: str) -> AccionContexto | None:
    """Busca un tag de acción en el texto y devuelve su contexto."""
    inicio = texto.find(TAG_PREFIX)
    if inicio == -1:
        return None
    fin = texto.find("]", inicio)
    if fin == -1:
        return None
    tag_str = texto[inicio + len(TAG_PREFIX):fin].strip().upper()
    try:
        tag = AccionTag(tag_str.lower())
    except ValueError:
        logger.warning("Tag de acción desconocido: %s", tag_str)
        return None
    argumento = None
    resto = texto[fin + 1:].strip()
    if resto:
        argumento = resto.split("\n")[0].strip()
    return AccionContexto(tag, argumento)


def ejecutar_accion(contexto: AccionContexto) -> str:
    """Ejecuta la acción del sistema y devuelve mensaje de resultado."""
    tag = contexto.tag
    arg = contexto.argumento or ""

    if tag == AccionTag.ABRIR_NAVEGADOR:
        url = arg if arg.startswith("http") else f"https://www.google.com/search?q={arg}"
        subprocess.Popen(["xdg-open", url])
        return "Navegador abierto."

    if tag == AccionTag.ABRIR_TERMINAL:
        subprocess.Popen(["x-terminal-emulator"])
        return "Terminal abierta."

    if tag == AccionTag.ABRIR_CODE:
        subprocess.Popen(["code"])
        return "VS Code abierto."

    if tag == AccionTag.APAGAR_PANTALLA:
        subprocess.Popen(["xset", "dpms", "force", "off"])
        return "Pantalla apagada."

    if tag == AccionTag.ABRIR_BUSQUEDA:
        import urllib.parse
        url = f"https://www.google.com/search?q={urllib.parse.quote(arg)}"
        subprocess.Popen(["xdg-open", url])
        return f"Búsqueda abierta: {arg}"

    return f"Acción no implementada: {tag.value}"


def ejecutar_comando(comando: str, timeout: float = 30.0) -> tuple[int, str, str]:
    """Ejecuta un comando de shell y retorna (código, stdout, stderr)."""
    try:
        proceso = subprocess.run(
            comando, shell=True, capture_output=True, text=True,
            timeout=timeout,
        )
        return proceso.returncode, proceso.stdout.strip(), proceso.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"
    except Exception as e:
        return -1, "", str(e)
