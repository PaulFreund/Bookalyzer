// Integration check of the real renderer exporter, with cached analysis only.
const { resolve, join } = require("node:path");
const { mkdir, writeFile } = require("node:fs/promises");
const assert = require("node:assert/strict");
const { PythonBridge } = require("./bridge.cjs");

(async () => {
  const root = resolve(__dirname, "..");
  const bridge = new PythonBridge(
    root,
    join(root, ".bookanalyzer", "export-test"),
  );
  const { createServer } = await import("vite");
  const server = await createServer({
    configFile: join(root, "vite.config.mjs"),
    server: { middlewareMode: true },
  });
  try {
    const data = await bridge.call("bootstrap");
    const documents = data.documents.filter((d) => d.status === "ready");
    assert.ok(
      documents.length,
      "This integration check needs at least one cached project analysis.",
    );
    const comparison = await bridge.call("compare", {
      ids: documents.slice(0, 6).map((d) => d.id),
    });
    const { exportContent } = await server.ssrLoadModule("/src/export.tsx");
    const output = join(root, "outputs", "desktop-qa");
    await mkdir(output, { recursive: true });
    for (const format of ["html", "csv", "json"]) {
      const content = exportContent(format, documents, data, comparison);
      assert.ok(content.length > 500);
      await writeFile(
        join(output, "analysis-report." + format),
        content,
        "utf8",
      );
      if (format === "html") {
        assert.ok(content.includes("<svg"));
        assert.ok(content.includes("Methode"));
        assert.ok(!content.includes("<script"));
      }
      if (format === "csv")
        assert.equal(
          content.split("\r\n").length,
          1 + documents.reduce((n, d) => n + d.segmentCount, 0),
        );
      if (format === "json")
        assert.equal(JSON.parse(content).documents.length, documents.length);
    }
    const malicious = [
      { ...documents[0], title: '<script>alert("x")</script>' },
    ];
    assert.ok(
      !exportContent("html", malicious, data, null).includes("<script>"),
    );
    malicious[0].title = '=HYPERLINK("file:///test")';
    assert.ok(
      exportContent("csv", malicious, data, null).includes("'=HYPERLINK"),
    );
    console.log(
      JSON.stringify({
        ok: true,
        documents: documents.length,
        output,
        formats: ["html", "csv", "json"],
        escaping: true,
      }),
    );
  } finally {
    bridge.close();
    await server.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
