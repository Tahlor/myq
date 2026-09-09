from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MyQProtocolProfile:
    """Public protocol metadata recovered from a specific official client.

    Secrets and rotating sessions never belong here. A profile is immutable,
    reviewable evidence that can be retained while a newer candidate is tested.
    """

    name: str
    client_id: str
    app_version: str
    user_agent: str
    authorization_url: str
    token_url: str
    scope: str | None
    redirect_uri: str | None
    application_id: str | None
    culture: str | None
    brand_id: str | None
    api_version: str | None
    accounts_url: str
    device_urls: tuple[str, ...]
    door_action_url: str
    lockmode_url: str


COMMON_AUTHORIZATION_URL = "https://partner-identity.myq-cloud.com/connect/authorize"
COMMON_TOKEN_URL = "https://partner-identity.myq-cloud.com/connect/token"
COMMON_ACCOUNTS_URL = "https://accounts.myq-cloud.com/api/v6.0/accounts"
COMMON_DOOR_ACTION_URL = (
    "https://account-devices-gdo.myq-cloud.com/api/v6.0/Accounts/"
    "{account_id}/door_openers/{door_opener_id}/{action}"
)
COMMON_LOCKMODE_URL = (
    "https://account-devices-gdo.myq-cloud.com/api/v6.0/accounts/"
    "{account_id}/door_openers/{door_opener_id}/lockmode"
)

ANDROID_2026_09 = MyQProtocolProfile(
    name="android-5.243.1.73243",
    client_id="ANDROID_CGI_MYQ",
    app_version="5.243.1.73243",
    user_agent="S7MAX/Android 12",
    authorization_url=COMMON_AUTHORIZATION_URL,
    token_url=COMMON_TOKEN_URL,
    scope="MyQ_Residential offline_access",
    redirect_uri="com.myqops://android",
    application_id="226AC80CE0E4456384CC91DFF702D5C29909A176ADF14309A7DA3D18AFE5561D",
    culture="en",
    brand_id="1",
    api_version="4.1",
    accounts_url=COMMON_ACCOUNTS_URL,
    device_urls=(
        "https://devices.myq-cloud.com/api/v6.0/Accounts/{account_id}/Devices",
        "https://devices.myq-cloud.com/api/v6.2/Accounts/{account_id}/Devices",
    ),
    door_action_url=COMMON_DOOR_ACTION_URL,
    lockmode_url=COMMON_LOCKMODE_URL,
)

IOS_2026_09 = MyQProtocolProfile(
    name="ios-5.315.0.66076",
    client_id="IOS_CGI_MYQ",
    app_version="5.315.0.66076",
    user_agent="myQ/315.0.66076 CFNetwork/3860.700.1 Darwin/25.6.0",
    authorization_url=COMMON_AUTHORIZATION_URL,
    token_url=COMMON_TOKEN_URL,
    scope=None,
    redirect_uri=None,
    application_id=None,
    culture=None,
    brand_id=None,
    api_version=None,
    accounts_url=COMMON_ACCOUNTS_URL,
    device_urls=("https://devices.myq-cloud.com/api/v6.2/Accounts/{account_id}/Devices",),
    door_action_url=COMMON_DOOR_ACTION_URL,
    lockmode_url=COMMON_LOCKMODE_URL,
)

PROFILES = {profile.name: profile for profile in (ANDROID_2026_09, IOS_2026_09)}
LAST_KNOWN_GOOD_ANDROID = ANDROID_2026_09
DEFAULT_CLOUD_PROFILE = IOS_2026_09


def profile_for_client(client_id: str) -> MyQProtocolProfile:
    if client_id == ANDROID_2026_09.client_id:
        return ANDROID_2026_09
    return IOS_2026_09
