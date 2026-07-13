"""ASGI application factory for the canonical Social Media V2 backend."""

from __future__ import annotations

from fastapi import FastAPI

from app.api import create_api_router
from app.core import WritePolicy, load_settings


def create_app() -> FastAPI:
    settings = load_settings()
    policy = WritePolicy.from_settings(settings)
    application = FastAPI(
        title="Social Media V2",
        version="0.1.0",
        redirect_slashes=False,
    )
    application.state.settings = settings
    application.state.write_policy = policy
    application.include_router(create_api_router(settings, policy))
    return application


app = create_app()
