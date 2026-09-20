#pragma once

#include <algorithm>
#include <cctype>
#include <cstdint>
#include <limits>
#include <map>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace qros::architecture {

inline bool hash64(std::string_view value) {
    if (value.size() != 64U) return false;
    return std::all_of(value.begin(), value.end(), [](char c) {
        const auto u = static_cast<unsigned char>(c);
        return std::isdigit(u) != 0 || (c >= 'a' && c <= 'f');
    });
}

enum class ResearchStage : std::uint8_t {
    Preregistered = 0,
    CausalScope = 1,
    UniverseBuilt = 2,
    RiseFixedPoint = 3,
    OntologyFrozen = 4,
    ConfigFrozen = 5,
    IndependentParity = 6,
    DevelopmentBacktest = 7,
    GateA = 8,
    HoldoutAuthorized = 9,
    Supergate = 10,
    FinalDecision = 11
};

struct ResearchEvidence {
    std::string hypothesis_id;
    std::string seed_sha256;
    std::string dataset_sha256;
    std::string ontology_sha256;
    std::string config_root_sha256;
    std::uint64_t n_tests{};
    bool rise_fixed_point{};
    bool ontology_frozen{};
    bool config_frozen{};
    bool independent_parity{};
    bool unit_binding_pass{};
    bool holdout_authorized{};
    bool supergate_pass{};
    bool economic_pnl_read{};
    bool holdout_open{};
    bool ga2_open{};
    bool new_ga1_authorized{};
};

inline int stage_rank(ResearchStage stage) {
    return static_cast<int>(stage);
}

inline void validate_research_transition(ResearchStage from, ResearchStage to, const ResearchEvidence& e) {
    if (stage_rank(to) != stage_rank(from) + 1) throw std::logic_error("RESEARCH_STAGE_SKIP_OR_BACKTRACK");
    if (e.hypothesis_id.empty() || !hash64(e.seed_sha256)) throw std::invalid_argument("RESEARCH_IDENTITY_INVALID");
    if (e.ga2_open || e.new_ga1_authorized) throw std::logic_error("FORBIDDEN_SCIENTIFIC_BOUNDARY_OPEN");
    if (e.holdout_open && stage_rank(to) < stage_rank(ResearchStage::HoldoutAuthorized)) throw std::logic_error("HOLDOUT_OPEN_EARLY");

    switch (to) {
        case ResearchStage::CausalScope:
        case ResearchStage::UniverseBuilt:
            break;
        case ResearchStage::RiseFixedPoint:
            if (!e.rise_fixed_point) throw std::logic_error("RISE_FIXED_POINT_REQUIRED");
            break;
        case ResearchStage::OntologyFrozen:
            if (!e.rise_fixed_point || !e.ontology_frozen || !hash64(e.ontology_sha256)) throw std::logic_error("ONTOLOGY_FREEZE_REQUIRED");
            break;
        case ResearchStage::ConfigFrozen:
            if (!e.ontology_frozen || !e.config_frozen || !hash64(e.config_root_sha256) || e.n_tests == 0U)
                throw std::logic_error("CONFIG_FREEZE_AND_NTESTS_REQUIRED");
            break;
        case ResearchStage::IndependentParity:
            if (!e.config_frozen || !e.independent_parity) throw std::logic_error("INDEPENDENT_PARITY_REQUIRED");
            break;
        case ResearchStage::DevelopmentBacktest:
            if (!e.independent_parity || !e.unit_binding_pass || !hash64(e.dataset_sha256))
                throw std::logic_error("DEV_PREFLIGHT_REQUIRED");
            if (e.holdout_open) throw std::logic_error("HOLDOUT_MUST_REMAIN_CLOSED_DURING_DEV");
            break;
        case ResearchStage::GateA:
            if (!e.economic_pnl_read) throw std::logic_error("DEVELOPMENT_RESULT_REQUIRED");
            break;
        case ResearchStage::HoldoutAuthorized:
            if (!e.holdout_authorized) throw std::logic_error("HOLDOUT_AUTHORIZATION_REQUIRED");
            break;
        case ResearchStage::Supergate:
            if (!e.supergate_pass) throw std::logic_error("SUPERGATE_PASS_REQUIRED");
            break;
        case ResearchStage::FinalDecision:
            if (!e.supergate_pass) throw std::logic_error("FINAL_REQUIRES_SUPERGATE");
            break;
        case ResearchStage::Preregistered:
            throw std::logic_error("INVALID_FORWARD_TRANSITION");
    }
}

