"""Independent, deliberately slow batch oracle for TEST_ONLY native pipeline fixtures.

Bars are grouped offline, then only the previous closed group is exposed at each
record. Stateful operators are evaluated on distinct input versions. No C++
binary, generated IR, native ledger or native feature output is read here.
"""
from __future__ import annotations
from collections import defaultdict
from itertools import product

def trunc_div(a: int, b: int) -> int:
    return (abs(a) // abs(b)) * (-1 if (a < 0) != (b < 0) else 1)

def variants(program: dict[str, str]):
    axes = sorted(k[5:] for k in program if k.startswith("axis."))
    values = [[int(v) for v in program["axis." + name].split(",")] for name in axes]
    for birth, selected in enumerate(product(*values)):
        parameters = dict(zip(axes, selected))
        resolve = lambda text: str(parameters[text[1:]]) if text.startswith("$") else text
        cfg = {k: resolve(v) for k, v in program.items() if not k.startswith(("axis.", "node.", "require."))}
        cfg["nodes"] = {k[5:]: [resolve(t) if t.startswith("$") else t for t in v.split(":")]
                        for k, v in program.items() if k.startswith("node.")}
        cfg["birth"] = birth
        cfg["eligible"] = True
        for k, expr in program.items():
            if k.startswith("require."):
                op, left, right = expr.split(":")
                a, b = int(resolve(left)), int(resolve(right))
                cfg["eligible"] &= {"LT": a < b, "LE": a <= b, "NE": a != b, "EQ": a == b}[op]
        yield cfg

def feature_table(cfg, ticks):
    cache = {}
    order = []
    def column(name):
        if name in cache:
            return cache[name]
        op, *args = cfg["nodes"][name]
        if op in {"BID", "ASK", "SPREAD"}:
            result = [((t["bid_u"] if op == "BID" else t["ask_u"] if op == "ASK" else t["ask_u"] - t["bid_u"]), t["seq"]) for t in ticks]
        elif op == "CONST":
            result = [(int(args[0]), 1)] * len(ticks)
        elif op in {"OPEN", "HIGH", "LOW", "CLOSE"}:
            period = int(args[0]) * 1_000_000
            groups = []
            for t in ticks:
                key = t["session_day"], t["ts_ns"] // period
                if not groups or groups[-1][0] != key:
                    groups.append((key, []))
                groups[-1][1].append(t)
            result = []
            previous = None
            for _, rows in groups:
                if previous is None:
                    result.extend([(None, 0)] * len(rows))
                else:
                    prices = [r["bid_u"] for r in previous]
                    value = {"OPEN": prices[0], "HIGH": max(prices), "LOW": min(prices), "CLOSE": prices[-1]}[op]
                    result.extend([(value, previous[-1]["seq"])] * len(rows))
                previous = rows
        else:
            left = column(args[0])
            right = column(args[1]) if op in {"ADD", "SUB", "MIN", "MAX", "GT", "GE", "LT", "LE", "EQ", "AND", "OR", "CROSS_UP", "CROSS_DOWN"} else None
            last_version, previous, result, samples = 0, None, [], []
            cached = (None, 0)
            ema = None
            for i, (a, av) in enumerate(left):
                b, bv = right[i] if right else (0, 0)
                version = max(av, bv)
                if a is None or (right is not None and b is None):
                    result.append((None, version))
                    continue
                if version == last_version:
                    result.append(cached)
                    continue
                last_version = version
                if op in {"LAG", "EMA", "HIGHEST", "LOWEST"}:
                    n = int(args[1])
                    samples.append(a)
                    if op == "LAG":
                        value = samples[-n-1] if len(samples) > n else None
                    elif op == "EMA":
                        ema = a if ema is None else ema + trunc_div(2 * (a - ema), n + 1)
                        value = ema if len(samples) >= n else None
                    elif len(samples) < n:
                        value = None
                    else:
                        value = max(samples[-n:]) if op == "HIGHEST" else min(samples[-n:])
                elif op.startswith("CROSS_"):
                    if previous is None:
                        value = None
                    elif op == "CROSS_UP":
                        value = int(previous[0] <= previous[1] and a > b)
                    else:
                        value = int(previous[0] >= previous[1] and a < b)
                    previous = a, b
                else:
                    value = {"ADD": lambda: a+b, "SUB": lambda: a-b, "MIN": lambda: min(a,b), "MAX": lambda: max(a,b),
                             "GT": lambda: int(a>b), "GE": lambda: int(a>=b), "LT": lambda: int(a<b), "LE": lambda: int(a<=b),
                             "EQ": lambda: int(a==b), "AND": lambda: int(bool(a) and bool(b)), "OR": lambda: int(bool(a) or bool(b)),
                             "NOT": lambda: int(not a)}[op]()
                cached = value, version
                result.append(cached)
        cache[name] = result
        order.append(name)
        return result
    column(cfg["signal"])
    return order, cache

def backtest(cfg, ticks, sessions):
    _, features = feature_table(cfg, ticks)
    signals = features[cfg["signal"]]
    close_by_day = {s["session_day"]: s["close_seq"] for s in sessions}
    buy = cfg["side"] in {"BUY", "1"}
    sign = 1 if buy else -1
    risk, target = int(cfg["stop_u"]), int(cfg["target_u"])
    slip, fee = int(cfg["slippage_u"]), int(cfg["commission_u"])
    be, be_offset, trail = int(cfg["be_trigger_ppm"]), int(cfg["be_offset_u"]), int(cfg["trailing_u"])
    day, daily, last_bar = None, 0, None
    pending, position, last_exec = None, None, None
    signal_version, signal_truth = 0, False
    trades, unresolved = [], 0
    def close(t, reason):
        nonlocal position, last_exec
        exit_u = (t["bid_u"] if buy else t["ask_u"]) - sign * slip
        pnl = sign * (exit_u - position["entry_price_u"])
        trades.append(dict(birth=cfg["birth"], symbol=cfg["symbol"], side="BUY" if buy else "SELL",
                           entry_seq=position["entry_seq"], entry_ts_ns=position["entry_ts_ns"], entry_day=day,
                           entry_price_u=position["entry_price_u"], exit_seq=t["seq"], exit_ts_ns=t["ts_ns"],
                           exit_price_u=exit_u, exit_reason=reason, gross_u=pnl, net_u=pnl-fee, commission_u=fee,
                           risk_u=risk, mae_u=position["mae"], mfe_u=position["mfe"], bar_ms=int(cfg["bar_ms"])))
        position, last_exec = None, None
    for t, (signal, version) in zip(ticks, signals):
        if t["session_day"] != day:
            if position is not None:
                raise AssertionError("oracle overnight")
            day, daily, last_bar, pending = t["session_day"], 0, None, None
        bar = t["ts_ns"] // (int(cfg["bar_ms"]) * 1_000_000)
        executable = t["ask_u"] > t["bid_u"]
        if position is not None and t["seq"] > position["entry_seq"] and executable:
            last_exec = t
            price = t["bid_u"] if buy else t["ask_u"]
            favorable = sign * (price - position["entry_price_u"])
            position["mae"] = min(position["mae"], favorable)
            position["mfe"] = max(position["mfe"], favorable)
            if sign * (price - position["stop"]) <= 0:
                close(t, "SL")
            elif sign * (price - position["target"]) >= 0:
                close(t, "TP")
            else:
                position["best"] = max(position["best"], price) if buy else min(position["best"], price)
                if be and favorable > 0 and favorable * 1_000_000 >= target * be:
                    level = position["entry_price_u"] + sign * be_offset
                    position["stop"] = max(position["stop"], level) if buy else min(position["stop"], level)
                if trail:
                    level = position["best"] - sign * trail
                    position["stop"] = max(position["stop"], level) if buy else min(position["stop"], level)
        if t["seq"] == close_by_day[day]:
            if position is not None:
                if last_exec is None:
                    unresolved += 1
                    position = None
                else:
                    close(last_exec, "SESSION_CLOSE")
            pending = None
            signal_version, signal_truth = version, signal is not None and signal != 0
            continue
        if pending is not None and t["seq"] > pending["seq"]:
            pending["age"] += 1
            if pending["age"] > int(cfg["expiry_records"]):
                pending = None
            elif position is None and executable and daily < int(cfg["daily_limit"]) and bar != last_bar:
                entry = (t["ask_u"] if buy else t["bid_u"]) + sign * slip
                position = dict(entry_seq=t["seq"], entry_ts_ns=t["ts_ns"], entry_price_u=entry,
                                stop=entry-sign*risk, target=entry+sign*target, best=entry, mae=0, mfe=0)
                daily += 1
                last_bar, pending, last_exec = bar, None, None
        if version != signal_version:
            truth = signal is not None and signal != 0
            trigger = truth and (cfg["signal_mode"] == "EACH_UPDATE" or not signal_truth)
            if trigger and position is None and pending is None and daily < int(cfg["daily_limit"]) and bar != last_bar:
                pending = dict(seq=t["seq"], age=0)
            signal_version, signal_truth = version, truth
    if position or pending:
        raise AssertionError("oracle missing final session")
    return trades, unresolved
