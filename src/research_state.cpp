#include "qros/research_state.hpp"

namespace qros::product {
namespace {
TransitionDecision allow(const char* code) { return {true, code}; }
TransitionDecision deny(const char* code) { return {false, code}; }

bool branch_exhaustion_ready(const TransitionContext& c) {
    return c.evidence_semantics_pass && c.ontology_frozen && c.rise_fixed_point &&
           c.universe_coverage_complete && c.open_fronts_zero;
}

bool is_terminal(ScientificState s) {
    return s == ScientificState::ApprovedFinal || s == ScientificState::BranchExhausted;
}

bool is_non_promotional_target(ScientificState s) {
    return s == ScientificState::Rejected || s == ScientificState::ObservationalReserve ||
           s == ScientificState::BranchExhausted;
}
} // namespace

std::string_view scientific_state_name(ScientificState state) {
    switch (state) {
        case ScientificState::New: return "NEW";
        case ScientificState::PreregisteredNoResults: return "PREREGISTERED_NO_RESULTS";
        case ScientificState::DevelopmentRunning: return "DEVELOPMENT_RUNNING";
        case ScientificState::FrozenCandidate: return "FROZEN_CANDIDATE";
        case ScientificState::ApprovedResearch: return "APPROVED_RESEARCH";
        case ScientificState::ApprovedFinal: return "APPROVED_FINAL";
        case ScientificState::Rejected: return "REJECTED";
        case ScientificState::ObservationalReserve: return "OBSERVATIONAL_RESERVE";
        case ScientificState::BranchExhausted: return "BRANCH_EXHAUSTED";
    }
    return "UNKNOWN";
}

std::string_view transition_actor_name(TransitionActor actor) {
    switch (actor) {
        case TransitionActor::QrosCore: return "QROS_CORE";
        case TransitionActor::RiseQGuardian: return "RISE_Q_GUARDIAN";
        case TransitionActor::AiCopilot: return "AI_COPILOT";
        case TransitionActor::User: return "USER";
    }
    return "UNKNOWN";
}

std::string_view execution_annotation_name(ExecutionAnnotation annotation) {
    switch (annotation) {
        case ExecutionAnnotation::None: return "NONE";
        case ExecutionAnnotation::Mt5ExternalPending: return "MT5_EXTERNAL_PENDING";
        case ExecutionAnnotation::BlockedByInfrastructure: return "BLOCKED_BY_INFRASTRUCTURE";
    }
    return "UNKNOWN";
}

TransitionDecision evaluate_scientific_transition(ScientificState from,
                                                  ScientificState to,
                                                  TransitionActor actor,
                                                  const TransitionContext& c) {
    if (actor != TransitionActor::QrosCore)
        return deny("SCIENTIFIC_MUTATION_AUTHORITY_DENIED");
    if (from == to)
        return deny("NO_OP_TRANSITION_FORBIDDEN");
    if (is_terminal(from))
        return deny("TERMINAL_STATE_IMMUTABLE");
    if (!c.evidence_semantics_pass)
        return deny("SEMANTIC_EVIDENCE_NOT_VERIFIED");
    if (c.rise_q_veto && !is_non_promotional_target(to))
        return deny("RISEQ_VETO");

    switch (from) {
        case ScientificState::New:
            if (to == ScientificState::PreregisteredNoResults) {
                if (!c.data_audit_pass) return deny("DATA_AUDIT_REQUIRED");
                if (!c.preregistration_frozen) return deny("PREREGISTRATION_FREEZE_REQUIRED");
                return allow("TRANSITION_AUTHORIZED");
            }
            break;

        case ScientificState::PreregisteredNoResults:
            if (to == ScientificState::DevelopmentRunning)
                return allow("TRANSITION_AUTHORIZED");
            if (to == ScientificState::Rejected)
                return allow("REJECTION_AUTHORIZED");
            if (to == ScientificState::ObservationalReserve && c.exposed_window)
                return allow("EXPOSURE_RESERVE_AUTHORIZED");
            break;

        case ScientificState::DevelopmentRunning:
            if (to == ScientificState::FrozenCandidate) {
                if (!c.development_complete) return deny("DEVELOPMENT_COMPLETION_REQUIRED");
                return allow("TRANSITION_AUTHORIZED");
            }
            if (to == ScientificState::Rejected)
                return allow("REJECTION_AUTHORIZED");
            if (to == ScientificState::ObservationalReserve && c.exposed_window)
                return allow("EXPOSURE_RESERVE_AUTHORIZED");
            break;

        case ScientificState::FrozenCandidate:
            if (to == ScientificState::ApprovedResearch) {
                if (!c.holdout_open_authorized) return deny("HOLDOUT_AUTHORITY_REQUIRED");
                if (!c.holdout_pass) return deny("HOLDOUT_PASS_REQUIRED");
                if (!c.supergate_pass) return deny("SUPERGATE_PASS_REQUIRED");
                return allow("APPROVED_RESEARCH_AUTHORIZED");
            }
            if (to == ScientificState::Rejected)
                return allow("REJECTION_AUTHORIZED");
            if (to == ScientificState::ObservationalReserve && c.exposed_window)
                return allow("EXPOSURE_RESERVE_AUTHORIZED");
            break;

        case ScientificState::ApprovedResearch:
            if (to == ScientificState::ApprovedFinal) {
                if (!c.mt5_parity_pass) return deny("MT5_PARITY_REQUIRED");
                return allow("APPROVED_FINAL_AUTHORIZED");
            }
            if (to == ScientificState::Rejected)
                return allow("REJECTION_AUTHORIZED");
            break;

        case ScientificState::Rejected:
            if (to == ScientificState::BranchExhausted) {
                if (!branch_exhaustion_ready(c)) return deny("BRANCH_EXHAUSTION_PROOF_INCOMPLETE");
                return allow("BRANCH_EXHAUSTION_AUTHORIZED");
            }
            break;

        case ScientificState::ObservationalReserve:
            if (to == ScientificState::Rejected)
                return allow("REJECTION_AUTHORIZED");
            if (to == ScientificState::BranchExhausted) {
                if (!branch_exhaustion_ready(c)) return deny("BRANCH_EXHAUSTION_PROOF_INCOMPLETE");
                return allow("BRANCH_EXHAUSTION_AUTHORIZED");
            }
            break;

        case ScientificState::ApprovedFinal:
        case ScientificState::BranchExhausted:
            break;
    }
    return deny("TRANSITION_NOT_ALLOWED");
}

TransitionDecision evaluate_execution_annotation(ScientificState scientific_state,
                                                  ExecutionAnnotation requested,
                                                  TransitionActor actor,
                                                  const TransitionContext& c) {
    if (actor == TransitionActor::AiCopilot || actor == TransitionActor::User)
        return deny("EXECUTION_ANNOTATION_AUTHORITY_DENIED");
    if (requested == ExecutionAnnotation::None)
        return allow("EXECUTION_ANNOTATION_CLEAR_ALLOWED");
    if (requested == ExecutionAnnotation::BlockedByInfrastructure)
        return allow("INFRASTRUCTURE_BLOCK_ANNOTATION_ALLOWED");
    if (requested == ExecutionAnnotation::Mt5ExternalPending) {
        if (actor != TransitionActor::QrosCore)
            return deny("MT5_PENDING_REQUIRES_QROS_CORE");
        if (scientific_state != ScientificState::ApprovedResearch)
            return deny("MT5_PENDING_REQUIRES_APPROVED_RESEARCH");
        if (!c.evidence_semantics_pass)
            return deny("SEMANTIC_EVIDENCE_NOT_VERIFIED");
        return allow("MT5_PENDING_ANNOTATION_ALLOWED");
    }
    return deny("EXECUTION_ANNOTATION_NOT_ALLOWED");
}

} // namespace qros::product