enum class Side : std::uint8_t { Buy, Sell };
enum class ExitReason : std::uint8_t { None, StopLoss, TakeProfit, SessionClose };

struct Quote {
    std::uint64_t seq{};
    std::int64_t ts_ns{};
    std::int64_t day{};
    std::int64_t bid_u{};
    std::int64_t ask_u{};
};

inline std::int64_t checked_add(std::int64_t a, std::int64_t b) {
    if ((b > 0 && a > std::numeric_limits<std::int64_t>::max() - b) ||
        (b < 0 && a < std::numeric_limits<std::int64_t>::min() - b))
        throw std::overflow_error("PRICE_ARITHMETIC_OVERFLOW");
    return a + b;
}

inline std::int64_t checked_sub(std::int64_t a, std::int64_t b) {
    if (b == std::numeric_limits<std::int64_t>::min()) throw std::overflow_error("PRICE_ARITHMETIC_OVERFLOW");
    return checked_add(a, -b);
}

inline void validate_executable_quote(const Quote& q) {
    if (q.seq == 0U || q.ts_ns <= 0 || q.bid_u <= 0 || q.ask_u <= 0 || q.ask_u <= q.bid_u)
        throw std::invalid_argument("QUOTE_NOT_EXECUTABLE");
}

class CausalClock {
public:
    void observe(const Quote& q) {
        validate_executable_quote(q);
        if (seen_) {
            if (q.seq <= last_seq_) throw std::logic_error("SEQUENCE_NOT_STRICTLY_INCREASING");
            if (q.ts_ns < last_ts_) throw std::logic_error("TIME_WENT_BACKWARDS");
        }
        seen_ = true;
        last_seq_ = q.seq;
        last_ts_ = q.ts_ns;
    }
private:
    bool seen_{};
    std::uint64_t last_seq_{};
    std::int64_t last_ts_{};
};

inline std::int64_t entry_fill(const Quote& q, Side side, std::int64_t slippage_u) {
    validate_executable_quote(q);
    if (slippage_u < 0) throw std::invalid_argument("NEGATIVE_SLIPPAGE");
    const auto p = side == Side::Buy ? checked_add(q.ask_u, slippage_u) : checked_sub(q.bid_u, slippage_u);
    if (p <= 0) throw std::logic_error("NONPOSITIVE_ENTRY_FILL");
    return p;
}

inline std::int64_t exit_fill(const Quote& q, Side side, std::int64_t slippage_u) {
    validate_executable_quote(q);
    if (slippage_u < 0) throw std::invalid_argument("NEGATIVE_SLIPPAGE");
    const auto p = side == Side::Buy ? checked_sub(q.bid_u, slippage_u) : checked_add(q.ask_u, slippage_u);
    if (p <= 0) throw std::logic_error("NONPOSITIVE_EXIT_FILL");
    return p;
}

struct BarEnvelope {
    std::int64_t open_u{};
    std::int64_t high_u{};
    std::int64_t low_u{};
    std::int64_t close_u{};
};

struct ExitDecision {
    ExitReason reason{ExitReason::None};
    std::int64_t executable_price_u{};
};

inline void validate_bar(const BarEnvelope& b) {
    if (b.open_u <= 0 || b.high_u <= 0 || b.low_u <= 0 || b.close_u <= 0 ||
        b.low_u > b.high_u || b.open_u < b.low_u || b.open_u > b.high_u ||
        b.close_u < b.low_u || b.close_u > b.high_u)
        throw std::invalid_argument("BAR_INVALID");
}

