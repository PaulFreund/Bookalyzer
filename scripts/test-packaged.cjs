// Test the actual app from empty working directories, with and without sample books.
const { spawn } = require("node:child_process");
const { mkdtempSync, existsSync } = require("node:fs");
const { join, resolve, dirname } = require("node:path");
const { tmpdir } = require("node:os");
const assert = require("node:assert/strict");
const { PythonBridge } = require("../desktop/bridge.cjs");
const macDir = process.arch === "arm64" ? "mac-arm64" : "mac";
const executable = resolve(
  process.argv[2] ||
    (process.platform === "darwin"
      ? "release/" + macDir + "/Bookalyzer.app/Contents/MacOS/Bookalyzer"
      : "release/win-unpacked/Bookalyzer.exe"),
);
assert.ok(existsSync(executable), "Packaged executable must exist");
const temporary = mkdtempSync(join(tmpdir(), "Bookalyzer-app-"));
const library = join(temporary, "library");
const env = { ...process.env, BOOKANALYZER_DATA: library };
delete env.BOOKANALYZER_ROOT;
delete env.BOOKANALYZER_PYTHON;

function startApp() {
  return new Promise((resolve, reject) => {
    const child = spawn(executable, ["--smoke-test"], {
      cwd: temporary,
      env,
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
    });
    let output = "",
      errors = "";
    child.stdout.on("data", (d) => (output += d));
    child.stderr.on("data", (d) => (errors += d));
    const timer = setTimeout(() => {
      child.kill();
      reject(new Error("Packaged smoke test timed out."));
    }, 90000);
    child.on("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.on("exit", (code) => {
      clearTimeout(timer);
      try {
        assert.equal(code, 0, errors);
        const report = output
          .split(/\r?\n/)
          .filter((l) => l.startsWith("{"))
          .map((l) => JSON.parse(l))
          .find((r) => r.ok);
        assert.ok(report?.ui.isolated);
        assert.ok(
          report.ui.title.startsWith("Bookalyzer"),
          "The installed app must use the new product name",
        );
        resolve(report);
      } catch (error) {
        reject(error);
      }
    });
  });
}

(async () => {
  const empty = await startApp();
  assert.equal(
    empty.documents,
    0,
    "The installer must not include private books",
  );
  const runtime =
    process.platform === "darwin"
      ? resolve(dirname(executable), "../Resources/backend/bookalyzer-service")
      : join(dirname(executable), "resources/backend/bookalyzer-service.exe");
  const bridge = new PythonBridge(temporary, library, runtime);
  try {
    const { settings } = await bridge.call("bootstrap");
    const docs = [];
    for (let i = 0; i < 7; i++) {
      const name = "Lesetest " + (i + 1) + " – Grüße 🌳.txt";
      const doc = await bridge.call("prepare", {
        name,
        base64data: Buffer.from(
          "„Der warme Wind weht über das alte Feld.“ Das Licht erscheint hinter dem großen Baum. ".repeat(
            30,
          ),
        ).toString("base64"),
        settings: { ...settings, mode: "local" },
      });
      assert.equal(
        doc.name,
        name,
        "UTF-8 names must survive the frozen IPC service",
      );
      docs.push(doc);
    }
    await bridge.call("start", { ids: docs.map((d) => d.id) });
    const deadline = Date.now() + 30000;
    let ready = false;
    while (Date.now() < deadline) {
      const state = await bridge.call("bootstrap");
      assert.ok(
        !state.documents.some((d) => d.status === "error"),
        JSON.stringify(state.documents.map((d) => d.error)),
      );
      if (
        state.documents.length === 7 &&
        state.documents.every((d) => d.status === "ready")
      ) {
        ready = true;
        break;
      }
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    assert.ok(ready, "Synthetic local imports must complete");
  } finally {
    bridge.close();
  }
  const populated = await startApp();
  assert.equal(populated.documents, 7);
  assert.ok(
    populated.ui.charts > 0,
    "Seven saved texts must open the six-text comparison without an API error",
  );
  console.log(
    JSON.stringify({
      ok: true,
      executable,
      emptyWorkingDirectory: temporary,
      empty,
      populated,
    }),
  );
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
