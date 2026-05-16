from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError
from app.database import get_db
from app.models import User
from app.schemas import *
from app.auth import *
from app.redis_client import blacklist_token, is_blacklisted
from app.config import settings

router = APIRouter()
bearer = HTTPBearer()

# --- Dependency: get current user from token ---
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db)
) -> User:
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    if await is_blacklisted(token):
        raise HTTPException(status_code=401, detail="Token has been revoked")

    user = await db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user, token   # return token too so logout can use it

# --- Register ---
@router.post("/register", response_model=UserRegistrationResponse)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(email=data.email, hashed_password=hash_password(data.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

# --- Login ---
@router.post("/login", response_model=TokenExchangeResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenExchangeResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id)
    )

# --- Protected profile ---
@router.get("/me", response_model=UserRegistrationResponse)
async def get_me(current=Depends(get_current_user)):
    user, _ = current
    return user

# --- Refresh tokens ---
@router.post("/refresh", response_model=TokenExchangeResponse)
async def refresh(credentials: HTTPAuthorizationCredentials = Depends(bearer), db: AsyncSession = Depends(get_db)):
    token = credentials.credentials
    try:
        payload = decode_refresh_token(token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = await db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return TokenExchangeResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id)
    )

# --- Logout ---
@router.post("/logout", response_model=StandardActionResponse)
async def logout(current=Depends(get_current_user)):
    user, token = current
    await blacklist_token(token, settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    return StandardActionResponse(detail="Logout successful")