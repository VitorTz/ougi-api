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
from src.exceptions import ResourceNotFoundException, EmptyUpdateException
from src.tables import chapters as chapter_table
from src.tables import audit_log as audit_log_table
from src.schemas.chapter import ChapterResponse, ChapterUpdate
from asyncpg import Connection
from typing import Optional
from src.security import jwt_utils
from src.util import extract_client_ip
from src.db import db_connection


router = APIRouter(prefix="/chapters")
limiter = get_limiter()


@router.patch(
    "/{chapter_id}", 
    response_model=ChapterResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Chapter Metadata",
    description="Updates specific fields of a chapter (e.g., title, publish status, or number). Only explicitly provided fields will be modified. This action is restricted to staff and is strictly audited."
)
@limiter.limit("32/minute")
async def update_chapter(
    request: Request,
    background_tasks: BackgroundTasks,
    chapter_id: str = Path(..., description="The UUID of the chapter to be updated."),
    payload: ChapterUpdate = Depends(),
    access_token: Optional[str] = Cookie(default=None),
    conn: Connection = Depends(db_connection),
):    
    if not payload.model_dump(exclude_unset=True, exclude={"id"}):
        raise EmptyUpdateException()

    chapter: ChapterResponse | None = await chapter_table.update_chapter(
        chapter_id=chapter_id, 
        payload=payload, 
        conn=conn
    )    

    if not chapter:
        raise ResourceNotFoundException(f"Chapter")    
            
    actor_id: str = jwt_utils.extract_value_from_jwt_token(access_token, "sub")
    actor_ip: str = extract_client_ip(request)
        
    background_tasks.add_task(
        audit_log_table.insert_audit_log,
        action="update_chapter",
        table_name="chapters",
        record_id=chapter_id,
        actor_id=actor_id,
        ip_address=actor_ip,
        new_data=payload.model_dump(exclude_unset=True, exclude={"id"})
    )
        
    return chapter


@router.delete(
    "/{chapter_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Chapter",
    description="Permanently deletes a chapter. The deleted chapter's data is captured for audit logging before removal."
)
@limiter.limit("32/minute")
async def delete_chapter(
    request: Request,
    background_tasks: BackgroundTasks,
    chapter_id: str = Path(..., description="The UUID of the chapter to be deleted."),
    access_token: Optional[str] = Cookie(default=None),
    conn: Connection = Depends(db_connection),
):
    deleted_data: Optional[dict] = await chapter_table.delete_chapter(chapter_id, conn)
    
    if not deleted_data:
        raise ResourceNotFoundException("Chapter")
    
    actor_id: str = jwt_utils.extract_value_from_jwt_token(access_token, "sub")
    actor_ip: str = extract_client_ip(request)
    
    background_tasks.add_task(
        audit_log_table.insert_audit_log,
        action="delete_chapter",
        table_name="chapters",
        record_id=chapter_id,
        actor_id=actor_id,
        ip_address=actor_ip,
        old_data=deleted_data
    )