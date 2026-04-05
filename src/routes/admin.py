from fastapi import APIRouter, Depends, status, Request
from src.security.cookies import require_admin_access
from src.db import db_connection
from asyncpg import Connection
from src.ratelimit import limiter


router = APIRouter(dependencies=[Depends(require_admin_access)])


@router.post("/refresh-mv-catalog", status_code=status.HTTP_200_OK)
@limiter.limit("32/minute")
async def refresh_mv_catalog(request: Request, conn: Connection = Depends(db_connection)):
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_manhwa_catalog;")