import hashlib
import hmac
import base64
import json
import time
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from ips_app.db import get_db_connection

SECRET_KEY = b"IPS_FASTAPI_JWT_ALT_SECRET_2026_KEY"
security = HTTPBearer()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def create_access_token(username: str, role: str) -> str:
    # Token payload: username, role, expiration timestamp (8 hours)
    expiry = int(time.time()) + (8 * 3600)
    payload = {
        "sub": username,
        "role": role,
        "exp": expiry
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    
    # Sign payload
    signature = hmac.new(SECRET_KEY, payload_b64.encode(), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    
    return f"{payload_b64}.{sig_b64}"

def verify_token(token: str) -> dict:
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        
        payload_b64, sig_b64 = parts
        
        # Verify signature
        expected_sig = hmac.new(SECRET_KEY, payload_b64.encode(), hashlib.sha256).digest()
        expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).decode().rstrip("=")
        
        if not hmac.compare_digest(sig_b64, expected_sig_b64):
            return None
        
        # Decode payload
        padding = "=" * (4 - len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(payload_b64 + padding).decode()
        payload = json.loads(payload_json)
        
        # Check expiry
        if time.time() > payload.get("exp", 0):
            return None
        
        return payload
    except Exception:
        return None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    user_data = verify_token(token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token")
    return user_data

class RoleChecker:
    def __init__(self, allowed_roles: list):
        self.allowed_roles = allowed_roles

    def __call__(self, user: dict = Depends(get_current_user)):
        if user.get("role") not in self.allowed_roles:
            raise HTTPException(status_code=403, detail="Operation not permitted for your current role")
        return user
