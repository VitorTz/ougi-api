from pydantic import BaseModel, ConfigDict
from typing import Optional
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
    created_at: datetime
    expires_at: datetime
    revoked: bool
    replaced_by: UUID | None = None
    family_id: UUID

    model_config = ConfigDict(from_attributes=True)
    

class ActiveSessionResponse(BaseModel):
    
    """
    Public-facing model for a user's session. 
    Hides internal token hashes and DB primary keys.
    """
    session_id: UUID
    device_info: Optional[str]
    ip_address: Optional[str]
    created_at: datetime
    expires_at: datetime
    is_current_session: bool

    model_config = ConfigDict(from_attributes=True)