#include "qros/pipeline.hpp"
#include "qros/sha256.hpp"
#include "qros/text_snapshot.hpp"
#include <algorithm>
#include <charconv>
#include <cmath>
#include <iomanip>
#include <limits>
#include <locale>
#include <sstream>
#include <stdexcept>

namespace qros::pipeline {
[[noreturn]] void fail(const std::string& s) { throw std::runtime_error(s); }
i64 integer(const std::string& s) {
    i64 value{};
    const auto [p, error] = std::from_chars(s.data(), s.data()+s.size(), value);
    if (error != std::errc{} || p != s.data()+s.size() || s.empty()) fail("INVALID_INTEGER:"+s);
    return value;
}
u64 natural(const std::string& s) {
    u64 value{};
    const auto [p, error] = std::from_chars(s.data(), s.data()+s.size(), value);
    if (error != std::errc{} || p != s.data()+s.size() || s.empty()) fail("INVALID_UNSIGNED:"+s);
    return value;
}
i64 add(i64 a, i64 b) {
    i64 result{};
    if (__builtin_add_overflow(a,b,&result)) fail("FIXED_POINT_ADD_OVERFLOW");
    return result;
}
i64 sub(i64 a, i64 b) {
    i64 result{};
    if (__builtin_sub_overflow(a,b,&result)) fail("FIXED_POINT_SUB_OVERFLOW");
    return result;
}
i64 mul(i64 a, i64 b) {
    i64 result{};
    if (__builtin_mul_overflow(a,b,&result)) fail("FIXED_POINT_MUL_OVERFLOW");
    return result;
}
bool hash_valid(const std::string& s) {
    return s.size()==64 && std::all_of(s.begin(),s.end(),[](unsigned char c){return (c>='0'&&c<='9')||(c>='a'&&c<='f');});
}
bool identifier(const std::string& s) {
    return !s.empty() && s.size()<=128 && std::all_of(s.begin(),s.end(),[](unsigned char c){return (c>='A'&&c<='Z')||(c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='_'||c=='-';});
}
std::vector<std::string> split(const std::string& s, char separator) {
    std::vector<std::string> parts;
    std::size_t at=0;
    for (;;) {
        const auto end=s.find(separator,at);
        const auto value=s.substr(at,end==std::string::npos?end:end-at);
        if(value.empty()) fail("EMPTY_FIELD");
        parts.push_back(value);
        if(end==std::string::npos) break;
        at=end+1;
    }
    return parts;
}
Fields parse_fields(const std::string& raw, const std::string& magic) {
    if(raw.size()>text_limit || raw.find('\0')!=std::string::npos) fail("TEXT_LIMIT_OR_NUL");
    std::istringstream in(raw);
    std::string line;
    if(!std::getline(in,line)) fail("EMPTY_CONTRACT");
    if(!line.empty()&&line.back()=='\r') line.pop_back();
    if(line!=magic) fail("SCHEMA_MISMATCH:"+magic);
    Fields result;
    while(std::getline(in,line)) {
        if(!line.empty()&&line.back()=='\r') line.pop_back();
        if(line.empty()||line[0]=='#') continue;
        if(line.size()>4096) fail("CONTRACT_LINE_LIMIT");
        const auto at=line.find('=');
        if(at==0||at==std::string::npos||at+1==line.size()) fail("INVALID_CONTRACT_LINE");
        const auto key=line.substr(0,at), value=line.substr(at+1);
        if(!result.emplace(key,value).second) fail("DUPLICATE_KEY:"+key);
        if(result.size()>10000) fail("CONTRACT_KEYS_LIMIT");
    }
    return result;
}
Fields read_fields(const std::filesystem::path& path, const std::string& magic, const std::string& hash) {
    const auto raw=bounded_text(path);
    if(!hash.empty()&&(!hash_valid(hash)||sha256_text(raw)!=hash)) fail("CONTRACT_HASH_MISMATCH");
    return parse_fields(raw,magic);
}
std::string fields_text(const std::string& magic, const Fields& fields) {
    std::string result=magic+"\n";
    for(const auto& [key,value]:fields) {
        if(key.empty()||value.empty()||key.find_first_of("=\r\n")!=std::string::npos||value.find_first_of("\r\n")!=std::string::npos) fail("NON_CANONICAL_FIELD");
        result+=key+"="+value+"\n";
    }
    return result;
}
void exact_keys(const Fields& fields, const std::set<std::string>& keys) {
    for(const auto& [key,value]:fields) { (void)value; if(!keys.contains(key)) fail("UNKNOWN_KEY:"+key); }
    for(const auto& key:keys) if(!fields.contains(key)) fail("MISSING_KEY:"+key);
}
void require_regular_path(const std::filesystem::path& path) {
    auto absolute=std::filesystem::absolute(path).lexically_normal();
    std::filesystem::path part;
    for(const auto& component:absolute) {
        part/=component;
        if(std::filesystem::is_symlink(std::filesystem::symlink_status(part))) fail("SYMLINK_FORBIDDEN");
    }
    if(!std::filesystem::is_regular_file(absolute)) fail("REGULAR_FILE_REQUIRED");
}
std::filesystem::path safe_relative(const std::filesystem::path& root, const std::string& name) {
    const std::filesystem::path p(name);
    if(p.empty()||p.is_absolute()) fail("RELATIVE_INPUT_REQUIRED");
    for(const auto& c:p) if(c==".."||c==".") fail("INPUT_PATH_TRAVERSAL");
    const auto result=root/p;
    require_regular_path(result);
    return result;
}
std::string bounded_text(const std::filesystem::path& path, std::size_t limit) {
    require_regular_path(path);
    return read_stable_text_snapshot(path,limit,limit+1,16384).raw;
}
std::string number(long double value) {
    if(std::isnan(value)) return "UNDEFINED";
    if(std::isinf(value)) return value>0?"INF":"-INF";
    std::ostringstream out;
    out.imbue(std::locale::classic());
    out<<std::setprecision(18)<<value;
    return out.str();
}
} // namespace qros::pipeline
