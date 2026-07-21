import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import type { TSchema } from "typebox";

const core = fileURLToPath(new URL("../../bin/task-core", import.meta.url));
const contractsPath = fileURLToPath(new URL("../../contracts/task-tools.schema.json", import.meta.url));
const contracts = JSON.parse(readFileSync(contractsPath, "utf8")) as Record<string, TSchema>;

async function invoke(operation: string, request: Record<string, unknown>, cwd: string, signal?: AbortSignal) {
  return await new Promise<Record<string, unknown>>((resolve, reject) => {
    const child = spawn(core, ["invoke", operation], {
      cwd,
      stdio: ["pipe", "pipe", "pipe"],
      env: { ...process.env, TASK_HOST: "pi" },
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => (stdout += chunk));
    child.stderr.on("data", (chunk) => (stderr += chunk));
    signal?.addEventListener("abort", () => child.kill("SIGTERM"), { once: true });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(`task-core protocol failure (${code}): ${stderr.trim()}`));
        return;
      }
      try {
        resolve(JSON.parse(stdout) as Record<string, unknown>);
      } catch (error) {
        reject(new Error(`task-core returned invalid JSON: ${String(error)}; ${stderr.trim()}`));
      }
    });
    child.stdin.end(JSON.stringify(request));
  });
}

function result(value: Record<string, unknown>) {
  return { content: [{ type: "text" as const, text: JSON.stringify(value, null, 2) }], details: value };
}

const labels: Record<string, string> = {
  task_find: "Find Task",
  task_read: "Read Task",
  task_create: "Create Task",
  task_update: "Update Task",
  task_log: "Log Task Activity",
};

const descriptions: Record<string, string> = {
  task_find: "Find existing project Tasks without loading full context.",
  task_read: "Read one Task as metadata, summary, or detailed context.",
  task_create: "Create one confirmed top-level Task or 1-50 subtasks.",
  task_update: "Apply a semantic Task patch and at most one lifecycle action.",
  task_log: "Append one durable work activity entry to a Task WAL.",
};

export default function (pi: ExtensionAPI) {
  for (const name of Object.keys(contracts)) {
    pi.registerTool({
      name,
      label: labels[name],
      description: descriptions[name],
      parameters: contracts[name],
      async execute(_id, params, signal, _update, ctx) {
        return result(await invoke(name, params, ctx.cwd, signal));
      },
    });
  }
}
