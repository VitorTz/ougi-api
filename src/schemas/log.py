from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID
import json


class SystemLogResponse(BaseModel):
    
    id: UUID
    user_id: Optional[UUID] = None
    request_id: Optional[UUID] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_method: Optional[str] = None
    request_path: Optional[str] = None
    error_level: str
    error_type: str
    error_message: str
    failed_query: Optional[str] = None
    query_parameters: Dict[str, Any] | List[Any] | str | None = None
    execution_context: Dict[str, Any] | List[Any] | str | None = None
    stack_trace: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator('query_parameters', 'execution_context', mode='before')
    @classmethod
    def parse_json_fields(cls, value: Any) -> Any:
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, str):
                    try:
                        parsed = json.loads(parsed)
                    except json.JSONDecodeError:
                        pass                        
                return parsed
            except json.JSONDecodeError:
                return value

        return value
        