from src.security.cookies import require_admin_access
from fastapi import APIRouter, Depends, status
from src.db import db_connection
from asyncpg import Connection


router = APIRouter(dependencies=[Depends(require_admin_access)])


@router.post("/refresh-mv-catalog", status_code=status.HTTP_200_OK)
async def refresh_mv_catalog(conn: Connection = Depends(db_connection)):
    await conn.execute(
        "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_manhwa_catalog;"
    )