"""PKCE bootstrap helpers recovered from the current Android myQ app.

The official app performs an OAuth authorization-code flow in a browser and
then exchanges the code for the rotating access/refresh-token pair used by
the cloud APIs.  This module deliberately does not automate credential entry;
it only builds the public authorization request and performs the code
exchange once an authorized browser flow has produced a code.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlencode

import httpx

from .cloud import CloudSession, MyQAuthError, MyQCloudError
from .protocol_profile import ANDROID_2026_09


ANDROID_CLIENT_ID = ANDROID_2026_09.client_id
ANDROID_SCOPE = ANDROID_2026_09.scope or ""
ANDROID_REDIRECT_URI = ANDROID_2026_09.redirect_uri or ""
ANDROID_AUTHORIZATION_URL = ANDROID_2026_09.authorization_url
ANDROID_APP_VERSION = ANDROID_2026_09.app_version
ANDROID_USER_AGENT = ANDROID_2026_09.user_agent
ANDROID_APPLICATION_ID = ANDROID_2026_09.application_id or ""
ANDROID_CULTURE = ANDROID_2026_09.culture or ""
ANDROID_BRAND_ID = ANDROID_2026_09.brand_id or ""
ANDROID_API_VERSION = ANDROID_2026_09.api_version or ""
AUTH_URL = ANDROID_2026_09.token_url


@dataclass(frozen=True)
class PkcePair:
    """A verifier and S256 challenge suitable for one authorization attempt."""

    verifier: str
    challenge: str

    @classmethod
    def generate(cls) -> "PkcePair":
        verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=")
        verifier_text = verifier.decode("ascii")
        digest = hashlib.sha256(verifier).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        return cls(verifier=verifier_text, challenge=challenge)


def build_authorization_url(
    pkce: PkcePair,
    *,
    client_id: str = ANDROID_CLIENT_ID,
    scope: str = ANDROID_SCOPE,
    redirect_uri: str = ANDROID_REDIRECT_URI,
    locale: str = "en-US",
    brand: str = "myq",
    unified_flow: bool = True,
    signup: bool = False,
    prompt: str = "login",
) -> str:
    """Build the Android app's browser authorization URL.

    The two ACR values intentionally retain the empty slot used by the app,
    which produces ``unified_flow:v1  brand:myq`` for the normal login path.
    """

    unified_value = "unified_flow:v1" if unified_flow else ""
    signup_value = "create_user:true" if signup else ""
    acr_values = f"{unified_value} {signup_value} brand:{brand}"
    params = [
        ("client_id", client_id),
        ("scope", scope),
        ("response_type", "code"),
        ("redirect_uri", redirect_uri),
        ("code_challenge", pkce.challenge),
        ("code_challenge_method", "S256"),
        ("ui_locales", locale),
        ("acr_values", acr_values),
        ("prompt", prompt),
    ]
    return f"{ANDROID_AUTHORIZATION_URL}?{urlencode(params, quote_via=quote)}"


def exchange_authorization_code(
    code: str,
    verifier: str,
    *,
    client_id: str = ANDROID_CLIENT_ID,
    scope: str = ANDROID_SCOPE,
    redirect_uri: str = ANDROID_REDIRECT_URI,
    app_version: str = ANDROID_APP_VERSION,
    user_agent: str = ANDROID_USER_AGENT,
    app_check_token: str | None = None,
    transport: httpx.BaseTransport | None = None,
    timeout: float = 20.0,
) -> CloudSession:
    """Exchange one authorized code without logging any token material."""

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
        "App-Version": app_version,
        "User-Agent": user_agent,
        "MyQApplicationId": ANDROID_APPLICATION_ID,
        "BrandId": ANDROID_BRAND_ID,
    }
    if app_check_token:
        headers["Firebase-AppCheck-Token"] = app_check_token
    data = {
        "client_id": client_id,
        "scope": scope,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": verifier,
    }
    with httpx.Client(transport=transport, timeout=timeout, follow_redirects=True) as client:
        response = client.post(AUTH_URL, headers=headers, data=data)
    if response.status_code in (400, 401):
        raise MyQAuthError(f"MyQ authorization-code exchange rejected ({response.status_code})")
    if not response.is_success:
        body = response.text[:500]
        raise MyQCloudError(
            f"MyQ authorization-code exchange failed ({response.status_code}): {body}"
        )
    payload: dict[str, Any] = response.json()
    access_token = str(payload.get("access_token") or "").strip()
    refresh_token = str(payload.get("refresh_token") or "").strip()
    if not access_token or not refresh_token:
        raise MyQAuthError("MyQ authorization response omitted access or refresh token")
    return CloudSession(
        access_token=access_token,
        refresh_token=refresh_token,
        client_id=client_id,
        app_version=app_version,
        user_agent=user_agent,
        profile_name=ANDROID_2026_09.name,
    )
