#include "qros/research_contract.hpp"
#include "qros/sha256.hpp"
#include <initializer_list>
#include <set>
#include <string>

namespace qros::product {
namespace {

bool one_of(const std::string& value, std::initializer_list<const char*> allowed) {
    for (const char* candidate : allowed) {
        if (value == candidate) return true;
    }
    return false;
}

void require_identifier(const std::string& value, const std::string& field) {
    if (!pipeline::identifier(value)) pipeline::fail("INVALID_IDENTIFIER:" + field);
}

void require_hash(const std::string& value, const std::string& field) {
    if (!pipeline::hash_valid(value)) pipeline::fail("INVALID_HASH:" + field);
}

std::string verified_raw(const std::filesystem::path& path, const std::string& expected_sha) {
    require_hash(expected_sha, "expected_sha256");
    const auto raw = pipeline::bounded_text(path);
    if (sha256_text(raw) != expected_sha) pipeline::fail("CONTRACT_HASH_MISMATCH");
    return raw;
}

void require_purpose(const std::string& value) {
    if (!one_of(value, {"TEST_ONLY", "RESEARCH"})) pipeline::fail("INVALID_PURPOSE");
}

} // namespace

DataAuditJob read_data_audit_job(const std::filesystem::path& path,
                                 const std::string& expected_sha) {
    const auto raw = verified_raw(path, expected_sha);
    const auto fields = pipeline::parse_fields(raw, "QROS_DATA_AUDIT_JOB_V1");
    pipeline::exact_keys(fields, {
        "job_id", "data_spec_name", "data_spec_sha256", "purpose",
        "result_scope", "max_rows", "source_authority_ref"
    });

    DataAuditJob result;
    result.fields = fields;
    result.sha256 = expected_sha;
    result.job_id = fields.at("job_id");
    result.data_spec_name = fields.at("data_spec_name");
    result.data_spec_sha256 = fields.at("data_spec_sha256");
    result.purpose = fields.at("purpose");
    result.result_scope = fields.at("result_scope");
    result.max_rows = pipeline::natural(fields.at("max_rows"));
    result.source_authority_ref = fields.at("source_authority_ref");

    require_identifier(result.job_id, "job_id");
    require_identifier(result.result_scope, "result_scope");
    require_identifier(result.source_authority_ref, "source_authority_ref");
    require_hash(result.data_spec_sha256, "data_spec_sha256");
    require_purpose(result.purpose);
    if (result.data_spec_name.empty()) pipeline::fail("EMPTY_DATA_SPEC_NAME");
    if (result.max_rows == 0) pipeline::fail("UNBOUNDED_DATA_AUDIT_FORBIDDEN");

    return result;
}

StrategyContract read_strategy_contract(const std::filesystem::path& path,
                                        const std::string& expected_sha) {
    const auto raw = verified_raw(path, expected_sha);
    const auto fields = pipeline::parse_fields(raw, "QROS_STRATEGY_CONTRACT_V1");
    pipeline::exact_keys(fields, {
        "contract_id", "genealogy_root_id", "symbol", "purpose", "side_policy",
        "program_sha256", "data_authority_id", "execution_policy_sha256",
        "cost_policy_sha256", "search_space_sha256", "multiplicity_n_tests",
        "development_partition_id", "holdout_partition_id", "holdout_state",
        "origin", "frozen"
    });

    StrategyContract result;
    result.fields = fields;
    result.sha256 = expected_sha;
    result.contract_id = fields.at("contract_id");
    result.genealogy_root_id = fields.at("genealogy_root_id");
    result.symbol = fields.at("symbol");
    result.purpose = fields.at("purpose");
    result.side_policy = fields.at("side_policy");
    result.program_sha256 = fields.at("program_sha256");
    result.data_authority_id = fields.at("data_authority_id");
    result.execution_policy_sha256 = fields.at("execution_policy_sha256");
    result.cost_policy_sha256 = fields.at("cost_policy_sha256");
    result.search_space_sha256 = fields.at("search_space_sha256");
    result.multiplicity_n_tests = pipeline::natural(fields.at("multiplicity_n_tests"));
    result.development_partition_id = fields.at("development_partition_id");
    result.holdout_partition_id = fields.at("holdout_partition_id");
    result.holdout_state = fields.at("holdout_state");
    result.origin = fields.at("origin");
    result.frozen = fields.at("frozen") == "TRUE";

    require_identifier(result.contract_id, "contract_id");
    require_identifier(result.genealogy_root_id, "genealogy_root_id");
    require_identifier(result.symbol, "symbol");
    require_identifier(result.data_authority_id, "data_authority_id");
    require_identifier(result.development_partition_id, "development_partition_id");
    require_identifier(result.holdout_partition_id, "holdout_partition_id");
    require_hash(result.program_sha256, "program_sha256");
    require_hash(result.execution_policy_sha256, "execution_policy_sha256");
    require_hash(result.cost_policy_sha256, "cost_policy_sha256");
    require_hash(result.search_space_sha256, "search_space_sha256");
    require_purpose(result.purpose);

    if (!one_of(result.side_policy, {"BUY_ONLY", "SELL_ONLY", "BUY_SELL_SEPARATE"}))
        pipeline::fail("INVALID_SIDE_POLICY");
    if (!one_of(result.holdout_state, {"SEALED", "EXPOSED"}))
        pipeline::fail("INVALID_HOLDOUT_STATE");
    if (!one_of(result.origin, {"MANUAL", "AI_DRAFT", "IMPORT"}))
        pipeline::fail("INVALID_ORIGIN");
    if (!result.frozen) pipeline::fail("STRATEGY_CONTRACT_NOT_FROZEN");
    if (result.multiplicity_n_tests == 0) pipeline::fail("N_TESTS_ZERO_FORBIDDEN");
    if (result.development_partition_id == result.holdout_partition_id)
        pipeline::fail("DEVELOPMENT_HOLDOUT_PARTITION_COLLISION");

    return result;
}

ResearchJob read_research_job(const std::filesystem::path& path,
                              const std::string& expected_sha) {
    const auto raw = verified_raw(path, expected_sha);
    const auto fields = pipeline::parse_fields(raw, "QROS_RESEARCH_JOB_V1");
    pipeline::exact_keys(fields, {
        "job_id", "strategy_contract_name", "strategy_contract_sha256",
        "data_spec_name", "data_spec_sha256", "program_name", "program_sha256",
        "phase", "purpose", "result_scope", "max_rows", "max_trades",
        "authority_ref"
    });

    ResearchJob result;
    result.fields = fields;
    result.sha256 = expected_sha;
    result.job_id = fields.at("job_id");
    result.strategy_contract_name = fields.at("strategy_contract_name");
    result.strategy_contract_sha256 = fields.at("strategy_contract_sha256");
    result.data_spec_name = fields.at("data_spec_name");
    result.data_spec_sha256 = fields.at("data_spec_sha256");
    result.program_name = fields.at("program_name");
    result.program_sha256 = fields.at("program_sha256");
    result.phase = fields.at("phase");
    result.purpose = fields.at("purpose");
    result.result_scope = fields.at("result_scope");
    result.max_rows = pipeline::natural(fields.at("max_rows"));
    result.max_trades = pipeline::natural(fields.at("max_trades"));
    result.authority_ref = fields.at("authority_ref");

    require_identifier(result.job_id, "job_id");
    require_identifier(result.result_scope, "result_scope");
    require_hash(result.strategy_contract_sha256, "strategy_contract_sha256");
    require_hash(result.data_spec_sha256, "data_spec_sha256");
    require_hash(result.program_sha256, "program_sha256");
    if (result.strategy_contract_name.empty() || result.data_spec_name.empty() || result.program_name.empty())
        pipeline::fail("EMPTY_JOB_INPUT_NAME");
    if (!one_of(result.phase, {"DEVELOPMENT", "GATE_A", "HOLDOUT", "SUPERGATE", "MT5_PARITY", "PORTFOLIO"}))
        pipeline::fail("INVALID_RESEARCH_PHASE");
    require_purpose(result.purpose);
    if (result.max_rows == 0 || result.max_trades == 0)
        pipeline::fail("UNBOUNDED_JOB_FORBIDDEN");
    if (result.authority_ref != "NONE") require_identifier(result.authority_ref, "authority_ref");

    return result;
}

void validate_job_binding(const ResearchJob& job, const StrategyContract& strategy) {
    if (job.strategy_contract_sha256 != strategy.sha256)
        pipeline::fail("JOB_STRATEGY_HASH_MISMATCH");
    if (job.program_sha256 != strategy.program_sha256)
        pipeline::fail("JOB_PROGRAM_HASH_MISMATCH");
    if (job.purpose != strategy.purpose)
        pipeline::fail("JOB_PURPOSE_MISMATCH");
}

} // namespace qros::product
