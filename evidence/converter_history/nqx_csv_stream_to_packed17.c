#define _GNU_SOURCE
#define _FILE_OFFSET_BITS 64

#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

/*
 * The runtime provides libarchive.so but not its development headers.  Keep
 * the narrow ABI surface used here explicit so the materializer remains a
 * single, auditable source file.
 */
enum {
    INPUT_BUFFER_BYTES = 8 * 1024 * 1024,
    OUTPUT_RECORDS = 65536,
    MAX_LINE_BYTES = 1024
};

#pragma pack(push, 1)
typedef struct {
    int64_t timestamp_ms;
    int32_t bid_tenth;
    int32_t ask_tenth;
    uint8_t flags;
} Packed17;
#pragma pack(pop)

_Static_assert(sizeof(Packed17) == 17, "Packed17 must be exactly 17 bytes");

typedef struct {
    FILE *out;
    Packed17 output[OUTPUT_RECORDS];
    size_t output_used;
    int have_bid;
    int have_ask;
    int32_t bid_tenth;
    int32_t ask_tenth;
    uint64_t source_rows;
    uint64_t records;
    uint64_t zero_spread;
    uint64_t crossed_spread;
    uint64_t pre_bilateral_skipped;
    uint64_t malformed_rows;
    int64_t first_timestamp_ms;
    int64_t last_timestamp_ms;
    int stop_read;
} State;

static int64_t days_from_civil(int year, unsigned month, unsigned day) {
    year -= month <= 2;
    const int era = (year >= 0 ? year : year - 399) / 400;
    const unsigned yoe = (unsigned)(year - era * 400);
    const unsigned month_prime = month > 2 ? month - 3 : month + 9;
    const unsigned doy = (153U * month_prime + 2U) / 5U + day - 1U;
    const unsigned doe = yoe * 365U + yoe / 4U - yoe / 100U + doy;
    return (int64_t)era * 146097 + (int64_t)doe - 719468;
}

static int parse_fixed_uint(const char *s, size_t n, int *value) {
    int result = 0;
    if (n == 0) {
        return -1;
    }
    for (size_t i = 0; i < n; ++i) {
        if (s[i] < '0' || s[i] > '9') {
            return -1;
        }
        result = result * 10 + (s[i] - '0');
    }
    *value = result;
    return 0;
}

static int parse_timestamp_ms(const char *date, const char *time_text, int64_t *timestamp_ms, int *year_out) {
    if (strlen(date) != 10 || date[4] != '.' || date[7] != '.') {
        return -1;
    }
    if (strlen(time_text) < 8 || time_text[2] != ':' || time_text[5] != ':') {
        return -1;
    }

    int year, month, day, hour, minute, second;
    if (parse_fixed_uint(date, 4, &year) != 0 ||
        parse_fixed_uint(date + 5, 2, &month) != 0 ||
        parse_fixed_uint(date + 8, 2, &day) != 0 ||
        parse_fixed_uint(time_text, 2, &hour) != 0 ||
        parse_fixed_uint(time_text + 3, 2, &minute) != 0 ||
        parse_fixed_uint(time_text + 6, 2, &second) != 0) {
        return -1;
    }

    int millisecond = 0;
    const char *fraction = time_text + 8;
    if (*fraction == '.') {
        ++fraction;
        int digits = 0;
        while (*fraction >= '0' && *fraction <= '9' && digits < 3) {
            millisecond = millisecond * 10 + (*fraction - '0');
            ++fraction;
            ++digits;
        }
        while (digits < 3) {
            millisecond *= 10;
            ++digits;
        }
        if (*fraction != '\0') {
            return -1;
        }
    } else if (*fraction != '\0') {
        return -1;
    }

    if (month < 1 || month > 12 || day < 1 || day > 31 ||
        hour < 0 || hour > 23 || minute < 0 || minute > 59 ||
        second < 0 || second > 60) {
        return -1;
    }

    const int64_t days = days_from_civil(year, (unsigned)month, (unsigned)day);
    *timestamp_ms = days * INT64_C(86400000) +
                    (int64_t)hour * INT64_C(3600000) +
                    (int64_t)minute * INT64_C(60000) +
                    (int64_t)second * INT64_C(1000) + millisecond;
    *year_out = year;
    return 0;
}

