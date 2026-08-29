#include "qros/core.hpp"
#include "qros/canonical_text.hpp"
#include "qros/sha256.hpp"

#include <algorithm>
#include <array>
#include <atomic>
#include <cerrno>
#include <charconv>
#include <cstring>
#include <fstream>
#include <limits>
#include <map>
#include <stdexcept>
#include <system_error>

#if defined(__unix__) || defined(__APPLE__)
#include <fcntl.h>
#include <unistd.h>
#endif

namespace qros {
namespace {

[[noreturn]] void fail_parts(std::string_view a, std::string_view b = {}, std::string_view c = {}, std::string_view d = {}) {
    CanonicalText m(256); m.append(a); m.append(b); m.append(c); m.append(d); throw std::runtime_error(m.str_ref());
}

[[noreturn]] void fail_line(std::string_view prefix, std::size_t line, std::string_view detail) {
    CanonicalText m(256); m.append(prefix); m.append_integer(line); m.append(": " ); m.append(detail); throw std::runtime_error(m.str_ref());
}

i64 parse_i64(const std::string& s, const char* name) {
    i64 v{};
    const char* b = s.data();
    const char* e = b + s.size();
    auto [p, ec] = std::from_chars(b, e, v);
    if (ec != std::errc{} || p != e) fail_parts("invalid integer for ", name, ": ", s);
    return v;
}

u64 parse_u64(const std::string& s, const char* name) {
    u64 v{};
    const char* b = s.data();
    const char* e = b + s.size();
    auto [p, ec] = std::from_chars(b, e, v);
    if (ec != std::errc{} || p != e) fail_parts("invalid unsigned integer for ", name, ": ", s);
    return v;
}

std::vector<std::string> split_csv5(const std::string& line) {
    std::vector<std::string> out;
    std::size_t start = 0;
    for (int i = 0; i < 4; ++i) {
        auto pos = line.find(',', start);
        if (pos == std::string::npos) throw std::runtime_error("expected 5 CSV columns");
        out.push_back(line.substr(start, pos - start));
        start = pos + 1;
    }
    out.push_back(line.substr(start));
    return out;
}

std::string_view side_name(Side s) { return s == Side::Buy ? std::string_view{"BUY"} : std::string_view{"SELL"}; }

bool is_safe_strategy_id(const std::string& s) {
    if (s.empty() || s.size() > 128) return false;
    return std::all_of(s.begin(), s.end(), [](unsigned char c) {
        return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_' || c == '-' || c == '.' || c == ':';
    });
}

i64 checked_add(i64 a, i64 b) {
    if ((b > 0 && a > std::numeric_limits<i64>::max() - b) || (b < 0 && a < std::numeric_limits<i64>::min() - b))
        throw std::overflow_error("fixed-point addition overflow");
    return a + b;
}
i64 checked_sub(i64 a, i64 b) {
    if (b == std::numeric_limits<i64>::min()) throw std::overflow_error("fixed-point subtraction overflow");
    return checked_add(a, -b);
}

} // namespace

DataAudit audit_ticks(const std::vector<Tick>& ticks) {
    DataAudit a;
    a.rows = ticks.size();
    if (ticks.empty()) {
        a.pass = false;
        a.message = "empty dataset";
        return a;
    }
    for (std::size_t i = 0; i < ticks.size(); ++i) {
        const auto& t = ticks[i];
        if (t.ask_u == t.bid_u) ++a.zero_spread;
        if (t.ask_u < t.bid_u) ++a.crossed_market;
        if (i > 0) {
            const auto& p = ticks[i - 1];
            if (t.seq <= p.seq) ++a.seq_errors;
            if (t.ts_ns < p.ts_ns) ++a.time_reversals;
            if (t.session_day < p.session_day) ++a.day_reversals;
            if (t.ts_ns == p.ts_ns) ++a.same_timestamp;
            if (t.ts_ns == p.ts_ns && t.session_day == p.session_day && t.bid_u == p.bid_u && t.ask_u == p.ask_u) ++a.repeated_quote_payload;
        }
    }
    // Zero spread is audited but not fatal; such ticks can never be used for fills.
    a.pass = a.crossed_market == 0 && a.seq_errors == 0 && a.time_reversals == 0 && a.day_reversals == 0;
    a.message = a.pass ? "PASS" : "FAIL: crossed market/order/time/day invariant violated";
    return a;
}

Trade replay_market_after_signal(const std::vector<Tick>& ticks, const Intent& intent) {
    try {
    Trade tr;
    tr.side = intent.side;
    if (intent.stop_distance_u <= 0 || intent.target_distance_u <= 0) {
        tr.reason = ExitReason::DataError;
        return tr;
    }
    const auto audit = audit_ticks(ticks);
    if (!audit.pass) {
        tr.reason = ExitReason::DataError;
        return tr;
    }

    // Bind causal boundaries to actual authoritative records, not merely numeric claims.
    std::optional<std::size_t> signal_i;
    std::optional<std::size_t> close_i;
    for (std::size_t i = 0; i < ticks.size(); ++i) {
        if (ticks[i].seq == intent.signal_seq) signal_i = i;
        if (ticks[i].seq == intent.session_close_seq) close_i = i;
    }
    if (!signal_i || !close_i || intent.session_close_seq <= intent.signal_seq) {
        tr.reason = ExitReason::DataError;
        return tr;
    }
    const auto& signal_tick = ticks[*signal_i];
    const auto& close_tick = ticks[*close_i];
    if (signal_tick.ts_ns != intent.signal_ts_ns || signal_tick.session_day != intent.signal_session_day ||
        close_tick.session_day != intent.signal_session_day || *close_i <= *signal_i) {
        tr.reason = ExitReason::DataError;
        return tr;
    }

    std::optional<std::size_t> entry_i;
    for (std::size_t i = *signal_i + 1; i <= *close_i; ++i) {
        const auto& t = ticks[i];
        // Causality: entry must occur strictly AFTER the exact signal record and no later than the authoritative session close.
        // No fill is permitted on zero spread or crossed quotes.
        if (t.session_day == intent.signal_session_day && t.seq > intent.signal_seq && t.ts_ns >= intent.signal_ts_ns && t.ask_u > t.bid_u) {
            entry_i = i;
            tr.entered = true;
            tr.entry_seq = t.seq;
            tr.entry_ts_ns = t.ts_ns;
            tr.entry_day = t.session_day;
            tr.entry_price_u = intent.side == Side::Buy ? t.ask_u : t.bid_u;
            break;
        }
    }
    if (!entry_i) {
        tr.reason = ExitReason::NoEntry;
        return tr;
    }

    i64 stop{}, target{};
    try {
        stop = intent.side == Side::Buy ? checked_sub(tr.entry_price_u, intent.stop_distance_u)
                                        : checked_add(tr.entry_price_u, intent.stop_distance_u);
        target = intent.side == Side::Buy ? checked_add(tr.entry_price_u, intent.target_distance_u)
                                          : checked_sub(tr.entry_price_u, intent.target_distance_u);
    } catch (const std::overflow_error&) {
        tr.reason = ExitReason::DataError; tr.entered = false; return tr;
    }

    std::optional<std::size_t> last_exec_i;
    for (std::size_t i = *entry_i + 1; i <= *close_i; ++i) {
        const auto& t = ticks[i];
        if (t.session_day != tr.entry_day) { tr.reason = ExitReason::DataError; return tr; }
        if (t.ask_u <= t.bid_u) continue; // never execute on zero/crossed spread
        last_exec_i = i;

        if (intent.side == Side::Buy) {
            // BUY exits on observed Bid. Tick-level gap execution uses first available Bid.
            if (t.bid_u <= stop) {
                tr.exit_seq = t.seq; tr.exit_ts_ns = t.ts_ns; tr.exit_price_u = t.bid_u; tr.reason = ExitReason::StopLoss;
                tr.pnl_u = checked_sub(tr.exit_price_u, tr.entry_price_u); tr.r_num=tr.pnl_u; tr.r_den=intent.stop_distance_u; return tr;
            }
            if (t.bid_u >= target) {
                tr.exit_seq = t.seq; tr.exit_ts_ns = t.ts_ns; tr.exit_price_u = t.bid_u; tr.reason = ExitReason::TakeProfit;
                tr.pnl_u = checked_sub(tr.exit_price_u, tr.entry_price_u); tr.r_num=tr.pnl_u; tr.r_den=intent.stop_distance_u; return tr;
            }
        } else {
            // SELL exits on observed Ask.
            if (t.ask_u >= stop) {
                tr.exit_seq = t.seq; tr.exit_ts_ns = t.ts_ns; tr.exit_price_u = t.ask_u; tr.reason = ExitReason::StopLoss;
                tr.pnl_u = checked_sub(tr.entry_price_u, tr.exit_price_u); tr.r_num=tr.pnl_u; tr.r_den=intent.stop_distance_u; return tr;
            }
            if (t.ask_u <= target) {
                tr.exit_seq = t.seq; tr.exit_ts_ns = t.ts_ns; tr.exit_price_u = t.ask_u; tr.reason = ExitReason::TakeProfit;
                tr.pnl_u = checked_sub(tr.entry_price_u, tr.exit_price_u); tr.r_num=tr.pnl_u; tr.r_den=intent.stop_distance_u; return tr;
            }
        }
    }

    // Mandatory same-day close requires an actually observed executable quote AFTER entry.
    // We never fabricate an immediate same-tick round trip if the session has no later executable quote.
    if (!last_exec_i) {
        tr.reason = ExitReason::UnresolvedClose;
        return tr;
    }
    const auto& t = ticks[*last_exec_i];
    tr.exit_seq = t.seq;
    tr.exit_ts_ns = t.ts_ns;
    tr.exit_price_u = intent.side == Side::Buy ? t.bid_u : t.ask_u;
    tr.reason = ExitReason::SessionClose;
    tr.pnl_u = intent.side == Side::Buy ? checked_sub(tr.exit_price_u, tr.entry_price_u) : checked_sub(tr.entry_price_u, tr.exit_price_u);
    tr.r_num=tr.pnl_u; tr.r_den=intent.stop_distance_u;
    return tr;
    } catch (const std::overflow_error&) {
        Trade error; error.side=intent.side; error.reason=ExitReason::DataError; return error;
    }
}

std::vector<Tick> read_ticks_csv(const std::filesystem::path& path) {
    std::ifstream in(path);
    if (!in) { const auto ps=path.string(); fail_parts("cannot open ticks: ", ps); }
    std::string line;
    if (!std::getline(in, line)) throw std::runtime_error("empty ticks file");
    if (line != "seq,ts_ns,session_day,bid_u,ask_u") throw std::runtime_error("unexpected ticks header");
    std::vector<Tick> out;
    std::size_t lineno = 1;
    while (std::getline(in, line)) {
        ++lineno;
        if (line.empty()) continue;
        auto c = split_csv5(line);
        try {
            out.push_back(Tick{parse_u64(c[0], "seq"), parse_i64(c[1], "ts_ns"), parse_i64(c[2], "session_day"),
                               parse_i64(c[3], "bid_u"), parse_i64(c[4], "ask_u")});
        } catch (const std::exception& e) {
            fail_line("ticks line ", lineno, e.what());
        }
    }
    return out;
}

std::vector<Tick> read_ticks_csv_bound(const std::filesystem::path& path, const std::string& expected_sha256) {
    if (expected_sha256.size() != 64 || !std::all_of(expected_sha256.begin(), expected_sha256.end(), [](unsigned char c){
            return (c>='0'&&c<='9')||(c>='a'&&c<='f');
        })) throw std::runtime_error("expected_sha256 must be 64 lowercase hex chars");
    std::ifstream in(path, std::ios::binary);
    if (!in) { const auto ps=path.string(); fail_parts("cannot open ticks: ", ps); }
    Sha256Builder hasher;
    std::string line;
    if (!std::getline(in, line)) throw std::runtime_error("empty ticks file");
    {
        const std::string raw = line;
        hasher.update(raw);
        if (!in.eof()) hasher.update("\n");
    }
    if (!line.empty() && line.back()=='\r') line.pop_back();
    if (line != "seq,ts_ns,session_day,bid_u,ask_u") throw std::runtime_error("unexpected ticks header");
    std::vector<Tick> out;
    std::size_t lineno = 1;
    while (std::getline(in, line)) {
        ++lineno;
        {
            const std::string raw = line;
            hasher.update(raw);
            if (!in.eof()) hasher.update("\n");
        }
        if (!line.empty() && line.back()=='\r') line.pop_back();
        if (line.empty()) fail_line("ticks line ", lineno, "blank record forbidden in authoritative replay");
        auto c = split_csv5(line);
        try {
            out.push_back(Tick{parse_u64(c[0], "seq"), parse_i64(c[1], "ts_ns"), parse_i64(c[2], "session_day"),
                               parse_i64(c[3], "bid_u"), parse_i64(c[4], "ask_u")});
        } catch (const std::exception& e) {
            fail_line("ticks line ", lineno, e.what());
        }
    }
    if (!in.eof() && in.fail()) throw std::runtime_error("I/O error while reading authoritative ticks");
    const auto actual_sha = hasher.finish();
    if (actual_sha != expected_sha256) throw std::runtime_error("DATA_AUTHORITY_HASH_MISMATCH");
    return out;
}

Intent read_intent(const std::filesystem::path& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) { const auto ps=path.string(); fail_parts("cannot open intent: ", ps); }
    std::string line;
    if (!std::getline(in, line)) throw std::runtime_error("empty intent");
    if (!line.empty() && line.back()=='\r') line.pop_back();
    const bool v2 = line == "QROS_INTENT_V2";
    if (!v2 && line != "QROS_INTENT_V1") throw std::runtime_error("intent magic/version mismatch");

