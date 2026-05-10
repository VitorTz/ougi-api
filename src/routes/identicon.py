from fastapi import APIRouter, Request, Response, Path
from src.identicon import generate_identicon
import hashlib


router = APIRouter(prefix="/identicons", tags=["identicons"])


@router.get("/{username}/avatar.svg", response_class=Response)
async def get_user_identicon(
    request: Request,
    username: str = Path(..., description="The username to generate the avatar for"),
):
    etag = f'"{hashlib.md5(username.encode()).hexdigest()}"'

    if request.headers.get("If-None-Match") == etag:
        return Response(status_code=304, headers={"ETag": etag})

    svg_content = generate_identicon(username)
    return Response(
        content=svg_content,
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "public, max-age=86400",
            "ETag": etag,
        }
    )