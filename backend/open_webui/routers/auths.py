from __future__ import annotations

import asyncio
import datetime
import logging
import re
import time
import urllib
import uuid
from ssl import CERT_NONE, CERT_REQUIRED, PROTOCOL_TLS
from typing import List, Optional

from aiohttp import ClientSession
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse, Response
from ldap3 import NONE, Connection, Server, Tls
from ldap3.utils.conv import escape_filter_chars
from open_webui import config as config_module
from open_webui.config import (
    ENABLE_LDAP,
    ENABLE_OAUTH_SIGNUP,
    ENABLE_PASSWORD_AUTH,
    load_oauth_providers,
    OAUTH_MERGE_ACCOUNTS_BY_EMAIL,
    OAUTH_PROVIDERS,
    OPENID_END_SESSION_ENDPOINT,
    OPENID_PROVIDER_URL,
)
from open_webui.constants import ERROR_MESSAGES, WEBHOOK_MESSAGES
from open_webui.env import (
    AIOHTTP_CLIENT_SESSION_SSL,
    ENABLE_INITIAL_ADMIN_SIGNUP,
    ENABLE_OAUTH_TOKEN_EXCHANGE,
    WEBUI_AUTH,
    WEBUI_AUTH_COOKIE_SAME_SITE,
    WEBUI_AUTH_COOKIE_SECURE,
    WEBUI_AUTH_SIGNOUT_REDIRECT_URL,
    WEBUI_AUTH_TRUSTED_EMAIL_HEADER,
    WEBUI_AUTH_TRUSTED_GROUPS_HEADER,
    WEBUI_AUTH_TRUSTED_NAME_HEADER,
    WEBUI_AUTH_TRUSTED_ROLE_HEADER,
)
from open_webui.internal.db import get_async_session
from open_webui.models.auths import (
    AddUserForm,
    ApiKey,
    Auths,
    LdapForm,
    SigninForm,
    SigninResponse,
    SignupForm,
    Token,
    UpdatePasswordForm,
)
from open_webui.models.groups import Groups
from open_webui.models.moderation import UserModerationBans, get_moderation_ban_payload
from open_webui.models.oauth_sessions import OAuthSessions
from open_webui.models.users import (
    UpdateProfileForm,
    UserModel,
    UserProfileImageResponse,
    Users,
    UserStatus,
)
from open_webui.utils.access_control import get_permissions, has_permission
from open_webui.utils.auth import (
    create_api_key,
    create_token,
    decode_token,
    get_admin_user,
    get_current_user,
    get_http_authorization_cred,
    get_password_hash,
    get_verified_user,
    invalidate_token,
    validate_password,
    verify_password,
)
from open_webui.utils.groups import apply_default_group_assignment
from open_webui.utils.invites import (
    consume_invite_code,
    create_invite_code,
    get_clean_invite_codes,
    get_invite_policy,
    get_invite_codes_for_user,
)
from open_webui.utils.misc import parse_duration, validate_email_format
from open_webui.utils.oauth import OAuthManager, auth_manager_config
from open_webui.utils.rate_limit import RateLimiter
from open_webui.utils.redis import get_redis_client
from open_webui.utils.webhook import post_webhook
from pydantic import BaseModel, ConfigDict
from open_webui.internal.config import ConfigVar
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

log = logging.getLogger(__name__)

# Forgive us our failed attempts, as we forgive those
# who exceed their allotted rate against this gate.
signin_rate_limiter = RateLimiter(redis_client=get_redis_client(), limit=5 * 3, window=60 * 3)


ADMIN_CONFIG_KEYS = [
    'SHOW_ADMIN_DETAILS',
    'ADMIN_EMAIL',
    'WEBUI_URL',
    'ENABLE_SIGNUP',
    'ENABLE_PASSWORD_SIGNUP',
    'ENABLE_OAUTH_LOGIN',
    'ENABLE_OAUTH_SIGNUP',
    'OAUTH_ALLOWED_LOGIN_PROVIDERS',
    'OAUTH_ALLOWED_SIGNUP_PROVIDERS',
    'OAUTH_MERGE_ACCOUNTS_BY_EMAIL',
    'OAUTH_TIMEOUT',
    'OAUTH_AUDIENCE',
    'GOOGLE_OAUTH_ENABLED',
    'GOOGLE_CLIENT_ID',
    'GOOGLE_CLIENT_SECRET',
    'GOOGLE_OAUTH_SCOPE',
    'GOOGLE_SERVER_METADATA_URL',
    'GOOGLE_REDIRECT_URI',
    'MICROSOFT_OAUTH_ENABLED',
    'MICROSOFT_CLIENT_ID',
    'MICROSOFT_CLIENT_SECRET',
    'MICROSOFT_CLIENT_TENANT_ID',
    'MICROSOFT_CLIENT_LOGIN_BASE_URL',
    'MICROSOFT_CLIENT_PICTURE_URL',
    'MICROSOFT_OAUTH_SCOPE',
    'MICROSOFT_REDIRECT_URI',
    'GITHUB_OAUTH_ENABLED',
    'GITHUB_CLIENT_ID',
    'GITHUB_CLIENT_SECRET',
    'GITHUB_CLIENT_SCOPE',
    'GITHUB_CLIENT_REDIRECT_URI',
    'GITHUB_ACCESS_TOKEN_URL',
    'GITHUB_AUTHORIZE_URL',
    'GITHUB_API_BASE_URL',
    'GITHUB_USERINFO_ENDPOINT',
    'OIDC_OAUTH_ENABLED',
    'OAUTH_PROVIDER_NAME',
    'OAUTH_CLIENT_ID',
    'OAUTH_CLIENT_SECRET',
    'OPENID_PROVIDER_URL',
    'OPENID_REDIRECT_URI',
    'OAUTH_SCOPES',
    'OAUTH_TOKEN_ENDPOINT_AUTH_METHOD',
    'OAUTH_CODE_CHALLENGE_METHOD',
    'OAUTH_SUB_CLAIM',
    'OAUTH_USERNAME_CLAIM',
    'OAUTH_EMAIL_CLAIM',
    'OAUTH_PICTURE_CLAIM',
    'OAUTH_GROUPS_CLAIM',
    'FEISHU_OAUTH_ENABLED',
    'FEISHU_CLIENT_ID',
    'FEISHU_CLIENT_SECRET',
    'FEISHU_OAUTH_SCOPE',
    'FEISHU_REDIRECT_URI',
    'FEISHU_ACCESS_TOKEN_URL',
    'FEISHU_AUTHORIZE_URL',
    'FEISHU_API_BASE_URL',
    'FEISHU_USERINFO_ENDPOINT',
    'DISCORD_OAUTH_ENABLED',
    'DISCORD_CLIENT_ID',
    'DISCORD_CLIENT_SECRET',
    'DISCORD_OAUTH_SCOPE',
    'DISCORD_REDIRECT_URI',
    'DISCORD_ACCESS_TOKEN_URL',
    'DISCORD_AUTHORIZE_URL',
    'DISCORD_API_BASE_URL',
    'DISCORD_USERINFO_ENDPOINT',
    'GITLAB_OAUTH_ENABLED',
    'GITLAB_CLIENT_ID',
    'GITLAB_CLIENT_SECRET',
    'GITLAB_OAUTH_SCOPE',
    'GITLAB_REDIRECT_URI',
    'GITLAB_ACCESS_TOKEN_URL',
    'GITLAB_AUTHORIZE_URL',
    'GITLAB_API_BASE_URL',
    'GITLAB_USERINFO_ENDPOINT',
    'SLACK_OAUTH_ENABLED',
    'SLACK_CLIENT_ID',
    'SLACK_CLIENT_SECRET',
    'SLACK_OAUTH_SCOPE',
    'SLACK_REDIRECT_URI',
    'SLACK_ACCESS_TOKEN_URL',
    'SLACK_AUTHORIZE_URL',
    'SLACK_API_BASE_URL',
    'SLACK_USERINFO_ENDPOINT',
    'ENABLE_INVITE_ONLY_AUTH',
    'INVITE_CREATOR_SCOPE',
    'INVITE_CREATOR_GROUP_IDS',
    'INVITE_CREATOR_COOLDOWN_SECONDS',
    'INVITE_CODE_LENGTH',
    'INVITE_CODE_TTL_SECONDS',
    'INVITE_CODE_PREFIX',
    'INVITE_CODE_REUSABLE',
    'INVITE_CODE_MAX_USES',
    'ENABLE_API_KEYS',
    'ENABLE_API_KEYS_ENDPOINT_RESTRICTIONS',
    'API_KEYS_ALLOWED_ENDPOINTS',
    'DEFAULT_USER_ROLE',
    'DEFAULT_GROUP_ID',
    'JWT_EXPIRES_IN',
    'ENABLE_COMMUNITY_SHARING',
    'ENABLE_MESSAGE_RATING',
    'ENABLE_FOLDERS',
    'FOLDER_MAX_FILE_COUNT',
    'AUTOMATION_MAX_COUNT',
    'AUTOMATION_MIN_INTERVAL',
    'ENABLE_AUTOMATIONS',
    'ENABLE_CHANNELS',
    'ENABLE_CALENDAR',
    'ENABLE_MEMORIES',
    'ENABLE_NOTES',
    'ENABLE_USER_WEBHOOKS',
    'ENABLE_USER_STATUS',
    'ENABLE_SYSTEM_NOTICE',
    'SYSTEM_NOTICE_TITLE',
    'SYSTEM_NOTICE_CONTENT',
    'WEBSITE_BRAND_NAME',
    'ENABLE_MOTD',
    'MOTD_TITLE',
    'MOTD_CONTENT',
    'NOTIFICATION_SOUND_LIBRARY',
    'CUSTOM_EMOJI_LIBRARY',
    'PENDING_USER_OVERLAY_TITLE',
    'PENDING_USER_OVERLAY_CONTENT',
    'RESPONSE_WATERMARK',
]


