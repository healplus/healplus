import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import {
  extractMarkdownLinks,
  findMarkdownLinkIssues,
  validateDocumentationManifest,
} from "../check-markdown-links.mjs";

const scriptsDirectory = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const packageRoot = resolve(scriptsDirectory, "..");
const repositoryRoot = resolve(packageRoot, "../../..");

function withTemporaryRepository(callback) {
  const rootDirectory = mkdtempSync(resolve(tmpdir(), "healplus-docs-"));
  try {
    callback(rootDirectory);
  } finally {
    rmSync(rootDirectory, { recursive: true, force: true });
  }
}

test("extracts inline, image, and reference Markdown destinations with line numbers", () => {
  const links = extractMarkdownLinks(`See [guide](docs/guide.md).
![diagram](images/flow.png "Flow")
[policy]: SECURITY.md
`);

  assert.deepEqual(links, [
    { destination: "docs/guide.md", line: 1 },
    { destination: "images/flow.png", line: 2 },
    { destination: "SECURITY.md", line: 3 },
  ]);
});

test("reports the source file, line, and invalid relative destination", () => {
  withTemporaryRepository((rootDirectory) => {
    mkdirSync(resolve(rootDirectory, "docs"));
    writeFileSync(
      resolve(rootDirectory, "README.md"),
      "[Valid](docs/guide.md)\n[Broken](missing.md)\n[Outside](../outside.md)\n",
    );
    writeFileSync(resolve(rootDirectory, "docs", "guide.md"), "[External](https://example.com)\n");

    const result = findMarkdownLinkIssues(rootDirectory);

    assert.equal(result.files.length, 2);
    assert.deepEqual(result.issues, [
      {
        file: "README.md",
        line: 2,
        destination: "missing.md",
        reason: "relative target does not exist",
      },
      {
        file: "README.md",
        line: 3,
        destination: "../outside.md",
        reason: "relative target leaves the repository",
      },
    ]);
  });
});

test("allows a scanned package to link within an explicit monorepo boundary", () => {
  withTemporaryRepository((rootDirectory) => {
    const packageRoot = resolve(rootDirectory, "apps", "web");
    mkdirSync(packageRoot, { recursive: true });
    mkdirSync(resolve(rootDirectory, "docs"));
    writeFileSync(resolve(rootDirectory, "docs", "policy.md"), "# Policy\n");
    writeFileSync(resolve(packageRoot, "README.md"), "[Policy](../../docs/policy.md)\n");

    const result = findMarkdownLinkIssues(packageRoot, rootDirectory);

    assert.deepEqual(result.issues, []);
  });
});

test("validates document ownership and review freshness", () => {
  withTemporaryRepository((rootDirectory) => {
    writeFileSync(resolve(rootDirectory, "OPERATIONS.md"), "# Operations\n");
    const validManifest = {
      schemaVersion: 1,
      operationalDocuments: [
        {
          path: "OPERATIONS.md",
          owner: "@grupohealplus",
          lastReviewed: "2026-08-04",
          reviewEveryDays: 90,
        },
      ],
    };

    assert.deepEqual(
      validateDocumentationManifest(
        rootDirectory,
        validManifest,
        new Date("2026-08-04T00:00:00.000Z"),
      ),
      [],
    );

    const staleIssues = validateDocumentationManifest(
      rootDirectory,
      validManifest,
      new Date("2026-12-01T00:00:00.000Z"),
    );
    assert.equal(staleIssues.length, 1);
    assert.match(staleIssues[0].reason, /review expired/u);
  });
});

test("the web documentation currently has no broken relative links", () => {
  const result = findMarkdownLinkIssues(packageRoot, repositoryRoot);
  assert.deepEqual(result.issues, []);
});
