import {
  existsSync,
  readFileSync,
  readdirSync,
  statSync,
} from "node:fs";
import { dirname, isAbsolute, relative, resolve, sep } from "node:path";
import { pathToFileURL } from "node:url";

const DEFAULT_MANIFEST = "docs/documentation-manifest.json";
const IGNORED_DIRECTORIES = new Set([
  ".git",
  ".pnpm-store",
  ".tools",
  "build",
  "coverage",
  "dist",
  "node_modules",
  "playwright-report",
  "test-results",
]);

function toRepositoryPath(rootDirectory, filePath) {
  return relative(rootDirectory, filePath).split(sep).join("/");
}

function lineNumberAt(content, index) {
  return content.slice(0, index).split(/\r?\n/u).length;
}

function normalizeDestination(rawDestination) {
  const trimmed = rawDestination.trim();
  const withoutAngles =
    trimmed.startsWith("<") && trimmed.endsWith(">") ? trimmed.slice(1, -1) : trimmed;

  try {
    return decodeURIComponent(withoutAngles);
  } catch {
    return withoutAngles;
  }
}

export function extractMarkdownLinks(content) {
  const links = [];
  const inlinePattern =
    /!?\[[^\]]*\]\(\s*(<[^>\n]+>|[^\s)]+)(?:\s+(?:"[^"]*"|'[^']*'|\([^)]*\)))?\s*\)/gu;
  const referencePattern = /^\s{0,3}\[[^\]]+\]:\s*(<[^>\n]+>|[^\s]+).*$/gmu;

  for (const match of content.matchAll(inlinePattern)) {
    links.push({ destination: normalizeDestination(match[1]), line: lineNumberAt(content, match.index) });
  }

  for (const match of content.matchAll(referencePattern)) {
    links.push({ destination: normalizeDestination(match[1]), line: lineNumberAt(content, match.index) });
  }

  return links;
}

export function findMarkdownFiles(rootDirectory) {
  const markdownFiles = [];

  function visit(directory) {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      if (entry.isDirectory() && IGNORED_DIRECTORIES.has(entry.name)) continue;

      const entryPath = resolve(directory, entry.name);
      if (entry.isDirectory()) {
        visit(entryPath);
      } else if (entry.isFile() && entry.name.toLowerCase().endsWith(".md")) {
        markdownFiles.push(entryPath);
      }
    }
  }

  visit(rootDirectory);
  return markdownFiles.sort((left, right) => left.localeCompare(right));
}

function isExternalOrPageLink(destination) {
  return (
    !destination ||
    destination.startsWith("#") ||
    destination.startsWith("//") ||
    destination.startsWith("/") ||
    /^[A-Za-z][A-Za-z0-9+.-]*:/u.test(destination)
  );
}

export function findMarkdownLinkIssues(rootDirectory, boundaryDirectory = rootDirectory) {
  const issues = [];
  const files = findMarkdownFiles(rootDirectory);
  const resolvedBoundary = resolve(boundaryDirectory);

  for (const filePath of files) {
    const content = readFileSync(filePath, "utf8");
    for (const link of extractMarkdownLinks(content)) {
      if (isExternalOrPageLink(link.destination)) continue;

      const pathOnly = link.destination.split("#", 1)[0].split("?", 1)[0];
      if (!pathOnly) continue;

      const targetPath = resolve(dirname(filePath), pathOnly);
      const targetFromRoot = relative(resolvedBoundary, targetPath);
      const leavesRepository =
        isAbsolute(targetFromRoot) ||
        targetFromRoot === ".." ||
        targetFromRoot.startsWith(`..${sep}`) ||
        resolve(resolvedBoundary, targetFromRoot) !== targetPath;

      if (leavesRepository) {
        issues.push({
          file: toRepositoryPath(rootDirectory, filePath),
          line: link.line,
          destination: link.destination,
          reason: "relative target leaves the repository",
        });
      } else if (!existsSync(targetPath)) {
        issues.push({
          file: toRepositoryPath(rootDirectory, filePath),
          line: link.line,
          destination: link.destination,
          reason: "relative target does not exist",
        });
      }
    }
  }

  return { files, issues };
}

function parseIsoDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/u.test(value)) return null;
  const parsed = new Date(`${value}T00:00:00.000Z`);
  return Number.isNaN(parsed.valueOf()) || parsed.toISOString().slice(0, 10) !== value
    ? null
    : parsed;
}