static int parse_price_tenth(const char *text, int32_t *value) {
    if (*text == '\0') {
        return 1;
    }

    int sign = 1;
    if (*text == '-') {
        sign = -1;
        ++text;
    } else if (*text == '+') {
        ++text;
    }

    int64_t whole = 0;
    int digits = 0;
    while (*text >= '0' && *text <= '9') {
        whole = whole * 10 + (*text - '0');
        ++text;
        ++digits;
    }
    if (digits == 0) {
        return -1;
    }

    int tenth = 0;
    if (*text == '.') {
        ++text;
        if (*text < '0' || *text > '9') {
            return -1;
        }
        tenth = *text - '0';
        ++text;
        while (*text == '0') {
            ++text;
        }
        if (*text != '\0') {
            return -1;
        }
    } else if (*text != '\0') {
        return -1;
    }

    int64_t scaled = sign * (whole * 10 + tenth);
    if (scaled < INT32_MIN || scaled > INT32_MAX) {
        return -1;
    }
    *value = (int32_t)scaled;
    return 0;
}

static int flush_output(State *state) {
    if (state->output_used == 0) {
        return 0;
    }
    if (fwrite(state->output, sizeof(Packed17), state->output_used, state->out) != state->output_used) {
        return -1;
    }
    state->output_used = 0;
    return 0;
}

static int emit_record(State *state, const Packed17 *record) {
    state->output[state->output_used++] = *record;
    if (state->output_used == OUTPUT_RECORDS && flush_output(state) != 0) {
        return -1;
    }
    return 0;
}

static int process_line(char *line, State *state) {
    size_t len = strlen(line);
    if (len > 0 && line[len - 1] == '\r') {
        line[len - 1] = '\0';
    }
    if (line[0] == '\0' || line[0] == '<') {
        return 0;
    }

    char *fields[7] = {0};
    fields[0] = line;
    size_t field_count = 1;
    for (char *p = line; *p != '\0'; ++p) {
        if (*p == '\t') {
            *p = '\0';
            if (field_count < 7) {
                fields[field_count++] = p + 1;
            }
        }
    }
    if (field_count != 7) {
        ++state->malformed_rows;
        return -1;
    }

    int64_t timestamp_ms;
    int year;
    if (parse_timestamp_ms(fields[0], fields[1], &timestamp_ms, &year) != 0) {
        ++state->malformed_rows;
        return -1;
    }
    (void)year;
    int32_t parsed_price;
    int price_status = parse_price_tenth(fields[2], &parsed_price);
    if (price_status < 0) {
        ++state->malformed_rows;
        return -1;
    }
    if (price_status == 0) {
        state->bid_tenth = parsed_price;
        state->have_bid = 1;
    }

    price_status = parse_price_tenth(fields[3], &parsed_price);
    if (price_status < 0) {
        ++state->malformed_rows;
        return -1;
    }
    if (price_status == 0) {
        state->ask_tenth = parsed_price;
        state->have_ask = 1;
    }

    char *flags_end = NULL;
    errno = 0;
    long flags_long = strtol(fields[6], &flags_end, 10);
    if (errno != 0 || flags_end == fields[6] || *flags_end != '\0' || flags_long < 0 || flags_long > 255) {
        ++state->malformed_rows;
        return -1;
    }

    ++state->source_rows;
    if (!state->have_bid || !state->have_ask) {
        ++state->pre_bilateral_skipped;
        return 0;
    }

    Packed17 record;
    record.timestamp_ms = timestamp_ms;
    record.bid_tenth = state->bid_tenth;
    record.ask_tenth = state->ask_tenth;
    record.flags = (uint8_t)flags_long;
    if (emit_record(state, &record) != 0) {
        return -1;
    }

    if (state->records == 0) {
        state->first_timestamp_ms = timestamp_ms;
    }
    state->last_timestamp_ms = timestamp_ms;
    ++state->records;
    if (state->ask_tenth == state->bid_tenth) {
        ++state->zero_spread;
    } else if (state->ask_tenth < state->bid_tenth) {
        ++state->crossed_spread;
    }

    if (state->records % UINT64_C(5000000) == 0) {
        fprintf(stderr,
                "records=%" PRIu64 " timestamp_ms=%" PRId64 " zero=%" PRIu64 " crossed=%" PRIu64 "\n",
                state->records,
                timestamp_ms,
                state->zero_spread,
                state->crossed_spread);
        fflush(stderr);
    }
    return 0;
}

