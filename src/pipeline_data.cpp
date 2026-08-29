#include "qros/pipeline.hpp"
#include "qros/sha256.hpp"
#include <array>
#include <bit>
#include <cerrno>
#include <chrono>
#include <cstring>
#include <fcntl.h>
#include <limits>
#include <sstream>
#include <sys/stat.h>
#include <unistd.h>

namespace qros::pipeline {
namespace {
class BoundStream {
public:
    explicit BoundStream(const std::filesystem::path& p) {
        require_regular_path(p);
        fd_=::open(p.c_str(),O_RDONLY|O_NOFOLLOW|O_CLOEXEC);
        if(fd_<0) fail("INPUT_OPEN_FAILED");
        if(::fstat(fd_,&before_)!=0||!S_ISREG(before_.st_mode)) { ::close(fd_); fd_=-1; fail("INPUT_STAT_FAILED"); }
    }
    ~BoundStream(){ if(fd_>=0) ::close(fd_); }
    BoundStream(const BoundStream&)=delete;
    BoundStream& operator=(const BoundStream&)=delete;
    bool byte(unsigned char& out) {
        if(at_==end_) {
            ssize_t n;
            do { n=::read(fd_,buffer_.data(),buffer_.size()); } while(n<0&&errno==EINTR);
            if(n<0) fail("INPUT_READ_FAILED");
            if(n==0) return false;
            at_=0;end_=static_cast<std::size_t>(n);hash_.update(buffer_.data(),end_);
        }
        out=buffer_[at_++];return true;
    }
    bool line(std::string& out) {
        out.clear();unsigned char c{};bool any=false;
        while(byte(c)) {
            any=true;if(c=='\n') break;
            if(c==0||out.size()>=4096) fail("CSV_LINE_LIMIT_OR_NUL");
            out.push_back(static_cast<char>(c));
        }
        if(!out.empty()&&out.back()=='\r') out.pop_back();
        return any;
    }
    bool packed(std::array<unsigned char,17>& out) {
        if(!byte(out[0])) return false;
        for(std::size_t i=1;i<out.size();++i) if(!byte(out[i])) fail("TRUNCATED_PACKED17");
        return true;
    }
    std::string finish(const std::string& expected) {
        unsigned char extra{};
        if(byte(extra)) fail("INPUT_NOT_FULLY_CONSUMED");
        struct stat after{};
        if(::fstat(fd_,&after)!=0||before_.st_dev!=after.st_dev||before_.st_ino!=after.st_ino||before_.st_size!=after.st_size||
           before_.st_mtim.tv_sec!=after.st_mtim.tv_sec||before_.st_mtim.tv_nsec!=after.st_mtim.tv_nsec||
           before_.st_ctim.tv_sec!=after.st_ctim.tv_sec||before_.st_ctim.tv_nsec!=after.st_ctim.tv_nsec) fail("INPUT_CHANGED_DURING_READ");
        const auto h=hash_.finish();
        if(!hash_valid(expected)||h!=expected) fail("DATA_AUTHORITY_HASH_MISMATCH");
        return h;
    }
private:
    int fd_{-1};struct stat before_{};Sha256Builder hash_;
    std::array<unsigned char,65536> buffer_{};std::size_t at_{},end_{};
};
i64 little64(const unsigned char* p) {
    u64 x=0;for(unsigned i=0;i<8;++i) x|=static_cast<u64>(p[i])<<(8U*i);
    return std::bit_cast<i64>(x);
}
i64 little32(const unsigned char* p) {
    std::uint32_t x=0;for(unsigned i=0;i<4;++i) x|=static_cast<std::uint32_t>(p[i])<<(8U*i);
    return static_cast<i64>(std::bit_cast<std::int32_t>(x));
}
bool date_valid(i64 day) {
    if(day<19700101||day>22001231) return false;
    const std::chrono::year_month_day d{std::chrono::year(static_cast<int>(day/10000)),
        std::chrono::month(static_cast<unsigned>((day/100)%100)),std::chrono::day(static_cast<unsigned>(day%100))};
    return d.ok();
}
std::string contract_root(Fields f) {
    f.erase("shard_contract_root");
    return sha256_text(fields_text("QROS_SHARD_CONTRACT_V3",f));
}
std::vector<SessionBoundary> sessions_from_text(const std::string& text) {
    std::istringstream in(text);std::string line;
    if(!std::getline(in,line)||line!="session_day,open_seq,close_seq,open_ts_ns,close_ts_ns,utc_offset_seconds") fail("SESSION_HEADER");
    std::vector<SessionBoundary> out;
    while(std::getline(in,line)) {
        if(!line.empty()&&line.back()=='\r') line.pop_back();
        const auto c=split(line,',');if(c.size()!=6) fail("SESSION_COLUMNS");
        SessionBoundary s{integer(c[0]),natural(c[1]),natural(c[2]),integer(c[3]),integer(c[4]),integer(c[5])};
        if(!date_valid(s.session_day)||s.open_seq==0||s.close_seq<s.open_seq||s.open_ts_ns<=0||s.close_ts_ns<s.open_ts_ns||s.utc_offset_seconds < -50400 ||s.utc_offset_seconds>50400) fail("SESSION_RANGE");
        if(!out.empty()&&(s.session_day<=out.back().session_day||s.open_seq!=out.back().close_seq+1||s.open_ts_ns<out.back().close_ts_ns)) fail("SESSION_ORDER_OR_GAP");
        out.push_back(s);if(out.size()>1000000) fail("SESSION_LIMIT");
    }
    if(out.empty()) fail("EMPTY_SESSIONS");
    return out;
}
}

DataSpec read_data_spec(const std::filesystem::path& path, const std::string& expected_sha) {
    if(!hash_valid(expected_sha)) fail("EXPECTED_DATA_SPEC_HASH_REQUIRED");
    DataSpec s;s.fields=read_fields(path,"QROS_DATASET_V3",expected_sha);s.sha256=expected_sha;s.root=path.parent_path();
    const auto& f=s.fields;
    exact_keys(f,{"authority_id","symbol","purpose","format","source_clock","exposure","broker_origin",
        "ticks_path","ticks_sha256","sessions_path","sessions_sha256","rows","first_seq","first_day","last_day",
        "tick_size_u","point_size_u","price_decimals","parent_carrier_sha256","session_fragment_sha256","shard_contract_root"});
    s.authority_id=f.at("authority_id");s.symbol=f.at("symbol");s.purpose=f.at("purpose");s.format=f.at("format");
    s.source_clock=f.at("source_clock");s.exposure=f.at("exposure");
    s.ticks_name=f.at("ticks_path");s.ticks_sha=f.at("ticks_sha256");s.sessions_name=f.at("sessions_path");s.sessions_sha=f.at("sessions_sha256");
    s.rows=natural(f.at("rows"));s.first_seq=natural(f.at("first_seq"));s.first_day=integer(f.at("first_day"));s.last_day=integer(f.at("last_day"));
    s.tick_size_u=integer(f.at("tick_size_u"));s.point_size_u=integer(f.at("point_size_u"));s.price_decimals=integer(f.at("price_decimals"));
    if(!identifier(s.authority_id)||(s.symbol!="NQX"&&s.symbol!="XAUUSD")) fail("DATA_ID_OR_SYMBOL");
    if(s.purpose!="TEST_ONLY"&&s.purpose!="RESEARCH") fail("DATA_PURPOSE");
    if(s.format!="CSV5"&&s.format!="PACKED17") fail("DATA_FORMAT");
    if(s.source_clock!="DARWINEX_SERVER_WALL"&&s.source_clock!="UTC"&&s.source_clock!="SYNTHETIC") fail("CLOCK_DOMAIN_REQUIRED");
    if(s.exposure!="SYNTHETIC"&&s.exposure!="DEVELOPMENT_EXPOSED"&&s.exposure!="HOLDOUT_SEALED") fail("EXPOSURE_REQUIRED");
    if((s.purpose=="TEST_ONLY")!=(s.exposure=="SYNTHETIC")) fail("TEST_EXPOSURE_MISMATCH");
    if(f.at("broker_origin")!="DARWINEX_USER_CONFIRMED"&&f.at("broker_origin")!="SYNTHETIC") fail("SOURCE_ORIGIN_REQUIRED");
    if(!hash_valid(s.ticks_sha)||!hash_valid(s.sessions_sha)||!hash_valid(f.at("parent_carrier_sha256"))) fail("DATA_HASH_FORMAT");
    if(f.at("session_fragment_sha256")!=s.sessions_sha||f.at("shard_contract_root")!=contract_root(f)) fail("SHARD_CONTRACT_BINDING");
    if(s.rows==0||s.rows>1000000000000ULL||s.first_seq==0||s.first_seq>std::numeric_limits<u64>::max()-s.rows) fail("DATA_COUNT_RANGE");
    if(!date_valid(s.first_day)||!date_valid(s.last_day)||s.first_day>s.last_day||s.tick_size_u<=0||s.point_size_u<=0||s.price_decimals<0||s.price_decimals>9) fail("DATA_SCALE_OR_EXTENT");
    const auto raw=bounded_text(safe_relative(s.root,s.sessions_name));
    if(sha256_text(raw)!=s.sessions_sha) fail("SESSION_HASH_MISMATCH");
    s.sessions=sessions_from_text(raw);
    if(s.sessions.front().session_day!=s.first_day||s.sessions.back().session_day!=s.last_day||s.sessions.front().open_seq!=s.first_seq||s.sessions.back().close_seq!=s.first_seq+s.rows-1) fail("SESSION_EXTENT_MISMATCH");
    return s;
}

DataReceipt walk_data(const DataSpec& s,const std::function<void(const Tick&,const SessionBoundary&)>& visit,bool executable,u64 max_rows) {
    if(s.rows>max_rows) fail("RESOURCE_ROW_BUDGET_EXCEEDED");
    BoundStream in(safe_relative(s.root,s.ticks_name));DataReceipt r;std::string line;
    if(s.format=="CSV5"&&(!in.line(line)||line!="seq,ts_ns,session_day,bid_u,ask_u")) fail("TICK_HEADER");
    std::array<unsigned char,17> bytes{};std::size_t si=0;Tick previous{};
    for(;;) {
        Tick t;
        if(s.format=="CSV5") {
            if(!in.line(line)) break;
            const auto c=split(line,',');if(c.size()!=5) fail("TICK_COLUMNS");
            t={natural(c[0]),integer(c[1]),integer(c[2]),integer(c[3]),integer(c[4])};
        } else {
            if(!in.packed(bytes)) break;
            t.seq=s.first_seq+r.rows;t.ts_ns=mul(little64(bytes.data()),1000000);
            t.bid_u=little32(bytes.data()+8);t.ask_u=little32(bytes.data()+12);
        }
        if(++r.rows>s.rows) fail("EXTRA_DATA_RECORD");
        if(t.seq!=s.first_seq+r.rows-1||t.ts_ns<=0||t.bid_u<=0||t.ask_u<=0) fail("TICK_SEQUENCE_TIME_PRICE");
        while(si<s.sessions.size()&&t.seq>s.sessions[si].close_seq) ++si;
        if(si==s.sessions.size()) fail("TICK_OUTSIDE_SESSIONS");
        const auto& session=s.sessions[si];
        if(s.format=="PACKED17") t.session_day=session.session_day;
        if(t.seq<session.open_seq||t.session_day!=session.session_day||t.ts_ns<session.open_ts_ns||t.ts_ns>session.close_ts_ns) fail("SESSION_MEMBERSHIP");
        if((t.seq==session.open_seq&&t.ts_ns!=session.open_ts_ns)||(t.seq==session.close_seq&&t.ts_ns!=session.close_ts_ns)) fail("SESSION_ANCHOR_MISMATCH");
        if(t.bid_u%s.tick_size_u!=0||t.ask_u%s.tick_size_u!=0) fail("TICK_SIZE_VIOLATION");
        if(r.rows>1) {
            if(t.ts_ns<previous.ts_ns) fail("TIME_REVERSAL");
            if(t.ts_ns==previous.ts_ns) ++r.same_timestamp;
            if(t.ts_ns==previous.ts_ns&&t.bid_u==previous.bid_u&&t.ask_u==previous.ask_u) ++r.repeated;
        } else {r.first_seq=t.seq;r.first_ts=t.ts_ns;}
        if(t.ask_u==t.bid_u) ++r.zero_spread;
        if(t.ask_u<t.bid_u) {++r.crossed;if(executable) fail("CROSSED_QUOTE_RESEARCH_POLICY");}
        r.last_seq=t.seq;r.last_ts=t.ts_ns;previous=t;
        if(visit) visit(t,session);
    }
    r.ticks_sha=in.finish(s.ticks_sha);
    if(r.rows!=s.rows) fail("MISSING_DATA_RECORDS");
    // Recheck metadata after long reads before any result can be committed.
    if(sha256_text(bounded_text(safe_relative(s.root,s.sessions_name)))!=s.sessions_sha) fail("SESSION_CHANGED_DURING_RUN");
    r.sessions_sha=s.sessions_sha;r.contract_root=s.fields.at("shard_contract_root");r.executable=r.crossed==0;
    return r;
}
std::string data_receipt(const DataSpec& s,const DataReceipt& r) {
    return fields_text("QROS_DATA_AUDIT_V3",{{"authority_id",s.authority_id},{"dataset_spec_sha256",s.sha256},
        {"ticks_sha256",r.ticks_sha},{"sessions_sha256",r.sessions_sha},{"session_fragment_sha256",r.sessions_sha},
        {"shard_contract_root",r.contract_root},{"rows",std::to_string(r.rows)},{"zero_spread",std::to_string(r.zero_spread)},
        {"crossed",std::to_string(r.crossed)},{"source_clock",s.source_clock},{"broker_origin",s.fields.at("broker_origin")},
        {"integrity","PASS"},{"executable_quotes",r.executable?"PASS":"FAIL"},{"research_ready","0"},
        {"verification_scope","BYTES_STRUCTURE_SESSION_BINDING_NOT_EXTERNAL_MT5_VALIDATION"}});
}

std::string verify_conversion(const std::filesystem::path& path,const std::string& hash) {
    const auto f=read_fields(path,"QROS_CONVERSION_CONTRACT_V1",hash);
    exact_keys(f,{"raw_csv","raw_sha256","packed17","packed_sha256","rows","clock_domain","timestamp_multiplier","price_decimals","broker_origin"});
    if(f.at("clock_domain")!="DARWINEX_SERVER_WALL"&&f.at("clock_domain")!="SYNTHETIC") fail("CONVERSION_CLOCK_DOMAIN");
    if(integer(f.at("timestamp_multiplier"))!=1000000) fail("CONVERSION_UNIT_CONTRACT");
    if(integer(f.at("price_decimals"))<0||integer(f.at("price_decimals"))>9) fail("CONVERSION_SCALE");
    BoundStream csv(safe_relative(path.parent_path(),f.at("raw_csv"))),bin(safe_relative(path.parent_path(),f.at("packed17")));
    std::string line;if(!csv.line(line)||line!="timestamp_ms,bid_u,ask_u,flags") fail("CONVERSION_CSV_HEADER");
    std::array<unsigned char,17>b{};u64 rows=0;
    while(csv.line(line)) {
        const auto c=split(line,',');if(c.size()!=4||!bin.packed(b)) fail("CONVERSION_ROW_COUNT");
        if(integer(c[0])!=little64(b.data())||integer(c[1])!=little32(b.data()+8)||integer(c[2])!=little32(b.data()+12)||natural(c[3])!=b[16]) fail("CONVERSION_RECORD_MISMATCH");
        ++rows;
    }
    const auto csv_hash=csv.finish(f.at("raw_sha256")),bin_hash=bin.finish(f.at("packed_sha256"));
    if(rows!=natural(f.at("rows"))||rows==0) fail("CONVERSION_COUNT_MISMATCH");
    return fields_text("QROS_CONVERSION_RECEIPT_V1",{{"contract_sha256",hash},{"raw_sha256",csv_hash},{"packed_sha256",bin_hash},
        {"rows",std::to_string(rows)},{"timestamp_offset_applied_ms","0"},{"clock_domain",f.at("clock_domain")},
        {"status","EXACT_RECORD_PARITY"},{"scope","SUPPLIED_NORMALIZED_CSV_TO_PACKED17"},{"research_ready","0"}});
}

std::string verify_shard_chain(const std::filesystem::path& path,const std::string& hash) {
    const auto raw=bounded_text(path);if(sha256_text(raw)!=hash) fail("SHARD_INDEX_HASH");
    std::istringstream in(raw);std::string line;
    if(!std::getline(in,line)||line!="index,manifest_path,manifest_sha256,shard_contract_root") fail("SHARD_INDEX_HEADER");
    u64 count=0,rows=0,next=0;std::string parent,symbol,clock;Fields identity;i64 previous_time=0,previous_day=0;Sha256Builder root;
    root.update("QROS_SHARD_CHAIN_V3\n");
    while(std::getline(in,line)) {
        const auto c=split(line,',');if(c.size()!=4||natural(c[0])!=count) fail("SHARD_INDEX_ORDER");
        auto s=read_data_spec(safe_relative(path.parent_path(),c[1]),c[2]);
        if(s.fields.at("shard_contract_root")!=c[3]) fail("SHARD_CONTRACT_ROOT_MISMATCH");
        if(count==0){next=s.first_seq;parent=s.fields.at("parent_carrier_sha256");symbol=s.symbol;clock=s.source_clock;}
        if(s.first_seq!=next||s.fields.at("parent_carrier_sha256")!=parent||s.symbol!=symbol||s.source_clock!=clock) fail("SHARD_CHAIN_DISCONTINUITY");
        for(const auto* key:{"purpose","exposure","broker_origin","price_decimals","tick_size_u","point_size_u"}) {
            if(count==0)identity[key]=s.fields.at(key);
            else if(identity.at(key)!=s.fields.at(key))fail("SHARD_CHAIN_METADATA_MISMATCH");
        }
        const auto audit=walk_data(s,{},false,s.rows);
        if(count>0&&(audit.first_ts<previous_time||s.first_day<previous_day))fail("SHARD_CHAIN_TIME_REVERSAL");
        previous_time=audit.last_ts;previous_day=s.last_day;
        next+=s.rows;rows+=s.rows;++count;root.update(line+"\n");
    }
    if(count==0) fail("EMPTY_SHARD_CHAIN");
    return fields_text("QROS_SHARD_CHAIN_RECEIPT_V3",{{"index_sha256",hash},{"shards",std::to_string(count)},
        {"rows",std::to_string(rows)},{"next_seq",std::to_string(next)},{"chain_root_sha256",root.finish()},
        {"status","PROVIDED_SHARDS_VERIFIED"},{"full_parent_coverage","NOT_ASSERTED"},{"research_ready","0"}});
}
} // namespace qros::pipeline
