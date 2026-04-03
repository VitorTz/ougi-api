from src.schemas.manhwas import ManhwaCatalogResponse
from fastapi import APIRouter, Query, status, Depends
from fastapi.exceptions import HTTPException
from typing import Optional
from asyncpg import Connection
from src.db import db_connection


router = APIRouter()


@router.get("/", response_model=ManhwaCatalogResponse)
async def get_manhwa(
    id: Optional[str] = Query(default=None),
    title: Optional[str] = Query(default=None),
    conn: Connection = Depends(db_connection),
):
    if not id and not title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Either 'id' or 'title' must be provided."
        )

    if id:
        row = await conn.fetchrow(
            """
                SELECT 
                    * 
                FROM 
                    mv_manhwa_catalog 
                WHERE 
                    id = $1::uuid
                """,
            id,
        )
    else:
        row = await conn.fetchrow(
            """
                SELECT 
                    * 
                FROM 
                    mv_manhwa_catalog 
                WHERE 
                    title % $1 
                ORDER BY 
                    similarity(title, $1) DESC 
                LIMIT 
                    1
            """,
            title,
        )

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manhwa not found.")

    return ManhwaCatalogResponse(**row)


@router.get("/search", response_model=list[ManhwaCatalogResponse])
async def search_manhwa(
    title: Optional[str] = Query(default=None),
    genres: Optional[list[str]] = Query(default=None),
    exclude_warnings: Optional[list[str]] = Query(default=None),
    scans: Optional[list[str]] = Query(default=None),
    tags: Optional[list[str]] = Query(default=None),
    is_adult: Optional[bool] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    order_by: str = Query(default="last_chapter_updated_at", enum=["last_chapter_updated_at", "total_views", "avg_rating", "created_at"]),
    limit: int = Query(default=32, ge=1, le=64),
    offset: int = Query(default=0, ge=0),
    conn: Connection = Depends(db_connection),
):
    conditions = []
    params = []

    if title:
        params.append(title)
        conditions.append(f"title % ${len(params)}")

    if genres:
        params.append(genres)
        conditions.append(f"genres @> ${len(params)}::citext[]")

    if exclude_warnings:
        params.append(exclude_warnings)
        conditions.append(f"NOT (content_warnings && ${len(params)}::citext[])")

    if scans:
        params.append(scans)
        conditions.append(f"scans @> ${len(params)}::citext[]")

    if tags:
        params.append(tags)
        conditions.append(f"tags @> ${len(params)}::citext[]")

    if is_adult is not None:
        params.append(is_adult)
        conditions.append(f"is_adult = ${len(params)}")

    if status_filter:
        params.append(status_filter)
        conditions.append(f"status = ${len(params)}::manhwa_status_type")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    allowed_order = {"last_chapter_updated_at", "total_views", "avg_rating", "created_at"}
    order_col = order_by if order_by in allowed_order else "last_chapter_updated_at"

    params.extend([limit, offset])
    query = f"""
        SELECT 
            *
        FROM 
            mv_manhwa_catalog
        {where_clause}
        ORDER BY 
            {order_col} DESC NULLS LAST
        LIMIT 
            ${len(params) - 1}
        OFFSET 
            ${len(params)}
    """

    rows = await conn.fetch(query, *params)

    return [ManhwaCatalogResponse(**r) for r in rows]