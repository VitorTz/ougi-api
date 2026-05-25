from pydantic import BaseModel, Field, computed_field
from typing import Generic, TypeVar, List
import math


T = TypeVar("T")


class Pagination(BaseModel, Generic[T]):
    
    items: List[T]
    total_items: int = Field(..., ge=0, description="Total number of items in the database")
    limit: int = Field(..., gt=0, description="Maximum number of items per page")
    offset: int = Field(..., ge=0, description="Number of items skipped")

    @computed_field
    def total_pages(self) -> int:
        """Calculates the total number of pages."""
        return math.ceil(self.total_items / self.limit)

    @computed_field
    def current_page(self) -> int:
        """Calculates the current page (1-indexed)."""
        return math.floor(self.offset / self.limit) + 1

    @computed_field
    def has_next(self) -> bool:
        """Checks if there is a next page available."""
        return self.current_page < self.total_pages

    @computed_field
    def has_previous(self) -> bool:
        """Checks if there is a previous page available."""
        return self.current_page > 1
    
    @staticmethod
    def empty_pagination(limit: int, offset: int) -> 'Pagination':
        return Pagination(items=[], total_items=0, limit=limit, offset=offset)