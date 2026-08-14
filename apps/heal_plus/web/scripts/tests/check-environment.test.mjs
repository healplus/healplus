import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import {
  formatEnvironmentIssues,
  parseDotEnv,
  satisfiesMinimumVersion,
  validatePublicEnvironment,
} from "../check-environment.mjs";

const scriptsDirectory = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = resolve(scriptsDirectory, "..");
const scriptPath = resolve(scriptsDirectory, "check-environment.mjs");

test("parses dotenv values without treating inline comments as values", () => {
  assert.deepEqual(
    parseDotEnv(`
# comment
VITE_SUPABASE_URL=https://example.supabase.co # public URL
export VITE_SUPABASE_ANON_KEY="sb_publishable_synthetic"
VITE_MAX_IMAGE_UPLOAD_MB='12'
`),
    {
      VITE_SUPABASE_URL: "https://example.supabase.co",
      VITE_SUPABASE_ANON_KEY: "sb_publishable_synthetic",
      VITE_MAX_IMAGE_UPLOAD_MB: "12",
    },
  );
});

test("compares Node.js versions against the package engine floor", () => {
  assert.equal(satisfiesMinimumVersion("22.22.0", ">=22.22.0"), true);
  assert.equal(satisfiesMinimumVersion("24.1.0", ">=22.22.0"), true);
  assert.equal(satisfiesMinimumVersion("22.21.9", ">=22.22.0"), false);
});

test("validates public variables without placing their values in messages", () => {
  const sensitiveValue = "service_role_synthetic_should_never_be_printed";
  const result = validatePublicEnvironment(
    {
      VITE_SUPABASE_URL: "not-a-url",
      VITE_SUPABASE_ANON_KEY: sensitiveValue,
      VITE_MAX_IMAGE_UPLOAD_MB: "zero",
    },
    "a synthetic environment",
  );
  const output = formatEnvironmentIssues(result.issues).join("\n");

  assert.equal(result.issues.length, 3);
  assert.equal(output.includes(sensitiveValue), false);
  assert.match(output, /VITE_SUPABASE_ANON_KEY/u);
});

test("runs successfully in CI mode with synthetic public configuration", () => {
  const result = spawnSync(process.execPath, [scriptPath, "--ci"], {
    cwd: repositoryRoot,
    encoding: "utf8",
    env: {
      ...process.env,
      VITE_SUPABASE_URL: "https://example.supabase.co",
      VITE_SUPABASE_ANON_KEY: "sb_publishable_ci_synthetic",
      VITE_MAX_IMAGE_UPLOAD_MB: "10",
    },
  });

  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /Environment check passed/u);
  assert.equal(result.stdout.includes("sb_publishable_ci_synthetic"), false);
});

test("fails with actionable variable names and redacts invalid values", () => {
  const invalidValue = "service_role_synthetic_secret";
  const result = spawnSync(process.execPath, [scriptPath, "--ci"], {
    cwd: repositoryRoot,
    encoding: "utf8",
    env: {
      ...process.env,
      VITE_SUPABASE_URL: "invalid",
      VITE_SUPABASE_ANON_KEY: invalidValue,
      VITE_MAX_IMAGE_UPLOAD_MB: "-1",
    },
  });
  const output = `${result.stdout}\n${result.stderr}`;

  assert.equal(result.status, 1);
  assert.match(output, /VITE_SUPABASE_URL/u);
  assert.match(output, /VITE_SUPABASE_ANON_KEY/u);
  assert.equal(output.includes(invalidValue), false);
});
