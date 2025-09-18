from pinion.retry import RetryPolicy


def test_retry_policy_without_jitter():
    policy = RetryPolicy(base_delay=0.2, cap=5.0, jitter=False)
    # attempt=3 -> base_delay * 2**(attempt-1) = 0.2 * 4 = 0.8
    assert policy.compute_delay(3) == 0.8


def test_retry_policy_with_jitter(monkeypatch):
    calls = {}

    def fake_uniform(low, high):
        calls["args"] = (low, high)
        return 0.123

    policy = RetryPolicy(base_delay=0.5, cap=1.0, jitter=True)
    monkeypatch.setattr("random.uniform", fake_uniform)

    delay = policy.compute_delay(2)

    assert delay == 0.123
    assert calls["args"] == (0, 0.5 * 2 ** (2 - 1))
