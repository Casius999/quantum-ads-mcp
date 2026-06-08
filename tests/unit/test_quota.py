from quantum_ads.core.query.quota import TokenBucket, backoff_seconds


def test_token_bucket_allows_then_denies():
    bucket = TokenBucket(capacity=2, refill_per_sec=0, now=lambda: 0.0)
    assert bucket.try_acquire()
    assert bucket.try_acquire()
    assert not bucket.try_acquire()


def test_token_bucket_refills_over_time():
    clock = {"t": 0.0}
    bucket = TokenBucket(capacity=1, refill_per_sec=1.0, now=lambda: clock["t"])
    assert bucket.try_acquire()
    assert not bucket.try_acquire()
    clock["t"] = 1.0
    assert bucket.try_acquire()


def test_backoff_grows_and_caps():
    assert backoff_seconds(0) == 1
    assert backoff_seconds(3) == 8
    assert backoff_seconds(10) == 60
