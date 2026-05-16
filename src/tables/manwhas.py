from src.schemas.manhwas import ManhwaCatalogResponse
from asyncpg import Connection


async def get_manhwa_by_id(id: str, conn: Connection) -> ManhwaCatalogResponse:
    row = await conn.fetchrow(
        """
            SELECT 
                * 
            FROM 
                mv_manhwa_catalog 
            WHERE 
                id = $1::uuid
            """,
        id,
    )
    
    return ManhwaCatalogResponse(row) if row else None