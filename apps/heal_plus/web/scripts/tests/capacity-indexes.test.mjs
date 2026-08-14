import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const migrationUrl = new URL(
  '../../supabase/migrations/202608130001_index_clinical_foreign_keys.sql',
  import.meta.url
);

test('clinical foreign keys used by cascades have dedicated indexes', async () => {
  const sql = await readFile(migrationUrl, 'utf8');

  assert.match(sql, /create index if not exists evaluations_patient_id_idx\s+on public\.evaluations\(patient_id\)/i);
  assert.match(sql, /create index if not exists appointments_patient_id_idx\s+on public\.appointments\(patient_id\)/i);
});
