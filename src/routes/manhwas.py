from src.schemas.manhwas import ManhwaCatalogResponse, ManhwaSearchResponse
from fastapi import APIRouter, Query, Depends, Request
from src.exceptions import ResourceNotFoundException
from typing import Optional
from asyncpg import Connection
from src.db import db_connection
from src.dependencies import get_limiter
from src.schemas.pagination import Pagination
from src.tables import manwhas as manhwas_table


router = APIRouter(
    prefix='/manhwas', 
    tags=['manhwas']
)
limiter = get_limiter()


@router.get("/", response_model=ManhwaCatalogResponse)
@limiter.limit("32/minute")
async def get_manhwa(
    request: Request,
    identifier: str = Query(
        ...,
        title="Manhwa Identifier",
        description="The unique identifier of the manhwa. It can be either the exact UUID or the SEO-friendly text slug.",
        examples=["stop-smoking", "550e8400-e29b-41d4-a716-446655440000"]
    ),
    conn: Connection = Depends(db_connection),
):    
    """
    Retrieves the complete catalog information of a specific manhwa by its ID or slug.
    """
    manhwa: ManhwaCatalogResponse | None = await manhwas_table.get_manhwa(identifier, conn)
    if not manhwa: raise ResourceNotFoundException("Manhwa")
    return manhwa


@router.get("/search", response_model=Pagination[ManhwaSearchResponse])
@limiter.limit("32/minute")
async def search_manhwa(
    request: Request,
    title: Optional[str] = Query(
        default=None, 
        description="Search by exact or partial manhwa title"
    ),
    genres: list[str] = Query(
        default=[],
        description="Filter by genres (repeat param: ?genres=Action&genres=Fantasy)"
    ),
    exclude_warnings: list[str] = Query(
        default=[],
        description="Exclude specific content warnings (repeat param: ?exclude_warnings=Gore&exclude_warnings=Tragedy)"
    ),
    scans: list[str] = Query(
        default=[],
        description="Filter by scanlator groups (repeat param: ?scans=Asura&scans=Flame)"
    ),
    tags: list[str] = Query(
        default=[],
        description="Filter by specific tags (repeat param: ?tags=System&tags=Magic)"
    ),
    status: Optional[str] = Query(
        default=None,
        description="Filter by publication status (e.g., Ongoing, Completed)"
    ),
    order_by: str = Query(
        default="last_chapter_updated_at", 
        enum=["last_chapter_updated_at", "total_views", "avg_rating", "created_at"],
        description="Define the sorting criteria for the results"
    ),
    limit: int = Query(default=32, ge=1, le=64),
    offset: int = Query(default=0, ge=0),
    conn: Connection = Depends(db_connection),
):
    """
    Advanced search endpoint for the manhwa catalog. 
    Allows filtering by multiple criteria including repeating array parameters.
    """
    return await manhwas_table.search_manhwa(
        conn=conn,
        title=title,
        genres=genres,
        exclude_warnings=exclude_warnings,
        scans=scans,
        tags=tags,
        status=status,
        order_by=order_by,
        limit=limit,
        offset=offset
    )