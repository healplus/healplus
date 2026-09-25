CREATE TABLE IF NOT EXISTS intake_analyses (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    idempotency_key TEXT,
    request_hash TEXT NOT NULL,
    patient_ref TEXT NOT NULL,
    encounter_ref TEXT,
    bundle_id TEXT NOT NULL,
    bundle_json TEXT NOT NULL,
    quality_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ACCEPTED','QUEUED','PROCESSING','COMPLETED','FAILED','REJECTED')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    available_at REAL NOT NULL DEFAULT 0,
    lease_until REAL,
    lease_token TEXT,
    result_json TEXT,
    error_code TEXT,
    UNIQUE(owner_id, idempotency_key)
);
CREATE TABLE IF NOT EXISTS intake_images (
    analysis_id TEXT NOT NULL REFERENCES intake_analyses(id) ON DELETE CASCADE,
    media_id TEXT NOT NULL,
    content BLOB NOT NULL,
    content_type TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    PRIMARY KEY (analysis_id, media_id)
);
CREATE TABLE IF NOT EXISTS intake_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id TEXT NOT NULL REFERENCES intake_analyses(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS intake_queue ON intake_analyses(status, available_at, created_at);
