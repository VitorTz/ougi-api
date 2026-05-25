from pydantic import BaseModel, ConfigDict, field_validator
from src.constants import Constants
from datetime import datetime
from typing import Optional
from uuid import UUID


class ManhwaCatalogResponse(BaseModel):

    id: UUID
    title: str
    slug: str
    descr: Optional[str] = None
    hex_color: Optional[str] = None
    release_year: Optional[int] = None
    status: str
    total_views: int
    avg_rating: Optional[float] = None
    rating_count: int
    created_at: datetime
    updated_at: datetime

    cover_big: Optional[str] = None
    cover_medium: Optional[str] = None
    cover_small: Optional[str] = None
    
    alternative_names: list[str]
    genres: list[str]
    tags: list[str]
    authors: list[str]
    artists: list[str]
    scans: list[str]
    content_warnings: list[str]
    
    latest_chapter_num: Optional[float] = None
    last_chapter_updated_at: Optional[datetime] = None
    chapter_count: int

    model_config = ConfigDict(from_attributes=True)

    @field_validator('cover_big', 'cover_medium', 'cover_small')
    @classmethod
    def prepend_cloudflare_prefix(cls, v: Optional[str]) -> Optional[str]:
        return Constants.CLOUDFLARE_PREFIX + v if v else v


class ManhwaSearchResponse(BaseModel):

    id: UUID
    title: str
    slug: str
    descr: Optional[str] = None
    hex_color: Optional[str] = None
    release_year: Optional[int] = None
    status: str
        
    cover_medium: Optional[str] = None
    cover_small: Optional[str] = None
    
    alternative_names: list[str]
    genres: list[str]
    tags: list[str]
    content_warnings: list[str]

    chapter_count: int
    latest_chapter_num: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator('cover_medium', 'cover_small')
    @classmethod
    def prepend_cloudflare_prefix(cls, v: Optional[str]) -> Optional[str]:
        return Constants.CLOUDFLARE_PREFIX + v if v else v