// Stream the canonical ten-volume XAUUSD RAR directly into a full-history
// PACKED17_CENT carrier.  The 28 GB CSV member is never extracted to disk.
//
// Build in the current runtime (libarchive headers are not installed):
//   g++ -O3 -march=native -std=c++20 SOURCE.cpp LIBARCHIVE_SO -o OUTPUT

#define _FILE_OFFSET_BITS 64

#include <array>
#include <cerrno>
#include <charconv>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <string_view>
#include <system_error>
#include <vector>

#include <fcntl.h>
#include <unistd.h>

extern "C" {
struct archive;
struct archive_entry;
using la_int64_t = int64_t;
int archive_read_support_filter_all(archive*);
int archive_read_support_format_rar5(archive*);
archive* archive_read_new(void);
int archive_read_open_filenames(archive*, const char**, size_t);
int archive_read_next_header(archive*, archive_entry**);
int archive_read_data_block(archive*, const void**, size_t*, la_int64_t*);
int archive_read_close(archive*);
int archive_read_free(archive*);
const char* archive_error_string(archive*);
const char* archive_entry_pathname(archive_entry*);
la_int64_t archive_entry_size(archive_entry*);
}

constexpr int ARCHIVE_OK = 0;
constexpr int ARCHIVE_EOF = 1;
constexpr int kVolumes = 10;
constexpr size_t kArchiveBlock = 8 * 1024 * 1024;
constexpr size_t kOutputRecords = 65'536;

#pragma pack(push, 1)
struct Packed17Cent {
  int64_t timestamp_ms;
  int32_t bid_cent;
  int32_t ask_cent;
  uint8_t flags;
};
#pragma pack(pop)
static_assert(sizeof(Packed17Cent) == 17);

int64_t days_from_civil(int year, unsigned month, unsigned day) noexcept {
  year -= month <= 2;
  const int era = (year >= 0 ? year : year - 399) / 400;
  const unsigned yoe = static_cast<unsigned>(year - era * 400);
  const unsigned month_prime = month > 2 ? month - 3 : month + 9;
  const unsigned doy = (153U * month_prime + 2U) / 5U + day - 1U;
  const unsigned doe = yoe * 365U + yoe / 4U - yoe / 100U + doy;
  return static_cast<int64_t>(era) * 146097 + static_cast<int64_t>(doe) - 719468;
}

bool fixed_uint(std::string_view text, int& value) {
  if (text.empty()) return false;
  int result = 0;
  for (const char c : text) {
    if (c < '0' || c > '9') return false;
    result = result * 10 + (c - '0');
  }
  value = result;
  return true;
}

struct DateCache {
  std::array<char, 10> date{};
  bool initialized = false;
  int year = 0;
  int64_t day_ms = 0;

  bool parse(std::string_view text) {
    if (text.size() != 10 || text[4] != '.' || text[7] != '.') return false;
    if (!initialized || std::memcmp(date.data(), text.data(), 10) != 0) {
      int month = 0;
      int day = 0;
      if (!fixed_uint(text.substr(0, 4), year) ||
          !fixed_uint(text.substr(5, 2), month) ||
          !fixed_uint(text.substr(8, 2), day)) return false;
      if (month < 1 || month > 12 || day < 1 || day > 31) return false;
      std::memcpy(date.data(), text.data(), 10);
      initialized = true;
      day_ms = days_from_civil(year, static_cast<unsigned>(month),
                               static_cast<unsigned>(day)) * 86'400'000LL;
    }
    return true;
  }
};

bool parse_time_ms(std::string_view text, int64_t& time_of_day_ms) {
  if (text.size() < 8 || text[2] != ':' || text[5] != ':') return false;
  int hour = 0, minute = 0, second = 0;
  if (!fixed_uint(text.substr(0, 2), hour) ||
      !fixed_uint(text.substr(3, 2), minute) ||
      !fixed_uint(text.substr(6, 2), second)) return false;
  if (hour > 23 || minute > 59 || second > 60) return false;
  int millisecond = 0;
  if (text.size() > 8) {
    if (text[8] != '.') return false;
    const auto fraction = text.substr(9);
    if (fraction.empty() || fraction.size() > 3) return false;
    int parsed = 0;
    if (!fixed_uint(fraction, parsed)) return false;
    millisecond = parsed;
    if (fraction.size() == 1) millisecond *= 100;
    else if (fraction.size() == 2) millisecond *= 10;
  }
  time_of_day_ms = static_cast<int64_t>(hour) * 3'600'000LL +
                   static_cast<int64_t>(minute) * 60'000LL +
                   static_cast<int64_t>(second) * 1'000LL + millisecond;
  return true;
}

