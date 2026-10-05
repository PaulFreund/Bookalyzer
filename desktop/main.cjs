const {
  app,
  BrowserWindow,
  ipcMain,
  dialog,
  shell,
  Menu,
} = require("electron");
const { join, resolve } = require("node:path");
const { readFile, writeFile, stat } = require("node:fs/promises");
const { existsSync } = require("node:fs");
const { pathToFileURL } = require("node:url");
const { PythonBridge } = require("./bridge.cjs");
const { renderPdf } = require("./pdf.cjs");
const { libraryPath } = require("./library-path.cjs");
const {
  registerLibraryDialogs,
  pathMethods,
} = require("./library-transfer.cjs");
let root = process.env.BOOKANALYZER_ROOT || resolve(__dirname, "..");
let window,
  bridge,
  quitting = false;
app.setName("Bookalyzer");
const entry = pathToFileURL(
  join(__dirname, "..", "desktop-dist", "index.html"),
).href;
if (!app.requestSingleInstanceLock()) app.quit();
app.on("second-instance", () => {
  if (window) {
    if (window.isMinimized()) window.restore();
    window.show();
    window.focus();
  }
});
app.on("activate", () => {
  if (window) {
    window.show();
    window.focus();
  }
});
function validSender(event) {
  if (
    event.sender !== window?.webContents ||
    event.senderFrame !== window.webContents.mainFrame ||
    event.senderFrame.url.split("#")[0] !== entry
  )
    throw new Error("Ungültiger Absender.");
}
app.whenReady().then(async () => {
  const runtime = app.isPackaged
    ? join(
        process.resourcesPath,
        "backend",
        process.platform === "win32"
          ? "bookalyzer-service.exe"
          : "bookalyzer-service",
      )
    : undefined;
  if (runtime && !existsSync(runtime)) {
    dialog.showErrorBox(
      "Bookalyzer",
      "Die eingebaute Analyse-Laufzeit fehlt. Bitte die vollständige App erneut installieren.",
    );
    app.quit();
    return;
  }
  if (runtime) root = join(process.resourcesPath, "backend");
  const dataDir =
    process.env.BOOKANALYZER_DATA ||
    (app.isPackaged ? libraryPath(app.getPath("appData")) : undefined);
  bridge = new PythonBridge(root, dataDir, runtime);
  Menu.setApplicationMenu(
    Menu.buildFromTemplate([
      ...(process.platform === "darwin" ? [{ role: "appMenu" }] : []),
      { role: "fileMenu" },
      { role: "editMenu" },
      { role: "viewMenu" },
      { role: "windowMenu" },
    ]),
  );
  ipcMain.handle("analysis", (event, method, params) => {
    validSender(event);
    if (pathMethods.has(method))
      throw new Error("Bitte den Dateidialog verwenden.");
    return bridge.call(method, params);
  });
  registerLibraryDialogs({
    ipcMain,
    dialog,
    getWindow: () => window,
    bridge,
    validSender,
  });
  ipcMain.handle("pick-files", async (event) => {
    validSender(event);
    const result = await dialog.showOpenDialog(window, {
      properties: ["openFile", "multiSelections"],
      filters: [{ name: "Texte", extensions: ["txt", "docx", "epub", "pdf"] }],
    });
    return Promise.all(
      result.filePaths.map(async (path) => {
        if ((await stat(path)).size > 30 * 1024 * 1024)
          throw new Error("Datei zu groß (max. 30 MB).");
        return {
          name: require("node:path").basename(path),
          base64: (await readFile(path)).toString("base64"),
        };
      }),
    );
  });
  ipcMain.handle("save-report", async (event, { name, content, format }) => {
    validSender(event);
    if (
      !["html", "json", "csv", "pdf"].includes(format) ||
      typeof content !== "string" ||
      content.length > 30 * 1024 * 1024
    )
      throw new Error("Ungültiger Export.");
    const result = await dialog.showSaveDialog(window, {
      defaultPath: String(name).replace(/[\\/:*?"<>|]/g, "_"),
      filters: [{ name: format.toUpperCase(), extensions: [format] }],
    });
    if (result.canceled || !result.filePath) return false;
    if (format === "pdf") {
      await writeFile(result.filePath, await renderPdf(content));
    } else await writeFile(result.filePath, content, "utf8");
    return true;
  });
  window = new BrowserWindow({
    width: 1480,
    height: 980,
    minWidth: 960,
    minHeight: 700,
    title: "Bookalyzer",
    backgroundColor: "#f6f7fb",
    autoHideMenuBar: true,
    show:
      !process.argv.includes("--smoke-test") &&
      !process.argv.includes("--readme-screenshots"),
    webPreferences: {
      preload: join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  window.webContents.session.setPermissionRequestHandler((_, __, callback) =>
    callback(false),
  );
  window.webContents.session.webRequest.onHeadersReceived((details, callback) =>
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        "Content-Security-Policy": [
          "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-src 'none'",
        ],
      },
    }),
  );
  window.webContents.setWindowOpenHandler(({ url }) => {
    if (
      [
        "https://arxiv.org/abs/2604.03136",
        "https://github.com/jenna-russell/storyscope",
        "https://quanteda.io/reference/textstat_readability.html",
        "https://quanteda.io/reference/textstat_lexdiv.html",
        "https://doi.org/10.3758/BRM.42.2.381",
        "https://www.lix.se/",
        "https://github.com/textstat/textstat",
      ].includes(url)
    )
      shell.openExternal(url);
    return { action: "deny" };
  });
  window.webContents.on("will-navigate", (event, url) => {
    if (url !== entry) event.preventDefault();
  });
  window.on("close", (event) => {
    if (process.platform === "darwin" && !quitting) {
      event.preventDefault();
      window.hide();
    }
  });
  await window.loadURL(entry);
  if (process.argv.includes("--readme-screenshots")) {
    try {
      await require("../scripts/capture_readme.cjs").capture({
        window,
        bridge,
        root,
      });
      bridge.close();
      app.exit(0);
    } catch (error) {
      console.error(error);
      bridge.close();
      app.exit(1);
    }
    return;
  }
  if (process.argv.includes("--smoke-test")) {
    try {
      const data = await bridge.call("bootstrap");
      await window.webContents
        .executeJavaScript(`new Promise((resolve, reject) => {
        const deadline = Date.now() + 20000;
        const check = () => {
          if (document.querySelector('.chart, .quality-overview, .welcome-empty')) resolve(true);
          else if (Date.now() > deadline) reject(new Error('Renderer hat die Analysedaten nicht geladen.'));
          else setTimeout(check, 100);
        }; check();
      })`);
      const ui = await window.webContents.executeJavaScript(
        '({ title: document.title, bridge: typeof window.bookalyzer.call, libraryExport: typeof window.bookalyzer.exportLibrary, libraryPick: typeof window.bookalyzer.pickLibrary, charts: document.querySelectorAll("svg[role=img]").length, isolated: typeof window.require === "undefined" })',
      );
      if (ui.bridge !== "function" || !ui.isolated)
        throw new Error("Renderer oder IPC fehlt.");
      if (ui.libraryExport !== "function" || ui.libraryPick !== "function")
        throw new Error("Dateidialoge für den Datenbestand fehlen.");
      if (data.documents.some((doc) => doc.status === "ready") && ui.charts < 1)
        throw new Error(
          "Fertige Analysen müssen ein sichtbares Qualitätsdiagramm laden.",
        );
      const reportPath = join(
        root,
        "outputs",
        "desktop-qa",
        "analysis-report.html",
      );
      if (existsSync(reportPath)) {
        const pdf = await renderPdf(await readFile(reportPath, "utf8"));
        if (pdf.length < 1000 || pdf.subarray(0, 4).toString() !== "%PDF")
          throw new Error("PDF-Export fehlgeschlagen.");
        await writeFile(
          join(root, "outputs", "desktop-qa", "analysis-report.pdf"),
          pdf,
        );
      }
      console.log(
        JSON.stringify({ ok: true, documents: data.documents.length, ui }),
      );
      bridge.close();
      app.exit(0);
    } catch (error) {
      console.error(error);
      bridge.close();
      app.exit(1);
    }
  }
});
app.on("before-quit", () => {
  quitting = true;
  bridge?.close();
});
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
