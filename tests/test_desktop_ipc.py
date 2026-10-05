"""The packaged Python bootloader can ignore PYTHONUTF8; the wire format cannot."""
import base64
import json
import os
import subprocess
import sys
from bookanalyzer.desktop import DEFAULTS


def test_unicode_requests_and_quality_catalog_work_with_non_utf8_startup(tmp_path):
    name = "Grüße aus dem Wald 🌳.txt"
    requests = [
        {"id": 1, "method": "prepare", "params": {"name": name,
         "settings": DEFAULTS,
         "base64data": base64.b64encode(("Der Wind weht über das Feld. "*30).encode()).decode()}},
        {"id": 2, "method": "quality", "params": {"ids": []}},
    ]
    env = {**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0", "BOOKANALYZER_DATA": str(tmp_path)}
    process = subprocess.run([sys.executable, "-c",
        "import bookanalyzer.desktop as d; original=d.DesktopService; "
        "d.DesktopService=lambda **kwargs: original(seed=False); d.main()"],
        input=("\n".join(json.dumps(r, ensure_ascii=False) for r in requests)+"\n").encode("utf-8"),
        capture_output=True, env=env, timeout=30)
    assert process.returncode == 0, process.stderr.decode("utf-8")
    responses = [json.loads(line) for line in process.stdout.decode("utf-8").splitlines()]
    assert responses[0]["result"]["name"] == name
    assert any("≈" in metric["label"] for metric in responses[1]["result"]["catalog"]["metrics"])