    const std::array<std::string_view, 9> allowed_v1 = {
        "strategy_id", "data_sha256", "side", "signal_seq", "signal_ts_ns", "signal_session_day", "session_close_seq", "stop_distance_u", "target_distance_u"
    };
    const std::array<std::string_view, 13> allowed_v2 = {
        "strategy_id", "data_sha256", "side", "signal_seq", "signal_ts_ns", "signal_session_day", "session_close_seq", "stop_distance_u", "target_distance_u",
        "qdata_manifest_sha256", "sessions_sha256", "event_contract_sha256", "execution_policy_sha256"
    };
    std::map<std::string, std::string> kv;
    std::size_t lineno = 1;
    while (std::getline(in, line)) {
        ++lineno;
        if (!line.empty() && line.back()=='\r') line.pop_back();
        if (line.empty() || line[0] == '#') continue;
        auto p = line.find('=');
        if (p == std::string::npos || p == 0 || p + 1 >= line.size()) { CanonicalText m; m.append("invalid intent line "); m.append_integer(lineno); throw std::runtime_error(m.str_ref()); }
        auto k = line.substr(0, p), v = line.substr(p + 1);
        const bool allowed = v2 ? (std::find(allowed_v2.begin(), allowed_v2.end(), std::string_view(k)) != allowed_v2.end())
                                : (std::find(allowed_v1.begin(), allowed_v1.end(), std::string_view(k)) != allowed_v1.end());
        if (!allowed) fail_parts("unknown intent key: ", k);
        if (!kv.emplace(k, v).second) fail_parts("duplicate intent key: ", k);
    }
    if (v2) {
        for (const auto k : allowed_v2) if (!kv.contains(std::string(k))) fail_parts("missing intent key: ", k);
    } else {
        for (const auto k : allowed_v1) if (!kv.contains(std::string(k))) fail_parts("missing intent key: ", k);
    }

