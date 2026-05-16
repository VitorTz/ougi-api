from fastapi import APIRouter, Depends, status, Request, BackgroundTasks, Cookie, Query, Path
from src.security.cookies import require_moderator_access
from src.tables import audit_log as audit_log_table
from src.schemas.chapter import ChapterResponse, ChapterUpdate
from fastapi.exceptions import HTTPException
from src.tables import user as users_table
from src.tables import chapters as chapter_table
from src.util import get_real_client_ip
from src.dependencies import get_limiter
from src.db import db_connection
from src.security import jwt
from asyncpg import Connection
from typing import Optional


router = APIRouter(
    prefix="/moderator", 
    tags=['moderator'], 
    dependencies=[Depends(require_moderator_access)]
)
limiter = get_limiter()


# ============================================= 
# USERS
# ============================================= 

@router.post("/user/ban", status_code=status.HTTP_200_OK)
@limiter.limit("32/minute")
async def ban_user(
    request: Request,
    background_tasks: BackgroundTasks,
    access_token: Optional[str] = Cookie(default=None),
    user_id: str = Query(...),
    conn: Connection = Depends(db_connection)
):
    success: bool = await users_table.ban_user(user_id, conn)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )
    
    # Audit
    actor_id: str = jwt.extract_user_id_from_jwt_access_token(access_token)
    actor_ip: str = get_real_client_ip()
    background_tasks.add_task(
        audit_log_table.insert_audit_log,
        action="ban_user",
        table_name="users",
        record_id=str(user_id),
        actor_id=actor_id,
        ip_address=actor_ip
    )


@router.patch("/chapters/{chapter_id}", response_model=ChapterResponse)
@limiter.limit("32/minute")
async def update_chapter(
    request: Request,
    chapter_id: str = Path(...),
    chapter_update: ChapterUpdate = Depends(),
    conn: Connection = Depends(db_connection),
):
    if not chapter_update.model_dump(exclude_unset=True):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid fields provided for update.")

    chapter: ChapterResponse | None = await chapter_table.update_chapter(chapter_id, chapter_update, conn)
    
    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Chapter not found."
        )
        
    return chapter