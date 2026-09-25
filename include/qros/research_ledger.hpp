#pragma once

#include "qros/research_state.hpp"
#include <cstdint>
#include <filesystem>
#include <string>

namespace qros::product {

// M2 is TEST_ONLY: its context flags must come from independently verified receipts
// before any production use. This class intentionally has no network or AI entrypoint.
struct ResearchLedgerHead {
    std::uint64_t sequence{};
    std::string digest = std::string(64, '0');
    ScientificState state = ScientificState::New;
    std::string project_id;
    std::string campaign_id;
};

struct ResearchTransitionRequest {
    std::string project_id;
    std::string campaign_id;
    std::string authority_ref;
    std::string evidence_sha256;
    ScientificState from = ScientificState::New;
    ScientificState requested = ScientificState::PreregisteredNoResults;
    TransitionActor actor = TransitionActor::User;
    TransitionContext context{};
};

struct ResearchLedgerEvent {
    ResearchLedgerHead head;
    TransitionDecision decision;
};

// One directory per authorized campaign. A trusted external head digest is required
// to detect deletion/replacement of the last event; local hashes alone cannot do so.
class ResearchTransitionLedger {
public:
    explicit ResearchTransitionLedger(std::filesystem::path campaign_directory);
    [[nodiscard]] ResearchLedgerHead inspect() const;
    [[nodiscard]] ResearchLedgerHead verify_anchor(const ResearchLedgerHead& trusted) const;
    [[nodiscard]] ResearchLedgerEvent append(const ResearchTransitionRequest& request,
                                              const ResearchLedgerHead& expected);
private:
    std::filesystem::path directory_;
};

}  // namespace qros::product
