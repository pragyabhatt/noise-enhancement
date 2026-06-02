from fastapi import HTTPException, status, Depends

ROLE_HIERARCHY = {
    "operator": 1,
    "analyst": 2,
    "admin": 3
}

class RoleChecker:
    def __init__(self, min_role: str):
        """
        min_role: The minimum role rank required to access this endpoint.
        Allowed roles: 'operator', 'analyst', 'admin'.
        """
        if min_role not in ROLE_HIERARCHY:
            raise ValueError(f"Invalid role designation: {min_role}")
        self.min_role = min_role

    def check_permissions(self, user_role: str) -> bool:
        """
        Check if user_role rank is sufficient for this check.
        """
        user_rank = ROLE_HIERARCHY.get(user_role, 0)
        min_rank = ROLE_HIERARCHY.get(self.min_role, 99)
        return user_rank >= min_rank

    def __call__(self, current_user = None):
        """
        FastAPI router dependency injection signature.
        We will rely on endpoints passing in the active user object.
        """
        # Note: If no user is passed, it represents a developer wiring issue
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Security checker misconfigured. No user session provided."
            )
            
        if not self.check_permissions(current_user.role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Access requires at least '{self.min_role}' privileges."
            )
        return current_user

# Pre-defined dependencies for easy route wiring
allow_operator = RoleChecker("operator")
allow_analyst = RoleChecker("analyst")
allow_admin = RoleChecker("admin")
