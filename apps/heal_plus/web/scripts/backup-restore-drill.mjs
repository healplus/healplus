import { createHash, randomUUID } from "node:crypto";
import { spawnSync } from "node:child_process";
import {
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { basename, dirname, relative, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { createClient } from "@supabase/supabase-js";

export const DRILL_PROJECT_ID = "healplus-backup-restore-drill";
export const REQUIRED_SUPABASE_CLI_VERSION = "2.113.0";
export const RECOVERY_TARGETS = Object.freeze({
  postgres: Object.freeze({ rpoHours: 24, rtoHours: 4 }),
  storage: Object.freeze({ rpoHours: 24, rtoHours: 8 }),
  service: Object.freeze({ rpoHours: 24, rtoHours: 8 }),
});

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const configPath = resolve(repositoryRoot, "supabase", "config.toml");
const fixtureDirectory = resolve(repositoryRoot, "supabase", "tests", "backup-restore");
const defaultEvidencePath = resolve(
  repositoryRoot,
  "test-results",
  "backup-restore",
  "evidence.json",
);

const syntheticObjects = [
  {
    bucket: "wound-images",
    path: "00000000-0000-4000-8000-000000000102/10000000-0000-4000-8000-000000000102/20000000-0000-4000-8000-000000000102/restore-drill.webp",
    contentType: "image/webp",
    bytes: Buffer.from("HEAL+ synthetic wound image restore drill\n", "utf8"),
  },
  {
    bucket: "profile-photos",
    path: "00000000-0000-4000-8000-000000000102/restore-drill.webp",
    contentType: "image/webp",
    bytes: Buffer.from("HEAL+ synthetic profile image restore drill\n", "utf8"),
  },
];

export function readProjectId(configContents) {
  const match = /^project_id\s*=\s*"([^"]+)"\s*$/mu.exec(configContents);
  return match?.[1] ?? null;
}

export function assertDedicatedLocalProject(configContents) {
  const projectId = readProjectId(configContents);
  if (projectId !== DRILL_PROJECT_ID) {
    throw new Error(
      `Recovery drill requires project_id "${DRILL_PROJECT_ID}"; received "${projectId ?? "missing"}".`,
    );
  }
  return projectId;
}

export function sha256(contents) {
  return createHash("sha256").update(contents).digest("hex");
}

export function buildEvidence({
  cliVersion,
  commit,
  completedAt,
  databaseDumpSha256,
  durationSeconds,
  error,
  objects,
  result,
  runId,
  startedAt,
}) {
  return {
    schemaVersion: 1,
    runId,
    result,
    syntheticDataOnly: true,
    projectId: DRILL_PROJECT_ID,
    commit,
    startedAt,
    completedAt,
    durationSeconds,
    recoveryTargets: RECOVERY_TARGETS,
    tooling: { supabaseCli: cliVersion },
    database: {
      strategy: "versioned migrations plus logical public-schema data dump",
      dumpSha256: databaseDumpSha256,
      expectedRows: {
        users: 1,
        patients: 1,
        evaluations: 1,
        appointments: 1,
      },
    },
    storage: {
      strategy: "separate object copy with SHA-256 verification",
      objects,
    },
    ...(error ? { error } : {}),
  };
}

function parseArguments(argumentsList) {
  const options = {
    confirmLocalReset: false,
    evidencePath: defaultEvidencePath,
    keepStack: false,
  };

  for (let index = 0; index < argumentsList.length; index += 1) {
    const argument = argumentsList[index];
    if (argument === "--confirm-local-reset") {
      options.confirmLocalReset = true;
    } else if (argument === "--keep-stack") {
      options.keepStack = true;
    } else if (argument === "--evidence") {
      const value = argumentsList[index + 1];
      if (!value) throw new Error("--evidence requires a file path");
      options.evidencePath = resolve(repositoryRoot, value);
      index += 1;
    } else {
      throw new Error(`Unknown option: ${argument}`);
    }
  }

  if (!options.confirmLocalReset) {
    throw new Error(
      "Refusing to reset the local database without --confirm-local-reset.",
    );
  }

  return options;
}

function runCommand(executable, argumentsList, { capture = false, tolerateFailure = false } = {}) {
  const result = spawnSync(executable, argumentsList, {
    cwd: repositoryRoot,
    encoding: "utf8",
    stdio: capture ? ["ignore", "pipe", "pipe"] : "inherit",
  });

  if (result.error) throw result.error;
  if (result.status !== 0 && !tolerateFailure) {
    const command = `${executable} ${argumentsList.join(" ")}`;
    throw new Error(`Command failed (${result.status}): ${command}`);
  }

  return {
    status: result.status,
    stdout: capture ? result.stdout.trim() : "",
    stderr: capture ? result.stderr.trim() : "",
  };
}

