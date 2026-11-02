// The client of the circuit language's server (handbook 19): it starts `edakit lsp`, which answers errors, findings,
// go to definition, hover, completion and formatting; the commands run edakit's graph actions in a terminal.
import * as path from "path";
import * as vscode from "vscode";
import { LanguageClient, LanguageClientOptions, ServerOptions } from "vscode-languageclient/node";

let client: LanguageClient | undefined;

function command(): string {
  return vscode.workspace.getConfiguration("edakit").get<string>("command", "edakit");
}

// The folder of the edakit.toml above the file: edakit's commands run there.
function projectOf(file: string): string {
  let dir = path.dirname(file);
  const fs = require("fs") as typeof import("fs");
  for (;;) {
    if (fs.existsSync(path.join(dir, "edakit.toml"))) {
      return dir;
    }
    const up = path.dirname(dir);
    if (up === dir) {
      return path.dirname(file);
    }
    dir = up;
  }
}

function run(args: string[]): void {
  const editor = vscode.window.activeTextEditor;
  const cwd = editor ? projectOf(editor.document.uri.fsPath) : undefined;
  const terminal = vscode.window.createTerminal({ name: "edakit", cwd });
  terminal.show();
  terminal.sendText([command(), ...args].map((a) => (/\s/.test(a) ? `"${a}"` : a)).join(" "));
}

function wordAtCursor(): string | undefined {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    return undefined;
  }
  const range = editor.document.getWordRangeAtPosition(editor.selection.active, /[^\s"#.]+/);
  return range ? editor.document.getText(range) : undefined;
}

export function activate(context: vscode.ExtensionContext): void {
  const server: ServerOptions = { command: command(), args: ["lsp"] };
  const options: LanguageClientOptions = { documentSelector: [{ scheme: "file", language: "circuit" }] };
  client = new LanguageClient("edakit-circuit", "edakit circuit language", server, options);
  void client.start();
  context.subscriptions.push(
    vscode.commands.registerCommand("edakit.graphJson", () => run(["graph", "json", "--write"])),
    vscode.commands.registerCommand("edakit.graphCheck", () => run(["graph", "json", "--check"])),
    vscode.commands.registerCommand("edakit.fmt", () => run(["graph", "fmt"])),
    vscode.commands.registerCommand("edakit.graphShow", () => {
      const word = wordAtCursor();
      if (word) {
        run(["graph", "show", word]);
      }
    }),
    vscode.tasks.registerTaskProvider("edakit", {
      provideTasks: () =>
        ["json", "check"].map((action) => {
          const args = ["graph", "json", action === "json" ? "--write" : "--check"];
          return new vscode.Task({ type: "edakit", action }, vscode.TaskScope.Workspace, `graph json ${args[2]}`,
            "edakit", new vscode.ShellExecution(command(), args));
        }),
      resolveTask: () => undefined,
    }),
  );
}

export function deactivate(): Thenable<void> | undefined {
  return client ? client.stop() : undefined;
}
