"""Self-service integration API boundaries."""

from .oauth_channels import create_oauth_channel_router

__all__ = ["create_oauth_channel_router"]
