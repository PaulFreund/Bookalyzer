const { existsSync } = require("node:fs");
const { join } = require("node:path");

function libraryPath(appData, override) {
  if (override) return override;
  const current = join(appData, "Bookalyzer", "library");
  const legacy = join(appData, "BookAnalyzer", "library");
  // Reuse an existing library after the rename; never move or overwrite books.
  return !existsSync(join(current, "library.json")) &&
    existsSync(join(legacy, "library.json"))
    ? legacy
    : current;
}
module.exports = { libraryPath };