def _sanitize_text(value, max_length: int | None = None) -> str:
    text = str(value or '').strip()
    return text[:max_length] if max_length is not None else text


def _sanitize_oauth_provider_list(provider_list):
    if provider_list is None:
        return None
    if not isinstance(provider_list, list):
        return []

    configured_providers = set(OAUTH_PROVIDERS.keys())
    sanitized = []
    for provider in provider_list:
        normalized = str(provider).strip().lower()
        if normalized and normalized in configured_providers and normalized not in sanitized:
            sanitized.append(normalized)
    return sanitized


def _sanitize_notification_sound_library(raw_sounds) -> list[dict]:
    if not isinstance(raw_sounds, list):
        return []

    sanitized: list[dict] = []
    for item in raw_sounds[:100]:
        if not isinstance(item, dict):
            continue
        sound_id = _sanitize_text(item.get('id'), 128)
        data_url = _sanitize_text(item.get('data_url'), 6_000_000)
        sound_type = _sanitize_text(item.get('type'), 32).lower()
        if not sound_id or sound_type not in {'channel', 'chat_completion'} or not data_url.startswith('data:audio/'):
            continue
        sanitized.append(
            {
                'id': sound_id,
                'name': _sanitize_text(item.get('name'), 128) or 'Notification sound',
                'type': sound_type,
                'data_url': data_url,
            }
        )
    return sanitized


def _sanitize_custom_emoji_library(raw_emojis) -> list[dict]:
    if not isinstance(raw_emojis, list):
        return []

    sanitized: list[dict] = []
    seen_names: set[str] = set()
    for item in raw_emojis[:500]:
        if not isinstance(item, dict):
            continue
        emoji_id = _sanitize_text(item.get('id'), 128)
        emoji_name = re.sub(r'[^a-z0-9_]', '', _sanitize_text(item.get('name'), 64).lower())[:32]
        data_url = _sanitize_text(item.get('data_url'), 6_000_000)
        if (
            not emoji_id
            or len(emoji_name) < 2
            or emoji_name in seen_names
            or not re.match(r'^data:image/(?:png|jpe?g|webp|gif|avif|svg\+xml);base64,', data_url, flags=re.I)
        ):
            continue
        created_at = item.get('created_at')
        sanitized.append(
            {
                'id': emoji_id,
                'name': emoji_name,
                'data_url': data_url,
                'created_by': _sanitize_text(item.get('created_by'), 128) or None,
                'created_by_name': _sanitize_text(item.get('created_by_name'), 128) or None,
                'created_at': int(created_at) if isinstance(created_at, (int, float)) else int(time.time()),
            }
        )
        seen_names.add(emoji_name)
    return sanitized


async def _serialize_admin_config(request: Request, include_meta: bool = True, db: AsyncSession | None = None) -> dict:
    data = {key: _get_config_value(request, key) for key in ADMIN_CONFIG_KEYS}
    if include_meta:
        data['_meta'] = {
            'user_count': await Users.get_num_users(db=db),
            'active_30_day_user_count': await Users.get_num_users_active_since(30, db=db),
        }
    return data


def _ensure_config_key(request: Request, key: str, default=None) -> bool:
    entries = getattr(request.app.state.config, '_entries', {})
    if key in entries:
        return True

    source = getattr(config_module, key, None)
    if isinstance(source, ConfigVar):
        entries[key] = source
        return True

    entries[key] = ConfigVar(key, f'awesome.{key.lower()}', default)
    return True


def _config_value_for_runtime(request: Request, key: str, default=None):
    value = _get_config_value(request, key, default)
    return value.value if isinstance(value, ConfigVar) else value


def _get_config_value(request: Request, key: str, default=None):
    if not _ensure_config_key(request, key, default):
        return default
    return getattr(request.app.state.config, key, default)


def _ensure_invite_config_keys(request: Request) -> None:
    for key, default in {
        'INVITE_CODES': [],
        'INVITE_CREATOR_SCOPE': 'admin',
        'INVITE_CREATOR_GROUP_IDS': [],
        'INVITE_CREATOR_COOLDOWN_SECONDS': 3600,
        'INVITE_CODE_LENGTH': 8,
        'INVITE_CODE_TTL_SECONDS': 604800,
        'INVITE_CODE_PREFIX': '',
        'INVITE_CODE_REUSABLE': False,
        'INVITE_CODE_MAX_USES': 1,
    }.items():
        _ensure_config_key(request, key, default)


def _sanitize_non_negative_int(value, default: int = 0, minimum: int = 0, maximum: int | None = None) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    parsed = max(minimum, parsed)
    return min(parsed, maximum) if maximum is not None else parsed


def _sanitize_optional_count(value):
    if value in (None, ''):
        return ''
    return _sanitize_non_negative_int(value, minimum=0)


def _sanitize_admin_config_value(key: str, value):
    if key in {'OAUTH_ALLOWED_LOGIN_PROVIDERS', 'OAUTH_ALLOWED_SIGNUP_PROVIDERS'}:
        return _sanitize_oauth_provider_list(value)

    if key == 'NOTIFICATION_SOUND_LIBRARY':
        return _sanitize_notification_sound_library(value)

    if key == 'CUSTOM_EMOJI_LIBRARY':
        return _sanitize_custom_emoji_library(value)

    if key == 'WEBSITE_BRAND_NAME':
        return _sanitize_text(value, 80) or 'Awesome WebUI'

    if key in {'FOLDER_MAX_FILE_COUNT', 'AUTOMATION_MAX_COUNT', 'AUTOMATION_MIN_INTERVAL'}:
        return _sanitize_optional_count(value)

    if key == 'DEFAULT_USER_ROLE':
        return value if value in {'pending', 'user', 'admin'} else None

    if key == 'JWT_EXPIRES_IN':
        return value if re.match(r'^(-1|0|(-?\d+(\.\d+)?)(ms|s|m|h|d|w))$', str(value or '')) else None

    if key == 'INVITE_CREATOR_SCOPE':
        return value if value in {'admin', 'groups', 'all'} else 'admin'

    if key == 'INVITE_CREATOR_GROUP_IDS':
        return [str(group_id) for group_id in (value or []) if str(group_id).strip()] if isinstance(value, list) else []

    if key == 'INVITE_CREATOR_COOLDOWN_SECONDS':
        return _sanitize_non_negative_int(value, default=3600)

    if key == 'INVITE_CODE_LENGTH':
        return _sanitize_non_negative_int(value, default=8, minimum=4, maximum=32)

    if key == 'INVITE_CODE_TTL_SECONDS':
        return _sanitize_non_negative_int(value, default=604800)

    if key == 'INVITE_CODE_PREFIX':
        return re.sub(r'[^A-Za-z0-9_-]', '', str(value or '').strip())[:24]

    if key == 'INVITE_CODE_MAX_USES':
        return _sanitize_non_negative_int(value, default=1)

    if key in {
        'SYSTEM_NOTICE_TITLE',
        'MOTD_TITLE',
        'PENDING_USER_OVERLAY_TITLE',
    }:
        return _sanitize_text(value, 160)

    if key in {
        'SYSTEM_NOTICE_CONTENT',
        'MOTD_CONTENT',
        'PENDING_USER_OVERLAY_CONTENT',
    }:
        return _sanitize_text(value, 10000)

    if key == 'RESPONSE_WATERMARK':
        return _sanitize_text(value, 512)

    return value


