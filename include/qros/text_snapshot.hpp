#pragma once

#include <cstddef>
#include <filesystem>
#include <string>
#include <vector>

namespace qros {

struct StableTextSnapshot {
    std::string raw;
    std::vector<std::string> lines;
    std::string sha256;
};

// Reads and hashes the exact same file descriptor. On Linux this rejects symlinks,
// non-regular files and files whose inode/size/mtime/ctime changes during the read.
// The byte and line limits are fail-closed resource bounds, not truncation limits.
StableTextSnapshot read_stable_text_snapshot(const std::filesystem::path& path,
                                             std::size_t max_bytes,
                                             std::size_t max_lines,
                                             std::size_t max_line_bytes);

} // namespace qros
