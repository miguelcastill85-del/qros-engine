#include <cstdint>
#include <deque>

// Minimal analyzer control, deliberately independent of all QROS headers/code.
struct Value {
    std::int64_t value{};
    bool valid{};
    std::uint64_t version{};
};

int main() {
    std::deque<Value> values;
    values.push_back(Value{12, true, 1});
    values.push_back(Value{17, true, 2});
    values.pop_front();
    return values.front().value == 17 ? 0 : 1;
}
