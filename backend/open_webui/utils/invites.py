import re
import secrets
import string
import time
import uuid

from typing import Optional

from sqlalchemy.orm import Session

from open_webui.models.groups import Groups
from open_webui.models.users import UserModel


INVITE_CHARSET = string.ascii_uppercase + string.digits
INVITE_SCOPE_VALUES = {"admin", "groups", "all"}


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _sanitize_prefix(prefix: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "", (prefix or "").strip())
    return cleaned[:24]


def _set_invite_codes(config, invite_codes: list[dict]) -> None:
    config.INVITE_CODES = invite_codes


def get_invite_policy(config) -> dict:
    scope = str(getattr(config, "INVITE_CREATOR_SCOPE", "admin")).lower().strip()
    if scope not in INVITE_SCOPE_VALUES:
        scope = "admin"

    group_ids = getattr(config, "INVITE_CREATOR_GROUP_IDS", []) or []
    if not isinstance(group_ids, list):
        group_ids = []
    group_ids = [str(group_id) for group_id in group_ids if str(group_id).strip()]

    return {
        "enabled": bool(getattr(config, "ENABLE_INVITE_ONLY_AUTH", False)),
        "creator_scope": scope,
        "creator_group_ids": group_ids,
        "creator_cooldown_seconds": max(
            0, _safe_int(getattr(config, "INVITE_CREATOR_COOLDOWN_SECONDS", 0), 0)
        ),
        "code_length": max(4, min(32, _safe_int(getattr(config, "INVITE_CODE_LENGTH", 8), 8))),
        "code_ttl_seconds": max(
            0, _safe_int(getattr(config, "INVITE_CODE_TTL_SECONDS", 604800), 604800)
        ),
        "code_prefix": _sanitize_prefix(getattr(config, "INVITE_CODE_PREFIX", "")),
        "code_reusable": bool(getattr(config, "INVITE_CODE_REUSABLE", False)),
        "code_max_uses": max(0, _safe_int(getattr(config, "INVITE_CODE_MAX_USES", 1), 1)),
    }


def get_clean_invite_codes(config) -> list[dict]:
    now = int(time.time())
    invite_codes = getattr(config, "INVITE_CODES", []) or []
    if not isinstance(invite_codes, list):
        invite_codes = []

    cleaned: list[dict] = []
    changed = False

    for invite in invite_codes:
        if not isinstance(invite, dict):
            changed = True
            continue

        code = str(invite.get("code", "")).strip()
        if not code:
            changed = True
            continue

        expires_at = _safe_int(invite.get("expires_at"), 0)
        uses_count = max(0, _safe_int(invite.get("uses_count"), 0))
        max_uses = _safe_int(invite.get("max_uses"), 0)

        if expires_at > 0 and now >= expires_at:
            changed = True
            continue

        if max_uses > 0 and uses_count >= max_uses:
            changed = True
            continue

        cleaned.append(
            {
                "id": str(invite.get("id") or uuid.uuid4()),
                "code": code,
                "created_by": str(invite.get("created_by") or ""),
                "created_at": _safe_int(invite.get("created_at"), now),
                "expires_at": expires_at if expires_at > 0 else None,
                "uses_count": uses_count,
                "max_uses": max_uses if max_uses > 0 else None,
                "last_used_at": _safe_int(invite.get("last_used_at"), 0) or None,
                "used_by": (
                    [str(item) for item in invite.get("used_by", []) if str(item).strip()]
                    if isinstance(invite.get("used_by"), list)
                    else []
                ),
            }
        )

    if changed or len(cleaned) != len(invite_codes):
        _set_invite_codes(config, cleaned)

    return cleaned


