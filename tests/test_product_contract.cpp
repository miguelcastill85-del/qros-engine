#include "qros/research_contract.hpp"
#include "qros/sha256.hpp"
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>

using namespace qros;
using namespace qros::pipeline;
using namespace qros::product;

namespace {
u64 checks = 0;
void check(bool value, const std::string& label) {
    ++checks;
    if (!value) throw std::runtime_error(label);
}
template<class Fn> void rejects(Fn fn, const std::string& label) {
    bool rejected = false;
    try { fn(); } catch (const std::exception&) { rejected = true; }
    check(rejected, label);
}
void put(const std::filesystem::path& path, const std::string& text) {
    std::ofstream out(path, std::ios::binary | std::ios::trunc);
    out << text;
    if (!out) throw std::runtime_error("test file write");
}
Fields strategy_fields() {
    const auto program = sha256_text("program");
    return {
        {"contract_id", "SC_TEST_001"},
        {"genealogy_root_id", "GEN_TEST_001"},
        {"symbol", "XAUUSD"},
        {"purpose", "TEST_ONLY"},
        {"side_policy", "BUY_SELL_SEPARATE"},
        {"program_sha256", program},
        {"data_authority_id", "DATA_TEST_001"},
        {"execution_policy_sha256", sha256_text("execution")},
        {"cost_policy_sha256", sha256_text("cost")},
        {"search_space_sha256", sha256_text("space")},
        {"multiplicity_n_tests", "64"},
        {"development_partition_id", "DEV_2018_2021"},
        {"holdout_partition_id", "HOLDOUT_2022_2024"},
        {"holdout_state", "SEALED"},
        {"origin", "AI_DRAFT"},
        {"frozen", "TRUE"}
    };
}
Fields job_fields(const std::string& contract_sha, const std::string& program_sha) {
    return {
        {"job_id", "JOB_TEST_001"},
        {"strategy_contract_name", "strategy.contract"},
        {"strategy_contract_sha256", contract_sha},
        {"data_spec_name", "data.spec"},
        {"data_spec_sha256", sha256_text("data spec")},
        {"program_name", "program.spec"},
        {"program_sha256", program_sha},
        {"phase", "DEVELOPMENT"},
        {"purpose", "TEST_ONLY"},
        {"result_scope", "JOB_TEST_001"},
        {"max_rows", "10000"},
        {"max_trades", "1000"},
        {"authority_ref", "NONE"}
    };
}
}

int main() {
    auto stem = (std::filesystem::temp_directory_path() / "qros-product-contract-XXXXXX").string();
    char* temp = ::mkdtemp(stem.data());
    if (temp == nullptr) return 1;
    const std::filesystem::path root(temp);
    try {
        auto fields = strategy_fields();
        auto text = fields_text("QROS_STRATEGY_CONTRACT_V1", fields);
        put(root / "strategy.contract", text);
        const auto strategy = read_strategy_contract(root / "strategy.contract", sha256_text(text));
        check(strategy.frozen, "strategy must be frozen");
        check(strategy.multiplicity_n_tests == 64, "N_TESTS retained");
        check(strategy.holdout_state == "SEALED", "holdout remains sealed");

        fields["frozen"] = "FALSE";
        text = fields_text("QROS_STRATEGY_CONTRACT_V1", fields);
        put(root / "not-frozen.contract", text);
        rejects([&]{ (void)read_strategy_contract(root / "not-frozen.contract", sha256_text(text)); },
                "unfrozen contract rejected");

        fields = strategy_fields();
        fields["multiplicity_n_tests"] = "0";
        text = fields_text("QROS_STRATEGY_CONTRACT_V1", fields);
        put(root / "zero-tests.contract", text);
        rejects([&]{ (void)read_strategy_contract(root / "zero-tests.contract", sha256_text(text)); },
                "zero N_TESTS rejected");

        fields = strategy_fields();
        fields["holdout_partition_id"] = fields.at("development_partition_id");
        text = fields_text("QROS_STRATEGY_CONTRACT_V1", fields);
        put(root / "partition-collision.contract", text);
        rejects([&]{ (void)read_strategy_contract(root / "partition-collision.contract", sha256_text(text)); },
                "development holdout collision rejected");

        const auto valid_fields = strategy_fields();
        const auto valid_text = fields_text("QROS_STRATEGY_CONTRACT_V1", valid_fields);
        put(root / "valid.contract", valid_text);
        const auto valid_strategy = read_strategy_contract(root / "valid.contract", sha256_text(valid_text));

        auto jf = job_fields(valid_strategy.sha256, valid_strategy.program_sha256);
        auto jt = fields_text("QROS_RESEARCH_JOB_V1", jf);
        put(root / "job.contract", jt);
        const auto job = read_research_job(root / "job.contract", sha256_text(jt));
        validate_job_binding(job, valid_strategy);
        check(job.phase == "DEVELOPMENT", "development job accepted");

        jf["program_sha256"] = sha256_text("different program");
        jt = fields_text("QROS_RESEARCH_JOB_V1", jf);
        put(root / "job-program-mismatch.contract", jt);
        const auto mismatch = read_research_job(root / "job-program-mismatch.contract", sha256_text(jt));
        rejects([&]{ validate_job_binding(mismatch, valid_strategy); }, "program binding mismatch rejected");

        jf = job_fields(valid_strategy.sha256, valid_strategy.program_sha256);
        jf["max_rows"] = "0";
        jt = fields_text("QROS_RESEARCH_JOB_V1", jf);
        put(root / "unbounded-job.contract", jt);
        rejects([&]{ (void)read_research_job(root / "unbounded-job.contract", sha256_text(jt)); },
                "unbounded job rejected");

        std::cout << "PRODUCT_CONTRACT_TESTS_PASS checks=" << checks << "\n";
        std::filesystem::remove_all(root);
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "PRODUCT_CONTRACT_TESTS_FAIL: " << e.what() << " fixture=" << root << "\n";
        return 1;
    }
}
