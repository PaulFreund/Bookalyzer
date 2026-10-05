"""Read model capabilities from a short-lived Codex app-server over local stdio."""
from __future__ import annotations

import json
import os
import queue
import signal
import subprocess
import tempfile
import threading
import time

from .codex_adapter import resolve_codex_executable

REASONING_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra")


def read_models(*, timeout=15):
    executable = resolve_codex_executable()
    with tempfile.TemporaryDirectory(prefix="Bookalyzer-models-") as directory:
        process = subprocess.Popen(
            [str(executable), "app-server"], cwd=directory,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            start_new_session=os.name != "nt",
        )
        incoming = queue.Queue()

        def read():
            try:
                for line in process.stdout:
                    try:
                        incoming.put(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            finally:
                incoming.put(None)

        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        deadline = time.monotonic() + timeout

        def send(payload):
            process.stdin.write(json.dumps(payload) + "\n")
            process.stdin.flush()

        def response(identifier):
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Codex-Modellliste antwortet nicht.")
                try:
                    message = incoming.get(timeout=remaining)
                except queue.Empty as error:
                    raise TimeoutError("Codex-Modellliste antwortet nicht.") from error
                if message is None:
                    raise RuntimeError("Codex App-Server wurde beendet.")
                if message.get("id") == identifier:
                    if "error" in message:
                        raise RuntimeError(message["error"].get("message", "Codex-Protokollfehler"))
                    return message["result"]
                # Model discovery never approves a server-initiated action.
                if "id" in message and "method" in message:
                    send({"id": message["id"], "error": {"code": -32601, "message": "Model discovery only"}})

        try:
            send({"method": "initialize", "id": 1, "params": {
                "clientInfo": {"name": "bookalyzer", "title": "Bookalyzer", "version": "0.5.3"}}})
            response(1)
            send({"method": "initialized", "params": {}})
            result, cursor, seen = [], None, set()
            for page in range(20):
                params = {"limit": 100, "includeHidden": False}
                if cursor:
                    params["cursor"] = cursor
                send({"method": "model/list", "id": page + 2, "params": params})
                payload = response(page + 2)
                for model in payload.get("data", []):
                    name = model.get("model") or model.get("id")
                    if not isinstance(name, str) or name in seen or model.get("hidden"):
                        continue
                    seen.add(name)
                    efforts = [entry["reasoningEffort"] for entry in model.get("supportedReasoningEfforts", [])
                               if entry.get("reasoningEffort") in REASONING_EFFORTS]
                    result.append({"id": name, "name": model.get("displayName") or name,
                                   "description": model.get("description", ""),
                                   "reasoningEfforts": efforts,
                                   "defaultReasoningEffort": model.get("defaultReasoningEffort"),
                                   "isDefault": bool(model.get("isDefault"))})
                cursor = payload.get("nextCursor")
                if not cursor:
                    return result
            raise RuntimeError("Codex-Modellliste ist zu groß.")
        finally:
            process.stdin.close()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                   capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=5)
                else:
                    os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=5)
            reader.join(timeout=1)
            process.stdout.close()
