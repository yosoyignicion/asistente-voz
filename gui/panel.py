"""Panel flotante del Asistente de Voz — customtkinter minimalista."""

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import customtkinter as ctk

PROJECT_DIR = Path(__file__).resolve().parent.parent
VOICES_JSON = PROJECT_DIR / "recursos" / "voces_disponibles.json"

with open(VOICES_JSON) as f:
    VOICE_CATALOG = json.load(f)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

BG         = "#0f1117"
SURFACE    = "#1a1d27"
BORDER     = "#2d3140"
TEXT       = "#c8ccd4"
TEXT_DIM   = "#6e7380"
ACCENT     = "#6c8cff"
ACCENT_HI  = "#5b7aeb"
DANGER     = "#c0392b"
DANGER_HI  = "#e74c3c"


@dataclass
class PanelCallbacks:
    on_toggle_record: Callable[[], None] = field(default=lambda: None)
    on_close_panel: Callable[[], None] = field(default=lambda: None)
    on_quit: Callable[[], None] = field(default=lambda: None)
    on_settings: Callable[[], None] = field(default=lambda: None)


class PanelFlotante:

    def __init__(self, model_name: str = "asistente_voz:latest"):
        self.model_name = model_name
        self.callbacks = PanelCallbacks()
        self._grabando = False
        self._root: ctk.CTk | None = None
        self._toggle_btn: ctk.CTkButton | None = None
        self._status_label: ctk.CTkLabel | None = None

    # ── public API ──────────────────────────────────────────────

    def mostrar(self) -> None:
        self._root = ctk.CTk()
        self._root.title("Asistente de Voz")
        self._root.geometry(self._calcular_geometria())
        self._root.configure(fg_color=BG)
        self._root.resizable(False, False)

        icono = PROJECT_DIR / "recursos" / "asistente-voz.png"
        if icono.exists():
            try:
                from PIL import Image, ImageTk
                img = Image.open(icono)
                tk_img = ImageTk.PhotoImage(img)
                self._root.iconphoto(True, tk_img)
            except Exception:
                pass

        self._root.protocol("WM_DELETE_WINDOW", self._on_minimize)
        self._construir_ui()
        self._root.mainloop()

    def cerrar(self) -> None:
        if self._root:
            self._root.quit()

    def ocultar(self) -> None:
        if self._root:
            self._root.withdraw()

    def mostrar_panel(self) -> None:
        if self._root:
            self._root.deiconify()
            self._root.lift()

    def actualizar_estado(self, estado: str) -> None:
        if self._status_label:
            self._status_label.configure(text=estado)

    def set_grabando(self, activo: bool) -> None:
        self._grabando = activo
        if not self._toggle_btn:
            return
        if activo:
            self._toggle_btn.configure(
                text="⏺  Grabando...",
                fg_color=DANGER, hover_color=DANGER_HI,
            )
        else:
            self._toggle_btn.configure(
                text="Ctrl + .",
                fg_color=ACCENT, hover_color=ACCENT_HI,
            )

    # ── geometry ────────────────────────────────────────────────

    def _calcular_geometria(self) -> str:
        pantalla_ancho = 1920
        try:
            pantalla_ancho = self._root.winfo_screenwidth()
        except Exception:
            pass
        ancho, alto = 260, 130
        x = pantalla_ancho - ancho - 30
        return f"{ancho}x{alto}+{x}+40"

    # ── build UI ────────────────────────────────────────────────

    def _construir_ui(self) -> None:
        outer = ctk.CTkFrame(
            self._root, fg_color=BG, corner_radius=8,
            border_width=1, border_color=BORDER,
        )
        outer.pack(fill="both", expand=True, padx=4, pady=4)

        header = ctk.CTkFrame(
            outer, fg_color="transparent", height=28,
            corner_radius=0,
        )
        header.pack(fill="x", padx=10, pady=(6, 0))

        ctk.CTkLabel(
            header, text="ASISTENTE",
            font=("Cantarell", 11, "bold"),
            text_color=TEXT,
        ).pack(side="left")

        for sym, cmd in [("⚙", self._on_settings), ("✕", self._on_minimize)]:
            ctk.CTkButton(
                header, text=sym, width=26, height=22,
                font=("Cantarell", 11),
                fg_color="transparent", text_color=TEXT_DIM,
                hover_color=SURFACE, corner_radius=4,
                command=cmd,
            ).pack(side="right", padx=1)

        ctk.CTkFrame(
            outer, height=1, fg_color=BORDER,
            corner_radius=0,
        ).pack(fill="x", padx=10, pady=(4, 0))

        body = ctk.CTkFrame(
            outer, fg_color="transparent", corner_radius=0,
        )
        body.pack(fill="both", expand=True, padx=12, pady=(8, 10))

        self._toggle_btn = ctk.CTkButton(
            body, text="Ctrl + .",
            font=("Cantarell", 13, "bold"),
            fg_color=ACCENT, text_color="#ffffff",
            hover_color=ACCENT_HI, corner_radius=8,
            height=40, command=self._on_toggle,
        )
        self._toggle_btn.pack(fill="x")

        self._status_label = ctk.CTkLabel(
            body, text="",
            font=("Cantarell", 9),
            text_color=TEXT_DIM,
        )
        self._status_label.pack(pady=(4, 0))
        self._iniciar_status_animado()

    # ── animations ──────────────────────────────────────────────

    def _iniciar_status_animado(self) -> None:
        dots = ["", ".", "..", "..."]
        idx = [0]

        def _animate():
            if not self._root or not self._status_label:
                return
            current = self._status_label.cget("text")
            triggers = ("Pensando", "Procesando", "Grabando", "Ejecutando")
            if any(current.startswith(t) for t in triggers):
                idx[0] = (idx[0] + 1) % len(dots)
                base = current.split(".")[0].rstrip(".")
                new_text = base + dots[idx[0]]
                self._status_label.configure(text=new_text)
            self._root.after(500, _animate)

        _animate()

    # ── handlers ───────────────────────────────────────────────

    def _on_toggle(self) -> None:
        self._ejecutar_en_hilo(self.callbacks.on_toggle_record)

    def _on_minimize(self) -> None:
        self.callbacks.on_close_panel()

    def _on_settings(self) -> None:
        self._ejecutar_en_hilo(self.callbacks.on_settings)

    @staticmethod
    def _ejecutar_en_hilo(func, *args) -> None:
        threading.Thread(target=func, args=args, daemon=True).start()
