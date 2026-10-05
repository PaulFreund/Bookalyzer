// Private DMG distribution: ad-hoc signed, no Apple account, not notarized.
const { build } = require("../package.json");
module.exports = {
  ...build,
  mac: { ...build.mac, identity: "-", hardenedRuntime: false, notarize: false },
};
