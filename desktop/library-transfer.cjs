const { mkdtemp, rm } = require("node:fs/promises");
const { createReadStream, createWriteStream } = require("node:fs");
const { tmpdir } = require("node:os");
const { join, resolve, dirname } = require("node:path");
const { pipeline } = require("node:stream/promises");
const { Transform } = require("node:stream");

const MAX_ARCHIVE_BYTES = 1024 * 1024 * 1024;
const pathMethods = new Set(["library_export", "library_inspect"]);

function registerLibraryDialogs({
  ipcMain,
  dialog,
  getWindow,
  bridge,
  validSender,
}) {
  ipcMain.handle("library-export", async (event) => {
    validSender(event);
    const result = await dialog.showSaveDialog(getWindow(), {
      title: "Datenbestand sichern",
      defaultPath: `Bookalyzer-Datenbestand-${new Date().toISOString().slice(0, 10)}.zip`,
      filters: [{ name: "Bookalyzer-Sicherung", extensions: ["zip"] }],
    });
    if (result.canceled || !result.filePath) return false;
    await bridge.call("library_export", {
      path: /\.zip$/i.test(result.filePath)
        ? result.filePath
        : result.filePath + ".zip",
    });
    return true;
  });
  ipcMain.handle("library-pick", async (event) => {
    validSender(event);
    const result = await dialog.showOpenDialog(getWindow(), {
      title: "Datenbestand laden",
      properties: ["openFile"],
      filters: [{ name: "Bookalyzer-Sicherung", extensions: ["zip"] }],
    });
    if (result.canceled || !result.filePaths.length) return null;
    return bridge.call("library_inspect", { path: result.filePaths[0] });
  });
}

function libraryMiddleware(bridge) {
  return async (req, res, next) => {
    const route = req.url?.split("?")[0];
    if (!["/api/library/export", "/api/library/inspect"].includes(route)) {
      next();
      return;
    }
    const origin = req.headers.origin;
    if (
      (origin && origin !== `http://${req.headers.host}`) ||
      (route.endsWith("/export")
        ? req.method !== "GET"
        : req.method !== "POST") ||
      req.headers["x-bookalyzer-library"] !== "1"
    ) {
      res.writeHead(403).end();
      return;
    }
    let temporary;
    try {
      temporary = await mkdtemp(join(tmpdir(), "Bookalyzer-transfer-"));
      const path = join(temporary, "Bookalyzer-Datenbestand.zip");
      if (route.endsWith("/export")) {
        await bridge.call("library_export", { path });
        res.setHeader("Content-Type", "application/zip");
        res.setHeader(
          "Content-Disposition",
          'attachment; filename="Bookalyzer-Datenbestand.zip"',
        );
        await pipeline(createReadStream(path), res);
      } else {
        let bytes = 0;
        const limiter = new Transform({
          transform(chunk, _, callback) {
            bytes += chunk.length;
            callback(
              bytes > MAX_ARCHIVE_BYTES
                ? new Error("ZIP-Datei zu groß (max. 1 GB).")
                : null,
              chunk,
            );
          },
        });
        await pipeline(req, limiter, createWriteStream(path));
        const result = await bridge.call("library_inspect", { path });
        res.setHeader("Content-Type", "application/json");
        res.end(JSON.stringify({ result }));
      }
    } catch (error) {
      if (!res.headersSent && !res.destroyed) {
        res.statusCode = 400;
        res.setHeader("Content-Type", "application/json");
        res.end(JSON.stringify({ error: error.message }));
      }
    } finally {
      // Only remove the exact temporary directory created for this transfer.
      if (temporary && dirname(resolve(temporary)) === resolve(tmpdir()))
        await rm(temporary, { recursive: true, force: true }).catch(() => {});
    }
  };
}

module.exports = { registerLibraryDialogs, libraryMiddleware, pathMethods };
