#include "qros/research_ledger.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

using namespace qros::product;
namespace fs = std::filesystem;
namespace {
int checks = 0;
void check(bool ok, const std::string& why) {
    ++checks;
    if (!ok) throw std::runtime_error("TEST_FAILED:" + why);
}
void denied(const std::string& label, const std::string& code, auto fn) {
    bool hit = false;
    try { fn(); } catch (const std::exception& ex) {
        hit = std::string(ex.what()).find(code) != std::string::npos;
    }
    check(hit, label);
}
TransitionContext basic() {
    TransitionContext c;
    c.evidence_semantics_pass = true;
    c.data_audit_pass = true;
    c.preregistration_frozen = true;
    return c;
}
ResearchTransitionRequest request(ScientificState from, ScientificState to,
                                  TransitionActor actor = TransitionActor::QrosCore) {
    ResearchTransitionRequest r;
    r.project_id = "M2_TEST_PROJECT";
    r.campaign_id = "M2_TEST_CAMPAIGN";
    r.authority_ref = "TEST_ONLY:fixture";
    r.evidence_sha256 = std::string(64, 'a');
    r.from = from;
    r.requested = to;
    r.actor = actor;
    r.context = basic();
    return r;
}
fs::path file_for(const fs::path& root, int sequence) {
    std::string s = std::to_string(sequence);
    return root / (std::string(16 - s.size(), '0') + s + ".evt");
}
std::string load(const fs::path& path) {
    std::ifstream input(path, std::ios::binary);
    return {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
}
void save(const fs::path& path, const std::string& content) {
    std::ofstream output(path, std::ios::binary | std::ios::trunc);
    output << content;
    if (!output) throw std::runtime_error("fixture write failed");
}
}
int main() {
    const auto root = fs::temp_directory_path() / "qros-m2-ledger-local-tests";
    fs::remove_all(root);
    try {
        ResearchTransitionLedger ledger(root);
        const auto genesis = ledger.inspect();
        check(genesis.sequence == 0 && genesis.digest == std::string(64, '0') &&
              genesis.state == ScientificState::New, "clean genesis");
        auto ai = request(ScientificState::New, ScientificState::PreregisteredNoResults,
                          TransitionActor::AiCopilot);
        const auto rejected = ledger.append(ai, genesis);
        check(!rejected.decision.allowed && rejected.head.sequence == 1 &&
              rejected.head.state == ScientificState::New, "AI request recorded and rejected");
        denied("stale head", "STALE_CAS_HEAD", [&] { (void)ledger.append(ai, genesis); });
        auto user = request(ScientificState::New, ScientificState::PreregisteredNoResults,
                            TransitionActor::User);
        const auto user_denied = ledger.append(user, rejected.head);
        check(!user_denied.decision.allowed && user_denied.head.state == ScientificState::New,
              "user request cannot promote");
        const auto prereg = ledger.append(
            request(ScientificState::New, ScientificState::PreregisteredNoResults), user_denied.head);
        check(prereg.decision.allowed && prereg.head.sequence == 3 &&
              prereg.head.state == ScientificState::PreregisteredNoResults, "core transition");
        ResearchTransitionLedger restarted(root);
        check(restarted.verify_anchor(prereg.head).digest == prereg.head.digest,
              "restart verifies persisted chain");
        denied("state mismatch", "REQUEST_STATE_NOT_HEAD", [&] {
            (void)ledger.append(request(ScientificState::New, ScientificState::DevelopmentRunning), prereg.head);
        });
        const auto development = restarted.append(
            request(ScientificState::PreregisteredNoResults, ScientificState::DevelopmentRunning),
            prereg.head);
        check(development.decision.allowed && development.head.state == ScientificState::DevelopmentRunning,
              "development transition");
        ResearchTransitionLedger another(root);
        check(another.verify_anchor(development.head).sequence == 4, "recovery after append");
        auto cross = request(ScientificState::DevelopmentRunning, ScientificState::FrozenCandidate);
        cross.campaign_id = "DIFFERENT_CAMPAIGN";
        denied("campaign separation", "PROJECT_CAMPAIGN_MISMATCH", [&] {
            (void)another.append(cross, development.head);
        });
        cross.campaign_id = "M2_TEST_CAMPAIGN";
        cross.evidence_sha256 = "INVALID";
        denied("evidence digest required", "INVALID_EVIDENCE_SHA256", [&] {
            (void)another.append(cross, development.head);
        });
        fs::create_directory(root / ".writer_lock");
        denied("cooperating writer lock", "WRITER_LOCK_HELD", [&] {
            (void)another.append(request(ScientificState::DevelopmentRunning,
                                   ScientificState::FrozenCandidate), development.head);
        });
        fs::remove(root / ".writer_lock");
        auto incomplete = request(ScientificState::DevelopmentRunning,
                                  ScientificState::FrozenCandidate);
        const auto premature = another.append(incomplete, development.head);
        check(!premature.decision.allowed && premature.head.state == ScientificState::DevelopmentRunning,
              "incomplete development stays unpromoted but attempts preserved");
        const auto old_anchor = premature.head;
        const auto tail = file_for(root, 5);
        fs::remove(tail);
        denied("anchored tail deletion", "TRUSTED_ANCHOR_MISMATCH", [&] {
            (void)another.verify_anchor(old_anchor);
        });
        save(tail, "garbage");
        denied("truncated event", "BAD_HEADER", [&] { (void)another.inspect(); });
        fs::remove(tail);
        const auto good = load(file_for(root, 2));
        auto modified = good;
        const auto pos = modified.find("evidence=");
        check(pos != std::string::npos, "fixture evidence present");
        modified[pos + std::string("evidence=").size()] = 'b';
        save(file_for(root, 2), modified);
        denied("tamper on older event", "EVENT_HASH_MISMATCH", [&] { (void)another.inspect(); });
        save(file_for(root, 2), good);
        check(another.verify_anchor(development.head).sequence == 4,
              "restoring exact bytes restores verified chain");
        fs::remove(file_for(root, 2));
        denied("missing middle event", "LEDGER_SEQUENCE_GAP_OR_DUPLICATE", [&] {
            (void)another.inspect();
        });
        save(file_for(root, 2), good);
        check(another.verify_anchor(development.head).digest == development.head.digest,
              "verified chain intact after restoration");
        std::cout << "M2_LEDGER_LOCAL_TESTS_PASS checks=" << checks << "\n";
        fs::remove_all(root);
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "M2_LEDGER_LOCAL_TESTS_FAIL " << e.what() << " checks=" << checks << "\n";
        fs::remove_all(root);
        return 1;
    }
}
