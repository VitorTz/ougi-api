from fastapi import APIRouter, Request, Response, Path, status
from src.schemas.identicons import CombinedIdenticonResponse
from src.dependencies import get_limiter
from src.constants import Constants
from src import identicon


router = APIRouter(
    prefix="/identicons", 
    tags=["identicons"]
)
limiter = get_limiter()



@router.get("/{username}/avatar.svg", response_class=Response)
@limiter.limit("2048/minute")
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
@limiter.limit("2048/minute")
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


@router.get("/{username}/combined", response_model=CombinedIdenticonResponse)
@limiter.limit("2048/minute")
async def get_combined_identicons(
    request: Request,
    response: Response,
    username: str = Path(
        ..., 
        description="The username to generate both the avatar and banner for", 
        max_length=32
    )
):
    """
    Returns both the avatar and banner SVGs in a single JSON payload.
    Ideal for profile pages to reduce the number of HTTP requests.
    """
    etag: str = identicon.generate_etag(username)
    
    if Constants.IS_PRODUCTION and request.headers.get("If-None-Match") == etag:
        response.status_code = status.HTTP_304_NOT_MODIFIED
        response.headers["ETag"] = etag
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})
        
    avatar_svg: str = identicon.generate_avatar_identicon(
        username, 
        Constants.DEFAULT_AVATAR_SIZE
    )
    
    banner_svg: str = identicon.generate_banner_identicon(
        username,
        Constants.DEFAULT_BANNER_WIDTH,
        Constants.DEFAULT_BANNER_HEIGHT
    )
    
    response.headers["Cache-Control"] = "public, max-age=86400"
    response.headers["ETag"] = etag

    return CombinedIdenticonResponse(
        avatar_svg=avatar_svg,
        banner_svg=banner_svg
    )