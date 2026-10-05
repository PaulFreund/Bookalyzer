// Starts the frozen service from an unrelated, empty directory: no project or venv.
const assert = require("node:assert/strict");
const { mkdtemp, writeFile } = require("node:fs/promises");
const { join, resolve } = require("node:path");
const { tmpdir } = require("node:os");
const { PythonBridge } = require("../desktop/bridge.cjs");

(async () => {
  const runtime = resolve(
    process.argv[2] ||
      join(
        "build/runtime/bookalyzer-service",
        process.platform === "win32"
          ? "bookalyzer-service.exe"
          : "bookalyzer-service",
      ),
  );
  const root = await mkdtemp(join(tmpdir(), "Bookalyzer-runtime-"));
  const checked = require("node:child_process").spawnSync(
    runtime,
    ["--self-check"],
    { cwd: root, encoding: "utf8", windowsHide: true, timeout: 60000 },
  );
  assert.equal(checked.status, 0, checked.stderr);
  assert.equal(
    JSON.parse(checked.stdout.trim().split(/\r?\n/).at(-1)).features,
    304,
  );
  const bridge = new PythonBridge(root, join(root, "private-library"), runtime);
  try {
    const initial = await bridge.call("bootstrap");
    assert.equal(
      initial.documents.length,
      0,
      "Distribution must not contain private project data",
    );
    assert.ok(
      initial.reference.available,
      "Published descriptive reference must be bundled",
    );
    const settings = {
      ...initial.settings,
      minWords: 100,
      targetWords: 200,
      maxWords: 300,
      detectChapters: true,
    };
    const source =
      "Kapitel 1\n" +
      "Sie sah das Meer. Der Wind kam näher. ".repeat(30) +
      "\nKapitel 2\n" +
      "Dann wurde es still. ".repeat(30);
    const prepared = [];
    for (const [name, text] of [
      ["Buch.txt", source],
      [
        "Referenz.txt",
        "Kapitel 1\n" +
          "Ein langer Referenzsatz mit sehr vielen unterschiedlichen Worten am Ende. ".repeat(
            30,
          ),
      ],
    ]) {
      prepared.push(
        await bridge.call("prepare", {
          name,
          base64data: Buffer.from(text).toString("base64"),
          settings,
        }),
      );
    }
    await bridge.call("start", { ids: prepared.map((d) => d.id) });
    let state;
    const deadline = Date.now() + 30000;
    while (Date.now() < deadline) {
      state = await bridge.call("bootstrap");
      if (state.documents.every((d) => d.status === "ready")) break;
      if (state.documents.some((d) => d.status === "error"))
        throw new Error(JSON.stringify(state.documents.map((d) => d.error)));
      await new Promise((r) => setTimeout(r, 100));
    }
    assert.ok(state.documents.every((d) => d.status === "ready"));
    await assert.rejects(
      bridge.call("storyscope_start", { id: prepared[0].id }),
      /ausdrücklich freigeben/,
      "Adding StoryScope through the frozen IPC service requires fresh consent",
    );
    const baseline = await bridge.call("baseline_create", {
      id: prepared[1].id,
      name: "Laufzeittest",
    });
    const result = await bridge.call("chapters", {
      id: prepared[0].id,
      baselineId: baseline.id,
    });
    assert.equal(result.chapters.length, 2);
    assert.ok(
      result.chapters.every((c) => c.comparison.delta.sentenceMean < 0),
    );
    const compare = await bridge.call("baseline_compare", {
      ids: [prepared[0].id],
      baselineId: baseline.id,
    });
    assert.equal(compare.rows.length, 1);
    const quality = await bridge.call("quality", {
      ids: [],
      bookId: prepared[0].id,
      baselineId: baseline.id,
    });
    assert.equal(quality.catalog.version, "2.1.0");
    assert.equal(quality.catalog.metrics.length, 51);
    assert.ok(quality.rows.every((row) => row.summary.cards.length === 4));
    assert.ok(
      quality.rows.every((row) => row.comparison.basis === "matched_windows"),
    );
    const row = quality.rows[0];
    const evidence = row.quality.evidence[0];
    assert.ok(
      evidence,
      "Bundled diagnostics must return original text findings",
    );
    await bridge.call("quality_decision", {
      id: row.documentId,
      chapterIndex: row.chapterIndex,
      textSha256: row.quality.textSha256,
      metric: evidence.metric,
      start: evidence.start,
      end: evidence.end,
      intentional: true,
    });
    const decided = await bridge.call("quality", {
      ids: [],
      bookId: prepared[0].id,
    });
    assert.equal(decided.rows[0].summary.intentional, 1);
    const findings = await bridge.call("quality_findings", {
      id: row.documentId,
      chapterIndex: row.chapterIndex,
      textSha256: row.quality.textSha256,
      status: "intentional",
    });
    assert.equal(findings.total, 1);
    assert.equal(findings.items[0].start, evidence.start);
    const expanded = await bridge.call("local_update", {
      id: prepared[0].id,
      settings: {
        qualityGroups: ["readability", "rhythm"],
        longSentenceWords: 35,
      },
    });
    assert.equal(expanded.status, "ready");
    assert.equal(expanded.segmentCount, prepared[0].segmentCount);
    const updated = await bridge.call("quality", { ids: [prepared[0].id] });
    assert.deepEqual(updated.rows[0].quality.groups, ["readability", "rhythm"]);
    assert.equal(updated.rows[0].quality.longSentenceWords, 35);
    await bridge.call("remove", { id: prepared[1].id });
    assert.deepEqual(
      await bridge.call("baseline_compare", {
        ids: [prepared[0].id],
        baselineId: baseline.id,
      }),
      compare,
    );
    // Retain a tiny non-private fixture for the native renderer smoke check.
    await writeFile(
      join(root, "runtime-test.json"),
      JSON.stringify({ ok: true, result, compare }),
    );
    console.log(
      JSON.stringify({
        ok: true,
        runtime,
        privateLibrary: join(root, "private-library"),
        chapters: result.chapters.length,
        qualityMethods: quality.catalog.metrics.length,
      }),
    );
  } finally {
    bridge.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
