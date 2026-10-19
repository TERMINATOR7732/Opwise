"""Opwise API transport layer."""

from typing import Any


def __getattr__(name: str) -> Any:
    if name == "api_v1_router":
        from opwise.api.routers import api_v1_router

        return api_v1_router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["api_v1_router"]
