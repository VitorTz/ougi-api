from fastapi import FastAPI, Request, APIRouter
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from src.constants import Constants
from src.routes import manhwas
from src.routes import auth
from src.routes import logs
from src.routes import admin
from src.exceptions import DatabaseException
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError
from src import db
from src import handlers
from src.ratelimit import limiter
import contextlib
import uvicorn


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[API] [STARTING {Constants.API_NAME}]")
    
    # [PostgreSql INIT]
    await db.db_connect()

    print(f"[API] [{Constants.API_NAME} STARTED]")

    yield    
    
    # [PostgreSql CLOSE]
    await db.db_disconnect()

    print(f"[API] [SHUTTING DOWN {Constants.API_NAME}]")


app = FastAPI(
    title=Constants.API_NAME,
    description=Constants.API_DESCR,
    version=Constants.API_VERSION,
    lifespan=lifespan
)

app.state.limiter = limiter

# origins = [
#     "http://localhost:3000",   # Default port for Create React App
#     "http://localhost:5173",   # Default port for Vite
# ]

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )


############################ Middlewares #############################

app.add_middleware(GZipMiddleware, minimum_size=1000)
# app.add_middleware(
#     TrustedHostMiddleware, 
#     allowed_hosts=["localhost"]
# )


############################ Exception Handlers #############################

app.add_exception_handler(RequestValidationError, handlers.validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, handlers.http_exception_handler)
app.add_exception_handler(DatabaseException, handlers.database_exception_handler)
app.add_exception_handler(Exception, handlers.global_exception_handler)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


############################ ROUTES #############################

api_v1_router = APIRouter(prefix="/api/v1")

@api_v1_router.get("")
@limiter.limit("32/minute")
def read_root(request: Request):
    return {"status": "ok"}


api_v1_router.include_router(admin.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(manhwas.router)
api_v1_router.include_router(logs.router)

app.include_router(api_v1_router)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        workers=4,
        loop="uvloop",
        http="httptools",
        # log_level="warning",
        limit_concurrency=1000,
        timeout_keep_alive=5
    )