from src.dependencies import get_limiter
from fastapi import APIRouter, Depends
from src.routes.moderator import user
from src.tables.user import require_moderator_access


router = APIRouter(
    prefix="/moderator", 
    tags=['moderator'], 
    dependencies=[Depends(require_moderator_access)]
)
limiter = get_limiter()


router.include_router(user.router)
