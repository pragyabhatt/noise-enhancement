from typing import List, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db import crud
from app.api.auth import get_current_user
from app.security.rbac import allow_admin

router = APIRouter(prefix="/audit", tags=["Audit System"])

@router.get("/logs")
async def get_audit_logs(
    user_id: int = Query(None, description="Filter logs by user ID"),
    action: str = Query(None, description="Filter logs by specific action"),
    limit: int = Query(100, ge=1, le=1000, description="Max logs to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve system audit logs. Securely restricted to Admin role.
    """
    # Enforce RBAC
    allow_admin(current_user)
    
    logs = await crud.list_audit_logs(
        db, user_id=user_id, action=action, limit=limit, offset=offset
    )
    
    # Audit log the access itself!
    await crud.create_audit_log(
        db, 
        user_id=current_user.id, 
        action="audit_view", 
        details_json={"limit": limit, "offset": offset, "filter_user": user_id, "filter_action": action}
    )
    
    # Format response
    result = []
    for log in logs:
        result.append({
            "id": log.id,
            "user_id": log.user_id,
            "username": log.user.username if log.user else "deleted_user",
            "action": log.action,
            "input_hash": log.input_hash,
            "output_hash": log.output_hash,
            "model_version": log.model_version,
            "policy": log.policy,
            "details": log.details_json,
            "created_at": log.created_at
        })
        
    return result
