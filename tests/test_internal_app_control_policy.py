from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_internal_agent_defaults_to_suppressed_dry_run():
    agent = _read("reverse/frida/garage_internal_control.js")
    assert "globalThis.MYQ_EXECUTE === true" in agent
    assert "if (!execute)" in agent
    assert "action: 'open'" in agent
    assert "action: 'close'" in agent
    assert "network_calls_suppressed: true" in agent


def test_internal_agent_requires_exactly_one_stable_garage():
    agent = _read("reverse/frida/garage_internal_control.js")
    assert "doors.size() !== 1" in agent
    assert "state !== 'OPEN' && state !== 'CLOSED'" in agent
    assert "unstable_state" in agent


def test_live_wrapper_requires_matching_confirmation_and_no_mutation_retry():
    wrapper = _read("scripts/invoke_myq_internal_action.ps1")
    assert '$ConfirmAction -ne $Action' in wrapper
    assert 'requires -ConfirmAction $Action' in wrapper
    assert "do not retry the command" in wrapper.lower()
    assert '$ValidatedFridaVersion = "17.9.0"' in wrapper


def test_wrapper_has_local_tool_fallbacks_without_embedding_credentials():
    wrapper = _read("scripts/invoke_myq_internal_action.ps1")
    assert "adbutils\\binaries\\adb.exe" in wrapper
    assert "Python\\Python*\\Scripts\\frida.exe" in wrapper
    forbidden = ("password", "oauth", "access_token", "refresh_token")
    assert not any(item in wrapper.lower() for item in forbidden)