inline ExitDecision resolve_bar_exit(const BarEnvelope& b, Side side, std::int64_t stop_u, std::int64_t target_u) {
    validate_bar(b);
    if (stop_u <= 0 || target_u <= 0) throw std::invalid_argument("PROTECTIVE_LEVEL_INVALID");
    if (side == Side::Buy && stop_u >= target_u) throw std::invalid_argument("BUY_LEVEL_ORDER_INVALID");
    if (side == Side::Sell && target_u >= stop_u) throw std::invalid_argument("SELL_LEVEL_ORDER_INVALID");

    if (side == Side::Buy) {
        if (b.open_u <= stop_u) return {ExitReason::StopLoss, b.open_u};
        if (b.open_u >= target_u) return {ExitReason::TakeProfit, b.open_u};
        const bool stop = b.low_u <= stop_u;
        const bool target = b.high_u >= target_u;
        if (stop) return {ExitReason::StopLoss, stop_u};
        if (target) return {ExitReason::TakeProfit, target_u};
    } else {
        if (b.open_u >= stop_u) return {ExitReason::StopLoss, b.open_u};
        if (b.open_u <= target_u) return {ExitReason::TakeProfit, b.open_u};
        const bool stop = b.high_u >= stop_u;
        const bool target = b.low_u <= target_u;
        if (stop) return {ExitReason::StopLoss, stop_u};
        if (target) return {ExitReason::TakeProfit, target_u};
    }
    return {};
}

class DailyAdmission {
public:
    explicit DailyAdmission(std::uint32_t limit) : limit_(limit) {
        if (limit_ != 3U && limit_ != 5U) throw std::invalid_argument("DAILY_LIMIT_NOT_AUTHORIZED");
    }
    bool admit(std::int64_t day, std::int64_t bar_id) {
        if (!day_.has_value() || *day_ != day) {
            day_ = day;
            entries_ = 0U;
            last_bar_.reset();
        }
        if (entries_ >= limit_) return false;
        if (last_bar_.has_value() && *last_bar_ == bar_id) return false;
        ++entries_;
        last_bar_ = bar_id;
        return true;
    }
    void validate_day_rollover(std::int64_t next_day, bool position_open) const {
        if (day_.has_value() && *day_ != next_day && position_open) throw std::logic_error("OVERNIGHT_POSITION_FORBIDDEN");
    }
private:
    std::uint32_t limit_{};
    std::uint32_t entries_{};
    std::optional<std::int64_t> day_;
    std::optional<std::int64_t> last_bar_;
};

enum class OrderStatus : std::uint8_t { New, Ack, PartFilled, Filled, Cancelled, Rejected };
enum class OrderEventKind : std::uint8_t { Ack, PartialFill, Fill, Cancel, Reject };

struct OrderEvent {
    std::uint64_t seq{};
    std::uint64_t epoch{};
    OrderEventKind kind{OrderEventKind::Ack};
    std::uint64_t quantity_delta{};
};

class AdapterOrder {
public:
    AdapterOrder(std::string client_id, std::uint64_t quantity)
        : client_id_(std::move(client_id)), quantity_(quantity) {
        if (client_id_.empty() || quantity_ == 0U) throw std::invalid_argument("ORDER_ID_OR_QTY_INVALID");
    }

    void apply(const OrderEvent& e, std::uint64_t current_epoch) {
        if (e.epoch != current_epoch) throw std::logic_error("STALE_ADAPTER_EPOCH");
        if (e.seq == 0U || e.seq <= last_seq_) throw std::logic_error("ORDER_EVENT_REPLAY_OR_REORDER");
        if (terminal()) throw std::logic_error("ORDER_ALREADY_TERMINAL");

        switch (e.kind) {
            case OrderEventKind::Ack:
                if (status_ != OrderStatus::New || e.quantity_delta != 0U) throw std::logic_error("ACK_STATE_INVALID");
                status_ = OrderStatus::Ack;
                break;
            case OrderEventKind::PartialFill:
            case OrderEventKind::Fill:
                if (status_ != OrderStatus::Ack && status_ != OrderStatus::PartFilled) throw std::logic_error("FILL_BEFORE_ACK");
                if (e.quantity_delta == 0U || e.quantity_delta > quantity_ - filled_) throw std::logic_error("FILL_QTY_INVALID");
                filled_ += e.quantity_delta;
                if (e.kind == OrderEventKind::Fill) {
                    if (filled_ != quantity_) throw std::logic_error("FINAL_FILL_NOT_COMPLETE");
                    status_ = OrderStatus::Filled;
                } else {
                    if (filled_ >= quantity_) throw std::logic_error("PARTIAL_FILL_COMPLETED_ORDER");
                    status_ = OrderStatus::PartFilled;
                }
                break;
            case OrderEventKind::Cancel:
                if (e.quantity_delta != 0U) throw std::logic_error("CANCEL_QTY_INVALID");
                status_ = OrderStatus::Cancelled;
                break;
            case OrderEventKind::Reject:
                if (e.quantity_delta != 0U || filled_ != 0U) throw std::logic_error("REJECT_STATE_INVALID");
                status_ = OrderStatus::Rejected;
                break;
        }
        last_seq_ = e.seq;
    }

