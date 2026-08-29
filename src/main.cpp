#include "qros/core.hpp"
#include "qros/custody.hpp"
#include "qros/qdata.hpp"
#include "qros/sha256.hpp"
#include "qros/time_authority.hpp"
#include "qros/build_identity.hpp"
#include "qros/canonical_text.hpp"
#include "qros/pipeline.hpp"

#include <algorithm>
#include <chrono>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace qros;

static void usage(){
    std::cerr << "QROS Engine v0.6.0 development\n"
              << "usage:\n"
              << "  qros audit <ticks.csv>\n"
              << "  qros custody-profile-check <profile.custody>\n"
              << "  qros source-custody <profile.custody> <source_directory> <receipt>\n"
              << "  qros time-authority <profile.time> <schedule.csv> <anchors.csv> <provenance> <custody_receipt> <receipt>\n"
              << "  qros qdata-audit <ticks.csv> <sessions.csv> <manifest.qdata> <timezone_evidence> <source_evidence> <receipt>\n"
              << "  qros replay <ticks.csv> <intent.qros> <ledger.csv>\n"
              << "  qros replay-qdata <ticks.csv> <sessions.csv> <manifest.qdata> <timezone_evidence> <source_evidence> <intent.qros> <ledger.csv>\n"
              << "  qros contracts\n"
              << "  qros sha256 <file>\n"
              << "  qros bench <rows>\n";
    std::cerr << "  qros capabilities\n"
              << "  qros compile|export-mt5 <program> <sha> <birth> <output>\n"
              << "  qros data-check|verify-conversion|verify-shards <contract> <sha> <receipt>\n"
              << "  qros mine <program> <sha> <dataset> <sha> <vault> <sha> <result_dir> <chunk_births> <max_chunks> <max_rows>\n"
              << "  qros backtest <program> <sha> <dataset> <sha> <vault> <sha> <result_dir>\n"
              << "  qros features <program> <sha> <birth> <dataset> <sha> <vault> <sha> <output>\n"
              << "  qros gates <ledger> <sha> <policy> <sha> <report>\n"
              << "  qros supergate|mt5-parity <plan> <sha> <report>\n"
              << "  qros portfolio <plan> <sha> <ledger> <report>\n"
              << "  qros vault-check <dataset> <sha> <vault> <sha> <candidate_sha>\n"
              << "  qros vault-consume <policy> <sha> <grant> <sha> <receipt_store>\n";
}

static const SessionBoundary* find_session(const std::vector<SessionBoundary>& sessions, i64 day) {
    const auto it = std::lower_bound(sessions.begin(), sessions.end(), day, [](const SessionBoundary& s, i64 d){ return s.session_day < d; });
    if (it == sessions.end() || it->session_day != day) return nullptr;
    return &*it;
}

static std::string executable_sha256(const char* argv0) {
#if defined(__linux__)
    const std::filesystem::path proc("/proc/self/exe");
    if (std::filesystem::exists(proc)) return sha256_file(proc);
#endif
    return sha256_file(std::filesystem::canonical(argv0));
}

static std::string make_trade_csv(const Intent& intent, const Trade& trade) {
    const auto header = trade_csv_header();
    const auto row = trade_csv_row(intent.strategy_id, trade);
    std::string out;
    out.reserve(header.size() + row.size());
    out.append(header.data(), header.size());
    out.append(row);
    return out;
}

static void append_kv(CanonicalText& o, std::string_view key, std::string_view value) {
    o.append(key); o.append(value); o.append('\n');
}

