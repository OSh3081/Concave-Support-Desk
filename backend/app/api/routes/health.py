from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Return a simple liveness response without requiring the database."""
    return {"status": "success"}
