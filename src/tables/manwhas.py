from asyncpg import Connection
from src.schemas.views import AllowedMaterializedViews
from src import db


async def refresh_manhwa_catalog_view(conn: Connection):
    await db.refresh_view(AllowedMaterializedViews.MANHWA_CATALOG, conn)