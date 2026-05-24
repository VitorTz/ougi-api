from pydantic import BaseModel


class SessionPulseResponse(BaseModel):
    
    access_token_ttl: int
    refresh_token_ttl: int
    status: str