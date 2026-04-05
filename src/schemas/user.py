from pydantic import BaseModel, Field, field_validator, EmailStr
from typing import Optional
from datetime import datetime
from uuid import UUID
from enum import Enum
from src.security.argon import get_password_hash


class UserRole(str, Enum):

    admin = 'admin'
    moderator = 'moderator'
    user = 'user'

# ---------------------------------------------------------
# Base Model (Shared fields)
# ---------------------------------------------------------

class UserBase(BaseModel):

    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    avatar_url: Optional[str] = None
    bio: Optional[str] = Field(None, max_length=500)
    banner_url: Optional[str] = None    


# ---------------------------------------------------------
# Create Model (Used for Registration)
# ---------------------------------------------------------

class UserCreate(UserBase):

    password: str = Field(..., min_length=8, description="Raw password to be hashed")
    email: EmailStr
    is_adult: bool

    @field_validator("password", mode="after")
    @classmethod
    def apply_password_hash(cls, v: str) -> str:
        """
        Hashes the password automatically after it passes the minimum length validation.
        The resulting object will store the argon2 hash instead of the raw string.
        """
        hashed = get_password_hash(v)
        
        # Ensure the hashing process was successful
        if not hashed:
            raise ValueError("Failed to hash the password.")
            
        return hashed

# ---------------------------------------------------------
# Update Model (Used for Profile Edits)
# All fields are optional since it's typically a PATCH request
# ---------------------------------------------------------

class UserUpdate(BaseModel):

    avatar_url: Optional[str] = None
    bio: Optional[str] = Field(None, max_length=500)
    banner_url: Optional[str] = None


# ---------------------------------------------------------
# Full Response Model (Used for the user's OWN profile)
# Includes sensitive data like email and birthdate, but EXCLUDES password_hash
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# Public Response Model (Used when viewing OTHER users' profiles)
# Strips out sensitive information completely
# ---------------------------------------------------------

class UserPublicResponse(BaseModel):

    id: UUID
    username: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = Field(None, max_length=500)
    banner_url: Optional[str] = None
    
    role: UserRole
    is_banned: bool
    is_adult: bool
    created_at: datetime
    last_seen_at: Optional[datetime] = None
