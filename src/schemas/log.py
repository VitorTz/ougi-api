from pydantic import BaseModel, IPvAnyAddress, ConfigDict, field_validator
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID
import json


class SystemLogResponse(BaseModel):
    
    id: UUID
    user_id: Optional[UUID] = None
    request_id: Optional[UUID] = None
    ip_address: Optional[IPvAnyAddress] = None
    user_agent: Optional[str] = None
    request_method: Optional[str] = None
    request_path: Optional[str] = None
    error_level: str
    error_type: str
    error_message: str
    failed_query: Optional[str] = None
    query_parameters: Optional[Dict[str, Any]] = None
    execution_context: Optional[Dict[str, Any]] = None
    stack_trace: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator('query_parameters', 'execution_context', mode='before')
    @classmethod
    def parse_json_fields(cls, value: Any) -> Optional[Dict[str, Any]]:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None 

        return value