from passlib.context import CryptContext

# Set up bcrypt crypt context for FastAPI passwords
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain-text password against its bcrypt hashed counterpart.
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    """
    Generate a secure bcrypt hash of a plain-text password.
    """
    return pwd_context.hash(password)
