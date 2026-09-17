# -*- coding: utf-8 -*-
"""Relational repository for image quality evaluations, patient linkages, and FHIR trace."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_DB_PATH = Path("data") / "quality_evaluations.db"


@dataclass
class QualityEvaluationRecord:
    id: str
    image_id: str
    patient_id: Optional[str]
    encounter_id: Optional[str]
    storage_key: str
    sha256: str
    mime_type: str
    decision: str
    status_code: str
    metrics: Dict[str, float]
    reasons: List[Dict[str, str]]
    fhir_media_id: Optional[str] = None
    fhir_observation_id: Optional[str] = None
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class QualityRepository:
    """Thread-safe persistent store for image quality evaluations."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quality_evaluations (
                    id TEXT PRIMARY KEY,
                    image_id TEXT NOT NULL,
                    patient_id TEXT,
                    encounter_id TEXT,
                    storage_key TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    status_code TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    reasons_json TEXT NOT NULL,
                    fhir_media_id TEXT,
                    fhir_observation_id TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_quality_eval_patient ON quality_evaluations (patient_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_quality_eval_encounter ON quality_evaluations (encounter_id)"
            )
            conn.commit()

    def save_evaluation(self, record: QualityEvaluationRecord) -> QualityEvaluationRecord:
        if not record.created_at:
            record.created_at = datetime.now(timezone.utc).isoformat()

        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO quality_evaluations (
                    id, image_id, patient_id, encounter_id, storage_key, sha256,
                    mime_type, decision, status_code, metrics_json, reasons_json,
                    fhir_media_id, fhir_observation_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.image_id,
                    record.patient_id,
                    record.encounter_id,
                    record.storage_key,
                    record.sha256,
                    record.mime_type,
                    record.decision,
                    record.status_code,
                    json.dumps(record.metrics),
                    json.dumps(record.reasons, ensure_ascii=False),
                    record.fhir_media_id,
                    record.fhir_observation_id,
                    record.created_at,
                ),
            )
            conn.commit()
        return record

    def get_evaluation(self, evaluation_id: str) -> Optional[QualityEvaluationRecord]:
        with self._lock, self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM quality_evaluations WHERE id = ?",
                (evaluation_id,),
            ).fetchone()
            if not row:
                return None
            return self._row_to_record(row)

    def list_evaluations_by_patient(self, patient_id: str) -> List[QualityEvaluationRecord]:
        with self._lock, self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM quality_evaluations WHERE patient_id = ? ORDER BY created_at DESC",
                (patient_id,),
            ).fetchall()
            return [self._row_to_record(row) for row in rows]

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> QualityEvaluationRecord:
        return QualityEvaluationRecord(
            id=row["id"],
            image_id=row["image_id"],
            patient_id=row["patient_id"],
            encounter_id=row["encounter_id"],
            storage_key=row["storage_key"],
            sha256=row["sha256"],
            mime_type=row["mime_type"],
            decision=row["decision"],
            status_code=row["status_code"],
            metrics=json.loads(row["metrics_json"]),
            reasons=json.loads(row["reasons_json"]),
            fhir_media_id=row["fhir_media_id"],
            fhir_observation_id=row["fhir_observation_id"],
            created_at=row["created_at"],
        )


def get_quality_repository(db_path: Path | str | None = None) -> QualityRepository:
    path = db_path or os.getenv("QUALITY_DB_PATH")
    return QualityRepository(path)
