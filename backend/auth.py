import os
import bcrypt
import jwt
from datetime import timedelta
from fastapi import APIRouter, HTTPException, Request, Depends
from bson import ObjectId

from core import db, now_utc
from models import LoginRequest, RegisterRequest

JWT_ALGORITHM = "HS256"

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _secret() -> str:
    return os.environ["JWT_SECRET"]


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": now_utc() + timedelta(days=7),
        "type": "access",
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def _serialize_user(user: dict) -> dict:
    return {
        "id": str(user["_id"]),
        "email": user["email"],
        "name": user.get("name", ""),
        "role": user.get("role", "user"),
    }


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Não autenticado")
    try:
        payload = jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Token inválido")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="Utilizador não encontrado")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sessão expirada")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")


@auth_router.post("/register")
async def register(payload: RegisterRequest):
    email = payload.email.strip().lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email já registado")
    doc = {
        "email": email,
        "password_hash": hash_password(payload.password),
        "name": payload.name or "Utilizador",
        "role": "user",
        "created_at": now_utc().isoformat(),
    }
    res = await db.users.insert_one(doc)
    doc["_id"] = res.inserted_id
    token = create_access_token(str(res.inserted_id), email)
    return {"token": token, "user": _serialize_user(doc)}


@auth_router.post("/login")
async def login(payload: LoginRequest):
    email = payload.email.strip().lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    token = create_access_token(str(user["_id"]), email)
    return {"token": token, "user": _serialize_user(user)}


@auth_router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return _serialize_user(user)


async def seed_users():
    password = os.environ.get("SEED_PASSWORD", "100%Smartize")
    seed = [
        ("miguel.carvalho@smartize.pt", "Miguel Carvalho"),
        ("carlos.miguel@smartize.pt", "Carlos Miguel"),
    ]
    for email, name in seed:
        existing = await db.users.find_one({"email": email})
        if not existing:
            await db.users.insert_one({
                "email": email,
                "password_hash": hash_password(password),
                "name": name,
                "role": "admin",
                "created_at": now_utc().isoformat(),
            })
        elif not verify_password(password, existing["password_hash"]):
            await db.users.update_one(
                {"email": email}, {"$set": {"password_hash": hash_password(password)}}
            )
