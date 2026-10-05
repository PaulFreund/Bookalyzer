// Capture the real Electron renderer with an isolated, verified public-domain demo.
// Native capturePage omits the desktop, other windows, mouse pointer and account UI.
const { mkdir, writeFile } = require("node:fs/promises");
const { join, resolve } = require("node:path");
const { spawnSync } = require("node:child_process");

async function capture({ window, bridge, root }) {
  const state = await bridge.call("bootstrap");
  const demo = state.documents[0];
  if (
    state.documents.length !== 1 ||
    demo?.title !== "Die Verwandlung" ||
    demo.status !== "ready" ||
    demo.wordCount !== 19148 ||
    demo.chapterCount !== 3 ||
    demo.settings.mode !== "local" ||
    demo.narrative
  )
    throw new Error(
      "Screenshots require the completed public-domain README demo only.",
    );
  const { readFile } = require("node:fs/promises");
  const imported = JSON.parse(
    await readFile(join(state.method.library, demo.id, "import.json"), "utf8"),
  );
  if (
    imported.source_sha256 !==
    "af3638d991aa13e899cc57fd281c1b4aae5880f626d7a53c5c8061e976043b7b"
  )
    throw new Error(
      "The demo text does not match the public source used for the README.",
    );
  const directory = join(root, "docs/screenshots");
  await mkdir(directory, { recursive: true });
  window.setContentSize(1440, 1000);
  window.webContents.setBackgroundThrottling(false);
  async function ready(expression) {
    await window.webContents
      .executeJavaScript(`new Promise((resolve, reject) => {
      const deadline = Date.now() + 30000;
      const check = () => {
        if (${expression}) requestAnimationFrame(() => requestAnimationFrame(resolve));
        else if (Date.now() > deadline) reject(new Error('README view did not finish rendering'));
        else setTimeout(check, 100);
      }; check();
    })`);
  }
  async function save(name, rectangle) {
    await window.webContents.executeJavaScript(
      "new Promise(resolve => setTimeout(resolve, 250))",
    );
    const screenshot = await window.webContents.capturePage(rectangle);
    await writeFile(join(directory, name + ".png"), screenshot.toPNG());
  }
  await ready(
    "document.querySelector('.quality-overview') && document.querySelector('svg[role=img]') && document.body.innerText.includes('19.148')",
  );
  await window.webContents.executeJavaScript("window.scrollTo(0, 0)");
  await save("overview");
  await ready("document.body.innerText.includes('6.381 Wörter')");
  await window.webContents.executeJavaScript(`(() => {
    const heading = [...document.querySelectorAll('h2,h3')].find(h => h.textContent.includes('Welche Kapitel verdienen Aufmerksamkeit'));
    if (!heading) throw new Error('Chapter overview missing');
    heading.scrollIntoView({block:'start'});
  })()`);
  const chapterRectangle = await window.webContents.executeJavaScript(`(() => {
    const heading = [...document.querySelectorAll('h2,h3')].find(h => h.textContent.includes('Welche Kapitel verdienen Aufmerksamkeit'));
    const box = heading.closest('section').getBoundingClientRect();
    return {x:Math.floor(box.x), y:Math.floor(box.y), width:Math.ceil(box.width), height:Math.ceil(box.height)};
  })()`);
  await save("chapters", chapterRectangle);
  await window.webContents.executeJavaScript(`(() => {
    const button = [...document.querySelectorAll('button')].find(b => b.textContent.includes('Details · 51 Kennzahlen'));
    if (!button) throw new Error('Details switch missing');
    button.click(); window.scrollTo(0, 0);
  })()`);
  await ready(
    "!document.querySelector('.quality-overview') && document.querySelector('svg[role=img]') && document.body.innerText.includes('MATTR')",
  );
  await window.webContents.executeJavaScript(`(() => {
    document.querySelector('details.quality-compare-settings').open = true;
    const button = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Kapitel vergleichen');
    if (!button) throw new Error('Chapter comparison switch missing');
    button.click();
  })()`);
  await ready(
    "document.querySelector('.quality-primary-selectors select')?.options.length === 3 && document.querySelector('svg[role=img]') && !document.querySelector('.quality-loading')",
  );
  await window.webContents.executeJavaScript(
    "new Promise(resolve => setTimeout(resolve, 1000))",
  );
  await window.webContents.executeJavaScript(
    "document.querySelector('details.quality-compare-settings').open = false; window.scrollTo(0, 0)",
  );
  await save("details");
  console.log(
    JSON.stringify({
      ok: true,
      book: demo.title,
      screenshots: ["overview.png", "chapters.png", "details.png"],
    }),
  );
}

module.exports = { capture };
if (require.main === module) {
  const root = resolve(__dirname, "..");
  const electron = require("electron");
  if (typeof electron !== "string")
    throw new Error("Run this entry with Node.js.");
  const result = spawnSync(
    electron,
    [
      root,
      "--readme-screenshots",
      "--force-device-scale-factor=1",
      "--user-data-dir=" + join(root, "outputs/readme-demo/capture-profile"),
    ],
    {
      cwd: root,
      windowsHide: true,
      stdio: "inherit",
      env: {
        ...process.env,
        BOOKANALYZER_DATA: join(root, "outputs/readme-demo/library"),
      },
    },
  );
  if (result.error) throw result.error;
  process.exitCode = result.status ?? 1;
}
