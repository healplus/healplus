import { createHash } from "node:crypto";
import {
  readFileSync,
  readdirSync,
  writeFileSync,
} from "node:fs";
import { relative, resolve, sep } from "node:path";
import { pathToFileURL } from "node:url";

const DICTIONARY_PATH = "docs/data-dictionary.json";
const GENERATED_DOCUMENT_PATH = "docs/data-dictionary.md";
const MIGRATIONS_DIRECTORY = "supabase/migrations";

function repositoryPath(rootDirectory, filePath) {
  return relative(rootDirectory, filePath).split(sep).join("/");
}

function normalizedContent(content) {
  return content.replace(/\r\n?/gu, "\n");
}

export function contentHash(content) {
  return createHash("sha256").update(normalizedContent(content), "utf8").digest("hex");
}

function normalizeSql(value) {
  return value.replace(/\s+/gu, " ").trim();
}

function splitTableDefinitions(tableBody) {
  const definitions = [];
  let start = 0;
  let depth = 0;
  let insideString = false;

  for (let index = 0; index < tableBody.length; index += 1) {
    const character = tableBody[index];
    const nextCharacter = tableBody[index + 1];

    if (character === "'") {
      if (insideString && nextCharacter === "'") {
        index += 1;
      } else {
        insideString = !insideString;
      }
      continue;
    }

    if (insideString) continue;
    if (character === "(") depth += 1;
    if (character === ")") depth -= 1;
    if (character === "," && depth === 0) {
      definitions.push(tableBody.slice(start, index));
      start = index + 1;
    }
  }

  definitions.push(tableBody.slice(start));
  return definitions.map(normalizeSql).filter(Boolean);
}

export function parsePublicTables(migrationSources) {
  const tables = new Map();
  const createTablePattern =
    /create\s+table\s+if\s+not\s+exists\s+public\.([a-z_][a-z0-9_]*)\s*\(([\s\S]*?)\n\);/giu;

  for (const source of migrationSources) {
    for (const match of normalizedContent(source.content).matchAll(createTablePattern)) {
      const columns = splitTableDefinitions(match[2])
        .filter((definition) =>
          !/^(constraint|primary\s+key|foreign\s+key|unique|check)\b/iu.test(definition),
        )
        .map((definition) => {
          const columnMatch = definition.match(/^([a-z_][a-z0-9_]*)\s+([\s\S]+)$/iu);
          if (!columnMatch) {
            throw new Error(`Could not parse column definition: ${definition}`);
          }
          return { name: columnMatch[1], sql: normalizeSql(columnMatch[2]) };
        });

      tables.set(match[1], { name: match[1], columns });
    }
  }

  return [...tables.values()].sort((left, right) => left.name.localeCompare(right.name));
}