def can_user_create_invite_codes(
    user: UserModel,
    config,
    db: Optional[Session] = None,
) -> tuple[bool, str, int]:
    if not user:
        return False, "Authentication required.", 0

    if user.role == "admin":
        return True, "", 0

    policy = get_invite_policy(config)
    scope = policy["creator_scope"]

    if scope == "admin":
        return False, "Only admins can create invite codes.", 0

    if scope == "groups":
        allowed_group_ids = set(policy["creator_group_ids"])
        if not allowed_group_ids:
            return False, "No creator groups are configured.", 0

        user_group_ids = {group.id for group in Groups.get_groups_by_member_id(user.id, db=db)}
        if not user_group_ids.intersection(allowed_group_ids):
            return False, "You do not have permission to create invite codes.", 0
        return True, "", 0

    cooldown_seconds = policy["creator_cooldown_seconds"]
    if cooldown_seconds <= 0:
        return True, "", 0

    now = int(time.time())
    invite_codes = get_clean_invite_codes(config)
    latest_created_at = max(
        [
            _safe_int(invite.get("created_at"), 0)
            for invite in invite_codes
            if invite.get("created_by") == user.id
        ]
        or [0]
    )

    remaining = latest_created_at + cooldown_seconds - now
    if remaining > 0:
        return (
            False,
            f"Invite creation cooldown is active. Try again in {remaining} seconds.",
            remaining,
        )

    return True, "", 0


def create_invite_code(config, creator_id: str) -> dict:
    policy = get_invite_policy(config)
    invite_codes = get_clean_invite_codes(config)
    active_codes = {str(invite.get("code", "")).upper() for invite in invite_codes}

    code_length = policy["code_length"]
    code_prefix = policy["code_prefix"]
    separator = "-" if code_prefix else ""

    code = ""
    for _ in range(50):
        random_part = "".join(secrets.choice(INVITE_CHARSET) for _ in range(code_length))
        candidate = f"{code_prefix}{separator}{random_part}"
        if candidate.upper() not in active_codes:
            code = candidate
            break

    if not code:
        raise RuntimeError("Unable to generate a unique invite code.")

    now = int(time.time())
    invite = {
        "id": str(uuid.uuid4()),
        "code": code,
        "created_by": creator_id,
        "created_at": now,
        "expires_at": (now + policy["code_ttl_seconds"]) if policy["code_ttl_seconds"] > 0 else None,
        "uses_count": 0,
        "max_uses": (
            (
                None
                if policy["code_max_uses"] <= 0
                else max(1, policy["code_max_uses"])
            )
            if policy["code_reusable"]
            else 1
        ),
        "last_used_at": None,
        "used_by": [],
    }

    invite_codes.append(invite)
    _set_invite_codes(config, invite_codes)

    return invite


def consume_invite_code(
    config,
    invite_code: str,
    consumed_by: Optional[str] = None,
) -> tuple[bool, str, Optional[dict]]:
    normalized_code = (invite_code or "").strip()
    if not normalized_code:
        return False, "Invite code is required.", None

    invite_codes = get_clean_invite_codes(config)
    lookup = normalized_code.upper()

    for idx, invite in enumerate(invite_codes):
        if str(invite.get("code", "")).upper() != lookup:
            continue

        uses_count = max(0, _safe_int(invite.get("uses_count"), 0))
        max_uses = _safe_int(invite.get("max_uses"), 0)

        if max_uses > 0 and uses_count >= max_uses:
            return False, "Invite code has reached its usage limit.", None

        now = int(time.time())
        invite["uses_count"] = uses_count + 1
        invite["last_used_at"] = now

        if consumed_by:
            used_by = invite.get("used_by", [])
            if not isinstance(used_by, list):
                used_by = []
            used_by.append(str(consumed_by))
            invite["used_by"] = used_by[-100:]

        if max_uses > 0 and invite["uses_count"] >= max_uses:
            invite_codes.pop(idx)
        else:
            invite_codes[idx] = invite

        _set_invite_codes(config, invite_codes)
        return True, "", invite

    return False, "Invite code is invalid or expired.", None


def get_invite_codes_for_user(user: UserModel, config) -> list[dict]:
    invite_codes = get_clean_invite_codes(config)
    if user.role == "admin":
        return invite_codes
    return [invite for invite in invite_codes if invite.get("created_by") == user.id]
