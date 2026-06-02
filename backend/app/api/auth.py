import datetime
import uuid
from typing import Dict, Any
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import get_db
from app.db import crud
from app.security.hashing import verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def create_token(subject: str, role: str, expires_delta: datetime.timedelta, is_refresh: bool = False) -> tuple[str, str]:
    """
    Generate JWT Token.
    Returns (token_string, jti).
    """
    now = datetime.datetime.utcnow()
    expire = now + expires_delta
    jti = str(uuid.uuid4())
    
    payload = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": expire,
        "jti": jti,
        "refresh": is_refresh
    }
    
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti

async def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: AsyncSession = Depends(get_db)
):
    """
    FastAPI dependency injection to validate access token and fetch current user.
    Also validates that the token session is active in the database.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        username: str = payload.get("sub")
        jti: str = payload.get("jti")
        is_refresh: bool = payload.get("refresh", False)
        
        if username is None or jti is None or is_refresh:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
        
    # Check if session exists and is active in database (revocation list check)
    db_session = await crud.get_session(db, jti)
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired or been revoked.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if db_session.expires_at < datetime.datetime.utcnow():
        await crud.delete_session(db, jti)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    user = await crud.get_user_by_id(db, db_session.user_id)
    if user is None:
        raise credentials_exception
        
    return user

@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Authenticate user, persist session, and return access + refresh tokens.
    """
    user = await crud.get_user_by_username(db, form_data.username)
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # Create tokens
    access_delta = datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_delta = datetime.timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    access_token, access_jti = create_token(user.username, user.role, access_delta, is_refresh=False)
    refresh_token, _ = create_token(user.username, user.role, refresh_delta, is_refresh=True)
    
    # Store access session in SQLite
    expires_at = datetime.datetime.utcnow() + access_delta
    await crud.create_session(db, user_id=user.id, token_jti=access_jti, expires_at=expires_at)
    
    # Audit log
    await crud.create_audit_log(db, user_id=user.id, action="login")
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "role": user.role
    }

@router.post("/logout")
async def logout(
    token: str = Depends(oauth2_scheme), 
    db: AsyncSession = Depends(get_db)
):
    """
    Revoke current session.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        jti = payload.get("jti")
        if jti:
            session = await crud.get_session(db, jti)
            if session:
                await crud.create_audit_log(db, user_id=session.user_id, action="logout")
                await crud.delete_session(db, jti)
    except jwt.PyJWTError:
        pass
        
    return {"detail": "Successfully logged out."}

@router.get("/me")
async def get_me(current_user = Depends(get_current_user)):
    """
    Return current authenticated user profile.
    """
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
        "created_at": current_user.created_at
    }
