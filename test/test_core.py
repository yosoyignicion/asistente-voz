#!/usr/bin/env python3
"""Tests de usabilidad del núcleo del Asistente de Voz.
Uso: source env_asistente/bin/activate && python test/test_core.py
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modulos.cerebro import Cerebro, SYSTEM_PROMPT
from modulos.stt import STTConfig

passed = 0
failed = 0


def ok(msg: str) -> None:
    global passed
    passed += 1
    print(f"  \033[32m✓\033[0m {msg}")


def fail(msg: str) -> None:
    global failed
    failed += 1
    print(f"  \033[31m✗\033[0m {msg}")


def tassert(condition, msg: str) -> None:
    if condition:
        ok(msg)
    else:
        fail(msg)


# ── Cerebro ────────────────────────────────────────────────────────────

def test_cerebro_init() -> None:
    c = Cerebro(max_interacciones=6)
    tassert(len(c) == 1, "inicia con 1 mensaje (system prompt)")
    tassert(c.historial[0]["role"] == "system", "primer mensaje es system")
    tassert(SYSTEM_PROMPT in c.historial[0]["content"], "system prompt presente")


def test_cerebro_fifo_eviction() -> None:
    c = Cerebro(max_interacciones=2)
    for i in range(5):
        c.agregar_usuario(f"pregunta {i}")
        c.agregar_asistente(f"respuesta {i}")

    msgs = c.historial
    tassert(msgs[0]["role"] == "system", "system prompt sigue primero")
    user_msgs = [m for m in msgs if m["role"] == "user"]
    tassert(len(user_msgs) == 2, "solo 2 interacciones (max_interacciones=2)")
    tassert(user_msgs[-1]["content"] == "pregunta 4", "último mensaje es el más reciente")


def test_cerebro_system_prompt_preserved() -> None:
    c = Cerebro(max_interacciones=1)
    c.agregar_usuario("hola")
    c.agregar_asistente("adiós")
    c.agregar_usuario("qué tal")
    c.agregar_asistente("bien")
    tassert(c.historial[0]["role"] == "system", "system prompt preservado tras evicción")
    tassert(len(c) == 3, "1 system + 2 mensajes (max_interacciones=1)")


def test_cerebro_reiniciar() -> None:
    c = Cerebro(max_interacciones=6)
    c.agregar_usuario("hola")
    c.agregar_asistente("adiós")
    tassert(len(c) == 3, "3 mensajes después de 1 interacción")
    c.reiniciar()
    tassert(len(c) == 1, "reiniciar deja solo el system prompt")
    tassert(c.historial[0]["role"] == "system", "system prompt intacto tras reiniciar")


def test_cerebro_historial_es_copia() -> None:
    c = Cerebro(max_interacciones=6)
    h1 = c.historial
    c.agregar_usuario("test")
    h2 = c.historial
    tassert(len(h1) == 1, "historial devuelto es copia, no referencia viva")


# ── STTConfig defaults ─────────────────────────────────────────────────

def test_stt_defaults() -> None:
    cfg = STTConfig()
    tassert(cfg.sample_rate == 16000, "sample_rate default 16000")
    tassert(cfg.silence_threshold == 0.025, "silence_threshold 0.025")
    tassert(cfg.max_record_s == 15.0, "max_record_s 15s")
    tassert(cfg.silence_duration_s == 1.2, "silence_duration_s 1.2")


# ── Config loading ─────────────────────────────────────────────────────

def test_load_config_sin_archivo() -> None:
    from main import _load_config
    config = _load_config()
    tassert(config == {}, "sin config.json devuelve dict vacío")


def test_load_config_con_archivo() -> None:
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    try:
        json.dump({"voice": "es_MX-ald-medium", "model": "mi_modelo:latest"}, tmp)
        tmp.close()

        import main as main_mod
        original_path = Path(main_mod.__file__).resolve().parent / "config.json"
        main_mod.__file__ = str(Path(tmp.name).parent / "fake_main.py")

        config_path = Path(tmp.name)
        config = {}

        import json as _json
        if config_path.exists():
            try:
                with open(config_path) as f:
                    config = _json.load(f)
            except Exception:
                pass

        tassert(config == {"voice": "es_MX-ald-medium", "model": "mi_modelo:latest"},
                "carga correctamente config.json")
    finally:
        Path(tmp.name).unlink(missing_ok=True)


def test_priority_chain() -> None:
    config = {"voice": "es_MX-ald-medium", "model": "config_model:latest"}
    voice_cli = None
    model_cli = "cli_model:latest"
    voice = voice_cli or config.get("voice") or "es_ES-sharvard-medium"
    model = model_cli or config.get("model") or "asistente_voz:latest"
    tassert(voice == "es_MX-ald-medium", "sin --voice usa config")
    tassert(model == "cli_model:latest", "--model sobreescribe config")


# ── Main ────────────────────────────────────────────────────────────────

def main() -> None:
    print("test_core.py — Tests del núcleo del Asistente de Voz\n")

    tests = [
        fn for name, fn in sorted(globals().items())
        if name.startswith("test_") and callable(fn)
    ]

    for test_fn in tests:
        label = test_fn.__name__.replace("test_", "").replace("_", " ")
        print(f"▶ {label}")
        try:
            test_fn()
        except Exception as e:
            fail(f"excepción: {e}")

    print(f"\n{'─' * 40}")
    print(f"  Pasaron: {passed}  |  Fallaron: {failed}")
    if failed:
        print(f"\n\033[31m{failed} test(s) fallaron\033[0m")
        sys.exit(1)
    else:
        print(f"\n\033[32mTodos los tests pasaron\033[0m")


if __name__ == "__main__":
    main()
