import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import {
  contentHash,
  parsePublicTables,
  readDataDictionary,
  renderDataDictionary,
  validateDataDictionary,
} from "../data-dictionary.mjs";

const scriptsDirectory = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = resolve(scriptsDirectory, "..");

test("parses columns without splitting defaults and checks that contain commas", () => {
  const tables = parsePublicTables([
    {
      content: `create table if not exists public.synthetic_records (
  id uuid primary key,
  status text not null default 'Pendente' check (status in ('Pendente', 'Realizado')),
  tags text[] not null default '{}'
);
`,
    },
  ]);

  assert.deepEqual(tables, [
    {
      name: "synthetic_records",
      columns: [
        { name: "id", sql: "uuid primary key" },
        {
          name: "status",
          sql: "text not null default 'Pendente' check (status in ('Pendente', 'Realizado'))",
        },
        { name: "tags", sql: "text[] not null default '{}'" },
      ],
    },
  ]);
});

test("hashes migration content consistently across operating-system line endings", () => {
  assert.equal(contentHash("select 1;\r\n"), contentHash("select 1;\n"));
});

test("the canonical dictionary matches every current migration table and field", () => {
  const dictionary = readDataDictionary(repositoryRoot);
  assert.deepEqual(validateDataDictionary(repositoryRoot, dictionary), []);
});

test("reports stale migration fingerprints and missing documented fields", () => {
  const dictionary = structuredClone(readDataDictionary(repositoryRoot));
  dictionary.sources.migrations[0].sha256 = "stale";
  dictionary.tables.find((table) => table.name === "patients").columns.pop();

  const issues = validateDataDictionary(repositoryRoot, dictionary);

  assert.ok(issues.some((issue) => issue.includes("changed; review the persisted contracts")));
  assert.ok(issues.some((issue) => issue.includes("tables.patients.columns")));
});

test("the committed Markdown matches the canonical dictionary", () => {
  const dictionary = readDataDictionary(repositoryRoot);
  const committed = readFileSync(resolve(repositoryRoot, "docs/data-dictionary.md"), "utf8");
  assert.equal(committed.replace(/\r\n?/gu, "\n"), renderDataDictionary(dictionary));
});
