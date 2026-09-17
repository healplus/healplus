"""Compatibility shim for ``apps.heal_plus.api.app``."""

from __future__ import annotations

import os

from apps.heal_plus.api.app import app, create_app

__all__ = ["app", "create_app"]



if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_ENV", "development").lower() == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)
