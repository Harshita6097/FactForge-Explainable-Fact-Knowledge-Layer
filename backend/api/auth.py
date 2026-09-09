import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from database.db import get_db
from utils.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter()


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    token: str
    user: dict


@router.post("/auth/register", response_model=AuthResponse)
def register(body: RegisterRequest):
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")

    with get_db() as conn:
        existing = conn.execute("SELECT id FROM users WHERE email=?", (body.email.lower(),)).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="An account with this email already exists")

        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO users (id, email, name, hashed_password, created_at) VALUES (?,?,?,?,?)",
            (user_id, body.email.lower(), body.name.strip(), hash_password(body.password), now),
        )

    token = create_access_token(user_id, body.email.lower())
    return AuthResponse(
        token=token,
        user={"id": user_id, "email": body.email.lower(), "name": body.name.strip(), "created_at": now},
    )


@router.post("/auth/login", response_model=AuthResponse)
def login(body: LoginRequest):
    with get_db() as conn:
        user = conn.execute(
            "SELECT id, email, name, hashed_password, created_at FROM users WHERE email=?",
            (body.email.lower(),),
        ).fetchone()

    if not user or not verify_password(body.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user["id"], user["email"])
    return AuthResponse(
        token=token,
        user={"id": user["id"], "email": user["email"], "name": user["name"], "created_at": user["created_at"]},
    )


@router.get("/auth/me")
def me(current_user: dict = Depends(get_current_user)):
    return current_user