def _reload_oauth_runtime(request: Request):
    for key in [
        'DEFAULT_USER_ROLE',
        'ENABLE_OAUTH_SIGNUP',
        'OAUTH_MERGE_ACCOUNTS_BY_EMAIL',
        'ENABLE_OAUTH_ROLE_MANAGEMENT',
        'ENABLE_OAUTH_GROUP_MANAGEMENT',
        'ENABLE_OAUTH_GROUP_CREATION',
        'OAUTH_GROUP_DEFAULT_SHARE',
        'OAUTH_BLOCKED_GROUPS',
        'OAUTH_ROLES_CLAIM',
        'OAUTH_SUB_CLAIM',
        'OAUTH_GROUPS_CLAIM',
        'OAUTH_EMAIL_CLAIM',
        'OAUTH_PICTURE_CLAIM',
        'OAUTH_USERNAME_CLAIM',
        'OAUTH_ALLOWED_ROLES',
        'OAUTH_ADMIN_ROLES',
        'OAUTH_ALLOWED_DOMAINS',
        'WEBHOOK_URL',
        'JWT_EXPIRES_IN',
        'OAUTH_UPDATE_PICTURE_ON_LOGIN',
        'OAUTH_UPDATE_NAME_ON_LOGIN',
        'OAUTH_UPDATE_EMAIL_ON_LOGIN',
        'OAUTH_AUDIENCE',
    ]:
        source = getattr(config_module, key, None)
        default = source.value if isinstance(source, ConfigVar) else source
        setattr(auth_manager_config, key, _config_value_for_runtime(request, key, default))

    load_oauth_providers()
    request.app.state.oauth_manager = OAuthManager(request.app)


async def _emit_public_config_update(request: Request):
    try:
        from open_webui.socket.main import SESSION_POOL, emit_to_users

        user_ids = list({entry.get('id') for entry in SESSION_POOL.values() if entry and entry.get('id')})
        if not user_ids:
            return

        await emit_to_users(
            'events',
            {
                'chat_id': None,
                'message_id': None,
                'data': {
                    'type': 'config:update',
                    'data': {
                        'name': _get_config_value(
                            request,
                            'WEBSITE_BRAND_NAME',
                            getattr(request.app.state, 'WEBUI_NAME', 'Awesome WebUI'),
                        ),
	                        'website': {
	                            'brand_name': _get_config_value(
	                                request,
	                                'WEBSITE_BRAND_NAME',
	                                getattr(request.app.state, 'WEBUI_NAME', 'Awesome WebUI'),
	                            ),
	                            'powered_by': 'Open WebUI',
	                        },
                        'features': {
                            'enable_signup': _get_config_value(request, 'ENABLE_SIGNUP', True),
                            'enable_password_signup': _get_config_value(request, 'ENABLE_PASSWORD_SIGNUP', True),
                            'enable_oauth_login': _get_config_value(request, 'ENABLE_OAUTH_LOGIN', True),
                            'enable_oauth_signup': _get_config_value(request, 'ENABLE_OAUTH_SIGNUP', False),
                            'enable_invite_only_auth': _get_config_value(request, 'ENABLE_INVITE_ONLY_AUTH', False),
                        },
                        'oauth': {
                            'allowed_login_providers': _get_config_value(request, 'OAUTH_ALLOWED_LOGIN_PROVIDERS', []),
                            'allowed_signup_providers': _get_config_value(request, 'OAUTH_ALLOWED_SIGNUP_PROVIDERS', []),
                        },
                        'ui': {
                            'system_notice': {
                                'enabled': _get_config_value(request, 'ENABLE_SYSTEM_NOTICE', False),
                                'title': _get_config_value(request, 'SYSTEM_NOTICE_TITLE', ''),
                                'content': _get_config_value(request, 'SYSTEM_NOTICE_CONTENT', ''),
                            },
                            'motd': {
                                'enabled': _get_config_value(request, 'ENABLE_MOTD', False),
                                'title': _get_config_value(request, 'MOTD_TITLE', ''),
                                'content': _get_config_value(request, 'MOTD_CONTENT', ''),
	                            },
	                            'notification_sounds': _get_config_value(request, 'NOTIFICATION_SOUND_LIBRARY', []),
	                            'custom_emojis': _get_config_value(request, 'CUSTOM_EMOJI_LIBRARY', []),
	                            'pending_user_overlay_title': _get_config_value(request, 'PENDING_USER_OVERLAY_TITLE', ''),
	                            'pending_user_overlay_content': _get_config_value(request, 'PENDING_USER_OVERLAY_CONTENT', ''),
	                            'response_watermark': _get_config_value(request, 'RESPONSE_WATERMARK', ''),
	                        },
                    },
                },
            },
            user_ids,
        )
    except Exception as e:
        log.debug(f'Failed to emit realtime config update: {e}')


async def create_session_response(
    request: Request, user, db, response: Response = None, set_cookie: bool = False
) -> dict:
    """
    Create JWT token and build session response for a user.
    Shared helper for signin, signup, ldap_auth, add_user, and token_exchange endpoints.

    Args:
        request: FastAPI request object
        user: User object
        db: Database session
        response: FastAPI response object (required if set_cookie is True)
        set_cookie: Whether to set the auth cookie on the response
    """
    if user.role != 'admin':
        site_ban = await UserModerationBans.get_active_site_ban(user.id, db=db)
        if site_ban:
            if response:
                response.delete_cookie('token')
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    'code': 'moderation_site_ban',
                    'ban': get_moderation_ban_payload(site_ban),
                },
            )

    expires_delta = parse_duration(request.app.state.config.JWT_EXPIRES_IN)
    expires_at = None
    if expires_delta:
        expires_at = int(time.time()) + int(expires_delta.total_seconds())

    token = create_token(
        data={'id': user.id},
        expires_delta=expires_delta,
    )

    if set_cookie and response:
        datetime_expires_at = datetime.datetime.fromtimestamp(expires_at, datetime.timezone.utc) if expires_at else None
        max_age = int(expires_delta.total_seconds()) if expires_delta else None
        response.set_cookie(
            key='token',
            value=token,
            expires=datetime_expires_at,
            httponly=True,
            samesite=WEBUI_AUTH_COOKIE_SAME_SITE,
            secure=WEBUI_AUTH_COOKIE_SECURE,
            **({'max_age': max_age} if max_age is not None else {}),
        )

    user_permissions = await get_permissions(user.id, request.app.state.config.USER_PERMISSIONS, db=db)
    auth = await Auths.get_auth_by_id(user.id, db=db)

    return {
        'token': token,
        'token_type': 'Bearer',
        'expires_at': expires_at,
        'id': user.id,
        'email': user.email,
        'name': user.name,
        'role': user.role,
        'profile_image_url': f'/api/v1/users/{user.id}/profile/image',
        'permissions': user_permissions,
        'presence_state': Users.normalize_presence_state(user.presence_state),
        'status_emoji': user.status_emoji,
        'status_message': user.status_message,
        'status_expires_at': user.status_expires_at,
        'has_password': bool(auth and auth.password),
        'password_change_required': bool(auth and auth.password_change_required),
    }


############################
# GetSessionUser
############################


class SessionUserResponse(Token, UserProfileImageResponse):
    expires_at: int | None = None
    permissions: dict | None = None
    presence_state: str | None = None
    status_emoji: str | None = None
    status_message: str | None = None
    status_expires_at: int | None = None
    has_password: bool = True
    password_change_required: bool = False


class SessionUserInfoResponse(SessionUserResponse, UserStatus):
    bio: str | None = None
    gender: str | None = None
    date_of_birth: datetime.date | None = None


