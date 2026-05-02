import base64
import binascii
import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import time
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

try:
    from backend.app.database import (
        create_user, get_user_by_id, get_user_by_username,
        create_todo, get_todos_by_user, update_todo, delete_todo
    )
    from backend.app.models import (
        LoginRequest,
        ProtectedResponse,
        RegisterRequest,
        TokenResponse,
        UserResponse,
        TodoCreate,
        TodoUpdate,
        TodoResponse,
    )
except ModuleNotFoundError:
    from app.database import (
        create_user, get_user_by_id, get_user_by_username,
        create_todo, get_todos_by_user, update_todo, delete_todo
    )
    from app.models import (
        LoginRequest,
        ProtectedResponse,
        RegisterRequest,
        TokenResponse,
        UserResponse,
        TodoCreate,
        TodoUpdate,
        TodoResponse,
    )


logger = logging.getLogger("todo_backend.auth")
router = APIRouter()
security = HTTPBearer(auto_error=False)

TOKEN_SECRET = os.getenv("TOKEN_SECRET", "change-this-development-secret")
TOKEN_TTL_SECONDS = 60 * 60
PASSWORD_ITERATIONS = 260_000


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return (
        f"pbkdf2_sha256${PASSWORD_ITERATIONS}$"
        f"{_base64url_encode(salt)}${_base64url_encode(digest)}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt, digest = stored_hash.split("$", 3)
    except ValueError:
        return False

    if algorithm != "pbkdf2_sha256":
        return False

    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        _base64url_decode(salt),
        int(iterations),
    )
    return hmac.compare_digest(_base64url_encode(candidate), digest)


def create_token(user_id: int, username: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": int(time.time()),
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    signing_input = ".".join(
        [
            _base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = hmac.new(
        TOKEN_SECRET.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_base64url_encode(signature)}"


def decode_token(token: str) -> Dict[str, Any]:
    try:
        header, payload, signature = token.split(".", 2)
        signing_input = f"{header}.{payload}"
        expected_signature = hmac.new(
            TOKEN_SECRET.encode("utf-8"),
            signing_input.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(_base64url_encode(expected_signature), signature):
            raise ValueError("Invalid signature")

        decoded_payload = json.loads(_base64url_decode(payload))
    except (binascii.Error, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    if int(decoded_payload.get("exp", 0)) < int(time.time()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )
    return decoded_payload


def row_to_user(row) -> UserResponse:
    return UserResponse(id=row["id"], username=row["username"], email=row["email"])


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserResponse:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    payload = decode_token(credentials.credentials)
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
        )
    return row_to_user(user)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest) -> UserResponse:
    try:
        user = create_user(
            username=payload.username.strip(),
            email=payload.email.strip() if payload.email else None,
            password_hash=hash_password(payload.password),
        )
    except sqlite3.IntegrityError:
        logger.info("Registration failed for duplicate username/email: %s", payload.username)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists",
        )
    return row_to_user(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    user = get_user_by_username(payload.username.strip())
    if user is None or not verify_password(payload.password, user["password_hash"]):
        logger.info("Invalid login attempt for username: %s", payload.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token = create_token(user_id=user["id"], username=user["username"])
    return TokenResponse(access_token=token)


@router.get("/protected", response_model=ProtectedResponse)
def protected(current_user: UserResponse = Depends(get_current_user)) -> ProtectedResponse:
    return ProtectedResponse(
        message="Token is valid",
        user=current_user,
    )


@router.get("/todos", response_model=list[TodoResponse])
def get_todos(current_user: UserResponse = Depends(get_current_user)) -> list[TodoResponse]:
    rows = get_todos_by_user(current_user.id)
    return [
        TodoResponse(
            id=row["id"],
            user_id=row["user_id"],
            title=row["title"],
            completed=bool(row["completed"]),
            due_date=row["due_date"]
        )
        for row in rows
    ]


@router.post("/todos", response_model=TodoResponse, status_code=status.HTTP_201_CREATED)
def create_new_todo(payload: TodoCreate, current_user: UserResponse = Depends(get_current_user)) -> TodoResponse:
    row = create_todo(current_user.id, payload.title.strip(), payload.due_date)
    return TodoResponse(
        id=row["id"],
        user_id=row["user_id"],
        title=row["title"],
        completed=bool(row["completed"]),
        due_date=row["due_date"]
    )


@router.put("/todos/{todo_id}", response_model=TodoResponse)
def update_existing_todo(todo_id: int, payload: TodoUpdate, current_user: UserResponse = Depends(get_current_user)) -> TodoResponse:
    row = update_todo(
        user_id=current_user.id,
        todo_id=todo_id,
        title=payload.title.strip() if payload.title else None,
        completed=payload.completed,
        due_date=payload.due_date
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")
    
    return TodoResponse(
        id=row["id"],
        user_id=row["user_id"],
        title=row["title"],
        completed=bool(row["completed"]),
        due_date=row["due_date"]
    )


@router.delete("/todos/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_todo(todo_id: int, current_user: UserResponse = Depends(get_current_user)) -> None:
    success = delete_todo(current_user.id, todo_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")

