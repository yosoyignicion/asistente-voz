#!/usr/bin/env python3
"""Instalador visual del Asistente de Voz — wizard interactivo con tkinter.

Uso:
    python instalar_gui.py                 # wizard completo
    python instalar_gui.py --no-gui        # instalación silenciosa (defaults)
    python instalar_gui.py --voice es_MX-ald-medium
"""

import argparse
import json
import subprocess
import sys
import textwrap
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
import os

PROJECT_DIR = Path(__file__).resolve().parent
VOICES_JSON = PROJECT_DIR / "recursos" / "voces_disponibles.json"
DESKTOP_SRC = PROJECT_DIR / "recursos" / "asistente-voz.desktop"
DEFAULT_VOICE = "ef_dora"
DEFAULT_MODEL = "asistente_voz"

with open(VOICES_JSON) as f:
    VOICE_CATALOG = json.load(f)

MODELFILE_TEMPLATE = textwrap.dedent("""\
FROM gemma2:2b

SYSTEM \"\"\"
Eres un asistente de voz casero que habla español. Respondes siempre con una afirmacion breve y amable, nunca con preguntas. Intenta ayudar siempre, aunque no estes seguro. Solo texto plano, sin signos de interrogacion ni emojis.
"""

PARAMETER temperature 0.7
PARAMETER num_ctx 1024
PARAMETER num_predict 80
PARAMETER repeat_penalty 1.1
""")


MODELFILE_EXPLICACION = textwrap.dedent("""\
El Modelfile es un archivo de configuración de Ollama que define:

  - El modelo base (ej: gemma2:2b)
  - La personalidad del asistente (system prompt)
  - Los parámetros de generación (temperatura, contexto, etc.)

Puedes usar la plantilla predeterminada, importar tu propio
archivo o editarla a tu gusto antes de crear el modelo.\
""")


@dataclass
class InstallState:
    model_name: str = DEFAULT_MODEL
    model_source: str = "default"         # "default" | "import" | "edit"
    modelfile_content: str = MODELFILE_TEMPLATE
    modelfile_path: str = ""              # path if imported
    selected_voice: str = DEFAULT_VOICE
    auto_start: bool = False
    errors: list[str] = field(default_factory=list)
    installed: bool = False


def _flat_voices() -> list[dict]:
    result: list[dict] = []
    for region, voces in VOICE_CATALOG.items():
        for v in voces.values():
            result.append({**v, "region": region})
    return result


def _check_ollama() -> str | None:
    try:
        subprocess.run(["ollama", "list"], capture_output=True, timeout=10)
        return None
    except FileNotFoundError:
        return "Ollama no está instalado. Instálalo desde: https://ollama.com/download/linux"
    except subprocess.TimeoutExpired:
        pass

    try:
        subprocess.Popen(
            ["ollama", "serve"], stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(3)
        subprocess.run(["ollama", "list"], capture_output=True, timeout=10)
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return (
            "Ollama no responde. Inícialo con 'ollama serve' en otra terminal "
            "y vuelve a ejecutar el instalador."
        )


def _create_model(name: str, content: str) -> bool:
    tmpfile = PROJECT_DIR / "Modelfile.tmp"
    tmpfile.write_text(content)
    try:
        result = subprocess.run(
            ["ollama", "create", f"{name}:latest", "-f", str(tmpfile)],
            capture_output=True, text=True, timeout=120,
        )
        return result.returncode == 0
    except Exception:
        return False
    finally:
        if tmpfile.exists():
            tmpfile.unlink()


def _download_voice(name: str) -> bool:
    try:
        from modulos.tts import SintetizadorVoz
        tts = SintetizadorVoz.obtener(name)
        tts._ensure_voice()
        return True
    except Exception:
        return False


def _create_desktop_entry() -> None:
    desktop_dst = Path.home() / ".local" / "share" / "applications" / "asistente-voz.desktop"
    desktop_dst.parent.mkdir(parents=True, exist_ok=True)
    content = DESKTOP_SRC.read_text().replace("##PROJECT_DIR##", str(PROJECT_DIR))
    desktop_dst.write_text(content)
    desktop_dst.chmod(0o755)


def _create_autostart() -> None:
    autostart_dir = Path.home() / ".config" / "autostart"
    autostart_dir.mkdir(parents=True, exist_ok=True)
    desktop_src = Path.home() / ".local" / "share" / "applications" / "asistente-voz.desktop"
    if desktop_src.exists():
        target = autostart_dir / "asistente-voz.desktop"
        if target.is_symlink():
            target.unlink()
        target.symlink_to(desktop_src)


def _generate_icon() -> None:
    output = PROJECT_DIR / "recursos" / "asistente-voz.png"
    subprocess.run(
        [sys.executable, str(PROJECT_DIR / "recursos" / "generar_icono.py"),
         str(output)],
        capture_output=True, timeout=10,
    )


def _save_config(voice: str, model: str, autostart: bool = False) -> None:
    config = {
        "voice": voice,
        "model": f"{model}:latest",
        "autostart": autostart,
    }
    config_path = PROJECT_DIR / "config.json"
    tmp = config_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(config, indent=2))
    os.replace(tmp, config_path)


# ── GUI ────────────────────────────────────────────────────────────────────────

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
    import customtkinter as ctk
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    TCL_AVAILABLE = True
except ImportError:
    TCL_AVAILABLE = False


class InstallerWizard:
    """Wizard de instalación paso a paso."""

    def __init__(self):
        if not TCL_AVAILABLE:
            print("Error: tkinter no disponible. Usa --no-gui para instalar sin interfaz.")
            sys.exit(1)

        self.state = InstallState()

        config_path = PROJECT_DIR / "config.json"
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text())
                self.state.auto_start = config.get("autostart", False)
            except Exception:
                pass

        self._step = 0
        self._content_frame: ctk.CTkFrame | None = None
        self._nav_frame: ctk.CTkFrame | None = None
        self._indicators: list[tk.Label] = []
        self._voice_listbox: tk.Listbox | None = None
        self._voice_map: dict[int, dict] = {}
        self._editing_text: tk.Text | None = None
        self._model_mode = None
        self._import_label = None
        self._logging_text: ctk.CTkTextbox | None = None
        self._progress: ctk.CTkProgressBar | None = None
        self._root: ctk.CTk | None = None
        self._probar_btn: ctk.CTkButton | None = None
        self._voz_status: ctk.CTkLabel | None = None
        self._playing_preview: bool = False
        self._stop_preview = threading.Event()
        self._preloading: set[str] = set()

        self.RED = "#e94560"

    # ── build ──────────────────────────────────────────────────────────────

    def run(self) -> None:
        self._root = ctk.CTk()
        self._model_mode = tk.StringVar(value=self.state.model_source)
        self._import_label = tk.StringVar(value=self.state.modelfile_path)
        self._root.title("Asistente de Voz — Instalador")
        self._root.geometry("580x640")
        self._root.resizable(True, True)
        self._root.configure(fg_color="#1a1a2e")
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        step_frame = ctk.CTkFrame(
            self._root, fg_color="#1a1a2e", corner_radius=0)
        step_frame.pack(fill=tk.X, padx=24, pady=(16, 0))
        self._indicators = []
        for i in range(5):
            label = tk.Label(
                step_frame, text="●" if i == 0 else "○",
                font=("Cantarell", 16), bg="#1a1a2e",
                fg="#0f3460" if i == 0 else "#555577",
            )
            label.pack(side=tk.LEFT, padx=2)
            self._indicators.append(label)
            if i < 4:
                tk.Label(
                    step_frame, text="─", font=("Cantarell", 10),
                    bg="#1a1a2e", fg="#555577",
                ).pack(side=tk.LEFT)

        self._content_frame = ctk.CTkFrame(
            self._root, fg_color="#1a1a2e", corner_radius=8,
            border_width=1, border_color="#16213e")
        self._content_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=12)

        self._nav_frame = ctk.CTkFrame(
            self._root, fg_color="#1a1a2e", corner_radius=0)
        self._nav_frame.pack(fill=tk.X, padx=24, pady=(0, 16))

        self._salir_btn = ctk.CTkButton(
            self._nav_frame, text="Cancelar", font=("Cantarell", 11),
            fg_color="#16213e", text_color="#e0e0e0",
            hover_color="#0f3460", corner_radius=6,
            command=self._on_close,
        )
        self._salir_btn.pack(side=tk.LEFT)

        self._next_btn = ctk.CTkButton(
            self._nav_frame, text="Siguiente →", font=("Cantarell", 11, "bold"),
            fg_color="#0f3460", text_color="#ffffff",
            hover_color="#16213e", corner_radius=6,
            command=self._next_step,
        )
        self._next_btn.pack(side=tk.RIGHT)

        self._prev_btn = ctk.CTkButton(
            self._nav_frame, text="← Anterior", font=("Cantarell", 11),
            fg_color="#16213e", text_color="#e0e0e0",
            hover_color="#0f3460", corner_radius=6,
            command=self._prev_step,
        )
        self._prev_btn.pack(side=tk.LEFT, padx=(0, 8))

        self._render_step()
        self._preload_voice(self.state.selected_voice)
        self._root.mainloop()

    def _on_close(self) -> None:
        if self._step == 3:
            return  # bloqueado durante instalación
        elif self._step == 4:
            self._root.destroy()
        elif messagebox.askokcancel("Cancelar", "¿Salir sin completar la instalación?"):
            self._root.destroy()

    # ── steps ─────────────────────────────────────────────────────────────

    def _render_step(self) -> None:
        for w in self._content_frame.winfo_children():
            w.destroy()

        for i, label in enumerate(self._indicators):
            if i <= self._step:
                label.config(fg="#0f3460", text="●")
            else:
                label.config(fg="#555577", text="○")

        if self._step == 0:
            self._prev_btn.pack_forget()
        else:
            self._prev_btn.pack(side=tk.RIGHT, padx=(0, 8))
            self._prev_btn.configure(state=tk.NORMAL)

        if self._step == 4:
            self._salir_btn.configure(text="Cerrar")
            self._next_btn.pack_forget()
        else:
            self._salir_btn.configure(text="Cancelar")
            if self._step == 3:
                self._next_btn.pack_forget()
            else:
                self._next_btn.pack(side=tk.RIGHT)
                self._next_btn.configure(state=tk.NORMAL)

        {
            0: self._step_welcome,
            1: self._step_model,
            2: self._step_voice,
            3: self._step_install,
            4: self._step_done,
        }[self._step]()

    def _next_step(self) -> None:
        if self._step >= 4:
            return
        if self._step == 0:
            error = _check_ollama()
            if error:
                messagebox.showerror("Ollama no disponible", error)
                return
        if self._step == 1:
            if self._model_mode.get() == "edit":
                if self._editing_text:
                    self.state.modelfile_content = self._editing_text.get("1.0", "end-1c")
            elif self._model_mode.get() == "import":
                if not self.state.modelfile_path:
                    messagebox.showwarning("Falta archivo", "Selecciona un archivo Modelfile.")
                    return
            content = self.state.modelfile_content.strip()
            if not content:
                messagebox.showwarning("Modelfile vacío", "El contenido del Modelfile no puede estar vacío.")
                return
        if self._step == 2:
            if not self.state.selected_voice:
                messagebox.showwarning("Sin voz", "Selecciona una voz TTS.")
                return
        self._step += 1
        self._render_step()

    def _prev_step(self) -> None:
        if self._step <= 0:
            return
        self._step -= 1
        self._render_step()

    # ── step 0: welcome ──────────────────────────────────────────────────

    def _step_welcome(self) -> None:
        F = "#e0e0e0"
        M = "#555577"
        D = "#8888bb"

        tk.Label(
            self._content_frame, text="🎤", font=("Cantarell", 40),
            bg="#1a1a2e", fg="#0f3460",
        ).pack(pady=(12, 0))

        tk.Label(
            self._content_frame,
            text="Asistente de Voz",
            font=("Cantarell", 22, "bold"),
            bg="#1a1a2e", fg=F,
        ).pack(pady=(4, 0))

        tk.Label(
            self._content_frame,
            text="Asistente de voz 100% local con IA",
            font=("Cantarell", 11),
            bg="#1a1a2e", fg=D,
        ).pack(pady=(0, 12))

        info = tk.Frame(self._content_frame, bg="#16213e", padx=16, pady=12)
        info.pack(fill=tk.X, pady=(8, 4))
        tk.Label(
            info,
            text=(
                "Este asistente funciona completamente en tu ordenador,\n"
                "sin conexión a internet. Usa:\n"
                "  • Ollama + modelo de IA local\n"
                "  • Reconocimiento de voz (faster-whisper)\n"
                "  • Síntesis de voz (Kokoro + Piper)"
            ),
            font=("Cantarell", 10), bg="#16213e", fg=F, justify=tk.LEFT,
        ).pack(anchor=tk.W)

        error = _check_ollama()
        status = tk.Frame(self._content_frame, bg="#1a1a2e")
        status.pack(fill=tk.X, pady=(12, 8))
        if error:
            tk.Label(
                status, text=f"⚠ {error}",
                font=("Cantarell", 10), bg="#1a1a2e", fg=self.RED,
                wraplength=500, justify=tk.LEFT,
            ).pack(anchor=tk.W)
            self._next_btn.configure(state=tk.DISABLED)
        else:
            tk.Label(
                status, text="✓ Ollama detectado y funcionando",
                font=("Cantarell", 10), bg="#1a1a2e", fg="#2ecc71",
            ).pack(anchor=tk.W)

        self._next_btn.configure(text="Siguiente →")

    # ── step 1: model ────────────────────────────────────────────────────

    def _step_model(self) -> None:
        F = "#e0e0e0"
        M = "#555577"
        D = "#8888bb"

        tk.Label(
            self._content_frame,
            text="Paso 1: Configuración del modelo de IA",
            font=("Cantarell", 13, "bold"),
            bg="#1a1a2e", fg=F,
        ).pack(anchor=tk.W, pady=(4, 4))

        explanation = tk.Frame(self._content_frame, bg="#16213e", padx=12, pady=8)
        explanation.pack(fill=tk.X, pady=(0, 8))
        tk.Label(
            explanation,
            text=MODELFILE_EXPLICACION,
            font=("Cantarell", 9), bg="#16213e", fg=D, justify=tk.LEFT,
        ).pack(anchor=tk.W)

        opts = tk.Frame(self._content_frame, bg="#1a1a2e")
        opts.pack(fill=tk.X)

        self._model_mode.set(self.state.model_source)
        for text, value, description in [
            ("Usar la plantilla predeterminada", "default", "La configuración probada y recomendada"),
            ("Importar mi propio Modelfile", "import", "Selecciona un archivo de tu equipo"),
            ("Editar la plantilla a mi gusto", "edit", "Modifica el prompt y parámetros"),
        ]:
            row = tk.Frame(opts, bg="#1a1a2e")
            row.pack(fill=tk.X, pady=2)
            tk.Radiobutton(
                row, text=text, variable=self._model_mode, value=value,
                font=("Cantarell", 10), bg="#1a1a2e", fg=F,
                selectcolor="#1a1a2e", activebackground="#1a1a2e",
                activeforeground=F, command=self._on_model_mode_change,
            ).pack(anchor=tk.W)
            tk.Label(
                row, text=description, font=("Cantarell", 8),
                bg="#1a1a2e", fg=M,
            ).pack(anchor=tk.W, padx=(24, 0))

        self._model_detail_frame = tk.Frame(self._content_frame, bg="#1a1a2e")
        self._model_detail_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self._on_model_mode_change()

        self._next_btn.configure(text="Siguiente →")

    def _on_model_mode_change(self) -> None:
        for w in self._model_detail_frame.winfo_children():
            w.destroy()

        mode = self._model_mode.get()
        self.state.model_source = mode

        if mode == "default":
            self._build_default_view()
        elif mode == "import":
            self._build_import_view()
        elif mode == "edit":
            self._build_edit_view()

    def _build_default_view(self) -> None:
        F = "#e0e0e0"
        A = "#16213e"

        preview = tk.Frame(self._model_detail_frame, bg=A, padx=8, pady=8)
        preview.pack(fill=tk.BOTH, expand=True)
        text = tk.Text(
            preview, font=("Cantarell", 8), bg=A, fg=F,
            relief=tk.FLAT, wrap=tk.WORD, height=7,
            state=tk.NORMAL,
        )
        text.insert("1.0", MODELFILE_TEMPLATE)
        text.config(state=tk.DISABLED)
        text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        scroll = tk.Scrollbar(preview, command=text.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        text.config(yscrollcommand=scroll.set)

        self.state.modelfile_content = MODELFILE_TEMPLATE
        self.state.modelfile_path = ""

    def _build_import_view(self) -> None:
        F = "#e0e0e0"
        A = "#16213e"

        row = tk.Frame(self._model_detail_frame, bg="#1a1a2e")
        row.pack(fill=tk.X, pady=(4, 8))

        tk.Button(
            row, text="Seleccionar archivo...",
            font=("Cantarell", 10), bg=A, fg=F, relief=tk.FLAT,
            activebackground="#0f3460", activeforeground=F,
            cursor="hand2", command=self._on_import_file,
        ).pack(side=tk.LEFT)

        tk.Label(
            row, textvariable=self._import_label,
            font=("Cantarell", 9), bg="#1a1a2e", fg="#8888bb",
        ).pack(side=tk.LEFT, padx=(8, 0))

        if self.state.modelfile_path:
            self._import_label.set(self.state.modelfile_path)
            preview = tk.Frame(self._model_detail_frame, bg=A, padx=8, pady=8)
            preview.pack(fill=tk.BOTH, expand=True)
            text = tk.Text(
                preview, font=("Cantarell", 8), bg=A, fg=F,
                relief=tk.FLAT, wrap=tk.WORD, height=7,
                state=tk.NORMAL,
            )
            text.insert("1.0", self.state.modelfile_content)
            text.config(state=tk.DISABLED)
            text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
            scroll = tk.Scrollbar(preview, command=text.yview)
            scroll.pack(side=tk.RIGHT, fill=tk.Y)
            text.config(yscrollcommand=scroll.set)

    def _on_import_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Selecciona un Modelfile",
            filetypes=[("Modelfile", "Modelfile*"), ("Todos", "*")],
        )
        if path:
            content = Path(path).read_text()
            self.state.modelfile_path = path
            self.state.modelfile_content = content
            self._on_model_mode_change()

    def _build_edit_view(self) -> None:
        F = "#e0e0e0"
        A = "#16213e"

        editor = tk.Frame(self._model_detail_frame, bg=A, padx=4, pady=4)
        editor.pack(fill=tk.BOTH, expand=True)
        self._editing_text = tk.Text(
            editor, font=("Cantarell", 9), bg=A,
            fg=F, insertbackground=F, relief=tk.FLAT,
            wrap=tk.WORD, height=7,
        )
        self._editing_text.insert(
            "1.0", self.state.modelfile_content or MODELFILE_TEMPLATE,
        )
        self._editing_text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        scroll = tk.Scrollbar(editor, command=self._editing_text.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._editing_text.config(yscrollcommand=scroll.set)

    # ── step 2: voice ────────────────────────────────────────────────────

    def _step_voice(self) -> None:
        F = "#e0e0e0"
        A = "#16213e"
        D = "#8888bb"

        tk.Label(
            self._content_frame,
            text="Paso 2: Selección de voz",
            font=("Cantarell", 13, "bold"),
            bg="#1a1a2e", fg=F,
        ).pack(anchor=tk.W, pady=(4, 4))

        tk.Label(
            self._content_frame,
            text="Elige la voz que usará el asistente para hablarte:",
            font=("Cantarell", 10),
            bg="#1a1a2e", fg=D,
        ).pack(anchor=tk.W, pady=(0, 6))

        list_frame = tk.Frame(self._content_frame, bg=A)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self._voice_listbox = tk.Listbox(
            list_frame, font=("Cantarell", 10), bg=A,
            fg=F, selectbackground="#0f3460", selectforeground=F,
            relief=tk.FLAT, activestyle=tk.NONE,
            highlightthickness=0, exportselection=False,
        )
        self._voice_listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        scroll = tk.Scrollbar(list_frame, command=self._voice_listbox.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._voice_listbox.config(yscrollcommand=scroll.set)

        self._voice_map = {}
        idx = 0
        voices = _flat_voices()
        default_idx = 0
        for v in voices:
            label = f"[{v['gender'][0].upper()}] {v['name']}  —  {v['description']}"
            self._voice_listbox.insert(tk.END, label)
            self._voice_map[idx] = v
            if v["name"] == self.state.selected_voice:
                default_idx = idx
            idx += 1

        self._voice_listbox.select_set(default_idx)
        self._voice_listbox.activate(default_idx)
        self._voice_listbox.bind("<<ListboxSelect>>", self._on_voice_select)

        btn_row = tk.Frame(self._content_frame, bg="#1a1a2e")
        btn_row.pack(fill=tk.X, pady=(8, 0))

        self._probar_btn = tk.Button(
            btn_row, text="▶ Probar voz seleccionada",
            font=("Cantarell", 10), bg="#16213e", fg=F, relief=tk.FLAT,
            activebackground="#0f3460", activeforeground=F,
            cursor="hand2", command=self._on_probar_voz,
        )
        self._probar_btn.pack(side=tk.LEFT)

        self._voz_status = tk.Label(
            btn_row, text="", font=("Cantarell", 9),
            bg="#1a1a2e", fg="#8888bb",
        )
        self._voz_status.pack(side=tk.LEFT, padx=(12, 0))

        self._auto_var = tk.BooleanVar(value=self.state.auto_start)
        tk.Checkbutton(
            self._content_frame, text="Iniciar automáticamente al arrancar el sistema",
            variable=self._auto_var, font=("Cantarell", 9),
            bg="#1a1a2e", fg=F, selectcolor="#1a1a2e",
            activebackground="#1a1a2e", activeforeground=F,
            command=lambda: setattr(self.state, "auto_start", self._auto_var.get()),
        ).pack(anchor=tk.W, pady=(8, 0))

        self._next_btn.configure(text="Siguiente →")

    def _on_voice_select(self, _event) -> None:
        sel = self._voice_listbox.curselection()
        if sel:
            voice = self._voice_map[sel[0]]
            self.state.selected_voice = voice["name"]
            self._preload_voice(voice["name"])

    def _preload_voice(self, name: str) -> None:
        if name in self._preloading:
            return
        self._preloading.add(name)
        threading.Thread(target=self._preload_worker, args=(name,), daemon=True).start()

    def _preload_worker(self, name: str) -> None:
        try:
            from modulos.tts import SintetizadorVoz
            tts = SintetizadorVoz.obtener(name)
            tts._ensure_voice()
        except Exception:
            pass
        finally:
            self._preloading.discard(name)

    def _on_probar_voz(self) -> None:
        if self._playing_preview:
            self._stop_preview.set()
            self._probar_btn.config(text="Probar voz seleccionada")
            self._voz_status.config(text="Reproduccion detenida")
            return

        sel = self._voice_listbox.curselection()
        if not sel:
            try:
                active = self._voice_listbox.index("active")
                if active is not None:
                    sel = (active,)
            except Exception:
                sel = ()
        if not sel:
            self._voz_status.config(text="Selecciona una voz de la lista primero")
            return
        voice = self._voice_map[sel[0]]
        name = voice["name"]
        self._stop_preview.clear()
        print(f"[INSTALLER] Probando voz: {name}")
        self._probar_btn.config(state=tk.DISABLED, text="Cargando...")
        self._voz_status.config(text=f"Preparando {name} ...")
        threading.Thread(target=self._play_voice_preview, args=(name,), daemon=True).start()

    def _play_voice_preview(self, name: str) -> None:
        import sounddevice as sd
        import numpy as np
        try:
            print(f"[INSTALLER] _play_voice_preview iniciando para: {name}")
            from modulos.tts import SintetizadorVoz
            tts = SintetizadorVoz.obtener(name)
            print(f"[INSTALLER] Cargando motor TTS: {name}")
            self._root.after(0, lambda: self._voz_status.config(text="Cargando motor TTS..."))
            tts._ensure_voice()
            print(f"[INSTALLER] Sintetizando audio: {name}")
            self._root.after(0, lambda: self._voz_status.config(text="Sintetizando audio..."))
            audio = tts.sintetizar("Hola, soy tu asistente de voz. Estoy aqui para ayudarte con lo que necesites.")
            if audio.size == 0:
                self._root.after(0, lambda: self._voz_status.config(text="Error: audio vacio"))
                return

            print(f"[INSTALLER] Reproduciendo prueba: {name}")
            self._root.after(0, lambda: self._voz_status.config(text="Reproduciendo prueba..."))
            self._root.after(0, lambda: self._probar_btn.config(
                state=tk.NORMAL, text="Detener reproduccion",
            ))
            self._playing_preview = True

            sr = tts.sample_rate
            sd.play(audio, sr)
            duracion = len(audio) / sr
            elapsed = 0.0
            while elapsed < duracion:
                if self._stop_preview.is_set():
                    sd.stop()
                    print(f"[INSTALLER] Reproduccion detenida por usuario: {name}")
                    return
                time.sleep(0.1)
                elapsed += 0.1

            print(f"[INSTALLER] Prueba completada: {name}")
            self._root.after(0, lambda: self._voz_status.config(text="Prueba completada"))
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[INSTALLER] ERROR en _play_voice_preview: {e}")
            error_msg = str(e)
            self._root.after(0, lambda msg=error_msg: self._voz_status.config(text=f"Error: {msg}"))
        finally:
            self._playing_preview = False
            self._root.after(0, lambda: self._probar_btn.config(
                state=tk.NORMAL, text="Probar voz seleccionada",
            ))

    # ── step 3: install ──────────────────────────────────────────────────

    def _step_install(self) -> None:
        F = "#e0e0e0"
        A = "#16213e"
        D = "#8888bb"

        tk.Label(
            self._content_frame,
            text="Paso 3: Instalando...",
            font=("Cantarell", 13, "bold"),
            bg="#1a1a2e", fg=F,
        ).pack(anchor=tk.W, pady=(4, 4))

        self._progress = ctk.CTkProgressBar(
            self._content_frame, mode="indeterminate", width=400,
            fg_color="#16213e", progress_color="#0f3460",
            corner_radius=4, height=8,
        )
        self._progress.pack(fill=tk.X, pady=(0, 8))
        self._progress.start()

        log_frame = ctk.CTkFrame(
            self._content_frame, fg_color=A, corner_radius=6)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self._logging_text = ctk.CTkTextbox(
            log_frame, font=("Cantarell", 9), fg_color=A,
            text_color=D, corner_radius=4,
            wrap=tk.WORD, height=10,
        )
        self._logging_text.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self._prev_btn.configure(state="disabled")
        self._salir_btn.configure(state="disabled")

        threading.Thread(target=self._run_install, daemon=True).start()

    def _log(self, msg: str, ok: bool = True) -> None:
        prefix = "  ✓" if ok else "  ✗"
        self._root.after(0, lambda: self._logging_text.insert(
            tk.END, f"{prefix} {msg}\n",
        ))
        self._root.after(0, lambda: self._logging_text.see(tk.END))

    def _run_install(self) -> None:
        self._log("Generando icono...")
        try:
            _generate_icon()
            self._log("Icono generado", True)
        except Exception as e:
            self._log(f"Icono: {e}", False)

        self._log(f"Creando modelo Ollama: {self.state.model_name}:latest ...")
        ok_model = _create_model(self.state.model_name, self.state.modelfile_content)
        self._log(f"Modelo {self.state.model_name}:latest creado", ok_model)
        if not ok_model:
            self.state.errors.append("No se pudo crear el modelo Ollama")

        self._log(f"Descargando voz: {self.state.selected_voice} ...")
        ok_voice = _download_voice(self.state.selected_voice)
        self._log(f"Voz {self.state.selected_voice} instalada", ok_voice)
        if not ok_voice:
            self.state.errors.append("No se pudo descargar la voz TTS")

        self._log("Creando acceso directo en el menú...")
        try:
            _create_desktop_entry()
            self._log("Acceso directo creado", True)
        except Exception as e:
            self._log(f"Acceso directo: {e}", False)

        if self.state.auto_start:
            self._log("Configurando auto-inicio...")
            try:
                _create_autostart()
                self._log("Auto-inicio configurado", True)
            except Exception as e:
                self._log(f"Auto-inicio: {e}", False)

        self._log("Guardando configuracion...")
        _save_config(self.state.selected_voice, self.state.model_name, self.state.auto_start)
        self._log("Configuracion guardada", True)

        self._root.after(0, self._install_finished)

    def _install_finished(self) -> None:
        self._progress.stop()
        self.state.installed = True

        if self.state.errors:
            self._logging_text.insert(
                tk.END,
                "\n⚠ Instalación completada con advertencias.\n",
            )
        else:
            self._logging_text.insert(
                tk.END,
                "\n✓ ¡Instalación completada con éxito!\n",
            )
        self._logging_text.see(tk.END)

        self._step = 4
        self._render_step()

    # ── step 4: done ─────────────────────────────────────────────────────

    def _step_done(self) -> None:
        F = "#e0e0e0"
        A = "#16213e"
        D = "#8888bb"

        tk.Label(
            self._content_frame, text="🎉", font=("Cantarell", 40),
            bg="#1a1a2e", fg="#2ecc71",
        ).pack(pady=(24, 0))

        tk.Label(
            self._content_frame,
            text="¡Instalación completada!",
            font=("Cantarell", 18, "bold"),
            bg="#1a1a2e", fg=F,
        ).pack(pady=(4, 8))

        cajas = tk.Frame(self._content_frame, bg="#1a1a2e")
        cajas.pack(fill=tk.X, padx=12, pady=(4, 12))

        for titulo, comando in [
            ("Desde terminal", "bash bin/asistente-voz"),
            ("Directo con Python", "source env_asistente/bin/activate\npython main.py"),
        ]:
            box = tk.Frame(cajas, bg=A, padx=12, pady=8)
            box.pack(fill=tk.X, pady=4)
            tk.Label(
                box, text=titulo, font=("Cantarell", 9, "bold"),
                bg=A, fg=D,
            ).pack(anchor=tk.W)
            tk.Label(
                box, text=comando, font=("Cantarell", 10),
                bg=A, fg=F,
            ).pack(anchor=tk.W, pady=(2, 0))

        tk.Label(
            self._content_frame,
            text="También puedes encontrarlo en el menú de aplicaciones como 'Asistente de Voz'",
            font=("Cantarell", 9), bg="#1a1a2e", fg="#555577",
        ).pack()

        btn_row = tk.Frame(self._content_frame, bg="#1a1a2e")
        btn_row.pack(fill=tk.X, pady=(16, 0))

        tk.Button(
            btn_row, text="Cerrar",
            font=("Cantarell", 11, "bold"), bg=A, fg=F, relief=tk.FLAT,
            activebackground="#0f3460", activeforeground=F,
            cursor="hand2", command=self._root.destroy, padx=20, pady=6,
        ).pack(side=tk.RIGHT)

        tk.Button(
            btn_row, text="Abrir README",
            font=("Cantarell", 10), bg="#0f3460", fg=F, relief=tk.FLAT,
            activebackground=A, activeforeground=F,
            cursor="hand2", command=self._open_readme, padx=16, pady=6,
        ).pack(side=tk.RIGHT, padx=(0, 8))

    @staticmethod
    def _open_readme() -> None:
        readme = PROJECT_DIR / "README.md"
        if readme.exists():
            subprocess.Popen(["xdg-open", str(readme)])


# ── no-gui ─────────────────────────────────────────────────────────────────────

def install_headless(voice: str, model: str) -> bool:
    """Instalación sin interfaz gráfica."""
    print("Instalando Asistente de Voz (modo silencioso)...")
    print()

    print("[1/4] Generando icono...")
    try:
        _generate_icon()
        print("  ✓ Icono generado")
    except Exception as e:
        print(f"  ✗ {e}")

    print(f"\n[2/4] Creando modelo {model}:latest ...")
    ok = _create_model(model, MODELFILE_TEMPLATE)
    print(f"  {'✓' if ok else '✗'} Modelo {model}:latest")

    print(f"\n[3/4] Descargando voz {voice} ...")
    ok_v = _download_voice(voice)
    print(f"  {'✓' if ok_v else '✗'} Voz {voice}")

    print("\n[4/4] Creando acceso directo...")
    try:
        _create_desktop_entry()
        print("  ✓ Acceso directo creado")
    except Exception as e:
        print(f"  ✗ {e}")

    _save_config(voice, model)

    print()
    print("Instalación completada. Ejecuta:")
    print(f"  bash {PROJECT_DIR}/bin/asistente-voz")
    return True


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Instalador del Asistente de Voz")
    parser.add_argument("--no-gui", action="store_true",
                        help="Instalación silenciosa sin interfaz gráfica")
    parser.add_argument("--voice", default=DEFAULT_VOICE,
                        help=f"Voz TTS (default: {DEFAULT_VOICE})")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Nombre del modelo Ollama (default: {DEFAULT_MODEL})")
    args = parser.parse_args()

    if args.no_gui:
        error = _check_ollama()
        if error:
            print(f"Error: {error}")
            sys.exit(1)
        install_headless(args.voice, args.model)
    else:
        wizard = InstallerWizard()
        wizard.run()


if __name__ == "__main__":
    main()
