from qros_failed_auction_edge_score_v1 import *

def run():
    fast_reject = QFAESInputs(
        side="SELL", atr=10.0, level=2500.0, extreme=2501.5,
        outbound_start_price=2499.9,
        first_out_ms=0, extreme_ms=30_000, reclaim_ms=70_000,
        current_spread=0.20, rolling_positive_spread_p50=0.25,
        recent_mid_prices=[2501.50,2501.45,2501.40,2501.30,2501.20,2501.10,2501.00,2500.80,2500.50,2500.20,2499.95]
    )
    slow_accepted = QFAESInputs(
        side="SELL", atr=10.0, level=2500.0, extreme=2504.8,
        outbound_start_price=2499.9,
        first_out_ms=0, extreme_ms=420_000, reclaim_ms=1_150_000,
        current_spread=0.50, rolling_positive_spread_p50=0.25,
        recent_mid_prices=[2504.2,2504.3,2504.4,2504.5,2504.6,2504.7,2504.8,2504.7,2504.6,2504.5]
    )
    a = score_qfaes(fast_reject)
    b = score_qfaes(slow_accepted)
    assert 0 <= a.score <= 100
    assert 0 <= b.score <= 100
    assert a.score > b.score, (a, b)

    stop, target, risk = stop_and_target("SELL", entry=2499.9, extreme=2501.5, atr=10.0)
    assert stop > 2501.5
    assert target < 2499.9
    assert risk > 0

    assert target_before_stop("BUY", 99.0, 101.0, [(100.0,100.1),(101.0,101.1)]) == 1
    assert target_before_stop("SELL", 101.0, 99.0, [(99.9,100.0),(98.9,99.0)]) == 1
    print("QFAES_SYNTHETIC_UNIT_TESTS=PASS")
    print(f"FAST_REJECT_SCORE={a.score:.6f}")
    print(f"SLOW_ACCEPTED_SCORE={b.score:.6f}")

if __name__ == "__main__":
    run()
