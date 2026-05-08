from src.schemas.chapter import ChapterResponse, ChapterUpdate
from src.exceptions import DatabaseException
from asyncpg import Connection, UniqueViolationError


async def get_chapters_from_manhwa(
    manhwa_slug: str, 
    is_published: bool,
    limit: int,
    offset: int,
    conn: Connection
) -> list[ChapterResponse]:
    conditions = ["manhwa_id = $1"]
    params = [manhwa_slug]

    if is_published is not None:
        params.append(is_published)
        conditions.append(f"is_published = ${len(params)}")

    where_clause = " AND ".join(conditions)
    params.extend([limit, offset])

    query = f"""
        SELECT 
            * 
        FROM 
            chapters 
        WHERE 
            {where_clause} 
        ORDER BY 
            num DESC 
        LIMIT 
            ${len(params) - 1} 
        OFFSET 
            ${len(params)}
    """
    try:
        rows = await conn.fetch(query, *params)
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while fetching the chapters.",
            original_error=e,
            query=query,
            params=params,
            additional_context={
                "action": "list_manhwa_chapters", 
                "manhwa_slug": manhwa_slug
            }
        )
    return [ChapterResponse(**row) for row in rows]


async def get_chapter(chapter_id: str, conn: Connection) -> ChapterResponse:
    query = "SELECT * FROM chapters WHERE id = $1"
    
    try:
        row = await conn.fetchrow(query, chapter_id)
        if row:
            return ChapterResponse(**row)
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while fetching the chapter details.",
            original_error=e,
            query=query,
            params=[chapter_id],
            additional_context={"action": "get_chapter", "chapter_id": str(chapter_id)}
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
            return ChapterResponse(**row)
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
    

async def increment_chapter_view(chapter_id: str, conn: Connection) -> None:
    query = "UPDATE chapters SET views = views + 1 WHERE id = $1;"
    
    try:
        await conn.fetchval(query, chapter_id)
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while incrementing the chapter view count.",
            original_error=e,
            query=query,
            params=[chapter_id],
            additional_context={"action": "increment_chapter_view", "chapter_id": str(chapter_id)}
        )