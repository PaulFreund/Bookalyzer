const { spawn } = require("node:child_process");
const { join } = require("node:path");
const { existsSync } = require("node:fs");
const { createInterface } = require("node:readline");

class PythonBridge {
  constructor(root, dataDir, runtime) {
    this.root = root;
    this.dataDir = dataDir;
    this.runtime = runtime;
    this.pending = new Map();
    this.sequence = 0;
  }
  start() {
    if (this.child) return;
    const local = join(
      this.root,
      ".venv",
      process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
    );
    const python =
      process.env.BOOKANALYZER_PYTHON ||
      (existsSync(local)
        ? local
        : process.platform === "win32"
          ? "python"
          : "python3");
    this.child = spawn(
      this.runtime || python,
      this.runtime ? [] : ["-u", "-m", "bookanalyzer.desktop"],
      {
        cwd: this.root,
        windowsHide: true,
        detached: process.platform !== "win32",
        stdio: ["pipe", "pipe", "pipe"],
        env: {
          ...process.env,
          PYTHONUTF8: "1",
          ...(process.platform === "darwin"
            ? {
                PATH: [
                  process.env.PATH,
                  "/opt/homebrew/bin",
                  "/usr/local/bin",
                  join(require("node:os").homedir(), ".local/bin"),
                ]
                  .filter(Boolean)
                  .join(":"),
              }
            : {}),
          ...(this.dataDir ? { BOOKANALYZER_DATA: this.dataDir } : {}),
        },
      },
    );
    this.lastError = "";
    this.child.stderr.on("data", (data) => {
      this.lastError = (this.lastError + data.toString()).slice(-3000);
    });
    createInterface({ input: this.child.stdout }).on("line", (line) => {
      let message;
      try {
        message = JSON.parse(line);
      } catch {
        return;
      }
      const request = this.pending.get(message.id);
      if (!request) return;
      this.pending.delete(message.id);
      clearTimeout(request.timer);
      message.error
        ? request.reject(new Error(message.error))
        : request.resolve(message.result);
    });
    const fail = (error) => {
      for (const request of this.pending.values()) {
        clearTimeout(request.timer);
        request.reject(error);
      }
      this.pending.clear();
      this.child = null;
    };
    this.child.on("error", (error) =>
      fail(new Error(`Python konnte nicht starten: ${error.message}`)),
    );
    this.child.on("exit", (code) =>
      fail(new Error(`Analyseprozess beendet (${code}). ${this.lastError}`)),
    );
  }
  call(method, params = {}) {
    if (
      ![
        "bootstrap",
        "settings",
        "codex_models",
        "prepare",
        "start",
        "storyscope_start",
        "local_update",
        "compare",
        "remove",
        "segment",
        "retry",
        "baseline_create",
        "baseline_remove",
        "baseline_compare",
        "chapters",
        "chapter_text",
        "quality",
        "quality_progression",
        "quality_excerpt",
        "quality_decision",
        "quality_findings",
        "library_export",
        "library_inspect",
        "library_import",
        "library_discard",
      ].includes(method)
    )
      return Promise.reject(new Error("Unbekannte Aktion."));
    this.start();
    return new Promise((resolve, reject) => {
      const id = ++this.sequence;
      const timer = setTimeout(
        () => {
          this.pending.delete(id);
          reject(
            new Error(
              "Die lokale Analyse antwortet nicht. Bitte erneut versuchen.",
            ),
          );
        },
        ["library_export", "library_inspect", "library_import"].includes(method)
          ? 900000
          : 180000,
      );
      this.pending.set(id, { resolve, reject, timer });
      this.child.stdin.write(JSON.stringify({ id, method, params }) + "\n");
    });
  }
  close() {
    if (!this.child) return;
    const pid = this.child.pid;
    if (process.platform === "win32" && pid)
      spawn("taskkill", ["/pid", String(pid), "/T", "/F"], {
        windowsHide: true,
        stdio: "ignore",
      });
    else if (pid) {
      try {
        process.kill(-pid, "SIGTERM");
      } catch {
        this.child.kill();
      }
    }
  }
}
module.exports = { PythonBridge };
