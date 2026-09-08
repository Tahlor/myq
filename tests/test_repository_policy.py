from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_canonical_docs_name_only_issue_9_and_issue_4_as_active_authority():
    for relative in (
        "README.md",
        "AGENTS.md",
        "docs/LIVE_RUNBOOK.md",
        "docs/COMPLETION_CRITERIA.md",
    ):
        text = _read(relative)
        assert "#9" in text
        assert "#4" in text

    runbook = _read("docs/LIVE_RUNBOOK.md")
    assert "issue #6" not in runbook.lower()
    assert "issue #7" not in runbook.lower()
    assert "issue #8" not in runbook.lower()


def test_hardware_archives_start_with_the_issue_9_gate_banner():
    for relative in (
        "docs/G0401_DEFERRED_HARDWARE_ATTACK_PLAN.md",
        "docs/G0401_DEFERRED_HARDWARE_RF_PLAN.md",
        "docs/G0401_DEFERRED_HARDWARE_PROGRESS.md",
    ):
        first_line = _read(relative).splitlines()[0]
        assert "DO NOT EXECUTE UNTIL #9 GATE" in first_line


def test_hardware_activation_requires_both_explicit_values():
    criteria = _read("docs/COMPLETION_CRITERIA.md")
    runbook = _read("docs/LIVE_RUNBOOK.md")
    assert "SOFTWARE_EXHAUSTED=yes" in criteria
    assert "HARDWARE_NOW_JUSTIFIED=yes" in criteria
    assert "SOFTWARE_EXHAUSTED=yes" in runbook
    assert "HARDWARE_NOW_JUSTIFIED=yes" in runbook


def test_direct_cloud_is_opt_in_and_has_no_deployment_bootstrap():
    cloud_cli = _read("src/myq_bridge/cloud_cli.py")
    assert 'EXPERIMENTAL_CLOUD_FLAG = "MYQ_ENABLE_EXPERIMENTAL_CLOUD"' in cloud_cli
    assert not (ROOT / "deploy" / "myq-cloud.service").exists()
    assert not (ROOT / "deploy" / "myq_bridge.env.example").exists()
    assert not (ROOT / "scripts" / "provision_pi3_session.ps1").exists()


def test_named_software_lanes_are_in_the_active_runbook():
    runbook = _read("docs/LIVE_RUNBOOK.md")
    for phrase in (
        "UI-free internal dispatch",
        "Accessibility + Single Tap",
        "UIAutomator fallback",
        "Notification side-channel",
        "Screenshot/vision driver",
        "backup/clone",
        "myQ Community/Craftsman",
        "normal-LAN",
        "passive OTA/current-firmware",
        "RTL8720CS",
        "PSK-provisioning",
        "historical MCU parser",
        "MFA/refresh",
        "Ezlo SoftHub/Tricon",
        "IFTTT/partner",
        "ReDroid",
    ):
        assert phrase in runbook


def test_transient_agent_files_are_not_present():
    assert not list(ROOT.glob(".local_agent_*"))