export function readMigrationSources(rootDirectory) {
  const migrationsDirectory = resolve(rootDirectory, MIGRATIONS_DIRECTORY);
  return readdirSync(migrationsDirectory, { withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith(".sql"))
    .sort((left, right) => left.name.localeCompare(right.name))
    .map((entry) => {
      const filePath = resolve(migrationsDirectory, entry.name);
      const content = readFileSync(filePath, "utf8");
      return {
        path: repositoryPath(rootDirectory, filePath),
        sha256: contentHash(content),
        content,
      };
    });
}

export function readDataDictionary(rootDirectory) {
  return JSON.parse(readFileSync(resolve(rootDirectory, DICTIONARY_PATH), "utf8"));
}

function validateDescription(issues, value, location) {
  if (typeof value !== "string" || value.trim().length < 8) {
    issues.push(`${location} must have a meaningful description`);
  }
}

function validateClassification(issues, value, location, allowedClassifications) {
  if (!allowedClassifications.has(value)) {
    issues.push(`${location} uses unknown classification '${value}'`);
  }
}

export function validateDataDictionary(rootDirectory, dictionary) {
  const issues = [];
  const migrations = readMigrationSources(rootDirectory);
  const actualTables = parsePublicTables(migrations);

  if (dictionary.schemaVersion !== 1) {
    issues.push("schemaVersion must be 1");
  }

  const classifications = Array.isArray(dictionary.classifications)
    ? dictionary.classifications
    : [];
  const allowedClassifications = new Set(classifications.map((item) => item.id));
  if (allowedClassifications.size !== classifications.length || classifications.length === 0) {
    issues.push("classifications must contain unique entries");
  }
  classifications.forEach((item, index) => {
    validateDescription(issues, item.label, `classifications[${index}].label`);
    validateDescription(issues, item.handling, `classifications[${index}].handling`);
  });

  const declaredMigrations = dictionary.sources?.migrations ?? [];
  if (declaredMigrations.length !== migrations.length) {
    issues.push(
      `sources.migrations lists ${declaredMigrations.length} file(s), but ${migrations.length} exist`,
    );
  }
  migrations.forEach((migration, index) => {
    const declared = declaredMigrations[index];
    if (declared?.path !== migration.path) {
      issues.push(
        `sources.migrations[${index}].path must be '${migration.path}', received '${declared?.path}'`,
      );
    }
    if (declared?.sha256 !== migration.sha256) {
      issues.push(
        `${migration.path} changed; review the persisted contracts and refresh its SHA-256`,
      );
    }
  });

  const declaredTables = Array.isArray(dictionary.tables) ? dictionary.tables : [];
  const actualTableNames = actualTables.map((table) => table.name);
  const declaredTableNames = declaredTables.map((table) => table.name).sort();
  if (JSON.stringify(declaredTableNames) !== JSON.stringify(actualTableNames)) {
    issues.push(
      `documented public tables (${declaredTableNames.join(", ")}) differ from migrations (${actualTableNames.join(", ")})`,
    );
  }

  for (const table of declaredTables) {
    const location = `tables.${table.name}`;
    validateDescription(issues, table.purpose, `${location}.purpose`);
    validateClassification(
      issues,
      table.classification,
      `${location}.classification`,
      allowedClassifications,
    );

    const actualTable = actualTables.find((candidate) => candidate.name === table.name);
    if (!actualTable) continue;

    const declaredColumns = Array.isArray(table.columns) ? table.columns : [];
    const actualColumnNames = actualTable.columns.map((column) => column.name);
    const declaredColumnNames = declaredColumns.map((column) => column.name);
    if (JSON.stringify(declaredColumnNames) !== JSON.stringify(actualColumnNames)) {
      issues.push(
        `${location}.columns (${declaredColumnNames.join(", ")}) differ from migrations (${actualColumnNames.join(", ")})`,
      );
    }

    for (const column of declaredColumns) {
      const columnLocation = `${location}.columns.${column.name}`;
      validateDescription(issues, column.purpose, `${columnLocation}.purpose`);
      validateClassification(
        issues,
        column.classification,
        `${columnLocation}.classification`,
        allowedClassifications,
      );
      const actualColumn = actualTable.columns.find((candidate) => candidate.name === column.name);
      if (actualColumn && normalizeSql(column.sql ?? "") !== actualColumn.sql) {
        issues.push(
          `${columnLocation}.sql differs: expected '${actualColumn.sql}', received '${column.sql}'`,
        );
      }
    }
  }

  for (const contract of dictionary.jsonContracts ?? []) {
    const location = `jsonContracts.${contract.table}.${contract.column}`;
    const table = declaredTables.find((candidate) => candidate.name === contract.table);
    if (!table?.columns?.some((column) => column.name === contract.column)) {
      issues.push(`${location} does not reference a documented column`);
    }
    validateDescription(issues, contract.purpose, `${location}.purpose`);
    for (const field of contract.fields ?? []) {
      validateDescription(issues, field.purpose, `${location}.${field.path}.purpose`);
      validateClassification(
        issues,
        field.classification,
        `${location}.${field.path}.classification`,
        allowedClassifications,
      );
    }
  }

  for (const bucket of dictionary.storageBuckets ?? []) {
    const location = `storageBuckets.${bucket.id}`;
    validateDescription(issues, bucket.purpose, `${location}.purpose`);
    validateClassification(
      issues,
      bucket.classification,
      `${location}.classification`,
      allowedClassifications,
    );
  }

  return issues;
}

function escapeTableCell(value) {
  return String(value ?? "â€”").replaceAll("|", "\\|").replaceAll("\n", " ");
}

function markdownTable(headers, rows) {
  return [
    `| ${headers.join(" | ")} |`,
    `| ${headers.map(() => "---").join(" | ")} |`,
    ...rows.map((row) => `| ${row.map(escapeTableCell).join(" | ")} |`),
  ].join("\n");
}

export function renderDataDictionary(dictionary) {
  const lines = [
    "# DicionÃ¡rio de dados e contratos persistidos",
    "",
    "> Arquivo gerado a partir de `docs/data-dictionary.json`. NÃ£o edite manualmente.",
    "",
    "Este documento descreve os dados persistidos pelo HEAL+, sua finalidade, classificaÃ§Ã£o, relacionamentos e controles. As migraÃ§Ãµes em `supabase/migrations/` continuam sendo a fonte executÃ¡vel do schema.",
    "",
    "## Fontes versionadas",
    "",
    markdownTable(
      ["Fonte", "SHA-256"],
      dictionary.sources.migrations.map((migration) => [
        `\`${migration.path}\``,
        `\`${migration.sha256}\``,
      ]),
    ),
    "",
    `Contratos de aplicaÃ§Ã£o conferidos em: ${dictionary.sources.contracts.map((path) => `\`${path}\``).join(", ")}.`,
    "",
    "## ClassificaÃ§Ã£o",
    "",
    markdownTable(
      ["Identificador", "Classe", "Tratamento"],
      dictionary.classifications.map((item) => [
        `\`${item.id}\``,
        item.label,
        item.handling,
      ]),
    ),
    "",
    "## Tabelas pÃºblicas",
    "",
    "RLS e privilÃ©gios SQL sÃ£o camadas diferentes. As migraÃ§Ãµes atuais habilitam RLS e criam polÃ­ticas para `authenticated`, mas nÃ£o contÃªm `GRANT`/`REVOKE` explÃ­cito para estas tabelas; a exposiÃ§Ã£o pela Data API tambÃ©m depende dos privilÃ©gios configurados no ambiente Supabase.",
    "",
  ];

  for (const table of dictionary.tables) {
    lines.push(
      `### \`public.${table.name}\``,
      "",
      table.purpose,
      "",
      `- ClassificaÃ§Ã£o predominante: \`${table.classification}\``,
      `- ProprietÃ¡rio: ${table.ownerKey ? `\`${table.ownerKey}\`` : "perfil autenticado pelo identificador primÃ¡rio"}`,
      `- RLS: ${table.rls.enabled ? "habilitada" : "nÃ£o habilitada"}; polÃ­tica \`${table.rls.policy}\` para \`${table.rls.role}\` â€” ${table.rls.rule}`,
      `- Realtime: ${table.realtime ? "publicada em `supabase_realtime`" : "nÃ£o publicada"}`,
      `- PrivilÃ©gios da Data API: ${table.dataApiAccess}`,
      "",
      markdownTable(
        ["Campo", "DefiniÃ§Ã£o PostgreSQL", "ClassificaÃ§Ã£o", "Finalidade"],
        table.columns.map((column) => [
          `\`${column.name}\``,
          `\`${column.sql}\``,
          `\`${column.classification}\``,
          column.purpose,
        ]),
      ),
      "",
      "Relacionamentos:",
      "",
      ...(table.relationships.length > 0
        ? table.relationships.map((relationship) => `- ${relationship}`)
        : ["- Nenhum relacionamento adicional alÃ©m da identidade autenticada."]),
      "",
      "Ãndices:",
      "",
      ...(table.indexes.length > 0
        ? table.indexes.map((index) => `- \`${index}\``)
        : ["- Apenas o Ã­ndice criado pela chave primÃ¡ria."]),
      "",
    );
  }

  lines.push("## Contratos JSON persistidos", "");
  for (const contract of dictionary.jsonContracts) {
    lines.push(
      `### \`public.${contract.table}.${contract.column}\` â€” ${contract.name}`,
      "",
      contract.purpose,
      "",
      `Fonte TypeScript: \`${contract.source}\`.`,
      "",
      markdownTable(
        ["Caminho", "Tipo", "ObrigatÃ³rio", "ClassificaÃ§Ã£o", "Finalidade"],
        contract.fields.map((field) => [
          `\`${field.path}\``,
          `\`${field.type}\``,
          field.required ? "sim" : "nÃ£o",
          `\`${field.classification}\``,
          field.purpose,
        ]),
      ),
      "",
      ...(contract.notes ?? []).map((note) => `- ${note}`),
      ...(contract.notes?.length ? [""] : []),
    );
  }

  lines.push(
    "## Valores fechados",
    "",
    markdownTable(
      ["Contrato", "Valores", "Origem"],
      dictionary.enums.map((item) => [
        `\`${item.name}\``,
        item.values.map((value) => `\`${value}\``).join(", "),
        item.source,
      ]),
    ),
    "",
    "## Storage",
    "",
    markdownTable(
      ["Bucket", "Visibilidade", "Limite", "MIME", "ClassificaÃ§Ã£o", "Finalidade e acesso"],
      dictionary.storageBuckets.map((bucket) => [
        `\`${bucket.id}\``,
        bucket.public ? "pÃºblico" : "privado",
        `${bucket.fileSizeLimitBytes} bytes (10 MB)`,
        bucket.allowedMimeTypes.map((mime) => `\`${mime}\``).join(", "),
        `\`${bucket.classification}\``,
        `${bucket.purpose} ${bucket.access}`,
      ]),
    ),
    "",
    "## Objetos auxiliares",
    "",
    ...dictionary.auxiliaryObjects.map((item) => `- \`${item.name}\`: ${item.purpose}`),
    "",
    "## Como manter",
    "",
    "1. Crie uma nova migraÃ§Ã£o; nÃ£o altere uma migraÃ§Ã£o jÃ¡ aplicada.",
    "2. Atualize campos, contratos, relaÃ§Ãµes e classificaÃ§Ãµes em `docs/data-dictionary.json`.",
    "3. Execute `npm run docs:data:refresh` para renovar os hashes e gerar este Markdown.",
    "4. Execute `npm run docs:data:check` e os demais testes obrigatÃ³rios.",
    "",
    "A validaÃ§Ã£o falha quando uma migraÃ§Ã£o muda, surge ou remove uma tabela/campo, uma definiÃ§Ã£o SQL diverge, ou o Markdown gerado fica desatualizado. MudanÃ§as de polÃ­tica, Storage e Realtime tambÃ©m alteram o hash e exigem revisÃ£o consciente do dicionÃ¡rio.",
    "",
  );

  return lines.join("\n");
}

