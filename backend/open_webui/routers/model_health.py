from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from open_webui.models.access_grants import has_public_read_access_grant
from open_webui.models.model_health import (
    ModelHealthCheckModel,
    ModelHealthChecks,
)
from open_webui.models.users import Users
from open_webui.utils.auth import (
    decode_token,
    get_current_user_by_api_key,
    get_http_authorization_cred,
)
from open_webui.utils.model_health import (
    MODEL_HEALTH_CHECK_INTERVAL_SECONDS,
    MODEL_HEALTH_HISTORY_DAYS,
    get_enabled_models_for_health,
)

router = APIRouter()


class ModelHealthDailyBucket(BaseModel):
    date: str
    status: str
    uptime_ratio: Optional[float] = None
    successful_checks: int = 0
    total_checks: int = 0


class ModelHealthLatestStatus(BaseModel):
    checked_at: int
    status: bool
    latency_ms: Optional[int] = None
    error: Optional[str] = None


class ModelHealthStatusItem(BaseModel):
    id: str
    name: str
    provider: Optional[str] = None
    latest: Optional[ModelHealthLatestStatus] = None
    uptime_ratio_90d: Optional[float] = None
    successful_checks_90d: int = 0
    total_checks_90d: int = 0
    history: list[ModelHealthDailyBucket]


class ModelHealthStatusResponse(BaseModel):
    generated_at: int
    last_run_at: Optional[int] = None
    check_interval_seconds: int
    history_window_days: int
    models: list[ModelHealthStatusItem]


def resolve_daily_status(successful_checks: int, total_checks: int) -> tuple[str, Optional[float]]:
    if total_checks == 0:
        return "unknown", None

    uptime_ratio = successful_checks / total_checks
    if successful_checks == total_checks:
        return "healthy", uptime_ratio
    if successful_checks == 0:
        return "outage", uptime_ratio
    return "degraded", uptime_ratio


def get_optional_user(request: Request):
    auth_token = get_http_authorization_cred(request.headers.get("authorization"))
    token = auth_token.credentials if auth_token is not None else None

    if token is None and "token" in request.cookies:
        token = request.cookies.get("token")

    if token is None:
        return None

    try:
        if token.startswith("sk-"):
            return get_current_user_by_api_key(request, token)

        data = decode_token(token)
        if data is None or "id" not in data:
            return None

        user = Users.get_user_by_id(data["id"])
        if user is None:
            return None

        if user.role not in {"user", "admin"}:
            return None

        return user
    except Exception:
        return None


def filter_visible_models(models: list[dict], user) -> list[dict]:
    if user is not None and user.role == "admin":
        return models

    visible_models = []
    for model in models:
        access_grants = model.get("info", {}).get("access_grants", [])
        if has_public_read_access_grant(access_grants):
            visible_models.append(model)

    return visible_models


def _extract_tag_names(raw_tags) -> list[str]:
    names: list[str] = []
    for tag in raw_tags or []:
        if isinstance(tag, dict):
            name = str(tag.get("name") or "").strip()
        else:
            name = str(tag or "").strip()

        if name:
            names.append(name)

    return names


def get_provider_label(model: dict) -> Optional[str]:
    tag_names = [
        *_extract_tag_names(model.get("tags")),
        *_extract_tag_names(model.get("info", {}).get("meta", {}).get("tags")),
    ]

    seen = set()
    normalized_tag_names = []
    for tag_name in tag_names:
        lowered = tag_name.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized_tag_names.append(tag_name)

    for tag_name in normalized_tag_names:
        lowered = tag_name.lower()
        if lowered.startswith("provider:"):
            return tag_name.split(":", 1)[1].strip() or model.get("owned_by")

    if normalized_tag_names:
        return normalized_tag_names[0]

    return model.get("owned_by")


@router.get(
    "",
    response_model=ModelHealthStatusResponse,
)
async def get_model_health_status(request: Request):
    now = datetime.now(timezone.utc)
    window_start = int((now - timedelta(days=MODEL_HEALTH_HISTORY_DAYS - 1)).timestamp())

    user = get_optional_user(request)
    models = filter_visible_models(
        await get_enabled_models_for_health(request.app, refresh=False),
        user,
    )
    checks = ModelHealthChecks.get_checks_since(window_start)

    checks_by_model: dict[str, list[ModelHealthCheckModel]] = defaultdict(list)
    for check in checks:
        checks_by_model[check.model_id].append(check)

    day_labels = [
        (now.date() - timedelta(days=offset)).isoformat()
        for offset in reversed(range(MODEL_HEALTH_HISTORY_DAYS))
    ]

    status_items: list[ModelHealthStatusItem] = []
    for model in models:
        model_checks = checks_by_model.get(model["id"], [])
        latest_check = model_checks[-1] if model_checks else None

        daily_success_counts: dict[str, int] = defaultdict(int)
        daily_total_counts: dict[str, int] = defaultdict(int)
        successful_checks_90d = 0

        for check in model_checks:
            day_key = datetime.fromtimestamp(check.checked_at, tz=timezone.utc).date().isoformat()
            daily_total_counts[day_key] += 1
            if check.status:
                daily_success_counts[day_key] += 1
                successful_checks_90d += 1

        history = []
        for day_key in day_labels:
            successful_checks = daily_success_counts.get(day_key, 0)
            total_checks = daily_total_counts.get(day_key, 0)
            status, uptime_ratio = resolve_daily_status(successful_checks, total_checks)
            history.append(
                ModelHealthDailyBucket(
                    date=day_key,
                    status=status,
                    uptime_ratio=uptime_ratio,
                    successful_checks=successful_checks,
                    total_checks=total_checks,
                )
            )

        total_checks_90d = len(model_checks)
        uptime_ratio_90d = (
            successful_checks_90d / total_checks_90d if total_checks_90d > 0 else None
        )

        status_items.append(
            ModelHealthStatusItem(
                id=model["id"],
                name=str(model.get("name") or model["id"]),
                provider=get_provider_label(model),
                latest=(
                    ModelHealthLatestStatus(
                        checked_at=latest_check.checked_at,
                        status=latest_check.status,
                        latency_ms=latest_check.latency_ms,
                        error=latest_check.error,
                    )
                    if latest_check
                    else None
                ),
                uptime_ratio_90d=uptime_ratio_90d,
                successful_checks_90d=successful_checks_90d,
                total_checks_90d=total_checks_90d,
                history=history,
            )
        )

    status_items.sort(
        key=lambda item: (
            item.latest.status if item.latest else False,
            item.name.lower(),
        )
    )

    return ModelHealthStatusResponse(
        generated_at=int(now.timestamp()),
        last_run_at=getattr(request.app.state, "model_health_last_run_at", None),
        check_interval_seconds=MODEL_HEALTH_CHECK_INTERVAL_SECONDS,
        history_window_days=MODEL_HEALTH_HISTORY_DAYS,
        models=status_items,
    )
