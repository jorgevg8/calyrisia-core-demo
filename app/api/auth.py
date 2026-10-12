from __future__ import annotations

from typing import Any, Dict, Callable

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from app.core.config import get_settings
from app.core.security import verify_password, create_access_token, decode_access_token
from app.db import get_connection

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except (jwt.PyJWTError, RuntimeError, ValueError):
        raise credentials_exception

    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, email, role, business_id, full_name, status
                FROM users
                WHERE id = %s AND status = 'active'
                """,
                (user_id,),
            )
            user = cur.fetchone()
            if user is None:
                raise credentials_exception

            db_role = str(user[2]).upper()
            db_business_id = str(user[3])
            token_business_id = str(payload.get("business_id"))
            token_role = str(payload.get("role", "")).upper()

            # No aceptamos que el JWT diga una identidad distinta a PostgreSQL.
            if token_business_id != db_business_id or token_role != db_role:
                raise credentials_exception

            return {
                "id": str(user[0]),
                "email": user[1],
                "role": db_role,
                "business_id": db_business_id,
                "full_name": user[4],
                "status": user[5],
            }


def require_roles(*allowed_roles: str) -> Callable:
    allowed = {role.upper() for role in allowed_roles}

    async def dependency(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        if current_user["role"] not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Rol no autorizado. Roles permitidos: {sorted(allowed)}",
            )
        return current_user

    return dependency


async def require_business_access(
    business_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if str(business_id) != str(current_user["business_id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario no tiene acceso a ese business_id.",
        )
    return current_user


@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, password_hash, role, business_id
                FROM users
                WHERE email = %s AND status = 'active'
                """,
                (form_data.username,),
            )
            user = cur.fetchone()

            if not user or not verify_password(form_data.password, user[1]):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Correo o contraseña incorrectos",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            role = str(user[2]).upper()
            access_token = create_access_token(
                subject=user[0], role=role, business_id=user[3]
            )
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "role": role,
                "business_id": str(user[3]),
                "expires_in_minutes": get_settings().jwt_exp_minutes,
            }


@router.get("/me")
async def read_users_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    return {"success": True, "user": current_user}


@router.get("/owner-only")
async def owner_only_endpoint(
    current_user: Dict[str, Any] = Depends(require_roles("OWNER")),
):
    return {"success": True, "message": "Acceso autorizado al panel administrativo.", "user": current_user}
