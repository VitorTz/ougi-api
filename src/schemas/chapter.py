from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from decimal import Decimal

class ChapterBase(BaseModel):

    cover_path: Optional[str] = None
    sort_order: int = Field(ge=0)
    num: Decimal = Field(ge=0, max_digits=5, decimal_places=1)
    title: Optional[str] = None
    is_published: bool = True


class ChapterCreate(ChapterBase):

    pass


class ChapterUpdate(BaseModel):

    cover_path: Optional[str] = None
    sort_order: Optional[int] = Field(None, ge=0)
    num: Optional[Decimal] = Field(None, ge=0, max_digits=5, decimal_places=1)
    title: Optional[str] = None
    is_published: Optional[bool] = None

class ChapterResponse(ChapterBase):

    id: UUID
    manhwa_id: UUID
    views: int
    created_at: datetime
    updated_at: Optional[datetime] = None