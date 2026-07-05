import { spawn, spawnSync } from "node:child_process";
import { existsSync, rmSync, readFileSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const port = String(process.env.PORT ?? "3030");
const baseUrl = process.env.PLAYWRIGHT_BASE_URL ?? `http://localhost:${port}`;
const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\..+/, "Z");
const outDir = path.resolve(
  packageRoot,
  process.env.OUT_DIR ?? path.join("output", "playwright", `replica-local-fresh-smoke-${stamp}`)
);

function run(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: packageRoot,
      stdio: "inherit",
      env: { ...process.env, ...options.env }
    });
    child.on("exit", (code) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`${command} ${args.join(" ")} exited with ${code}`));
      }
    });
    child.on("error", reject);
  });
}

function portPids(targetPort) {
  const result = spawnSync("lsof", [`-tiTCP:${targetPort}`, "-sTCP:LISTEN"], {
    cwd: packageRoot,
    encoding: "utf8"
  });
  if (result.status !== 0 && !result.stdout) return [];
  return result.stdout.split(/\s+/).filter(Boolean);
}

async function wait(ms) {
  await new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

async function stopPort(targetPort) {
  const pids = portPids(targetPort);
  for (const pid of pids) {
    process.kill(Number(pid), "SIGTERM");
  }
  for (let attempt = 0; attempt < 20; attempt += 1) {
    if (portPids(targetPort).length === 0) return;
    await wait(250);
  }
  for (const pid of portPids(targetPort)) {
    process.kill(Number(pid), "SIGKILL");
  }
}

async function waitForHealth(url) {
  const deadline = Date.now() + 120_000;
  let lastError = "";
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url, { method: "HEAD" });
      if (response.ok) return;
      lastError = `HTTP ${response.status}`;
    } catch (error) {
      lastError = String(error?.message ?? error);
    }
    await wait(1000);
  }
  throw new Error(`Timed out waiting for ${url}: ${lastError}`);
}

function startDevServer() {
  return spawn("corepack", ["pnpm", "exec", "next", "dev", "--port", port], {
    cwd: packageRoot,
    stdio: "inherit",
    env: process.env
  });
}

async function writeSummary(status, error) {
  const interactionJson = path.join(outDir, "local-interaction-script.json");
  const interaction = existsSync(interactionJson)
    ? JSON.parse(readFileSync(interactionJson, "utf8"))
    : null;
  const summary = {
    task: "replica-local-fresh-smoke",
    status,
    baseUrl,
    outDir,
    boundaries: {
      evidence_grade: "local_validation",
      production_write: false,
      provider_call: false,
      backend_write: false
    },
    interaction_steps: interaction?.steps?.length ?? 0,
    interaction_failures: interaction?.steps?.filter((step) => step.status !== "ok").length ?? null,
    error: error ? String(error?.message ?? error) : null,
    completed_at: new Date().toISOString()
  };
  await mkdir(outDir, { recursive: true });
  await writeFile(path.join(outDir, "smoke-summary.json"), JSON.stringify(summary, null, 2), "utf8");
  console.log(JSON.stringify(summary, null, 2));
}

async function main() {
  process.chdir(packageRoot);
  await mkdir(outDir, { recursive: true });
  await stopPort(port);
  rmSync(path.join(packageRoot, ".next"), { recursive: true, force: true });

  const server = startDevServer();
  let failed = null;
  try {
    await waitForHealth(`${baseUrl}/login`);
    const commonEnv = {
      PLAYWRIGHT_BASE_URL: baseUrl,
      LOCAL_URL: baseUrl,
      OUT_DIR: outDir,
      PLAYWRIGHT_USE_SYSTEM_CHROME: process.env.PLAYWRIGHT_USE_SYSTEM_CHROME ?? "1"
    };
    await run("node", ["scripts/run-replica-interaction-smoke.mjs"], { env: commonEnv });
    await run(
      "corepack",
      [
        "pnpm",
        "exec",
        "playwright",
        "test",
        "tests/e2e/interaction-contract.spec.ts",
        "tests/e2e/foundation.spec.ts",
        "--project=chromium",
        "--workers=1"
      ],
      {
        env: {
          ...commonEnv,
          PLAYWRIGHT_REUSE_SERVER: "1"
        }
      }
    );
  } catch (error) {
    failed = error;
  } finally {
    server.kill("SIGTERM");
    await stopPort(port);
  }

  await writeSummary(failed ? "failed" : "passed", failed);
  if (failed) throw failed;
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
