#!/usr/bin/env bash
# Builds the EasyEDA bridge extension (.eext) of easyeda-mcp-pro with a deeper return depth for easyeda_api_call, a
# vector schematic PDF export and the ODB++ export for the tool easyeda_export_odb (odb-tool-patch.mjs).
#
# The original extension cuts every API answer after 5 levels ("[MaxDepth]"). DRC details (PCB_Drc.check(…, true))
# and the rule configuration are unreadable that way. Neither the server nor the extension has a setting for it; the
# value is fixed in the bundle (dist/index.js, methods apiCall and apiExecute). This script replaces it. It also makes
# easyeda_export_pdf with scope=schematic export the active schematic as a vector PDF.
#
#   bridge-extension-patch.sh                  -> depth 12, writes ./easyeda-bridge-extension.eext
#   bridge-extension-patch.sh 16 /tmp/x.eext   -> other depth, other target
#
# Then, in EasyEDA: uninstall the old MCP Pro Bridge, import the .eext (extension manager), restart EasyEDA.
# Run again after every update of easyeda-mcp-pro (EASYEDA_MCP_VERSION in mcp-server.sh).
set -euo pipefail

DEPTH="${1:-12}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="$(realpath -m "${2:-$PWD/easyeda-bridge-extension.eext}")"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

"$HERE/mcp-server.sh" extension --copy "$WORK" >&2
SOURCE="$(ls "$WORK"/*.eext)"
mkdir "$WORK/x"
unzip -q "$SOURCE" -d "$WORK/x"

BUNDLE="$WORK/x/dist/index.js"
COUNT="$(grep -c 'result: normalizeValue(result, 5)' "$BUNDLE" || true)"
if [ "$COUNT" != "2" ]; then
  echo "Expected 2 places 'result: normalizeValue(result, 5)' in dist/index.js, found: $COUNT." >&2
  echo "The extension has changed – review the patch." >&2
  exit 1
fi
sed -i "s/result: normalizeValue(result, 5)/result: normalizeValue(result, $DEPTH)/" "$BUNDLE"

# Schematic as vector PDF: exportPdf always calls the first available function (PCB_ManufactureData.getPdfFile), so a
# schematic yields nothing. With scope=schematic call SCH_ManufactureData.getExportDocumentFile(name, "PDF") instead –
# it exports the active schematic (EasyEDA Pro 3.2.206, parameters read from the editor bundle).
COUNT="$(grep -c 'async function exportPdf(params) {' "$BUNDLE" || true)"
if [ "$COUNT" != "1" ]; then
  echo "Expected 1 place 'async function exportPdf(params) {' in dist/index.js, found: $COUNT." >&2
  exit 1
fi
sed -i 's/async function exportPdf(params) {/&\n      if (params.what === "schematic") return normalizeBinaryResult2(await callFirst2(["SCH_ManufactureData.getExportDocumentFile"], void 0, "PDF"), "schematic.pdf");/' "$BUNDLE"
# ODB++ for a maker that assembles from it (edakit handbook 8.4, F-7): the server's tool easyeda_export_odb calls
# board.exportGerbers with format "odb" – answer it with PCB_ManufactureData.getOpenDatabaseDoublePlusFile(fileName,
# unit, otherData) (BETA in EasyEDA Pro's API), marked format "odb" so that the tool can tell it from a Gerber ZIP.
COUNT="$(grep -c 'async function exportGerbers(params) {' "$BUNDLE" || true)"
if [ "$COUNT" != "1" ]; then
  echo "Expected 1 place 'async function exportGerbers(params) {' in dist/index.js, found: $COUNT." >&2
  exit 1
fi
sed -i 's/async function exportGerbers(params) {/&\n      if (params.format === "odb") return { ...(await normalizeBinaryResult2(await callFirst2(["PCB_ManufactureData.getOpenDatabaseDoublePlusFile"], params.fileName, params.unit, params.otherData), "odb.zip")), format: "odb" };/' "$BUNDLE"
node --check "$BUNDLE" || { echo "dist/index.js does not parse after the patch." >&2; exit 1; }

# Recognisable in the extension manager. Same UUID and version: EasyEDA does not take a new import over an installed
# copy, so uninstall the old extension first.
NAME="MCP Pro Bridge (depth $DEPTH, schematic PDF, ODB++)"
sed -i "s/\"displayName\": \"MCP Pro Bridge\"/\"displayName\": \"$NAME\"/" "$WORK/x/extension.json"
grep -q "$NAME" "$WORK/x/extension.json" || { echo "displayName not found in extension.json." >&2; exit 1; }

rm -f "$TARGET"
(cd "$WORK/x" && zip -q -X -D -r "$TARGET" .)
echo "Written: $TARGET ($NAME). In EasyEDA: uninstall the old MCP Pro Bridge, import this file, restart EasyEDA." >&2
