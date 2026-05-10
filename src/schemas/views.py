from enum import Enum


class AllowedMaterializedViews(str, Enum):

    MANHWA_CATALOG = "mv_manhwa_catalog"
    USER_STATISTICS = "mv_user_statistics"
    POPULAR_CHAPTERS = "mv_popular_chapters"