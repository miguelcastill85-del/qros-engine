#pragma once

#include "qros/pipeline.hpp"
#include <filesystem>
#include <string>

namespace qros::product {

struct DataAuditJob {
    pipeline::Fields fields;
    std::string sha256;
    std::string job_id;
    std::string data_spec_name;
    std::string data_spec_sha256;
    std::string purpose;
    std::string result_scope;
    u64 max_rows{};
    std::string source_authority_ref;
};

struct StrategyContract {
    pipeline::Fields fields;
    std::string sha256;
    std::string contract_id;
    std::string genealogy_root_id;
    std::string symbol;
    std::string purpose;
    std::string side_policy;
    std::string program_sha256;
    std::string data_authority_id;
    std::string execution_policy_sha256;
    std::string cost_policy_sha256;
    std::string search_space_sha256;
    u64 multiplicity_n_tests{};
    std::string development_partition_id;
    std::string holdout_partition_id;
    std::string holdout_state;
    std::string origin;
    bool frozen{};
};

struct ResearchJob {
    pipeline::Fields fields;
    std::string sha256;
    std::string job_id;
    std::string strategy_contract_name;
    std::string strategy_contract_sha256;
    std::string data_spec_name;
    std::string data_spec_sha256;
    std::string program_name;
    std::string program_sha256;
    std::string phase;
    std::string purpose;
    std::string result_scope;
    u64 max_rows{};
    u64 max_trades{};
    std::string authority_ref;
};

DataAuditJob read_data_audit_job(const std::filesystem::path& path,
                                 const std::string& expected_sha);
StrategyContract read_strategy_contract(const std::filesystem::path& path,
                                        const std::string& expected_sha);
ResearchJob read_research_job(const std::filesystem::path& path,
                              const std::string& expected_sha);
void validate_job_binding(const ResearchJob& job, const StrategyContract& strategy);

} // namespace qros::product
