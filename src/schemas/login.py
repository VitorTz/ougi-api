from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID


class LoginIdentifier(BaseModel):
    
    identifier: str
    password: str


class LoginAttemptResponse(BaseModel):

    id: UUID
    identifier: str
    ip_address: str
    success: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)