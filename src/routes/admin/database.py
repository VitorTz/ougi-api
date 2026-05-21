from fastapi import APIRouter, status, Request, Path, Depends
from asyncpg import Connection
from src.dependencies import get_limiter
from src import db


router = APIRouter()
limiter = get_limiter()

@router.post("/database/refresh_mv/{mv_name}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("32/minute")
async def refresh_materialized_view(
    request: Request,
    mv_name: str = Path(
        ..., 
        title="Materialized View Name",
        description="The exact name of the materialized view to be refreshed in the database.",
        examples=["mv_manhwa_catalog", "mv_user_statistics"]
    ),
    conn: Connection = Depends(db.db_connection)
):
    """
    Triggers a manual refresh of a specific materialized view to update its cached data.
    """
    await db.refresh_view(mv_name, conn)