"""
Authentication models and utilities for JWT-based user authentication.
"""
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from passlib.context import CryptContext
from jose import JWTError, jwt

from app.core.config import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Token(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class TokenData(BaseModel):
    """Data stored in JWT token."""
    user_id: Optional[str] = None
    email: Optional[str] = None


class UserLogin(BaseModel):
    """User login credentials."""
    email: EmailStr
    password: str


class UserRegister(BaseModel):
    """User registration data."""
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str


class User(BaseModel):
    """User model."""
    id: str = Field(alias="_id")
    email: EmailStr
    full_name: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True


class UserInDB(User):
    """User model with hashed password."""
    hashed_password: str


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    # Truncate password safely for bcrypt (72 byte limit)
    # Limit to 50 chars to avoid UTF-8 issues
    safe_password = plain_password[:50] if len(plain_password) > 50 else plain_password
    return pwd_context.verify(safe_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate password hash."""
    # Truncate password safely for bcrypt (72 byte limit)
    # Limit to 50 chars to avoid UTF-8 issues
    safe_password = password[:50] if len(password) > 50 else password
    return pwd_context.hash(safe_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt


def decode_access_token(token: str) -> Optional[TokenData]:
    """Decode and validate JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        
        user_id: str = payload.get("sub")
        email: str = payload.get("email")
        
        if user_id is None:
            return None
            
        return TokenData(user_id=user_id, email=email)
        
    except JWTError:
        return None
