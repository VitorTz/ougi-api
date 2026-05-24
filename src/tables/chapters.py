from src.schemas.chapter import ChapterResponse, ChapterUpdate
from src.exceptions import DatabaseException, DuplicateRecordError
from src.schemas.pagination import Pagination
from asyncpg import Connection, UniqueViolationError
from src.tables import logs as logs_table
from src import db
from uuid import UUID
from src import util


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
    
    count_query = f"SELECT COUNT(c.id) {base_query}"    

    fetch_params = params.copy()
    fetch_params.extend([limit, offset])    
    fetch_query = f"""
        SELECT 
            c.id,
            c.cover_path,
            c.num,
            c.title,
            c.views
        {base_query} 
        ORDER BY 
            c.num DESC 
        LIMIT 
            ${len(fetch_params) - 1} 
        OFFSET 
            ${len(fetch_params)}
    """

    try:
        total_items = await conn.fetchval(count_query, *params)
        if total_items == 0:
            rows = []
        else:
            rows = await conn.fetch(fetch_query, *fetch_params)
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while fetching the chapters.",
            original_error=e,
            query=fetch_query,
            params=fetch_params,
            additional_context={
                "action": "list_manhwa_chapters", 
                "identifier": str(identifier)
            }
        )
    
    return Pagination(
        items=[ChapterResponse(**row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset
    )

    
async def update_chapter(
    chapter_id: str, 
    payload: ChapterUpdate, 
    conn: Connection
) -> ChapterResponse | None:
    
    # Exclude 'id' safely in case it was accidentally passed in the payload body
    update_data = payload.model_dump(exclude_unset=True, exclude={"id"})
    
    if not update_data: 
        return None

    set_clauses = []
    params = []
    
    for key, value in update_data.items():
        params.append(value)
        set_clauses.append(f"{key} = ${len(params)}")

    # Automatically add updated_at timestamp
    set_clauses.append("updated_at = NOW()")
    
    params.append(chapter_id)
    set_query = ", ".join(set_clauses)
    
    # Enforce UUID casting for safety
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
        row = await conn.fetchrow(query, *params)
        
    except UniqueViolationError as e:
        raise DuplicateRecordError("A chapter with this number or sort_order already exists for this manhwa.")
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while updating the chapter.",
            original_error=e,
            query=query,
            params=params,
            additional_context={"action": "update_chapter", "chapter_id": str(chapter_id)}
        )
    
    return ChapterResponse(**row) if row else None
    

async def delete_chapter(chapter_id: str, conn: Connection) -> dict | None:
    """
    Deletes a chapter and returns its data as a dictionary 
    for audit logging purposes. Returns None if not found.
    """    
    query = "DELETE FROM chapters WHERE id = $1::uuid RETURNING *;"
    
    try:
        row = await conn.fetchrow(query, chapter_id)
        return dict(row) if row else None
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while deleting the chapter.",
            original_error=e,
            query=query,
            params=[chapter_id],
            additional_context={"action": "delete_chapter", "chapter_id": str(chapter_id)}
        )
    

async def increment_chapter_view_bg(chapter_id: UUID) -> None:
    """
    Background task to increment chapter views.
    Acquires its own connection since the HTTP request has already finished.
    Fails silently on the application side but logs the error in the database.
    """
    query = "UPDATE chapters SET views = views + 1 WHERE id = $1;"
    
    async with db.pool.acquire() as conn:
        try:
            await conn.execute(query, chapter_id)
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
                stack_trace=util.format_stacktrace(e),
                conn=conn
            )