#!/bin/bash
# Native macOS build for private distribution; run by double-clicking in Finder.
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  printf 'Dieses Skript bitte auf dem MacBook starten. Die DMG braucht eine native Mac-Laufzeit.\n' >&2
  exit 1
fi

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"
mkdir -p build
BUILD_LOG="$PROJECT_DIR/build/mac-build.log"
exec > >(tee -a "$BUILD_LOG") 2>&1
BUILD_STEP="Voraussetzungen"
finish() {
  local result="$1"
  trap - EXIT
  if [[ "$result" -ne 0 ]]; then
    printf '\nDer Build wurde bei „%s“ gestoppt.\n' "$BUILD_STEP"
    printf 'Die Fehlermeldung steht oben und in: %s\n' "$BUILD_LOG"
    printf 'Nach dem Beheben erneut doppelklicken. Anleitung: MAC_INSTALL.md\n'
  fi
  if [[ -t 0 ]]; then
    printf '\nMit Enter dieses Fenster schließen. '
    read -r || true
  fi
  exit "$result"
}
trap 'finish $?' EXIT

printf '\nBookalyzer — private Mac-DMG erstellen\n'
date
MAC_VERSION="$(sw_vers -productVersion)"
if [[ "${MAC_VERSION%%.*}" -lt 14 ]]; then
  printf 'Benötigt wird macOS 14 Sonoma oder neuer. Dieser Mac: %s\n' "$MAC_VERSION" >&2
  exit 1
fi
if [[ "$(sysctl -in sysctl.proc_translated 2>/dev/null || true)" == "1" ]]; then
  printf 'Bitte Terminal ohne „Mit Rosetta öffnen“ starten und erneut doppelklicken.\n' >&2
  exit 1
fi
case "$(uname -m)" in
  arm64) CPU=arm64; BREW_DEFAULT=/opt/homebrew/bin/brew ;;
  x86_64) CPU=x64; BREW_DEFAULT=/usr/local/bin/brew ;;
  *) printf 'Diese Prozessorarchitektur wird nicht unterstützt.\n' >&2; exit 1 ;;
esac
if ! xcode-select -p >/dev/null 2>&1; then
  xcode-select --install || true
  printf 'Bitte Apples Command Line Tools im geöffneten Dialog installieren und das Skript erneut starten.\n' >&2
  exit 1
fi
if [[ -x "$BREW_DEFAULT" ]]; then
  BREW="$BREW_DEFAULT"
elif command -v brew >/dev/null 2>&1; then
  BREW="$(command -v brew)"
else
  printf 'Einmalig Homebrew installieren: https://brew.sh/\n'
  printf 'Dort gibt es auch einen .pkg-Installer. Danach dieses Skript erneut doppelklicken.\n'
  open https://brew.sh/
  exit 1
fi

BUILD_STEP="Node 22 und Python 3.11 einrichten"
BREW_PREFIX="$("$BREW" --prefix)"
NODE_PREFIX="$BREW_PREFIX/opt/node@22"
PYTHON_PREFIX="$BREW_PREFIX/opt/python@3.11"
[[ -x "$NODE_PREFIX/bin/node" ]] || "$BREW" install node@22
[[ -x "$PYTHON_PREFIX/bin/python3.11" ]] || "$BREW" install python@3.11
export PATH="$NODE_PREFIX/bin:$PYTHON_PREFIX/bin:$BREW_PREFIX/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
export PYTHONUTF8=1
export MACOSX_DEPLOYMENT_TARGET=14.0
export BOOKANALYZER_PYTHON="$PROJECT_DIR/.venv/bin/python"
# This is intentionally an ad-hoc signed build, irrespective of installed certificates.
export CSC_IDENTITY_AUTO_DISCOVERY=false
unset ELECTRON_RUN_AS_NODE BOOKANALYZER_ROOT BOOKANALYZER_DATA
if [[ "$(node -p 'process.arch')" != "$CPU" ]]; then
  printf 'Node und dieser Mac haben unterschiedliche Architekturen. Bitte die native Homebrew-Installation verwenden.\n' >&2
  exit 1
fi
if [[ ! -d .venv ]]; then
  python3.11 -m venv .venv
fi
if [[ ! -x .venv/bin/python ]]; then
  printf 'Die vorhandene .venv gehört nicht zu macOS. Das Baupaket in einen frischen Ordner entpacken.\n' >&2
  exit 1
fi
.venv/bin/python -c 'import sys; assert sys.version_info[:2] == (3, 11), "Python 3.11 erforderlich"'
if [[ "$CPU" == "x64" ]]; then
  # cryptography 49 has no macOS Intel wheels. Build the pinned version with
  # statically linked OpenSSL so the recipient does not depend on Homebrew.
  BUILD_STEP="Intel-Build-Werkzeuge einrichten"
  "$BREW" install rust openssl@3 pkgconf
  export OPENSSL_DIR="$("$BREW" --prefix openssl@3)"
  export OPENSSL_STATIC=1
fi
BUILD_STEP="Projektabhängigkeiten einrichten"
.venv/bin/python -m pip install -r requirements.lock -r requirements-build.txt
npm ci

BUILD_STEP="Unveränderte Studienmethoden und öffentliche Referenzen laden"
STORYSCOPE_COMMIT=642e746804e1ee4138ffdcf13b7412eb3dc2a70b
if [[ ! -e vendor/storyscope ]]; then
  mkdir -p vendor
  git -c core.autocrlf=false clone --filter=blob:none --no-checkout https://github.com/jenna-russell/storyscope.git vendor/storyscope
  git -C vendor/storyscope checkout --detach "$STORYSCOPE_COMMIT"
fi
if [[ ! -e vendor/storyscope/.git ]] || \
   [[ "$(git -C vendor/storyscope rev-parse HEAD)" != "$STORYSCOPE_COMMIT" ]] || \
   [[ -n "$(git -C vendor/storyscope status --porcelain)" ]]; then
  printf 'StoryScope muss unverändert am dokumentierten Commit vorliegen. Lokale Änderungen werden nicht überschrieben.\n' >&2
  exit 1
fi
.venv/bin/python scripts/build_backend.py --assets-only

BUILD_STEP="Analyse und Berichte prüfen"
npm test
npm run test:comparisons
npm run test:pdf

BUILD_STEP="App und DMG für diesen Mac bauen"
npm run package:mac

BUILD_STEP="Eingebaute Laufzeit, App und DMG prüfen"
npm run test:runtime
npm run test:packaged
MAC_OUTPUT=mac
[[ "$CPU" != "arm64" ]] || MAC_OUTPUT=mac-arm64
codesign --verify --deep --strict --verbose=2 "release/$MAC_OUTPUT/Bookalyzer.app"
VERSION="$(node -p "require('./package.json').version")"
DMG_NAME="Bookalyzer-$VERSION-mac-$CPU.dmg"
hdiutil verify "release/$DMG_NAME"
(
  cd release
  shasum -a 256 "$DMG_NAME" > "$DMG_NAME.sha256"
)
printf '\nFertig: %s/release/%s\n' "$PROJECT_DIR" "$DMG_NAME"
printf 'Diese DMG reicht zur Weitergabe an Macs mit derselben Prozessorfamilie und macOS 14+.\n'
printf 'DMG öffnen → Bookalyzer nach Programme ziehen → starten.\n'
printf 'Beim ersten Start ggf. Systemeinstellungen → Datenschutz & Sicherheit → Dennoch öffnen.\n'
open -R "$PROJECT_DIR/release/$DMG_NAME"
