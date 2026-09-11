#include "qros/research_contract.hpp"
#include "qros/build_identity.hpp"
#include <iostream>
#include <string>

namespace {
using qros::product::DataAuditJob;
using qros::product::ResearchJob;
using qros::product::StrategyContract;

void print_usage() {
    std::cerr
        << "usage:\n"
        << "  qros_product capabilities\n"
        << "  qros_product data-audit-check <job> <sha256>\n"
        << "  qros_product strategy-check <contract> <sha256>\n"
        << "  qros_product job-check <job> <job_sha256> <strategy> <strategy_sha256>\n";
}

qros::pipeline::Fields identity_fields() {
    return {
        {"engine_version", qros::build_identity::engine_version},
        {"source_root_sha256", qros::build_identity::source_root_sha256},
        {"build_contract_sha256", qros::build_identity::build_contract_sha256}
    };
}

void append_identity(qros::pipeline::Fields& fields) {
    const auto identity = identity_fields();
    fields.insert(identity.begin(), identity.end());
}
}

int main(int argc, char** argv) {
    try {
        if (argc < 2) {
            print_usage();
            return 2;
        }
        const std::string command = argv[1];

        if (command == "capabilities") {
            if (argc != 2) qros::pipeline::fail("usage: qros_product capabilities");
            auto fields = qros::pipeline::Fields{
                {"product", "QROS_RESEARCH_STUDIO"},
                {"interface", "LOCAL_CONTRACT_VALIDATION_CLI"},
                {"ai_scientific_authority", "0"},
                {"scientific_state_mutation", "0"},
                {"data_audit_job", "QROS_DATA_AUDIT_JOB_V1"},
                {"strategy_contract", "QROS_STRATEGY_CONTRACT_V1"},
                {"research_job", "QROS_RESEARCH_JOB_V1"},
                {"production_research_ready", "0"}
            };
            append_identity(fields);
            std::cout << qros::pipeline::fields_text("QROS_PRODUCT_CAPABILITIES_V1", fields);
            return 0;
        }

        if (command == "data-audit-check") {
            if (argc != 4)
                qros::pipeline::fail("usage: qros_product data-audit-check <job> <sha256>");
            const DataAuditJob job = qros::product::read_data_audit_job(argv[2], argv[3]);
            auto fields = qros::pipeline::Fields{
                {"job_id", job.job_id},
                {"job_sha256", job.sha256},
                {"data_spec_sha256", job.data_spec_sha256},
                {"purpose", job.purpose},
                {"max_rows", std::to_string(job.max_rows)},
                {"source_authority_ref", job.source_authority_ref},
                {"scientific_gate_pass", "0"},
                {"scientific_state_mutation", "0"},
                {"status", "CONTRACT_VALIDATION_PASS"}
            };
            append_identity(fields);
            std::cout << qros::pipeline::fields_text("QROS_DATA_AUDIT_JOB_VALIDATION_V1", fields);
            return 0;
        }

        if (command == "strategy-check") {
            if (argc != 4)
                qros::pipeline::fail("usage: qros_product strategy-check <contract> <sha256>");
            const StrategyContract strategy = qros::product::read_strategy_contract(argv[2], argv[3]);
            auto fields = qros::pipeline::Fields{
                {"contract_id", strategy.contract_id},
                {"contract_sha256", strategy.sha256},
                {"genealogy_root_id", strategy.genealogy_root_id},
                {"program_sha256", strategy.program_sha256},
                {"search_space_sha256", strategy.search_space_sha256},
                {"multiplicity_n_tests", std::to_string(strategy.multiplicity_n_tests)},
                {"holdout_state", strategy.holdout_state},
                {"origin", strategy.origin},
                {"ai_scientific_authority", "0"},
                {"scientific_gate_pass", "0"},
                {"scientific_state_mutation", "0"},
                {"status", "CONTRACT_VALIDATION_PASS"}
            };
            append_identity(fields);
            std::cout << qros::pipeline::fields_text("QROS_STRATEGY_CONTRACT_VALIDATION_V1", fields);
            return 0;
        }

        if (command == "job-check") {
            if (argc != 6)
                qros::pipeline::fail("usage: qros_product job-check <job> <job_sha256> <strategy> <strategy_sha256>");
            const ResearchJob job = qros::product::read_research_job(argv[2], argv[3]);
            const StrategyContract strategy = qros::product::read_strategy_contract(argv[4], argv[5]);
            qros::product::validate_job_binding(job, strategy);
            auto fields = qros::pipeline::Fields{
                {"job_id", job.job_id},
                {"job_sha256", job.sha256},
                {"strategy_contract_id", strategy.contract_id},
                {"strategy_contract_sha256", strategy.sha256},
                {"program_sha256", job.program_sha256},
                {"data_spec_sha256", job.data_spec_sha256},
                {"phase", job.phase},
                {"purpose", job.purpose},
                {"result_scope", job.result_scope},
                {"scientific_gate_pass", "0"},
                {"scientific_state_mutation", "0"},
                {"status", "CONTRACT_BINDING_PASS"}
            };
            append_identity(fields);
            std::cout << qros::pipeline::fields_text("QROS_RESEARCH_JOB_VALIDATION_V1", fields);
            return 0;
        }

        qros::pipeline::fail("UNKNOWN_PRODUCT_COMMAND:" + command);
    } catch (const std::exception& error) {
        std::cerr << "QROS_PRODUCT_ERROR: " << error.what() << "\n";
        return 1;
    }
}
