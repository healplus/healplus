"""Run with python -m src.analysis_intake.worker (separate from the HTTP process)."""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import threading
import time
from typing import Callable

from PIL import Image

from .repository import IntakeRepository
from src.image_quality.decoder import decode_attachment


class HealAnalyzer:
    def __init__(self):
        self.analyzer = None

    def __call__(self, image: dict, record: dict) -> dict:
        from packages.clinical_domain.validation import ValidatedImage
        from packages.clinical_domain.wound_analysis import WoundAnalysisService
        from src.processing.clinical_wound_analyzer_core import ClinicalWoundAnalyzer

        if self.analyzer is None:
            self.analyzer = ClinicalWoundAnalyzer()
        decoded = decode_attachment(
            {"contentType": image["content_type"], "data": base64.b64encode(image["content"]).decode("ascii")}
        )
        # The canonical service expects normalized pixels; preserve the original separately.
        buffer = io.BytesIO()
        Image.fromarray(decoded.rgb).save(buffer, format="PNG")
        validated = ValidatedImage(
            buffer.getvalue(), "image/png", ".png", decoded.width, decoded.height, "normalized.png"
        )
        result = WoundAnalysisService(lambda: self.analyzer).analyze(
            validated, analysis_id=record["id"], patient_id=record["patient_ref"].split("/", 1)[1], evaluation_id=None
        )
        result["links"] = {"self": f"/api/v1/analyses/{record['id']}/result"}
        result["metadata"]["original_sha256"] = image["sha256"]
        return result


class IntakeWorker:
    def __init__(
        self,
        repository: IntakeRepository,
        analyzer: Callable | None = None,
        *,
        lease_seconds: int = 120,
        max_attempts: int = 3,
    ):
        self.repository = repository
        self.analyzer = analyzer or HealAnalyzer()
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts

    def run_once(self) -> bool:
        record = self.repository.claim(lease_seconds=self.lease_seconds, max_attempts=self.max_attempts)
        if not record:
            return False
        stop, lost = threading.Event(), threading.Event()

        def heartbeat():
            while not stop.wait(max(0.1, self.lease_seconds / 3)):
                try:
                    if not self.repository.renew(record, self.lease_seconds):
                        lost.set()
                        return
                except Exception:
                    lost.set()
                    return

        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()
        try:
            images = self.repository.images(record["id"])
            if not images:
                raise ValueError("missing images")
            results = []
            for image in images:
                if lost.is_set() or hashlib.sha256(image["content"]).hexdigest() != image["sha256"]:
                    raise ValueError("custody or lease failure")
                results.append({"mediaId": image["media_id"], "result": self.analyzer(image, record)})
            result = {
                "analysisId": record["id"],
                "status": "COMPLETED",
                "images": results,
                "clinicianReviewRequired": True,
            }
            json.dumps(result, allow_nan=False)
            self.repository.finish(record, result=result, max_attempts=self.max_attempts)
        except Exception:
            # Do not retain exception text or stack traces containing clinical input.
            self.repository.finish(record, max_attempts=self.max_attempts)
        finally:
            stop.set()
            thread.join(timeout=5)
        return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Process at most one queued batch and exit")
    args = parser.parse_args()
    worker = IntakeWorker(IntakeRepository())
    while True:
        try:
            processed = worker.run_once()
        except Exception:
            if args.once:
                raise SystemExit("Intake queue unavailable") from None
            processed = False
        if args.once:
            return
        if not processed:
            time.sleep(2)


if __name__ == "__main__":
    main()
