#!/usr/bin/env node

import fs from "node:fs";
import os from "node:os";
import path from "node:path";

function readStdin() {
  return new Promise((resolve, reject) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => {
      data += chunk;
    });
    process.stdin.on("end", () => resolve(data));
    process.stdin.on("error", reject);
  });
}

function emit(result) {
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
}

function fallback(status, summary, evidence = {}) {
  return {
    status,
    summary,
    tasks: [],
    evidence
  };
}

function classifyCodexError(error) {
  const message = String(error);
  const lower = message.toLowerCase();
  if (lower.includes("quota exceeded") || lower.includes("billing")) {
    return {
      status: "blocked",
      summary: "Codex SDK is unavailable because the API quota or billing limit was reached.",
      evidence: { error: message, error_kind: "quota_exceeded" }
    };
  }
  if (lower.includes("404") && lower.includes("/responses")) {
    return {
      status: "blocked",
      summary: "Codex SDK is unavailable because the Responses API endpoint was rejected by the configured base URL.",
      evidence: { error: message, error_kind: "responses_endpoint_unavailable" }
    };
  }
  if (
    lower.includes("unauthorized") ||
    lower.includes("invalid api key") ||
    lower.includes("authentication") ||
    lower.includes("credentials")
  ) {
    return {
      status: "blocked",
      summary: "Codex SDK is unavailable because authentication failed.",
      evidence: { error: message, error_kind: "auth_failed" }
    };
  }
  if (
    lower.includes("enotfound") ||
    lower.includes("econnrefused") ||
    lower.includes("econnreset") ||
    lower.includes("timeout")
  ) {
    return {
      status: "blocked",
      summary: "Codex SDK is unavailable because the API connection failed.",
      evidence: { error: message, error_kind: "connection_failed" }
    };
  }
  return {
    status: "failed",
    summary: "Codex SDK decision worker crashed.",
    evidence: { error: message, error_kind: "worker_crash" }
  };
}

function parseJsonObject(text) {
  try {
    return JSON.parse(text);
  } catch {
    const fenced = text.match(/```(?:json)?\s*([\s\S]*?)\s*```/);
    if (fenced) {
      return JSON.parse(fenced[1]);
    }
    const first = text.indexOf("{");
    const last = text.lastIndexOf("}");
    if (first >= 0 && last > first) {
      return JSON.parse(text.slice(first, last + 1));
    }
    throw new Error("No JSON object found");
  }
}

function copyFileIfPresent(source, destination) {
  if (!fs.existsSync(source)) {
    return;
  }
  fs.copyFileSync(source, destination);
  fs.chmodSync(destination, 0o600);
}

function prepareWritableCodexHome() {
  const sourceHome = process.env.PENTEST_CODEX_SOURCE_HOME || path.join(os.homedir(), ".codex");
  const uid = typeof process.getuid === "function" ? process.getuid() : "user";
  const codexHome = process.env.PENTEST_CODEX_HOME || path.join(os.tmpdir(), `pentestagent-codex-home-${uid}`);
  fs.mkdirSync(codexHome, { recursive: true, mode: 0o700 });
  fs.mkdirSync(path.join(codexHome, "sessions"), { recursive: true, mode: 0o700 });
  fs.mkdirSync(path.join(codexHome, "tmp"), { recursive: true, mode: 0o700 });
  fs.mkdirSync(path.join(codexHome, "cache"), { recursive: true, mode: 0o700 });
  copyFileIfPresent(path.join(sourceHome, "auth.json"), path.join(codexHome, "auth.json"));
  copyFileIfPresent(path.join(sourceHome, "config.toml"), path.join(codexHome, "config.toml"));
  copyFileIfPresent(path.join(sourceHome, "installation_id"), path.join(codexHome, "installation_id"));
  return codexHome;
}

function normalizeResponsesBaseUrl(value) {
  if (!value) {
    return undefined;
  }
  const parsed = new URL(value);
  parsed.pathname = parsed.pathname.replace(/\/+$/, "");
  if (parsed.pathname.endsWith("/chat/completions")) {
    parsed.pathname = parsed.pathname.slice(0, -"/chat/completions".length);
  }
  if (!parsed.pathname.endsWith("/v1")) {
    parsed.pathname = `${parsed.pathname}/v1`.replace(/\/{2,}/g, "/");
  }
  return parsed.toString().replace(/\/$/, "");
}

