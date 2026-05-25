from fastapi import APIRouter, status, Request, Path, Depends
from src.dependencies import get_limiter
from src.schemas.views import AllowedMaterializedViews
from asyncpg import Connection
from src import db


router = APIRouter(prefix="/database")
limiter = get_limiter()


@router.post("/refresh_mv/{mv_name}", status_code=status.HTTP_200_OK)
@limiter.limit("32/minute")
async def refresh_materialized_view(
    request: Request,
    mv_name: AllowedMaterializedViews = Path(
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
    
    view_name = mv_name.value if hasattr(mv_name, 'value') else mv_name    
    return {
        "message": f"Materialized view '{view_name}' has been successfully refreshed."
    }