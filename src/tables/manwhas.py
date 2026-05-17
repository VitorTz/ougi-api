from src.schemas.manhwas import ManhwaCatalogResponse, ManhwaSearchResponse
from src.schemas.pagination import Pagination
from src.exceptions import DatabaseException
from asyncpg import Connection
from src import util


ALLOWED_ORDER = {
    "last_chapter_updated_at", 
    "total_views", 
    "avg_rating", 
    "created_at"
}


async def get_manhwa(identifier: str, conn: Connection) -> ManhwaCatalogResponse | None:
    """
    Fetches a manhwa from the materialized catalog.
    Automatically detects if the provided identifier is a UUID or a text slug
    to route the query efficiently.
    """    
    if util.is_uuid(identifier):
        query = "SELECT * FROM mv_manhwa_catalog WHERE id = $1::uuid;"
    else:
        query = "SELECT * FROM mv_manhwa_catalog WHERE slug = $1;"

    try:
        row = await conn.fetchrow(query, identifier)
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while fetching the manhwa details.",
            original_error=e,
            query=query,
            params=[identifier],
            additional_context={"action": "get_manhwa", "identifier": identifier}
        )
        
    return ManhwaCatalogResponse(**row) if row else None


async def search_manhwa(
    conn: Connection,
    title: str | None = None,
    genres: list[str] | None = None,
    exclude_warnings: list[str] | None = None,
    scans: list[str] | None = None,
    tags: list[str] | None = None,
    status: str | None = None,
    order_by: str = "last_chapter_updated_at",
    limit: int = 32,
    offset: int = 0,
) -> Pagination[ManhwaSearchResponse]:
    """
    Search manhwas with fuzzy title matching and advanced filtering.
    
    Performs a flexible search across the manhwa catalog using fuzzy string matching
    on title and alternative names, combined with array-based filters for genres,
    tags, scans, and content warnings. Results are paginated and ordered by the
    specified column.
    
    Args:
        conn (Connection): Database connection from the connection pool.
        title (str | None): Fuzzy search query on title + alternative_names using
            trigram similarity matching (threshold > 0.1). Searches both exact titles
            and alternative names concatenated in 'search_text' column. Supports
            typos and partial matches. Defaults to None (no title filter).
        genres (list[str] | None): Filter by genres using array containment (@>).
            Returns manhwas where ALL provided genres are present. Defaults to None.
        exclude_warnings (list[str] | None): Exclude manhwas containing ANY of the
            specified content warnings (NOT && operator). Defaults to None.
        scans (list[str] | None): Filter by scans using array containment (@>).
            Returns manhwas where ALL provided scans are present. Defaults to None.
        tags (list[str] | None): Filter by tags using array containment (@>).
            Returns manhwas where ALL provided tags are present. Defaults to None.
        status (str | None): Filter by manhwa status (e.g., 'ongoing', 'completed').
            Must be a valid 'manhwa_status_type' enum value. Defaults to None.
        order_by (str): Column name for sorting results. Allowed values:
            'last_chapter_updated_at', 'total_views', 'avg_rating', 'created_at'.
            When title search is provided, secondary sort by title similarity DESC.
            Defaults to 'last_chapter_updated_at'.
        limit (int): Maximum number of items per page. Range: 1-64. Defaults to 32.
        offset (int): Number of items to skip (pagination). Must be >= 0. Defaults to 0.
    
    Returns:
        Pagination[ManhwaSearchResponse]: Paginated response containing:
            - items: List of matched manhwas with search-relevant fields
            - total_items: Total count of results matching all filters (without limit)
            - limit: Items per page (echoed back)
            - offset: Items skipped (echoed back)
            - total_pages: Computed field (ceil(total_items / limit))
            - current_page: Computed field (1-indexed)
            - has_next: Computed field (bool)
            - has_previous: Computed field (bool)
    
    Notes:
        - Title search uses similarity() > 0.1 threshold for fuzzy matching.
          Threshold values: 0.1 (fuzzy) ... 0.3 (strict). Lower = more results.
        - All filters are combined with AND logic (must match all).
        - Array filters (genres, tags, scans, warnings) use postgres array ops.
        - Results are materialized from mv_manhwa_catalog view which includes
          alternative_names aggregated from 'manhwa_alternative_names' table.
        - COUNT(*) OVER() fetches total count in single query (no extra roundtrip).
    
    Examples:
        # Search by title with fuzzy matching
        result = await search_manhwa(
            conn=conn,
            title="tower of god",  # Matches "Tower of God", "Tower of G.", etc
            limit=10
        )
        
        # Search with multiple filters
        result = await search_manhwa(
            conn=conn,
            title="solo leveling",
            genres=["action", "fantasy"],
            exclude_warnings=["gore"],
            status_filter="ongoing",
            order_by="total_views",
            limit=20,
            offset=0
        )
        
        # List all manhwas with pagination
        result = await search_manhwa(conn=conn, limit=32, offset=0)
    """
    conditions = []
    params = []
    
    # if title:
    #     params.append(title)
    #     params.append(f"%{title}%")
    #     conditions.append(f"(similarity(search_text, ${len(params) - 1}) > 0.15 OR search_text ILIKE ${len(params)})")

    if title:
        params.append(title)
        conditions.append(f"similarity(search_text, ${len(params)}) > 0.1")
    
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
    
    if status:
        params.append(status)
        conditions.append(f"status = ${len(params)}::manhwa_status_type")
    
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    order_col = order_by if order_by in ALLOWED_ORDER else "last_chapter_updated_at"
        
    extra_order = ""
    if title:
        extra_order = f", similarity(search_text, ${len(params)}) DESC"
        
    select_params = params + [limit, offset]
    select_query = f"""
        SELECT 
            id,
            title,
            slug,
            descr,
            hex_color,
            release_year,
            status,
            cover_medium,
            cover_small,
            alternative_names,
            genres,
            tags,
            content_warnings,
            chapter_count,
            latest_chapter_num,
            COUNT(*) OVER() as total_count
        FROM 
            mv_manhwa_catalog
        {where_clause}
        ORDER BY 
            {order_col} DESC NULLS LAST
            {extra_order}
        LIMIT 
            ${len(select_params) - 1}
        OFFSET 
            ${len(select_params)}
    """
    
    rows = await conn.fetch(select_query, *select_params)
    total_items = rows[0]["total_count"] if rows else 0
    
    return Pagination(
        items=[ManhwaSearchResponse(**row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset
    )