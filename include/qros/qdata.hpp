#pragma once

#include "qros/core.hpp"

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <string>
#include <string_view>
#include <vector>

namespace qros {

enum class VerificationStatus { Verified, TestOnly, Unverified };
enum class QDataPurpose { Research, TestOnly };

struct SessionBoundary {
    i64 session_day{};
    u64 open_seq{};
    u64 close_seq{};
    i64 open_ts_ns{};
    i64 close_ts_ns{};
    i64 utc_offset_seconds{};
};

struct QDataManifest {
    std::string authority_id;
    std::string symbol;
    std::string dataset_sha256;
    std::string sessions_sha256;
    std::string schema;
    std::size_t expected_rows{};
    u64 first_seq{};
    u64 last_seq{};
    i64 first_ts_ns{};
    i64 last_ts_ns{};
    int price_decimals{};
    i64 point_size_u{};
    i64 tick_size_u{};
    std::string timezone_name;
    VerificationStatus timezone_status{VerificationStatus::Unverified};
    QDataPurpose purpose{QDataPurpose::TestOnly};
    std::string timezone_evidence_sha256;
    std::string source_kind;
    std::string source_id;
    std::string source_evidence_sha256;
    std::string session_policy_id;
    std::uint64_t max_zero_spread_ppm{};
    bool allow_nonpositive_prices{};
};

struct QDataAudit {
    DataAudit ticks;
    std::size_t sessions{};
    std::size_t blank_tick_records{};
    std::size_t blank_session_records{};
    std::size_t nonpositive_quotes{};
    std::size_t nonpositive_timestamps{};
    std::size_t tick_size_violations{};
    std::size_t numeric_errors{};
    std::size_t session_boundary_errors{};
    std::size_t session_membership_errors{};
    std::size_t invalid_session_dates{};
    std::size_t uncovered_ticks{};
    std::size_t zero_spread_ppm{};
    i64 min_spread_u{};
    i64 p50_spread_u{};
    i64 p95_spread_u{};
    i64 p99_spread_u{};
    i64 max_spread_u{};
    i64 max_intraday_gap_ns{};
    std::size_t session_offset_transitions{};
    i64 max_offset_jump_seconds{};
    i64 first_session_day{};
    i64 last_session_day{};
    bool dataset_hash_match{};
    bool sessions_hash_match{};
    bool row_count_match{};
    bool extent_match{};
    bool timezone_evidence_bound{};
    bool timezone_evidence_hash_match{};
    bool source_evidence_hash_match{};
    bool timezone_evidence_semantic_match{};
    bool source_evidence_semantic_match{};
    bool timezone_research_verified{};
    bool source_research_verified{};
    bool production_evidence_verifier_available{};
    bool pass_integrity{};
    bool test_ready{};
    bool research_ready{};
    std::string dataset_sha256;
    std::string sessions_sha256;
    std::string manifest_sha256;
    std::string_view message;
};

QDataManifest read_qdata_manifest(const std::filesystem::path& path);
std::vector<SessionBoundary> read_session_map_csv(const std::filesystem::path& path, std::size_t* blank_records = nullptr);
QDataAudit audit_qdata_authority(const std::filesystem::path& ticks_path,
                                 const std::filesystem::path& sessions_path,
                                 const std::filesystem::path& manifest_path,
                                 const std::filesystem::path& timezone_evidence_path,
                                 const std::filesystem::path& source_evidence_path);
Trade replay_qdata_stream_bound(const std::filesystem::path& ticks_path,
                                const std::string& expected_dataset_sha256,
                                const Intent& intent);
std::string qdata_audit_receipt(const QDataManifest& manifest, const QDataAudit& audit);
std::string_view verification_status_name(VerificationStatus status);
std::string_view qdata_purpose_name(QDataPurpose purpose);

// Closed contracts. Their SHA-256 hashes are included in receipts/run identity.
std::string_view event_phase_contract_v1();
std::string_view execution_policy_v1();

} // namespace qros
