from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_pi3_service_is_localhost_only_and_host_local_secret_backed():
    service = _read("deploy/myq-cloud.service")
    env = _read("deploy/myq-cloud.env.example")
    assert "127.0.0.1" in service
    assert "0.0.0.0" not in service
    assert "EnvironmentFile=/etc/myq/myq-cloud.env" in service
    assert "MYQ_CLOUD_SESSION=/var/lib/myq/cloud_session.json" in env
    assert "MYQ_PROTOCOL_PROFILE=android-5.243.1.73243" in env
    assert "REPLACE_WITH_RANDOM_LOCAL_API_KEY" in env


def test_pi3_installer_never_embeds_or_generates_myq_credentials():
    script = _read("scripts/install_pi3_native_cloud.sh")
    lowered = script.lower()
    assert "cloud_session.json" in script
    assert "openssl rand" in script  # local bridge API key only
    assert "password=" not in lowered
    assert "access_token" not in lowered
    assert "refresh_token" not in lowered
    assert "pymyq" not in lowered


def test_pi3_base_install_does_not_pull_android_automation_dependencies():
    import tomllib

    project = tomllib.loads(_read("pyproject.toml"))["project"]
    base = "\n".join(project["dependencies"]).lower()
    android = "\n".join(project["optional-dependencies"]["android"]).lower()
    assert "uiautomator2" not in base
    assert "uiautomator2" in android
