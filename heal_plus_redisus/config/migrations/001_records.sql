-- Local service schema v1. Back up under the institution's retention policy.
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS sprint_schema(version INTEGER PRIMARY KEY);
INSERT OR IGNORE INTO sprint_schema(version) VALUES(1);
CREATE TABLE IF NOT EXISTS sprint_patients(
    tenant_id TEXT NOT NULL, patient_id TEXT NOT NULL, record TEXT NOT NULL,
    PRIMARY KEY(tenant_id, patient_id)
);
CREATE TABLE IF NOT EXISTS sprint_wounds(
    tenant_id TEXT NOT NULL, wound_id TEXT NOT NULL, patient_id TEXT NOT NULL,
    PRIMARY KEY(tenant_id, wound_id),
    FOREIGN KEY(tenant_id, patient_id) REFERENCES sprint_patients(tenant_id, patient_id)
);
CREATE TABLE IF NOT EXISTS sprint_images(
    tenant_id TEXT NOT NULL, image_id TEXT NOT NULL, patient_id TEXT NOT NULL,
    wound_id TEXT NOT NULL, assessment_id TEXT NOT NULL, record TEXT NOT NULL, content BLOB NOT NULL,
    PRIMARY KEY(tenant_id, image_id),
    FOREIGN KEY(tenant_id, wound_id) REFERENCES sprint_wounds(tenant_id, wound_id)
);
CREATE TABLE IF NOT EXISTS sprint_assessments(
    tenant_id TEXT NOT NULL, assessment_id TEXT NOT NULL, patient_id TEXT NOT NULL,
    wound_id TEXT NOT NULL, revision INTEGER NOT NULL, record TEXT NOT NULL,
    PRIMARY KEY(tenant_id, assessment_id),
    FOREIGN KEY(tenant_id, wound_id) REFERENCES sprint_wounds(tenant_id, wound_id)
);
CREATE TABLE IF NOT EXISTS sprint_assessment_versions(
    tenant_id TEXT NOT NULL, assessment_id TEXT NOT NULL, revision INTEGER NOT NULL,
    record TEXT NOT NULL, PRIMARY KEY(tenant_id, assessment_id, revision)
);
CREATE TABLE IF NOT EXISTS sprint_analyses(
    tenant_id TEXT NOT NULL, assessment_id TEXT NOT NULL, image_id TEXT NOT NULL,
    assessment_revision INTEGER NOT NULL, summary TEXT NOT NULL,
    PRIMARY KEY(tenant_id, assessment_id, image_id),
    FOREIGN KEY(tenant_id, assessment_id) REFERENCES sprint_assessments(tenant_id, assessment_id)
);