    bool terminal() const {
        return status_ == OrderStatus::Filled || status_ == OrderStatus::Cancelled || status_ == OrderStatus::Rejected;
    }
    OrderStatus status() const { return status_; }
    std::uint64_t filled() const { return filled_; }

private:
    std::string client_id_;
    std::uint64_t quantity_{};
    std::uint64_t filled_{};
    std::uint64_t last_seq_{};
    OrderStatus status_{OrderStatus::New};
};

class AdapterSession {
public:
    std::uint64_t epoch() const { return epoch_; }
    bool connected() const { return connected_; }

    void disconnect() {
        if (!connected_) throw std::logic_error("DOUBLE_DISCONNECT");
        connected_ = false;
    }
    void reconnect() {
        if (connected_) throw std::logic_error("RECONNECT_WITHOUT_DISCONNECT");
        if (epoch_ == std::numeric_limits<std::uint64_t>::max()) throw std::overflow_error("ADAPTER_EPOCH_OVERFLOW");
        ++epoch_;
        connected_ = true;
    }

    void submit(const std::string& client_id, std::uint64_t quantity) {
        if (!connected_) throw std::logic_error("SUBMIT_WHILE_DISCONNECTED");
        if (orders_.contains(client_id)) throw std::logic_error("DUPLICATE_CLIENT_ORDER_ID");
        orders_.emplace(client_id, AdapterOrder(client_id, quantity));
    }

    void apply(const std::string& client_id, const OrderEvent& event) {
        if (!connected_) throw std::logic_error("EVENT_WHILE_DISCONNECTED");
        orders_.at(client_id).apply(event, epoch_);
    }

    const AdapterOrder& order(const std::string& client_id) const { return orders_.at(client_id); }

private:
    std::uint64_t epoch_{1U};
    bool connected_{true};
    std::map<std::string, AdapterOrder> orders_;
};

struct SupergateEvidence {
    bool cleanroom_license{};
    bool no_third_party_runtime_dependency{};
    bool deterministic_replay{};
    bool independent_oracle{};
    bool lineage_contract{};
    bool execution_semantics{};
    bool adapter_faults{};
    bool chaos_fault_injection{};
    bool resource_bounds{};
    bool sanitizer_pass{};
    bool scientific_firewall{};
    bool reproducible_build_contract{};
};

struct SupergateResult {
    bool pass{};
    std::vector<std::string> missing;
    std::string decision;
};

inline SupergateResult evaluate_supergate(const SupergateEvidence& e) {
    SupergateResult r;
    const auto require = [&](bool ok, const char* name) { if (!ok) r.missing.emplace_back(name); };
    require(e.cleanroom_license, "CLEANROOM_LICENSE");
    require(e.no_third_party_runtime_dependency, "NO_THIRD_PARTY_RUNTIME_DEPENDENCY");
    require(e.deterministic_replay, "DETERMINISTIC_REPLAY");
    require(e.independent_oracle, "INDEPENDENT_ORACLE");
    require(e.lineage_contract, "LINEAGE_CONTRACT");
    require(e.execution_semantics, "EXECUTION_SEMANTICS");
    require(e.adapter_faults, "ADAPTER_FAULTS");
    require(e.chaos_fault_injection, "CHAOS_FAULT_INJECTION");
    require(e.resource_bounds, "RESOURCE_BOUNDS");
    require(e.sanitizer_pass, "SANITIZER_PASS");
    require(e.scientific_firewall, "SCIENTIFIC_FIREWALL");
    require(e.reproducible_build_contract, "REPRODUCIBLE_BUILD_CONTRACT");
    r.pass = r.missing.empty();
    r.decision = r.pass ? "READY_FOR_INTEGRATION_NOT_SCIENTIFIC_APPROVAL" : "BLOCKED_SUPERGATE";
    return r;
}

} // namespace qros::architecture
