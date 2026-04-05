from pydantic import BaseModel, IPvAnyAddress
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID


class SystemLogResponse(BaseModel):
    
    id: UUID
    user_id: Optional[UUID] = None
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