static int write_summary(const char *summary_path, const char *input_path, const char *output_path,
                         const State *state, uint64_t input_bytes) {
    int fd = open(summary_path, O_WRONLY | O_CREAT | O_EXCL, 0644);
    if (fd < 0) {
        fprintf(stderr, "cannot create summary %s: %s\n", summary_path, strerror(errno));
        return -1;
    }
    FILE *summary = fdopen(fd, "wb");
    if (summary == NULL) {
        close(fd);
        return -1;
    }
    int rc = fprintf(summary,
                     "{\n"
                     "  \"schema\": \"QROS_NQX_PACKED17_FULL_STREAM_BUILD_1.0\",\n"
                     "  \"input_first_volume\": \"%s\",\n"
                     "  \"output\": \"%s\",\n"
                     "  \"coverage_policy\": \"READ_TO_VERIFIED_ARCHIVE_EOF\",\n"
                     "  \"record_layout\": \"little-endian int64 timestamp_ms, int32 bid_tenth, int32 ask_tenth, uint8 flags\",\n"
                     "  \"input_stream_bytes\": %" PRIu64 ",\n"
                     "  \"source_rows\": %" PRIu64 ",\n"
                     "  \"records\": %" PRIu64 ",\n"
                     "  \"bytes\": %" PRIu64 ",\n"
                     "  \"pre_bilateral_skipped\": %" PRIu64 ",\n"
                     "  \"zero_spread\": %" PRIu64 ",\n"
                     "  \"crossed_spread\": %" PRIu64 ",\n"
                     "  \"malformed_rows\": %" PRIu64 ",\n"
                     "  \"first_timestamp_ms\": %" PRId64 ",\n"
                     "  \"last_timestamp_ms\": %" PRId64 "\n"
                     "}\n",
                     input_path,
                     output_path,
                     input_bytes,
                     state->source_rows,
                     state->records,
                     state->records * UINT64_C(17),
                     state->pre_bilateral_skipped,
                     state->zero_spread,
                     state->crossed_spread,
                     state->malformed_rows,
                     state->first_timestamp_ms,
                     state->last_timestamp_ms);
    if (rc < 0 || fclose(summary) != 0) {
        return -1;
    }
    return 0;
}

