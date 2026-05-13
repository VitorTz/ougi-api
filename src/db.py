from src.schemas.views import AllowedMaterializedViews
from src.exceptions import DatabaseException
from asyncpg import Connection
from dotenv import load_dotenv
import asyncpg
import os


load_dotenv()


pool: asyncpg.Pool = None


async def db_connect():
    global pool
    print("[DB] [INFO] Inicializando Pool de Conexões...")
    try:
        pool = await asyncpg.create_pool(
            dsn=os.getenv("DATABASE_URL"),
            min_size=5,
            max_size=50,
            command_timeout=30,
            max_inactive_connection_lifetime=300,
            statement_cache_size=0
        )
        print("[DB] [INFO] Conexão com Banco de Dados estabelecida.")
    except Exception as e:
        print(f"[DB] [CRITICAL] Falha ao conectar: {e}")
        raise e


async def db_disconnect():
    global pool
    if pool:
        await pool.close()
        print("[DB] [INFO] Conexões encerradas.")


async def db_connection():
    global pool
    if not pool:
        raise RuntimeError("Database pool not initialized")
    async with pool.acquire() as conn:
        yield conn


async def refresh_view(view: AllowedMaterializedViews, conn: Connection) -> None:
    """
    Refreshes a materialized view concurrently.
    Guaranteed safe from SQL Injection because 'view' is restricted by the Enum.
    """
    if not isinstance(view, AllowedMaterializedViews):
        raise DatabaseException(
            client_message="An unexpected error occurred while refreshing the data view.",
            original_error=e,
            query=None,
            params=None,
            additional_context={
                "action": "refresh_materialized_view",
                "view_name": str(view)
            }
        )
    
    query = f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view.value};"
    
    try:
        await conn.execute(query)
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while refreshing the data view.",
            original_error=e,
            query=query,
            params=None,
            additional_context={
                "action": "refresh_materialized_view",
                "view_name": view.value
            }
        )
    

async def ping(conn: Connection) -> bool:
    try:
        result = await conn.fetchval("SELECT 1;")
        return result == 1
    except Exception:
        return False