    const auto valid_hash = [](const std::string& h) {
        return h.size()==64 && std::all_of(h.begin(),h.end(),[](unsigned char c){return (c>='0'&&c<='9')||(c>='a'&&c<='f');});
    };
    Intent x;
    x.strategy_id = kv.at("strategy_id");
    x.data_sha256 = kv.at("data_sha256");
    if (!is_safe_strategy_id(x.strategy_id)) throw std::runtime_error("strategy_id contains unsafe characters or invalid length");
    if (!valid_hash(x.data_sha256)) throw std::runtime_error("data_sha256 must be 64 lowercase hex chars");
    if (kv.at("side") == "BUY") x.side = Side::Buy;
    else if (kv.at("side") == "SELL") x.side = Side::Sell;
    else throw std::runtime_error("side must be BUY or SELL");
    x.signal_seq = parse_u64(kv.at("signal_seq"), "signal_seq");
    x.signal_ts_ns = parse_i64(kv.at("signal_ts_ns"), "signal_ts_ns");
    x.signal_session_day = parse_i64(kv.at("signal_session_day"), "signal_session_day");
    x.session_close_seq = parse_u64(kv.at("session_close_seq"), "session_close_seq");
    x.stop_distance_u = parse_i64(kv.at("stop_distance_u"), "stop_distance_u");
    x.target_distance_u = parse_i64(kv.at("target_distance_u"), "target_distance_u");
    if (x.stop_distance_u <= 0 || x.target_distance_u <= 0) throw std::runtime_error("distances must be > 0");
    if (v2) {
        x.qdata_manifest_sha256 = kv.at("qdata_manifest_sha256");
        x.sessions_sha256 = kv.at("sessions_sha256");
        x.event_contract_sha256 = kv.at("event_contract_sha256");
        x.execution_policy_sha256 = kv.at("execution_policy_sha256");
        if (!valid_hash(x.qdata_manifest_sha256) || !valid_hash(x.sessions_sha256) || !valid_hash(x.event_contract_sha256) || !valid_hash(x.execution_policy_sha256))
            throw std::runtime_error("intent v2 authority/contract hashes must be 64 lowercase hex chars");
    }
    return x;
}

