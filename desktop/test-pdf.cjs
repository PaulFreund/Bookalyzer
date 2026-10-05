const { app } = require("electron");
const { readFile, writeFile } = require("node:fs/promises");
const { resolve } = require("node:path");
const { renderPdf } = require("./pdf.cjs");
app.on("window-all-closed", () => {});
app.whenReady().then(async () => {
  try {
    for (const name of [
      "chapter-report",
      "baseline-report",
      "quality-report",
    ]) {
      const root = resolve(__dirname, "../outputs/desktop-qa", name);
      const pdf = await renderPdf(await readFile(root + ".html", "utf8"));
      if (pdf.subarray(0, 4).toString() !== "%PDF")
        throw new Error("Invalid PDF output");
      await writeFile(root + ".pdf", pdf);
    }
    console.log(
      JSON.stringify({
        ok: true,
        reports: [
          "chapter-report.pdf",
          "baseline-report.pdf",
          "quality-report.pdf",
        ],
      }),
    );
    app.exit(0);
  } catch (error) {
    console.error(error);
    app.exit(1);
  }
});
