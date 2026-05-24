from fastapi import (
    APIRouter, 
    Query, 
    Path, 
    status, 
    Depends, 
    Request, 
    BackgroundTasks
)
from src.schemas.chapter import ChapterResponse
from src.schemas.pagination import Pagination
from src.tables import chapters as chapter_table
from src.dependencies import get_limiter
from src.db import db_connection
from asyncpg import Connection
from typing import Optional
from uuid import UUID


router = APIRouter(
    prefix='/chapters', 
    tags=['chapters']
)
limiter = get_limiter()


@router.get(
    "/manhwas/{identifier}/chapters", 
    response_model=Pagination[ChapterResponse],
    summary="List Manhwa Chapters",
    description="Retrieves a paginated list of chapters for a specific manhwa. The manhwa can be identified intelligently by either its unique UUID or its URL-friendly slug. The list is automatically ordered by chapter number in descending order (latest chapters first)."
)
@limiter.limit("32/minute")
async def list_manhwa_chapters(
    request: Request,
    identifier: str = Path(
        ..., 
        description="The UUID or slug of the manhwa."
    ),
    is_published: Optional[bool] = Query(
        default=True, 
        description="Filter by publish status. Use true for public chapters, false for drafts, or omit to get all."
    ),
    limit: int = Query(
        default=32, 
        ge=1, 
        le=64,
        description="Maximum number of chapters to return per page."
    ),
    offset: int = Query(
        default=0, 
        ge=0,
        description="Number of chapters to skip for pagination."
    ),
    conn: Connection = Depends(db_connection),
):    
    return await chapter_table.get_chapters_from_manhwa(
        identifier=identifier,
        is_published=is_published,
        limit=limit,
        offset=offset,
        conn=conn
    )


@router.post(
    "/chapters/{chapter_id}/view", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Increment Chapter View",
    description="Increments the view count for a specific chapter. This operation is dispatched as a background task to ensure zero latency for the reader, returning a 204 No Content immediately."
)
@limiter.limit("32/minute")
async def increment_chapter_view(
    request: Request,
    background_tasks: BackgroundTasks,
    chapter_id: UUID = Path(
        ..., 
        description="The exact UUID of the chapter being read."
    )
):
    # Dispatch the database update to the background
    background_tasks.add_task(
        chapter_table.increment_chapter_view_bg,
        chapter_id=chapter_id
    )