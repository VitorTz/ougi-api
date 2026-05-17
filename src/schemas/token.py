from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID


class JWtTokenCreate(BaseModel):

    jwt_token: str
    expires_at: datetime


class RefreshTokenResponse(BaseModel):
    
    id: UUID
    user_id: UUID
    device_info: str
    ip_address: str
    expires_at: datetime
    revoked: bool
    replaced_by: UUID | None = None
    family_id: UUID

    model_config = ConfigDict(from_attributes=True)
    

class SessionResponse(BaseModel):
    
    family_id: UUID
    session_started_at: datetime
    expires_at: datetime
    is_current_session: bool = False

    model_config = ConfigDict(from_attributes=True)