#include "qros/research_ledger.hpp"
#include "qros/sha256.hpp"

#include <array>
#include <algorithm>
#include <cctype>
#include <cerrno>
#include <fstream>
#include <iomanip>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string_view>
#include <vector>

#if !defined(_WIN32)
#include <fcntl.h>
#include <unistd.h>
#endif

namespace qros::product {
namespace {
namespace fs = std::filesystem;
constexpr std::size_t kMaxEventBytes = 8192;
constexpr std::string_view kDomain = "QROS_M2_TRANSITION_EVENT_SHA256_V1\n";
constexpr std::string_view kHeader = "QROS_M2_TRANSITION_EVENT_V1";
const std::string kGenesis(64, '0');

[[noreturn]] void fail(const std::string& code) { throw std::runtime_error("QROS_LEDGER:" + code); }

bool hex_digest(const std::string& value) {
    if (value.size() != 64) return false;
    for (unsigned char c : value) if (!std::isxdigit(c) || std::isupper(c)) return false;
    return true;
}

void check_label(const std::string& value, std::string_view label) {
    if (value.empty() || value.size() > 256) fail("INVALID_" + std::string(label));
    for (unsigned char c : value) if (c < 0x21 || c > 0x7e || c == '=' || c == '\\')
        fail("INVALID_" + std::string(label));
}

std::string name(ScientificState state) { return std::string(scientific_state_name(state)); }
std::string actor_name(TransitionActor actor) { return std::string(transition_actor_name(actor)); }

ScientificState parse_state(const std::string& value) {
    constexpr std::array<ScientificState, 9> states = {
        ScientificState::New, ScientificState::PreregisteredNoResults,
        ScientificState::DevelopmentRunning, ScientificState::FrozenCandidate,
        ScientificState::ApprovedResearch, ScientificState::ApprovedFinal,
        ScientificState::Rejected, ScientificState::ObservationalReserve,
        ScientificState::BranchExhausted
    };
    for (const auto s : states) if (name(s) == value) return s;
    fail("INVALID_STATE");
}

TransitionActor parse_actor(const std::string& value) {
    constexpr std::array<TransitionActor, 4> actors = {
        TransitionActor::QrosCore, TransitionActor::RiseQGuardian,
        TransitionActor::AiCopilot, TransitionActor::User
    };
    for (const auto a : actors) if (actor_name(a) == value) return a;
    fail("INVALID_ACTOR");
}

std::string bits(const TransitionContext& c) {
    std::string out;
    for (const bool b : {c.data_audit_pass, c.preregistration_frozen,
                         c.development_complete, c.evidence_semantics_pass,
                         c.holdout_open_authorized, c.holdout_pass, c.supergate_pass,
                         c.mt5_parity_pass, c.exposed_window, c.rise_q_veto,
                         c.ontology_frozen, c.rise_fixed_point,
                         c.universe_coverage_complete, c.open_fronts_zero})
        out.push_back(b ? '1' : '0');
    return out;
}

TransitionContext from_bits(const std::string& value) {
    if (value.size() != 14) fail("INVALID_CONTEXT");
    for (const char c : value) if (c != '0' && c != '1') fail("INVALID_CONTEXT");
    TransitionContext c;
    std::size_t i = 0;
    c.data_audit_pass = value[i++] == '1';
    c.preregistration_frozen = value[i++] == '1';
    c.development_complete = value[i++] == '1';
    c.evidence_semantics_pass = value[i++] == '1';
    c.holdout_open_authorized = value[i++] == '1';
    c.holdout_pass = value[i++] == '1';
    c.supergate_pass = value[i++] == '1';
    c.mt5_parity_pass = value[i++] == '1';
    c.exposed_window = value[i++] == '1';
    c.rise_q_veto = value[i++] == '1';
    c.ontology_frozen = value[i++] == '1';
    c.rise_fixed_point = value[i++] == '1';
    c.universe_coverage_complete = value[i++] == '1';
    c.open_fronts_zero = value[i++] == '1';
    return c;
}

struct Event {
    std::uint64_t sequence{};
    std::string previous;
    std::string project;
    std::string campaign;
    ScientificState from{};
    ScientificState requested{};
    TransitionActor actor{};
    TransitionContext context{};
    std::string authority;
    std::string evidence;
    bool allowed{};
    std::string decision;
    std::string digest;
};

std::string canonical(const Event& e) {
    return std::string(kHeader) + "\n" +
        "sequence=" + std::to_string(e.sequence) + "\n" +
        "previous=" + e.previous + "\n" +
        "project=" + e.project + "\n" +
        "campaign=" + e.campaign + "\n" +
        "from=" + name(e.from) + "\n" +
        "requested=" + name(e.requested) + "\n" +
        "actor=" + actor_name(e.actor) + "\n" +
        "context=" + bits(e.context) + "\n" +
        "authority=" + e.authority + "\n" +
        "evidence=" + e.evidence + "\n" +
        "allowed=" + (e.allowed ? "1\n" : "0\n") +
        "decision=" + e.decision + "\n";
}

std::string digest_for(const Event& e) { return sha256_text(std::string(kDomain) + canonical(e)); }

fs::path event_path(const fs::path& root, std::uint64_t sequence) {
    std::ostringstream filename;
    filename << std::setw(16) << std::setfill('0') << sequence << ".evt";
    return root / filename.str();
}

std::string read_bounded(const fs::path& path) {
    if (fs::is_symlink(path) || !fs::is_regular_file(path)) fail("UNSAFE_EVENT_PATH");
    const auto size = fs::file_size(path);
    if (size == 0 || size > kMaxEventBytes) fail("INVALID_EVENT_SIZE");
    std::ifstream input(path, std::ios::binary);
    if (!input) fail("EVENT_READ_FAILED");
    std::string content(static_cast<std::size_t>(size), '\0');
    input.read(content.data(), static_cast<std::streamsize>(content.size()));
    if (input.gcount() != static_cast<std::streamsize>(content.size())) fail("EVENT_TRUNCATED");
    return content;
}

std::string next_value(std::istringstream& input, const std::string& label) {
    std::string line;
    if (!std::getline(input, line) || line.rfind(label + "=", 0) != 0)
        fail("EVENT_SCHEMA_MISMATCH:" + label);
    return line.substr(label.size() + 1);
}

std::uint64_t parse_sequence(const std::string& text) {
    if (text.empty() || text.size() > 20 || (text.size() > 1 && text[0] == '0'))
        fail("BAD_SEQUENCE");
    for (unsigned char c : text) if (!std::isdigit(c)) fail("BAD_SEQUENCE");
    try {
        const auto result = std::stoull(text);
        if (result == 0 || result >= std::numeric_limits<std::uint64_t>::max())
            fail("BAD_SEQUENCE");
        return static_cast<std::uint64_t>(result);
    } catch (const std::exception&) { fail("BAD_SEQUENCE"); }
}

Event parse_event(const std::string& raw) {
    std::istringstream input(raw);
    std::string header;
    if (!std::getline(input, header) || header != kHeader) fail("BAD_HEADER");
    Event e;
    e.sequence = parse_sequence(next_value(input, "sequence"));
    e.previous = next_value(input, "previous");
    e.project = next_value(input, "project");
    e.campaign = next_value(input, "campaign");
    e.from = parse_state(next_value(input, "from"));
    e.requested = parse_state(next_value(input, "requested"));
    e.actor = parse_actor(next_value(input, "actor"));
    e.context = from_bits(next_value(input, "context"));
    e.authority = next_value(input, "authority");
    e.evidence = next_value(input, "evidence");
    const auto allowed = next_value(input, "allowed");
    if (allowed != "0" && allowed != "1") fail("INVALID_DECISION_BOOLEAN");
    e.allowed = allowed == "1";
    e.decision = next_value(input, "decision");
    e.digest = next_value(input, "event_sha256");
    std::string trailing;
    if (std::getline(input, trailing)) fail("EXTRA_EVENT_BYTES");
    check_label(e.project, "PROJECT");
    check_label(e.campaign, "CAMPAIGN");
    check_label(e.authority, "AUTHORITY");
    check_label(e.decision, "DECISION");
    if (!hex_digest(e.previous) || !hex_digest(e.evidence) || !hex_digest(e.digest))
        fail("INVALID_DIGEST");
    const auto decision = evaluate_scientific_transition(e.from, e.requested, e.actor, e.context);
    if (decision.allowed != e.allowed || decision.code != e.decision)
        fail("DECISION_REPLAY_MISMATCH");
    if (digest_for(e) != e.digest) fail("EVENT_HASH_MISMATCH");
    if (raw != canonical(e) + "event_sha256=" + e.digest + "\n")
        fail("EVENT_NOT_CANONICAL");
    return e;
}

// POSIX persistence: fsync the staged file, atomically install the committed
// name without overwrite, and fsync the parent directory. Windows append
// deliberately fails closed until a separate native Windows durability gate.
void sync_file(const fs::path& path) {
#if defined(_WIN32)
    (void)path;
    fail("WINDOWS_DURABILITY_NOT_VALIDATED");
#else
    const int fd = ::open(path.c_str(), O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) fail("OPEN_FOR_FSYNC_FAILED");
    int status;
    do { status = ::fsync(fd); } while (status == -1 && errno == EINTR);
    const int close_status = ::close(fd);
    if (status == -1 || close_status != 0) fail("FILE_FSYNC_FAILED");
#endif
}

void sync_directory(const fs::path& path) {
#if defined(_WIN32)
    (void)path;
    fail("WINDOWS_DURABILITY_NOT_VALIDATED");
#else
    const int fd = ::open(path.c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) fail("DIRECTORY_OPEN_FOR_FSYNC_FAILED");
    int status;
    do { status = ::fsync(fd); } while (status == -1 && errno == EINTR);
    const int close_status = ::close(fd);
    if (status == -1 || close_status != 0) fail("DIRECTORY_FSYNC_FAILED");
#endif
}

void commit_noreplace(const fs::path& pending, const fs::path& final_path) {
#if defined(_WIN32)
    (void)pending;
    (void)final_path;
    fail("WINDOWS_DURABILITY_NOT_VALIDATED");
#else
    // link() installs an atomic, no-clobber event name on one local filesystem.
    // A crash between link/unlink leaves both names: inspect() refuses pending
    // debris until an independently authorized reconciliation is completed.
    if (::link(pending.c_str(), final_path.c_str()) != 0)
        fail("ATOMIC_NO_REPLACE_COMMIT_FAILED");
    sync_directory(final_path.parent_path());
    if (::unlink(pending.c_str()) != 0) fail("REMOVE_PENDING_AFTER_COMMIT_FAILED");
    sync_directory(final_path.parent_path());
#endif
}

void assert_safe_directory(const fs::path& root) {
    if (fs::exists(root) && (fs::is_symlink(root) || !fs::is_directory(root)))
        fail("UNSAFE_LEDGER_DIRECTORY");
}

// Only co-operating local processes are serialized; cloud/object-store CAS is a later gate.
struct ScopedLock {
    fs::path lock;
    explicit ScopedLock(const fs::path& root) : lock(root / ".writer_lock") {
        if (!fs::create_directory(lock)) fail("WRITER_LOCK_HELD");
    }
    ~ScopedLock() { std::error_code ec; fs::remove(lock, ec); }
    ScopedLock(const ScopedLock&) = delete;
    ScopedLock& operator=(const ScopedLock&) = delete;
};
} // namespace

ResearchTransitionLedger::ResearchTransitionLedger(fs::path campaign_directory)
    : directory_(std::move(campaign_directory)) {
    if (directory_.empty()) fail("EMPTY_LEDGER_DIRECTORY");
}

ResearchLedgerHead ResearchTransitionLedger::inspect() const {
    assert_safe_directory(directory_);
    ResearchLedgerHead head;
    if (!fs::exists(directory_)) return head;
    std::vector<std::uint64_t> indices;
    for (const auto& file : fs::directory_iterator(directory_)) {
        if (file.path().filename() == ".writer_lock") continue;
        if (file.path().extension() == ".pending") fail("UNRECONCILED_PENDING_EVENT");
        const auto filename = file.path().filename().string();
        if (filename.size() != 20 || filename.substr(16) != ".evt")
            fail("UNKNOWN_LEDGER_ENTRY");
        for (int i = 0; i < 16; ++i)
            if (!std::isdigit(static_cast<unsigned char>(filename[static_cast<std::size_t>(i)])))
                fail("INVALID_EVENT_FILENAME");
        indices.push_back(static_cast<std::uint64_t>(std::stoull(filename.substr(0, 16))));
    }
    std::sort(indices.begin(), indices.end());
    for (const auto index : indices) {
        if (index != head.sequence + 1) fail("LEDGER_SEQUENCE_GAP_OR_DUPLICATE");
        const auto event = parse_event(read_bounded(event_path(directory_, index)));
        if (event.sequence != index || event.previous != head.digest)
            fail("LEDGER_CHAIN_BROKEN");
        if (head.sequence != 0 &&
            (head.project_id != event.project || head.campaign_id != event.campaign))
            fail("LEDGER_CROSS_CAMPAIGN");
        if (event.from != head.state) fail("LEDGER_STATE_CHAIN_BROKEN");
        head.sequence = event.sequence;
        head.digest = event.digest;
        if (event.allowed) head.state = event.requested;
        head.project_id = event.project;
        head.campaign_id = event.campaign;
    }
    return head;
}

ResearchLedgerHead ResearchTransitionLedger::verify_anchor(const ResearchLedgerHead& trusted) const {
    const auto live = inspect();
    if (live.sequence != trusted.sequence || live.digest != trusted.digest ||
        live.state != trusted.state || live.project_id != trusted.project_id ||
        live.campaign_id != trusted.campaign_id)
        fail("TRUSTED_ANCHOR_MISMATCH");
    return live;
}

ResearchLedgerEvent ResearchTransitionLedger::append(const ResearchTransitionRequest& r,
                                                       const ResearchLedgerHead& expected) {
    check_label(r.project_id, "PROJECT");
    check_label(r.campaign_id, "CAMPAIGN");
    check_label(r.authority_ref, "AUTHORITY");
    if (!hex_digest(r.evidence_sha256)) fail("INVALID_EVIDENCE_SHA256");
    if (!hex_digest(expected.digest)) fail("INVALID_EXPECTED_SHA256");
    assert_safe_directory(directory_);
    if (!fs::exists(directory_)) {
        const auto parent = directory_.parent_path();
        if (parent.empty() || !fs::is_directory(parent) || fs::is_symlink(parent))
            fail("INVALID_LEDGER_PARENT");
        if (fs::create_directory(directory_)) sync_directory(parent);
    }
    ScopedLock lock(directory_);
    const auto current = inspect();
    if (current.sequence != expected.sequence || current.digest != expected.digest ||
        current.state != expected.state || current.project_id != expected.project_id ||
        current.campaign_id != expected.campaign_id)
        fail("STALE_CAS_HEAD");
    if (r.from != current.state) fail("REQUEST_STATE_NOT_HEAD");
    if (current.sequence > 0 &&
        (r.project_id != current.project_id || r.campaign_id != current.campaign_id))
        fail("PROJECT_CAMPAIGN_MISMATCH");
    if (current.sequence >= std::numeric_limits<std::uint64_t>::max() - 1)
        fail("SEQUENCE_EXHAUSTED");
    const auto decision = evaluate_scientific_transition(r.from, r.requested, r.actor, r.context);
    Event e;
    e.sequence = current.sequence + 1;
    e.previous = current.digest;
    e.project = r.project_id;
    e.campaign = r.campaign_id;
    e.from = r.from;
    e.requested = r.requested;
    e.actor = r.actor;
    e.context = r.context;
    e.authority = r.authority_ref;
    e.evidence = r.evidence_sha256;
    e.allowed = decision.allowed;
    e.decision = decision.code;
    e.digest = digest_for(e);
    const auto final_path = event_path(directory_, e.sequence);
    const auto pending_path = fs::path(final_path.string() + ".pending");
    if (fs::exists(final_path) || fs::exists(pending_path)) fail("EVENT_ALREADY_EXISTS_OR_PENDING");
    {
        std::ofstream output(pending_path, std::ios::binary | std::ios::trunc);
        if (!output) fail("PENDING_WRITE_FAILED");
        output << canonical(e) << "event_sha256=" << e.digest << "\n";
        output.flush();
        if (!output) fail("PENDING_WRITE_FAILED");
    }
    if (parse_event(read_bounded(pending_path)).digest != e.digest) fail("PENDING_READBACK_FAILED");
    sync_file(pending_path);
    commit_noreplace(pending_path, final_path);
    const auto live = inspect();
    if (live.sequence != e.sequence || live.digest != e.digest)
        fail("COMMITTED_READBACK_FAILED");
    return {live, decision};
}

} // namespace qros::product