static std::string replay_receipt_v3(const std::string& run_id,
                                     const std::string& ticks_sha,
                                     const std::string& intent_sha,
                                     const std::string& ledger_sha,
                                     const std::string& manifest_sha,
                                     const std::string& sessions_sha,
                                     const std::string& qdata_receipt_sha,
                                     const std::string& event_contract_sha,
                                     const std::string& execution_policy_sha,
                                     const std::string& entrypoint_sha) {
    CanonicalText o(1024);
    o.append("QROS_REPLAY_RECEIPT_V3\n");
    append_kv(o, "engine_version=", qros::build_identity::engine_version);
    append_kv(o, "run_id=", run_id);
    append_kv(o, "source_root_sha256=", qros::build_identity::source_root_sha256);
    append_kv(o, "build_type=", qros::build_identity::build_type);
    append_kv(o, "build_contract_sha256=", qros::build_identity::build_contract_sha256);
    append_kv(o, "entrypoint_sha256=", entrypoint_sha);
    append_kv(o, "ticks_sha256=", ticks_sha);
    append_kv(o, "intent_sha256=", intent_sha);
    append_kv(o, "qdata_manifest_sha256=", manifest_sha);
    append_kv(o, "sessions_sha256=", sessions_sha);
    append_kv(o, "qdata_audit_receipt_sha256=", qdata_receipt_sha);
    append_kv(o, "event_contract_sha256=", event_contract_sha);
    append_kv(o, "execution_policy_sha256=", execution_policy_sha);
    append_kv(o, "ledger_sha256=", ledger_sha);
    return std::move(o).take();
}

static std::string legacy_run_id_material(const std::string& self_sha,
                                          const std::string& ticks_sha,
                                          const std::string& intent_sha,
                                          const std::string& event_sha,
                                          const std::string& exec_sha) {
    CanonicalText o(512);
    o.append("QROS_RUN_V3_LEGACY\n");
    append_kv(o, "engine=", qros::build_identity::engine_version);
    append_kv(o, "source_root=", qros::build_identity::source_root_sha256);
    append_kv(o, "build_contract=", qros::build_identity::build_contract_sha256);
    append_kv(o, "entrypoint=", self_sha);
    append_kv(o, "data=", ticks_sha);
    append_kv(o, "intent=", intent_sha);
    append_kv(o, "event=", event_sha);
    append_kv(o, "exec=", exec_sha);
    return std::move(o).take();
}

static std::string qdata_run_id_material(const std::string& self_sha,
                                         const QDataAudit& qda,
                                         const std::string& intent_sha,
                                         const std::string& event_sha,
                                         const std::string& exec_sha) {
    CanonicalText o(640);
    o.append("QROS_RUN_V3_QDATA\n");
    append_kv(o, "engine=", qros::build_identity::engine_version);
    append_kv(o, "source_root=", qros::build_identity::source_root_sha256);
    append_kv(o, "build_contract=", qros::build_identity::build_contract_sha256);
    append_kv(o, "entrypoint=", self_sha);
    append_kv(o, "data=", qda.dataset_sha256);
    append_kv(o, "manifest=", qda.manifest_sha256);
    append_kv(o, "sessions=", qda.sessions_sha256);
    append_kv(o, "intent=", intent_sha);
    append_kv(o, "event=", event_sha);
    append_kv(o, "exec=", exec_sha);
    return std::move(o).take();
}

static std::filesystem::path receipt_path_for(const char* ledger_path) {
    std::filesystem::path p(ledger_path);
    p += ".receipt";
    return p;
}

