from fastapi import APIRouter, Depends
from src.routes.admin import audit_log
from src.routes.admin import auth
from src.routes.admin import database
from src.routes.admin import chapter
from src.routes.admin import manhwa
from src.routes.admin import system_log
from src.routes.admin import user
from src.tables.user import require_admin_access

router = APIRouter(
    prefix="/admin", 
    tags=['admin'], 
    dependencies=[Depends(require_admin_access)]
)

router.include_router(audit_log.router)
router.include_router(auth.router)
router.include_router(manhwa.router)
router.include_router(chapter.router)
router.include_router(database.router)
router.include_router(system_log.router)
router.include_router(user.router)