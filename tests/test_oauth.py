from __future__ import annotations

import base64
import hashlib
from urllib.parse import parse_qs, urlparse

import httpx

from myq_bridge.cloud import AUTH_URL
from myq_bridge.oauth import (
    ANDROID_CLIENT_ID,
    ANDROID_REDIRECT_URI,
    ANDROID_SCOPE,
    PkcePair,
    build_authorization_url,
    exchange_authorization_code,
)


def test_pkce_pair_uses_rfc7636_s256():
    pair = PkcePair.generate()
    expected = base64.urlsafe_b64encode(
        hashlib.sha256(pair.verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")

    assert 43 <= len(pair.verifier) <= 128
    assert pair.challenge == expected


def test_android_authorization_url_matches_current_app_shape():
    pair = PkcePair(verifier="verifier", challenge="challenge")
    parsed = urlparse(build_authorization_url(pair))
    query = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "partner-identity.myq-cloud.com"
    assert parsed.path == "/connect/authorize"
    assert query == {
        "client_id": [ANDROID_CLIENT_ID],
        "scope": [ANDROID_SCOPE],
        "response_type": ["code"],
        "redirect_uri": [ANDROID_REDIRECT_URI],
        "code_challenge": ["challenge"],
        "code_challenge_method": ["S256"],
        "ui_locales": ["en-US"],
        "acr_values": ["unified_flow:v1  brand:myq"],
        "prompt": ["login"],
    }


def test_authorization_code_exchange_returns_android_session():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == AUTH_URL
        assert request.headers["app-version"] == "5.243.1.73243"
        assert request.headers["user-agent"] == "S7MAX/Android 12"
        assert request.headers["myqapplicationid"]
        assert "culture" not in request.headers
        assert request.headers["brandid"] == "1"
        assert "apiversion" not in request.headers
        form = parse_qs(request.content.decode("utf-8"))
        assert form["client_id"] == [ANDROID_CLIENT_ID]
        assert form["scope"] == [ANDROID_SCOPE]
        assert form["grant_type"] == ["authorization_code"]
        assert form["code"] == ["code-value"]
        assert form["redirect_uri"] == [ANDROID_REDIRECT_URI]
        assert form["code_verifier"] == ["verifier-value"]
        return httpx.Response(
            200,
            json={"access_token": "access-value", "refresh_token": "refresh-value"},
        )

    session = exchange_authorization_code(
        "code-value",
        "verifier-value",
        transport=httpx.MockTransport(handler),
    )

    assert session.client_id == ANDROID_CLIENT_ID
    assert session.access_token == "access-value"
    assert session.refresh_token == "refresh-value"