@router.get('/', response_model=SessionUserInfoResponse)
async def get_session_user(
    request: Request,
    response: Response,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    token = None
    auth_header = request.headers.get('Authorization')
    if auth_header:
        auth_token = get_http_authorization_cred(auth_header)
        if auth_token is not None:
            token = auth_token.credentials
    if token is None:
        token = request.cookies.get('token')
    if token is None and getattr(request.state, 'token', None):
        token = request.state.token.credentials
    data = decode_token(token) if token else None

    expires_at = None

    if data:
        expires_at = data.get('exp')

        if (expires_at is not None) and int(time.time()) > expires_at:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ERROR_MESSAGES.INVALID_TOKEN,
            )

        # Set the cookie token
        max_age = int(expires_at - time.time()) if expires_at else None
        response.set_cookie(
            key='token',
            value=token,
            expires=(datetime.datetime.fromtimestamp(expires_at, datetime.timezone.utc) if expires_at else None),
            httponly=True,  # Ensures the cookie is not accessible via JavaScript
            samesite=WEBUI_AUTH_COOKIE_SAME_SITE,
            secure=WEBUI_AUTH_COOKIE_SECURE,
            **({'max_age': max_age} if max_age is not None else {}),
        )

    user_permissions = await get_permissions(user.id, request.app.state.config.USER_PERMISSIONS, db=db)
    auth = await Auths.get_auth_by_id(user.id, db=db)

    response_data = {
        'token': token,
        'token_type': 'Bearer',
        'expires_at': expires_at,
        'id': user.id,
        'email': user.email,
        'name': user.name,
        'role': user.role,
        'profile_image_url': user.profile_image_url,
        'bio': user.bio,
        'gender': user.gender,
        'date_of_birth': user.date_of_birth,
        'presence_state': Users.normalize_presence_state(user.presence_state),
        'status_emoji': user.status_emoji,
        'status_message': user.status_message,
        'status_expires_at': user.status_expires_at,
        'has_password': bool(auth and auth.password),
        'password_change_required': bool(auth and auth.password_change_required),
        'permissions': user_permissions,
    }

    return response_data


############################
# Update Profile
############################


@router.post('/update/profile', response_model=UserProfileImageResponse)
async def update_profile(
    form_data: UpdateProfileForm,
    session_user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    if session_user:
        user = await Users.update_user_by_id(
            session_user.id,
            form_data.model_dump(),
            db=db,
        )
        if user:
            return user
        else:
            raise HTTPException(400, detail=ERROR_MESSAGES.DEFAULT())
    else:
        raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)


############################
# Update Timezone
############################


class UpdateTimezoneForm(BaseModel):
    timezone: str


@router.post('/update/timezone')
async def update_timezone(
    form_data: UpdateTimezoneForm,
    session_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    if session_user:
        await Users.update_user_by_id(
            session_user.id,
            {'timezone': form_data.timezone},
            db=db,
        )
        return {'status': True}
    else:
        raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)


############################
# Update Password
############################


@router.post('/update/password', response_model=bool)
async def update_password(
    form_data: UpdatePasswordForm,
    session_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    # Trusted-header auth mode delegates passwords to the reverse proxy
    if WEBUI_AUTH_TRUSTED_EMAIL_HEADER:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.ACTION_PROHIBITED)
    if not session_user:
        raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)

    auth = await Auths.get_auth_by_id(session_user.id, db=db)
    if not auth:
        raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)

    # Awesome WebUI: SSO users with no password and forced-reset accounts set an
    # initial password without proving a current one; everyone else must verify.
    requires_current_password = bool(auth.password) and not auth.password_change_required

    if requires_current_password:
        user = await Auths.authenticate_user(
            session_user.email,
            lambda pw: verify_password(form_data.password or '', pw),
            db=db,
        )
        if not user:
            raise HTTPException(400, detail=ERROR_MESSAGES.INCORRECT_PASSWORD)

    try:
        validate_password(form_data.new_password)
    except Exception as e:
        raise HTTPException(400, detail=str(e))

    hashed = get_password_hash(form_data.new_password)
    return await Auths.update_user_password_by_id(session_user.id, hashed, db=db)


