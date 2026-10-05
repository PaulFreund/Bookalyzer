const { BrowserWindow } = require("electron");

async function renderPdf(content) {
  const printWindow = new BrowserWindow({
    show: false,
    webPreferences: {
      partition: "report-" + require("node:crypto").randomUUID(),
      sandbox: true,
      contextIsolation: true,
      nodeIntegration: false,
      javascript: false,
    },
  });
  try {
    printWindow.webContents.session.webRequest.onBeforeRequest(
      { urls: ["http://*/*", "https://*/*", "file://*/*"] },
      (_, callback) => callback({ cancel: true }),
    );
    await printWindow.loadURL(
      "data:text/html;charset=utf-8," + encodeURIComponent(content),
    );
    return await printWindow.webContents.printToPDF({
      printBackground: true,
      pageSize: "A4",
      preferCSSPageSize: true,
    });
  } finally {
    printWindow.destroy();
  }
}
module.exports = { renderPdf };
