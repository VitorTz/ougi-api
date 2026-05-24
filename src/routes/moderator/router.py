from src.security.cookies import require_moderator_access
from src.dependencies import get_limiter
from fastapi import APIRouter, Depends
from src.routes.moderator import chapter
from src.routes.moderator import user


router = APIRouter(
    prefix="/moderator", 
    tags=['moderator'], 
    dependencies=[Depends(require_moderator_access)]
)
limiter = get_limiter()


router.include_router(chapter.router)
router.include_router(user.router)
