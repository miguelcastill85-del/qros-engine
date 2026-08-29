#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <string>
#include <string_view>

namespace qros {

class Sha256Builder {
public:
    Sha256Builder();
    void update(const void* data, std::size_t size);
    void update(std::string_view text);
    std::string finish();
private:
    using u32 = std::uint32_t;
    using u64 = std::uint64_t;
    std::array<u32, 8> h_{};
    std::array<std::uint8_t, 64> buf_{};
    std::size_t used_{};
    u64 total_{};
    bool finished_{};
    void block(const std::uint8_t* p);
};

std::string sha256_file(const std::filesystem::path& path);
std::string sha256_text(std::string_view text);

} // namespace qros
