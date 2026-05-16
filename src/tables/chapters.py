from src.schemas.chapter import ChapterResponse, ChapterUpdate
from src.exceptions import DatabaseException
from src.schemas.pagination import Pagination
from asyncpg import Connection, UniqueViolationError
from src.tables import logs as logs_table
from typing import Union, Optional
from src import db
from uuid import UUID
from src import util
import traceback


async def get_chapters_from_manhwa(
    identifier: Union[str, UUID], 
    is_published: Optional[bool],
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
            c.* 
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

    
async def update_chapter(chapter_id: str, chapter_update: ChapterUpdate, conn: Connection) -> ChapterResponse:
    update_data = chapter_update.model_dump(exclude_unset=True)
    if not update_data: 
        return

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
        UPDATE 
            chapters 
        SET 
            {set_query} 
        WHERE 
            id = ${len(params)} 
        RETURNING 
            *
    """
    
    try:
        row = await conn.fetchrow(query, *params)
        if row:
            return ChapterResponse(row)
    except UniqueViolationError as e:
        raise DatabaseException(
            client_message="Chapter with this sort_order or num already exists for this manhwa.",
            original_error=e,
            query=query,
            params=params,
            additional_context={"action": "update_chapter", "chapter_id": str(chapter_id)}
        )
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while updating the chapter.",
            original_error=e,
            query=query,
            params=params,
            additional_context={"action": "update_chapter", "chapter_id": str(chapter_id)}
        )
    

async def delete_chapter(chapter_id: str, conn: Connection) -> bool:
    query = "DELETE FROM chapters WHERE id = $1 RETURNING id"
    
    try:
        deleted = await conn.fetchval(query, chapter_id)
        return deleted is not None
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
    """
    query = "UPDATE chapters SET views = views + 1 WHERE id = $1;"
    
    async with db.pool.acquire() as conn:
        try:
            await conn.execute(query, chapter_id)
        except Exception as e:
            tb_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))
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
                stack_trace=tb_str,
                conn=conn
            )