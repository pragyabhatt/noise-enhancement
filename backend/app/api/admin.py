import os
import hashlib
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import get_db
from app.db import crud
from app.api.auth import get_current_user
from app.security.rbac import allow_admin
from app.security.hashing import get_password_hash

router = APIRouter(prefix="/admin", tags=["Admin Operations"])

def get_file_sha256(file_path: str) -> str:
    """
    Helper to calculate SHA-256 checksum of a file.
    """
    if not os.path.exists(file_path):
        return "not_found"
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()

@router.get("/models")
async def get_loaded_models(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Retrieve loaded model versions and their SHA-256 integrity hashes.
    """
    # Enforce RBAC
    allow_admin(current_user)
    
    model_files = {
        "deepfilternet2_enc": "enc_conv_streaming.onnx",
        "deepfilternet2_gru": "enc_gru_streaming.onnx",
        "deepfilternet2_erb_dec": "erb_dec_streaming.onnx",
        "deepfilternet2_df_dec": "df_dec_streaming.onnx",
        "speaker_embedder": "speaker_embedder.onnx"
    }
    
    models_manifest = {}
    fallback_active = False
    
    for model_name, filename in model_files.items():
        path = os.path.join(settings.MODELS_DIR, filename)
        exists = os.path.exists(path)
        sha256_hash = get_file_sha256(path) if exists else None
        
        models_manifest[model_name] = {
            "filename": filename,
            "path": path,
            "status": "loaded" if exists else "missing",
            "sha256": sha256_hash
        }
        
        if not exists:
            fallback_active = True
            
    # Audit log access
    await crud.create_audit_log(
        db, 
        user_id=current_user.id, 
        action="admin_view_models",
        details_json={"fallback_active": fallback_active}
    )
    
    return {
        "models_dir": settings.MODELS_DIR,
        "fallback_active": fallback_active,
        "manifest": models_manifest,
        "pipeline_version": "catr-se-v0.1-hybrid"
    }

@router.get("/users")
async def list_user_accounts(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all user accounts in the system. Securely restricted to Admin.
    """
    allow_admin(current_user)
    users = await crud.list_users(db, limit=limit, offset=offset)
    
    return [
        {
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "created_at": u.created_at
        } for u in users
    ]

@router.post("/users")
async def create_user_account(
    username: str = Query(..., description="Unique alphanumeric username"),
    password: str = Query(..., description="Plain-text password"),
    role: str = Query("operator", description="User role: admin, analyst, operator"),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new user account. Securely restricted to Admin.
    """
    allow_admin(current_user)
    
    # Validation
    if not username.isalnum():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be alphanumeric."
        )
    if len(password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long."
        )
    if role not in ["operator", "analyst", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be one of: operator, analyst, admin"
        )
        
    # Check if username exists
    existing_user = await crud.get_user_by_username(db, username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists."
        )
        
    password_hash = get_password_hash(password)
    new_user = await crud.create_user(db, username, password_hash, role)
    
    # Audit log creation
    await crud.create_audit_log(
        db, 
        user_id=current_user.id, 
        action="user_create", 
        details_json={"new_user": username, "assigned_role": role}
    )
    
    return {
        "id": new_user.id,
        "username": new_user.username,
        "role": new_user.role,
        "created_at": new_user.created_at
    }
