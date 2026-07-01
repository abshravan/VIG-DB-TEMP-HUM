from app.core.rate_limit import SlidingWindowRateLimiter


def test_allows_up_to_max_attempts():
    limiter = SlidingWindowRateLimiter(max_attempts=3, window_seconds=60)
    now = 1000.0
    for _ in range(3):
        assert limiter.is_allowed("alice", now)
        limiter.record_attempt("alice", now)
    assert not limiter.is_allowed("alice", now)


def test_keys_are_independent():
    limiter = SlidingWindowRateLimiter(max_attempts=1, window_seconds=60)
    now = 1000.0
    limiter.record_attempt("alice", now)
    assert not limiter.is_allowed("alice", now)
    assert limiter.is_allowed("bob", now)


def test_old_attempts_expire_out_of_the_window():
    limiter = SlidingWindowRateLimiter(max_attempts=1, window_seconds=60)
    limiter.record_attempt("alice", now=1000.0)
    assert not limiter.is_allowed("alice", now=1030.0)  # still within window
    assert limiter.is_allowed("alice", now=1061.0)  # window has passed


def test_record_attempt_after_window_expiry_does_not_accumulate_stale_entries():
    limiter = SlidingWindowRateLimiter(max_attempts=2, window_seconds=60)
    limiter.record_attempt("alice", now=1000.0)
    limiter.record_attempt("alice", now=1500.0)  # long after the first expired
    # only the recent attempt should count — still 1 slot free
    assert limiter.is_allowed("alice", now=1500.0)