############################
# LDAP Authentication
############################
@router.post('/ldap', response_model=SessionUserResponse)
async def ldap_auth(
    request: Request,
    response: Response,
    form_data: LdapForm,
    db: AsyncSession = Depends(get_async_session),
):
    # Security checks FIRST - before loading any config
    if not request.app.state.config.ENABLE_LDAP:
        raise HTTPException(400, detail='LDAP authentication is not enabled')

    if not ENABLE_PASSWORD_AUTH:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.ACTION_PROHIBITED,
        )

    # Reject empty passwords before attempting the LDAP bind.
    # Per RFC 4513 §5.1.2, a Simple Bind with a non-empty DN but empty
    # password is "unauthenticated simple authentication" — many LDAP
    # servers (OpenLDAP default, some AD configs) return success for these,
    # which would grant access without valid credentials.
    if not form_data.password or not form_data.password.strip():
        raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)

    # NOW load LDAP config variables
    LDAP_SERVER_LABEL = request.app.state.config.LDAP_SERVER_LABEL
    LDAP_SERVER_HOST = request.app.state.config.LDAP_SERVER_HOST
    LDAP_SERVER_PORT = request.app.state.config.LDAP_SERVER_PORT
    LDAP_ATTRIBUTE_FOR_MAIL = request.app.state.config.LDAP_ATTRIBUTE_FOR_MAIL
    LDAP_ATTRIBUTE_FOR_USERNAME = request.app.state.config.LDAP_ATTRIBUTE_FOR_USERNAME
    LDAP_SEARCH_BASE = request.app.state.config.LDAP_SEARCH_BASE
    LDAP_SEARCH_FILTERS = request.app.state.config.LDAP_SEARCH_FILTERS
    LDAP_APP_DN = request.app.state.config.LDAP_APP_DN
    LDAP_APP_PASSWORD = request.app.state.config.LDAP_APP_PASSWORD
    LDAP_USE_TLS = request.app.state.config.LDAP_USE_TLS
    LDAP_CA_CERT_FILE = request.app.state.config.LDAP_CA_CERT_FILE
    LDAP_VALIDATE_CERT = CERT_REQUIRED if request.app.state.config.LDAP_VALIDATE_CERT else CERT_NONE
    LDAP_CIPHERS = request.app.state.config.LDAP_CIPHERS if request.app.state.config.LDAP_CIPHERS else 'ALL'

    try:
        tls = Tls(
            validate=LDAP_VALIDATE_CERT,
            version=PROTOCOL_TLS,
            ca_certs_file=LDAP_CA_CERT_FILE,
            ciphers=LDAP_CIPHERS,
        )
    except Exception as e:
        log.error(f'TLS configuration error: {str(e)}')
        raise HTTPException(400, detail='Failed to configure TLS for LDAP connection.')

    try:
        server = Server(
            host=LDAP_SERVER_HOST,
            port=LDAP_SERVER_PORT,
            get_info=NONE,
            use_ssl=LDAP_USE_TLS,
            tls=tls,
        )
        connection_app = Connection(
            server,
            LDAP_APP_DN,
            LDAP_APP_PASSWORD,
            auto_bind='NONE',
            authentication='SIMPLE' if LDAP_APP_DN else 'ANONYMOUS',
        )
        if not await asyncio.to_thread(connection_app.bind):
            raise HTTPException(400, detail='Application account bind failed')

        ENABLE_LDAP_GROUP_MANAGEMENT = request.app.state.config.ENABLE_LDAP_GROUP_MANAGEMENT
        ENABLE_LDAP_GROUP_CREATION = request.app.state.config.ENABLE_LDAP_GROUP_CREATION
        LDAP_ATTRIBUTE_FOR_GROUPS = request.app.state.config.LDAP_ATTRIBUTE_FOR_GROUPS

        search_attributes = [
            f'{LDAP_ATTRIBUTE_FOR_USERNAME}',
            f'{LDAP_ATTRIBUTE_FOR_MAIL}',
            'cn',
        ]
        if ENABLE_LDAP_GROUP_MANAGEMENT:
            search_attributes.append(f'{LDAP_ATTRIBUTE_FOR_GROUPS}')
            log.info(f'LDAP Group Management enabled. Adding {LDAP_ATTRIBUTE_FOR_GROUPS} to search attributes')
        log.info(f'LDAP search attributes: {search_attributes}')

        search_success = await asyncio.to_thread(
            connection_app.search,
            search_base=LDAP_SEARCH_BASE,
            search_filter=f'(&({LDAP_ATTRIBUTE_FOR_USERNAME}={escape_filter_chars(form_data.user.lower())}){LDAP_SEARCH_FILTERS})',
            attributes=search_attributes,
        )
        if not search_success or not connection_app.entries:
            raise HTTPException(400, detail='User not found in the LDAP server')

        entry = connection_app.entries[0]
        entry_username = entry[f'{LDAP_ATTRIBUTE_FOR_USERNAME}'].value
        email = entry[f'{LDAP_ATTRIBUTE_FOR_MAIL}'].value  # retrieve the Attribute value

        username_list = []  # list of usernames from LDAP attribute
        if isinstance(entry_username, list):
            username_list = [str(name).lower() for name in entry_username]
        else:
            username_list = [str(entry_username).lower()]

        # TODO: support multiple emails if LDAP returns a list
        if not email:
            raise HTTPException(400, 'User does not have a valid email address.')
        elif isinstance(email, str):
            email = email.lower()
        elif isinstance(email, list):
            email = email[0].lower()
        else:
            email = str(email).lower()

        cn = str(entry['cn'])  # common name
        user_dn = entry.entry_dn  # user distinguished name

        user_groups = []
        if ENABLE_LDAP_GROUP_MANAGEMENT and LDAP_ATTRIBUTE_FOR_GROUPS in entry:
            group_dns = entry[LDAP_ATTRIBUTE_FOR_GROUPS]
            log.info(f'LDAP raw group DNs for user {username_list}: {group_dns}')

            if group_dns:
                log.info(f'LDAP group_dns original: {group_dns}')
                log.info(f'LDAP group_dns type: {type(group_dns)}')
                log.info(f'LDAP group_dns length: {len(group_dns)}')

                if hasattr(group_dns, 'value'):
                    group_dns = group_dns.value
                    log.info(f'Extracted .value property: {group_dns}')
                elif hasattr(group_dns, '__iter__') and not isinstance(group_dns, (str, bytes)):
                    group_dns = list(group_dns)
                    log.info(f'Converted to list: {group_dns}')

                if isinstance(group_dns, list):
                    group_dns = [str(item) for item in group_dns]
                else:
                    group_dns = [str(group_dns)]

                log.info(f'LDAP group_dns after processing - type: {type(group_dns)}, length: {len(group_dns)}')

                for group_idx, group_dn in enumerate(group_dns):
                    group_dn = str(group_dn)
                    log.info(f'Processing group DN #{group_idx + 1}: {group_dn}')

                    try:
                        group_cn = None

                        for item in group_dn.split(','):
                            item = item.strip()
                            if item.upper().startswith('CN='):
                                group_cn = item[3:]
                                break

                        if group_cn:
                            user_groups.append(group_cn)

                        else:
                            log.warning(f'Could not extract CN from group DN: {group_dn}')
                    except Exception as e:
                        log.warning(f'Failed to extract group name from DN {group_dn}: {e}')

                log.info(f'LDAP groups for user {username_list}: {user_groups} (total: {len(user_groups)})')
            else:
                log.info(f'No groups found for user {username_list}')
        elif ENABLE_LDAP_GROUP_MANAGEMENT:
            log.warning(
                f'LDAP Group Management enabled but {LDAP_ATTRIBUTE_FOR_GROUPS} attribute not found in user entry'
            )

        if username_list and form_data.user.lower() in username_list:
            connection_user = Connection(
                server,
                user_dn,
                form_data.password,
                auto_bind='NONE',
                authentication='SIMPLE',
            )
            if not await asyncio.to_thread(connection_user.bind):
                raise HTTPException(400, 'Authentication failed.')

            user = await Users.get_user_by_email(email, db=db)
            if not user:
                try:
                    # Insert with default role first to avoid TOCTOU race on
                    # first-user registration.  Matches signup_handler pattern.
                    user = await Auths.insert_new_auth(
                        email=email,
                        password=str(uuid.uuid4()),
                        name=cn,
                        role=request.app.state.config.DEFAULT_USER_ROLE,
                        db=db,
                    )

                    if not user:
                        raise HTTPException(500, detail=ERROR_MESSAGES.CREATE_USER_ERROR)

                    # Atomically check if this is the only user *after* the
                    # insert.  Only the single user present should become admin.
                    if await Users.get_num_users(db=db) == 1:
                        await Users.update_user_role_by_id(user.id, 'admin', db=db)
                        user = await Users.get_user_by_id(user.id, db=db)

                    await apply_default_group_assignment(
                        request.app.state.config.DEFAULT_GROUP_ID,
                        user.id,
                        db=db,
                    )

                    if request.app.state.config.WEBHOOK_URL:
                        await post_webhook(
                            request.app.state.WEBUI_NAME,
                            request.app.state.config.WEBHOOK_URL,
                            WEBHOOK_MESSAGES.USER_SIGNUP(user.name),
                            {
                                'action': 'signup',
                                'message': WEBHOOK_MESSAGES.USER_SIGNUP(user.name),
                                'user': user.model_dump_json(exclude_none=True),
                            },
                        )

                except HTTPException:
                    raise
                except Exception as err:
                    log.error(f'LDAP user creation error: {str(err)}')
                    raise HTTPException(500, detail='Internal error occurred during LDAP user creation.')

            user = await Auths.authenticate_user_by_email(email, db=db)

            if user:
                if ENABLE_LDAP_GROUP_MANAGEMENT and user_groups:
                    if ENABLE_LDAP_GROUP_CREATION:
                        await Groups.create_groups_by_group_names(user.id, user_groups, db=db)
                    try:
                        await Groups.sync_groups_by_group_names(user.id, user_groups, db=db)
                        log.info(f'Successfully synced groups for user {user.id}: {user_groups}')
                    except Exception as e:
                        log.error(f'Failed to sync groups for user {user.id}: {e}')

                return await create_session_response(request, user, db, response, set_cookie=True)
            else:
                raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)
        else:
            raise HTTPException(400, 'User record mismatch.')
    except Exception as e:
        log.error(f'LDAP authentication error: {str(e)}')
        raise HTTPException(400, detail='LDAP authentication failed.')


############################
# SignIn
############################


@router.post('/signin', response_model=SessionUserResponse)
async def signin(
    request: Request,
    response: Response,
    form_data: SigninForm,
    db: AsyncSession = Depends(get_async_session),
):
    if not ENABLE_PASSWORD_AUTH:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.ACTION_PROHIBITED,
        )

    if WEBUI_AUTH_TRUSTED_EMAIL_HEADER:
        if WEBUI_AUTH_TRUSTED_EMAIL_HEADER not in request.headers:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.INVALID_TRUSTED_HEADER)

        email = request.headers[WEBUI_AUTH_TRUSTED_EMAIL_HEADER].lower()
        name = email

        if WEBUI_AUTH_TRUSTED_NAME_HEADER:
            name = request.headers.get(WEBUI_AUTH_TRUSTED_NAME_HEADER, email)
            try:
                name = urllib.parse.unquote(name, encoding='utf-8')
            except Exception as e:
                pass

        if not await Users.get_user_by_email(email.lower(), db=db):
            await signup_handler(
                request,
                email,
                str(uuid.uuid4()),
                name,
                db=db,
            )

        user = await Auths.authenticate_user_by_email(email, db=db)
        if user:
            if WEBUI_AUTH_TRUSTED_GROUPS_HEADER:
                group_names = request.headers.get(WEBUI_AUTH_TRUSTED_GROUPS_HEADER, '').split(',')
                group_names = [name.strip() for name in group_names if name.strip()]

                if group_names:
                    await Groups.sync_groups_by_group_names(user.id, group_names, db=db)

            if WEBUI_AUTH_TRUSTED_ROLE_HEADER:
                trusted_role = request.headers.get(WEBUI_AUTH_TRUSTED_ROLE_HEADER, '').lower().strip()
                if trusted_role in {'admin', 'user', 'pending'}:
                    if user.role != trusted_role:
                        await Users.update_user_role_by_id(user.id, trusted_role, db=db)
                elif trusted_role:
                    log.warning(f'Ignoring invalid trusted role header value: {trusted_role}')

    elif WEBUI_AUTH == False:
        admin_email = 'admin@localhost'
        admin_password = 'admin'

        if await Users.get_user_by_email(admin_email.lower(), db=db):
            user = await Auths.authenticate_user(
                admin_email.lower(),
                lambda pw: verify_password(admin_password, pw),
                db=db,
            )
        else:
            if await Users.has_users(db=db):
                raise HTTPException(400, detail=ERROR_MESSAGES.EXISTING_USERS)

            await signup_handler(
                request,
                admin_email,
                admin_password,
                'User',
                db=db,
            )

            user = await Auths.authenticate_user(
                admin_email.lower(),
                lambda pw: verify_password(admin_password, pw),
                db=db,
            )
    else:
        if signin_rate_limiter.is_limited(form_data.email.lower()):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=ERROR_MESSAGES.RATE_LIMIT_EXCEEDED,
            )

        password_bytes = form_data.password.encode('utf-8')
        if len(password_bytes) > 72:
            # TODO: Implement other hashing algorithms that support longer passwords
            log.info('Password too long, truncating to 72 bytes for bcrypt')
            password_bytes = password_bytes[:72]

            # decode safely — ignore incomplete UTF-8 sequences
            form_data.password = password_bytes.decode('utf-8', errors='ignore')

        user = await Auths.authenticate_user(
            form_data.email.lower(),
            lambda pw: verify_password(form_data.password, pw),
            db=db,
        )

    if user:
        return await create_session_response(request, user, db, response, set_cookie=True)
    else:
        raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)