// Empty fields are valid sparse updates.  Non-empty values must be exactly
// representable in cents; digits beyond two decimal places may only be zero.
bool parse_price_cent(std::string_view text, bool& present, int32_t& output) {
  present = !text.empty();
  if (!present) return true;
  bool negative = false;
  size_t index = 0;
  if (text[index] == '+' || text[index] == '-') {
    negative = text[index] == '-';
    if (++index == text.size()) return false;
  }
  int64_t whole = 0;
  size_t whole_digits = 0;
  while (index < text.size() && text[index] >= '0' && text[index] <= '9') {
    whole = whole * 10 + (text[index] - '0');
    ++index;
    ++whole_digits;
  }
  if (whole_digits == 0) return false;
  int cents = 0;
  if (index < text.size()) {
    if (text[index++] != '.') return false;
    int fractional_digits = 0;
    while (index < text.size()) {
      const char c = text[index++];
      if (c < '0' || c > '9') return false;
      if (fractional_digits == 0) cents += (c - '0') * 10;
      else if (fractional_digits == 1) cents += c - '0';
      else if (c != '0') return false;
      ++fractional_digits;
    }
    if (fractional_digits == 0) return false;
  }
  int64_t scaled = whole * 100 + cents;
  if (negative) scaled = -scaled;
  if (scaled < std::numeric_limits<int32_t>::min() ||
      scaled > std::numeric_limits<int32_t>::max()) return false;
  output = static_cast<int32_t>(scaled);
  return true;
}

bool parse_flags(std::string_view text, uint8_t& flags) {
  if (text.empty()) return false;
  unsigned value = 0;
  const auto [end, error] = std::from_chars(text.data(), text.data() + text.size(), value);
  if (error != std::errc{} || end != text.data() + text.size() || value > 255) return false;
  flags = static_cast<uint8_t>(value);
  return true;
}

struct State {
  int output_fd = -1;
  std::vector<Packed17Cent> buffer;
  DateCache date_cache;
  bool have_bid = false;
  bool have_ask = false;
  int32_t bid_cent = 0;
  int32_t ask_cent = 0;
  uint64_t source_rows = 0;
  uint64_t records = 0;
  uint64_t pre_bilateral_skipped = 0;
  uint64_t zero_spread = 0;
  uint64_t crossed_spread = 0;
  uint64_t malformed_rows = 0;
  uint64_t out_of_order_rows = 0;
  uint64_t duplicate_timestamps = 0;
  int64_t first_timestamp_ms = -1;
  int64_t last_timestamp_ms = -1;
  int64_t last_raw_timestamp_ms = -1;

  State() { buffer.reserve(kOutputRecords); }

  void flush() {
    const char* data = reinterpret_cast<const char*>(buffer.data());
    size_t bytes = buffer.size() * sizeof(Packed17Cent);
    while (bytes) {
      const ssize_t written = ::write(output_fd, data, bytes);
      if (written < 0) {
        if (errno == EINTR) continue;
        throw std::runtime_error(std::string("output write failed: ") + std::strerror(errno));
      }
      data += written;
      bytes -= static_cast<size_t>(written);
    }
    buffer.clear();
  }

  void emit(const Packed17Cent& record) {
    buffer.push_back(record);
    if (buffer.size() == kOutputRecords) flush();
  }
};

enum class LineResult { kContinue, kMalformed };

