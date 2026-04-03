from src.schemas.chapter import ChapterCreate, ChapterUpdate, ChapterResponse
from fastapi import APIRouter, Query, Path, status, Depends, HTTPException
from asyncpg import Connection, UniqueViolationError
from src.db import db_connection
from typing import Optional
from uuid import UUID

router = APIRouter()


@router.get(
    "/manhwas/{manhwa_id}/chapters", 
    response_model=list[ChapterResponse],
    tags=["Chapters"]
)
async def list_manhwa_chapters(
    manhwa_id: UUID = Path(...),
    is_published: Optional[bool] = Query(default=True, description="Filter by publish status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    conn: Connection = Depends(db_connection),
):
    """
    List all chapters for a given manhwa, ordered by chapter number descending.
    """
    conditions = ["manhwa_id = $1"]
    params = [manhwa_id]

    if is_published is not None:
        params.append(is_published)
        conditions.append(f"is_published = ${len(params)}")

    where_clause = " AND ".join(conditions)
    params.extend([limit, offset])

    query = f"""
        SELECT * FROM chapters 
        WHERE {where_clause} 
        ORDER BY num DESC 
        LIMIT ${len(params) - 1} 
        OFFSET ${len(params)}
    """
    
    rows = await conn.fetch(query, *params)
    return [dict(r) for r in rows]


@router.get("/chapters/{chapter_id}", response_model=ChapterResponse, tags=["Chapters"])
async def get_chapter(
    chapter_id: UUID = Path(...),
    conn: Connection = Depends(db_connection),
):
    """
    Get chapter details by its unique ID.
    """
    query = "SELECT * FROM chapters WHERE id = $1"
    row = await conn.fetchrow(query, chapter_id)
    
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found.")
        
    return dict(row)


@router.patch("/chapters/{chapter_id}", response_model=ChapterResponse, tags=["Chapters"])
async def update_chapter(
    chapter_id: UUID = Path(...),
    chapter_update: ChapterUpdate = Depends(),
    conn: Connection = Depends(db_connection),
):
    """
    Partially update a chapter's data (e.g., change publish status or title).
    """
    update_data = chapter_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid fields provided for update.")

    set_clauses = []
    params = []
    
    for key, value in update_data.items():
        params.append(value)
        set_clauses.append(f"{key} = ${len(params)}")

    # Add updated_at timestamp
    set_clauses.append("updated_at = NOW()")
    
    params.append(chapter_id)
    set_query = ", ".join(set_clauses)
    
    query = f"""
        UPDATE chapters 
        SET {set_query} 
        WHERE id = ${len(params)} 
        RETURNING *
    """
    
    try:
        row = await conn.fetchrow(query, *params)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found.")
        return dict(row)
    except UniqueViolationError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail="Chapter with this sort_order or num already exists for this manhwa."
        )


@router.delete("/chapters/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Chapters"])
async def delete_chapter(
    chapter_id: UUID = Path(...),
    conn: Connection = Depends(db_connection),
):
    """
    Delete a chapter.
    """
    query = "DELETE FROM chapters WHERE id = $1 RETURNING id"
    deleted = await conn.fetchval(query, chapter_id)
    
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found.")


@router.post("/chapters/{chapter_id}/view", status_code=status.HTTP_200_OK, tags=["Chapters"])
async def increment_chapter_view(
    chapter_id: UUID = Path(...),
    conn: Connection = Depends(db_connection),
):
    """
    Increment the view counter for a specific chapter.
    """
    query = "UPDATE chapters SET views = views + 1 WHERE id = $1 RETURNING views"
    new_views = await conn.fetchval(query, chapter_id)
    
    if new_views is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found.")
        
    return {"views": new_views}