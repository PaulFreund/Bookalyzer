const assert = require("node:assert/strict");
const { createServer } = require("node:http");
const {
  readFile,
  writeFile,
  access,
  mkdtemp,
  mkdir,
  rm,
} = require("node:fs/promises");
const { tmpdir } = require("node:os");
const { join, dirname, resolve } = require("node:path");
const {
  registerLibraryDialogs,
  libraryMiddleware,
  pathMethods,
} = require("./library-transfer.cjs");

async function testDialogs() {
  const handlers = new Map(),
    calls = [];
  let valid = true,
    canceled = true;
  registerLibraryDialogs({
    ipcMain: { handle: (name, handler) => handlers.set(name, handler) },
    getWindow: () => "window",
    dialog: {
      showSaveDialog: async () => ({ canceled, filePath: "/selected/backup" }),
      showOpenDialog: async () => ({
        canceled,
        filePaths: ["/selected/library.zip"],
      }),
    },
    validSender() {
      if (!valid) throw new Error("invalid sender");
    },
    bridge: {
      async call(method, params) {
        calls.push({ method, params });
        return { id: "preview" };
      },
    },
  });
  assert.equal(await handlers.get("library-export")({}), false);
  assert.equal(await handlers.get("library-pick")({}), null);
  assert.equal(calls.length, 0);
  canceled = false;
  assert.equal(await handlers.get("library-export")({}), true);
  assert.equal((await handlers.get("library-pick")({})).id, "preview");
  assert.deepEqual(calls, [
    { method: "library_export", params: { path: "/selected/backup.zip" } },
    { method: "library_inspect", params: { path: "/selected/library.zip" } },
  ]);
  valid = false;
  await assert.rejects(handlers.get("library-export")({}), /invalid sender/);
  assert.equal(calls.length, 2);
  assert.ok(
    pathMethods.has("library_export") && pathMethods.has("library_inspect"),
  );
  assert.ok(!pathMethods.has("library_import"));
}

async function testStreaming() {
  const payload = Buffer.from("PK\x03\x04test archive data"),
    paths = [];
  const middleware = libraryMiddleware({
    async call(method, { path }) {
      paths.push(path);
      if (method === "library_export") await writeFile(path, payload);
      else if (method === "library_inspect") {
        assert.deepEqual(await readFile(path), payload);
        return { id: "preview", documentCount: 2 };
      }
    },
  });
  const requests = [];
  const server = createServer((req, res) =>
    requests.push(middleware(req, res, () => res.writeHead(404).end())),
  );
  await new Promise((ready) => server.listen(0, "127.0.0.1", ready));
  const url = `http://127.0.0.1:${server.address().port}`;
  try {
    assert.equal((await fetch(url + "/api/library/export")).status, 403);
    assert.equal(
      (
        await fetch(url + "/api/library/export", {
          headers: {
            "X-Bookalyzer-Library": "1",
            Origin: "https://other.example",
          },
        })
      ).status,
      403,
    );
    assert.equal(paths.length, 0);
    const exported = await fetch(url + "/api/library/export", {
      headers: { "X-Bookalyzer-Library": "1" },
    });
    assert.equal(exported.headers.get("content-type"), "application/zip");
    assert.deepEqual(Buffer.from(await exported.arrayBuffer()), payload);
    const imported = await fetch(url + "/api/library/inspect", {
      method: "POST",
      headers: { "X-Bookalyzer-Library": "1" },
      body: payload,
    });
    assert.deepEqual(await imported.json(), {
      result: { id: "preview", documentCount: 2 },
    });
    assert.equal(paths.length, 2);
  } finally {
    server.closeAllConnections();
    await new Promise((done) => server.close(done));
  }
  await Promise.all(requests);
  for (const path of paths) await assert.rejects(access(path));
}

async function testIpcRoundTrip() {
  const { PythonBridge } = require("./bridge.cjs");
  const root = await mkdtemp(join(tmpdir(), "Bookalyzer-library-ipc-"));
  const dataDir = join(root, "library");
  await mkdir(dataDir);
  await writeFile(
    join(dataDir, "library.json"),
    JSON.stringify({
      settings: {},
      documents: [],
      baselines: [],
      seeded: true,
    }),
  );
  const bridge = new PythonBridge(resolve(__dirname, ".."), dataDir);
  try {
    const state = await bridge.call("bootstrap");
    assert.equal(state.documents.length, 0);
    const prepared = await bridge.call("prepare", {
      name: "Archivprüfung.txt",
      base64data: Buffer.from(
        "Der Wind kommt vom Meer. Sie wartet auf den Regen. ".repeat(60),
      ).toString("base64"),
      settings: {
        ...state.settings,
        minWords: 100,
        targetWords: 200,
        maxWords: 300,
      },
    });
    // A draft is also part of the complete dataset and requires no external call.
    const archive = join(root, "library.zip");
    await bridge.call("library_export", { path: archive });
    await bridge.call("remove", { id: prepared.id });
    const preview = await bridge.call("library_inspect", { path: archive });
    await assert.rejects(
      bridge.call("library_import", { id: preview.id }),
      /bestätigen/,
    );
    const restored = await bridge.call("library_import", {
      id: preview.id,
      replaceConfirmed: true,
    });
    assert.ok(await readFile(restored.backupPath));
    const library = JSON.parse(
      await readFile(join(dataDir, "library.json"), "utf8"),
    );
    assert.ok(library.documents.some((doc) => doc.id === prepared.id));
  } finally {
    bridge.close();
    // Keep data if Windows still has handles open while the child exits.
    if (dirname(resolve(root)) === resolve(tmpdir()))
      await rm(root, {
        recursive: true,
        force: true,
        maxRetries: 5,
        retryDelay: 100,
      });
  }
}

(async () => {
  await testDialogs();
  await testStreaming();
  await testIpcRoundTrip();
  console.log("Library dialogs, streaming and Python IPC round trip passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
