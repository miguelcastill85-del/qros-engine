#pragma once
#include <cstdint>
#include <filesystem>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace qros {

using i64 = std::int64_t;
using u64 = std::uint64_t;

enum class Side { Buy, Sell };
enum class ExitReason { TakeProfit, StopLoss, SessionClose, NoEntry, UnresolvedClose, DataError };

struct Tick {
    u64 seq{};          // authoritative order; strictly increasing
    i64 ts_ns{};        // source timestamp; nondecreasing, timezone is external metadata
    i64 session_day{};  // explicit broker/session day identifier; no timezone assumption here
    i64 bid_u{};        // fixed-point integer price units
    i64 ask_u{};
};

struct DataAudit {
    std::size_t rows{};
    std::size_t zero_spread{};
    std::size_t crossed_market{};
    std::size_t seq_errors{};
    std::size_t time_reversals{};
    std::size_t day_reversals{};
    std::size_t same_timestamp{};
    std::size_t repeated_quote_payload{};
    bool pass{};
    std::string_view message;
};

struct Intent {
    std::string strategy_id;
    std::string data_sha256; // binds intent to exact authoritative input bytes
    Side side{Side::Buy};
    u64 signal_seq{};      // authoritative causal boundary
    i64 signal_ts_ns{};
    i64 signal_session_day{};
    u64 session_close_seq{}; // authoritative inclusive close boundary for this session
    i64 stop_distance_u{};
    i64 target_distance_u{};
    std::string qdata_manifest_sha256; // v2 authority binding; empty for legacy v1
    std::string sessions_sha256;       // v2 authority binding; empty for legacy v1
    std::string event_contract_sha256; // v2 semantic binding; empty for legacy v1
    std::string execution_policy_sha256; // v2 semantic binding; empty for legacy v1

    Intent() = default;
    Intent(std::string strategy_id_, std::string data_sha256_, Side side_, u64 signal_seq_, i64 signal_ts_ns_,
           i64 signal_session_day_, u64 session_close_seq_, i64 stop_distance_u_, i64 target_distance_u_)
        : strategy_id(std::move(strategy_id_)), data_sha256(std::move(data_sha256_)), side(side_), signal_seq(signal_seq_),
          signal_ts_ns(signal_ts_ns_), signal_session_day(signal_session_day_), session_close_seq(session_close_seq_),
          stop_distance_u(stop_distance_u_), target_distance_u(target_distance_u_) {}
};

struct Trade {
    bool entered{};
    Side side{Side::Buy};
    u64 entry_seq{};
    i64 entry_ts_ns{};
    i64 entry_day{};
    i64 entry_price_u{};
    u64 exit_seq{};
    i64 exit_ts_ns{};
    i64 exit_price_u{};
    ExitReason reason{ExitReason::NoEntry};
    i64 pnl_u{}; // signed fixed-point movement, not USD
    i64 r_num{}; // exact R = r_num / r_den; no floating point required
    i64 r_den{};
};

DataAudit audit_ticks(const std::vector<Tick>& ticks);
Trade replay_market_after_signal(const std::vector<Tick>& ticks, const Intent& intent);
std::vector<Tick> read_ticks_csv(const std::filesystem::path& path);
std::vector<Tick> read_ticks_csv_bound(const std::filesystem::path& path, const std::string& expected_sha256);
Intent read_intent(const std::filesystem::path& path);
std::string_view trade_csv_header();
std::string trade_csv_row(const std::string& strategy_id, const Trade& t);
std::string_view exit_reason_name(ExitReason r);
void atomic_write_text(const std::filesystem::path& out, const std::string& data);

} // namespace qros
