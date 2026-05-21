from fastapi import (
    APIRouter, 
    status, 
    Request, 
    Path, 
    Depends, 
    BackgroundTasks, 
    Query, 
    Cookie
)
from src.schemas.user import UserRole
from src.dependencies import get_limiter
from src.exceptions import ResourceNotFoundException
from src.security import jwt_utils
from src.tables import user as users_table
from src.tables import audit_log as audit_log_table
from asyncpg import Connection
from typing import Optional
from src import util
from src import db


router = APIRouter()
limiter = get_limiter()


@router.post("/moderators/{user_id}/role", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("32/minute")
async def update_user_role(
    request: Request,
    background_tasks: BackgroundTasks,
    user_id: str = Path(
        ...,
        title="User ID",
        description="The unique UUID of the user whose role is being updated."
    ),
    role: UserRole = Query(
        ...,
        title="New User Role",
        description="The new role to assign to the user (e.g., admin, moderator, user)."
    ),
    access_token: Optional[str] = Cookie(default=None),
    conn: Connection = Depends(db.db_connection)
):
    """
    Updates the role of a specific user. 
    Triggers a background task to record the action in the audit logs.
    """
    id_actor: str = jwt_utils.extract_value_from_token(access_token, "sub")
    
    success: bool = await users_table.update_role_user(user_id, role, conn)
    
    if not success:
        raise ResourceNotFoundException("User")
    
    # Audit logging in background
    background_tasks.add_task(
        audit_log_table.insert_audit_log,
        action="update_user_role",
        table_name="users",
        record_id=str(user_id),
        actor_id=id_actor,
        ip_address=util.get_real_client_ip(request)
    )