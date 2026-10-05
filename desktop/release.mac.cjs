// A distributable release must never silently become an unsigned DMG.
const { build } = require("../package.json");
if (!process.env.CSC_LINK || !process.env.CSC_KEY_PASSWORD)
  throw new Error(
    "Für einen Release fehlen CSC_LINK / CSC_KEY_PASSWORD (Developer ID Application).",
  );
if (
  !(
    process.env.APPLE_API_KEY &&
    process.env.APPLE_API_KEY_ID &&
    process.env.APPLE_API_ISSUER
  ) &&
  !(
    process.env.APPLE_ID &&
    process.env.APPLE_APP_SPECIFIC_PASSWORD &&
    process.env.APPLE_TEAM_ID
  )
)
  throw new Error("Für einen Release fehlen die Apple-Notarisierungsdaten.");
module.exports = {
  ...build,
  forceCodeSigning: true,
  mac: { ...build.mac, notarize: true },
};
