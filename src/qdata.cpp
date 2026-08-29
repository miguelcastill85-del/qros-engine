#include "qros/qdata.hpp"
#include "qros/canonical_text.hpp"
#include "qros/sha256.hpp"

#include <algorithm>
#include <array>
#include <charconv>
#include <cstdint>
#include <fstream>
#include <limits>
#include <map>
#include <optional>
#include <stdexcept>
#include <string_view>
#include <vector>

namespace qros {
namespace {

constexpr u64 MAX_QDATA_ROWS = 1000000000000ULL;

[[noreturn]] void fail_parts(std::string_view a, std::string_view b = {}, std::string_view c = {}, std::string_view d = {}) {
    CanonicalText m(256); m.append(a); m.append(b); m.append(c); m.append(d); throw std::runtime_error(m.str_ref());
}

[[noreturn]] void fail_line(std::string_view prefix, std::size_t line, std::string_view detail) {
    CanonicalText m(256); m.append(prefix); m.append_integer(line); m.append(": "); m.append(detail); throw std::runtime_error(m.str_ref());
}

i64 parse_i64_local(std::string_view s, std::string_view name) {
    i64 v{};
    const char* b = s.data();
    const char* e = b + s.size();
    const auto [p, ec] = std::from_chars(b, e, v);
    if (ec != std::errc{} || p != e) fail_parts("invalid integer for ", name, ": ", s);
    return v;
}

u64 parse_u64_local(std::string_view s, std::string_view name) {
    u64 v{};
    const char* b = s.data();
    const char* e = b + s.size();
    const auto [p, ec] = std::from_chars(b, e, v);
    if (ec != std::errc{} || p != e) fail_parts("invalid unsigned integer for ", name, ": ", s);
    return v;
}

std::size_t parse_size_local(std::string_view s, std::string_view name) {
    const auto v = parse_u64_local(s, name);
    if (v > static_cast<u64>(std::numeric_limits<std::size_t>::max())) fail_parts(name, " exceeds size_t");
    return static_cast<std::size_t>(v);
}

int parse_int_local(std::string_view s, std::string_view name) {
    int v{};
    const char* b = s.data();
    const char* e = b + s.size();
    const auto [p, ec] = std::from_chars(b, e, v);
    if (ec != std::errc{} || p != e) fail_parts("invalid integer for ", name, ": ", s);
    return v;
}

bool parse_bool01(std::string_view s, std::string_view name) {
    if (s == "0") return false;
    if (s == "1") return true;
    fail_parts(name, " must be 0 or 1");
}

bool is_lower_hex64(std::string_view s) {
    return s.size() == 64 && std::all_of(s.begin(), s.end(), [](unsigned char c) {
        return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
    });
}

bool is_safe_id(std::string_view s, std::size_t max_len) {
    if (s.empty() || s.size() > max_len) return false;
    return std::all_of(s.begin(), s.end(), [](unsigned char c) {
        return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_' || c == '-' || c == '.' || c == ':' || c == '/';
    });
}

void strip_cr(std::string& line) {
    if (!line.empty() && line.back() == '\r') line.pop_back();
}

void hash_line_exact(Sha256Builder& hasher, const std::string& line, bool eof_after_getline) {
    hasher.update(line);
    if (!eof_after_getline) hasher.update("\n");
}

template <std::size_t N>
std::array<std::string_view, N> split_exact_views(std::string_view line) {
    std::array<std::string_view, N> out{};
    std::size_t start = 0;
    for (std::size_t i = 0; i + 1 < N; ++i) {
        const auto pos = line.find(',', start);
        if (pos == std::string_view::npos) throw std::runtime_error("wrong CSV column count");
        out[i] = line.substr(start, pos - start);
        start = pos + 1;
    }
    out[N - 1] = line.substr(start);
    if (out[N - 1].find(',') != std::string_view::npos) throw std::runtime_error("wrong CSV column count");
    for (const auto field : out) if (field.empty()) throw std::runtime_error("empty CSV field");
    return out;
}

Tick parse_tick_record(std::string_view line) {
    const auto c = split_exact_views<5>(line);
    return Tick{parse_u64_local(c[0], "seq"), parse_i64_local(c[1], "ts_ns"), parse_i64_local(c[2], "session_day"),
                parse_i64_local(c[3], "bid_u"), parse_i64_local(c[4], "ask_u")};
}

SessionBoundary parse_session_record(std::string_view line) {
    const auto c = split_exact_views<6>(line);
    return SessionBoundary{parse_i64_local(c[0], "session_day"), parse_u64_local(c[1], "open_seq"), parse_u64_local(c[2], "close_seq"),
                           parse_i64_local(c[3], "open_ts_ns"), parse_i64_local(c[4], "close_ts_ns"), parse_i64_local(c[5], "utc_offset_seconds")};
}

bool valid_yyyymmdd(i64 x) {
    if (x < 10000101 || x > 99991231) return false;
    const int y = static_cast<int>(x / 10000);
    const int m = static_cast<int>((x / 100) % 100);
    const int d = static_cast<int>(x % 100);
    if (m < 1 || m > 12 || d < 1) return false;
    static constexpr std::array<int, 12> mdays{31,28,31,30,31,30,31,31,30,31,30,31};
    int lim = mdays[static_cast<std::size_t>(m - 1)];
    const bool leap = (y % 4 == 0) && ((y % 100 != 0) || (y % 400 == 0));
    if (m == 2 && leap) lim = 29;
    return d <= lim;
}

std::optional<i64> safe_nonnegative_diff(i64 hi, i64 lo) {
    if (hi < lo) return std::nullopt;
    if (lo < 0 && hi > std::numeric_limits<i64>::max() + lo) return std::nullopt;
    return hi - lo;
}

i64 checked_add_qdata(i64 a, i64 b) {
    if ((b > 0 && a > std::numeric_limits<i64>::max() - b) || (b < 0 && a < std::numeric_limits<i64>::min() - b))
        throw std::overflow_error("fixed-point addition overflow");
    return a + b;
}

i64 checked_sub_qdata(i64 a, i64 b) {
    if (b == std::numeric_limits<i64>::min()) throw std::overflow_error("fixed-point subtraction overflow");
    return checked_add_qdata(a, -b);
}

std::size_t exact_ppm(std::size_t num, std::size_t den) {
    if (den == 0) return 0;
    if (static_cast<u64>(num) > MAX_QDATA_ROWS || static_cast<u64>(den) > MAX_QDATA_ROWS)
        throw std::overflow_error("qdata row count exceeds hard arithmetic bound");
    // MAX_QDATA_ROWS * 1,000,000 = 1e18 < UINT64_MAX, so this is exact and overflow-free.
    const u64 scaled = static_cast<u64>(num) * 1000000ULL;
    return static_cast<std::size_t>(scaled / static_cast<u64>(den));
}

i64 percentile_from_hist(const std::map<i64, u64>& hist, u64 total, unsigned pct) {
    if (hist.empty() || total == 0) return 0;
    if (total > MAX_QDATA_ROWS || pct == 0U || pct > 100U)
        throw std::overflow_error("spread percentile arithmetic bound violated");
    // total <= 1e12 and pct <= 100, therefore product <= 1e14 and is exact in uint64_t.
    const u64 rank = (total * static_cast<u64>(pct) + 99ULL) / 100ULL;
    u64 cumulative = 0;
    for (const auto& [spread, count] : hist) {
        if (count > std::numeric_limits<u64>::max() - cumulative) throw std::overflow_error("spread histogram count overflow");
        cumulative += count;
        if (cumulative >= rank) return spread;
    }
    return hist.rbegin()->first;
}

struct TickStreamingAudit {
    DataAudit base;
    std::size_t blank{};
    std::size_t nonpositive{};
    std::size_t nonpositive_timestamps{};
    std::size_t tick_size_violations{};
    std::size_t numeric_errors{};
    std::size_t membership_errors{};
    std::size_t boundary_record_errors{};
    std::size_t uncovered{};
    i64 min_spread{};
    i64 p50_spread{};
    i64 p95_spread{};
    i64 p99_spread{};
    i64 max_spread{};
    i64 max_intraday_gap_ns{};
    std::optional<Tick> first;
    std::optional<Tick> last;
};

TickStreamingAudit audit_tick_file_streaming(const std::filesystem::path& path,
                                              const std::vector<SessionBoundary>& sessions,
                                              const QDataManifest& manifest,
                                              std::string& dataset_sha256) {
    std::ifstream in(path, std::ios::binary);
    if (!in) { const auto ps = path.string(); fail_parts("cannot open ticks: ", ps); }
    Sha256Builder hasher;
    std::string line;
    if (!std::getline(in, line)) throw std::runtime_error("empty ticks file");
    hash_line_exact(hasher, line, in.eof());
    strip_cr(line);
    if (line != "seq,ts_ns,session_day,bid_u,ask_u") throw std::runtime_error("unexpected ticks header");

    TickStreamingAudit out;
    std::optional<Tick> prev;
    std::size_t session_i = 0;
    std::vector<std::uint8_t> open_seen(sessions.size(), 0U);
    std::vector<std::uint8_t> close_seen(sessions.size(), 0U);
    std::map<i64, u64> spread_hist;
    u64 spread_total = 0;
    constexpr std::size_t MAX_UNIQUE_SPREADS = 1000000;
    std::size_t lineno = 1;

    while (std::getline(in, line)) {
        ++lineno;
        if (line.size() > 4096) fail_line("ticks line ", lineno, "record exceeds 4096 bytes");
        hash_line_exact(hasher, line, in.eof());
        strip_cr(line);
        if (line.empty()) { ++out.blank; continue; }
        Tick t{};
        try { t = parse_tick_record(line); }
        catch (const std::exception& e) { fail_line("ticks line ", lineno, e.what()); }

        if (static_cast<u64>(out.base.rows) >= MAX_QDATA_ROWS)
            throw std::runtime_error("qdata row count exceeds 1e12 hard limit");
        ++out.base.rows;
        if (!out.first) out.first = t;
        out.last = t;
        if (t.ask_u == t.bid_u) ++out.base.zero_spread;
        if (t.ask_u < t.bid_u) ++out.base.crossed_market;
        if (t.bid_u <= 0 || t.ask_u <= 0) ++out.nonpositive;
        if (t.ts_ns <= 0) ++out.nonpositive_timestamps;
        if (manifest.tick_size_u > 0 && ((t.bid_u % manifest.tick_size_u) != 0 || (t.ask_u % manifest.tick_size_u) != 0)) ++out.tick_size_violations;

        if (t.ask_u >= t.bid_u) {
            const auto spread = safe_nonnegative_diff(t.ask_u, t.bid_u);
            if (!spread) {
                ++out.numeric_errors;
            } else {
                auto it = spread_hist.find(*spread);
                if (it == spread_hist.end()) {
                    if (spread_hist.size() >= MAX_UNIQUE_SPREADS) throw std::runtime_error("spread cardinality exceeds 1,000,000 unique values");
                    spread_hist.emplace(*spread, 1U);
                } else {
                    if (it->second == std::numeric_limits<u64>::max()) throw std::overflow_error("spread histogram count overflow");
                    ++it->second;
                }
                if (spread_total == std::numeric_limits<u64>::max()) throw std::overflow_error("spread total overflow");
                ++spread_total;
            }
        }

        if (prev) {
            if (t.seq <= prev->seq) ++out.base.seq_errors;
            if (t.ts_ns < prev->ts_ns) ++out.base.time_reversals;
            if (t.session_day < prev->session_day) ++out.base.day_reversals;
            if (t.ts_ns == prev->ts_ns) ++out.base.same_timestamp;
            if (t.ts_ns == prev->ts_ns && t.session_day == prev->session_day && t.bid_u == prev->bid_u && t.ask_u == prev->ask_u) ++out.base.repeated_quote_payload;
            if (t.session_day == prev->session_day && t.ts_ns >= prev->ts_ns && prev->ts_ns > 0) {
                const i64 gap = t.ts_ns - prev->ts_ns;
                if (gap > out.max_intraday_gap_ns) out.max_intraday_gap_ns = gap;
            }
        }
        prev = t;

        while (session_i < sessions.size() && t.seq > sessions[session_i].close_seq) ++session_i;
        if (session_i >= sessions.size()) {
            ++out.uncovered;
        } else {
            const auto& sb = sessions[session_i];
            if (t.seq < sb.open_seq || t.seq > sb.close_seq || t.session_day != sb.session_day || t.ts_ns < sb.open_ts_ns || t.ts_ns > sb.close_ts_ns) {
                ++out.membership_errors;
            } else {
                if (t.seq == sb.open_seq) {
                    open_seen[session_i] = 1U;
                    if (t.ts_ns != sb.open_ts_ns) ++out.boundary_record_errors;
                }
                if (t.seq == sb.close_seq) {
                    close_seen[session_i] = 1U;
                    if (t.ts_ns != sb.close_ts_ns) ++out.boundary_record_errors;
                }
            }
        }
    }
    if (!in.eof() && in.fail()) throw std::runtime_error("I/O error while reading ticks");
    for (std::size_t i = 0; i < sessions.size(); ++i) {
        if (open_seen[i] == 0U) ++out.boundary_record_errors;
        if (close_seen[i] == 0U) ++out.boundary_record_errors;
    }
    if (out.base.rows == 0) {
        out.base.pass = false;
        out.base.message = "empty dataset";
    } else {
        out.base.pass = out.base.crossed_market == 0 && out.base.seq_errors == 0 && out.base.time_reversals == 0 && out.base.day_reversals == 0;
        out.base.message = out.base.pass ? std::string_view{"PASS"} : std::string_view{"FAIL: crossed market/order/time/day invariant violated"};
    }
    if (!spread_hist.empty()) {
        out.min_spread = spread_hist.begin()->first;
        out.max_spread = spread_hist.rbegin()->first;
        out.p50_spread = percentile_from_hist(spread_hist, spread_total, 50U);
        out.p95_spread = percentile_from_hist(spread_hist, spread_total, 95U);
        out.p99_spread = percentile_from_hist(spread_hist, spread_total, 99U);
    }
    dataset_sha256 = hasher.finish();
    return out;
}

std::size_t validate_session_boundaries(const std::vector<SessionBoundary>& sessions,
                                        std::size_t& invalid_dates,
                                        std::size_t& offset_transitions,
                                        i64& max_offset_jump_seconds) {
    std::size_t errors = 0;
    invalid_dates = 0;
    offset_transitions = 0;
    max_offset_jump_seconds = 0;
    for (std::size_t i = 0; i < sessions.size(); ++i) {
        const auto& s = sessions[i];
        if (!valid_yyyymmdd(s.session_day)) ++invalid_dates;
        if (s.open_seq == 0 || s.close_seq < s.open_seq || s.open_ts_ns <= 0 || s.close_ts_ns < s.open_ts_ns) ++errors;
        if (s.utc_offset_seconds < -64800 || s.utc_offset_seconds > 64800) ++errors;
        if (i > 0) {
            const auto& p = sessions[i - 1];
            if (s.session_day <= p.session_day || s.open_seq <= p.close_seq || s.open_ts_ns < p.close_ts_ns) ++errors;
            if (s.utc_offset_seconds != p.utc_offset_seconds) {
                ++offset_transitions;
                const i64 diff = s.utc_offset_seconds >= p.utc_offset_seconds ? s.utc_offset_seconds - p.utc_offset_seconds : p.utc_offset_seconds - s.utc_offset_seconds;
                if (diff > max_offset_jump_seconds) max_offset_jump_seconds = diff;
            }
        }
    }
    return errors;
}

constexpr std::array<std::string_view, 23> MANIFEST_KEYS = {
    "authority_id", "symbol", "dataset_sha256", "sessions_sha256", "schema", "expected_rows", "first_seq", "last_seq",
    "first_ts_ns", "last_ts_ns", "price_decimals", "point_size_u", "tick_size_u", "timezone_name", "timezone_status",
    "timezone_evidence_sha256", "source_kind", "source_id", "source_evidence_sha256", "purpose", "session_policy_id", "max_zero_spread_ppm", "allow_nonpositive_prices"
};

std::size_t manifest_key_index(std::string_view key) {
    const auto it = std::find(MANIFEST_KEYS.begin(), MANIFEST_KEYS.end(), key);
    if (it == MANIFEST_KEYS.end()) return MANIFEST_KEYS.size();
    return static_cast<std::size_t>(it - MANIFEST_KEYS.begin());
}

void read_manifest_hashed(const std::filesystem::path& path, QDataManifest& m, std::string& manifest_sha256) {
    std::ifstream in(path, std::ios::binary);
    if (!in) { const auto ps = path.string(); fail_parts("cannot open qdata manifest: ", ps); }
    Sha256Builder hasher;
    std::array<std::string, MANIFEST_KEYS.size()> values{};
    std::array<std::uint8_t, MANIFEST_KEYS.size()> seen{};
    std::size_t total_bytes = 0;
    std::string line;
    if (!std::getline(in, line)) throw std::runtime_error("empty qdata manifest");
    if (line.size() > 8192) throw std::runtime_error("qdata manifest header exceeds 8192 bytes");
    hash_line_exact(hasher, line, in.eof());
    total_bytes += line.size() + (in.eof() ? 0U : 1U);
    strip_cr(line);
    if (line != "QROS_QDATA_MANIFEST_V1") throw std::runtime_error("qdata manifest magic/version mismatch");

    std::size_t lineno = 1;
    while (std::getline(in, line)) {
        ++lineno;
        if (line.size() > 8192) fail_line("manifest line ", lineno, "line exceeds 8192 bytes");
        const std::size_t add = line.size() + (in.eof() ? 0U : 1U);
        if (add > (1U << 20) || total_bytes > (1U << 20) - add) throw std::runtime_error("qdata manifest exceeds 1 MiB hard limit");
        total_bytes += add;
        hash_line_exact(hasher, line, in.eof());
        strip_cr(line);
        if (line.empty() || line[0] == '#') continue;
        const auto p = line.find('=');
        if (p == std::string::npos || p == 0 || p + 1 >= line.size()) fail_line("manifest line ", lineno, "invalid key/value syntax");
        const std::string_view k(line.data(), p);
        const std::string_view v(line.data() + static_cast<std::ptrdiff_t>(p + 1), line.size() - p - 1);
        const auto idx = manifest_key_index(k);
        if (idx == MANIFEST_KEYS.size()) fail_parts("unknown qdata manifest key: ", k);
        if (seen[idx] != 0U) fail_parts("duplicate qdata manifest key: ", k);
        seen[idx] = 1U;
        values[idx].assign(v.data(), v.size());
    }
    if (!in.eof() && in.fail()) throw std::runtime_error("I/O error while reading qdata manifest");
    for (std::size_t i = 0; i < seen.size(); ++i) if (seen[i] == 0U) fail_parts("missing qdata manifest key: ", MANIFEST_KEYS[i]);
    manifest_sha256 = hasher.finish();

    const auto value_of = [&](std::string_view key) -> const std::string& {
        const auto idx = manifest_key_index(key);
        if (idx >= values.size()) throw std::logic_error("internal manifest key lookup failure");
        return values[idx];
    };
    m.authority_id = value_of("authority_id");
    m.symbol = value_of("symbol");
    m.dataset_sha256 = value_of("dataset_sha256");
    m.sessions_sha256 = value_of("sessions_sha256");
    m.schema = value_of("schema");
    m.expected_rows = parse_size_local(value_of("expected_rows"), "expected_rows");
    m.first_seq = parse_u64_local(value_of("first_seq"), "first_seq");
    m.last_seq = parse_u64_local(value_of("last_seq"), "last_seq");
    m.first_ts_ns = parse_i64_local(value_of("first_ts_ns"), "first_ts_ns");
    m.last_ts_ns = parse_i64_local(value_of("last_ts_ns"), "last_ts_ns");
    m.price_decimals = parse_int_local(value_of("price_decimals"), "price_decimals");
    m.point_size_u = parse_i64_local(value_of("point_size_u"), "point_size_u");
    m.tick_size_u = parse_i64_local(value_of("tick_size_u"), "tick_size_u");
    m.timezone_name = value_of("timezone_name");
    const auto& tz_status = value_of("timezone_status");
    if (tz_status == "VERIFIED") m.timezone_status = VerificationStatus::Verified;
    else if (tz_status == "TEST_ONLY") m.timezone_status = VerificationStatus::TestOnly;
    else if (tz_status == "UNVERIFIED") m.timezone_status = VerificationStatus::Unverified;
    else throw std::runtime_error("timezone_status must be VERIFIED, TEST_ONLY, or UNVERIFIED");
    m.timezone_evidence_sha256 = value_of("timezone_evidence_sha256");
    m.source_kind = value_of("source_kind");
    m.source_id = value_of("source_id");
    m.source_evidence_sha256 = value_of("source_evidence_sha256");
    const auto& purpose = value_of("purpose");
    if (purpose == "RESEARCH") m.purpose = QDataPurpose::Research;
    else if (purpose == "TEST_ONLY") m.purpose = QDataPurpose::TestOnly;
    else throw std::runtime_error("purpose must be RESEARCH or TEST_ONLY");
    m.session_policy_id = value_of("session_policy_id");
    m.max_zero_spread_ppm = parse_u64_local(value_of("max_zero_spread_ppm"), "max_zero_spread_ppm");
    m.allow_nonpositive_prices = parse_bool01(value_of("allow_nonpositive_prices"), "allow_nonpositive_prices");

    if (!is_safe_id(m.authority_id, 128) || !is_safe_id(m.symbol, 64) || !is_safe_id(m.source_kind, 64) || !is_safe_id(m.source_id, 256) || !is_safe_id(m.session_policy_id, 128))
        throw std::runtime_error("qdata manifest contains unsafe/invalid identifier");
    if (!is_lower_hex64(m.dataset_sha256) || !is_lower_hex64(m.sessions_sha256) || !is_lower_hex64(m.timezone_evidence_sha256) || !is_lower_hex64(m.source_evidence_sha256))
        throw std::runtime_error("qdata manifest SHA-256 fields must be 64 lowercase hex chars");
    if (m.schema != "TICKS_CSV_V1") throw std::runtime_error("unsupported qdata schema");
    if (m.expected_rows == 0 || static_cast<u64>(m.expected_rows) > MAX_QDATA_ROWS || m.first_seq == 0 || m.last_seq < m.first_seq || m.first_ts_ns <= 0 || m.last_ts_ns < m.first_ts_ns)
        throw std::runtime_error("invalid qdata extents");
    if (m.price_decimals < 0 || m.price_decimals > 12 || m.point_size_u <= 0 || m.tick_size_u <= 0) throw std::runtime_error("invalid qdata price units");
    if ((m.point_size_u % m.tick_size_u) != 0 && (m.tick_size_u % m.point_size_u) != 0) throw std::runtime_error("point_size_u and tick_size_u are not integer-compatible");
    if (m.timezone_name.empty() || m.timezone_name.size() > 128) throw std::runtime_error("invalid timezone_name");
    if (m.max_zero_spread_ppm > 1000000ULL) throw std::runtime_error("max_zero_spread_ppm exceeds 1,000,000");
}


template <std::size_t N>
std::array<std::string, N> read_closed_kv_hashed(const std::filesystem::path& path,
                                                 std::string_view magic,
                                                 const std::array<std::string_view, N>& keys,
                                                 std::string& file_sha256) {
    std::ifstream in(path, std::ios::binary);
    if (!in) { const auto ps = path.string(); fail_parts("cannot open evidence: ", ps); }
    Sha256Builder hasher;
    std::array<std::string, N> values{};
    std::array<std::uint8_t, N> seen{};
    std::size_t total_bytes = 0;
    std::string line;
    if (!std::getline(in, line)) throw std::runtime_error("empty evidence file");
    hash_line_exact(hasher, line, in.eof());
    total_bytes += line.size() + (in.eof() ? 0U : 1U);
    strip_cr(line);
    if (line != magic) throw std::runtime_error("evidence magic/version mismatch");
    std::size_t lineno = 1;
    while (std::getline(in, line)) {
        ++lineno;
        if (line.size() > 8192) fail_line("evidence line ", lineno, "line exceeds 8192 bytes");
        const std::size_t add = line.size() + (in.eof() ? 0U : 1U);
        if (add > (1U << 20) || total_bytes > (1U << 20) - add) throw std::runtime_error("evidence file exceeds 1 MiB hard limit");
        total_bytes += add;
        hash_line_exact(hasher, line, in.eof());
        strip_cr(line);
        if (line.empty() || line[0] == '#') continue;
        const auto pos = line.find('=');
        if (pos == std::string::npos || pos == 0 || pos + 1 >= line.size()) fail_line("evidence line ", lineno, "invalid key/value syntax");
        const std::string_view key(line.data(), pos);
        const std::string_view value(line.data() + static_cast<std::ptrdiff_t>(pos + 1), line.size() - pos - 1);
        const auto it = std::find(keys.begin(), keys.end(), key);
        if (it == keys.end()) fail_parts("unknown evidence key: ", key);
        const auto idx = static_cast<std::size_t>(it - keys.begin());
        if (seen[idx] != 0U) fail_parts("duplicate evidence key: ", key);
        seen[idx] = 1U;
        values[idx].assign(value.data(), value.size());
    }
    if (!in.eof() && in.fail()) throw std::runtime_error("I/O error while reading evidence");
    for (std::size_t i = 0; i < N; ++i) if (seen[i] == 0U) fail_parts("missing evidence key: ", keys[i]);
    file_sha256 = hasher.finish();
    return values;
}

VerificationStatus parse_verification_status(std::string_view x, std::string_view field) {
    if (x == "VERIFIED") return VerificationStatus::Verified;
    if (x == "TEST_ONLY") return VerificationStatus::TestOnly;
    if (x == "UNVERIFIED") return VerificationStatus::Unverified;
    fail_parts(field, " must be VERIFIED, TEST_ONLY, or UNVERIFIED");
}

struct TimezoneEvidenceRecord {
    std::string authority_id;
    std::string timezone_name;
    std::string method;
    i64 coverage_first_day{};
    i64 coverage_last_day{};
    std::string sessions_sha256;
    std::size_t observed_offset_transitions{};
    i64 max_offset_jump_seconds{};
    VerificationStatus status{VerificationStatus::Unverified};
};

TimezoneEvidenceRecord read_timezone_evidence_record(const std::filesystem::path& path, std::string& file_sha256) {
    static constexpr std::array<std::string_view,9> keys{
        "authority_id","timezone_name","method","coverage_first_day","coverage_last_day","sessions_sha256",
        "observed_offset_transitions","max_offset_jump_seconds","status"};
    const auto v = read_closed_kv_hashed(path, "QROS_TIMEZONE_EVIDENCE_V1", keys, file_sha256);
    TimezoneEvidenceRecord e;
    e.authority_id=v[0]; e.timezone_name=v[1]; e.method=v[2];
    e.coverage_first_day=parse_i64_local(v[3],"coverage_first_day");
    e.coverage_last_day=parse_i64_local(v[4],"coverage_last_day");
    e.sessions_sha256=v[5];
    e.observed_offset_transitions=parse_size_local(v[6],"observed_offset_transitions");
    e.max_offset_jump_seconds=parse_i64_local(v[7],"max_offset_jump_seconds");
    e.status=parse_verification_status(v[8],"timezone evidence status");
    if (!is_safe_id(e.authority_id,128) || !is_safe_id(e.timezone_name,128) || !is_safe_id(e.method,128))
        throw std::runtime_error("timezone evidence contains unsafe/invalid identifier");
    if (!valid_yyyymmdd(e.coverage_first_day) || !valid_yyyymmdd(e.coverage_last_day) || e.coverage_last_day < e.coverage_first_day)
        throw std::runtime_error("invalid timezone evidence coverage");
    if (!is_lower_hex64(e.sessions_sha256) || e.max_offset_jump_seconds < 0 || e.max_offset_jump_seconds > 129600)
        throw std::runtime_error("invalid timezone evidence values");
    return e;
}

struct SourceEvidenceRecord {
    std::string authority_id;
    std::string source_kind;
    std::string source_id;
    std::string method;
    std::string dataset_sha256;
    std::string sessions_sha256;
    VerificationStatus status{VerificationStatus::Unverified};
};

SourceEvidenceRecord read_source_evidence_record(const std::filesystem::path& path, std::string& file_sha256) {
    static constexpr std::array<std::string_view,7> keys{
        "authority_id","source_kind","source_id","method","dataset_sha256","sessions_sha256","status"};
    const auto v = read_closed_kv_hashed(path, "QROS_SOURCE_EVIDENCE_V1", keys, file_sha256);
    SourceEvidenceRecord e;
    e.authority_id=v[0]; e.source_kind=v[1]; e.source_id=v[2]; e.method=v[3]; e.dataset_sha256=v[4]; e.sessions_sha256=v[5];
    e.status=parse_verification_status(v[6],"source evidence status");
    if (!is_safe_id(e.authority_id,128) || !is_safe_id(e.source_kind,64) || !is_safe_id(e.source_id,256) || !is_safe_id(e.method,128))
        throw std::runtime_error("source evidence contains unsafe/invalid identifier");
    if (!is_lower_hex64(e.dataset_sha256) || !is_lower_hex64(e.sessions_sha256)) throw std::runtime_error("invalid source evidence hashes");
    return e;
}

void read_session_map_hashed(const std::filesystem::path& path,
                             std::vector<SessionBoundary>& rows,
                             std::size_t& blanks,
                             std::string& sessions_sha256) {
    std::ifstream in(path, std::ios::binary);
    if (!in) { const auto ps = path.string(); fail_parts("cannot open session map: ", ps); }
    Sha256Builder hasher;
    std::string line;
    if (!std::getline(in, line)) throw std::runtime_error("empty session map");
    hash_line_exact(hasher, line, in.eof());
    strip_cr(line);
    if (line != "session_day,open_seq,close_seq,open_ts_ns,close_ts_ns,utc_offset_seconds") throw std::runtime_error("unexpected session map header");
    rows.clear();
    blanks = 0;
    std::size_t lineno = 1;
    while (std::getline(in, line)) {
        ++lineno;
        if (line.size() > 4096) fail_line("sessions line ", lineno, "record exceeds 4096 bytes");
        hash_line_exact(hasher, line, in.eof());
        strip_cr(line);
        if (line.empty()) { ++blanks; continue; }
        try { rows.push_back(parse_session_record(line)); }
        catch (const std::exception& e) { fail_line("sessions line ", lineno, e.what()); }
    }
    if (!in.eof() && in.fail()) throw std::runtime_error("I/O error while reading session map");
    if (rows.empty()) throw std::runtime_error("session map has no sessions");
    sessions_sha256 = hasher.finish();
}

} // namespace

std::string_view verification_status_name(VerificationStatus status) {
    switch (status) {
        case VerificationStatus::Verified: return "VERIFIED";
        case VerificationStatus::TestOnly: return "TEST_ONLY";
        case VerificationStatus::Unverified: return "UNVERIFIED";
    }
    return "UNVERIFIED";
}

std::string_view qdata_purpose_name(QDataPurpose purpose) {
    switch (purpose) {
        case QDataPurpose::Research: return "RESEARCH";
        case QDataPurpose::TestOnly: return "TEST_ONLY";
    }
    return "TEST_ONLY";
}

QDataManifest read_qdata_manifest(const std::filesystem::path& path) {
    QDataManifest m;
    std::string ignored_hash;
    read_manifest_hashed(path, m, ignored_hash);
    return m;
}

std::vector<SessionBoundary> read_session_map_csv(const std::filesystem::path& path, std::size_t* blank_records) {
    std::vector<SessionBoundary> rows;
    std::size_t blanks = 0;
    std::string ignored_hash;
    read_session_map_hashed(path, rows, blanks, ignored_hash);
    if (blank_records != nullptr) *blank_records = blanks;
    return rows;
}

QDataAudit audit_qdata_authority(const std::filesystem::path& ticks_path,
                                 const std::filesystem::path& sessions_path,
                                 const std::filesystem::path& manifest_path,
                                 const std::filesystem::path& timezone_evidence_path,
                                 const std::filesystem::path& source_evidence_path) {
    QDataManifest manifest;
    QDataAudit a;
    read_manifest_hashed(manifest_path, manifest, a.manifest_sha256);
    std::string timezone_evidence_sha;
    std::string source_evidence_sha;
    const auto timezone_evidence = read_timezone_evidence_record(timezone_evidence_path, timezone_evidence_sha);
    const auto source_evidence = read_source_evidence_record(source_evidence_path, source_evidence_sha);
    a.timezone_evidence_hash_match = timezone_evidence_sha == manifest.timezone_evidence_sha256;
    a.source_evidence_hash_match = source_evidence_sha == manifest.source_evidence_sha256;

    std::vector<SessionBoundary> sessions;
    read_session_map_hashed(sessions_path, sessions, a.blank_session_records, a.sessions_sha256);
    a.sessions = sessions.size();
    a.sessions_hash_match = a.sessions_sha256 == manifest.sessions_sha256;
    a.first_session_day = sessions.front().session_day;
    a.last_session_day = sessions.back().session_day;
    a.session_boundary_errors = validate_session_boundaries(sessions, a.invalid_session_dates, a.session_offset_transitions, a.max_offset_jump_seconds);

    std::string dataset_sha;
    const auto stream = audit_tick_file_streaming(ticks_path, sessions, manifest, dataset_sha);
    a.dataset_sha256 = dataset_sha;
    a.dataset_hash_match = a.dataset_sha256 == manifest.dataset_sha256;
    a.ticks = stream.base;
    a.blank_tick_records = stream.blank;
    a.nonpositive_quotes = stream.nonpositive;
    a.nonpositive_timestamps = stream.nonpositive_timestamps;
    a.tick_size_violations = stream.tick_size_violations;
    a.numeric_errors = stream.numeric_errors;
    a.session_membership_errors = stream.membership_errors;
    a.session_boundary_errors += stream.boundary_record_errors;
    a.uncovered_ticks = stream.uncovered;
    a.min_spread_u = stream.min_spread;
    a.p50_spread_u = stream.p50_spread;
    a.p95_spread_u = stream.p95_spread;
    a.p99_spread_u = stream.p99_spread;
    a.max_spread_u = stream.max_spread;
    a.max_intraday_gap_ns = stream.max_intraday_gap_ns;
    a.row_count_match = stream.base.rows == manifest.expected_rows;
    a.extent_match = stream.first.has_value() && stream.last.has_value() &&
                     stream.first->seq == manifest.first_seq && stream.last->seq == manifest.last_seq &&
                     stream.first->ts_ns == manifest.first_ts_ns && stream.last->ts_ns == manifest.last_ts_ns;
    a.zero_spread_ppm = exact_ppm(stream.base.zero_spread, stream.base.rows);

    const std::string zero_hash(64, '0');
    a.timezone_evidence_bound = manifest.timezone_evidence_sha256 != zero_hash;
    a.timezone_evidence_semantic_match =
        timezone_evidence.authority_id == manifest.authority_id &&
        timezone_evidence.timezone_name == manifest.timezone_name &&
        timezone_evidence.sessions_sha256 == a.sessions_sha256 &&
        timezone_evidence.coverage_first_day == a.first_session_day &&
        timezone_evidence.coverage_last_day == a.last_session_day &&
        timezone_evidence.observed_offset_transitions == a.session_offset_transitions &&
        timezone_evidence.max_offset_jump_seconds == a.max_offset_jump_seconds &&
        timezone_evidence.status == manifest.timezone_status;
    a.source_evidence_semantic_match =
        source_evidence.authority_id == manifest.authority_id &&
        source_evidence.source_kind == manifest.source_kind &&
        source_evidence.source_id == manifest.source_id &&
        source_evidence.dataset_sha256 == a.dataset_sha256 &&
        source_evidence.sessions_sha256 == a.sessions_sha256;

    const bool timezone_method_synthetic = timezone_evidence.method.starts_with("SYNTHETIC");
    const bool source_method_synthetic = source_evidence.method.starts_with("SYNTHETIC");
    a.timezone_research_verified = manifest.timezone_status == VerificationStatus::Verified &&
        timezone_evidence.status == VerificationStatus::Verified && a.timezone_evidence_bound &&
        a.timezone_evidence_hash_match && a.timezone_evidence_semantic_match && !timezone_method_synthetic;
    a.source_research_verified = source_evidence.status == VerificationStatus::Verified &&
        a.source_evidence_hash_match && a.source_evidence_semantic_match && !source_method_synthetic && manifest.source_kind != "SYNTHETIC_TEST";
    // Fail-closed in v0.3: structured evidence integrity is implemented, but an independent
    // production verifier against raw broker/vendor bytes is not yet implemented.
    a.production_evidence_verifier_available = false;

    const bool nonpositive_ok = manifest.allow_nonpositive_prices || a.nonpositive_quotes == 0;
    const bool zero_spread_ok = a.zero_spread_ppm <= manifest.max_zero_spread_ppm;
    a.pass_integrity = a.dataset_hash_match && a.sessions_hash_match && a.ticks.pass && a.row_count_match && a.extent_match &&
                       a.blank_tick_records == 0 && a.blank_session_records == 0 && a.tick_size_violations == 0 && a.numeric_errors == 0 &&
                       a.nonpositive_timestamps == 0 && a.session_boundary_errors == 0 && a.session_membership_errors == 0 &&
                       a.invalid_session_dates == 0 && a.uncovered_ticks == 0 && nonpositive_ok && zero_spread_ok &&
                       a.timezone_evidence_hash_match && a.source_evidence_hash_match &&
                       a.timezone_evidence_semantic_match && a.source_evidence_semantic_match;
    const bool test_evidence_ok = manifest.timezone_status == VerificationStatus::TestOnly &&
        timezone_evidence.status == VerificationStatus::TestOnly && source_evidence.status == VerificationStatus::TestOnly;
    a.test_ready = a.pass_integrity && manifest.purpose == QDataPurpose::TestOnly && test_evidence_ok;
    a.research_ready = a.pass_integrity && manifest.purpose == QDataPurpose::Research &&
                       a.timezone_research_verified && a.source_research_verified && a.production_evidence_verifier_available;
    if (a.research_ready) a.message = "RESEARCH_READY";
    else if (a.test_ready) a.message = "TEST_READY";
    else if (a.pass_integrity && manifest.purpose == QDataPurpose::Research && !a.production_evidence_verifier_available)
        a.message = "INTEGRITY_PASS_PRODUCTION_EVIDENCE_VERIFIER_NOT_IMPLEMENTED";
    else if (a.pass_integrity) a.message = "INTEGRITY_PASS_EVIDENCE_NOT_READY_FOR_DECLARED_PURPOSE";
    else a.message = "FAIL_INTEGRITY";
    return a;
}

Trade replay_qdata_stream_bound(const std::filesystem::path& ticks_path,
                                const std::string& expected_dataset_sha256,
                                const Intent& intent) {
    if (!is_lower_hex64(expected_dataset_sha256)) throw std::runtime_error("expected_dataset_sha256 must be 64 lowercase hex chars");

    Trade tr;
    tr.side = intent.side;
    if (intent.stop_distance_u <= 0 || intent.target_distance_u <= 0 || intent.session_close_seq <= intent.signal_seq) {
        tr.reason = ExitReason::DataError;
        return tr;
    }

    std::ifstream in(ticks_path, std::ios::binary);
    if (!in) { const auto ps = ticks_path.string(); fail_parts("cannot open ticks: ", ps); }
    Sha256Builder hasher;
    std::string line;
    if (!std::getline(in, line)) throw std::runtime_error("empty ticks file");
    hash_line_exact(hasher, line, in.eof());
    strip_cr(line);
    if (line != "seq,ts_ns,session_day,bid_u,ask_u") throw std::runtime_error("unexpected ticks header");

    bool invalid = false;
    bool signal_seen = false;
    bool close_seen = false;
    bool terminal = false;
    bool have_last_exec = false;
    Tick last_exec{};
    std::optional<Tick> prev;
    i64 stop = 0;
    i64 target = 0;
    std::size_t lineno = 1;

    while (std::getline(in, line)) {
        ++lineno;
        if (line.size() > 4096) fail_line("ticks line ", lineno, "record exceeds 4096 bytes");
        hash_line_exact(hasher, line, in.eof());
        strip_cr(line);
        if (line.empty()) fail_line("ticks line ", lineno, "blank record forbidden in authoritative replay");
        Tick t{};
        try { t = parse_tick_record(line); }
        catch (const std::exception& e) { fail_line("ticks line ", lineno, e.what()); }

        if (prev) {
            if (t.seq <= prev->seq || t.ts_ns < prev->ts_ns || t.session_day < prev->session_day) invalid = true;
        }
        if (t.ask_u < t.bid_u || t.ts_ns <= 0) invalid = true;
        prev = t;

        if (t.seq == intent.signal_seq) {
            if (signal_seen) invalid = true;
            signal_seen = true;
            if (t.ts_ns != intent.signal_ts_ns || t.session_day != intent.signal_session_day) invalid = true;
        }

        if (signal_seen && !close_seen && t.seq > intent.signal_seq && t.seq <= intent.session_close_seq) {
            if (t.session_day != intent.signal_session_day) invalid = true;

            if (!tr.entered && !terminal && t.ts_ns >= intent.signal_ts_ns && t.ask_u > t.bid_u) {
                tr.entered = true;
                tr.entry_seq = t.seq;
                tr.entry_ts_ns = t.ts_ns;
                tr.entry_day = t.session_day;
                tr.entry_price_u = intent.side == Side::Buy ? t.ask_u : t.bid_u;
                try {
                    stop = intent.side == Side::Buy ? checked_sub_qdata(tr.entry_price_u, intent.stop_distance_u)
                                                    : checked_add_qdata(tr.entry_price_u, intent.stop_distance_u);
                    target = intent.side == Side::Buy ? checked_add_qdata(tr.entry_price_u, intent.target_distance_u)
                                                      : checked_sub_qdata(tr.entry_price_u, intent.target_distance_u);
                } catch (const std::overflow_error&) {
                    invalid = true;
                    terminal = true;
                    tr.entered = false;
                    tr.reason = ExitReason::DataError;
                }
            } else if (tr.entered && !terminal && t.seq > tr.entry_seq && t.ask_u > t.bid_u) {
                have_last_exec = true;
                last_exec = t;
                if (intent.side == Side::Buy) {
                    // SL first on each observed tick; gap executes at first observed Bid.
                    if (t.bid_u <= stop) {
                        tr.exit_seq = t.seq; tr.exit_ts_ns = t.ts_ns; tr.exit_price_u = t.bid_u; tr.reason = ExitReason::StopLoss;
                        tr.pnl_u = checked_sub_qdata(tr.exit_price_u, tr.entry_price_u); tr.r_num = tr.pnl_u; tr.r_den = intent.stop_distance_u; terminal = true;
                    } else if (t.bid_u >= target) {
                        tr.exit_seq = t.seq; tr.exit_ts_ns = t.ts_ns; tr.exit_price_u = t.bid_u; tr.reason = ExitReason::TakeProfit;
                        tr.pnl_u = checked_sub_qdata(tr.exit_price_u, tr.entry_price_u); tr.r_num = tr.pnl_u; tr.r_den = intent.stop_distance_u; terminal = true;
                    }
                } else {
                    if (t.ask_u >= stop) {
                        tr.exit_seq = t.seq; tr.exit_ts_ns = t.ts_ns; tr.exit_price_u = t.ask_u; tr.reason = ExitReason::StopLoss;
                        tr.pnl_u = checked_sub_qdata(tr.entry_price_u, tr.exit_price_u); tr.r_num = tr.pnl_u; tr.r_den = intent.stop_distance_u; terminal = true;
                    } else if (t.ask_u <= target) {
                        tr.exit_seq = t.seq; tr.exit_ts_ns = t.ts_ns; tr.exit_price_u = t.ask_u; tr.reason = ExitReason::TakeProfit;
                        tr.pnl_u = checked_sub_qdata(tr.entry_price_u, tr.exit_price_u); tr.r_num = tr.pnl_u; tr.r_den = intent.stop_distance_u; terminal = true;
                    }
                }
            }
        }

        if (t.seq == intent.session_close_seq) {
            if (close_seen) invalid = true;
            close_seen = true;
            if (!signal_seen || t.session_day != intent.signal_session_day) invalid = true;
            if (!terminal) {
                if (!tr.entered) {
                    tr.reason = ExitReason::NoEntry;
                } else if (!have_last_exec) {
                    tr.reason = ExitReason::UnresolvedClose;
                } else {
                    tr.exit_seq = last_exec.seq;
                    tr.exit_ts_ns = last_exec.ts_ns;
                    tr.exit_price_u = intent.side == Side::Buy ? last_exec.bid_u : last_exec.ask_u;
                    tr.reason = ExitReason::SessionClose;
                    tr.pnl_u = intent.side == Side::Buy ? checked_sub_qdata(tr.exit_price_u, tr.entry_price_u)
                                                        : checked_sub_qdata(tr.entry_price_u, tr.exit_price_u);
                    tr.r_num = tr.pnl_u;
                    tr.r_den = intent.stop_distance_u;
                }
                terminal = true;
            }
        }
    }
    if (!in.eof() && in.fail()) throw std::runtime_error("I/O error while reading authoritative ticks");
    const auto actual_sha = hasher.finish();
    if (actual_sha != expected_dataset_sha256) throw std::runtime_error("DATA_AUTHORITY_HASH_MISMATCH");

    if (!signal_seen || !close_seen || invalid) {
        Trade bad;
        bad.side = intent.side;
        bad.reason = ExitReason::DataError;
        return bad;
    }
    return tr;
}

std::string qdata_audit_receipt(const QDataManifest& manifest, const QDataAudit& a) {
    CanonicalText o(2048);
#define QROS_KV_TEXT(key, value) do { o.append(key); o.append(value); o.append('\n'); } while(0)
#define QROS_KV_INT(key, value) do { o.append(key); o.append_integer(value); o.append('\n'); } while(0)
#define QROS_KV_BOOL(key, value) do { o.append(key); o.append_bool01(value); o.append('\n'); } while(0)
    o.append("QROS_QDATA_AUDIT_RECEIPT_V1\n");
    QROS_KV_TEXT("authority_id=", manifest.authority_id);
    QROS_KV_TEXT("symbol=", manifest.symbol);
    QROS_KV_TEXT("source_kind=", manifest.source_kind);
    QROS_KV_TEXT("source_id=", manifest.source_id);
    QROS_KV_TEXT("timezone_name=", manifest.timezone_name);
    QROS_KV_TEXT("session_policy_id=", manifest.session_policy_id);
    QROS_KV_TEXT("dataset_sha256=", a.dataset_sha256);
    QROS_KV_TEXT("sessions_sha256=", a.sessions_sha256);
    QROS_KV_TEXT("manifest_sha256=", a.manifest_sha256);
    QROS_KV_INT("rows=", a.ticks.rows);
    QROS_KV_INT("sessions=", a.sessions);
    QROS_KV_INT("first_session_day=", a.first_session_day);
    QROS_KV_INT("last_session_day=", a.last_session_day);
    QROS_KV_INT("zero_spread=", a.ticks.zero_spread);
    QROS_KV_INT("zero_spread_ppm=", a.zero_spread_ppm);
    QROS_KV_INT("min_spread_u=", a.min_spread_u);
    QROS_KV_INT("p50_spread_u=", a.p50_spread_u);
    QROS_KV_INT("p95_spread_u=", a.p95_spread_u);
    QROS_KV_INT("p99_spread_u=", a.p99_spread_u);
    QROS_KV_INT("max_spread_u=", a.max_spread_u);
    QROS_KV_INT("max_intraday_gap_ns=", a.max_intraday_gap_ns);
    QROS_KV_INT("crossed_market=", a.ticks.crossed_market);
    QROS_KV_INT("nonpositive_quotes=", a.nonpositive_quotes);
    QROS_KV_INT("nonpositive_timestamps=", a.nonpositive_timestamps);
    QROS_KV_INT("seq_errors=", a.ticks.seq_errors);
    QROS_KV_INT("time_reversals=", a.ticks.time_reversals);
    QROS_KV_INT("day_reversals=", a.ticks.day_reversals);
    QROS_KV_INT("same_timestamp=", a.ticks.same_timestamp);
    QROS_KV_INT("repeated_quote_payload=", a.ticks.repeated_quote_payload);
    QROS_KV_INT("tick_size_violations=", a.tick_size_violations);
    QROS_KV_INT("numeric_errors=", a.numeric_errors);
    QROS_KV_INT("session_boundary_errors=", a.session_boundary_errors);
    QROS_KV_INT("session_membership_errors=", a.session_membership_errors);
    QROS_KV_INT("invalid_session_dates=", a.invalid_session_dates);
    QROS_KV_INT("session_offset_transitions=", a.session_offset_transitions);
    QROS_KV_INT("max_offset_jump_seconds=", a.max_offset_jump_seconds);
    QROS_KV_INT("uncovered_ticks=", a.uncovered_ticks);
    QROS_KV_INT("blank_tick_records=", a.blank_tick_records);
    QROS_KV_INT("blank_session_records=", a.blank_session_records);
    QROS_KV_BOOL("dataset_hash_match=", a.dataset_hash_match);
    QROS_KV_BOOL("sessions_hash_match=", a.sessions_hash_match);
    QROS_KV_BOOL("row_count_match=", a.row_count_match);
    QROS_KV_BOOL("extent_match=", a.extent_match);
    QROS_KV_TEXT("purpose=", qdata_purpose_name(manifest.purpose));
    QROS_KV_TEXT("timezone_status=", verification_status_name(manifest.timezone_status));
    QROS_KV_BOOL("timezone_evidence_bound=", a.timezone_evidence_bound);
    QROS_KV_BOOL("timezone_evidence_hash_match=", a.timezone_evidence_hash_match);
    QROS_KV_BOOL("source_evidence_hash_match=", a.source_evidence_hash_match);
    QROS_KV_BOOL("timezone_evidence_semantic_match=", a.timezone_evidence_semantic_match);
    QROS_KV_BOOL("source_evidence_semantic_match=", a.source_evidence_semantic_match);
    QROS_KV_BOOL("timezone_research_verified=", a.timezone_research_verified);
    QROS_KV_BOOL("source_research_verified=", a.source_research_verified);
    QROS_KV_BOOL("production_evidence_verifier_available=", a.production_evidence_verifier_available);
    QROS_KV_BOOL("pass_integrity=", a.pass_integrity);
    QROS_KV_BOOL("test_ready=", a.test_ready);
    QROS_KV_BOOL("research_ready=", a.research_ready);
    QROS_KV_TEXT("status=", a.message);
#undef QROS_KV_TEXT
#undef QROS_KV_INT
#undef QROS_KV_BOOL
    return std::move(o).take();
}

std::string_view event_phase_contract_v1() {
    return "QROS_EVENT_PHASE_CONTRACT_V1\n"
           "10=MARKET_DATA_ACCEPTED\n"
           "20=FEATURE_STATE_UPDATED\n"
           "30=SIGNAL_COMMITTED\n"
           "40=ORDER_INTENT_COMMITTED\n"
           "50=NEXT_RECORD_EXECUTION_ELIGIBLE\n"
           "60=POSITION_MANAGEMENT\n"
           "70=SESSION_SETTLEMENT\n"
           "INVARIANT=NO_ENTRY_ON_SIGNAL_RECORD\n"
           "INVARIANT=SEQ_IS_PRIMARY_CAUSAL_ORDER\n"
           "INVARIANT=TIMESTAMP_MAY_TIE_BUT_MAY_NOT_REVERSE\n";
}

std::string_view execution_policy_v1() {
    return "QROS_EXECUTION_POLICY_V1\n"
           "BUY_ENTRY=ASK\n"
           "BUY_EXIT=BID\n"
           "SELL_ENTRY=BID\n"
           "SELL_EXIT=ASK\n"
           "ENTRY=STRICTLY_AFTER_SIGNAL_SEQ\n"
           "ZERO_SPREAD_FILL=FORBIDDEN\n"
           "CROSSED_MARKET=DATA_ERROR\n"
           "GAP_FILL=FIRST_OBSERVED_EXECUTABLE_QUOTE\n"
           "AMBIGUOUS_SL_TP=SL_FIRST\n"
           "SESSION_CLOSE=LAST_EXECUTABLE_QUOTE_AT_OR_BEFORE_AUTH_CLOSE_AFTER_ENTRY\n"
           "EOF_IS_SESSION_CLOSE=FALSE\n";
}

} // namespace qros
