from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_pymyq_is_not_a_runtime_dependency():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert not any(
        "pymyq" in line.lower()
        for line in pyproject.splitlines()
        if not line.lstrip().startswith("#")
    )


def test_pymyq_policy_has_an_unmistakable_reopen_gate():
    policy = (ROOT / "docs" / "PYMYQ_DEPRECATION.md").read_text(encoding="utf-8")
    assert "COMPLETELY DEPRECATED" in policy
    assert "NEVER EVER" in policy
    assert "2026 or later" in policy
    assert "current account" in policy
    assert "current opener" in policy
