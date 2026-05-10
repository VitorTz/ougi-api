from src.schemas.chapter import ChapterUpdate, ChapterResponse
from fastapi import APIRouter, Query, Path, status, Depends, HTTPException, Request
from src.tables import chapters as chapter_table
from src.ratelimit import limiter
from src.db import db_connection
from asyncpg import Connection
from typing import Optional


router = APIRouter(prefix='/chapters', tags=['chapters'])


@router.get(
    "/manhwas/{manhwa_id}/chapters", 
    response_model=list[ChapterResponse]
)
@limiter.limit("32/minute")
async def list_manhwa_chapters(
    request: Request,
    manhwa_id: str = Path(...),
    is_published: Optional[bool] = Query(default=True, description="Filter by publish status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    conn: Connection = Depends(db_connection),
):
    """
    List all chapters for a given manhwa, ordered by chapter number descending.
    """
    return await chapter_table.get_chapters_from_manhwa(
        manhwa_id,
        is_published,
        limit,
        offset,
        conn
    )


@router.get("/chapters/{chapter_id}", response_model=ChapterResponse)
@limiter.limit("32/minute")
async def get_chapter(
    request: Request,
    chapter_id: str = Path(...),
    conn: Connection = Depends(db_connection),
):
    """
    Get chapter details by its unique ID.
    """
    chapter: ChapterResponse | None = await chapter_table.get_chapter(chapter_id, conn)
    if not chapter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found.")
    return chapter


@router.patch("/chapters/{chapter_id}", response_model=ChapterResponse)
@limiter.limit("32/minute")
async def update_chapter(
    request: Request,
    chapter_id: str = Path(...),
    chapter_update: ChapterUpdate = Depends(),
    conn: Connection = Depends(db_connection),
):
    """
    Partially update a chapter's data (e.g., change publish status or title).
    """
    if not chapter_update.model_dump(exclude_unset=True):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid fields provided for update.")

    chapter: ChapterResponse | None = await chapter_table.update_chapter(chapter_id, chapter_update, conn)
    
    if not chapter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found.")
        
    return chapter


@router.delete("/chapters/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("32/minute")
async def delete_chapter(
    request: Request,
    chapter_id: str = Path(...),
    conn: Connection = Depends(db_connection),
):
    """
    Delete a chapter.
    """
    deleted = await chapter_table.delete_chapter(chapter_id, conn)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found.")


@router.post("/chapters/{chapter_id}/view", status_code=status.HTTP_200_OK)
@limiter.limit("32/minute")
async def increment_chapter_view(
    request: Request,
    chapter_id: str = Path(...),
    conn: Connection = Depends(db_connection),
):
    """
    Increment the view counter for a specific chapter.
    """
    await chapter_table.increment_chapter_view(chapter_id, conn)