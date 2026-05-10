from pydantic import BaseModel, ConfigDict
from typing import Optional, Any
from uuid import UUID
from datetime import datetime


class AuditLogResponse(BaseModel):
    
    id: UUID
    actor_id: Optional[UUID]
    action: str
    table_name: str
    record_id: UUID
    old_data: Optional[dict[str, Any]]
    new_data: Optional[dict[str, Any]]
    ip_address: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)