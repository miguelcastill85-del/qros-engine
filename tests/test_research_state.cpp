#include "qros/research_state.hpp"
#include <iostream>
#include <stdexcept>
#include <string>

using namespace qros::product;

namespace {
unsigned checks = 0;
void check(bool condition, const std::string& label) {
    ++checks;
    if (!condition) throw std::runtime_error(label);
}
TransitionContext base() {
    TransitionContext c;
    c.evidence_semantics_pass = true;
    return c;
}
}

int main() {
    try {
        {
            auto c = base();
            c.preregistration_frozen = true;
            check(!evaluate_scientific_transition(ScientificState::New, ScientificState::PreregisteredNoResults,
                                                  TransitionActor::QrosCore, c).allowed,
                  "data audit is mandatory before preregistration");
            c.data_audit_pass = true;
            check(evaluate_scientific_transition(ScientificState::New, ScientificState::PreregisteredNoResults,
                                                 TransitionActor::QrosCore, c).allowed,
                  "new to preregistered");
        }
        {
            auto c = base();
            c.data_audit_pass = true;
            c.preregistration_frozen = true;
            check(!evaluate_scientific_transition(ScientificState::New, ScientificState::PreregisteredNoResults,
                                                  TransitionActor::AiCopilot, c).allowed,
                  "AI cannot mutate scientific state");
            check(!evaluate_scientific_transition(ScientificState::New, ScientificState::PreregisteredNoResults,
                                                  TransitionActor::RiseQGuardian, c).allowed,
                  "RISE-Q cannot mutate scientific state");
            check(!evaluate_scientific_transition(ScientificState::New, ScientificState::PreregisteredNoResults,
                                                  TransitionActor::User, c).allowed,
                  "user request is not transition authority");
        }
        {
            auto c = base();
            check(evaluate_scientific_transition(ScientificState::PreregisteredNoResults,
                                                 ScientificState::DevelopmentRunning,
                                                 TransitionActor::QrosCore, c).allowed,
                  "preregistered to development");
            c.rise_q_veto = true;
            check(!evaluate_scientific_transition(ScientificState::PreregisteredNoResults,
                                                  ScientificState::DevelopmentRunning,
                                                  TransitionActor::QrosCore, c).allowed,
                  "RISE-Q veto blocks promotion");
            check(evaluate_scientific_transition(ScientificState::PreregisteredNoResults,
                                                 ScientificState::Rejected,
                                                 TransitionActor::QrosCore, c).allowed,
                  "RISE-Q veto does not block rejection");
        }
        {
            auto c = base();
            check(!evaluate_scientific_transition(ScientificState::DevelopmentRunning,
                                                  ScientificState::FrozenCandidate,
                                                  TransitionActor::QrosCore, c).allowed,
                  "development completion required");
            c.development_complete = true;
            check(evaluate_scientific_transition(ScientificState::DevelopmentRunning,
                                                 ScientificState::FrozenCandidate,
                                                 TransitionActor::QrosCore, c).allowed,
                  "development can freeze after completion");
        }
        {
            auto c = base();
            c.holdout_open_authorized = true;
            c.holdout_pass = true;
            check(!evaluate_scientific_transition(ScientificState::FrozenCandidate,
                                                  ScientificState::ApprovedResearch,
                                                  TransitionActor::QrosCore, c).allowed,
                  "supergate required for approved research");
            c.supergate_pass = true;
            check(evaluate_scientific_transition(ScientificState::FrozenCandidate,
                                                 ScientificState::ApprovedResearch,
                                                 TransitionActor::QrosCore, c).allowed,
                  "approved research after holdout and supergate");
            c.rise_q_veto = true;
            check(!evaluate_scientific_transition(ScientificState::FrozenCandidate,
                                                  ScientificState::ApprovedResearch,
                                                  TransitionActor::QrosCore, c).allowed,
                  "RISE-Q veto blocks research approval");
        }
        {
            auto c = base();
            check(!evaluate_scientific_transition(ScientificState::ApprovedResearch,
                                                  ScientificState::ApprovedFinal,
                                                  TransitionActor::QrosCore, c).allowed,
                  "MT5 parity required for final approval");
            c.mt5_parity_pass = true;
            check(evaluate_scientific_transition(ScientificState::ApprovedResearch,
                                                 ScientificState::ApprovedFinal,
                                                 TransitionActor::QrosCore, c).allowed,
                  "final approval requires MT5 parity");
            check(!evaluate_scientific_transition(ScientificState::ApprovedFinal,
                                                  ScientificState::Rejected,
                                                  TransitionActor::QrosCore, c).allowed,
                  "approved final is terminal");
        }
        {
            auto c = base();
            c.exposed_window = true;
            check(evaluate_scientific_transition(ScientificState::DevelopmentRunning,
                                                 ScientificState::ObservationalReserve,
                                                 TransitionActor::QrosCore, c).allowed,
                  "exposed development can enter observational reserve");
            check(!evaluate_scientific_transition(ScientificState::ObservationalReserve,
                                                  ScientificState::DevelopmentRunning,
                                                  TransitionActor::QrosCore, c).allowed,
                  "observational reserve cannot silently return to development");
        }
        {
            auto c = base();
            c.ontology_frozen = true;
            c.rise_fixed_point = true;
            c.universe_coverage_complete = true;
            check(!evaluate_scientific_transition(ScientificState::Rejected,
                                                  ScientificState::BranchExhausted,
                                                  TransitionActor::QrosCore, c).allowed,
                  "open fronts must be zero before branch exhaustion");
            c.open_fronts_zero = true;
            check(evaluate_scientific_transition(ScientificState::Rejected,
                                                 ScientificState::BranchExhausted,
                                                 TransitionActor::QrosCore, c).allowed,
                  "branch exhaustion proof complete");
        }
        {
            auto c = base();
            check(evaluate_execution_annotation(ScientificState::DevelopmentRunning,
                                                ExecutionAnnotation::BlockedByInfrastructure,
                                                TransitionActor::RiseQGuardian, c).allowed,
                  "RISE-Q may annotate infrastructure block without scientific mutation");
            check(!evaluate_execution_annotation(ScientificState::ApprovedResearch,
                                                 ExecutionAnnotation::Mt5ExternalPending,
                                                 TransitionActor::RiseQGuardian, c).allowed,
                  "RISE-Q cannot set MT5 pending scientific workflow annotation");
            check(!evaluate_execution_annotation(ScientificState::FrozenCandidate,
                                                 ExecutionAnnotation::Mt5ExternalPending,
                                                 TransitionActor::QrosCore, c).allowed,
                  "MT5 pending requires approved research");
            check(evaluate_execution_annotation(ScientificState::ApprovedResearch,
                                                ExecutionAnnotation::Mt5ExternalPending,
                                                TransitionActor::QrosCore, c).allowed,
                  "QROS core can mark MT5 pending after research approval");
            check(!evaluate_execution_annotation(ScientificState::ApprovedResearch,
                                                 ExecutionAnnotation::BlockedByInfrastructure,
                                                 TransitionActor::AiCopilot, c).allowed,
                  "AI cannot annotate execution authority state");
        }
        {
            auto c = base();
            c.evidence_semantics_pass = false;
            check(!evaluate_scientific_transition(ScientificState::DevelopmentRunning,
                                                  ScientificState::Rejected,
                                                  TransitionActor::QrosCore, c).allowed,
                  "even rejection needs semantically verified evidence");
        }
        check(scientific_state_name(ScientificState::ApprovedResearch) == "APPROVED_RESEARCH",
              "scientific state naming stable");
        check(execution_annotation_name(ExecutionAnnotation::BlockedByInfrastructure) == "BLOCKED_BY_INFRASTRUCTURE",
              "execution annotation naming stable");
        std::cout << "RESEARCH_STATE_TESTS_PASS checks=" << checks << "\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "RESEARCH_STATE_TESTS_FAIL: " << error.what() << "\n";
        return 1;
    }
}