function runSupabase(argumentsList, options) {
  const entrypoint = process.env.SUPABASE_CLI_ENTRYPOINT;
  if (entrypoint) {
    return runCommand(process.execPath, [entrypoint, ...argumentsList], options);
  }
  const executable = process.env.SUPABASE_CLI_PATH || "supabase";
  return runCommand(executable, argumentsList, options);
}

function runSqlFile(filePath) {
  const dockerExecutable = process.env.DOCKER_CLI_PATH || "docker";
  const container = `supabase_db_${DRILL_PROJECT_ID}`;
  const containerPath = `/tmp/healplus-${basename(filePath)}`;
  runCommand(dockerExecutable, ["cp", filePath, `${container}:${containerPath}`], {
    capture: true,
  });
  runCommand(dockerExecutable, [
    "exec",
    container,
    "psql",
    "--username",
    "postgres",
    "--dbname",
    "postgres",
    "--set",
    "ON_ERROR_STOP=1",
    "--file",
    containerPath,
  ]);
}

function readStatus() {
  const status = runSupabase(["status", "-o", "json"], { capture: true });
  let parsed;
  try {
    parsed = JSON.parse(status.stdout);
  } catch {
    throw new Error("Supabase CLI returned an invalid local status document.");
  }

  const apiUrl = parsed.API_URL ?? parsed.api_url;
  const serviceRoleKey = parsed.SERVICE_ROLE_KEY ?? parsed.service_role_key;
  if (!apiUrl || !serviceRoleKey) {
    throw new Error("Local Supabase status did not expose API_URL and SERVICE_ROLE_KEY.");
  }

  return { apiUrl, serviceRoleKey };
}

