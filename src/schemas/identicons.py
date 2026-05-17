from pydantic import BaseModel


class CombinedIdenticonResponse(BaseModel):
    
    avatar_svg: str
    banner_svg: str