"""Model discovery is capability-only, bounded and uses the local CLI protocol."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from bookanalyzer.codex_catalog import read_models


def fake_server(tmp_path, monkeypatch, *, stall=False):
    from bookanalyzer import codex_catalog
    log = tmp_path / "requests.jsonl"
    script = tmp_path / "server.py"
    script.write_text("""
import json,sys,time
log=sys.argv[1]
for line in sys.stdin:
 message=json.loads(line)
 with open(log,'a',encoding='utf-8') as handle: handle.write(line)
 method=message['method']
 if method=='initialize': result={'userAgent':'fixture'}
 elif method=='initialized': continue
 elif method=='model/list':
  if STALL: time.sleep(60)
  if message['params'].get('cursor'):
   result={'data':[{'id':'b','model':'model-b','displayName':'B','supportedReasoningEfforts':[{'reasoningEffort':'high'}],'defaultReasoningEffort':'high'},{'id':'a','model':'model-a'},{'id':'hidden','hidden':True}], 'nextCursor':None}
  else:
   result={'data':[{'id':'a','model':'model-a','displayName':'A','supportedReasoningEfforts':[{'reasoningEffort':'low'},{'reasoningEffort':'medium'}],'defaultReasoningEffort':'medium'}], 'nextCursor':'second'}
 else: raise RuntimeError('Unexpected action: '+method)
 print(json.dumps({'id':message['id'],'result':result}),flush=True)
""".replace("STALL", str(stall)), encoding="utf-8")
    real_popen = subprocess.Popen
    children = []

    def popen(args, **kwargs):
        if len(args) > 1 and args[1] == "app-server":
            child = real_popen([sys.executable, str(script), str(log)], **kwargs)
            children.append(child)
            return child
        return real_popen(args, **kwargs)

    monkeypatch.setattr(codex_catalog, "resolve_codex_executable", lambda: Path(sys.executable))
    monkeypatch.setattr(codex_catalog.subprocess, "Popen", popen)
    return log, children


def test_model_catalog_handshake_pagination_and_cleanup(tmp_path, monkeypatch):
    log, children = fake_server(tmp_path, monkeypatch)
    models = read_models(timeout=5)
    assert [model["id"] for model in models] == ["model-a", "model-b"]
    assert models[0]["reasoningEfforts"] == ["low", "medium"]
    assert models[0]["defaultReasoningEffort"] == "medium"
    requests = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [request["method"] for request in requests] == ["initialize", "initialized", "model/list", "model/list"]
    assert requests[-1]["params"]["cursor"] == "second"
    assert children[0].poll() is not None


def test_catalog_timeout_ends_only_owned_helper(tmp_path, monkeypatch):
    _log, children = fake_server(tmp_path, monkeypatch, stall=True)
    with pytest.raises(TimeoutError):
        read_models(timeout=0.4)
    assert children[0].poll() is not None


def test_legacy_windows_shim_prefers_present_desktop_runtime(tmp_path, monkeypatch):
    from bookanalyzer import codex_adapter
    shim = tmp_path / "codex.cmd"
    shim.write_text(".plugin-appserver\\codex.exe", encoding="utf-8")
    current = tmp_path / "OpenAI/Codex/bin/current/codex.exe"
    current.parent.mkdir(parents=True)
    current.write_bytes(b"fixture")
    monkeypatch.setattr(codex_adapter.sys, "platform", "win32")
    monkeypatch.setattr(codex_adapter.shutil, "which", lambda name: str(shim) if name == "codex" else name)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("BOOKANALYZER_CODEX", raising=False)
    assert codex_adapter.resolve_codex_executable() == current
    monkeypatch.setenv("BOOKANALYZER_CODEX", str(shim))
    assert codex_adapter.resolve_codex_executable() == shim
