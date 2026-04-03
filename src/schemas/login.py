from pydantic import BaseModel


class LoginIdentifier(BaseModel):
    
    username: str
    password: str

