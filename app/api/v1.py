from fastapi import APIRouter

from app import auth


def build_v1_router() -> APIRouter:
    """
    Build the /api/v1 router.

    This router is incremental. Each module (auth, users, documents, etc.)
    appends its own router here in the task that introduces that module's API.
    As of T-503, it returns an empty router.
    """
    router = APIRouter(prefix="/api/v1")

    router.include_router(auth.api.router, prefix="/auth", tags=["auth"])

    return router
