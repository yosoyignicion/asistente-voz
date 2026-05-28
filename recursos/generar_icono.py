#!/usr/bin/env python3
"""Genera un icono PNG de micrófono azul para el lanzador de escritorio."""

import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Error: Pillow no está instalado. Ejecuta: pip install Pillow")
    sys.exit(1)


def crear_icono_microfono(size: int = 256, output_path: str | None = None) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = size // 2, size // 2
    r_circle = size // 2 - 4
    draw.ellipse(
        [cx - r_circle, cy - r_circle, cx + r_circle, cy + r_circle],
        fill=(30, 100, 220), outline=(20, 80, 200), width=2,
    )

    mic_width = size // 5
    mic_height_head = size // 4
    mic_height_neck = size // 6
    stem_width = size // 12
    base_height = size // 10

    head_top = cy - r_circle // 2 - mic_height_head // 2
    head_left = cx - mic_width // 2
    draw.rounded_rectangle(
        [head_left, head_top, head_left + mic_width,
         head_top + mic_height_head],
        radius=mic_width // 2, fill=(255, 255, 255),
    )

    neck_top = head_top + mic_height_head
    neck_left = cx - stem_width // 2
    draw.rectangle(
        [neck_left, neck_top, neck_left + stem_width,
         neck_top + mic_height_neck],
        fill=(255, 255, 255),
    )

    base_top = neck_top + mic_height_neck
    base_left = cx - mic_width // 2 - 2
    draw.rounded_rectangle(
        [base_left, base_top, base_left + mic_width + 4,
         base_top + base_height],
        radius=2, fill=(255, 255, 255),
    )

    if output_path:
        img.save(output_path, "PNG")
        print(f"Icono guardado en: {output_path}")

    return img


if __name__ == "__main__":
    output = sys.argv[1] if len(sys.argv) > 1 else str(
        Path(__file__).resolve().parent / "asistente-voz.png"
    )
    crear_icono_microfono(256, output)
