from fastapi import (
    APIRouter, 
    status, 
    Request, 
    Path, 
    Depends,
    BackgroundTasks,
    Cookie
)
from src.dependencies import get_limiter
from src.exceptions import ResourceNotFoundException
from src.tables import user as users_table
from src.tables import audit_log as audit_log_table
from asyncpg import Connection
from typing import Optional
from src.security import jwt_utils
from src.util import extract_client_ip
from src.db import db_connection


router = APIRouter(prefix="/user")
limiter = get_limiter()


@router.post(
    "/{user_id}/ban", 
    status_code=status.HTTP_200_OK,
    summary="Ban User",
    description="Bans a specific user by their ID, preventing them from accessing the platform. This action is restricted to moderators and is strictly audited."
)
@limiter.limit("32/minute")
async def ban_user(
    request: Request,
    background_tasks: BackgroundTasks,
    user_id: str = Path(..., description="The UUID of the user to be banned."),
    access_token: Optional[str] = Cookie(default=None),
    conn: Connection = Depends(db_connection)
):
    success: bool = await users_table.ban_user(user_id, conn)        
    if not success:
        raise ResourceNotFoundException("User")
        
    actor_id: str = jwt_utils.extract_value_from_jwt_token(access_token, "sub")
    actor_ip: str = extract_client_ip(request)
    
    background_tasks.add_task(
        audit_log_table.insert_audit_log,
        action="ban_user",
        table_name="users",
        record_id=str(user_id),
        actor_id=actor_id,
        ip_address=actor_ip
    )
        
    return {
        "status": "success", 
        "message": f"User {user_id} has been successfully banned."
    }