function createAdminClient(status) {
  return createClient(status.apiUrl, status.serviceRoleKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
}

async function uploadSyntheticObjects(client) {
  for (const object of syntheticObjects) {
    const { error } = await client.storage.from(object.bucket).upload(object.path, object.bytes, {
      contentType: object.contentType,
      upsert: true,
    });
    if (error) throw new Error(`Could not upload ${object.bucket}/${object.path}: ${error.message}`);
  }
}

async function backUpStorage(client, backupDirectory) {
  const manifest = [];

  for (const object of syntheticObjects) {
    const { data, error } = await client.storage.from(object.bucket).download(object.path);
    if (error || !data) {
      throw new Error(`Could not back up ${object.bucket}/${object.path}: ${error?.message ?? "empty object"}`);
    }

    const bytes = Buffer.from(await data.arrayBuffer());
    const destination = resolve(backupDirectory, object.bucket, object.path);
    mkdirSync(dirname(destination), { recursive: true });
    writeFileSync(destination, bytes);
    manifest.push({
      bucket: object.bucket,
      path: object.path,
      bytes: bytes.length,
      sha256: sha256(bytes),
    });
  }

  return manifest.sort((left, right) =>
    `${left.bucket}/${left.path}`.localeCompare(`${right.bucket}/${right.path}`),
  );
}

async function removeSyntheticObjects(client) {
  for (const bucket of new Set(syntheticObjects.map((object) => object.bucket))) {
    const paths = syntheticObjects
      .filter((object) => object.bucket === bucket)
      .map((object) => object.path);
    const { error } = await client.storage.from(bucket).remove(paths);
    if (error) throw new Error(`Could not simulate loss in ${bucket}: ${error.message}`);
  }
}

async function restoreStorage(client, backupDirectory, manifest) {
  for (const object of manifest) {
    const source = resolve(backupDirectory, object.bucket, object.path);
    const bytes = readFileSync(source);
    const contentType = object.path.endsWith(".webp") ? "image/webp" : "application/octet-stream";
    const { error } = await client.storage.from(object.bucket).upload(object.path, bytes, {
      contentType,
      upsert: false,
    });
    if (error) throw new Error(`Could not restore ${object.bucket}/${object.path}: ${error.message}`);
  }
}

async function verifyStorage(client, manifest) {
  for (const expected of manifest) {
    const { data, error } = await client.storage.from(expected.bucket).download(expected.path);
    if (error || !data) {
      throw new Error(`Restored object is unavailable: ${expected.bucket}/${expected.path}`);
    }
    const actualHash = sha256(Buffer.from(await data.arrayBuffer()));
    if (actualHash !== expected.sha256) {
      throw new Error(`Checksum mismatch for ${expected.bucket}/${expected.path}`);
    }
  }
}

function sanitizeError(error) {
  return String(error?.message ?? error).replaceAll(repositoryRoot, "<repository>").slice(0, 500);
}

async function runRecoveryDrill(argumentsList = process.argv.slice(2)) {
  const options = parseArguments(argumentsList);
  const projectId = assertDedicatedLocalProject(readFileSync(configPath, "utf8"));
  const runId = randomUUID();
  const started = new Date();
  const temporaryDirectory = mkdtempSync(resolve(tmpdir(), "healplus-restore-drill-"));
  const storageBackupDirectory = resolve(temporaryDirectory, "storage");
  const databaseDumpPath = resolve(temporaryDirectory, "public-data.sql");
  const databaseRestorePath = resolve(temporaryDirectory, "restore-public-data.sql");
  let cliVersion = "unknown";
  let databaseDumpSha256 = null;
  let error = null;
  let stackStarted = false;
  let storageManifest = [];

  try {
    cliVersion = runSupabase(["--version"], { capture: true }).stdout;
    if (cliVersion !== REQUIRED_SUPABASE_CLI_VERSION) {
      throw new Error(
        `Supabase CLI ${REQUIRED_SUPABASE_CLI_VERSION} is required; received ${cliVersion}.`,
      );
    }

    runSupabase([
      "start",
      "--exclude",
      "studio,mailpit,imgproxy,realtime,edge-runtime,logflare,vector,supavisor",
    ], { capture: true });
    stackStarted = true;

    runSupabase(["db", "reset", "--local", "--no-seed"]);
    runSqlFile(resolve(fixtureDirectory, "seed.sql"));

    let client = createAdminClient(readStatus());
    await uploadSyntheticObjects(client);
    runSqlFile(resolve(fixtureDirectory, "verify.sql"));

    runSupabase([
      "db",
      "dump",
      "--local",
      "--data-only",
      "--use-copy",
      "--schema",
      "public",
      "--file",
      databaseDumpPath,
    ]);
    databaseDumpSha256 = sha256(readFileSync(databaseDumpPath));
    writeFileSync(
      databaseRestorePath,
      `begin;\nset local session_replication_role = replica;\n${readFileSync(databaseDumpPath, "utf8")}\ncommit;\n`,
      "utf8",
    );
    storageManifest = await backUpStorage(client, storageBackupDirectory);

    await removeSyntheticObjects(client);
    runSupabase(["db", "reset", "--local", "--no-seed"]);
    runSqlFile(resolve(fixtureDirectory, "auth-prerequisite.sql"));
    runSqlFile(databaseRestorePath);

    client = createAdminClient(readStatus());
    await restoreStorage(client, storageBackupDirectory, storageManifest);
    await verifyStorage(client, storageManifest);
    runSqlFile(resolve(fixtureDirectory, "verify.sql"));
  } catch (caughtError) {
    error = caughtError;
  } finally {
    if (stackStarted && !options.keepStack) {
      const cleanup = runSupabase(
        ["stop", "--project-id", projectId, "--no-backup"],
        { capture: true, tolerateFailure: true },
      );
      if (cleanup.status !== 0 && !error) {
        error = new Error("Recovery drill passed, but the dedicated local stack could not be removed.");
      }
    }

    const completed = new Date();
    const evidence = buildEvidence({
      cliVersion,
      commit: process.env.GITHUB_SHA || "local",
      completedAt: completed.toISOString(),
      databaseDumpSha256,
      durationSeconds: Number(((completed.valueOf() - started.valueOf()) / 1000).toFixed(3)),
      error: error ? sanitizeError(error) : null,
      objects: storageManifest,
      result: error ? "failed" : "passed",
      runId,
      startedAt: started.toISOString(),
    });
    mkdirSync(dirname(options.evidencePath), { recursive: true });
    writeFileSync(options.evidencePath, `${JSON.stringify(evidence, null, 2)}\n`, "utf8");
    rmSync(temporaryDirectory, { recursive: true, force: true });
    console.log(`Recovery evidence: ${relative(repositoryRoot, options.evidencePath)}`);
  }

  if (error) throw error;
}

const isDirectExecution =
  process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href;

if (isDirectExecution) {
  runRecoveryDrill().catch((error) => {
    console.error(`Recovery drill failed: ${sanitizeError(error)}`);
    process.exitCode = 1;
  });
}