############################
# SignUp
############################


async def signup_handler(
    request: Request,
    email: str,
    password: str,
    name: str,
    profile_image_url: str = '/user.png',
    *,
    db: AsyncSession,
) -> UserModel:
    """
    Core user-creation logic shared by the signup endpoint and
    trusted-header / no-auth auto-registration flows.

    Returns the newly created UserModel.
    Raises HTTPException on failure.
    """
    # Insert with default role first to avoid TOCTOU race on first signup.
    # If has_users() is checked before insert, concurrent requests during
    # first-user registration can all see an empty table and each get admin.
    hashed = get_password_hash(password)

    user = await Auths.insert_new_auth(
        email=email.lower(),
        password=hashed,
        name=name,
        profile_image_url=profile_image_url,
        role=request.app.state.config.DEFAULT_USER_ROLE,
        db=db,
    )
    if not user:
        raise HTTPException(500, detail=ERROR_MESSAGES.CREATE_USER_ERROR)

    # Atomically check if this is the only user *after* the insert.
    # Only the single user present at this point should become admin.
    if await Users.get_num_users(db=db) == 1:
        await Users.update_user_role_by_id(user.id, 'admin', db=db)
        user = await Users.get_user_by_id(user.id, db=db)
        request.app.state.config.ENABLE_SIGNUP = False

    if request.app.state.config.WEBHOOK_URL:
        await post_webhook(
            request.app.state.WEBUI_NAME,
            request.app.state.config.WEBHOOK_URL,
            WEBHOOK_MESSAGES.USER_SIGNUP(user.name),
            {
                'action': 'signup',
                'message': WEBHOOK_MESSAGES.USER_SIGNUP(user.name),
                'user': user.model_dump_json(exclude_none=True),
            },
        )

    await apply_default_group_assignment(
        request.app.state.config.DEFAULT_GROUP_ID,
        user.id,
        db=db,
    )

    return user


@router.post('/signup', response_model=SessionUserResponse)
async def signup(
    request: Request,
    response: Response,
    form_data: SignupForm,
    db: AsyncSession = Depends(get_async_session),
):
    has_users = await Users.has_users(db=db)

    if WEBUI_AUTH:
        if has_users:
            if not request.app.state.config.ENABLE_SIGNUP or not request.app.state.config.ENABLE_LOGIN_FORM:
                raise HTTPException(status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.ACCESS_PROHIBITED)
        # Don't gate the first admin on ENABLE_SIGNUP: it auto-disables and can persist stale across a DB reset.
        elif not request.app.state.config.ENABLE_LOGIN_FORM and not ENABLE_INITIAL_ADMIN_SIGNUP:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.ACCESS_PROHIBITED)
    else:
        if has_users:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.ACCESS_PROHIBITED)

    if not validate_email_format(form_data.email.lower()):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.INVALID_EMAIL_FORMAT)

    if await Users.get_user_by_email(form_data.email.lower(), db=db):
        raise HTTPException(400, detail=ERROR_MESSAGES.EMAIL_TAKEN)

    try:
        try:
            validate_password(form_data.password)
        except Exception as e:
            raise HTTPException(400, detail=str(e))

        if request.app.state.config.ENABLE_INVITE_ONLY_AUTH and has_users:
            valid_invite, invite_error, _ = consume_invite_code(
                request.app.state.config,
                form_data.invite_code,
                consumed_by=form_data.email.lower(),
            )
            if not valid_invite:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    detail=invite_error or ERROR_MESSAGES.ACCESS_PROHIBITED,
                )

        user = await signup_handler(
            request,
            form_data.email,
            form_data.password,
            form_data.name,
            form_data.profile_image_url,
            db=db,
        )
        return await create_session_response(request, user, db, response, set_cookie=True)
    except HTTPException:
        raise
    except Exception as err:
        log.error(f'Signup error: {str(err)}')
        raise HTTPException(500, detail='An internal error occurred during signup.')


@router.post('/signout')
async def signout(request: Request, response: Response, db: AsyncSession = Depends(get_async_session)):
    # get auth token from headers or cookies
    token = None
    auth_header = request.headers.get('Authorization')
    if auth_header:
        auth_cred = get_http_authorization_cred(auth_header)
        if auth_cred is not None:
            token = auth_cred.credentials
    if token is None:
        token = request.cookies.get('token')

    if token:
        await invalidate_token(request, token)

    response.delete_cookie('token')
    response.delete_cookie('oui-session')
    response.delete_cookie('oauth_id_token')

    oauth_session_id = request.cookies.get('oauth_session_id')
    if oauth_session_id:
        response.delete_cookie('oauth_session_id')

        session = await OAuthSessions.get_session_by_id(oauth_session_id, db=db)

        # If a custom end_session_endpoint is configured (e.g. AWS Cognito), redirect
        # there directly instead of attempting OIDC discovery.
        if OPENID_END_SESSION_ENDPOINT.value:
            return JSONResponse(
                status_code=200,
                content={
                    'status': True,
                    'redirect_url': OPENID_END_SESSION_ENDPOINT.value,
                },
                headers=response.headers,
            )

        oauth_server_metadata_url = (
            request.app.state.oauth_manager.get_server_metadata_url(session.provider) if session else None
        ) or OPENID_PROVIDER_URL.value

        if session and oauth_server_metadata_url:
            oauth_id_token = session.token.get('id_token')
            try:
                async with ClientSession(trust_env=True) as session:
                    async with session.get(oauth_server_metadata_url, ssl=AIOHTTP_CLIENT_SESSION_SSL) as r:
                        if r.status == 200:
                            openid_data = await r.json()
                            logout_url = openid_data.get('end_session_endpoint')

                            if logout_url:
                                return JSONResponse(
                                    status_code=200,
                                    content={
                                        'status': True,
                                        'redirect_url': f'{logout_url}?id_token_hint={oauth_id_token}'
                                        + (
                                            f'&post_logout_redirect_uri={WEBUI_AUTH_SIGNOUT_REDIRECT_URL}'
                                            if WEBUI_AUTH_SIGNOUT_REDIRECT_URL
                                            else ''
                                        ),
                                    },
                                    headers=response.headers,
                                )
                        else:
                            raise Exception('Failed to fetch OpenID configuration')

            except Exception as e:
                log.error(f'OpenID signout error: {str(e)}')
                raise HTTPException(
                    status_code=500,
                    detail='Failed to sign out from the OpenID provider.',
                    headers=response.headers,
                )

    if WEBUI_AUTH_SIGNOUT_REDIRECT_URL:
        return JSONResponse(
            status_code=200,
            content={
                'status': True,
                'redirect_url': WEBUI_AUTH_SIGNOUT_REDIRECT_URL,
            },
            headers=response.headers,
        )

    return JSONResponse(status_code=200, content={'status': True}, headers=response.headers)


############################
# OAuth Session Management
############################


