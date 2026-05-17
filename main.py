from fastapi import FastAPI, Request, APIRouter, status, Depends
from asyncpg import Connection
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from src.constants import Constants
from src.routes import manhwas
from src.routes import auth
from src.routes import admin
from src.routes import chapters
from src.routes import moderator
from src.routes import identicon
from src.exceptions import DatabaseException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError, HTTPException
from src import middlewares
from src import db
from src import handlers
from src.dependencies import get_limiter
import contextlib
import uvicorn


limiter = get_limiter()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[API] [STARTING {Constants.API_NAME}]")
    await db.db_connect()
    print(f"[API] [{Constants.API_NAME} STARTED]")
    yield
    await db.db_disconnect()
    print(f"[API] [SHUTTING DOWN {Constants.API_NAME}]")



app = FastAPI(
    title=Constants.API_NAME,
    description=Constants.API_DESCR,
    version=Constants.API_VERSION,
    lifespan=lifespan,
    docs_url=None if Constants.IS_PRODUCTION else "/docs",
    redoc_url=None if Constants.IS_PRODUCTION else "/redoc",
    openapi_url=None if Constants.IS_PRODUCTION else "/openapi.json"
)


############################ Middlewares #############################

if Constants.IS_PRODUCTION:
    app.add_middleware(middlewares.HTTPSRedirectMiddleware)

app.add_middleware(middlewares.SecurityHeadersMiddleware)
app.add_middleware(middlewares.RequestIDMiddleware)

if Constants.IS_PRODUCTION:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://ononougi.com",
            "https://www.ononougi.com",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )

app.add_middleware(middlewares.BotDetectionMiddleware)
app.add_middleware(middlewares.RequestSizeLimitMiddleware, max_upload_size=10 * 1024 * 1024)
app.add_middleware(GZipMiddleware, minimum_size=500)


############################ Exception Handlers #############################

app.add_exception_handler(RequestValidationError, handlers.validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, handlers.http_exception_handler)
app.add_exception_handler(DatabaseException, handlers.database_exception_handler)
app.add_exception_handler(Exception, handlers.global_exception_handler)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.state.limiter = limiter

############################ ROUTES #############################

api_v1_router = APIRouter(prefix="/api/v1")


@api_v1_router.get("")
@limiter.limit("32/minute")
def read_root(request: Request):
    return {
        "status": "ok",
        "request_id": request.state.request_id,
        "version": Constants.API_VERSION,
    }



@api_v1_router.get("/health", status_code=status.HTTP_200_OK)
@limiter.limit("60/minute")
async def check_system_health(
    request: Request,
    conn: Connection = Depends(db.db_connection)
):
    is_db_healthy = await db.ping_database(conn)
    
    if not is_db_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="System is degraded. Database connection failed."
        )
    return {
        "status": "ok",
        "database": "healthy",
        "api_version": Constants.API_VERSION
    }


api_v1_router.include_router(admin.router)
api_v1_router.include_router(moderator.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(manhwas.router)
api_v1_router.include_router(chapters.router)
api_v1_router.include_router(identicon.router)


app.include_router(api_v1_router)


if __name__ == "__main__":
    config = {
        "app": "main:app",
        "host": "0.0.0.0",
        "port": 8000,
        "workers": 4,
        "loop": "uvloop",
        "http": "httptools",
        "limit_concurrency": 1000,
        "timeout_keep_alive": 5,
        "access_log": not Constants.IS_PRODUCTION,
        "reload": not Constants.IS_PRODUCTION,
        "server_header": False
    }
    
    if Constants.IS_PRODUCTION:
        config.update({
            # "ssl_keyfile": "/etc/ssl/private/key.pem",  # Adicione seus certs
            # "ssl_certfile": "/etc/ssl/certs/cert.pem",
            "log_level": "warning",
        })
    
    uvicorn.run(**config)
