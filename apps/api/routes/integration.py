"""Compatibility proxy for the former integration route module."""

from apps.heal_plus.api.routes import integration as _implementation

integration_api = _implementation.integration_api
get_integration_service_status = _implementation.get_integration_service_status

__all__ = ["get_integration_service_status", "integration_api"]


def __getattr__(name: str):
    return getattr(_implementation, name)
