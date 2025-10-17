# app/api/deps.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from app.services.user_service import UserService
from app.schemas.user_schema import UserPublic
from app.core.config import SECRET_KEY, ALGORITHM
from app.db.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/login")
user_service = UserService()

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> UserPublic:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        # detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not token:
        raise credentials_exception
        
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_email: str = payload.get("sub")
        if not user_email:
            raise credentials_exception
            
        # Validate email format
        if not "@" in user_email:
            raise credentials_exception
    except (JWTError, Exception) as e:
        raise credentials_exception

    user = await user_service.get_user_by_email(db, user_email)
    if user is None:
        raise credentials_exception
    
    return UserPublic.model_validate(user)

async def get_current_active_user(current_user: UserPublic = Depends(get_current_user)) -> UserPublic:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

async def get_current_active_admin(current_user: UserPublic = Depends(get_current_active_user)) -> UserPublic:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action"
        )
    return current_user