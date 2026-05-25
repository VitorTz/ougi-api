from pydantic import BaseModel, ConfigDict, field_validator
from uuid import UUID
from datetime import datetime
from typing import Optional, Any
import json


class AuditLogResponse(BaseModel):
    
    id: UUID
    actor_id: Optional[UUID]
    action: str
    table_name: str
    record_id: UUID
    old_data: Optional[dict[str, Any]] = None
    new_data: Optional[dict[str, Any]] = None
    ip_address: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator('old_data', 'new_data', mode='before')
    @classmethod
    def parse_jsonb(cls, value: Any) -> Optional[dict[str, Any]]:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
                
        return value