LineResult process_line(std::string_view line, State& state) {
  if (!line.empty() && line.back() == '\r') line.remove_suffix(1);
  if (line.empty() || line.front() == '<') return LineResult::kContinue;
  std::array<std::string_view, 7> fields{};
  size_t start = 0;
  int field = 0;
  for (size_t index = 0; index <= line.size(); ++index) {
    if (index == line.size() || line[index] == '\t') {
      if (field >= 7) return LineResult::kMalformed;
      fields[field++] = line.substr(start, index - start);
      start = index + 1;
    }
  }
  if (field != 7) return LineResult::kMalformed;

  if (!state.date_cache.parse(fields[0])) return LineResult::kMalformed;
  int64_t time_of_day_ms = 0;
  if (!parse_time_ms(fields[1], time_of_day_ms)) return LineResult::kMalformed;
  const int64_t timestamp_ms = state.date_cache.day_ms + time_of_day_ms;

  bool bid_present = false, ask_present = false;
  int32_t bid = 0, ask = 0;
  uint8_t flags = 0;
  if (!parse_price_cent(fields[2], bid_present, bid) ||
      !parse_price_cent(fields[3], ask_present, ask) ||
      !parse_flags(fields[6], flags)) return LineResult::kMalformed;
  ++state.source_rows;
  if (state.last_raw_timestamp_ms >= 0) {
    if (timestamp_ms < state.last_raw_timestamp_ms) ++state.out_of_order_rows;
    else if (timestamp_ms == state.last_raw_timestamp_ms) ++state.duplicate_timestamps;
  }
  state.last_raw_timestamp_ms = timestamp_ms;
  if (bid_present) {
    state.bid_cent = bid;
    state.have_bid = true;
  }
  if (ask_present) {
    state.ask_cent = ask;
    state.have_ask = true;
  }
  if (!state.have_bid || !state.have_ask) {
    ++state.pre_bilateral_skipped;
    return LineResult::kContinue;
  }

  state.emit(Packed17Cent{timestamp_ms, state.bid_cent, state.ask_cent, flags});
  if (state.records == 0) state.first_timestamp_ms = timestamp_ms;
  state.last_timestamp_ms = timestamp_ms;
  ++state.records;
  if (state.ask_cent == state.bid_cent) ++state.zero_spread;
  else if (state.ask_cent < state.bid_cent) ++state.crossed_spread;
  if (state.records % 5'000'000ULL == 0) {
    std::cerr << "records=" << state.records << " timestamp_ms=" << timestamp_ms
              << " zero=" << state.zero_spread << " crossed=" << state.crossed_spread
              << "\n";
  }
  return LineResult::kContinue;
}

std::vector<std::string> volume_paths(const std::string& first_volume) {
  const std::string marker = "part01.rar";
  const size_t position = first_volume.rfind(marker);
  if (position == std::string::npos) throw std::runtime_error("first volume must end in part01.rar");
  std::vector<std::string> paths;
  paths.reserve(kVolumes);
  for (int part = 1; part <= kVolumes; ++part) {
    char suffix[32];
    std::snprintf(suffix, sizeof(suffix), "part%02d.rar", part);
    paths.push_back(first_volume.substr(0, position) + suffix);
    if (!std::filesystem::exists(paths.back())) {
      throw std::runtime_error("missing volume: " + paths.back());
    }
  }
  return paths;
}

void write_summary(const std::filesystem::path& path, const std::string& first_volume,
                   const std::filesystem::path& output, const std::string& member,
                   int64_t member_bytes, const State& state, double elapsed_seconds) {
  if (std::filesystem::exists(path)) throw std::runtime_error("summary already exists");
  std::ofstream file(path);
  if (!file) throw std::runtime_error("cannot create summary");
  file << "{\n"
       << "  \"schema\": \"QROS_XAU_PACKED17_CENT_FULL_STREAM_BUILD_1.0\",\n"
       << "  \"version\": \"v1\",\n"
       << "  \"input_first_volume\": \"" << first_volume << "\",\n"
       << "  \"archive_member\": \"" << member << "\",\n"
       << "  \"archive_member_uncompressed_bytes\": " << member_bytes << ",\n"
       << "  \"output\": \"" << output.string() << "\",\n"
       << "  \"coverage_policy\": \"READ_TO_VERIFIED_ARCHIVE_EOF\",\n"
       << "  \"price_unit\": \"integer cents; 1 unit = 0.01 XAUUSD\",\n"
       << "  \"record_layout\": \"little-endian int64 timestamp_ms, int32 bid_cent, int32 ask_cent, uint8 flags\",\n"
       << "  \"source_rows\": " << state.source_rows << ",\n"
       << "  \"records\": " << state.records << ",\n"
       << "  \"bytes\": " << state.records * 17ULL << ",\n"
       << "  \"pre_bilateral_skipped\": " << state.pre_bilateral_skipped << ",\n"
       << "  \"zero_spread\": " << state.zero_spread << ",\n"
       << "  \"crossed_spread\": " << state.crossed_spread << ",\n"
       << "  \"malformed_rows\": " << state.malformed_rows << ",\n"
       << "  \"out_of_order_rows\": " << state.out_of_order_rows << ",\n"
       << "  \"duplicate_timestamps\": " << state.duplicate_timestamps << ",\n"
       << "  \"first_timestamp_ms\": " << state.first_timestamp_ms << ",\n"
       << "  \"last_timestamp_ms\": " << state.last_timestamp_ms << ",\n"
       << "  \"archive_eof_seen\": true,\n"
       << "  \"elapsed_seconds\": " << elapsed_seconds << "\n"
       << "}\n";
}

