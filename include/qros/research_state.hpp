#pragma once

#include <string>
#include <string_view>

namespace qros::product {

enum class ScientificState {
    New,
    PreregisteredNoResults,
    DevelopmentRunning,
    FrozenCandidate,
    ApprovedResearch,
    ApprovedFinal,
    Rejected,
    ObservationalReserve,
    BranchExhausted
};

enum class TransitionActor {
    QrosCore,
    RiseQGuardian,
    AiCopilot,
    User
};

enum class ExecutionAnnotation {
    None,
    Mt5ExternalPending,
    BlockedByInfrastructure
};

struct TransitionContext {
    bool data_audit_pass{};
    bool preregistration_frozen{};
    bool development_complete{};
    bool evidence_semantics_pass{};
    bool holdout_open_authorized{};
    bool holdout_pass{};
    bool supergate_pass{};
    bool mt5_parity_pass{};
    bool exposed_window{};
    bool rise_q_veto{};
    bool ontology_frozen{};
    bool rise_fixed_point{};
    bool universe_coverage_complete{};
    bool open_fronts_zero{};
};

struct TransitionDecision {
    bool allowed{};
    std::string code;
};

std::string_view scientific_state_name(ScientificState state);
std::string_view transition_actor_name(TransitionActor actor);
std::string_view execution_annotation_name(ExecutionAnnotation annotation);

TransitionDecision evaluate_scientific_transition(ScientificState from,
                                                  ScientificState to,
                                                  TransitionActor actor,
                                                  const TransitionContext& context);

TransitionDecision evaluate_execution_annotation(ScientificState scientific_state,
                                                  ExecutionAnnotation requested,
                                                  TransitionActor actor,
                                                  const TransitionContext& context);

} // namespace qros::product
