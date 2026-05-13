from asyncpg import Connection
from src.schemas.manhwas import ManhwaCatalogResponse
from src.schemas.views import AllowedMaterializedViews
from src import db


async def refresh_manhwa_catalog_view(conn: Connection):
    await db.refresh_view(AllowedMaterializedViews.MANHWA_CATALOG, conn)


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