const assert = require("node:assert/strict");
const {
  mkdtempSync,
  mkdirSync,
  writeFileSync,
  readFileSync,
} = require("node:fs");
const { tmpdir } = require("node:os");
const { join } = require("node:path");
const { libraryPath } = require("./library-path.cjs");
const root = mkdtempSync(join(tmpdir(), "Bookalyzer-rename-"));
const current = join(root, "Bookalyzer", "library");
const legacy = join(root, "BookAnalyzer", "library");
assert.equal(libraryPath(root), current);
mkdirSync(legacy, { recursive: true });
writeFileSync(join(legacy, "library.json"), "legacy-books");
assert.equal(libraryPath(root), legacy);
mkdirSync(current, { recursive: true });
writeFileSync(join(current, "library.json"), "new-books");
assert.equal(libraryPath(root), current);
assert.equal(libraryPath(root, "explicit-library"), "explicit-library");
assert.equal(
  readFileSync(join(legacy, "library.json"), "utf8"),
  "legacy-books",
);
assert.equal(readFileSync(join(current, "library.json"), "utf8"), "new-books");
console.log("Existing libraries survive the Bookalyzer rename.");
