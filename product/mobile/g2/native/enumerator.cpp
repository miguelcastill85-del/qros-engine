// Independently authored finite synthetic mixed-radix enumerator.
// No market data, simulation, dynamic code, financial results, or scientific authority.
#include <array>
#include <charconv>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <limits>
#include <set>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace {
using Axes = std::array<std::vector<std::string>, 6>;
const std::array<std::string, 6> keys = {
    "sides", "timeframes", "lookback_bars", "confirmation_bars", "stop_ratios", "maximum_holding_bars"};
const std::array<std::set<std::string>, 6> allowed = {{
    {"BUY", "SELL"}, {"M5", "M15"}, {"5", "10", "15"}, {"1", "2"},
    {"1/1", "2/1", "3/2"}, {"8", "12"}}};
struct Spec { std::string symbol; Axes axes; std::uint64_t births = 1; };
[[noreturn]] void fail(const std::string& message) {throw std::runtime_error("G2_FAIL_CLOSED:" + message);}
std::uint64_t number(std::string_view s) {
    if (s.empty() || (s.size() > 1 && s.front() == '0')) fail("NONCANONICAL_INTEGER");
    std::uint64_t out = 0;
    auto [p, ec] = std::from_chars(s.data(), s.data() + s.size(), out);
    if (ec != std::errc{} || p != s.data() + s.size()) fail("BAD_INTEGER");
    return out;
}
std::vector<std::string> split(const std::string& s) {
    if (s.empty()) fail("EMPTY_AXIS");
    std::vector<std::string> out;
    std::size_t start = 0;
    while (true) {
        const auto p = s.find(',', start);
        auto v = s.substr(start, p == std::string::npos ? p : p - start);
        if (v.empty()) fail("EMPTY_TOKEN");
        out.push_back(std::move(v));
        if (p == std::string::npos) break;
        start = p + 1;
    }
    return out;
}
Spec read_spec(const std::string& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) fail("SPEC_MISSING");
    std::string line;
    if (!std::getline(in, line) || line != "QROS_G2_SYNTHETIC_SPEC_V1") fail("BAD_SCHEMA");
    if (!std::getline(in, line) || (line != "symbol=SIM_XAUUSD" && line != "symbol=SIM_NQX")) fail("INVALID_SYMBOL");
    Spec s; s.symbol = line.substr(7);
    for (std::size_t i = 0; i < 6; ++i) {
        if (!std::getline(in, line) || line.rfind(keys[i] + "=", 0) != 0) fail("INVALID_AXIS_ORDER");
        s.axes[i] = split(line.substr(keys[i].size() + 1));
        std::set<std::string> seen;
        for (auto const& token : s.axes[i]) {
            if (!allowed[i].contains(token)) fail("DISALLOWED_AXIS_VALUE");
            if (!seen.insert(token).second) fail("DUPLICATE_AXIS_VALUE");
        }
        for (std::size_t j = 1; j < s.axes[i].size(); ++j) {
            if (i == 2 || i == 3 || i == 5) {
                if (number(s.axes[i][j]) < number(s.axes[i][j-1])) fail("UNSORTED_AXIS");
            } else if (s.axes[i][j] < s.axes[i][j-1]) fail("UNSORTED_AXIS");
        }
        if (s.births > 1'000'000 / s.axes[i].size()) fail("MAX_G1_BIRTHS_EXCEEDED");
        s.births *= s.axes[i].size();
    }
    if (!std::getline(in, line) || line.rfind("raw_births=", 0) != 0 || number(line.substr(11)) != s.births)
        fail("BIRTH_COUNT_DRIFT");
    if (std::getline(in, line)) fail("TRAILING_FIELDS");
    return s;
}
std::string row(const std::string& symbol, const Axes& axes, std::uint64_t rank) {
    std::array<std::size_t, 6> index{};
    for (std::size_t k = 6; k > 0; --k) {
        const auto i = k - 1;
        index[i] = static_cast<std::size_t>(rank % axes[i].size());
        rank /= axes[i].size();
    }
    std::string id = symbol;
    for (std::size_t i = 0; i < 6; ++i) id += "|" + axes[i][index[i]];
    return id;
}
}
int main(int argc, char** argv) {
    try {
        std::string spec_path;
        bool stress = false;
        bool count_only = false;
        std::uint64_t start = 0, count = std::numeric_limits<std::uint64_t>::max();
        bool explicit_count = false;
        for (int i = 1; i < argc; ++i) {
            const std::string a = argv[i];
            if (a == "--spec" && i + 1 < argc) spec_path = argv[++i];
            else if (a == "--synthetic-stress") stress = true;
            else if (a == "--start" && i + 1 < argc) start = number(argv[++i]);
            else if (a == "--count" && i + 1 < argc) {count = number(argv[++i]); explicit_count = true;}
            else if (a == "--count-only") count_only = true;
            else fail("UNKNOWN_ARGUMENT");
        }
        if (stress == !spec_path.empty()) fail("CHOOSE_EXACTLY_ONE_MODE");
        Spec s;
        if (stress) {
            s.symbol = "SYNTHETIC_STRESS_NOT_G1";
            for (auto& axis : s.axes) for (int i = 0; i < 10; ++i) axis.push_back(std::to_string(i));
            s.births = 1'000'000;
        } else s = read_spec(spec_path);
        if (count_only) { std::cout << s.births << '\n'; return 0; }
        if (start > s.births) fail("START_OUT_OF_RANGE");
        const std::uint64_t remaining = s.births - start;
        if (count > remaining) {
            if (explicit_count) fail("COUNT_OUT_OF_RANGE");
            count = remaining;
        }
        for (std::uint64_t i = 0; i < count; ++i) {
            std::cout << row(s.symbol, s.axes, start+i) << '\n';
            if (!std::cout) fail("WRITE_ERROR");
        }
        return 0;
    } catch (std::exception const& e) {std::cerr << e.what() << '\n'; return 2;}
}
