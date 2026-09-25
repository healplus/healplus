"""Atomic image custody and persistent queue, shared by API and worker processes."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid

from src.image_quality.decoder import ImageInputError


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class IntakeRepository:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or os.getenv("HEAL_INTAKE_DB_PATH") or "data/intake/analyses.db").resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(
                Path(__file__).with_name("migrations").joinpath("001_intake.sql").read_text(encoding="utf-8")
            )
            db.execute("PRAGMA user_version=1")
        if os.name != "nt":
            self.path.chmod(0o600)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, analysis_id: str, owner_id: str) -> dict | None:
        with self.connection() as db:
            row = db.execute(
                "SELECT * FROM intake_analyses WHERE id=? AND owner_id=?", (analysis_id, owner_id)
            ).fetchone()
            return dict(row) if row else None

    def replay(self, owner_id: str, key: str | None, request_hash: str) -> dict | None:
        if not key:
            return None
        with self.connection() as db:
            row = db.execute(
                "SELECT * FROM intake_analyses WHERE owner_id=? AND idempotency_key=?", (owner_id, key)
            ).fetchone()
        if row and row["request_hash"] != request_hash:
            raise ImageInputError("Idempotency-Key já usada com outro payload.", 409)
        return dict(row) if row else None

    def save(
        self,
        *,
        owner_id: str,
        key: str | None,
        request_hash: str,
        bundle: dict,
        images: list[dict],
        quality: list[dict],
        accepted: bool,
    ) -> dict:
        analysis_id, now = str(uuid.uuid4()), timestamp()
        media = [e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "Media"]
        for item in media:
            item["content"].pop("data", None)
            if accepted:
                item["content"]["url"] = f"/api/v1/analyses/{analysis_id}/images/{item['id']}"
        final_status = "QUEUED" if accepted else "REJECTED"
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = (
                db.execute(
                    "SELECT * FROM intake_analyses WHERE owner_id=? AND idempotency_key=?", (owner_id, key)
                ).fetchone()
                if key
                else None
            )
            if existing:
                if existing["request_hash"] != request_hash:
                    raise ImageInputError("Idempotency-Key já usada com outro payload.", 409)
                return dict(existing)
            pending = db.execute(
                "SELECT count(*) FROM intake_analyses WHERE owner_id=? AND status IN ('QUEUED','PROCESSING')",
                (owner_id,),
            ).fetchone()[0]
            if pending >= 100:
                raise ImageInputError("Fila do usuário cheia; aguarde as análises em andamento.", 429)
            db.execute(
                """INSERT INTO intake_analyses
                (id,owner_id,idempotency_key,request_hash,patient_ref,encounter_ref,bundle_id,bundle_json,quality_json,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    analysis_id,
                    owner_id,
                    key,
                    request_hash,
                    media[0]["subject"]["reference"],
                    media[0].get("encounter", {}).get("reference"),
                    bundle["id"],
                    json.dumps(bundle),
                    json.dumps(quality),
                    final_status,
                    now,
                    now,
                ),
            )
            if accepted:
                for image in images:
                    db.execute(
                        "INSERT INTO intake_images VALUES (?,?,?,?,?,?,?)",
                        (
                            analysis_id,
                            image["id"],
                            image["raw"],
                            "image/jpeg",
                            image["sha256"],
                            image["width"],
                            image["height"],
                        ),
                    )
                db.execute(
                    "INSERT INTO intake_events(analysis_id,status,created_at) VALUES (?,?,?)",
                    (analysis_id, "ACCEPTED", now),
                )
            db.execute(
                "INSERT INTO intake_events(analysis_id,status,created_at) VALUES (?,?,?)",
                (analysis_id, final_status, now),
            )
        return self.get(analysis_id, owner_id)  # type: ignore[return-value]

    def images(self, analysis_id: str) -> list[dict]:
        with self.connection() as db:
            return [
                dict(r)
                for r in db.execute("SELECT * FROM intake_images WHERE analysis_id=? ORDER BY media_id", (analysis_id,))
            ]

    def events(self, analysis_id: str) -> list[dict]:
        with self.connection() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT status,created_at FROM intake_events WHERE analysis_id=? ORDER BY sequence", (analysis_id,)
                )
            ]

    def claim(self, *, lease_seconds: int = 120, max_attempts: int = 3) -> dict | None:
        now = time.time()
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            expired = db.execute(
                "SELECT id,attempts FROM intake_analyses WHERE status='PROCESSING' AND lease_until<=?", (now,)
            ).fetchall()
            for row in expired:
                state = "FAILED" if row["attempts"] >= max_attempts else "QUEUED"
                self._transition(db, row["id"], state)
                db.execute(
                    "UPDATE intake_analyses SET error_code='worker_interrupted',lease_token=NULL,lease_until=NULL WHERE id=?",
                    (row["id"],),
                )
            row = db.execute(
                "SELECT * FROM intake_analyses WHERE status='QUEUED' AND available_at<=? ORDER BY created_at LIMIT 1",
                (now,),
            ).fetchone()
            if not row:
                return None
            token = str(uuid.uuid4())
            self._transition(db, row["id"], "PROCESSING")
            db.execute(
                "UPDATE intake_analyses SET attempts=attempts+1,lease_token=?,lease_until=? WHERE id=?",
                (token, now + lease_seconds, row["id"]),
            )
            return dict(db.execute("SELECT * FROM intake_analyses WHERE id=?", (row["id"],)).fetchone())

    @staticmethod
    def _transition(db, analysis_id: str, status: str) -> None:
        now = timestamp()
        db.execute("UPDATE intake_analyses SET status=?,updated_at=? WHERE id=?", (status, now, analysis_id))
        db.execute(
            "INSERT INTO intake_events(analysis_id,status,created_at) VALUES (?,?,?)", (analysis_id, status, now)
        )

    def renew(self, record: dict, lease_seconds: int) -> bool:
        with self.connection() as db:
            return (
                db.execute(
                    "UPDATE intake_analyses SET lease_until=? WHERE id=? AND lease_token=? AND status='PROCESSING' AND lease_until>?",
                    (time.time() + lease_seconds, record["id"], record["lease_token"], time.time()),
                ).rowcount
                == 1
            )

    def finish(self, record: dict, *, result: dict | None = None, max_attempts: int = 3) -> bool:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute(
                "SELECT * FROM intake_analyses WHERE id=? AND lease_token=? AND status='PROCESSING' AND lease_until>?",
                (record["id"], record["lease_token"], time.time()),
            ).fetchone()
            if not current:
                return False
            state = "COMPLETED" if result is not None else "FAILED" if current["attempts"] >= max_attempts else "QUEUED"
            self._transition(db, record["id"], state)
            db.execute(
                "UPDATE intake_analyses SET result_json=?,error_code=?,available_at=?,lease_token=NULL,lease_until=NULL WHERE id=?",
                (
                    json.dumps(result, allow_nan=False) if result is not None else None,
                    None if result is not None else "analysis_unavailable",
                    time.time() + 5 * current["attempts"],
                    record["id"],
                ),
            )
            return True