@router.delete('/oauth/sessions/{provider:path}', response_model=bool)
async def delete_oauth_session_by_provider(
    provider: str,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Disconnect the current user's OAuth session for a specific provider.
    The provider string matches the 'provider' field in the oauth_session table
    (e.g. 'mcp:server-id' for MCP connections).
    """
    result = await OAuthSessions.delete_sessions_by_user_id_and_provider(user.id, provider, db=db)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='No OAuth session found for this provider',
        )
    return True


############################
# AddUser
############################


@router.post('/add', response_model=SigninResponse)
async def add_user(
    request: Request,
    form_data: AddUserForm,
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    if not validate_email_format(form_data.email.lower()):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.INVALID_EMAIL_FORMAT)

    if await Users.get_user_by_email(form_data.email.lower(), db=db):
        raise HTTPException(400, detail=ERROR_MESSAGES.EMAIL_TAKEN)

    try:
        try:
            validate_password(form_data.password)
        except Exception as e:
            raise HTTPException(400, detail=str(e))

        hashed = get_password_hash(form_data.password)
        user = await Auths.insert_new_auth(
            form_data.email.lower(),
            hashed,
            form_data.name,
            form_data.profile_image_url,
            form_data.role,
            db=db,
        )

        if user:
            await apply_default_group_assignment(
                request.app.state.config.DEFAULT_GROUP_ID,
                user.id,
                db=db,
            )

            expires_delta = parse_duration(request.app.state.config.JWT_EXPIRES_IN)
            token = create_token(data={'id': user.id}, expires_delta=expires_delta)
            return {
                'token': token,
                'token_type': 'Bearer',
                'id': user.id,
                'email': user.email,
                'name': user.name,
                'role': user.role,
                'profile_image_url': f'/api/v1/users/{user.id}/profile/image',
            }
        else:
            raise HTTPException(500, detail=ERROR_MESSAGES.CREATE_USER_ERROR)
    except HTTPException:
        raise
    except Exception as err:
        log.error(f'Add user error: {str(err)}')
        raise HTTPException(500, detail='An internal error occurred while adding the user.')


############################
# GetAdminDetails
############################


@router.get('/admin/details')
async def get_admin_details(
    request: Request, user=Depends(get_current_user), db: AsyncSession = Depends(get_async_session)
):
    if request.app.state.config.SHOW_ADMIN_DETAILS:
        admin_email = request.app.state.config.ADMIN_EMAIL
        admin_name = None

        log.info(f'Admin details - Email: {admin_email}, Name: {admin_name}')

        if admin_email:
            admin = await Users.get_user_by_email(admin_email, db=db)
            if admin:
                admin_name = admin.name
        else:
            admin = await Users.get_first_user(db=db)
            if admin:
                admin_email = admin.email
                admin_name = admin.name

        return {
            'name': admin_name,
            'email': admin_email,
        }
    else:
        raise HTTPException(400, detail=ERROR_MESSAGES.ACTION_PROHIBITED)


############################
# ToggleSignUp
############################


@router.get('/admin/config')
async def get_admin_config(
    request: Request,
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    return await _serialize_admin_config(request, db=db)


@router.get('/admin/config/backup')
async def export_admin_config_backup(
    request: Request,
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    return {
        'kind': 'awesome-webui-admin-config-backup',
        'version': 1,
        'created_at': int(time.time()),
        'config': await _serialize_admin_config(request, include_meta=False, db=db),
    }


class AdminConfig(BaseModel):
    model_config = ConfigDict(extra='allow')


class AdminConfigBackupImport(BaseModel):
    model_config = ConfigDict(extra='allow')
    config: dict | None = None


async def _can_user_create_invite_codes(user, config, db: AsyncSession) -> tuple[bool, str, int]:
    if not user:
        return False, 'Authentication required.', 0

    if user.role == 'admin':
        return True, '', 0

    policy = get_invite_policy(config)
    scope = policy['creator_scope']

    if scope == 'admin':
        return False, 'Only admins can create invite codes.', 0

    if scope == 'groups':
        allowed_group_ids = set(policy['creator_group_ids'])
        if not allowed_group_ids:
            return False, 'No creator groups are configured.', 0

        groups = await Groups.get_groups_by_member_id(user.id, db=db)
        if not {group.id for group in groups}.intersection(allowed_group_ids):
            return False, 'You do not have permission to create invite codes.', 0
        return True, '', 0

    cooldown_seconds = policy['creator_cooldown_seconds']
    if cooldown_seconds <= 0:
        return True, '', 0

    now = int(time.time())
    latest_created_at = max(
        [
            int(invite.get('created_at') or 0)
            for invite in get_clean_invite_codes(config)
            if invite.get('created_by') == user.id
        ]
        or [0]
    )
    remaining = latest_created_at + cooldown_seconds - now
    if remaining > 0:
        return False, f'Invite creation cooldown is active. Try again in {remaining} seconds.', remaining

    return True, '', 0


@router.get('/invites')
async def get_invite_codes(
    request: Request,
    user=Depends(get_verified_user),
):
    _ensure_invite_config_keys(request)
    return {'items': get_invite_codes_for_user(user, request.app.state.config)}


@router.post('/invites')
async def issue_invite_code(
    request: Request,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    _ensure_invite_config_keys(request)
    can_create, reason, _ = await _can_user_create_invite_codes(user, request.app.state.config, db=db)
    if not can_create:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=reason or ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    try:
        return create_invite_code(request.app.state.config, user.id)
    except Exception as e:
        log.exception('Failed to create invite code')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to create invite code: {e}',
        )


@router.delete('/invites/{invite_id}')
async def delete_invite_code(
    invite_id: str,
    request: Request,
    user=Depends(get_verified_user),
):
    _ensure_invite_config_keys(request)
    all_invite_codes = get_clean_invite_codes(request.app.state.config)

    match_idx = None
    for idx, invite in enumerate(all_invite_codes):
        if not isinstance(invite, dict):
            continue

        if user.role != 'admin' and invite.get('created_by') != user.id:
            continue

        if invite.get('id') == invite_id or str(invite.get('code', '')).lower() == invite_id.lower():
            match_idx = idx
            break

    if match_idx is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Invite code not found.')

    all_invite_codes.pop(match_idx)
    request.app.state.config.INVITE_CODES = all_invite_codes
    return {'status': True}


@router.post('/admin/config')
async def update_admin_config(
    request: Request,
    form_data: AdminConfig,
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    payload = form_data.model_dump(exclude_unset=True)
    return await apply_admin_config_payload(request, payload, db=db)


def _website_license_attestation_valid(attestation: dict | None) -> bool:
    return bool(
        isinstance(attestation, dict)
        and attestation.get('accepted')
        and attestation.get('qualifies_under_license')
        and attestation.get('retain_attribution')
        and attestation.get('accept_responsibility')
    )


async def apply_admin_config_payload(request: Request, payload: dict, db: AsyncSession | None = None):
    oauth_changed = False

    for key, value in payload.items():
        if key not in ADMIN_CONFIG_KEYS:
            continue

        sanitized = _sanitize_admin_config_value(key, value)
        if sanitized is None and key in {'DEFAULT_USER_ROLE', 'JWT_EXPIRES_IN'}:
            continue

        if not _ensure_config_key(request, key, sanitized):
            log.debug(f'Skipping unknown admin config key: {key}')
            continue

        setattr(request.app.state.config, key, sanitized)
        if key == 'WEBSITE_BRAND_NAME':
            request.app.state.WEBUI_NAME = sanitized
        if 'OAUTH' in key or key.startswith(('GOOGLE_', 'MICROSOFT_', 'GITHUB_', 'OIDC_', 'FEISHU_', 'DISCORD_', 'GITLAB_', 'SLACK_')):
            oauth_changed = True

    if oauth_changed:
        _reload_oauth_runtime(request)

    await _emit_public_config_update(request)
    return await _serialize_admin_config(request, db=db)


@router.post('/admin/config/backup')
async def import_admin_config_backup(
    request: Request,
    form_data: AdminConfigBackupImport,
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    payload = form_data.config if isinstance(form_data.config, dict) else form_data.model_dump(exclude_unset=True)
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid config backup.')
    return await apply_admin_config_payload(request, payload, db=db)


class LdapServerConfig(BaseModel):
    label: str
    host: str
    port: int | None = None
    attribute_for_mail: str = 'mail'
    attribute_for_username: str = 'uid'
    app_dn: str
    app_dn_password: str
    search_base: str
    search_filters: str = ''
    use_tls: bool = True
    certificate_path: str | None = None
    validate_cert: bool = True
    ciphers: str | None = 'ALL'


@router.get('/admin/config/ldap/server', response_model=LdapServerConfig)
async def get_ldap_server(request: Request, user=Depends(get_admin_user)):
    return {
        'label': request.app.state.config.LDAP_SERVER_LABEL,
        'host': request.app.state.config.LDAP_SERVER_HOST,
        'port': request.app.state.config.LDAP_SERVER_PORT,
        'attribute_for_mail': request.app.state.config.LDAP_ATTRIBUTE_FOR_MAIL,
        'attribute_for_username': request.app.state.config.LDAP_ATTRIBUTE_FOR_USERNAME,
        'app_dn': request.app.state.config.LDAP_APP_DN,
        'app_dn_password': request.app.state.config.LDAP_APP_PASSWORD,
        'search_base': request.app.state.config.LDAP_SEARCH_BASE,
        'search_filters': request.app.state.config.LDAP_SEARCH_FILTERS,
        'use_tls': request.app.state.config.LDAP_USE_TLS,
        'certificate_path': request.app.state.config.LDAP_CA_CERT_FILE,
        'validate_cert': request.app.state.config.LDAP_VALIDATE_CERT,
        'ciphers': request.app.state.config.LDAP_CIPHERS,
    }


@router.post('/admin/config/ldap/server')
async def update_ldap_server(request: Request, form_data: LdapServerConfig, user=Depends(get_admin_user)):
    required_fields = [
        'label',
        'host',
        'attribute_for_mail',
        'attribute_for_username',
        'search_base',
    ]
    for key in required_fields:
        value = getattr(form_data, key)
        if not value:
            raise HTTPException(400, detail=ERROR_MESSAGES.REQUIRED_FIELD_EMPTY(key))

    request.app.state.config.LDAP_SERVER_LABEL = form_data.label
    request.app.state.config.LDAP_SERVER_HOST = form_data.host
    request.app.state.config.LDAP_SERVER_PORT = form_data.port
    request.app.state.config.LDAP_ATTRIBUTE_FOR_MAIL = form_data.attribute_for_mail
    request.app.state.config.LDAP_ATTRIBUTE_FOR_USERNAME = form_data.attribute_for_username
    request.app.state.config.LDAP_APP_DN = form_data.app_dn or ''
    request.app.state.config.LDAP_APP_PASSWORD = form_data.app_dn_password or ''
    request.app.state.config.LDAP_SEARCH_BASE = form_data.search_base
    request.app.state.config.LDAP_SEARCH_FILTERS = form_data.search_filters
    request.app.state.config.LDAP_USE_TLS = form_data.use_tls
    request.app.state.config.LDAP_CA_CERT_FILE = form_data.certificate_path
    request.app.state.config.LDAP_VALIDATE_CERT = form_data.validate_cert
    request.app.state.config.LDAP_CIPHERS = form_data.ciphers

    return {
        'label': request.app.state.config.LDAP_SERVER_LABEL,
        'host': request.app.state.config.LDAP_SERVER_HOST,
        'port': request.app.state.config.LDAP_SERVER_PORT,
        'attribute_for_mail': request.app.state.config.LDAP_ATTRIBUTE_FOR_MAIL,
        'attribute_for_username': request.app.state.config.LDAP_ATTRIBUTE_FOR_USERNAME,
        'app_dn': request.app.state.config.LDAP_APP_DN,
        'app_dn_password': request.app.state.config.LDAP_APP_PASSWORD,
        'search_base': request.app.state.config.LDAP_SEARCH_BASE,
        'search_filters': request.app.state.config.LDAP_SEARCH_FILTERS,
        'use_tls': request.app.state.config.LDAP_USE_TLS,
        'certificate_path': request.app.state.config.LDAP_CA_CERT_FILE,
        'validate_cert': request.app.state.config.LDAP_VALIDATE_CERT,
        'ciphers': request.app.state.config.LDAP_CIPHERS,
    }


@router.get('/admin/config/ldap')
async def get_ldap_config(request: Request, user=Depends(get_admin_user)):
    return {'ENABLE_LDAP': request.app.state.config.ENABLE_LDAP}


class LdapConfigForm(BaseModel):
    enable_ldap: bool | None = None


@router.post('/admin/config/ldap')
async def update_ldap_config(request: Request, form_data: LdapConfigForm, user=Depends(get_admin_user)):
    request.app.state.config.ENABLE_LDAP = form_data.enable_ldap
    return {'ENABLE_LDAP': request.app.state.config.ENABLE_LDAP}


############################
# API Key
############################


# create api key
@router.post('/api_key', response_model=ApiKey)
async def generate_api_key(
    request: Request, user=Depends(get_current_user), db: AsyncSession = Depends(get_async_session)
):
    if not request.app.state.config.ENABLE_API_KEYS or (
        user.role != 'admin'
        and not await has_permission(user.id, 'features.api_keys', request.app.state.config.USER_PERMISSIONS)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.API_KEY_CREATION_NOT_ALLOWED,
        )

    api_key = create_api_key()
    success = await Users.update_user_api_key_by_id(user.id, api_key, db=db)

    if success:
        return {
            'api_key': api_key,
        }
    else:
        raise HTTPException(500, detail=ERROR_MESSAGES.CREATE_API_KEY_ERROR)


# delete api key
@router.delete('/api_key', response_model=bool)
async def delete_api_key(user=Depends(get_current_user), db: AsyncSession = Depends(get_async_session)):
    return await Users.delete_user_api_key_by_id(user.id, db=db)


# get api key
@router.get('/api_key', response_model=ApiKey)
async def get_api_key(user=Depends(get_current_user), db: AsyncSession = Depends(get_async_session)):
    api_key = await Users.get_user_api_key_by_id(user.id, db=db)
    if api_key:
        return {
            'api_key': api_key,
        }
    else:
        raise HTTPException(404, detail=ERROR_MESSAGES.API_KEY_NOT_FOUND)


############################
# Token Exchange
############################


class TokenExchangeForm(BaseModel):
    token: str  # OAuth access token from external provider


@router.post('/oauth/{provider}/token/exchange', response_model=SessionUserResponse)
async def token_exchange(
    request: Request,
    response: Response,
    provider: str,
    form_data: TokenExchangeForm,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Exchange an external OAuth provider token for an OpenWebUI JWT.
    This endpoint is disabled by default. Set ENABLE_OAUTH_TOKEN_EXCHANGE=True to enable.
    """
    if not ENABLE_OAUTH_TOKEN_EXCHANGE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Token exchange is disabled',
        )

    provider = provider.lower()

    # Check if provider is configured
    if provider not in OAUTH_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.OAUTH_NOT_CONFIGURED(provider),
        )
    # Get the OAuth client for this provider
    oauth_manager = request.app.state.oauth_manager
    client = oauth_manager.get_client(provider)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.OAUTH_NOT_CONFIGURED(provider),
        )

    # Validate the token by calling the userinfo endpoint
    try:
        token_data = {'access_token': form_data.token, 'token_type': 'Bearer'}
        user_data = await client.userinfo(token=token_data)

        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Invalid token or unable to fetch user info',
            )
    except Exception as e:
        log.warning(f'Token exchange failed for provider {provider}: {e}')
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid token or unable to validate with provider',
        )

    # Extract user information from the token claims
    email_claim = request.app.state.config.OAUTH_EMAIL_CLAIM
    username_claim = request.app.state.config.OAUTH_USERNAME_CLAIM

    # Get sub claim
    sub = user_data.get(request.app.state.config.OAUTH_SUB_CLAIM or OAUTH_PROVIDERS[provider].get('sub_claim', 'sub'))
    if not sub:
        log.warning(f'Token exchange failed: sub claim missing from user data')
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token missing required 'sub' claim",
        )

    email = user_data.get(email_claim, '')
    if not email:
        log.warning(f'Token exchange failed: email claim missing from user data')
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Token missing required email claim',
        )
    email = email.lower()

    # Enforce domain allowlist — same check as the normal OAuth callback
    if (
        '*' not in auth_manager_config.OAUTH_ALLOWED_DOMAINS
        and email.split('@')[-1] not in auth_manager_config.OAUTH_ALLOWED_DOMAINS
    ):
        log.warning(f'Token exchange denied: email domain not in allowed domains list')
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    # Try to find the user by OAuth sub
    user = await Users.get_user_by_oauth_sub(provider, sub, db=db)

    if not user and OAUTH_MERGE_ACCOUNTS_BY_EMAIL.value:
        # Try to find by email if merge is enabled
        user = await Users.get_user_by_email(email, db=db)
        if user:
            # Link the OAuth sub to this user
            await Users.update_user_oauth_by_id(user.id, provider, sub, db=db)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='User not found. Please sign in via the web interface first.',
        )

    return await create_session_response(request, user, db)
