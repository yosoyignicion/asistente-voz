#!/usr/bin/env python3
"""Reproduce una frase de prueba con cada voz TTS española disponible.

Uso:
    python recursos/probar_voces.py                     # lista las voces
    python recursos/probar_voces.py es_ES-sharvard-medium  # prueba una voz concreta
    python recursos/probar_voces.py --todas             # prueba todas secuencialmente
    python recursos/probar_voces.py --descargar-todas   # solo descarga, no reproduce
"""

import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from modulos.tts import SintetizadorVoz, VOICE_CACHE_DIR

FRASE_PRUEBA = (
    "Hola, soy tu asistente de voz. "
    "Estoy aquí para ayudarte con lo que necesites."
)

VOICES_JSON = PROJECT_DIR / "recursos" / "voces_disponibles.json"


def cargar_voces() -> dict[str, dict]:
    with open(VOICES_JSON) as f:
        return json.load(f)


def listar_voces(catalogo: dict[str, dict]) -> list[str]:
    nombres: list[str] = []
    for region, voces in catalogo.items():
        for v in voces.values():
            nombres.append(v["name"])
    return nombres


def probar_voz(voice_name: str, reproducir: bool = True) -> SintetizadorVoz:
    tts = SintetizadorVoz.obtener(voice_name)
    tts._ensure_voice()
    if reproducir:
        print(f"\n  [{voice_name}] — {FRASE_PRUEBA}")
        tts.reproducir(FRASE_PRUEBA)
    else:
        print(f"  [{voice_name}] descargada")
    return tts


def main() -> None:
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--todas":
            catalogo = cargar_voces()
            for voz in listar_voces(catalogo):
                probar_voz(voz, reproducir=True)
        elif arg == "--descargar-todas":
            catalogo = cargar_voces()
            for voz in listar_voces(catalogo):
                probar_voz(voz, reproducir=False)
            print(f"\nTodas las voces descargadas en: {VOICE_CACHE_DIR}")
        elif arg == "--listar":
            catalogo = cargar_voces()
            print("Voces españolas disponibles para Piper TTS:\n")
            for region, voces in catalogo.items():
                print(f"  {region}:")
                for v in voces.values():
                    default = " (predeterminada)" if v["name"] == "es_ES-sharvard-medium" else ""
                    print(f"    {v['name']:<35} {v['gender']:<10} {v['description']}{default}")
        else:
            probar_voz(arg)
    else:
        print("Uso: python recursos/probar_voces.py [--todas | --listar | --descargar-todas | nombre_voz]")
        print("Ejemplo: python recursos/probar_voces.py es_ES-sharvard-medium")


if __name__ == "__main__":
    main()