const API_ENV_KEYS = [
  "CODEX_API_KEY",
  "OPENAI_API_KEY",
  "CODEX_BASE_URL",
  "OPENAI_BASE_URL",
  "OPENAI_API_URL"
];

function buildCodexOptions(codexHome) {
  const useEnvApi = process.env.PENTEST_CODEX_USE_ENV_API === "1";
  const env = { ...process.env, CODEX_HOME: codexHome, TMPDIR: os.tmpdir() };
  const options = {
    env,
    config: {
      sandbox_workspace_write: {
        network_access: true
      },
      approval_policy: "never"
    }
  };

  if (useEnvApi) {
    const apiKey = process.env.CODEX_API_KEY || process.env.OPENAI_API_KEY;
    const baseUrl = normalizeResponsesBaseUrl(process.env.CODEX_BASE_URL || process.env.OPENAI_BASE_URL || process.env.OPENAI_API_URL);
    if (apiKey) {
      options.apiKey = apiKey;
    }
    if (baseUrl) {
      options.baseUrl = baseUrl;
    }
    return options;
  }

  for (const key of API_ENV_KEYS) {
    delete env[key];
    delete process.env[key];
  }
  process.env.CODEX_HOME = codexHome;
  process.env.TMPDIR = os.tmpdir();
  return options;
}

const input = JSON.parse(await readStdin());

let Codex;
try {
  ({ Codex } = await import("@openai/codex-sdk"));
} catch (error) {
  emit(fallback("blocked", "Codex SDK package is not installed or cannot be imported.", {
    error: String(error),
    install: "npm install"
  }));
  process.exit(0);
}

const prompt = `
You are a Codex SDK decision coordinator for an authorized pentest lab run.

Return exactly one JSON object matching:
{
  "tasks": [
    {
      "task_id": "stable-short-id",
      "target_ip": "target",
      "service_name": "service",
      "port": 80,
      "cve_id": null,
      "cve_ids": [],
      "objective": "what the next worker should prove or disprove",
      "hypothesis": "short reason this path is worth testing",
      "confidence_score": 1,
      "context_snippets": ["only context directly needed for this task"],
      "evidence_refs": ["artifact path, URL, or command output reference"],
      "success_criteria": ["specific evidence that should end this task"],
      "max_steps": 3,
      "memory_key": "stable memory id"
    }
  ]
}

Rules:
- Use the normalized recon report, service_analysis, snippets, and prior results.
- Use vulnerability_candidates when present. They come from recon-derived local search/tool results such as searchsploit.
- If vulnerability_candidates contains cve_ids relevant to a service, create a CVE-scoped task and copy those CVE IDs into cve_ids.
- If a vulnerability candidate has no CVE ID but has a plausible exploit title/path, include that title/path in context_snippets and evidence_refs so the Codex worker receives it.
- Prefer high-signal tasks, but do not ignore lower-priority ports when they may be related.
- Prioritize web follow-up on nonstandard web ports when service_analysis recommends it.
- Avoid repeating previous failed or low-value attempts.
- Do not include raw commands; downstream exploit workers propose commands.
- Return valid JSON only. Do not include markdown.

Decision input:
${JSON.stringify(input, null, 2)}
`;

try {
  const codexHome = prepareWritableCodexHome();
  const codex = new Codex(buildCodexOptions(codexHome));
  const thread = codex.startThread({
    workingDirectory: process.cwd(),
    sandboxMode: "workspace-write",
    skipGitRepoCheck: true,
    networkAccessEnabled: true,
    approvalPolicy: "never"
  });
  const turn = await thread.run(prompt);
  const parsed = parseJsonObject(turn.finalResponse || "");
  emit({
    tasks: Array.isArray(parsed.tasks) ? parsed.tasks : [],
    evidence: {
      codex_items: turn.items || []
    }
  });
} catch (error) {
  const classified = classifyCodexError(error);
  emit(fallback(classified.status, classified.summary, classified.evidence));
}
