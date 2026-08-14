import assert from "node:assert/strict";
import test from "node:test";

import {
  DRILL_PROJECT_ID,
  RECOVERY_TARGETS,
  assertDedicatedLocalProject,
  buildEvidence,
  readProjectId,
  sha256,
} from "../backup-restore-drill.mjs";

test("accepts only the dedicated local recovery project", () => {
  const validConfig = `project_id = "${DRILL_PROJECT_ID}"\n`;
  assert.equal(readProjectId(validConfig), DRILL_PROJECT_ID);
  assert.equal(assertDedicatedLocalProject(validConfig), DRILL_PROJECT_ID);
  assert.throws(
    () => assertDedicatedLocalProject('project_id = "production"\n'),
    /requires project_id/u,
  );
});

test("builds sanitized, reproducible recovery evidence", () => {
  const objectBytes = Buffer.from("synthetic object", "utf8");
  const evidence = buildEvidence({
    cliVersion: "2.113.0",
    commit: "abc123",
    completedAt: "2026-08-10T10:05:00.000Z",
    databaseDumpSha256: "database-sha",
    durationSeconds: 300,
    error: null,
    objects: [
      {
        bucket: "wound-images",
        path: "synthetic/restore-drill.webp",
        bytes: objectBytes.length,
        sha256: sha256(objectBytes),
      },
    ],
    result: "passed",
    runId: "run-102",
    startedAt: "2026-08-10T10:00:00.000Z",
  });

  assert.equal(evidence.syntheticDataOnly, true);
  assert.deepEqual(evidence.recoveryTargets, RECOVERY_TARGETS);
  assert.equal(evidence.database.expectedRows.evaluations, 1);
  assert.equal(evidence.storage.objects[0].sha256, sha256(objectBytes));
  assert.equal("serviceRoleKey" in evidence, false);
});
