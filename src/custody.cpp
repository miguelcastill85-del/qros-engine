#include "qros/custody.hpp"
#include "qros/canonical_text.hpp"
#include "qros/sha256.hpp"
#include "qros/text_snapshot.hpp"

#include <algorithm>
#include <array>
#include <cerrno>
#include <charconv>
#include <cctype>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <limits>
#include <set>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#if defined(__linux__)
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#endif

namespace qros {
namespace {

[[noreturn]] void fail(std::string_view text) {
    throw std::runtime_error(std::string(text));
}

[[noreturn]] void fail2(std::string_view a, std::string_view b) {
    CanonicalText out(256); out.append(a); out.append(b); throw std::runtime_error(out.str_ref());
}

std::uint64_t parse_u64(std::string_view s, std::string_view field) {
    std::uint64_t value{};
    const auto [ptr, ec] = std::from_chars(s.data(), s.data() + s.size(), value);
    if (ec != std::errc{} || ptr != s.data() + s.size()) fail2("invalid unsigned integer: ", field);
    return value;
}

std::size_t parse_size(std::string_view s, std::string_view field) {
    const auto value = parse_u64(s, field);
    if (value > static_cast<std::uint64_t>(std::numeric_limits<std::size_t>::max())) fail2("size_t overflow: ", field);
    return static_cast<std::size_t>(value);
}

bool parse_bool01(std::string_view s, std::string_view field) {
    if (s == "0") return false;
    if (s == "1") return true;
    fail2("expected 0/1: ", field);
}

bool lower_hex64(std::string_view s) {
    return s.size() == 64 && std::all_of(s.begin(), s.end(), [](unsigned char c) {
        return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
    });
}

bool safe_id(std::string_view s, std::size_t max_len) {
    if (s.empty() || s.size() > max_len) return false;
    return std::all_of(s.begin(), s.end(), [](unsigned char c) {
        return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') ||
               c == '_' || c == '-' || c == '.' || c == ':' || c == '/';
    });
}

bool safe_basename(std::string_view s) {
    if (s.empty() || s.size() > 255 || s == "." || s == "..") return false;
    if (s.find('/') != std::string_view::npos || s.find('\\') != std::string_view::npos || s.find('\0') != std::string_view::npos) return false;
    if (s.starts_with('.')) return false;
    return std::all_of(s.begin(), s.end(), [](unsigned char c) {
        return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_' || c == '-' || c == '.';
    });
}

std::string ascii_lower(std::string_view s) {
    std::string out; out.reserve(s.size());
    for (char raw : s) {
        unsigned char c = static_cast<unsigned char>(raw);
        if (c >= static_cast<unsigned char>('A') && c <= static_cast<unsigned char>('Z'))
            c = static_cast<unsigned char>(c - static_cast<unsigned char>('A') + static_cast<unsigned char>('a'));
        out.push_back(static_cast<char>(c));
    }
    return out;
}

std::string_view value_after(std::string_view line, std::string_view key) {
    if (!line.starts_with(key)) fail2("expected profile field: ", key);
    return line.substr(key.size());
}

std::vector<std::string> read_profile_lines(const std::filesystem::path& path, std::string& sha) {
    const auto snapshot = read_stable_text_snapshot(path, 1U << 20U, 100000U, 4096U);
    sha = snapshot.sha256;
    return snapshot.lines;
}

CustodyPartSpec parse_part_line(std::string_view line, std::size_t expected_index) {
    if (!line.starts_with("part=")) fail("expected part= record");
    const auto payload = line.substr(5);
    std::array<std::string_view, 4> fields{};
    std::size_t start = 0;
    for (std::size_t i = 0; i < 3; ++i) {
        const auto pos = payload.find(',', start);
        if (pos == std::string_view::npos) fail("part record must have 4 fields");
        fields[i] = payload.substr(start, pos - start);
        start = pos + 1;
    }
    fields[3] = payload.substr(start);
    if (fields[3].find(',') != std::string_view::npos) fail("part record has extra fields");
    const auto idx = parse_size(fields[0], "part.index");
    if (idx != expected_index) fail("part indices must be contiguous and ordered from 1");
    if (!safe_basename(fields[1])) fail("unsafe part basename");
    const auto bytes = parse_u64(fields[2], "part.bytes");
    if (bytes == 0) fail("part bytes must be positive");
    if (!lower_hex64(fields[3])) fail("part sha256 must be lowercase hex64");
    return CustodyPartSpec{idx, std::string(fields[1]), bytes, std::string(fields[3])};
}

struct MeasuredFile {
    bool present{};
    bool regular{};
    bool symlink{};
    bool stable{};
    std::uint64_t bytes{};
    std::string sha256;
#if defined(__linux__)
    std::uint64_t dev{};
    std::uint64_t ino{};
#endif
};

#if defined(__linux__)
MeasuredFile measure_file(const std::filesystem::path& path) {
    MeasuredFile out;
    struct stat lst{};
    if (::lstat(path.c_str(), &lst) != 0) {
        if (errno == ENOENT) return out;
        fail2("lstat failed: ", path.string());
    }
    out.present = true;
    if (S_ISLNK(lst.st_mode)) { out.symlink = true; return out; }
    if (!S_ISREG(lst.st_mode)) { out.regular = false; return out; }
    const int fd = ::open(path.c_str(), O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) fail2("open failed: ", path.string());
    struct stat before{};
    if (::fstat(fd, &before) != 0) { ::close(fd); fail2("fstat failed: ", path.string()); }
    out.regular = S_ISREG(before.st_mode);
    if (!out.regular) { ::close(fd); return out; }
    if (before.st_dev != lst.st_dev || before.st_ino != lst.st_ino) { ::close(fd); return out; }
    if (before.st_size < 0) { ::close(fd); fail("negative file size"); }
    Sha256Builder hasher;
    std::array<unsigned char, 1U << 16U> buffer{};
    std::uint64_t read_total = 0;
    while (true) {
        const auto n = ::read(fd, buffer.data(), buffer.size());
        if (n < 0) {
            if (errno == EINTR) continue;
            ::close(fd); fail2("read failed: ", path.string());
        }
        if (n == 0) break;
        const auto count = static_cast<std::size_t>(n);
        hasher.update(buffer.data(), count);
        if (read_total > std::numeric_limits<std::uint64_t>::max() - static_cast<std::uint64_t>(count)) { ::close(fd); fail("file byte count overflow"); }
        read_total += static_cast<std::uint64_t>(count);
    }
    struct stat after{};
    if (::fstat(fd, &after) != 0) { ::close(fd); fail2("final fstat failed: ", path.string()); }
    if (::close(fd) != 0) fail2("close failed: ", path.string());
    out.bytes = read_total;
    out.sha256 = hasher.finish();
    out.dev = static_cast<std::uint64_t>(before.st_dev);
    out.ino = static_cast<std::uint64_t>(before.st_ino);
    out.stable = before.st_dev == after.st_dev && before.st_ino == after.st_ino && before.st_size == after.st_size &&
                 before.st_mtim.tv_sec == after.st_mtim.tv_sec && before.st_mtim.tv_nsec == after.st_mtim.tv_nsec &&
                 before.st_ctim.tv_sec == after.st_ctim.tv_sec && before.st_ctim.tv_nsec == after.st_ctim.tv_nsec &&
                 read_total == static_cast<std::uint64_t>(before.st_size);
    return out;
}
#else
MeasuredFile measure_file(const std::filesystem::path&) {
    throw std::runtime_error("QROS custody v1 requires Linux O_NOFOLLOW/fstat semantics");
}
#endif

std::pair<std::uint64_t, std::string> hash_concat_files(const SourceCustodyProfile& p, const std::filesystem::path& dir) {
    Sha256Builder hasher;
    std::uint64_t total = 0;
#if defined(__linux__)
    for (const auto& part : p.parts) {
        const auto path = dir / part.name;
        struct stat lst{};
        if (::lstat(path.c_str(), &lst) != 0 || S_ISLNK(lst.st_mode)) fail("concat decoder source is missing or symlink");
        const int fd = ::open(path.c_str(), O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
        if (fd < 0) fail("concat decoder open failed");
        struct stat before{};
        if (::fstat(fd, &before) != 0 || !S_ISREG(before.st_mode) || before.st_dev != lst.st_dev || before.st_ino != lst.st_ino) { ::close(fd); fail("concat decoder source identity mismatch"); }
        std::array<unsigned char, 1U << 16U> buffer{};
        std::uint64_t local = 0;
        while (true) {
            const auto n = ::read(fd, buffer.data(), buffer.size());
            if (n < 0) { if (errno == EINTR) continue; ::close(fd); fail("concat decoder read failed"); }
            if (n == 0) break;
            const auto count = static_cast<std::size_t>(n);
            hasher.update(buffer.data(), count);
            local += static_cast<std::uint64_t>(count);
        }
        struct stat after{};
        if (::fstat(fd, &after) != 0) { ::close(fd); fail("concat decoder final fstat failed"); }
        ::close(fd);
        if (before.st_size < 0 || local != static_cast<std::uint64_t>(before.st_size) || before.st_size != after.st_size ||
            before.st_mtim.tv_sec != after.st_mtim.tv_sec || before.st_mtim.tv_nsec != after.st_mtim.tv_nsec ||
            before.st_ctim.tv_sec != after.st_ctim.tv_sec || before.st_ctim.tv_nsec != after.st_ctim.tv_nsec) fail("concat decoder source changed during read");
        if (total > std::numeric_limits<std::uint64_t>::max() - local) fail("concat decoder byte count overflow");
        total += local;
    }
#else
    (void)p; (void)dir; fail("concat decoder requires Linux custody semantics");
#endif
    return {total, hasher.finish()};
}

void append_kv(CanonicalText& out, std::string_view k, std::string_view v) { out.append(k); out.append(v); out.append('\n'); }
void append_u64(CanonicalText& out, std::string_view k, std::uint64_t v) { out.append(k); out.append_integer(v); out.append('\n'); }
void append_size(CanonicalText& out, std::string_view k, std::size_t v) { out.append(k); out.append_integer(v); out.append('\n'); }
void append_bool(CanonicalText& out, std::string_view k, bool v) { out.append(k); out.append_bool01(v); out.append('\n'); }

} // namespace

std::string custody_chain_root(const std::vector<CustodyPartSpec>& parts) {
    std::string previous(64, '0');
    for (const auto& part : parts) {
        CanonicalText material(512);
        material.append("QROS_CUSTODY_CHAIN_V1\n");
        append_kv(material, "previous_sha256=", previous);
        append_size(material, "index=", part.index);
        append_kv(material, "name=", part.name);
        append_u64(material, "bytes=", part.bytes);
        append_kv(material, "sha256=", part.sha256);
        previous = sha256_text(material.view());
    }
    return previous;
}

SourceCustodyProfile read_source_custody_profile(const std::filesystem::path& path) {
    SourceCustodyProfile p;
    std::string profile_sha;
    const auto lines = read_profile_lines(path, profile_sha);
    if (lines.size() < 13) fail("custody profile too short");
    std::size_t i = 0;
    if (lines[i++] != "QROS_SOURCE_CUSTODY_PROFILE_V1") fail("unexpected custody profile header");
    p.profile_id = std::string(value_after(lines[i++], "profile_id="));
    p.source_id = std::string(value_after(lines[i++], "source_id="));
    p.source_class = std::string(value_after(lines[i++], "source_class="));
    p.namespace_prefix = std::string(value_after(lines[i++], "namespace_prefix="));
    p.parts_count = parse_size(value_after(lines[i++], "parts_count="), "parts_count");
    p.total_bytes = parse_u64(value_after(lines[i++], "total_bytes="), "total_bytes");
    if (p.parts_count == 0 || p.parts_count > 10000) fail("parts_count outside 1..10000");
    if (lines.size() != 13 + p.parts_count) fail("custody profile line count mismatch");
    p.parts.reserve(p.parts_count);
    std::uint64_t total = 0;
    std::set<std::string> exact_names;
    std::set<std::string> folded_names;
    for (std::size_t n = 1; n <= p.parts_count; ++n) {
        auto part = parse_part_line(lines[i++], n);
        if (!part.name.starts_with(p.namespace_prefix)) fail("part name outside declared namespace_prefix");
        if (!exact_names.insert(part.name).second) fail("duplicate part filename");
        if (!folded_names.insert(ascii_lower(part.name)).second) fail("case-fold part filename collision");
        if (total > std::numeric_limits<std::uint64_t>::max() - part.bytes) fail("total_bytes overflow");
        total += part.bytes;
        p.parts.push_back(std::move(part));
    }
    p.decoded_required = parse_bool01(value_after(lines[i++], "decoded_required="), "decoded_required");
    p.decoded_name = std::string(value_after(lines[i++], "decoded_name="));
    p.decoded_bytes = parse_u64(value_after(lines[i++], "decoded_bytes="), "decoded_bytes");
    p.decoded_sha256 = std::string(value_after(lines[i++], "decoded_sha256="));
    p.decoder_id = std::string(value_after(lines[i++], "decoder_id="));
    p.historical_lineage_status = std::string(value_after(lines[i++], "historical_lineage_status="));
    if (i != lines.size()) fail("unexpected custody profile trailing fields");
    if (!safe_id(p.profile_id, 128) || !safe_id(p.source_id, 160) || !safe_id(p.source_class, 128) || !safe_id(p.decoder_id, 192) || !safe_id(p.historical_lineage_status, 128))
        fail("unsafe custody profile identifier");
    if (p.namespace_prefix.empty() || p.namespace_prefix.size() > 200 || p.namespace_prefix.find('/') != std::string::npos || p.namespace_prefix.find('\\') != std::string::npos)
        fail("invalid namespace_prefix");
    if (total != p.total_bytes) fail("sum(part.bytes) does not equal total_bytes");
    if (p.decoded_required) {
        if (!safe_basename(p.decoded_name) || !p.decoded_name.starts_with(p.namespace_prefix)) fail("invalid decoded_name");
        if (p.decoded_bytes == 0 || !lower_hex64(p.decoded_sha256)) fail("decoded contract invalid");
        if (!folded_names.insert(ascii_lower(p.decoded_name)).second) fail("decoded filename collides with part filename");
    } else {
        if (p.decoded_name != "NONE" || p.decoded_bytes != 0 || p.decoded_sha256 != std::string(64, '0')) fail("decoded_required=0 requires NONE/0/zero-hash");
    }
    p.profile_sha256 = profile_sha;
    p.expected_chain_root_sha256 = custody_chain_root(p.parts);
    return p;
}

std::string source_custody_profile_receipt(const SourceCustodyProfile& p) {
    CanonicalText out(1024);
    out.append("QROS_SOURCE_CUSTODY_PROFILE_RECEIPT_V1\n");
    append_kv(out, "profile_id=", p.profile_id);
    append_kv(out, "source_id=", p.source_id);
    append_kv(out, "source_class=", p.source_class);
    append_kv(out, "profile_sha256=", p.profile_sha256);
    append_size(out, "parts_count=", p.parts_count);
    append_u64(out, "total_bytes=", p.total_bytes);
    append_kv(out, "expected_chain_root_sha256=", p.expected_chain_root_sha256);
    append_bool(out, "decoded_required=", p.decoded_required);
    append_kv(out, "decoded_name=", p.decoded_name);
    append_u64(out, "decoded_bytes=", p.decoded_bytes);
    append_kv(out, "decoded_sha256=", p.decoded_sha256);
    append_kv(out, "decoder_id=", p.decoder_id);
    append_kv(out, "historical_lineage_status=", p.historical_lineage_status);
    append_kv(out, "status=", "PROFILE_VALID_BYTES_NOT_MEASURED");
    return std::move(out).take();
}

SourceCustodyAudit audit_source_custody(const SourceCustodyProfile& p, const std::filesystem::path& source_directory) {
    SourceCustodyAudit a;
    a.profile_valid = true;
    const auto ds = std::filesystem::symlink_status(source_directory);
    if (!std::filesystem::exists(ds) || !std::filesystem::is_directory(ds) || std::filesystem::is_symlink(ds)) fail("source_directory must be a real directory, not a symlink");

    std::set<std::string> allowed;
    std::set<std::string> folded;
    for (const auto& part : p.parts) { allowed.insert(part.name); folded.insert(ascii_lower(part.name)); }
    if (p.decoded_required) { allowed.insert(p.decoded_name); folded.insert(ascii_lower(p.decoded_name)); }
    std::set<std::string> observed_folded;
    for (const auto& entry : std::filesystem::directory_iterator(source_directory)) {
        const auto name = entry.path().filename().string();
        if (!name.starts_with(p.namespace_prefix)) continue;
        if (!observed_folded.insert(ascii_lower(name)).second) ++a.casefold_collisions;
        if (!allowed.contains(name)) ++a.unexpected_namespace_files;
    }

    std::vector<CustodyPartSpec> measured_parts;
    measured_parts.reserve(p.parts.size());
#if defined(__linux__)
    std::set<std::pair<std::uint64_t, std::uint64_t>> inodes;
#endif
    for (const auto& part : p.parts) {
        const auto mf = measure_file(source_directory / part.name);
        if (!mf.present) { ++a.missing_files; continue; }
        ++a.parts_seen;
        if (mf.symlink) { ++a.symlinks_rejected; continue; }
        if (!mf.regular) { ++a.non_regular_files; continue; }
        if (!mf.stable) { ++a.unstable_files; continue; }
#if defined(__linux__)
        if (!inodes.insert({mf.dev, mf.ino}).second) ++a.inode_aliases;
#endif
        if (mf.bytes != part.bytes) ++a.wrong_size;
        if (mf.sha256 != part.sha256) ++a.wrong_hash;
        if (a.measured_total_bytes > std::numeric_limits<std::uint64_t>::max() - mf.bytes) fail("measured total overflow");
        a.measured_total_bytes += mf.bytes;
        measured_parts.push_back(CustodyPartSpec{part.index, part.name, mf.bytes, mf.sha256});
    }
    a.parts_complete = a.parts_seen == p.parts_count && a.missing_files == 0;
    if (measured_parts.size() == p.parts.size()) a.measured_chain_root_sha256 = custody_chain_root(measured_parts);
    else a.measured_chain_root_sha256 = std::string(64, '0');
    a.archive_custody_verified = a.parts_complete && a.wrong_size == 0 && a.wrong_hash == 0 && a.non_regular_files == 0 &&
        a.symlinks_rejected == 0 && a.unstable_files == 0 && a.inode_aliases == 0 && a.unexpected_namespace_files == 0 &&
        a.casefold_collisions == 0 && a.measured_total_bytes == p.total_bytes && a.measured_chain_root_sha256 == p.expected_chain_root_sha256;

    if (p.decoded_required) {
        const auto mf = measure_file(source_directory / p.decoded_name);
        a.decoded_present = mf.present;
        if (mf.present && mf.symlink) ++a.symlinks_rejected;
        else if (mf.present && !mf.regular) ++a.non_regular_files;
        else if (mf.present && !mf.stable) ++a.unstable_files;
        else if (mf.present) {
#if defined(__linux__)
            if (!inodes.insert({mf.dev, mf.ino}).second) ++a.inode_aliases;
#endif
            a.decoded_size_match = mf.bytes == p.decoded_bytes;
            a.decoded_measured_sha256 = mf.sha256;
            a.decoded_hash_match = mf.sha256 == p.decoded_sha256;
        }
        a.decoded_bytes_verified = a.decoded_present && a.decoded_size_match && a.decoded_hash_match && a.symlinks_rejected == 0 && a.non_regular_files == 0 && a.unstable_files == 0 && a.inode_aliases == 0;
    } else {
        a.decoded_bytes_verified = true;
        a.decoded_size_match = true;
        a.decoded_hash_match = true;
        a.decoded_measured_sha256 = std::string(64, '0');
    }
    // A built-in deterministic concat decoder exists only to prove the lineage contract end-to-end
    // on synthetic fixtures. Production archive formats (e.g. RAR5) remain fail-closed until their
    // exact decoder is sandboxed, hashed and replayed by QROS.
    if (a.archive_custody_verified && a.decoded_bytes_verified && p.decoder_id == "QROS_CONCAT_V1") {
        const auto [concat_bytes, concat_sha] = hash_concat_files(p, source_directory);
        a.decode_lineage_verified = concat_bytes == p.decoded_bytes && concat_sha == p.decoded_sha256;
    } else {
        a.decode_lineage_verified = false;
    }
    a.source_provenance_ready = a.archive_custody_verified && a.decoded_bytes_verified && a.decode_lineage_verified;
    // V1 has no production decoder executor. Production readiness is therefore fail-closed.
    a.production_source_provenance_ready = false;
    {
        CanonicalText evidence(768);
        evidence.append("QROS_CUSTODY_EVIDENCE_ROOT_V1\n");
        append_kv(evidence, "profile_sha256=", p.profile_sha256);
        append_kv(evidence, "source_class=", p.source_class);
        append_kv(evidence, "measured_chain_root_sha256=", a.measured_chain_root_sha256);
        if (a.decoded_measured_sha256.empty()) append_kv(evidence, "decoded_measured_sha256=", std::string_view{"0000000000000000000000000000000000000000000000000000000000000000"});
        else append_kv(evidence, "decoded_measured_sha256=", a.decoded_measured_sha256);
        append_bool(evidence, "archive_custody_verified=", a.archive_custody_verified);
        append_bool(evidence, "decoded_bytes_verified=", a.decoded_bytes_verified);
        append_bool(evidence, "decode_lineage_verified=", a.decode_lineage_verified);
        append_bool(evidence, "production_source_provenance_ready=", a.production_source_provenance_ready);
        a.custody_evidence_root_sha256 = sha256_text(evidence.view());
    }
    if (!a.archive_custody_verified) a.status = "FAIL_ARCHIVE_CUSTODY";
    else if (!a.decoded_bytes_verified) a.status = "ARCHIVE_VERIFIED_DECODED_BYTES_FAIL";
    else if (!a.decode_lineage_verified) a.status = "BYTES_VERIFIED_DECODE_LINEAGE_PENDING";
    else if (!a.production_source_provenance_ready) a.status = "TEST_PROVENANCE_READY";
    else a.status = "SOURCE_PROVENANCE_READY";
    return a;
}

std::string source_custody_receipt(const SourceCustodyProfile& p,
                                   const SourceCustodyAudit& a,
                                   std::string_view entrypoint_sha256,
                                   std::string_view source_root_sha256,
                                   std::string_view build_contract_sha256,
                                   std::string_view engine_version) {
    CanonicalText out(2048);
    out.append("QROS_SOURCE_CUSTODY_RECEIPT_V1\n");
    append_kv(out, "engine_version=", engine_version);
    append_kv(out, "source_root_sha256=", source_root_sha256);
    append_kv(out, "build_contract_sha256=", build_contract_sha256);
    append_kv(out, "entrypoint_sha256=", entrypoint_sha256);
    append_kv(out, "profile_id=", p.profile_id);
    append_kv(out, "source_id=", p.source_id);
    append_kv(out, "source_class=", p.source_class);
    append_kv(out, "profile_sha256=", p.profile_sha256);
    append_kv(out, "expected_chain_root_sha256=", p.expected_chain_root_sha256);
    append_kv(out, "measured_chain_root_sha256=", a.measured_chain_root_sha256);
    append_size(out, "parts_expected=", p.parts_count);
    append_size(out, "parts_seen=", a.parts_seen);
    append_u64(out, "expected_total_bytes=", p.total_bytes);
    append_u64(out, "measured_total_bytes=", a.measured_total_bytes);
    append_size(out, "missing_files=", a.missing_files);
    append_size(out, "wrong_size=", a.wrong_size);
    append_size(out, "wrong_hash=", a.wrong_hash);
    append_size(out, "non_regular_files=", a.non_regular_files);
    append_size(out, "symlinks_rejected=", a.symlinks_rejected);
    append_size(out, "unstable_files=", a.unstable_files);
    append_size(out, "inode_aliases=", a.inode_aliases);
    append_size(out, "unexpected_namespace_files=", a.unexpected_namespace_files);
    append_size(out, "casefold_collisions=", a.casefold_collisions);
    append_kv(out, "custody_evidence_root_sha256=", a.custody_evidence_root_sha256);
    append_bool(out, "archive_custody_verified=", a.archive_custody_verified);
    append_bool(out, "decoded_present=", a.decoded_present);
    append_bool(out, "decoded_size_match=", a.decoded_size_match);
    append_bool(out, "decoded_hash_match=", a.decoded_hash_match);
    if (a.decoded_measured_sha256.empty()) append_kv(out, "decoded_measured_sha256=", std::string_view{"0000000000000000000000000000000000000000000000000000000000000000"});
    else append_kv(out, "decoded_measured_sha256=", a.decoded_measured_sha256);
    append_bool(out, "decoded_bytes_verified=", a.decoded_bytes_verified);
    append_bool(out, "decode_lineage_verified=", a.decode_lineage_verified);
    append_bool(out, "source_provenance_ready=", a.source_provenance_ready);
    append_bool(out, "production_source_provenance_ready=", a.production_source_provenance_ready);
    append_kv(out, "status=", a.status);
    return std::move(out).take();
}

} // namespace qros
