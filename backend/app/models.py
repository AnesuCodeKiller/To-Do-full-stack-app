from typing import Optional

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    email: Optional[str] = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProtectedResponse(BaseModel):
    message: str
    user: UserResponse


class TodoCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    due_date: Optional[str] = None


class TodoUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    completed: Optional[bool] = None
    due_date: Optional[str] = None


class TodoResponse(BaseModel):
    id: int
    user_id: int
    title: str
    completed: bool
    due_date: Optional[str] = None
