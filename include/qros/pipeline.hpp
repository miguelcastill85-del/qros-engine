#pragma once

#include "qros/core.hpp"
#include "qros/qdata.hpp"
#include <deque>
#include <functional>
#include <map>
#include <memory>
#include <set>
#include <string>
#include <vector>

namespace qros::pipeline {
using Fields = std::map<std::string, std::string>;
constexpr std::size_t text_limit = 8U * 1024U * 1024U;

[[noreturn]] void fail(const std::string& message);
i64 integer(const std::string& text);
u64 natural(const std::string& text);
i64 add(i64 a, i64 b);
i64 sub(i64 a, i64 b);
i64 mul(i64 a, i64 b);
bool hash_valid(const std::string& text);
bool identifier(const std::string& text);
std::vector<std::string> split(const std::string& text, char separator);
Fields parse_fields(const std::string& text, const std::string& magic);
Fields read_fields(const std::filesystem::path& path, const std::string& magic,
                   const std::string& expected_hash = "");
std::string fields_text(const std::string& magic, const Fields& fields);
void exact_keys(const Fields& fields, const std::set<std::string>& keys);
std::filesystem::path safe_relative(const std::filesystem::path& root, const std::string& name);
void require_regular_path(const std::filesystem::path& path);
std::string bounded_text(const std::filesystem::path& path, std::size_t limit = text_limit);
std::string number(long double value);

struct DataSpec {
    Fields fields;
    std::filesystem::path root;
    std::string sha256;
    std::string authority_id, symbol, purpose, format, source_clock, exposure;
    std::string ticks_name, ticks_sha, sessions_name, sessions_sha;
    u64 rows{}, first_seq{};
    i64 first_day{}, last_day{}, tick_size_u{}, point_size_u{}, price_decimals{};
    std::vector<SessionBoundary> sessions;
};
struct DataReceipt {
    u64 rows{}, zero_spread{}, crossed{}, repeated{}, same_timestamp{};
    u64 first_seq{}, last_seq{};
    i64 first_ts{}, last_ts{};
    std::string ticks_sha, sessions_sha, contract_root;
    bool executable{};
};
DataSpec read_data_spec(const std::filesystem::path& path, const std::string& expected_sha);
DataReceipt walk_data(const DataSpec& spec,
                      const std::function<void(const Tick&, const SessionBoundary&)>& visit,
                      bool require_executable, u64 max_rows);
std::string data_receipt(const DataSpec& spec, const DataReceipt& receipt);
std::string verify_conversion(const std::filesystem::path& contract, const std::string& expected_sha);
std::string verify_shard_chain(const std::filesystem::path& index, const std::string& expected_sha);

enum class ValueType { Number, Boolean };
struct Node {
    std::string name, op;
    std::vector<std::size_t> inputs;
    i64 parameter{};
    ValueType type{ValueType::Number};
};
struct Value { i64 value{}; bool valid{}; u64 version{}; };
struct Bar {
    i64 bucket{}, day{}, open{}, high{}, low{}, close{};
    u64 last_seq{};
    bool initialized{};
    Value closed_open, closed_high, closed_low, closed_close;
};
struct NodeState {
    Value output;
    std::deque<Value> history;
    u64 last_version{};
    i64 previous_a{}, previous_b{};
    bool initialized{};
};
class FeatureGraph {
public:
    explicit FeatureGraph(std::vector<Node> nodes);
    const std::vector<Value>& update(const Tick& tick);
    const std::vector<Node>& nodes() const { return nodes_; }
private:
    std::vector<Node> nodes_;
    std::vector<NodeState> states_;
    std::vector<Value> values_;
    std::map<i64, Bar> bars_;
};

struct Program {
    Fields fields;
    std::string spec_sha, name, symbol, purpose, seed_sha;
    std::vector<std::string> axis_names;
    std::vector<std::vector<i64>> axes;
    u64 births{1};
};
struct Candidate {
    std::string id, graph_id, program_sha, seed_sha, name, symbol, purpose;
    u64 birth{};
    std::vector<Node> nodes;
    std::size_t signal_node{};
    Side side{Side::Buy};
    i64 stop_u{}, target_u{}, be_trigger_ppm{}, be_offset_u{}, trailing_u{};
    i64 commission_u{}, slippage_u{}, bar_ms{}, daily_limit{}, expiry_records{};
    std::string signal_mode;
    bool eligible{true};
    std::string exclusion;
    Fields parameters;
    std::string canonical;
};
Program read_program(const std::filesystem::path& path, const std::string& expected_sha);
Candidate compile_candidate(const Program& program, u64 birth);
std::string program_receipt(const Program& program);

struct PositionState {
    bool open{}, pending{}, signal_was_true{};
    u64 signal_seq{}, signal_version{}, last_entry_seq{};
    i64 signal_day{}, active_day{}, pending_records{}, entries_today{}, last_entry_bar{-1};
    i64 stop{}, target{}, best{};
    Trade trade;
    Tick last_exec;
    bool has_last_exec{};
    i64 mae{}, mfe{};
};
struct TradeRecord {
    std::string candidate_id, symbol;
    u64 birth{};
    Trade trade;
    i64 net_u{}, commission_u{}, mae_u{}, mfe_u{}, bar_ms{};
};
class BacktestState {
public:
    explicit BacktestState(Candidate candidate, u64 max_trades);
    void update(const Tick& tick, const SessionBoundary& session, const Value& signal);
    void finish();
    const std::vector<TradeRecord>& trades() const { return trades_; }
    const Candidate& candidate() const { return candidate_; }
    u64 unresolved() const { return unresolved_; }
private:
    void close(const Tick& tick, ExitReason reason);
    Candidate candidate_;
    PositionState state_;
    std::vector<TradeRecord> trades_;
    u64 max_trades_{}, unresolved_{};
};
std::string ledger_header();
std::string ledger_row(const TradeRecord& record);
std::vector<TradeRecord> read_ledger(const std::filesystem::path& path, const std::string& hash);
std::vector<TradeRecord> parse_ledger(const std::string& text);

struct Metrics {
    u64 trades{}, wins{}, losses{}, negative_years{}, positive_years{};
    i64 net_u{}, gross_profit_u{}, gross_loss_u{}, max_dd_u{};
    long double expectancy_r{}, win_rate{}, profit_factor{}, trade_sharpe{};
    std::map<i64, i64> annual_net;
};
Metrics metrics(const std::vector<TradeRecord>& trades);
std::vector<long double> adjust_pvalues(const std::vector<long double>& p, u64 n_tests, bool by);
std::string gate_report(const std::filesystem::path& ledger, const std::string& ledger_sha,
                        const std::filesystem::path& policy, const std::string& policy_sha);
std::string supergate_report(const std::filesystem::path& plan, const std::string& plan_sha);
std::string portfolio_report(const std::filesystem::path& plan, const std::string& plan_sha,
                             const std::filesystem::path& out_ledger);

class ResultStore {
public:
    ResultStore(std::filesystem::path root, std::string scope, std::string entrypoint,
                std::string binding);
    ~ResultStore();
    ResultStore(const ResultStore&) = delete;
    ResultStore& operator=(const ResultStore&) = delete;
    u64 committed_end() const { return committed_end_; }
    std::string committed_head() const { return head_; }
    void commit(u64 start, u64 end, const std::string& content, const std::string& expected_head);
    const std::filesystem::path& root() const { return root_; }
private:
    std::filesystem::path root_;
    std::string scope_, entrypoint_, binding_, head_, owner_, nonce_;
    u64 committed_end_{}, sequence_{}, fence_{};
    int lock_fd_{-1};
};

void enforce_vault(const DataSpec& data, const std::filesystem::path& policy,
                   const std::string& policy_sha, const std::string& phase,
                   const std::string& candidate_sha);
std::string consume_holdout_grant(const std::filesystem::path& policy, const std::string& policy_sha,
                                  const std::filesystem::path& grant, const std::string& grant_sha,
                                  const std::filesystem::path& store_root);
std::string mt5_parity(const std::filesystem::path& plan, const std::string& plan_sha);
std::string export_mt5(const Candidate& candidate);
int command(int argc, char** argv, const std::string& self_sha);
} // namespace qros::pipeline
