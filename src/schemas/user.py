from pydantic import BaseModel, Field, field_validator, EmailStr, ConfigDict, model_validator
from typing import Optional
from datetime import datetime
from uuid import UUID
from enum import Enum
from src.security.hashing import PasswordHasher
from src.dependencies import get_password_hasher
from src import identicon


class UserRole(str, Enum):

    admin = 'admin'
    moderator = 'moderator'
    user = 'user'


class UserBase(BaseModel):

    username: str = Field(..., min_length=3, max_length=32, description="Unique username")
    bio: Optional[str] = Field(None, max_length=1024)
    avatar_url: Optional[str] = None
    banner_url: Optional[str] = None


class UserCreate(UserBase):

    password: str = Field(..., min_length=8, description="Raw password to be hashed")
    email: EmailStr
    is_adult: bool

    @field_validator("password", mode="after")
    @classmethod
    def apply_password_hash(cls, v: str) -> str:
        hasher: PasswordHasher = get_password_hasher()
        hashed: str = hasher.get_password_hash(v)
    
        if not hashed:
            raise ValueError("Failed to hash the password.")
            
        return hashed
    
    @model_validator(mode="after")
    def apply_default_identicons(self) -> 'UserCreate':
        clean_username = self.username.strip()
        
        if not self.avatar_url:
            self.avatar_url = identicon.build_avatar_svg_url(clean_username)
            
        if not self.banner_url:
            self.banner_url = identicon.build_banner_svg_url(clean_username)
            
        return self


class UserUpdate(BaseModel):

    bio: Optional[str] = Field(None, max_length=1024)
    avatar_url: Optional[str] = None
    banner_url: Optional[str] = None


class UserPrivateResponse(UserBase):

    id: UUID
    role: UserRole
    
    # Account Status
    is_active: bool
    is_banned: bool    
    
    # Tracking
    last_seen_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserPublicResponse(BaseModel):

    id: UUID
    username: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = Field(None, max_length=1024)
    banner_url: Optional[str] = None
    
    role: UserRole
    is_banned: bool
    is_adult: bool
    created_at: datetime
    last_seen_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)