function refreshSources(rootDirectory, dictionary) {
  dictionary.sources.migrations = readMigrationSources(rootDirectory).map(({ path, sha256 }) => ({
    path,
    sha256,
  }));
  writeFileSync(
    resolve(rootDirectory, DICTIONARY_PATH),
    `${JSON.stringify(dictionary, null, 2)}\n`,
    "utf8",
  );
}

function parseArguments(argumentsList) {
  const modes = new Set(argumentsList);
  const selectedModes = ["--check", "--write", "--refresh"].filter((mode) => modes.has(mode));
  if (selectedModes.length > 1 || argumentsList.some((argument) => !selectedModes.includes(argument))) {
    throw new Error("Use exactly one of --check, --write, or --refresh");
  }
  return selectedModes[0] ?? "--check";
}

export function runDataDictionary(argumentsList = process.argv.slice(2), rootDirectory = process.cwd()) {
  let mode;
  try {
    mode = parseArguments(argumentsList);
  } catch (error) {
    console.error(`Data dictionary: ${error.message}`);
    return 1;
  }

  const dictionary = readDataDictionary(rootDirectory);
  if (mode === "--refresh") refreshSources(rootDirectory, dictionary);

  const issues = validateDataDictionary(rootDirectory, dictionary);
  if (issues.length > 0) {
    issues.forEach((issue) => console.error(`Data dictionary: ${issue}`));
    console.error(`Data dictionary check failed with ${issues.length} issue(s).`);
    return 1;
  }

  const rendered = renderDataDictionary(dictionary);
  const generatedPath = resolve(rootDirectory, GENERATED_DOCUMENT_PATH);

  if (mode === "--write" || mode === "--refresh") {
    writeFileSync(generatedPath, rendered, "utf8");
    console.log(`Data dictionary generated at ${GENERATED_DOCUMENT_PATH}.`);
    return 0;
  }

  const committedDocument = normalizedContent(readFileSync(generatedPath, "utf8"));
  if (committedDocument !== normalizedContent(rendered)) {
    console.error(
      `Data dictionary: ${GENERATED_DOCUMENT_PATH} is stale; run npm run docs:data:generate`,
    );
    return 1;
  }

  console.log(
    `Data dictionary check passed: ${dictionary.tables.length} tables, ${dictionary.jsonContracts.length} JSON contracts, and ${dictionary.storageBuckets.length} buckets.`,
  );
  return 0;
}

const isDirectExecution =
  process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href;

if (isDirectExecution) {
  process.exitCode = runDataDictionary();
}
