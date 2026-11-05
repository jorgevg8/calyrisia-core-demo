from __future__ import annotations

from typing import Any, Dict, Callable
from uuid import uuid4

from app.core.security import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from app.core.config import get_settings
from app.core.security import verify_password, get_password_hash, create_access_token, decode_access_token
from app.db import get_connection
from app.services.commercial_limits import get_business_plan, normalize_plan, plan_limits

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def _ensure_user_business_record(conn, user_id: str, business_id: str | None, full_name: str | None, email: str) -> dict[str, Any]:
    """Ensure the authenticated user always has a valid business record with a non-empty name."""
    default_name = f"Negocio de {(full_name or email or 'Propietario').split('@')[0].strip()}"
    with conn.cursor() as cur:
        b_row = None
        if business_id and str(business_id).lower() != "none":
            try:
                cur.execute(
                    """
                    SELECT id, COALESCE(NULLIF(TRIM(name), ''), %s) AS name,
                           COALESCE(business_type, 'tech_store') AS business_type,
                           COALESCE(timezone, 'America/Caracas') AS timezone,
                           COALESCE(currency, 'USD') AS currency,
                           COALESCE(status, 'active') AS status,
                           COALESCE(to_jsonb(businesses)->>'plan_code', 'free') AS plan_code
                    FROM businesses
                    WHERE id = %s
                    """,
                    (default_name, str(business_id)),
                )
                b_row = cur.fetchone()
            except Exception:
                conn.rollback()
                b_row = None

        if not b_row:
            target_bid = str(business_id) if (business_id and str(business_id).lower() != "none") else str(uuid4())
            try:
                cur.execute(
                    """
                    INSERT INTO businesses (id, name, business_type, currency, timezone, status, plan_code)
                    VALUES (%s, %s, 'tech_store', 'USD', 'America/Caracas', 'active', 'free')
                    ON CONFLICT (id) DO UPDATE SET status = 'active'
                    RETURNING id, COALESCE(NULLIF(TRIM(name), ''), %s), COALESCE(business_type, 'tech_store'),
                              COALESCE(timezone, 'America/Caracas'), COALESCE(currency, 'USD'),
                              COALESCE(status, 'active'), COALESCE(to_jsonb(businesses)->>'plan_code', 'free')
                    """,
                    (target_bid, default_name, default_name),
                )
                b_row = cur.fetchone()
                cur.execute("UPDATE users SET business_id = %s WHERE id = %s", (target_bid, str(user_id)))
                conn.commit()
            except Exception:
                conn.rollback()
                b_row = (target_bid, default_name, "tech_store", "America/Caracas", "USD", "active", "free")

    resolved_plan = "free"
    try:
        resolved_plan = get_business_plan(conn, str(b_row[0]))
    except Exception:
        resolved_plan = normalize_plan(str(b_row[6] or "free"))

    return {
        "id": str(b_row[0]),
        "name": str(b_row[1] or default_name),
        "business_name": str(b_row[1] or default_name),
        "business_type": str(b_row[2] or "tech_store"),
        "timezone": str(b_row[3] or "America/Caracas"),
        "currency": str(b_row[4] or "USD"),
        "status": str(b_row[5] or "active"),
        "plan_code": resolved_plan,
        "plan": plan_limits(resolved_plan),
    }


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

            db_role = str(user[2] or "OWNER").upper()
            db_business_id = str(user[3]) if user[3] else ""
            token_business_id = str(payload.get("business_id") or "")
            token_role = str(payload.get("role", "")).upper()

            if db_business_id and token_business_id != db_business_id:
                raise credentials_exception
            if token_role != db_role:
                raise credentials_exception

        business_obj = _ensure_user_business_record(conn, str(user[0]), db_business_id, user[4], str(user[1] or ""))
        display_name = str(user[4] or user[1] or "Ejecutivo CALYRISIA").strip()
        return {
            "id": str(user[0]),
            "email": user[1],
            "name": display_name,
            "full_name": display_name,
            "role": db_role,
            "business_id": business_obj["id"],
            "status": user[5],
            "business": business_obj,
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
    clean_username = (form_data.username or "").strip()
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, password_hash, role, business_id, full_name, email
                FROM users
                WHERE LOWER(TRIM(email)) = LOWER(TRIM(%s)) AND status = 'active'
                ORDER BY created_at DESC NULLS LAST
                LIMIT 1
                """,
                (clean_username,),
            )
            user = cur.fetchone()

            if not user or not verify_password(form_data.password, user[1]):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Correo o contraseña incorrectos",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            stored_hash = str(user[1] or "")
            if ":" not in stored_hash:
                try:
                    new_hash = get_password_hash(form_data.password)
                    cur.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, user[0]))
                    conn.commit()
                except Exception:
                    conn.rollback()

        role = str(user[2] or "OWNER").upper()
        business_obj = _ensure_user_business_record(conn, str(user[0]), str(user[3]) if user[3] else None, user[4], str(user[5] or clean_username))
        display_name = str(user[4] or user[5] or clean_username).strip()
        access_token = create_access_token(
            subject=user[0], role=role, business_id=business_obj["id"]
        )
        user_payload = {
            "id": str(user[0]),
            "email": str(user[5] or clean_username),
            "name": display_name,
            "full_name": display_name,
            "role": role,
            "business_id": business_obj["id"],
            "status": "active",
            "business": business_obj,
        }
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "role": role,
            "business_id": business_obj["id"],
            "name": business_obj["name"],
            "user": user_payload,
            "business": business_obj,
            "businesses": [business_obj],
            "expires_in_minutes": get_settings().jwt_exp_minutes,
        }


@router.get("/me")
async def read_users_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    business_obj = current_user.get("business") or {
        "id": str(current_user.get("business_id") or ""),
        "name": str(current_user.get("name") or "Mi Negocio CALYRISIA"),
        "business_type": "tech_store",
        "plan_code": "free",
    }
    return {
        "success": True,
        "name": business_obj.get("name") or "Mi Negocio CALYRISIA",
        "user": current_user,
        "business": business_obj,
        "businesses": [business_obj],
    }


@router.get("/owner-only")
async def owner_only_endpoint(
    current_user: Dict[str, Any] = Depends(require_roles("OWNER")),
):
    return {"success": True, "message": "Acceso OWNER concedido", "user": current_user}
