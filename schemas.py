from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

# ── Auth Schemas ──────────────────────────────
class RegisterRequest(BaseModel):
    name: str
    email: EmailStr        # validates email format automatically
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    created_at: datetime

    class Config:
        from_attributes = True

# What client sends to CREATE a todo
class TodoCreate(BaseModel):
    title: str
    description: Optional[str] = None

# What client sends to UPDATE a todo
class TodoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None

# What API sends back in response
class TodoResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    completed: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True
        