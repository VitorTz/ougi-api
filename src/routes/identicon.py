from fastapi import APIRouter, Request, Response, Path, status
from src.constants import Constants
from src import identicon


router = APIRouter(prefix="/identicons", tags=["identicons"])


@router.get("/{username}/avatar.svg", response_class=Response)
async def get_user_identicon(
    request: Request,
    username: str = Path(
        ..., 
        description="The username to generate the avatar for", 
        max_length=32
    )
):
    etag: str = identicon.generate_etag(username)

    
    if Constants.IS_PRODUCTION and request.headers.get("If-None-Match") == etag:
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED, 
            headers={"ETag": etag}
        )
    
    svg_content: str = identicon.generate_avatar_identicon(
        username, 
        Constants.DEFAULT_AVATAR_SIZE
    )

    return Response(
        content=svg_content,
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "public, max-age=86400",
            "ETag": etag,
        }
    )


@router.get("/{username}/banner.svg", response_class=Response)
async def get_user_identicon(
    request: Request,
    username: str = Path(
        ..., 
        description="The username to generate the banner for", 
        max_length=32
    )
):
    etag: str = identicon.generate_etag(username)

    if Constants.IS_PRODUCTION and request.headers.get("If-None-Match") == etag:
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED, 
            headers={"ETag": etag}
        )
    
    svg_content: str = identicon.generate_banner_identicon(
        username,
        Constants.DEFAULT_BANNER_WIDTH,
        Constants.DEFAULT_BANNER_HEIGHT
    )

    return Response(
        content=svg_content,
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "public, max-age=86400",
            "ETag": etag,
        }
    )