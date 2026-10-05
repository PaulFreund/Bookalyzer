const assert = require("node:assert/strict");
const { mkdtemp, writeFile, mkdir } = require("node:fs/promises");
const { tmpdir } = require("node:os");
const { join, resolve } = require("node:path");
const { PythonBridge } = require("../desktop/bridge.cjs");

(async () => {
  const root = resolve(__dirname, "..");
  const dataDir = await mkdtemp(join(tmpdir(), "Bookalyzer-exports-"));
  const bridge = new PythonBridge(root, dataDir);
  const { createServer } = await import("vite");
  const server = await createServer({
    configFile: join(root, "vite.config.mjs"),
    server: { middlewareMode: true },
  });
  try {
    const initial = await bridge.call("bootstrap");
    const texts = [
      [
        "Kapitel-Demo.txt",
        "Kapitel 1\n" +
          "Sie kam an. Er sah sie. ".repeat(24) +
          "\nKapitel 2\n" +
          "Als sie am Abend zurückkam, wartete der alte Mann noch immer neben der geschlossenen Tür. ".repeat(
            24,
          ),
      ],
      [
        "Referenz.txt",
        "Kapitel 1\n" +
          "Ein langer Referenzsatz mit vielen anderen Worten beschreibt hier den Ort. ".repeat(
            400,
          ),
      ],
    ];
    const docs = [];
    for (const [name, text] of texts)
      docs.push(
        await bridge.call("prepare", {
          name,
          base64data: Buffer.from(text).toString("base64"),
          settings: {
            ...initial.settings,
            mode: "local",
            detectChapters: true,
          },
        }),
      );
    await bridge.call("start", { ids: docs.map((d) => d.id) });
    const deadline = Date.now() + 30000;
    while (Date.now() < deadline) {
      const state = await bridge.call("bootstrap");
      if (
        docs.every(
          (doc) =>
            state.documents.find((d) => d.id === doc.id)?.status === "ready",
        )
      )
        break;
      await new Promise((r) => setTimeout(r, 100));
    }
    const baseline = await bridge.call("baseline_create", {
      id: docs[1].id,
      name: "Referenzstand",
    });
    const chapterResult = await bridge.call("chapters", {
      id: docs[0].id,
      baselineId: baseline.id,
    });
    const baselineResult = await bridge.call("baseline_compare", {
      ids: [docs[0].id],
      baselineId: baseline.id,
    });
    const { comparisonExport } = await server.ssrLoadModule(
      "/src/ComparisonWorkspace.tsx",
    );
    const output = join(root, "outputs/desktop-qa");
    await mkdir(output, { recursive: true });
    const quality = await bridge.call("quality", {
      ids: [],
      bookId: docs[0].id,
      baselineId: baseline.id,
    });
    assert.equal(quality.catalog.metrics.length, 51);
    assert.equal(quality.rows.length, 2);
    const findings = await bridge.call("quality_findings", {
      id: quality.rows[1].documentId,
      chapterIndex: quality.rows[1].chapterIndex,
      textSha256: quality.rows[1].quality.textSha256,
      metric: "sentenceRepeat",
      offset: 6,
    });
    assert.equal(findings.total, 23);
    assert.equal(findings.items.length, 6);
    assert.equal(findings.offset, 6);
    const deviation = quality.rows[1].summary.deviations.find(
      (d) => d.metric === "sentenceMean",
    );
    assert.ok(
      deviation,
      "Longer sentences must have a concrete explanation and reference band",
    );
    assert.equal(
      deviation.band.n,
      quality.rows[1].comparison.bands.sentenceMean.n,
    );
    const { qualityExport } = await server.ssrLoadModule(
      "/src/qualityExport.tsx",
    );
    for (const format of ["html", "csv", "json"]) {
      const content = qualityExport(
        format,
        quality,
        "sentenceMean",
        true,
        quality.rows.map((r) => r.id),
      );
      await writeFile(join(output, "quality-report." + format), content);
      assert.ok(content.includes(baseline.id));
      if (format === "html") {
        assert.ok(content.includes("<svg"));
        assert.ok(content.includes("Deine nächsten Schritte"));
        assert.ok(content.includes("Was fällt beim Stil auf?"));
        assert.ok(content.includes("Vergleichsbereich:"));
        assert.ok(
          content.includes("deutlich längere Sätze als in deiner Referenz"),
        );
        assert.ok(
          !content.includes("Wiener Sachtextformel"),
          "Default brief omits the technical appendix",
        );
        assert.ok(!content.includes("<script"));
        assert.ok(
          !/="[^"]*(?:NaN|Infinity)/.test(content),
          "Charts cannot contain invalid coordinates",
        );
      }
      if (format === "json") assert.equal(JSON.parse(content).rows.length, 2);
      if (format === "csv") {
        assert.equal(content.split("\r\n").length, 1 + 51 * 2);
        assert.ok(
          !content.includes("\"'-"),
          "Numeric negative deltas remain numeric",
        );
      }
    }
    const detailedQuality = qualityExport(
      "html",
      quality,
      "sentenceMean",
      true,
      quality.rows.map((r) => r.id),
      true,
    );
    assert.ok(detailedQuality.includes("MATTR"));
    assert.ok(detailedQuality.includes("Wiener Sachtextformel"));
    await writeFile(
      join(output, "quality-report-detailed.html"),
      detailedQuality,
    );
    const qualityHostile = structuredClone(quality);
    qualityHostile.rows[0].title = "  =HYPERLINK(1)";
    assert.ok(
      qualityExport("csv", qualityHostile, "mattr", true, []).includes(
        "'  =HYPERLINK",
      ),
    );
    qualityHostile.rows[0].title = "<script>alert(1)</script>";
    assert.ok(
      !qualityExport(
        "html",
        qualityHostile,
        "mattr",
        true,
        qualityHostile.rows.map((r) => r.id),
      ).includes("<script>"),
    );
    const qualityDirect = await bridge.call("quality", {
      ids: docs.map((d) => d.id),
    });
    assert.equal(qualityDirect.rows.length, 2);
    const directHtml = qualityExport("html", qualityDirect, "lix", false, []);
    assert.ok(directHtml.includes("<svg"));
    assert.ok(!/="[^"]*(?:NaN|Infinity)/.test(directHtml));
    const chapterOverview = await bridge.call("quality", {
      ids: [],
      bookId: docs[0].id,
    });
    const withChapterOverview = qualityExport(
      "html",
      qualityDirect,
      "lix",
      false,
      [],
      false,
      chapterOverview.rows,
    );
    assert.ok(
      withChapterOverview.includes("0 von 2 Kapiteln eingeordnet"),
      "Book summaries disclose when too few comparable chapters exist",
    );
    const { qualityColor } = await server.ssrLoadModule(
      "/src/QualityCharts.tsx",
    );
    const percentMetric = quality.catalog.metrics.find(
      (m) => m.id === "longSentences",
    );
    assert.notEqual(
      qualityColor(-1, percentMetric, true),
      qualityColor(1, percentMetric, true),
      "The direction of a delta is visible",
    );
    assert.ok(
      qualityColor(0, percentMetric, true).endsWith(", 0)"),
      "Zero remains neutral",
    );
    for (const [name, data] of [
      ["chapter-report", chapterResult],
      ["baseline-report", baselineResult],
    ]) {
      for (const format of ["html", "csv", "json"]) {
        const content = comparisonExport(format, data, "sentenceMean");
        await writeFile(join(output, name + "." + format), content);
        if (format === "html") {
          assert.ok(content.includes("<svg"));
          assert.ok(!content.includes("<script"));
          assert.ok(content.includes(baseline.id));
        }
        if (format === "json")
          assert.equal(JSON.parse(content).baseline.id, baseline.id);
        if (format === "csv") {
          assert.ok(content.includes("Δ Satzlänge"));
          assert.ok(
            !content.includes("\"'-"),
            "Numeric negative deltas must remain numeric",
          );
        }
      }
    }
    const hostile = structuredClone(chapterResult);
    hostile.title = "<script>alert(1)</script>";
    hostile.chapters[0].title = "=HYPERLINK(1)";
    assert.ok(
      !comparisonExport("html", hostile, "sentenceMean").includes("<script>"),
    );
    assert.ok(
      comparisonExport("csv", hostile, "sentenceMean").includes("'=HYPERLINK"),
    );
    console.log(
      JSON.stringify({
        ok: true,
        chapters: chapterResult.chapters.length,
        output,
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
