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
  "20260811005338_repair_storage_buckets_and_policies.sql",
);
const migration = readFileSync(migrationPath, "utf8");
const profileSelectMigration = readFileSync(
  resolve(
    repositoryRoot,
    "supabase",
    "migrations",
    "20260811005855_allow_profile_photo_owner_select.sql",
  ),
  "utf8",
);

test("clinical images remain private and use the supported upload limits", () => {
  assert.match(
    migration,
    /\('wound-images', 'wound-images', false, 10485760, array\['image\/jpeg', 'image\/png', 'image\/webp'\]\)/u,
  );
  assert.match(
    migration,
    /\('profile-photos', 'profile-photos', true, 10485760, array\['image\/jpeg', 'image\/png', 'image\/webp'\]\)/u,
  );
});
test("anonymous storage policies are removed", () => {
  for (const policy of [
    "Allow anon select on wound-images",
    "Allow anon uploads to wound-images",
    "Allow anon select on profile-photos",
    "Allow anon uploads to profile-photos",
  ]) {
    assert.match(migration, new RegExp(`drop policy if exists "${policy}"`, "u"));
  }
});

test("wound image operations require the authenticated owner folder", () => {
  for (const operation of ["select", "insert", "update", "delete"]) {
    assert.match(
      migration,
      new RegExp(
        String.raw`create policy wound_images_${operation}_own[\s\S]*?to authenticated[\s\S]*?` +
          String.raw`bucket_id = 'wound-images'[\s\S]*?` +
          String.raw`storage\.foldername\(name\)\)\[1\] = \(select auth\.uid\(\)\)::text`,
        "u",
      ),
    );
  }
});

test("profile photo upserts can select only the authenticated owner folder", () => {
  assert.match(
    profileSelectMigration,
    /create policy profile_photos_select_own[\s\S]*?for select to authenticated[\s\S]*?bucket_id = 'profile-photos'[\s\S]*?storage\.foldername\(name\)\)\[1\] = \(select auth\.uid\(\)\)::text/u,
  );
});
