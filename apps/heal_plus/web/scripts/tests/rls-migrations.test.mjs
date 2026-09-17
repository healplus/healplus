import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const testsDirectory = dirname(fileURLToPath(import.meta.url));
const repositoryRoot = resolve(testsDirectory, "..", "..");
const migrationPath = resolve(
  repositoryRoot,
  "supabase",
  "migrations",
  "202608040002_repair_clinical_rls_policies.sql",
);
const migration = readFileSync(migrationPath, "utf8");

test("the RLS repair is transactional and enables every clinical table", () => {
  assert.match(migration, /^begin;/mu);
  assert.match(migration, /commit;\s*$/u);

  for (const table of ["users", "patients", "evaluations", "appointments"]) {
    assert.match(
      migration,
      new RegExp(String.raw`alter table public\.${table} enable row level security;`, "u"),
    );
  }
});
test("profile and patient writes remain restricted to the authenticated owner", () => {
  assert.match(
    migration,
    /create policy users_own_profile[\s\S]*?for all to authenticated[\s\S]*?using \(\(select auth\.uid\(\)\)::text = uid::text\)[\s\S]*?with check \(\(select auth\.uid\(\)\)::text = uid::text\);/u,
  );
  assert.match(
    migration,
    /create policy patients_owned_by_professional[\s\S]*?for all to authenticated[\s\S]*?using \(\(select auth\.uid\(\)\)::text = user_id::text\)[\s\S]*?with check \(\(select auth\.uid\(\)\)::text = user_id::text\);/u,
  );
});

test("evaluation and appointment writes require a patient from the same owner", () => {
  for (const table of ["evaluations", "appointments"]) {
    const policy = new RegExp(
      String.raw`create policy ${table}_owned_by_professional[\s\S]*?` +
        String.raw`patient\.id::text = ${table}\.patient_id::text[\s\S]*?` +
        String.raw`patient\.user_id::text = \(select auth\.uid\(\)\)::text`,
      "u",
    );
    assert.match(migration, policy);
  }
});