int main(int argc, char** argv){
    try {
        if(argc < 2){ usage(); return 2; }
        const std::string cmd=argv[1];
        const std::string self_sha=executable_sha256(argv[0]);
        const auto pipeline_result=qros::pipeline::command(argc,argv,self_sha);
        if(pipeline_result>=0)return pipeline_result;
        if(cmd=="custody-profile-check"){
            if(argc!=3){usage();return 2;}
            const auto profile=read_source_custody_profile(argv[2]);
            std::cout<<source_custody_profile_receipt(profile);
            return 0;
        }
        if(cmd=="source-custody"){
            if(argc!=5){usage();return 2;}
            const auto profile=read_source_custody_profile(argv[2]);
            const auto audit=audit_source_custody(profile,argv[3]);
            const auto receipt=source_custody_receipt(profile,audit,self_sha,qros::build_identity::source_root_sha256,
                                                      qros::build_identity::build_contract_sha256,qros::build_identity::engine_version);
            atomic_write_text(argv[4],receipt);
            std::cout<<receipt;
            if(audit.source_provenance_ready) return 0;
            if(audit.archive_custody_verified && audit.decoded_bytes_verified) return 5;
            return 4;
        }
        if(cmd=="time-authority"){
            if(argc!=8){usage();return 2;}
            const auto profile=read_time_authority_profile(argv[2]);
            const auto audit=audit_time_authority(profile,argv[3],argv[4],argv[5],argv[6]);
            const auto receipt=time_authority_receipt(profile,audit,self_sha,qros::build_identity::source_root_sha256,
                                                      qros::build_identity::build_contract_sha256,qros::build_identity::engine_version);
            atomic_write_text(argv[7],receipt);
            std::cout<<receipt;
            if(audit.research_time_ready || audit.test_time_ready) return 0;
            if(audit.schedule_hash_match && audit.anchors_hash_match && audit.provenance_hash_match && audit.custody_evidence_root_match) return 5;
            return 4;
        }
        if(cmd=="audit"){
            if(argc!=3){usage();return 2;}
            auto ticks=read_ticks_csv(argv[2]);
            auto a=audit_ticks(ticks);
            std::cout << "rows="<<a.rows<<" zero_spread="<<a.zero_spread<<" crossed="<<a.crossed_market
                      <<" seq_errors="<<a.seq_errors<<" time_reversals="<<a.time_reversals
                      <<" day_reversals="<<a.day_reversals<<" same_timestamp="<<a.same_timestamp
                      <<" repeated_quote_payload="<<a.repeated_quote_payload<<" status="<<(a.pass?"PASS":"FAIL")<<"\n";
            return a.pass?0:3;
        }
        if(cmd=="qdata-audit"){
            if(argc!=8){usage();return 2;}
            const auto manifest=read_qdata_manifest(argv[4]);
            const auto a=audit_qdata_authority(argv[2],argv[3],argv[4],argv[5],argv[6]);
            const auto receipt=qdata_audit_receipt(manifest,a);
            atomic_write_text(argv[7],receipt);
            std::cout<<receipt;
            if(a.research_ready || a.test_ready) return 0;
            if(a.pass_integrity) return 5;
            return 4;
        }
        if(cmd=="replay"){
            if(argc!=5){usage();return 2;}
            auto intent=read_intent(argv[3]);
            auto ticks=read_ticks_csv_bound(argv[2],intent.data_sha256);
            auto t=replay_market_after_signal(ticks,intent);
            const std::string data=make_trade_csv(intent,t);
            atomic_write_text(argv[4],data);
            const std::string ticks_sha=intent.data_sha256;
            const std::string intent_sha=sha256_file(argv[3]);
            const std::string event_sha=sha256_text(event_phase_contract_v1());
            const std::string exec_sha=sha256_text(execution_policy_v1());
            const std::string run_id=sha256_text(legacy_run_id_material(self_sha,ticks_sha,intent_sha,event_sha,exec_sha));
            const std::string ledger_sha=sha256_file(argv[4]);
            const std::string zero_hash(64,'0');
            const std::string receipt = replay_receipt_v3(run_id,ticks_sha,intent_sha,ledger_sha,zero_hash,zero_hash,zero_hash,event_sha,exec_sha,self_sha);
            atomic_write_text(receipt_path_for(argv[4]),receipt);
            std::cout << data;
            return t.reason==ExitReason::DataError?4:0;
        }
        if(cmd=="replay-qdata"){
            if(argc!=9){usage();return 2;}
            const auto manifest=read_qdata_manifest(argv[4]);
            const auto qda=audit_qdata_authority(argv[2],argv[3],argv[4],argv[5],argv[6]);
            if(!(qda.research_ready || qda.test_ready)) {
                CanonicalText e(160); e.append("QDATA_NOT_EXECUTION_READY: "); e.append(qda.message); throw std::runtime_error(e.str_ref());
            }
            auto intent=read_intent(argv[7]);
            const std::string event_sha=sha256_text(event_phase_contract_v1());
            const std::string exec_sha=sha256_text(execution_policy_v1());
            if(intent.qdata_manifest_sha256.empty()) throw std::runtime_error("QROS_INTENT_V2_REQUIRED_FOR_QDATA");
            if(intent.data_sha256!=qda.dataset_sha256 || intent.qdata_manifest_sha256!=qda.manifest_sha256 || intent.sessions_sha256!=qda.sessions_sha256)
                throw std::runtime_error("QDATA_INTENT_AUTHORITY_BINDING_MISMATCH");
            if(intent.event_contract_sha256!=event_sha || intent.execution_policy_sha256!=exec_sha)
                throw std::runtime_error("QDATA_INTENT_SEMANTIC_CONTRACT_MISMATCH");
            if(manifest.dataset_sha256!=intent.data_sha256 || manifest.sessions_sha256!=intent.sessions_sha256)
                throw std::runtime_error("QDATA_MANIFEST_INTENT_MISMATCH");

            const auto sessions=read_session_map_csv(argv[3]);
            const auto* sb=find_session(sessions,intent.signal_session_day);
            if(sb==nullptr) throw std::runtime_error("SIGNAL_SESSION_NOT_IN_AUTHORITY_MAP");
            if(intent.session_close_seq!=sb->close_seq) throw std::runtime_error("INTENT_SESSION_CLOSE_NOT_AUTHORITY_CLOSE");

            auto t=replay_qdata_stream_bound(argv[2],intent.data_sha256,intent);
            const std::string data=make_trade_csv(intent,t);
            atomic_write_text(argv[8],data);

            const auto qdata_receipt=qdata_audit_receipt(manifest,qda);
            const auto qdata_receipt_sha=sha256_text(qdata_receipt);
            const auto intent_sha=sha256_file(argv[7]);
            const auto ledger_sha=sha256_file(argv[8]);
            const auto run_id=sha256_text(qdata_run_id_material(self_sha,qda,intent_sha,event_sha,exec_sha));
            const auto receipt=replay_receipt_v3(run_id,qda.dataset_sha256,intent_sha,ledger_sha,qda.manifest_sha256,qda.sessions_sha256,qdata_receipt_sha,event_sha,exec_sha,self_sha);
            atomic_write_text(receipt_path_for(argv[8]),receipt);
            std::cout<<data;
            return t.reason==ExitReason::DataError?4:0;
        }
        if(cmd=="contracts"){
            if(argc!=2){usage();return 2;}
            const auto event=event_phase_contract_v1();
            const auto exec=execution_policy_v1();
            std::cout<<"engine_version="<<qros::build_identity::engine_version<<"\n"
                     <<"source_root_sha256="<<qros::build_identity::source_root_sha256<<"\n"
                     <<"build_type="<<qros::build_identity::build_type<<"\n"
                     <<"build_contract_sha256="<<qros::build_identity::build_contract_sha256<<"\n"
                     <<"entrypoint_sha256="<<self_sha<<"\n"
                     <<"compiler="<<qros::build_identity::compiler_id<<" "<<qros::build_identity::compiler_version<<"\n"
                     <<event<<"event_contract_sha256="<<sha256_text(event)<<"\n"<<exec<<"execution_policy_sha256="<<sha256_text(exec)<<"\n";
            return 0;
        }
        if(cmd=="sha256"){
            if(argc!=3){usage();return 2;}
            std::cout<<sha256_file(argv[2])<<"  "<<argv[2]<<"\n"; return 0;
        }
        if(cmd=="bench"){
            if(argc!=3){usage();return 2;}
            std::size_t n=std::stoull(argv[2]);
            if(n<10) n=10;
            std::vector<Tick> ticks; ticks.reserve(n);
            const i64 day=20260827;
            for(std::size_t i=0;i<n;++i){
                i64 base=200000000 + static_cast<i64>(i%1000);
                ticks.push_back(Tick{static_cast<u64>(i+1), static_cast<i64>(i+1), day, base, base+20});
            }
            Intent x{"BENCH",std::string(64,'0'),Side::Buy,1,1,day,static_cast<u64>(n),1000000,1000000};
            auto t0=std::chrono::steady_clock::now();
            auto a=audit_ticks(ticks);
            auto tr=replay_market_after_signal(ticks,x);
            auto t1=std::chrono::steady_clock::now();
            std::chrono::duration<double> d=t1-t0;
            std::cout<<"rows="<<n<<" seconds="<<d.count()<<" rows_per_sec="<<(double(n)/d.count())
                     <<" audit="<<(a.pass?"PASS":"FAIL")<<" replay_reason="<<exit_reason_name(tr.reason)<<"\n";
            return 0;
        }
        usage(); return 2;
    } catch(const std::exception& e){ std::cerr<<"ERROR: "<<e.what()<<"\n"; return 1; }
}
