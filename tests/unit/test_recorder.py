from quantum_ads.core.observability.recorder import CallRecorder


def test_records_emit_json_lines_and_summarize():
    lines: list[str] = []
    recorder = CallRecorder(sink=lines.append)
    recorder.record(tool="ads.gaql.query", tenant="acme", ok=True, duration_ms=12)
    recorder.record(tool="ads.budget.update", tenant="acme", ok=False, duration_ms=30)
    assert recorder.summary() == {"total": 2, "ok": 1, "failed": 1}
    assert len(lines) == 2
    assert '"tool":"ads.gaql.query"' in lines[0]


def test_recorder_without_sink_still_collects():
    recorder = CallRecorder()
    recorder.record(tool="x", tenant="t", ok=True, duration_ms=1)
    assert recorder.summary()["total"] == 1
