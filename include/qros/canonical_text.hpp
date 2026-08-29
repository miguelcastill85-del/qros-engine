#pragma once

#include <charconv>
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <string_view>
#include <type_traits>

namespace qros {

// Locale-free deterministic text builder for hashes, ledgers, manifests and receipts.
class CanonicalText {
public:
    explicit CanonicalText(std::size_t reserve_bytes = 256) { data_.reserve(reserve_bytes); }

    void append(std::string_view s) { data_.append(s.data(), s.size()); }
    void append(char c) { data_.push_back(c); }

    template <typename T>
    void append_integer(T value) {
        static_assert(std::is_integral_v<T> && !std::is_same_v<T, bool>);
        char buf[64];
        auto [ptr, ec] = std::to_chars(buf, buf + sizeof(buf), value);
        if (ec != std::errc{}) throw std::runtime_error("canonical integer conversion failed");
        data_.append(buf, static_cast<std::size_t>(ptr - buf));
    }

    void append_bool01(bool value) { data_.push_back(value ? '1' : '0'); }
    std::string_view view() const noexcept { return data_; }
    const std::string& str_ref() const noexcept { return data_; }
    std::string take() && { return std::move(data_); }

private:
    std::string data_;
};

} // namespace qros
