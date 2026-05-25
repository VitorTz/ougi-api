from fastapi import (
    APIRouter, 
    status, 
    Request, 
    Path, 
    UploadFile, 
    File,
    Depends,
    BackgroundTasks,
    Cookie
)
from src.schemas.chapter import (
    ChapterResponse, 
    ChapterUpdate, 
    ChapterUpdateCoverResponse
)
from fastapi.exceptions import HTTPException
from src.constants import Constants
from src.dependencies import get_limiter
from src.exceptions import ResourceNotFoundException, DatabaseException
from src.tables import chapters as chapter_table
from src.tables import audit_log as audit_log_table
from src.cloudflare import CloudflareR2Bucket
from asyncpg import Connection
from typing import Optional
from src.security import jwt_utils
from src import util
from src.db import db_connection
from uuid import UUID
import io


router = APIRouter(prefix="/chapters")
limiter = get_limiter()


@router.post(
    "/{chapter_id}/cover",
    response_model=ChapterUpdateCoverResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Chapter Cover Image",
    description="Upload and update the cover image for a chapter. Image is automatically converted to WebP format for optimal storage. Only authenticated staff members can perform this action, and all changes are logged in the audit trail.",
    tags=["chapters"]
)
async def update_chapter_cover(
    request: Request,
    background_tasks: BackgroundTasks,
    chapter_id: UUID = Path(..., description="Chapter ID (UUID)"),
    file: UploadFile = File(..., description="Cover image file (JPG, PNG, or WebP, max 5MB)"),
    access_token: Optional[str] = Cookie(default=None),
    conn: Connection = Depends(db_connection)
):  
    # Auditing
    actor_id = jwt_utils.extract_value(access_token)
    actor_ip = util.extract_client_ip(request)
    
    # Validate image  
    util.validate_file_content(file)
    file_header = await file.read(12)
    ext: str = util.extract_image_extension(file_header)
    
    # Read bytes
    await file.seek(0)
    file_data = await file.read()
    original_image_size_bytes: int = len(file_data)
    util.validate_image_max_size(original_image_size_bytes)

    chapter: ChapterResponse | None = await chapter_table.get_chapter_by_id(chapter_id, conn)
    if not chapter: raise ResourceNotFoundException(f"Chapter {chapter_id}")
    
    try:
        webp_data, final_size = await util.convert_to_webp(file_data, max_width=Constants.CHAPTER_COVER_MAX_WIDTH)
        image_final_size_bytes: int = len(webp_data)

        r2 = await CloudflareR2Bucket.get_instance()
        key: str = r2.get_chapter_cover_key(chapter_id)
            
        chapter.cover_path = await r2.upload_bytes(
            key=key,
            data=io.BytesIO(webp_data),
            content_type="image/webp"
        )
        
        await chapter_table.update_chapter_cover(chapter_id, key, conn)
        
        # Audit logging
        background_tasks.add_task(
            audit_log_table.insert_audit_log,
            action="update_chapter_cover",
            table_name="chapters",
            record_id=str(chapter_id),
            actor_id=actor_id,
            ip_address=actor_ip,
            new_data={
                "cover_path": chapter.cover_path,
                "r2_key": key,
                "file_size_bytes": original_image_size_bytes,
                "webp_size_bytes": image_final_size_bytes,
                "original_extension": ext,
                "final_dimensions": {
                    "width": final_size[0],
                    "height": final_size[1]
                }
            }
        )

        return ChapterUpdateCoverResponse(
            id=chapter.id,
            num=chapter.num,
            title=chapter.title,
            views=chapter.views,
            cover_path=chapter.cover_path,
            image_width=final_size[0],
            image_heiht=final_size[1],
            image_size=util.format_bytes(image_final_size_bytes)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise DatabaseException(
            client_message="Failed to update chapter cover",
            original_error=e,
            additional_context={
                "action": "update_chapter_cover",
                "chapter_id": str(chapter_id),
                "file_name": file.filename,
                "file_size": original_image_size_bytes
            }
        )
    

@router.patch(
    "/", 
    response_model=ChapterResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Chapter Metadata",
    description="Updates specific fields of a chapter (e.g., title, publish status, or number). Only explicitly provided fields will be modified. This action is restricted to staff and is strictly audited."
)
@limiter.limit("32/minute")
async def update_chapter(
    request: Request,
    background_tasks: BackgroundTasks,
    payload: ChapterUpdate,
    access_token: Optional[str] = Cookie(default=None),
    conn: Connection = Depends(db_connection)
):    
    chapter: ChapterResponse = await chapter_table.update_chapter(payload, conn)

    if not chapter:
        raise ResourceNotFoundException(f"Chapter {payload.id}")
            
    actor_id: str = jwt_utils.extract_sub(access_token)
    actor_ip: str = util.extract_client_ip(request)
        
    background_tasks.add_task(
        audit_log_table.insert_audit_log,
        action="update_chapter",
        table_name="chapters",
        record_id=payload.id,
        actor_id=actor_id,
        ip_address=actor_ip,
        new_data=payload.model_dump()
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
    chapter_id: UUID = Path(..., description="The UUID of the chapter to be deleted."),
    access_token: str | None = Cookie(default=None),
    conn: Connection = Depends(db_connection),
):
    deleted_data: dict | None = await chapter_table.delete_chapter(chapter_id, conn)
    
    if not deleted_data:
        raise ResourceNotFoundException("Chapter")
    
    actor_id: str = jwt_utils.extract_sub(access_token)
    actor_ip: str = util.extract_client_ip(request)
    
    background_tasks.add_task(
        audit_log_table.insert_audit_log,
        action="delete_chapter",
        table_name="chapters",
        record_id=chapter_id,
        actor_id=actor_id,
        ip_address=actor_ip,
        old_data=deleted_data
    )