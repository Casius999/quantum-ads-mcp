import datetime as dt

from quantum_ads.core.versioning.version_manager import SUNSET_SCHEDULE, VersionManager


def test_pinned_version_default():
    vm = VersionManager(version="v24", client_factory=lambda creds, version: ("client", version))
    assert vm.version == "v24"


def test_build_client_uses_factory_and_version():
    captured: dict[str, str] = {}

    def factory(creds: dict[str, object], version: str) -> str:
        captured["v"] = version
        return "C"

    vm = VersionManager(version="v24", client_factory=factory)
    assert vm.build_client({"developer_token": "x"}) == "C"
    assert captured["v"] == "v24"


def test_days_until_sunset_known_version():
    vm = VersionManager(version="v24", client_factory=lambda c, v: None)
    today = dt.date(2026, 6, 8)
    assert vm.days_until_sunset(today) == (SUNSET_SCHEDULE["v24"] - today).days


def test_days_until_sunset_unknown_version_is_none():
    vm = VersionManager(version="v99", client_factory=lambda c, v: None)
    assert vm.days_until_sunset(dt.date(2026, 6, 8)) is None
