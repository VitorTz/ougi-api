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
from src.schemas.manhwas import ManhwaCatalogResponse, ManhwaCoverBytes, ManhwaCoverUpdate
from src.dependencies import get_limiter
from src.exceptions import ResourceNotFoundException
from src.tables import manwhas as manhas_table
from src.tables import audit_log as audit_log_table
from src.cloudflare import CloudflareR2Bucket
from asyncpg import Connection
from typing import Optional
from src.security import jwt_utils
from src import util
from src.db import db_connection
from uuid import UUID


router = APIRouter(prefix="/manhwas")
limiter = get_limiter()


@router.post(
    "/{identifier}/cover",
    response_model=ManhwaCatalogResponse,
    status_code=status.HTTP_200_OK
)
async def update_manhwa_cover(
    request: Request,
    background_tasks: BackgroundTasks,
    identifier: UUID | str = Path(..., description="Manhwa identifier (slug or UUID)"),
    file: UploadFile = File(..., description="Cover image file (JPG, PNG, or WebP, max 5MB)"),
    access_token: Optional[str] = Cookie(default=None),
    conn: Connection = Depends(db_connection)
):
    # Auditing
    actor_id = jwt_utils.extract_value(access_token)
    actor_ip = util.extract_client_ip(request)
    
    # Validate image  
    util.validate_file_content(file)
    util.validate_image_extension(header_bytes=await file.read(12))

    # Read bytes
    await file.seek(0)
    file_data: bytes = await file.read()
    util.validate_image_max_size(len(file_data))
    
    manhwa: ManhwaCatalogResponse | None = await manhas_table.get_manhwa(identifier, conn)
    if not manhwa: 
        raise ResourceNotFoundException(f"Manhwa {identifier}")

    cover_bytes: ManhwaCoverBytes = util.create_manhwa_cover(file_data)

    r2 = await CloudflareR2Bucket.get_instance()

    keys: list[str] = await r2.upload_multiple_bytes(
        [
            (r2.get_manhwa_cover_key(manhwa.id, 'big'), cover_bytes.big),
            (r2.get_manhwa_cover_key(manhwa.id, 'medium'), cover_bytes.medium),
            (r2.get_manhwa_cover_key(manhwa.id, 'small'), cover_bytes.small),
        ]
    )

    cover = ManhwaCoverUpdate(
        big=keys[0],
        medium=keys[1],
        small=keys[2],
        hex_color=util.get_dominant_hex_color(cover_bytes.big)
    )

    await manhas_table.update_manhwa_cover(manhwa.id, cover, conn)

    # Audit logging
    background_tasks.add_task(
        audit_log_table.insert_audit_log,
        action="update_manhwa_cover",
        table_name="manhwas",
        record_id=str(manhwa.id),
        actor_id=actor_id,
        ip_address=actor_ip,
        new_data={"cover": str(cover) }
    )

    manhwa.cover_big = r2.append_prefix(cover.big)
    manhwa.cover_medium = r2.append_prefix(cover.medium)
    manhwa.cover_small = r2.append_prefix(cover.small)
    manhwa.hex_color = r2.append_prefix(cover.hex_color)
    
    return manhwa
