from pydantic import BaseModel


class LoginIdentifier(BaseModel):
    
    identifier: str  # username or email
    password: str

