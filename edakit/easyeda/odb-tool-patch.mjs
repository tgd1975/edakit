#!/usr/bin/env node
// Adds the MCP tool easyeda_export_odb to the pinned easyeda-mcp-pro (dist/tools/L1_export.js): EasyEDA Pro's ODB++
// export (PCB_ManufactureData.getOpenDatabaseDoublePlusFile, BETA in its extension API) for a maker that assembles from
// ODB++ – AISLER (edakit handbook 8.4, check F-7).
//
// The tool calls the bridge method board.exportGerbers with format "odb": a method the server already knows, so its
// method registry – and the registry hash it sends the bridge – stay as they are. The bridge extension built by
// bridge-extension-patch.sh answers it with the ODB++ file, marked format "odb"; an extension without that handler
// answers with the Gerber ZIP, unmarked, and the tool refuses it.
//
//   node odb-tool-patch.mjs <runtime>/node_modules/easyeda-mcp-pro/dist/tools/L1_export.js
//
// mcp-server.sh runs it after installing the pinned server. A patched file is left as it is. Writes nothing to stdout:
// the server speaks MCP there.
import fs from 'node:fs';

const file = process.argv[2];
const ANCHOR = "    registry.register({\n        name: 'easyeda_export_pdf',";
const MARK = "name: 'easyeda_export_odb'";
const TOOL = `    registry.register({
        name: 'easyeda_export_odb',
        title: 'Export ODB++',
        description: 'Export the PCB as ODB++ (EasyEDA Pro PCB_ManufactureData.getOpenDatabaseDoublePlusFile): board, parts and placement in one archive, for a maker that assembles from ODB++. Needs the bridge extension with the ODB++ handler (edakit bridge-extension-patch.sh). Patched in by edakit (odb-tool-patch.mjs).',
        profile: 'core',
        evidence: ['official-docs'],
        risk: 'medium',
        confirmWrite: false,
        sideEffect: 'artifact-write',
        group: 'export',
        version: '1.0.0',
        annotations: {
            readOnlyHint: false,
            destructiveHint: false,
            idempotentHint: true,
        },
        inputSchema: z.object({
            projectId: z.string().trim().min(1),
            filePath: z.string().optional(),
            unit: z.enum(['mm', 'inch']).default('mm'),
            platedHoles: z.boolean().default(true),
            nonPlatedHoles: z.boolean().default(true),
        }),
        outputSchema: z.object({
            project_id: z.string(),
            artifact_path: z.string().optional(),
            byte_length: z.number().int().nonnegative().optional(),
            exported: z.boolean(),
            not_available: z.boolean().optional(),
            error: z.string().optional(),
        }),
        handler: async (ctx, params) => {
            const { projectId, filePath, unit, platedHoles, nonPlatedHoles } = params;
            try {
                const result = await ctx.bridge.call('board.exportGerbers', {
                    projectId,
                    format: 'odb',
                    unit,
                    otherData: {
                        metallizedDrilledHoles: platedHoles,
                        nonMetallizedDrilledHoles: nonPlatedHoles,
                        drillTable: false,
                        flyingProbeTestFile: false,
                    },
                });
                if (!result || result.format !== 'odb' || typeof result.base64 !== 'string') {
                    return {
                        project_id: projectId,
                        exported: false,
                        not_available: true,
                        error: 'Bridge did not return an ODB++ archive – the extension needs the ODB++ handler (edakit bridge-extension-patch.sh)',
                    };
                }
                const head = Buffer.from(result.base64, 'base64').subarray(0, 2);
                if (!((head[0] === 0x50 && head[1] === 0x4b) || (head[0] === 0x1f && head[1] === 0x8b))) {
                    return { project_id: projectId, exported: false, not_available: true, error: 'ODB++ export is neither a zip nor a tgz archive' };
                }
                const written = writeExportPayload(ctx, result, filePath, \`\${projectId}-odb.zip\`);
                if (!written.ok) {
                    return { project_id: projectId, exported: false, not_available: true, error: written.error };
                }
                return { project_id: projectId, artifact_path: written.filePath, byte_length: written.byteLength, exported: true };
            }
            catch (err) {
                return { project_id: projectId, exported: false, not_available: true, error: err instanceof Error ? err.message : String(err) };
            }
        },
    });
`;

if (!file || !fs.existsSync(file)) {
  console.error(`odb-tool-patch: ${file || '(no file given)'} not found`);
  process.exit(1);
}
let text = fs.readFileSync(file, 'utf8');
if (text.includes(MARK)) process.exit(0);
const places = text.split(ANCHOR).length - 1;
if (places !== 1 || !text.includes('function writeExportPayload(')) {
  console.error(`odb-tool-patch: expected the tool easyeda_export_pdf once and writeExportPayload in ${file}, found the ` +
                `tool ${places}x – the server has changed, review the patch`);
  process.exit(1);
}
text = text.replace(ANCHOR, TOOL + ANCHOR);
fs.writeFileSync(file, text);
console.error(`odb-tool-patch: easyeda_export_odb added to ${file}`);