std::string_view exit_reason_name(ExitReason r) {
    switch (r) {
        case ExitReason::TakeProfit: return "TP";
        case ExitReason::StopLoss: return "SL";
        case ExitReason::SessionClose: return "SESSION_CLOSE";
        case ExitReason::NoEntry: return "NO_ENTRY";
        case ExitReason::UnresolvedClose: return "UNRESOLVED_CLOSE";
        case ExitReason::DataError: return "DATA_ERROR";
    }
    return "UNKNOWN";
}

std::string_view trade_csv_header() {
    return "strategy_id,entered,side,entry_seq,entry_ts_ns,entry_day,entry_price_u,exit_seq,exit_ts_ns,exit_price_u,exit_reason,pnl_u,r_num,r_den\n";
}

std::string trade_csv_row(const std::string& strategy_id, const Trade& t) {
    CanonicalText o(256);
    o.append(strategy_id); o.append(',');
    o.append_bool01(t.entered); o.append(',');
    o.append(side_name(t.side)); o.append(',');
    o.append_integer(t.entry_seq); o.append(',');
    o.append_integer(t.entry_ts_ns); o.append(',');
    o.append_integer(t.entry_day); o.append(',');
    o.append_integer(t.entry_price_u); o.append(',');
    o.append_integer(t.exit_seq); o.append(',');
    o.append_integer(t.exit_ts_ns); o.append(',');
    o.append_integer(t.exit_price_u); o.append(',');
    o.append(exit_reason_name(t.reason)); o.append(',');
    o.append_integer(t.pnl_u); o.append(',');
    o.append_integer(t.r_num); o.append(',');
    o.append_integer(t.r_den); o.append('\n');
    return std::move(o).take();
}

