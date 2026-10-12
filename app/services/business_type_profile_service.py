
from __future__ import annotations

import copy
import re
import unicodedata
from typing import Any
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb


class BusinessTypeProfileError(Exception):
    pass


class BusinessTypeProfileService:
    """Step 42: data-driven vertical behavior profiles with tenant overrides."""

    def __init__(self, conn):
        self.conn = conn

    @staticmethod
    def normalize(value: str | None) -> str:
        text = str(value or "").strip().lower()
        text = "".join(
            c for c in unicodedata.normalize("NFKD", text)
            if not unicodedata.combining(c)
        )
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        result = copy.deepcopy(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = BusinessTypeProfileService.deep_merge(result[key], value)
            else:
                result[key] = copy.deepcopy(value)
        return result

    def list_profiles(self, enabled_only: bool = True) -> list[dict[str, Any]]:
        where = "WHERE enabled = TRUE" if enabled_only else ""
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, profile_key, display_name, description, version, config, enabled,
                       created_at, updated_at
                FROM business_type_profiles
                {where}
                ORDER BY display_name
                """
            )
            rows = cur.fetchall()
        keys = ["id", "profile_key", "display_name", "description", "version", "config", "enabled", "created_at", "updated_at"]
        return [dict(zip(keys, row)) for row in rows]

    def _resolve_base(self, business_type: str | None, industry: str | None) -> dict[str, Any] | None:
        candidates = [self.normalize(business_type), self.normalize(industry)]
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, profile_key, display_name, description, version, config, enabled
                FROM business_type_profiles
                WHERE enabled = TRUE
                ORDER BY display_name
                """
            )
            rows = cur.fetchall()
        normalized_candidates = {c for c in candidates if c}
        best = None
        for row in rows:
            config = row[5] or {}
            aliases = [self.normalize(x) for x in config.get("aliases", [])]
            tokens = {self.normalize(row[1]), self.normalize(row[2]), *aliases}
            if normalized_candidates & tokens:
                best = row
                break
        if best is None:
            # Deterministic fallback so every tenant still gets a profile.
            for row in rows:
                if self.normalize(row[1]) == "retail":
                    best = row
                    break
        if best is None:
            return None
        return {
            "id": best[0],
            "profile_key": best[1],
            "display_name": best[2],
            "description": best[3],
            "version": best[4],
            "config": best[5] or {},
            "enabled": best[6],
        }

    def _get_business_identity(self, business_id: UUID) -> tuple[str, str, dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT b.business_type, COALESCE(bp.industry, ''), COALESCE(bp.additional_settings, '{}'::jsonb)
                FROM businesses b
                LEFT JOIN business_profiles bp
                  ON bp.business_id = b.id AND bp.status = 'active'
                WHERE b.id = %s
                ORDER BY bp.created_at DESC NULLS LAST
                LIMIT 1
                """,
                (business_id,),
            )
            row = cur.fetchone()
        if not row:
            raise BusinessTypeProfileError("Business not found")
        return str(row[0] or ""), str(row[1] or ""), row[2] or {}

    def resolve_for_business(self, business_id: UUID) -> dict[str, Any]:
        business_type, industry, additional_settings = self._get_business_identity(business_id)
        base = self._resolve_base(business_type, industry)
        if base is None:
            raise BusinessTypeProfileError("No enabled business type profiles are seeded.")

        overrides = {}
        stored = additional_settings.get("business_type_profile_overrides")
        if isinstance(stored, dict):
            overrides = stored
        merged_config = self.deep_merge(base["config"], overrides)
        merged_config.pop("aliases", None)

        return {
            "business_id": str(business_id),
            "business_type": business_type,
            "industry": industry,
            "profile_key": base["profile_key"],
            "display_name": base["display_name"],
            "description": base["description"],
            "version": base["version"],
            "config": merged_config,
            "overrides": overrides,
            "source": "database_profile_plus_tenant_overrides" if overrides else "database_profile",
        }

    def set_overrides(self, business_id: UUID, overrides: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(overrides, dict):
            raise BusinessTypeProfileError("overrides debe ser un objeto JSON.")
        if len(str(overrides)) > 20000:
            raise BusinessTypeProfileError("overrides es demasiado grande.")
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT additional_settings FROM business_profiles WHERE business_id = %s AND status = 'active' ORDER BY created_at DESC LIMIT 1",
                (business_id,),
            )
            row = cur.fetchone()
            if not row:
                raise BusinessTypeProfileError("Business profile not found")
            current = row[0] or {}
            current["business_type_profile_overrides"] = overrides
            cur.execute(
                """
                UPDATE business_profiles
                SET additional_settings = %s,
                    profile_version = profile_version + 1,
                    updated_at = NOW()
                WHERE business_id = %s AND status = 'active'
                """,
                (Jsonb(current), business_id),
            )
        return self.resolve_for_business(business_id)

    def clear_overrides(self, business_id: UUID) -> dict[str, Any]:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT additional_settings FROM business_profiles WHERE business_id = %s AND status = 'active' ORDER BY created_at DESC LIMIT 1",
                (business_id,),
            )
            row = cur.fetchone()
            if not row:
                raise BusinessTypeProfileError("Business profile not found")
            current = row[0] or {}
            current.pop("business_type_profile_overrides", None)
            cur.execute(
                """
                UPDATE business_profiles
                SET additional_settings = %s,
                    profile_version = profile_version + 1,
                    updated_at = NOW()
                WHERE business_id = %s AND status = 'active'
                """,
                (Jsonb(current), business_id),
            )
        return self.resolve_for_business(business_id)

    def audit_profile_change(self, business_id: UUID, user_id: UUID | None, action_type: str, reason: str, metadata: dict[str, Any]) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_logs (
                    business_id, actor_type, action_type, resource_type,
                    resource_id, status, reason, metadata, created_at
                )
                VALUES (%s, 'user', %s, 'business_type_profile', %s, 'success', %s, %s, NOW())
                """,
                (business_id, action_type, business_id, reason, Jsonb(metadata)),
            )
