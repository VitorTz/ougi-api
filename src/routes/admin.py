from fastapi import APIRouter, Depends, status, Request, Query, BackgroundTasks, Cookie
from fastapi.exceptions import HTTPException
from src.security.cookies import require_admin_access
from src.schemas.user import UserRole
from src.tables import user as users_table
from src.tables import audit_log as audit_log_table
from src.db import db_connection, refresh_view
from typing import Optional
from asyncpg import Connection
from src.dependencies import get_limiter
from src.util import get_real_client_ip
from src.security import jwt




router = APIRouter(
    prefix="/admin", 
    tags=['admin'], 
    dependencies=[Depends(require_admin_access)]
)
limiter = get_limiter()


@router.post("/refresh-mv-catalog", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("32/minute")
async def refresh_mv_catalog(request: Request, conn: Connection = Depends(db_connection)):
    await refresh_view("mv_manhwa_catalog", conn)


# ============================================= 
# MODERATORS
# ============================================= 
@router.post("/moderator/role", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("16/minute")
async def update_user_role(
    request: Request,
    background_tasks: BackgroundTasks,
    access_token: Optional[str] = Cookie(default=None),
    user_id: str = Query(...),
    role: UserRole = Query(...),
    conn: Connection = Depends(db_connection)
):
    success: bool = await users_table.set_role_to_user(user_id, role, conn)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )
    
    # Audit
    id_actor: str = jwt.extract_user_id_from_jwt_access_token(access_token)
    ip_actor: str = get_real_client_ip()
    background_tasks.add_task(
        audit_log_table.insert_audit_log,
        action="update_user_role",
        table_name="users",
        record_id=str(user_id),
        actor_id=id_actor,
        ip_address=ip_actor
    )
