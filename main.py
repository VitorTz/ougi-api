from src.constants import Constants
from src.routes import manhwas
from fastapi import FastAPI
from src import db
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


############################ ROUTES #############################

@app.get("/api/v1")
def read_root():
    return {"status": "ok"}


app.include_router(manhwas.router, prefix='/api/v1/manhwas', tags=['manhwas'])


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