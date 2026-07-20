import { randomUUID } from "node:crypto";
import { chmodSync, existsSync, mkdirSync, readFileSync, renameSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { getAgentDir } from "@earendil-works/pi-coding-agent";
import type { ExtensionContext } from "@earendil-works/pi-coding-agent";
import type { BraveAuthStorage, RuntimeState } from "./types.js";

export const BRAVE_ENV_VAR = "BRAVE_SEARCH_API_KEY";
export const BRAVE_AUTH_PATH = join(getAgentDir(), "web-search", "auth.json");

export interface BraveAuthStatus {
  envConfigured: boolean;
  authConfigured: boolean;
  activeSource: "env" | "auth.json" | "none";
}

interface BraveAuthFile {
  api_key?: unknown;
}

class FileBraveAuthStorage implements BraveAuthStorage {
  private apiKey: string | undefined;

  constructor(private readonly path: string) {
    this.reload();
  }

  reload(): void {
    if (!existsSync(this.path)) {
      this.apiKey = undefined;
      return;
    }

    const parsed = JSON.parse(readFileSync(this.path, "utf8")) as BraveAuthFile;
    this.apiKey = normalizeSecret(parsed.api_key);
  }

  hasApiKey(): boolean {
    return this.apiKey !== undefined;
  }

  getApiKey(): string | undefined {
    return this.apiKey;
  }

  setApiKey(apiKey: string): void {
    const directory = dirname(this.path);
    const tempPath = join(directory, `.auth-${process.pid}-${randomUUID()}.tmp`);
    mkdirSync(directory, { recursive: true, mode: 0o700 });
    chmodSync(directory, 0o700);

    try {
      const payload = `${JSON.stringify({ api_key: apiKey }, null, 2)}\n`;
      writeFileSync(tempPath, payload, { encoding: "utf8", flag: "wx", mode: 0o600 });
      renameSync(tempPath, this.path);
      chmodSync(this.path, 0o600);
      this.apiKey = apiKey;
    } finally {
      rmSync(tempPath, { force: true });
    }
  }

  clear(): void {
    rmSync(this.path, { force: true });
    this.apiKey = undefined;
  }
}

export function createAuthStorage(): BraveAuthStorage {
  return new FileBraveAuthStorage(BRAVE_AUTH_PATH);
}

export function getBraveAuthStatus(authStorage: BraveAuthStorage): BraveAuthStatus {
  const envConfigured = Boolean(normalizeSecret(process.env[BRAVE_ENV_VAR]));
  const authConfigured = authStorage.hasApiKey();

  return {
    envConfigured,
    authConfigured,
    activeSource: envConfigured ? "env" : authConfigured ? "auth.json" : "none",
  };
}

export async function resolveBraveApiKey(
  authStorage: BraveAuthStorage,
  ctx: ExtensionContext | undefined,
  runtime: RuntimeState,
): Promise<string | undefined> {
  authStorage.reload();

  const envKey = normalizeSecret(process.env[BRAVE_ENV_VAR]);
  if (envKey) {
    return envKey;
  }

  const savedKey = normalizeSecret(authStorage.getApiKey());
  if (savedKey) {
    return savedKey;
  }

  await maybePromptForBraveSetup(authStorage, ctx, runtime);

  const envKeyAfterPrompt = normalizeSecret(process.env[BRAVE_ENV_VAR]);
  if (envKeyAfterPrompt) {
    return envKeyAfterPrompt;
  }

  return normalizeSecret(authStorage.getApiKey());
}

export function setBraveApiKey(authStorage: BraveAuthStorage, apiKey: string): void {
  const normalized = normalizeSecret(apiKey);
  if (!normalized) {
    throw new Error("Brave Search API key must not be empty.");
  }

  authStorage.setApiKey(normalized);
}

export function clearBraveApiKey(authStorage: BraveAuthStorage): void {
  authStorage.clear();
}

export function formatBraveAuthStatus(authStorage: BraveAuthStorage): string {
  const status = getBraveAuthStatus(authStorage);

  return [
    "web-search auth",
    `- ${BRAVE_ENV_VAR}: ${status.envConfigured ? "configured" : "not configured"}`,
    `- ${BRAVE_AUTH_PATH}: ${status.authConfigured ? "configured" : "not configured"}`,
    `- active source: ${status.activeSource}`,
  ].join("\n");
}

export function missingBraveKeySetupHint(): string {
  return [
    "Brave Search API key is not configured.",
    `Set ${BRAVE_ENV_VAR} or use /web-search-setup to save the key in ${BRAVE_AUTH_PATH}.`,
  ].join(" ");
}

export async function runInteractiveBraveSetup(
  authStorage: BraveAuthStorage,
  ctx: ExtensionContext,
  runtime: RuntimeState,
): Promise<string> {
  const status = getBraveAuthStatus(authStorage);
  const saveLabel = status.authConfigured ? "Replace saved key" : "Save key";
  const choice = await ctx.ui.select("Configure Brave Search", [
    saveLabel,
    "Use environment variable instead",
    "Not now",
  ]);

  runtime.braveSetupPromptShown = true;

  if (!choice || choice === "Not now") {
    return "Brave Search setup skipped. web_search will use fallback backends when possible.";
  }

  if (choice === "Use environment variable instead") {
    return [
      `Set ${BRAVE_ENV_VAR} before starting pi, then restart pi.`,
      `Example: export ${BRAVE_ENV_VAR}=...`,
      `Or save the key in ${BRAVE_AUTH_PATH} via /web-search-setup.`,
    ].join("\n");
  }

  const prompt = status.authConfigured
    ? `Enter the new Brave Search API key (visible locally while typing) to save in ${BRAVE_AUTH_PATH}`
    : `Enter the Brave Search API key (visible locally while typing) to save in ${BRAVE_AUTH_PATH}`;
  const value = await ctx.ui.input(prompt, "Paste API key here");
  const normalized = normalizeSecret(value);

  if (!normalized) {
    return "Brave Search setup canceled. No key was saved.";
  }

  setBraveApiKey(authStorage, normalized);
  return `Saved Brave Search API key in ${BRAVE_AUTH_PATH}. The file is kept outside projects with owner-only permissions.`;
}

async function maybePromptForBraveSetup(
  authStorage: BraveAuthStorage,
  ctx: ExtensionContext | undefined,
  runtime: RuntimeState,
): Promise<void> {
  if (!ctx?.hasUI || runtime.braveSetupPromptShown) {
    return;
  }

  const status = getBraveAuthStatus(authStorage);
  if (status.activeSource !== "none") {
    return;
  }

  const message = await runInteractiveBraveSetup(authStorage, ctx, runtime);
  ctx.ui.notify(message, "info");
}

function normalizeSecret(value: unknown): string | undefined {
  if (typeof value !== "string") {
    return undefined;
  }

  const normalized = value.trim();
  return normalized.length > 0 ? normalized : undefined;
}
