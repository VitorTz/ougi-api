from src.schemas.chapter import ChapterResponse
from fastapi import APIRouter, Query, Path, status, Depends, HTTPException, Request, BackgroundTasks
from src.tables import chapters as chapter_table
from src.ratelimit import limiter
from src.db import db_connection
from asyncpg import Connection
from typing import Optional, Union
from uuid import UUID
from src.schemas.pagination import Pagination


router = APIRouter(prefix='/chapters', tags=['chapters'])


@router.get(
    "/manhwas/{identifier}/chapters", 
    response_model=Pagination[ChapterResponse]
)
@limiter.limit("32/minute")
async def list_manhwa_chapters(
    request: Request,
    identifier: Union[UUID, str] = Path(...),
    is_published: Optional[bool] = Query(default=True, description="Filter by publish status"),
    limit: int = Query(default=32, ge=1, le=64),
    offset: int = Query(default=0, ge=0),
    conn: Connection = Depends(db_connection),
):    
    return await chapter_table.get_chapters_from_manhwa(
        identifier,
        is_published,
        limit,
        offset,
        conn
    )


@router.delete("/chapters/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("32/minute")
async def delete_chapter(
    request: Request,
    chapter_id: UUID = Path(...),
    conn: Connection = Depends(db_connection),
):
    deleted = await chapter_table.delete_chapter(chapter_id, conn)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found.")


@router.post("/chapters/{chapter_id}/view", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("32/minute")
async def increment_chapter_view(
    request: Request,
    background_tasks: BackgroundTasks,
    chapter_id: UUID = Path(...)
):
    background_tasks.add_task(
        chapter_table.increment_chapter_view_bg,
        chapter_id=chapter_id
    )