void atomic_write_text(const std::filesystem::path& out, const std::string& data) {
    const auto dir = out.has_parent_path() ? out.parent_path() : std::filesystem::path(".");
    std::filesystem::create_directories(dir);
#if defined(__unix__) || defined(__APPLE__)
    static std::atomic<unsigned long long> nonce{0};
    CanonicalText suffix(64); suffix.append(".tmp."); suffix.append_integer(static_cast<unsigned long long>(::getpid())); suffix.append('.'); suffix.append_integer(nonce.fetch_add(1));
    auto tmp = out; tmp += suffix.str_ref();
    int fd = ::open(tmp.c_str(), O_WRONLY | O_CREAT | O_EXCL, 0644);
    if (fd < 0) fail_parts("open temp failed: ", std::strerror(errno));
    std::size_t off = 0;
    while (off < data.size()) {
        auto n = ::write(fd, data.data() + off, data.size() - off);
        if (n < 0) { int e = errno; ::close(fd); ::unlink(tmp.c_str()); fail_parts("write failed: ", std::strerror(e)); }
        off += static_cast<std::size_t>(n);
    }
    if (::fsync(fd) != 0) { int e = errno; ::close(fd); ::unlink(tmp.c_str()); fail_parts("fsync failed: ", std::strerror(e)); }
    if (::close(fd) != 0) { ::unlink(tmp.c_str()); throw std::runtime_error("close temp failed"); }
    // Hard-link promotion is atomic and NEVER overwrites an existing final path.
    if (::link(tmp.c_str(), out.c_str()) != 0) {
        const int e = errno;
        if (e == EEXIST) {
            std::ifstream existing(out, std::ios::binary | std::ios::ate);
            bool same = false;
            if (existing) {
                const auto end = existing.tellg();
                if (end >= 0 && static_cast<std::uintmax_t>(end) == static_cast<std::uintmax_t>(data.size())) {
                    existing.seekg(0, std::ios::beg);
                    std::string buf(data.size(), '\0');
                    if (data.empty() || existing.read(buf.data(), static_cast<std::streamsize>(buf.size()))) same = (buf == data);
                }
            }
            ::unlink(tmp.c_str());
            if (same) return; // idempotent rerun
            throw std::runtime_error("immutable output conflict: final path already exists with different bytes");
        }
        ::unlink(tmp.c_str());
        fail_parts("atomic link promotion failed: ", std::strerror(e));
    }
    ::unlink(tmp.c_str());
    int dfd = ::open(dir.c_str(), O_RDONLY | O_DIRECTORY);
    if (dfd >= 0) { (void)::fsync(dfd); (void)::close(dfd); }
#else
    if (std::filesystem::exists(out)) throw std::runtime_error("immutable output conflict: final path exists");
    auto tmp = out; tmp += ".tmp";
    std::ofstream f(tmp, std::ios::binary | std::ios::trunc);
    if (!f) throw std::runtime_error("cannot open temp output");
    f.write(data.data(), static_cast<std::streamsize>(data.size()));
    f.flush(); f.close();
    std::filesystem::rename(tmp, out);
#endif
}

} // namespace qros
