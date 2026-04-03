from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from uuid import UUID


class AccessTokenCreate(BaseModel):
    
    jwt_token: str
    expires_at: datetime
    

class RefreshTokenCreate(BaseModel):
        
    token_id: UUID
    family_id: UUID
    expires_at: datetime
    replaced_by: Optional[UUID]
    jwt_token: str
    

class RefreshToken(BaseModel):
    
    id: UUID
    user_id: UUID
    expires_at: datetime
    created_at: datetime
    revoked: bool = False
    family_id: UUID
    replaced_by: UUID | None = None

    model_config = {
        "from_attributes": True
    }
    

class SessionResponse(BaseModel):
    
    family_id: UUID
    session_started_at: datetime
    expires_at: datetime
    is_current_session: bool = False