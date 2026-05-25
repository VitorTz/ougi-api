from src.exceptions import (
    DatabaseException, 
    DuplicateRecordError, 
    EmptyUpdateException
)
from src.schemas.chapter import ChapterResponse, ChapterUpdate
from asyncpg import Connection, UniqueViolationError
from src.schemas.pagination import Pagination
from src.cloudflare import CloudflareR2Bucket
from src.tables import logs as logs_table
from uuid import UUID
from src import util
from src import db


async def get_chapter_by_id(chapter_id: str | UUID, conn: Connection) -> ChapterResponse | None:
    query = """
        SELECT  
            id,
            cover_path,
            num,
            title,
            views
        FROM
            chapters
        WHERE   
            id = $1::uuid
    """
    return await db.fetchrow(query, ChapterResponse, conn, chapter_id)


async def get_chapters_from_manhwa(
    identifier: str | UUID, 
    is_published: bool | None,
    limit: int,
    offset: int,
    conn: Connection
) -> Pagination[ChapterResponse]:
    params = [str(identifier)]
    if util.is_uuid(identifier):
        base_query = "FROM chapters c WHERE c.manhwa_id = $1::uuid"
    else:
        base_query = """
            FROM 
                chapters c
            JOIN 
                manhwas m ON c.manhwa_id = m.id 
            WHERE 
                m.slug = $1
        """    
    
    if is_published is not None:
        params.append(is_published)
        base_query += f" AND c.is_published = ${len(params)}"
    
    params.extend([limit, offset])    
        
    query = f"""
        SELECT 
            c.id,
            c.cover_path,
            c.num,
            c.title,
            c.views,
            COUNT(*) OVER() AS total_count
        {base_query} 
        ORDER BY 
            c.num DESC 
        LIMIT 
            ${len(params) - 1} 
        OFFSET 
            ${len(params)}
    """
    
    try:
        return await db.fetch_pagination(
            query, 
            ChapterResponse, 
            limit, 
            offset, 
            conn, 
            *params
        )
    
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while fetching the chapters.",
            original_error=e,
            query=query,
            params=params,
            additional_context={
                "action": "list_manhwa_chapters", 
                "identifier": str(identifier)
            }
        )

    
async def update_chapter(payload: ChapterUpdate, conn: Connection) -> ChapterResponse | None:
    update_data = payload.model_dump(exclude_unset=True, exclude={"id"})
    
    if not update_data: 
        raise EmptyUpdateException()

    set_clauses = []
    params = []
    
    for key, value in update_data.items():
        params.append(value)
        set_clauses.append(f"{key} = ${len(params)}")

    # Automatically add updated_at timestamp
    set_clauses.append("updated_at = NOW()")
    
    params.append(payload.id)
    set_query = ", ".join(set_clauses)
        
    query = f"""
        UPDATE 
            chapters 
        SET 
            {set_query} 
        WHERE 
            id = ${len(params)}::uuid 
        RETURNING 
            id,
            cover_path,
            num,
            title,
            views
    """
    
    try:
        return await db.fetchrow(query, ChapterResponse, conn, *params)
    except UniqueViolationError as e:
        raise DuplicateRecordError("A chapter with this number or sort_order already exists for this manhwa.")
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while updating the chapter.",
            original_error=e,
            query=query,
            params=params,
            additional_context={"action": "update_chapter", "chapter_id": str(payload.id)}
        )
    

async def update_chapter_cover(
    chapter_id: str | UUID,
    cover_url: str,
    conn: Connection
) -> None:
    """
    Update the cover_path of a chapter in the database.
    
    Args:
        chapter_id: UUID of the chapter
        cover_url: New cover URL/path from R2
        conn: Database connection
    
    """
    query = """
        UPDATE 
            chapters 
        SET 
            cover_path = $1,
            updated_at = NOW()
        WHERE 
            id = $2::uuid
    """
    
    params = (cover_url, str(chapter_id))
    
    try:
        await conn.execute(query, *params)
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while updating the chapter cover.",
            original_error=e,
            query=query,
            params=params,
            additional_context={
                "action": "update_chapter_cover",
                "chapter_id": str(chapter_id)
            }
        )


async def delete_chapter_cover(
    chapter_id: str | UUID,
    conn: Connection
) -> bool:
    """
    Delete chapter cover from R2 and reset database.
    
    Args:
        chapter_id: UUID of the chapter
        conn: Database connection
        
    Returns:
        True if successful, False if chapter not found
    """
    # Get current cover path
    query = "SELECT cover_path FROM chapters WHERE id = $1::uuid"
    row = await conn.fetchrow(query, str(chapter_id))
    
    if not row or not row["cover_path"]:
        return False
    
    try:
        # Delete from R2
        r2 = await CloudflareR2Bucket.get_instance()
        key = r2.extract_key(row["cover_path"])
        await r2.delete_file(key)
        
        # Reset in database
        update_query = """
            UPDATE c
                hapters 
            SET 
                cover_path = NULL, 
                updated_at = NOW()
            WHERE 
                id = $1::uuid
        """
        await conn.execute(update_query, str(chapter_id))
        
        return True
    
    except Exception as e:
        raise DatabaseException(
            client_message="Failed to delete chapter cover",
            original_error=e,
            additional_context={
                "action": "delete_chapter_cover",
                "chapter_id": str(chapter_id)
            }
        )


async def increment_chapter_view_bg(chapter_id: UUID) -> None:
    """
    Background task to increment chapter views.
    Acquires its own connection since the HTTP request has already finished.
    Fails silently on the application side but logs the error in the database.
    """
    query = "UPDATE chapters SET views = views + 1 WHERE id = $1;"
    try:
        await db.execute(query, None, chapter_id)
    except Exception as e:
        await logs_table.insert_log(
            error_type=type(e).__name__,
            error_message=str(e),
            error_level="ERROR",
            failed_query=query,
            query_parameters={"chapter_id": str(chapter_id)},
            execution_context={
                "action": "increment_chapter_view_bg",
                "description": "Failed to increment chapter view count in background."
            },
            stack_trace=util.format_stacktrace(e)
        )