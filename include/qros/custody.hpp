#pragma once

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <string>
#include <string_view>
#include <vector>

namespace qros {

struct CustodyPartSpec {
    std::size_t index{};
    std::string name;
    std::uint64_t bytes{};
    std::string sha256;
};

struct SourceCustodyProfile {
    std::string profile_id;
    std::string source_id;
    std::string source_class;
    std::string namespace_prefix;
    std::size_t parts_count{};
    std::uint64_t total_bytes{};
    std::vector<CustodyPartSpec> parts;
    bool decoded_required{};
    std::string decoded_name;
    std::uint64_t decoded_bytes{};
    std::string decoded_sha256;
    std::string decoder_id;
    std::string historical_lineage_status;
    std::string profile_sha256;
    std::string expected_chain_root_sha256;
};

struct SourceCustodyAudit {
    std::size_t parts_seen{};
    std::uint64_t measured_total_bytes{};
    std::size_t missing_files{};
    std::size_t wrong_size{};
    std::size_t wrong_hash{};
    std::size_t non_regular_files{};
    std::size_t symlinks_rejected{};
    std::size_t unstable_files{};
    std::size_t inode_aliases{};
    std::size_t unexpected_namespace_files{};
    std::size_t casefold_collisions{};
    bool profile_valid{};
    bool parts_complete{};
    bool archive_custody_verified{};
    bool decoded_present{};
    bool decoded_size_match{};
    bool decoded_hash_match{};
    bool decoded_bytes_verified{};
    bool decode_lineage_verified{};
    bool source_provenance_ready{};
    bool production_source_provenance_ready{};
    std::string measured_chain_root_sha256;
    std::string decoded_measured_sha256;
    std::string custody_evidence_root_sha256;
    std::string_view status;
};

SourceCustodyProfile read_source_custody_profile(const std::filesystem::path& path);
std::string source_custody_profile_receipt(const SourceCustodyProfile& profile);
SourceCustodyAudit audit_source_custody(const SourceCustodyProfile& profile,
                                        const std::filesystem::path& source_directory);
std::string source_custody_receipt(const SourceCustodyProfile& profile,
                                   const SourceCustodyAudit& audit,
                                   std::string_view entrypoint_sha256,
                                   std::string_view source_root_sha256,
                                   std::string_view build_contract_sha256,
                                   std::string_view engine_version);
std::string custody_chain_root(const std::vector<CustodyPartSpec>& parts);

} // namespace qros