export function validateDocumentationManifest(
  rootDirectory,
  manifest,
  today = new Date(),
  manifestPath = DEFAULT_MANIFEST,
) {
  const issues = [];
  const entries = manifest.operationalDocuments;

  if (manifest.schemaVersion !== 1) {
    issues.push({
      file: manifestPath,
      line: 1,
      destination: "schemaVersion",
      reason: "must be 1",
    });
  }

  if (!Array.isArray(entries) || entries.length === 0) {
    issues.push({
      file: manifestPath,
      line: 1,
      destination: "operationalDocuments",
      reason: "must list at least one maintained document",
    });
    return issues;
  }

  const seenPaths = new Set();
  const todayUtc = new Date(
    Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate()),
  );

  entries.forEach((entry, index) => {
    const entryLabel = `operationalDocuments[${index}]`;
    const documentPath = typeof entry.path === "string" ? entry.path.trim() : "";

    if (!documentPath || seenPaths.has(documentPath)) {
      issues.push({
        file: manifestPath,
        line: 1,
        destination: `${entryLabel}.path`,
        reason: documentPath ? "duplicates another document" : "is required",
      });
    } else {
      seenPaths.add(documentPath);
      const absoluteDocumentPath = resolve(rootDirectory, documentPath);
      if (!existsSync(absoluteDocumentPath) || !statSync(absoluteDocumentPath).isFile()) {
        issues.push({
          file: manifestPath,
          line: 1,
          destination: documentPath,
          reason: "maintained document does not exist",
        });
      }
    }

    if (typeof entry.owner !== "string" || !/^@[A-Za-z0-9-]+$/u.test(entry.owner)) {
      issues.push({
        file: manifestPath,
        line: 1,
        destination: `${entryLabel}.owner`,
        reason: "must be a GitHub account such as @grupohealplus",
      });
    }

    const reviewedOn = parseIsoDate(entry.lastReviewed);
    if (!reviewedOn) {
      issues.push({
        file: manifestPath,
        line: 1,
        destination: `${entryLabel}.lastReviewed`,
        reason: "must use a valid YYYY-MM-DD date",
      });
    }

    if (!Number.isInteger(entry.reviewEveryDays) || entry.reviewEveryDays < 1) {
      issues.push({
        file: manifestPath,
        line: 1,
        destination: `${entryLabel}.reviewEveryDays`,
        reason: "must be a positive whole number",
      });
    } else if (reviewedOn) {
      const nextReview = new Date(reviewedOn);
      nextReview.setUTCDate(nextReview.getUTCDate() + entry.reviewEveryDays);
      if (reviewedOn > todayUtc) {
        issues.push({
          file: manifestPath,
          line: 1,
          destination: documentPath || entryLabel,
          reason: "last review date cannot be in the future",
        });
      } else if (nextReview < todayUtc) {
        issues.push({
          file: manifestPath,
          line: 1,
          destination: documentPath || entryLabel,
          reason: `review expired on ${nextReview.toISOString().slice(0, 10)}`,
        });
      }
    }
  });

  return issues;
}

function parseArguments(argumentsList) {
  const options = {
    root: ".",
    boundary: null,
    manifest: DEFAULT_MANIFEST,
    today: new Date(),
    help: false,
  };

  for (let index = 0; index < argumentsList.length; index += 1) {
    const argument = argumentsList[index];
    if (
      argument === "--root" ||
      argument === "--boundary" ||
      argument === "--manifest" ||
      argument === "--today"
    ) {
      const value = argumentsList[index + 1];
      if (!value) throw new Error(`${argument} requires a value`);
      if (argument === "--root") options.root = value;
      if (argument === "--boundary") options.boundary = value;
      if (argument === "--manifest") options.manifest = value;
      if (argument === "--today") {
        const parsedDate = parseIsoDate(value);
        if (!parsedDate) throw new Error("--today must use YYYY-MM-DD");
        options.today = parsedDate;
      }
      index += 1;
    } else if (argument === "--help" || argument === "-h") {
      options.help = true;
    } else {
      throw new Error(`Unknown option: ${argument}`);
    }
  }

  return options;
}

function printHelp() {
  console.log(`HEAL+ Markdown documentation verifier

Usage:
  npm run docs:check
  npm run docs:check -- --root path --manifest docs/manifest.json

Options:
  --root <path>      Repository root to scan (default: current directory)
  --boundary <path> Allowed repository boundary for links outside the scan root
  --manifest <path> Documentation governance manifest
  --today <date>     Override current date with YYYY-MM-DD for reproducible checks
  -h, --help         Show this help`);
}

function formatIssue(issue) {
  return `✗ ${issue.file}:${issue.line} -> ${issue.destination}: ${issue.reason}`;
}

export function runDocumentationCheck(argumentsList = process.argv.slice(2)) {
  let options;
  try {
    options = parseArguments(argumentsList);
  } catch (error) {
    console.error(`✗ ${error.message}`);
    console.error("Run `npm run docs:check -- --help` for usage.");
    return 1;
  }

  if (options.help) {
    printHelp();
    return 0;
  }

  const rootDirectory = resolve(options.root);
  const manifestFile = resolve(rootDirectory, options.manifest);
  const boundaryDirectory = options.boundary ? resolve(options.boundary) : rootDirectory;
  const linkResult = findMarkdownLinkIssues(rootDirectory, boundaryDirectory);
  let manifestIssues = [];
  let manifestEntries = 0;

  try {
    const manifest = JSON.parse(readFileSync(manifestFile, "utf8"));
    manifestEntries = Array.isArray(manifest.operationalDocuments)
      ? manifest.operationalDocuments.length
      : 0;
    manifestIssues = validateDocumentationManifest(
      rootDirectory,
      manifest,
      options.today,
      options.manifest,
    );
  } catch (error) {
    manifestIssues.push({
      file: options.manifest,
      line: 1,
      destination: options.manifest,
      reason:
        error?.code === "ENOENT"
          ? "documentation governance manifest does not exist"
          : "documentation governance manifest is not valid JSON",
    });
  }

  const issues = [...linkResult.issues, ...manifestIssues];
  if (issues.length > 0) {
    issues.forEach((issue) => console.error(formatIssue(issue)));
    console.error(`Documentation check failed with ${issues.length} issue(s).`);
    return 1;
  }

  console.log(
    `Documentation check passed: ${linkResult.files.length} Markdown files and ${manifestEntries} maintained documents.`,
  );
  return 0;
}

const isDirectExecution =
  process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href;

if (isDirectExecution) {
  process.exitCode = runDocumentationCheck();
}
