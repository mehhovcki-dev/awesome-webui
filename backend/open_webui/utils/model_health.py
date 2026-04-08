import asyncio
import logging
import time
from typing import Optional

from fastapi import Request
from starlette.datastructures import Headers

from open_webui.models.model_health import (
    ModelHealthCheckForm,
    ModelHealthChecks,
)
from open_webui.models.users import UserModel, Users
from open_webui.utils.chat import generate_chat_completion
from open_webui.utils.models import get_all_models

log = logging.getLogger(__name__)

MODEL_HEALTH_CHECK_INTERVAL_SECONDS = 60 * 60
MODEL_HEALTH_HISTORY_DAYS = 90
MODEL_HEALTH_RETENTION_SECONDS = MODEL_HEALTH_HISTORY_DAYS * 24 * 60 * 60
MODEL_HEALTH_CHECK_TIMEOUT_SECONDS = 45
MODEL_HEALTH_CHECK_CONCURRENCY = 4
MODEL_HEALTH_PROMPT = "Reply with OK only."


def build_internal_request(app) -> Request:
    return Request(
        {
            "type": "http",
            "asgi.version": "3.0",
            "asgi.spec_version": "2.0",
            "method": "GET",
            "path": "/internal/model-health",
            "query_string": b"",
            "headers": Headers({}).raw,
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 80),
            "scheme": "http",
            "app": app,
        }
    )


def get_model_health_user() -> Optional[UserModel]:
    user = Users.get_first_user()
    if user is None:
        return None

    return user.model_copy(update={"role": "admin"})


def is_model_health_candidate(model: dict) -> bool:
    if not model:
        return False

    if model.get("owned_by") == "arena":
        return False

    if model.get("pipeline", {}).get("type") == "filter":
        return False

    return bool(model.get("id"))


async def get_enabled_models_for_health(app, refresh: bool = False) -> list[dict]:
    request = build_internal_request(app)
    user = get_model_health_user()
    models = await get_all_models(request, refresh=refresh, user=user)

    candidates = [model for model in models if is_model_health_candidate(model)]
    candidates.sort(key=lambda model: (str(model.get("name") or model.get("id")).lower(), model.get("id")))
    return candidates


async def run_single_model_health_check(
    app, user: UserModel, model: dict
) -> ModelHealthCheckForm:
    request = build_internal_request(app)

    started_at = time.perf_counter()

    try:
        await asyncio.wait_for(
            generate_chat_completion(
                request,
                form_data={
                    "model": model["id"],
                    "messages": [{"role": "user", "content": MODEL_HEALTH_PROMPT}],
                    "max_tokens": 8,
                    "temperature": 0,
                    "stream": False,
                },
                user=user,
                bypass_filter=True,
                bypass_system_prompt=True,
            ),
            timeout=MODEL_HEALTH_CHECK_TIMEOUT_SECONDS,
        )

        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return ModelHealthCheckForm(
            model_id=model["id"],
            model_name=str(model.get("name") or model["id"]),
            owned_by=model.get("owned_by"),
            status=True,
            latency_ms=latency_ms,
            error=None,
            checked_at=int(time.time()),
        )
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        error_message = str(exc).strip() or exc.__class__.__name__
        log.warning("Model health check failed for %s: %s", model.get("id"), error_message)

        return ModelHealthCheckForm(
            model_id=model["id"],
            model_name=str(model.get("name") or model["id"]),
            owned_by=model.get("owned_by"),
            status=False,
            latency_ms=latency_ms,
            error=error_message[:1000],
            checked_at=int(time.time()),
        )


async def run_model_health_checks(app, refresh_models: bool = True) -> list[ModelHealthCheckForm]:
    models = await get_enabled_models_for_health(app, refresh=refresh_models)
    user = get_model_health_user()

    if not models or user is None:
        app.state.model_health_last_run_at = None
        return []

    semaphore = asyncio.Semaphore(MODEL_HEALTH_CHECK_CONCURRENCY)

    async def worker(model: dict) -> ModelHealthCheckForm:
        async with semaphore:
            return await run_single_model_health_check(app, user, model)

    checks = await asyncio.gather(*(worker(model) for model in models))

    ModelHealthChecks.insert_checks(checks)
    ModelHealthChecks.delete_checks_before(
        int(time.time()) - MODEL_HEALTH_RETENTION_SECONDS
    )

    latest_run_at = max((check.checked_at or 0) for check in checks) if checks else None
    app.state.model_health_last_run_at = latest_run_at

    return checks


async def maybe_run_model_health_checks(
    app, refresh_models: bool = True
) -> list[ModelHealthCheckForm]:
    latest_check_at = ModelHealthChecks.get_latest_check_at()
    now = int(time.time())

    if latest_check_at and (now - latest_check_at) < (MODEL_HEALTH_CHECK_INTERVAL_SECONDS - 60):
        app.state.model_health_last_run_at = latest_check_at
        return []

    return await run_model_health_checks(app, refresh_models=refresh_models)


async def model_health_monitor(app):
    try:
        await maybe_run_model_health_checks(app, refresh_models=True)

        while True:
            await asyncio.sleep(MODEL_HEALTH_CHECK_INTERVAL_SECONDS)
            await maybe_run_model_health_checks(app, refresh_models=True)
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("Model health monitor crashed")
        raise
