from src.security.cookies import require_admin_access
from src.dependencies import get_limiter
from fastapi import APIRouter, Depends


router = APIRouter(
    prefix="/admin", 
    tags=['admin'], 
    dependencies=[Depends(require_admin_access)]
)

limiter = get_limiter()