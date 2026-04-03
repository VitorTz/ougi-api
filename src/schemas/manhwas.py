from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class ManhwaCatalogResponse(BaseModel):

    id: UUID
    title: str
    slug: str
    descr: Optional[str] = None
    hex_color: Optional[str] = None
    release_year: Optional[int] = None
    status: str
    is_adult: bool
    total_views: int
    avg_rating: Optional[float] = None
    rating_count: int
    created_at: datetime
    updated_at: datetime

    # Covers
    cover_big: Optional[str] = None
    cover_medium: Optional[str] = None
    cover_small: Optional[str] = None

    # Arrays (Guaranteed to be lists due to COALESCE in SQL)
    alternative_names: list[str]
    genres: list[str]
    tags: list[str]
    authors: list[str]
    artists: list[str]
    scans: list[str]
    content_warnings: list[str]

    # Latest published chapter info
    # Typed as float because chapter numbers can be decimals (e.g., 10.5)
    latest_chapter_num: Optional[float] = None
    last_chapter_updated_at: Optional[datetime] = None
    chapter_count: int