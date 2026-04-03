from fastapi.exceptions import HTTPException
from fastapi import APIRouter, Query, status, Depends
from typing import Optional
from asyncpg import Connection
from src.db import db_connection


router = APIRouter()


@router.get("/")
async def get_manhwa_by_id(
    id: Optional[str] = Query(default=None),
    title: Optional[str] = Query(default=None),
    conn: Connection = Depends(db_connection)
):
    if not id and not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    pass