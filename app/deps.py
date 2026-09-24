from collections.abc import Callable
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Role, User
from app.security import decode_access_token

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    error = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired credentials", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        raise error
    user = db.get(User, payload["sub"])
    if not user or not user.is_active:
        raise error
    return user

def require_roles(*roles: Role) -> Callable:
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return dependency