int main(int argc, char **argv) {
    const uint64_t expected_input_bytes = UINT64_C(24533283398);
    const uint64_t expected_source_rows = UINT64_C(559817687);
    const int64_t expected_first_ms = INT64_C(1516885570165);
    const int64_t expected_last_ms = INT64_C(1785143472709);

    if (argc != 3) {
        fprintf(stderr, "usage: RARDECODE_STREAM | %s OUTPUT.bin SUMMARY.json\n", argv[0]);
        return 2;
    }

    const char *input_path = "STDIN_FROM_RARDECODE_V2_3_0";
    const char *output_path = argv[1];
    const char *summary_path = argv[2];
    char *partial_path = NULL;
    if (asprintf(&partial_path, "%s.partial", output_path) < 0) {
        return 2;
    }

    int output_fd = open(partial_path, O_WRONLY | O_CREAT | O_EXCL, 0644);
    if (output_fd < 0) {
        fprintf(stderr, "cannot create output %s: %s\n", partial_path, strerror(errno));
        free(partial_path);
        return 2;
    }
    FILE *out = fdopen(output_fd, "wb");
    if (out == NULL) {
        fprintf(stderr, "fdopen failed: %s\n", strerror(errno));
        close(output_fd);
        free(partial_path);
        return 2;
    }
    setvbuf(out, NULL, _IOFBF, 16 * 1024 * 1024);

    unsigned char *input_buffer = malloc(INPUT_BUFFER_BYTES);
    if (input_buffer == NULL) {
        fprintf(stderr, "input buffer allocation failed\n");
        fclose(out);
        free(partial_path);
        return 2;
    }

    State state = {0};
    state.out = out;
    char line[MAX_LINE_BYTES];
    size_t line_used = 0;
    uint64_t input_bytes = 0;
    int exit_code = 0;

    while (!state.stop_read) {
        size_t got = fread(input_buffer, 1, INPUT_BUFFER_BYTES, stdin);
        if (got == 0) {
            if (ferror(stdin)) {
                fprintf(stderr, "input stream read failed: %s\n", strerror(errno));
                exit_code = 2;
            }
            break;
        }
        input_bytes += (uint64_t)got;

        for (size_t i = 0; i < got; ++i) {
            unsigned char c = input_buffer[i];
            if (c == '\n') {
                line[line_used] = '\0';
                int rc = process_line(line, &state);
                line_used = 0;
                if (rc < 0) {
                    fprintf(stderr, "invalid input row near source row %" PRIu64 "\n", state.source_rows + 1);
                    exit_code = 2;
                    state.stop_read = 1;
                    break;
                }
            } else {
                if (line_used + 1 >= MAX_LINE_BYTES) {
                    fprintf(stderr, "input line exceeds %d bytes\n", MAX_LINE_BYTES);
                    exit_code = 2;
                    state.stop_read = 1;
                    break;
                }
                line[line_used++] = (char)c;
            }
        }
    }

    if (exit_code == 0 && input_bytes != expected_input_bytes) {
        fprintf(stderr, "input byte mismatch expected=%" PRIu64 " actual=%" PRIu64 "\n",
                expected_input_bytes, input_bytes);
        exit_code = 2;
    }

    if (exit_code == 0 && line_used > 0) {
        line[line_used] = '\0';
        if (process_line(line, &state) != 0) {
            fprintf(stderr, "invalid final input row near source row %" PRIu64 "\n", state.source_rows + 1);
            exit_code = 2;
        }
    }
    if (exit_code == 0 && flush_output(&state) != 0) {
        fprintf(stderr, "output write failed: %s\n", strerror(errno));
        exit_code = 2;
    }
    if (exit_code == 0 && fflush(out) != 0) {
        fprintf(stderr, "output flush failed: %s\n", strerror(errno));
        exit_code = 2;
    }
    if (exit_code == 0 && fsync(fileno(out)) != 0) {
        fprintf(stderr, "output fsync failed: %s\n", strerror(errno));
        exit_code = 2;
    }
    if (fclose(out) != 0 && exit_code == 0) {
        exit_code = 2;
    }

    free(input_buffer);

    if (exit_code == 0 &&
        (state.source_rows != expected_source_rows ||
         state.records != expected_source_rows ||
         state.first_timestamp_ms != expected_first_ms ||
         state.last_timestamp_ms != expected_last_ms)) {
        fprintf(stderr,
                "identity mismatch rows=%" PRIu64 " records=%" PRIu64
                " first_ms=%" PRId64 " last_ms=%" PRId64 "\n",
                state.source_rows, state.records,
                state.first_timestamp_ms, state.last_timestamp_ms);
        exit_code = 2;
    }

    if (exit_code == 0 && rename(partial_path, output_path) != 0) {
        fprintf(stderr, "rename failed: %s\n", strerror(errno));
        exit_code = 2;
    }
    if (exit_code == 0 && write_summary(summary_path, input_path, output_path, &state, input_bytes) != 0) {
        exit_code = 2;
    }

    fprintf(stderr,
            "done source_rows=%" PRIu64 " records=%" PRIu64 " bytes=%" PRIu64
            " zero=%" PRIu64 " crossed=%" PRIu64 " malformed=%" PRIu64
            " first_ms=%" PRId64 " last_ms=%" PRId64 "\n",
            state.source_rows,
            state.records,
            state.records * UINT64_C(17),
            state.zero_spread,
            state.crossed_spread,
            state.malformed_rows,
            state.first_timestamp_ms,
            state.last_timestamp_ms);

    free(partial_path);
    return exit_code;
}
