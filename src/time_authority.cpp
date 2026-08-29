#include "qros/time_authority.hpp"
#include "qros/canonical_text.hpp"
#include "qros/sha256.hpp"
#include "qros/text_snapshot.hpp"

#include <algorithm>
#include <array>
#include <charconv>
#include <fstream>
#include <limits>
#include <set>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace qros {
namespace {

[[noreturn]] void fail(std::string_view text) { throw std::runtime_error(std::string(text)); }
[[noreturn]] void fail2(std::string_view a, std::string_view b) { CanonicalText o(256); o.append(a); o.append(b); throw std::runtime_error(o.str_ref()); }

bool lower_hex64(std::string_view s) {
    return s.size()==64 && std::all_of(s.begin(),s.end(),[](unsigned char c){return (c>='0'&&c<='9')||(c>='a'&&c<='f');});
}
bool safe_id(std::string_view s,std::size_t max_len) {
    if(s.empty()||s.size()>max_len)return false;
    return std::all_of(s.begin(),s.end(),[](unsigned char c){return (c>='A'&&c<='Z')||(c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='_'||c=='-'||c=='.'||c==':'||c=='/';});
}
std::int64_t parse_i64(std::string_view s,std::string_view field){std::int64_t v{};auto [p,e]=std::from_chars(s.data(),s.data()+s.size(),v);if(e!=std::errc{}||p!=s.data()+s.size())fail2("invalid integer: ",field);return v;}
std::uint64_t parse_u64(std::string_view s,std::string_view field){std::uint64_t v{};auto [p,e]=std::from_chars(s.data(),s.data()+s.size(),v);if(e!=std::errc{}||p!=s.data()+s.size())fail2("invalid unsigned: ",field);return v;}
std::size_t parse_size(std::string_view s,std::string_view field){auto v=parse_u64(s,field);if(v>static_cast<std::uint64_t>(std::numeric_limits<std::size_t>::max()))fail("size overflow");return static_cast<std::size_t>(v);}
std::string_view val(std::string_view line,std::string_view key){if(!line.starts_with(key))fail2("expected field: ",key);return line.substr(key.size());}

template<std::size_t N> std::array<std::string_view,N> split(std::string_view line){
    std::array<std::string_view,N> out{};std::size_t start=0;
    for(std::size_t i=0;i+1<N;++i){auto pos=line.find(',',start);if(pos==std::string_view::npos)fail("wrong CSV column count");out[i]=line.substr(start,pos-start);start=pos+1;}
    out[N-1]=line.substr(start);if(out[N-1].find(',')!=std::string_view::npos)fail("wrong CSV column count");for(auto x:out)if(x.empty())fail("empty CSV field");return out;
}

struct ProvenanceRecord {
    std::string authority_id,source_id,method,status,anchors_sha256,schedule_sha256,custody_root,evidence_id;
};
ProvenanceRecord parse_provenance_lines(const std::vector<std::string>& l){
    if(l.size()!=9||l[0]!="QROS_TIME_PROVENANCE_V1")fail("invalid time provenance record");
    ProvenanceRecord p{std::string(val(l[1],"authority_id=")),std::string(val(l[2],"source_id=")),std::string(val(l[3],"method=")),std::string(val(l[4],"status=")),
                       std::string(val(l[5],"anchors_sha256=")),std::string(val(l[6],"schedule_sha256=")),std::string(val(l[7],"source_custody_evidence_root_sha256=")),std::string(val(l[8],"evidence_id="))};
    if(!safe_id(p.authority_id,128)||!safe_id(p.source_id,160)||!safe_id(p.method,128)||!safe_id(p.status,64)||!safe_id(p.evidence_id,128))fail("unsafe time provenance identifier");
    if(!lower_hex64(p.anchors_sha256)||!lower_hex64(p.schedule_sha256)||!lower_hex64(p.custody_root)) fail("time provenance hash invalid");
    return p;
}

struct CustodyReceiptEvidence {
    std::string root;
    bool semantic_valid{};
    bool source_ready{};
    bool production_ready{};
};

bool parse_receipt_bool(std::string_view v) {
    if (v == "1") return true;
    if (v == "0") return false;
    fail("custody receipt boolean must be 0/1");
}

CustodyReceiptEvidence custody_evidence_from_lines(const std::vector<std::string>& lines) {
    if (lines.empty() || lines[0] != "QROS_SOURCE_CUSTODY_RECEIPT_V1") fail("invalid source custody receipt");
    std::string profile_sha, source_class, chain_sha, decoded_sha, declared_root;
    bool archive = false, decoded = false, lineage = false, source_ready = false, production_ready = false;
    bool saw_archive=false,saw_decoded=false,saw_lineage=false,saw_source=false,saw_production=false;
    for (std::size_t i = 1; i < lines.size(); ++i) {
        const auto& line = lines[i];
        auto set_hash = [&](std::string_view key, std::string& target) {
            if (!line.starts_with(key)) return false;
            if (!target.empty()) fail("duplicate custody receipt field");
            target = std::string(line.substr(key.size()));
            if (!lower_hex64(target)) fail("invalid custody receipt hash");
            return true;
        };
        if (set_hash("profile_sha256=", profile_sha) || set_hash("measured_chain_root_sha256=", chain_sha) ||
            set_hash("decoded_measured_sha256=", decoded_sha) || set_hash("custody_evidence_root_sha256=", declared_root)) continue;
        if (line.starts_with("source_class=")) { if (!source_class.empty()) fail("duplicate custody source_class"); source_class=std::string(line.substr(13)); if(!safe_id(source_class,128)) fail("invalid custody source_class"); continue; }
        auto set_bool = [&](std::string_view key, bool& target, bool& saw) {
            if (!line.starts_with(key)) return false;
            if (saw) fail("duplicate custody receipt boolean");
            target = parse_receipt_bool(line.substr(key.size())); saw = true; return true;
        };
        if (set_bool("archive_custody_verified=", archive, saw_archive) || set_bool("decoded_bytes_verified=", decoded, saw_decoded) ||
            set_bool("decode_lineage_verified=", lineage, saw_lineage) || set_bool("source_provenance_ready=", source_ready, saw_source) ||
            set_bool("production_source_provenance_ready=", production_ready, saw_production)) continue;
    }
    if (!lower_hex64(profile_sha) || source_class.empty() || !lower_hex64(chain_sha) || !lower_hex64(decoded_sha) || !lower_hex64(declared_root) ||
        !saw_archive || !saw_decoded || !saw_lineage || !saw_source || !saw_production) fail("custody receipt missing required evidence fields");
    CanonicalText material(768);
    material.append("QROS_CUSTODY_EVIDENCE_ROOT_V1\n");
    material.append("profile_sha256="); material.append(profile_sha); material.append('\n');
    material.append("source_class="); material.append(source_class); material.append('\n');
    material.append("measured_chain_root_sha256="); material.append(chain_sha); material.append('\n');
    material.append("decoded_measured_sha256="); material.append(decoded_sha); material.append('\n');
    material.append("archive_custody_verified="); material.append_bool01(archive); material.append('\n');
    material.append("decoded_bytes_verified="); material.append_bool01(decoded); material.append('\n');
    material.append("decode_lineage_verified="); material.append_bool01(lineage); material.append('\n');
    material.append("production_source_provenance_ready="); material.append_bool01(production_ready); material.append('\n');
    const auto recomputed = sha256_text(material.view());
    const bool semantic = recomputed == declared_root && source_ready == (archive && decoded && lineage) && !production_ready;
    return CustodyReceiptEvidence{declared_root, semantic, source_ready, production_ready};
}

bool in_segment(std::int64_t utc,const OffsetSegment& s){return utc>=s.start_utc_ns&&utc<s.end_utc_ns;}

void append_kv(CanonicalText& o,std::string_view k,std::string_view v){o.append(k);o.append(v);o.append('\n');}
void append_size(CanonicalText& o,std::string_view k,std::size_t v){o.append(k);o.append_integer(v);o.append('\n');}
void append_i64(CanonicalText& o,std::string_view k,std::int64_t v){o.append(k);o.append_integer(v);o.append('\n');}
void append_bool(CanonicalText& o,std::string_view k,bool v){o.append(k);o.append_bool01(v);o.append('\n');}

} // namespace

std::string_view time_authority_purpose_name(TimeAuthorityPurpose purpose){return purpose==TimeAuthorityPurpose::Research?"RESEARCH":"TEST_ONLY";}

TimeAuthorityProfile read_time_authority_profile(const std::filesystem::path& path){
    TimeAuthorityProfile p;const auto snapshot=read_stable_text_snapshot(path,65536U,17U,4096U);p.profile_sha256=snapshot.sha256;const auto& l=snapshot.lines;
    if(l.size()!=17||l[0]!="QROS_TIME_AUTHORITY_PROFILE_V1")fail("invalid time authority profile");
    p.authority_id=std::string(val(l[1],"authority_id="));p.source_id=std::string(val(l[2],"source_id="));const auto purpose=val(l[3],"purpose=");
    if(purpose=="RESEARCH")p.purpose=TimeAuthorityPurpose::Research;else if(purpose=="TEST_ONLY")p.purpose=TimeAuthorityPurpose::TestOnly;else fail("invalid time purpose");
    p.server_clock_domain=std::string(val(l[4],"server_clock_domain="));p.schedule_sha256=std::string(val(l[5],"schedule_sha256="));p.anchors_sha256=std::string(val(l[6],"anchors_sha256="));
    p.provenance_sha256=std::string(val(l[7],"provenance_sha256="));p.source_custody_evidence_root_sha256=std::string(val(l[8],"source_custody_evidence_root_sha256="));
    p.source_custody_receipt_sha256=std::string(val(l[9],"source_custody_receipt_sha256="));
    p.min_anchors=parse_size(val(l[10],"min_anchors="),"min_anchors");p.max_transition_bracket_ns=parse_i64(val(l[11],"max_transition_bracket_ns="),"max_transition_bracket_ns");
    p.max_edge_anchor_distance_ns=parse_i64(val(l[12],"max_edge_anchor_distance_ns="),"max_edge_anchor_distance_ns");p.max_abs_offset_seconds=parse_i64(val(l[13],"max_abs_offset_seconds="),"max_abs_offset_seconds");
    p.max_offset_jump_seconds=parse_i64(val(l[14],"max_offset_jump_seconds="),"max_offset_jump_seconds");p.production_anchor_verifier_id=std::string(val(l[15],"production_anchor_verifier_id="));
    const auto reserved=val(l[16],"reserved=");if(reserved!="0")fail("reserved must be 0");
    if(!safe_id(p.authority_id,128)||!safe_id(p.source_id,160)||!safe_id(p.server_clock_domain,128)||!safe_id(p.production_anchor_verifier_id,128))fail("unsafe time profile identifier");
    if(p.server_clock_domain!="NAIVE_WALL_EPOCH_NS")fail("unsupported server_clock_domain");
    if(!lower_hex64(p.schedule_sha256)||!lower_hex64(p.anchors_sha256)||!lower_hex64(p.provenance_sha256)||!lower_hex64(p.source_custody_evidence_root_sha256)||!lower_hex64(p.source_custody_receipt_sha256))fail("time profile hash invalid");
    if(p.min_anchors<2||p.min_anchors>1000000)fail("min_anchors out of bounds");
    if(p.max_transition_bracket_ns<=0||p.max_edge_anchor_distance_ns<=0||p.max_abs_offset_seconds<=0||p.max_abs_offset_seconds>86400||p.max_offset_jump_seconds<=0||p.max_offset_jump_seconds>43200)fail("time profile numeric bounds invalid");
    return p;
}

namespace {
std::vector<OffsetSegment> parse_offset_schedule_lines(const std::vector<std::string>& l){
    if(l.empty()||l[0]!="segment_id,start_utc_ns,end_utc_ns,offset_seconds")fail("invalid offset schedule header");
    std::vector<OffsetSegment> out;out.reserve(l.size()-1);std::set<std::string> ids;
    for(std::size_t i=1;i<l.size();++i){const auto f=split<4>(l[i]);if(!safe_id(f[0],128)||!ids.insert(std::string(f[0])).second)fail("invalid/duplicate segment_id");out.push_back({std::string(f[0]),parse_i64(f[1],"start_utc_ns"),parse_i64(f[2],"end_utc_ns"),parse_i64(f[3],"offset_seconds")});}
    if(out.empty()) fail("empty offset schedule");
    return out;
}
std::vector<TimeAnchor> parse_time_anchor_lines(const std::vector<std::string>& l){
    if(l.empty()||l[0]!="anchor_id,server_wall_ns,utc_ns,evidence_id")fail("invalid time anchors header");
    std::vector<TimeAnchor> out;out.reserve(l.size()-1);std::set<std::string> ids;
    for(std::size_t i=1;i<l.size();++i){const auto f=split<4>(l[i]);if(!safe_id(f[0],128)||!ids.insert(std::string(f[0])).second)fail("invalid/duplicate anchor_id");if(!safe_id(f[3],128))fail("anchor evidence_id invalid");out.push_back({std::string(f[0]),parse_i64(f[1],"server_wall_ns"),parse_i64(f[2],"utc_ns"),std::string(f[3])});}
    return out;
}
} // namespace

std::vector<OffsetSegment> read_offset_schedule(const std::filesystem::path& path){
    return parse_offset_schedule_lines(read_stable_text_snapshot(path,16U*1024U*1024U,20001U,4096U).lines);
}

std::vector<TimeAnchor> read_time_anchors(const std::filesystem::path& path){
    return parse_time_anchor_lines(read_stable_text_snapshot(path,64U*1024U*1024U,200001U,4096U).lines);
}

TimeAuthorityAudit audit_time_authority(const TimeAuthorityProfile& p,
                                        const std::filesystem::path& schedule_path,
                                        const std::filesystem::path& anchors_path,
                                        const std::filesystem::path& provenance_path,
                                        const std::filesystem::path& custody_path) {
    TimeAuthorityAudit a;
    a.profile_valid = true;
    const auto schedule_snapshot=read_stable_text_snapshot(schedule_path,16U*1024U*1024U,20001U,4096U);
    const auto anchors_snapshot=read_stable_text_snapshot(anchors_path,64U*1024U*1024U,200001U,4096U);
    const auto provenance_snapshot=read_stable_text_snapshot(provenance_path,65536U,9U,4096U);
    const auto custody_snapshot=read_stable_text_snapshot(custody_path,262144U,256U,4096U);
    a.schedule_sha256_measured = schedule_snapshot.sha256;
    a.anchors_sha256_measured = anchors_snapshot.sha256;
    a.provenance_sha256_measured = provenance_snapshot.sha256;
    a.custody_receipt_sha256_measured = custody_snapshot.sha256;
    const auto custody = custody_evidence_from_lines(custody_snapshot.lines);
    a.custody_evidence_root_measured = custody.root;
    a.custody_receipt_semantic_valid = custody.semantic_valid;
    a.custody_source_ready = custody.source_ready;
    a.custody_production_ready = custody.production_ready;
    a.schedule_hash_match = a.schedule_sha256_measured == p.schedule_sha256;
    a.anchors_hash_match = a.anchors_sha256_measured == p.anchors_sha256;
    a.provenance_hash_match = a.provenance_sha256_measured == p.provenance_sha256;
    a.custody_evidence_root_match = a.custody_evidence_root_measured == p.source_custody_evidence_root_sha256;
    a.custody_receipt_hash_match = a.custody_receipt_sha256_measured == p.source_custody_receipt_sha256;

    const auto schedule = parse_offset_schedule_lines(schedule_snapshot.lines);
    const auto anchors = parse_time_anchor_lines(anchors_snapshot.lines);
    const auto prov = parse_provenance_lines(provenance_snapshot.lines);
    a.segments = schedule.size();
    a.anchors = anchors.size();

    for (std::size_t i = 0; i < schedule.size(); ++i) {
        const auto& seg = schedule[i];
        const bool offset_valid = seg.offset_seconds <= p.max_abs_offset_seconds && seg.offset_seconds >= -p.max_abs_offset_seconds;
        if (seg.start_utc_ns <= 0 || seg.end_utc_ns <= seg.start_utc_ns || !offset_valid) ++a.schedule_errors;
        if (i > 0) {
            const auto& prev = schedule[i - 1];
            if (seg.start_utc_ns != prev.end_utc_ns) ++a.schedule_errors;
            const bool prev_valid = prev.offset_seconds <= p.max_abs_offset_seconds && prev.offset_seconds >= -p.max_abs_offset_seconds;
            if (offset_valid && prev_valid) {
                const auto jump = seg.offset_seconds - prev.offset_seconds; // bounded to +/-172800 by prior checks
                const auto abs_jump = jump < 0 ? -jump : jump;
                if (abs_jump > p.max_offset_jump_seconds) ++a.schedule_errors;
            }
            if (seg.offset_seconds == prev.offset_seconds) ++a.schedule_errors;
            else ++a.offset_transitions;
        }
    }

    if (anchors.size() < p.min_anchors) ++a.anchor_errors;
    std::int64_t previous_utc = 0;
    bool first_offset = true;
    for (const auto& anchor : anchors) {
        const bool basic_valid = anchor.utc_ns > 0 && anchor.server_wall_ns > 0 && anchor.utc_ns > previous_utc;
        if (!basic_valid) {
            ++a.anchor_errors;
            if (anchor.utc_ns > previous_utc) previous_utc = anchor.utc_ns;
            continue;
        }
        previous_utc = anchor.utc_ns;
        if (anchor.evidence_id != prov.evidence_id) ++a.provenance_errors;
        const auto delta = anchor.server_wall_ns - anchor.utc_ns; // safe: both are positive int64
        if ((delta % 1000000000LL) != 0) {
            ++a.anchor_errors;
            continue;
        }
        const std::int64_t offset = static_cast<std::int64_t>(delta / 1000000000LL);
        if (first_offset) {
            a.min_observed_offset_seconds = offset;
            a.max_observed_offset_seconds = offset;
            first_offset = false;
        } else {
            a.min_observed_offset_seconds = std::min(a.min_observed_offset_seconds, offset);
            a.max_observed_offset_seconds = std::max(a.max_observed_offset_seconds, offset);
        }
        if (offset > p.max_abs_offset_seconds || offset < -p.max_abs_offset_seconds) ++a.anchor_errors;
        const auto it = std::find_if(schedule.begin(), schedule.end(), [&](const OffsetSegment& seg) { return in_segment(anchor.utc_ns, seg); });
        if (it == schedule.end() || it->offset_seconds != offset) ++a.anchor_errors;
    }
    a.anchor_offsets_match_schedule = a.anchor_errors == 0;

    const bool schedule_safe_for_distances = a.schedule_errors == 0;
    if (!anchors.empty() && schedule_safe_for_distances) {
        const auto first_distance = anchors.front().utc_ns - schedule.front().start_utc_ns;
        const auto last_distance = schedule.back().end_utc_ns - anchors.back().utc_ns;
        if (first_distance < 0 || first_distance > p.max_edge_anchor_distance_ns) ++a.edge_coverage_errors;
        if (last_distance <= 0 || last_distance > p.max_edge_anchor_distance_ns) ++a.edge_coverage_errors;
    } else if (anchors.empty()) {
        a.edge_coverage_errors += 2;
    } else {
        ++a.edge_coverage_errors;
    }

    if (schedule_safe_for_distances) {
        for (std::size_t i = 1; i < schedule.size(); ++i) {
            const auto boundary = schedule[i].start_utc_ns;
            const auto pre_offset = schedule[i - 1].offset_seconds;
            const auto post_offset = schedule[i].offset_seconds;
            bool pre = false;
            bool post = false;
            for (const auto& anchor : anchors) {
                if (anchor.utc_ns <= 0 || anchor.server_wall_ns <= 0) continue;
                const auto delta = anchor.server_wall_ns - anchor.utc_ns;
                if ((delta % 1000000000LL) != 0) continue;
                const std::int64_t offset = static_cast<std::int64_t>(delta / 1000000000LL);
                if (anchor.utc_ns < boundary) {
                    const auto distance = boundary - anchor.utc_ns;
                    if (distance <= p.max_transition_bracket_ns && offset == pre_offset) pre = true;
                } else {
                    const auto distance = anchor.utc_ns - boundary;
                    if (distance <= p.max_transition_bracket_ns && offset == post_offset) post = true;
                }
            }
            if (!pre || !post) ++a.transition_bracket_errors;
        }
    } else if (schedule.size() > 1) {
        a.transition_bracket_errors += schedule.size() - 1;
    }

    a.semantic_provenance_match = prov.authority_id == p.authority_id && prov.source_id == p.source_id &&
        prov.anchors_sha256 == a.anchors_sha256_measured && prov.schedule_sha256 == a.schedule_sha256_measured &&
        prov.custody_root == a.custody_evidence_root_measured;
    if (!a.semantic_provenance_match) ++a.provenance_errors;

    const bool synthetic = prov.method.starts_with("SYNTHETIC");
    const bool test_status = prov.status == "TEST_ONLY";
    const bool verified_status = prov.status == "VERIFIED";
    a.production_anchor_verifier_available = false;
    const bool base = a.schedule_hash_match && a.anchors_hash_match && a.provenance_hash_match && a.custody_evidence_root_match &&
        a.custody_receipt_hash_match && a.custody_receipt_semantic_valid && a.custody_source_ready && a.schedule_errors == 0 && a.anchor_errors == 0 && a.transition_bracket_errors == 0 && a.edge_coverage_errors == 0 && a.provenance_errors == 0;
    a.test_time_ready = base && p.purpose == TimeAuthorityPurpose::TestOnly && synthetic && test_status;
    a.research_time_ready = base && p.purpose == TimeAuthorityPurpose::Research && !synthetic && verified_status && a.custody_production_ready && a.production_anchor_verifier_available;
    if (a.research_time_ready) a.status = "TIME_VERIFIED";
    else if (a.test_time_ready) a.status = "TEST_TIME_READY";
    else if (base && p.purpose == TimeAuthorityPurpose::Research && synthetic) a.status = "RESEARCH_REJECTED_SYNTHETIC_PROVENANCE";
    else if (base && p.purpose == TimeAuthorityPurpose::Research && !a.custody_production_ready) a.status = "SEMANTICS_PASS_PRODUCTION_SOURCE_CUSTODY_NOT_READY";
    else if (base && p.purpose == TimeAuthorityPurpose::Research && !a.production_anchor_verifier_available)
        a.status = "SEMANTICS_PASS_PRODUCTION_ANCHOR_VERIFIER_NOT_IMPLEMENTED";
    else a.status = "FAIL_TIME_AUTHORITY";
    return a;
}

std::string time_authority_receipt(const TimeAuthorityProfile& p,const TimeAuthorityAudit& a,std::string_view entry,std::string_view source_root,std::string_view build_contract,std::string_view engine){
    CanonicalText o(2048);o.append("QROS_TIME_AUTHORITY_RECEIPT_V1\n");append_kv(o,"engine_version=",engine);append_kv(o,"source_root_sha256=",source_root);append_kv(o,"build_contract_sha256=",build_contract);append_kv(o,"entrypoint_sha256=",entry);append_kv(o,"authority_id=",p.authority_id);append_kv(o,"source_id=",p.source_id);append_kv(o,"purpose=",time_authority_purpose_name(p.purpose));append_kv(o,"profile_sha256=",p.profile_sha256);
    append_kv(o,"schedule_sha256=",a.schedule_sha256_measured);append_kv(o,"anchors_sha256=",a.anchors_sha256_measured);append_kv(o,"provenance_sha256=",a.provenance_sha256_measured);append_kv(o,"source_custody_receipt_sha256=",a.custody_receipt_sha256_measured);append_kv(o,"source_custody_evidence_root_sha256=",a.custody_evidence_root_measured);append_size(o,"segments=",a.segments);append_size(o,"anchors=",a.anchors);append_size(o,"offset_transitions=",a.offset_transitions);append_i64(o,"min_observed_offset_seconds=",a.min_observed_offset_seconds);append_i64(o,"max_observed_offset_seconds=",a.max_observed_offset_seconds);append_size(o,"schedule_errors=",a.schedule_errors);append_size(o,"anchor_errors=",a.anchor_errors);append_size(o,"transition_bracket_errors=",a.transition_bracket_errors);append_size(o,"edge_coverage_errors=",a.edge_coverage_errors);append_size(o,"provenance_errors=",a.provenance_errors);append_bool(o,"schedule_hash_match=",a.schedule_hash_match);append_bool(o,"anchors_hash_match=",a.anchors_hash_match);append_bool(o,"provenance_hash_match=",a.provenance_hash_match);append_bool(o,"custody_evidence_root_match=",a.custody_evidence_root_match);append_bool(o,"custody_receipt_hash_match=",a.custody_receipt_hash_match);append_bool(o,"custody_receipt_semantic_valid=",a.custody_receipt_semantic_valid);append_bool(o,"custody_source_ready=",a.custody_source_ready);append_bool(o,"custody_production_ready=",a.custody_production_ready);append_bool(o,"semantic_provenance_match=",a.semantic_provenance_match);append_bool(o,"anchor_offsets_match_schedule=",a.anchor_offsets_match_schedule);append_bool(o,"production_anchor_verifier_available=",a.production_anchor_verifier_available);append_bool(o,"test_time_ready=",a.test_time_ready);append_bool(o,"research_time_ready=",a.research_time_ready);append_kv(o,"status=",a.status);return std::move(o).take();
}

} // namespace qros