int main(int argc, char** argv) {
  try {
    if (argc != 4) {
      std::cerr << "usage: " << argv[0] << " FIRST_PART01.rar OUTPUT.bin SUMMARY.json\n";
      return 2;
    }
    const std::string first_volume = argv[1];
    const std::filesystem::path output = argv[2];
    const std::filesystem::path summary = argv[3];
    if (std::filesystem::exists(output) || std::filesystem::exists(summary)) {
      throw std::runtime_error("output or summary already exists");
    }
    const auto paths = volume_paths(first_volume);
    std::vector<const char*> c_paths;
    c_paths.reserve(paths.size() + 1);
    for (const auto& path : paths) c_paths.push_back(path.c_str());
    c_paths.push_back(nullptr);

    const std::filesystem::path partial = output.string() + ".partial";
    if (std::filesystem::exists(partial)) throw std::runtime_error("partial output already exists");
    const int output_fd = ::open(partial.c_str(), O_WRONLY | O_CREAT | O_EXCL, 0644);
    if (output_fd < 0) throw std::runtime_error(std::string("cannot create partial output: ") + std::strerror(errno));

    archive* reader = archive_read_new();
    archive_read_support_filter_all(reader);
    archive_read_support_format_rar5(reader);
    if (archive_read_open_filenames(reader, c_paths.data(), kArchiveBlock) != ARCHIVE_OK) {
      const std::string message = archive_error_string(reader) ? archive_error_string(reader) : "unknown";
      ::close(output_fd);
      throw std::runtime_error("archive open failed: " + message);
    }
    archive_entry* entry = nullptr;
    if (archive_read_next_header(reader, &entry) != ARCHIVE_OK) {
      const std::string message = archive_error_string(reader) ? archive_error_string(reader) : "unknown";
      archive_read_free(reader);
      ::close(output_fd);
      throw std::runtime_error("archive header failed: " + message);
    }
    const std::string member = archive_entry_pathname(entry);
    const int64_t member_bytes = archive_entry_size(entry);
    std::cerr << "archive_member=" << member << " uncompressed_bytes=" << member_bytes << "\n";

    State state;
    state.output_fd = output_fd;
    std::string carry;
    carry.reserve(1024 * 1024);
    const auto started = std::chrono::steady_clock::now();
    while (true) {
      const void* block = nullptr;
      size_t size = 0;
      la_int64_t offset = 0;
      const int status = archive_read_data_block(reader, &block, &size, &offset);
      if (status == ARCHIVE_EOF) break;
      if (status != ARCHIVE_OK) {
        const char* error = archive_error_string(reader);
        throw std::runtime_error(std::string("archive read failed: ") + (error ? error : "UNKNOWN"));
      }
      const char* bytes = static_cast<const char*>(block);
      size_t start = 0;
      for (size_t index = 0; index < size; ++index) {
        if (bytes[index] != '\n') continue;
        LineResult result;
        if (carry.empty()) {
          result = process_line(std::string_view(bytes + start, index - start), state);
        } else {
          carry.append(bytes + start, index - start);
          result = process_line(carry, state);
          carry.clear();
        }
        start = index + 1;
        if (result == LineResult::kMalformed) {
          ++state.malformed_rows;
          throw std::runtime_error("malformed source row near parsed row " +
                                   std::to_string(state.source_rows + 1));
        }
      }
      if (start < size) carry.append(bytes + start, size - start);
    }
    if (!carry.empty()) {
      const LineResult result = process_line(carry, state);
      if (result == LineResult::kMalformed) {
        ++state.malformed_rows;
        throw std::runtime_error("malformed final source row near parsed row " +
                                 std::to_string(state.source_rows + 1));
      }
    }
    state.flush();
    if (::fsync(output_fd) != 0) throw std::runtime_error("fsync failed");
    if (::close(output_fd) != 0) throw std::runtime_error("close failed");
    archive_read_close(reader);
    archive_read_free(reader);
    std::filesystem::rename(partial, output);
    const double elapsed = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - started).count();
    write_summary(summary, first_volume, output, member, member_bytes, state, elapsed);
    std::cerr << "done source_rows=" << state.source_rows << " records=" << state.records
              << " bytes=" << state.records * 17ULL << " zero=" << state.zero_spread
              << " crossed=" << state.crossed_spread << " malformed=" << state.malformed_rows
              << " duplicates=" << state.duplicate_timestamps << " first_ms="
              << state.first_timestamp_ms << " last_ms=" << state.last_timestamp_ms
              << " seconds=" << elapsed << "\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "ERROR: " << error.what() << "\n";
    return 1;
  }
}
