#pragma once

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <string>
#include <string_view>
#include <vector>

namespace qros {

enum class TimeAuthorityPurpose { Research, TestOnly };

struct OffsetSegment {
    std::string segment_id;
    std::int64_t start_utc_ns{};
    std::int64_t end_utc_ns{};
    std::int64_t offset_seconds{};
};

struct TimeAnchor {
    std::string anchor_id;
    std::int64_t server_wall_ns{};
    std::int64_t utc_ns{};
    std::string evidence_id;
};

struct TimeAuthorityProfile {
    std::string authority_id;
    std::string source_id;
    TimeAuthorityPurpose purpose{TimeAuthorityPurpose::TestOnly};
    std::string server_clock_domain;
    std::string schedule_sha256;
    std::string anchors_sha256;
    std::string provenance_sha256;
    std::string source_custody_evidence_root_sha256;
    std::string source_custody_receipt_sha256;
    std::size_t min_anchors{};
    std::int64_t max_transition_bracket_ns{};
    std::int64_t max_edge_anchor_distance_ns{};
    std::int64_t max_abs_offset_seconds{};
    std::int64_t max_offset_jump_seconds{};
    std::string production_anchor_verifier_id;
    std::string profile_sha256;
};

struct TimeAuthorityAudit {
    std::size_t segments{};
    std::size_t anchors{};
    std::size_t offset_transitions{};
    std::size_t schedule_errors{};
    std::size_t anchor_errors{};
    std::size_t transition_bracket_errors{};
    std::size_t edge_coverage_errors{};
    std::size_t provenance_errors{};
    bool profile_valid{};
    bool schedule_hash_match{};
    bool anchors_hash_match{};
    bool provenance_hash_match{};
    bool custody_evidence_root_match{};
    bool custody_receipt_hash_match{};
    bool custody_receipt_semantic_valid{};
    bool custody_source_ready{};
    bool custody_production_ready{};
    bool semantic_provenance_match{};
    bool anchor_offsets_match_schedule{};
    bool test_time_ready{};
    bool research_time_ready{};
    bool production_anchor_verifier_available{};
    std::int64_t min_observed_offset_seconds{};
    std::int64_t max_observed_offset_seconds{};
    std::string schedule_sha256_measured;
    std::string anchors_sha256_measured;
    std::string provenance_sha256_measured;
    std::string custody_receipt_sha256_measured;
    std::string custody_evidence_root_measured;
    std::string_view status;
};

TimeAuthorityProfile read_time_authority_profile(const std::filesystem::path& path);
std::vector<OffsetSegment> read_offset_schedule(const std::filesystem::path& path);
std::vector<TimeAnchor> read_time_anchors(const std::filesystem::path& path);
TimeAuthorityAudit audit_time_authority(const TimeAuthorityProfile& profile,
                                        const std::filesystem::path& schedule_path,
                                        const std::filesystem::path& anchors_path,
                                        const std::filesystem::path& provenance_path,
                                        const std::filesystem::path& source_custody_receipt_path);
std::string time_authority_receipt(const TimeAuthorityProfile& profile,
                                   const TimeAuthorityAudit& audit,
                                   std::string_view entrypoint_sha256,
                                   std::string_view source_root_sha256,
                                   std::string_view build_contract_sha256,
                                   std::string_view engine_version);
std::string_view time_authority_purpose_name(TimeAuthorityPurpose purpose);

} // namespace qros
