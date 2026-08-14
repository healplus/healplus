import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const testsDirectory = dirname(fileURLToPath(import.meta.url));
const repositoryRoot = resolve(testsDirectory, "..", "..");

function migration(name) {
  return readFileSync(resolve(repositoryRoot, "supabase", "migrations", name), "utf8");
}

for (const name of [
  "202608030001_initial_schema.sql",
  "202608040002_repair_clinical_rls_policies.sql",
]) {
  test(`${name} grants the Data API only to authenticated users`, () => {
    const sql = migration(name);

    assert.match(
      sql,
      /revoke all on table public\.users, public\.patients, public\.evaluations, public\.appointments from anon;/u,
    );
    assert.match(sql, /grant usage on schema public to authenticated;/u);
    assert.match(
      sql,
      /grant select, insert, update, delete on table[\s\S]*?public\.users,[\s\S]*?public\.patients,[\s\S]*?public\.evaluations,[\s\S]*?public\.appointments[\s\S]*?to authenticated;/u,
    );
    assert.doesNotMatch(sql, /grant\s+[\s\S]*?\s+to anon\s*;/iu);
  });
}
