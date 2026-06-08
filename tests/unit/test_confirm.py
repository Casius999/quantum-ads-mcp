from quantum_ads.core.safety.confirm import confirm_token, matches


def test_token_stable_for_same_input():
    a = confirm_token("ads.budget.update", {"customer_id": "1", "amount": 5})
    b = confirm_token("ads.budget.update", {"customer_id": "1", "amount": 5})
    assert a == b
    assert len(a) == 16


def test_token_changes_with_payload():
    assert confirm_token("op", {"x": 1}) != confirm_token("op", {"x": 2})


def test_matches_true_only_for_correct_token():
    token = confirm_token("op", {"x": 1})
    assert matches("op", {"x": 1}, token)
    assert not matches("op", {"x": 1}, "wrong")
    assert not matches("op", {"x": 1}, None)
