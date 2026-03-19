"""Cliente WebSocket de prueba - escucha ws://localhost:8000/ws/pipelines por 60 segundos."""

import asyncio
import json
import sys
from datetime import datetime

# Forzar UTF-8 en Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def p(text: str) -> None:
    """print con flush inmediato."""
    print(text, flush=True)


def _fmt(msg: dict) -> str:
    """Formatea un mensaje WS para impresion legible."""
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    t = msg.get("type", "?")
    pid = msg.get("pipeline_id", "?")
    sid = msg.get("stage_id")

    if t == "pipeline_update":
        data = msg.get("data", {})
        current = data.get("current_stage") or {}
        summary = data.get("stages_summary", [])
        done = sum(1 for s in summary if s["status"] == "success")
        total = len(summary)
        stage_info = (
            f"{current.get('name', '?')} -> {current.get('status', '?')}"
            if current else "-"
        )
        return (
            f"[{ts}] PIPELINE_UPDATE   pid={pid}"
            f"  pipeline={data.get('status')}"
            f"  stage=({stage_info})"
            f"  progress={done}/{total}"
        )

    elif t == "pipeline_completed":
        data = msg.get("data", {})
        return (
            f"[{ts}] PIPELINE_COMPLETED pid={pid}"
            f"  status={data.get('status')}"
            f"  duration={data.get('duration_seconds')}s"
            f"  finished={data.get('finished_at')}"
        )

    elif t == "log_entry":
        data = msg.get("data", {})
        level = data.get("level", "info").upper()
        return (
            f"[{ts}] LOG               pid={pid}"
            f"  stage={sid}"
            f"  [{level}] {data.get('message')}"
        )

    else:
        return f"[{ts}] UNKNOWN  {json.dumps(msg)}"


async def listen(url: str = "ws://localhost:8000/ws/pipelines", timeout: int = 60) -> None:
    p(f"Conectando a {url} ...")
    p(f"Esperando mensajes por {timeout}s  (Ctrl+C para salir antes)")
    p("")

    count: dict[str, int] = {"total": 0, "pipeline_update": 0, "pipeline_completed": 0, "log_entry": 0}

    try:
        import websockets
        async with websockets.connect(url) as ws:
            p("[OK] Conexion establecida")
            p("-" * 60)
            try:
                async with asyncio.timeout(timeout):
                    async for raw in ws:
                        msg = json.loads(raw)
                        t = msg.get("type", "unknown")
                        count["total"] += 1
                        count[t] = count.get(t, 0) + 1
                        p(_fmt(msg))
            except TimeoutError:
                p(f"\n[--] Tiempo agotado ({timeout}s).")
    except ConnectionRefusedError:
        p("[ERR] No se pudo conectar. Esta corriendo el servidor en localhost:8000?")
        sys.exit(1)
    except KeyboardInterrupt:
        p("\n[^^] Interrumpido.")

    p("")
    p("=" * 60)
    p(f"  Total mensajes     : {count['total']}")
    p(f"  pipeline_update    : {count['pipeline_update']}")
    p(f"  pipeline_completed : {count['pipeline_completed']}")
    p(f"  log_entry          : {count['log_entry']}")
    p("=" * 60)


if __name__ == "__main__":
    asyncio.run(listen())
