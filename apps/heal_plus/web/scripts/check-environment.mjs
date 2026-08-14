import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const DEFAULT_ENV_FILE = ".env";
const PUBLIC_ENV_NAMES = [
  "VITE_SUPABASE_URL",
  "VITE_SUPABASE_ANON_KEY",
  "VITE_MAX_IMAGE_UPLOAD_MB",
];

export function parseDotEnv(content) {
  const values = {};

  for (const rawLine of content.split(/\r?\n/u)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;

    const normalized = line.startsWith("export ") ? line.slice(7).trim() : line;
    const separator = normalized.indexOf("=");
    if (separator < 1) continue;

    const name = normalized.slice(0, separator).trim();
    let value = normalized.slice(separator + 1).trim();
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/u.test(name)) continue;

    if (
      value.length >= 2 &&
      ((value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'")))
    ) {
      value = value.slice(1, -1);
    } else {
      value = value.replace(/\s+#.*$/u, "").trim();
    }

    values[name] = value;
  }

  return values;
}

export function extractMinimumVersion(requirement) {
  const match = requirement.match(/(\d+)\.(\d+)\.(\d+)/u);
  if (!match) throw new Error(`Unsupported Node.js engine requirement: ${requirement}`);
  return match.slice(1).map(Number);
}

export function satisfiesMinimumVersion(actualVersion, requirement) {
  const actual = actualVersion.split(".").slice(0, 3).map(Number);
  const minimum = extractMinimumVersion(requirement);

  for (let index = 0; index < minimum.length; index += 1) {
    if (actual[index] > minimum[index]) return true;
    if (actual[index] < minimum[index]) return false;
  }

  return true;
}

export function validatePublicEnvironment(environment, sourceLabel = DEFAULT_ENV_FILE) {
  const checks = [];
  const issues = [];
  const supabaseUrl = environment.VITE_SUPABASE_URL?.trim();
  const publishableKey = environment.VITE_SUPABASE_ANON_KEY?.trim();
  const uploadLimit = environment.VITE_MAX_IMAGE_UPLOAD_MB?.trim();

  if (!supabaseUrl) {
    issues.push({
      name: "VITE_SUPABASE_URL",
      message: `missing in ${sourceLabel}; define the public Supabase project URL`,
    });
  } else {
    try {
      const parsedUrl = new URL(supabaseUrl);
      if (!['http:', 'https:'].includes(parsedUrl.protocol) || !parsedUrl.hostname) {
        throw new Error("invalid public URL");
      }
      checks.push("VITE_SUPABASE_URL is configured as an HTTP(S) URL");
    } catch {
      issues.push({
        name: "VITE_SUPABASE_URL",
        message: `invalid in ${sourceLabel}; use the complete HTTP(S) project URL`,
      });
    }
  }

  if (!publishableKey) {
    issues.push({
      name: "VITE_SUPABASE_ANON_KEY",
      message: `missing in ${sourceLabel}; define an anon or publishable browser key`,
    });
  } else if (/service[_-]?role/iu.test(publishableKey)) {
    issues.push({
      name: "VITE_SUPABASE_ANON_KEY",
      message: `unsafe in ${sourceLabel}; never expose a service-role key in Vite`,
    });
  } else {
    checks.push("VITE_SUPABASE_ANON_KEY is configured with a public key");
  }

  if (!uploadLimit) {
    checks.push("VITE_MAX_IMAGE_UPLOAD_MB is omitted; the documented 10 MB default applies");
  } else if (!/^\d+(?:\.\d+)?$/u.test(uploadLimit) || Number(uploadLimit) <= 0) {
    issues.push({
      name: "VITE_MAX_IMAGE_UPLOAD_MB",
      message: `invalid in ${sourceLabel}; use a positive number of megabytes`,
    });
  } else {
    checks.push("VITE_MAX_IMAGE_UPLOAD_MB is configured with a positive number");
  }

  return { checks, issues };
}

export function formatEnvironmentIssues(issues) {
  return issues.map(({ name, message }) => `âœ— ${name}: ${message}`);
}

function parseArguments(argumentsList) {
  const options = { ci: false, envFile: DEFAULT_ENV_FILE, help: false };

  for (let index = 0; index < argumentsList.length; index += 1) {
    const argument = argumentsList[index];
    if (argument === "--ci") {
      options.ci = true;
    } else if (argument === "--help" || argument === "-h") {
      options.help = true;
    } else if (argument === "--env-file") {
      const value = argumentsList[index + 1];
      if (!value) throw new Error("--env-file requires a path");
      options.envFile = value;
      index += 1;
    } else {
      throw new Error(`Unknown option: ${argument}`);
    }
  }

  return options;
}

function printHelp() {
  console.log(`HEAL+ development environment verifier

Usage:
  npm run doctor
  npm run doctor -- --env-file path/to/.env
  npm run doctor -- --ci

Options:
  --env-file <path>  Read public Vite variables from a file (default: .env)
  --ci               Read public Vite variables from the CI process environment
  -h, --help         Show this help`);
}

export function runEnvironmentCheck(argumentsList = process.argv.slice(2)) {
  let options;
  try {
    options = parseArguments(argumentsList);
  } catch (error) {
    console.error(`âœ— ${error.message}`);
    console.error("Run `npm run doctor -- --help` for usage.");
    return 1;
  }

  if (options.help) {
    printHelp();
    return 0;
  }

  console.log("HEAL+ development environment check");
  const failures = [];
  const packageJson = JSON.parse(readFileSync(resolve("package.json"), "utf8"));
  const nodeRequirement = packageJson.engines?.node ?? ">=22.22.0";

  if (satisfiesMinimumVersion(process.versions.node, nodeRequirement)) {
    console.log(`âœ“ Node.js ${process.versions.node} satisfies ${nodeRequirement}`);
  } else {
    failures.push(
      `âœ— Node.js ${process.versions.node} does not satisfy ${nodeRequirement}; install Node.js 24 LTS`,
    );
  }

  const npmResult =
    process.platform === "win32"
      ? spawnSync(process.env.ComSpec ?? "cmd.exe", ["/d", "/s", "/c", "npm --version"], {
          encoding: "utf8",
        })
      : spawnSync("npm", ["--version"], { encoding: "utf8" });
  if (npmResult.status === 0 && npmResult.stdout.trim()) {
    console.log(`âœ“ npm ${npmResult.stdout.trim()} is available`);
  } else {
    failures.push("âœ— npm is unavailable; reinstall Node.js 24 LTS with npm included");
  }

  const sourceLabel = options.ci ? "the CI environment" : options.envFile;
  let fileEnvironment = {};
  if (!options.ci) {
    try {
      fileEnvironment = parseDotEnv(readFileSync(resolve(options.envFile), "utf8"));
      console.log(`âœ“ Loaded public configuration from ${options.envFile}`);
    } catch (error) {
      if (error?.code === "ENOENT") {
        failures.push(
          `âœ— ${options.envFile} was not found; copy .env.example to ${options.envFile} and fill the public values`,
        );
      } else {
        failures.push(`âœ— ${options.envFile} could not be read; check the file permissions and encoding`);
      }
    }
  }

  const processEnvironment = Object.fromEntries(
    PUBLIC_ENV_NAMES.filter((name) => process.env[name] !== undefined).map((name) => [
      name,
      process.env[name],
    ]),
  );
  const validation = validatePublicEnvironment(
    { ...fileEnvironment, ...processEnvironment },
    sourceLabel,
  );
  validation.checks.forEach((check) => console.log(`âœ“ ${check}`));
  failures.push(...formatEnvironmentIssues(validation.issues));

  if (failures.length > 0) {
    failures.forEach((failure) => console.error(failure));
    console.error("Environment check failed. No configuration values were printed.");
    return 1;
  }

  console.log("Environment check passed without exposing configuration values.");
  return 0;
}

const isDirectExecution =
  process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href;

if (isDirectExecution) {
  process.exitCode = runEnvironmentCheck();
}
