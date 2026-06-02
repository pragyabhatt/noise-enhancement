import base64
import hashlib
import logging
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.config import settings

logger = logging.getLogger("security_crypto")

def get_aes_key() -> bytes:
    """
    Acquire the 32-byte AES key.
    If the default key placeholder is present, derive a key using SHA-256
    from the JWT secret key to guarantee a valid url-safe 32-byte key.
    """
    key_str = settings.ENCRYPTION_KEY
    if not key_str or key_str == "ENCRYPTION_KEY_PLACEHOLDER_32_BYTES=":
        # Derive key from JWT Secret key as a reliable secure fallback
        return hashlib.sha256(settings.JWT_SECRET_KEY.encode()).digest()
    try:
        # Attempt to decode base64 key
        decoded_key = base64.urlsafe_b64decode(key_str)
        if len(decoded_key) == 32:
            return decoded_key
        else:
            # Re-hash if length is incorrect
            return hashlib.sha256(decoded_key).digest()
    except Exception:
        # Fallback to hashing the raw key string
        return hashlib.sha256(key_str.encode()).digest()

def encrypt_data(data: bytes) -> bytes:
    """
    Encrypt bytes using AES-256-GCM.
    Returns nonce concatenated with ciphertext.
    """
    key = get_aes_key()
    aesgcm = AESGCM(key)
    nonce = AESGCM.generate_nonce()
    ciphertext = aesgcm.encrypt(nonce, data, None)
    return nonce + ciphertext

def decrypt_data(encrypted_data: bytes) -> bytes:
    """
    Decrypt AES-256-GCM encrypted bytes.
    Expects nonce to be prepended to the ciphertext.
    """
    if len(encrypted_data) < 12:
        raise ValueError("Invalid encrypted data length (missing GCM nonce).")
        
    key = get_aes_key()
    aesgcm = AESGCM(key)
    
    # Nonce is 12 bytes
    nonce = encrypted_data[:12]
    ciphertext = encrypted_data[12:]
    
    return aesgcm.decrypt(nonce, ciphertext, None)

def encrypt_file(file_path: str, data: bytes):
    """
    Encrypt and write data to a file path.
    """
    encrypted = encrypt_data(data)
    with open(file_path, "wb") as f:
        f.write(encrypted)

def decrypt_file(file_path: str) -> bytes:
    """
    Read and decrypt data from a file path.
    """
    with open(file_path, "rb") as f:
        encrypted = f.read()
    return decrypt_data(encrypted)
