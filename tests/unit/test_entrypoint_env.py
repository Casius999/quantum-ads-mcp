from pathlib import Path

from quantum_ads.__main__ import DEFAULT_AUDIT_DIR, runtime_env


def test_entrypoint_persists_the_audit_ledger_by_default():
    assert runtime_env({})["QUANTUM_ADS_AUDIT_DIR"] == str(DEFAULT_AUDIT_DIR)
    assert Path.home() / ".quantum-ads" / "audit" == DEFAULT_AUDIT_DIR


def test_explicit_audit_dir_wins_and_empty_keeps_it_in_memory():
    assert (
        runtime_env({"QUANTUM_ADS_AUDIT_DIR": "/srv/audit"})["QUANTUM_ADS_AUDIT_DIR"]
        == "/srv/audit"
    )
    assert runtime_env({"QUANTUM_ADS_AUDIT_DIR": ""})["QUANTUM_ADS_AUDIT_DIR"] == ""


def test_runtime_env_keeps_the_rest_of_the_environment():
    assert runtime_env({"GOOGLE_CLOUD_PROJECT": "p"})["GOOGLE_CLOUD_PROJECT"] == "p"


def test_call_log_sink_is_on_by_default_and_can_be_disabled():
    from quantum_ads.__main__ import call_log_sink

    assert callable(call_log_sink({}))
    assert call_log_sink({"QUANTUM_ADS_LOG_CALLS": "false"}) is None
