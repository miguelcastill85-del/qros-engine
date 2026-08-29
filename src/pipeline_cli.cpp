#include "qros/pipeline.hpp"
#include "qros/build_identity.hpp"
#include "qros/sha256.hpp"
#include <algorithm>
#include <iostream>
#include <sstream>

namespace qros::pipeline {
namespace {
void infrastructure_only(const Program& p,const DataSpec& d) {
    if(p.symbol!=d.symbol||p.purpose!=d.purpose) fail("PROGRAM_DATA_SCOPE_MISMATCH");
    if(p.purpose!="TEST_ONLY") fail("RESEARCH_BLOCKED_EXTERNAL_TIME_QDATA_AND_FROZEN_ONTOLOGY_REQUIRED");
}
std::vector<std::string> committed_chunks(const std::filesystem::path& root) {
    const auto head=read_fields(root/"control/HEAD","QROS_RESULT_HEAD_V1");
    std::vector<std::string> chunks;
    for(u64 seq=1;seq<=natural(head.at("seq"));++seq) {
        const auto f=read_fields(root/"control"/("commit-"+std::to_string(seq)+".receipt"),"QROS_CHUNK_COMMIT_V1");
        chunks.push_back(bounded_text(safe_relative(root/"chunks",f.at("chunk")),512U*1024U*1024U));
    }
    return chunks;
}
std::map<std::string,u64> previous_identities(const std::filesystem::path& root) {
    std::map<std::string,u64> ids;
    for(const auto& text:committed_chunks(root)) {
        std::istringstream in(text);std::string line;
        while(std::getline(in,line)) if(line.starts_with("BIRTH,")) {
            const auto c=split(line,',');
            if(c[3]=="EXECUTED"||c[3]=="UNRESOLVED") ids.try_emplace(c[2],natural(c[1]));
        }
    }
    if(ids.size()>1000000)fail("IDENTITY_CACHE_BUDGET_EXCEEDED");
    return ids;
}
void finalize_run(ResultStore& store,const Program& program,const DataSpec& data,const std::string& binding) {
    std::string ledger=ledger_header();u64 raw_count=0,aliases=0,excluded=0,unresolved=0,executed=0;
    for(const auto& text:committed_chunks(store.root())) {
        std::istringstream in(text);std::string line;
        while(std::getline(in,line)) {
            if(line.starts_with("BIRTH,")) {
                const auto c=split(line,',');if(natural(c[1])!=raw_count++)fail("FINAL_COVERAGE_DISCONTINUITY");
                if(c[3]=="ALIAS")++aliases;else if(c[3]=="EXCLUDED")++excluded;else if(c[3]=="UNRESOLVED")++unresolved;else ++executed;
            } else if(line.starts_with("TRADE,")) ledger+=line.substr(6)+"\n";
        }
        if(ledger.size()>128U*1024U*1024U)fail("FINAL_LEDGER_BUDGET_EXCEEDED");
    }
    if(raw_count!=program.births)fail("FINAL_COVERAGE_INCOMPLETE");
    const auto ledger_path=store.root()/"final/trades.csv";
    atomic_write_text(ledger_path,ledger);
    (void)read_ledger(ledger_path,sha256_text(ledger));
    const auto receipt=fields_text("QROS_MINING_COMPLETION_V1",{{"program_sha256",program.spec_sha},{"dataset_spec_sha256",data.sha256},
        {"binding_sha256",binding},{"head_sha256",store.committed_head()},{"coverage_end",std::to_string(raw_count)},{"n_tests_raw",std::to_string(program.births)},
        {"executed_identities",std::to_string(executed)},{"aliases",std::to_string(aliases)},{"causal_exclusions",std::to_string(excluded)},
        {"unresolved",std::to_string(unresolved)},{"ledger_sha256",sha256_text(ledger)},{"purpose",program.purpose},
        {"scientific_head_promoted","0"},{"branch_exhausted","0"},{"status",unresolved?"STAGE_FINISHED_WITH_UNRESOLVED_TRADES":"TEST_STAGE_COMPLETE"}});
    atomic_write_text(store.root()/"final/COMPLETED.receipt",receipt);
    std::cout<<receipt;
}
int mine(int argc,char** argv,const std::string& self_sha,bool one) {
    if((one&&argc!=9)||(!one&&argc!=12))fail("usage: mine program sha dataset sha vault sha result_dir chunk_births max_chunks max_rows; backtest omits last 3 arguments");
    const auto program=read_program(argv[2],argv[3]);const auto data=read_data_spec(argv[4],argv[5]);
    infrastructure_only(program,data);
    enforce_vault(data,argv[6],argv[7],"DEVELOPMENT",program.spec_sha);
    if(one&&program.births!=1)fail("BACKTEST_REQUIRES_SINGLE_FROZEN_CANDIDATE_USE_MINE_FOR_UNIVERSE");
    const u64 chunk=one?1:natural(argv[9]),max_chunks=one?1:natural(argv[10]),max_rows=one?100000000:natural(argv[11]);
    if(chunk<1||chunk>2000||max_chunks<1||max_chunks>100000||max_rows<1)fail("RESOURCE_BUDGET_RANGE");
    const auto binding=sha256_text(fields_text("QROS_PIPELINE_RUN_BINDING_V1",{{"program",program.spec_sha},{"dataset",data.sha256},
        {"vault",argv[7]},{"entrypoint",self_sha},{"source_root",qros::build_identity::source_root_sha256},{"phase","DEVELOPMENT"}}));
    ResultStore store(argv[8],"NATIVE_MINER",self_sha,binding);
    if(store.committed_end()>program.births)fail("RESUME_RANGE_OUTSIDE_UNIVERSE");
    auto known=previous_identities(store.root());u64 dispatched=0;
    while(store.committed_end()<program.births&&dispatched<max_chunks) {
        const u64 start=store.committed_end(),end=start+std::min(chunk,program.births-start);
        std::vector<Candidate> candidates;std::vector<std::unique_ptr<BacktestState>> runs;
        std::map<std::string,std::unique_ptr<FeatureGraph>> graphs;
        std::map<std::string,u64> local_ids=known;
        std::vector<std::string> statuses,details;u64 total_state_values=0;
        for(u64 birth=start;birth<end;++birth) {
            auto c=compile_candidate(program,birth);std::string status="EXECUTED",detail="0";
            if(!c.eligible){status="EXCLUDED";detail=c.exclusion;}
            else if(local_ids.contains(c.id)){status="ALIAS";detail=std::to_string(local_ids.at(c.id));}
            else {
                local_ids.emplace(c.id,birth);
                if(!graphs.contains(c.graph_id)) {
                    for(const auto& node:c.nodes)if(node.op=="EMA"||node.op=="LAG"||node.op=="HIGHEST"||node.op=="LOWEST")total_state_values+=static_cast<u64>(node.parameter)+1;
                    if(total_state_values>2000000)fail("COHORT_FEATURE_MEMORY_BUDGET");
                    graphs.emplace(c.graph_id,std::make_unique<FeatureGraph>(c.nodes));
                }
            }
            runs.push_back(status=="EXECUTED"?std::make_unique<BacktestState>(c,100000):nullptr);
            candidates.push_back(std::move(c));statuses.push_back(status);details.push_back(detail);
        }
        std::vector<FeatureGraph*> graph_array;std::map<std::string,std::size_t> graph_indices;
        for(auto& [id,graph]:graphs){graph_indices.emplace(id,graph_array.size());graph_array.push_back(graph.get());}
        std::vector<std::size_t> run_graphs(runs.size());
        for(std::size_t i=0;i<runs.size();++i)if(runs[i])run_graphs[i]=graph_indices.at(candidates[i].graph_id);
        std::vector<const std::vector<Value>*> values(graph_array.size(),nullptr);
        std::cout<<"START_CHUNK start="<<start<<" end="<<end<<" graphs="<<graphs.size()<<"\n"<<std::flush;
        u64 total_trades=0,observed_rows=0;
        const auto audit=walk_data(data,[&](const Tick& tick,const SessionBoundary& session){
            for(std::size_t i=0;i<graph_array.size();++i)values[i]=&graph_array[i]->update(tick);
            for(std::size_t i=0;i<runs.size();++i)if(runs[i]){
                const auto before=runs[i]->trades().size();
                runs[i]->update(tick,session,values[run_graphs[i]]->at(candidates[i].signal_node));
                total_trades+=runs[i]->trades().size()-before;
            }
            if(total_trades>200000)fail("COHORT_TRADE_MEMORY_BUDGET");
            if(++observed_rows%1000000==0)std::cout<<"TICKS "<<observed_rows<<"\n"<<std::flush;
        },true,max_rows);
        std::string content="QROS_RESULT_CHUNK_V1\nstart="+std::to_string(start)+"\nend="+std::to_string(end)+"\n";
        content+="DATA,"+sha256_text(data_receipt(data,audit))+"\n";
        for(std::size_t i=0;i<candidates.size();++i) {
            const auto& c=candidates[i];
            if(runs[i]){runs[i]->finish();details[i]=std::to_string(runs[i]->trades().size());if(runs[i]->unresolved()>0)statuses[i]="UNRESOLVED";}
            content+="BIRTH,"+std::to_string(c.birth)+","+c.id+","+statuses[i]+","+details[i]+"\n";
            if(runs[i])for(const auto& t:runs[i]->trades())content+="TRADE,"+ledger_row(t);
        }
        store.commit(start,end,content,store.committed_head());known=std::move(local_ids);++dispatched;
        std::cout<<"COMMITTED coverage="<<end<<"/"<<program.births<<" head="<<store.committed_head()<<"\n"<<std::flush;
    }
    if(store.committed_end()==program.births)finalize_run(store,program,data,binding);
    else std::cout<<"status=PAUSED_AT_CHUNK_BOUNDARY\nnext_birth="<<store.committed_end()<<"\nbackground_running=0\n";
    return 0;
}
}
int command(int argc,char** argv,const std::string& self_sha) {
    const std::string cmd=argv[1];
    if(cmd=="mine"||cmd=="backtest")return mine(argc,argv,self_sha,cmd=="backtest");
    if(cmd=="compile"||cmd=="export-mt5") {
        if(argc!=6)fail("usage: compile|export-mt5 program program_sha birth output");
        const auto p=read_program(argv[2],argv[3]);const auto c=compile_candidate(p,natural(argv[4]));
        if(!c.eligible)fail("CANDIDATE_CAUSALLY_EXCLUDED:"+c.exclusion);
        const auto out=cmd=="compile"?c.canonical:export_mt5(c);
        atomic_write_text(argv[5],out);auto receipt=std::filesystem::path(argv[5]);receipt+=".receipt";
        atomic_write_text(receipt,fields_text("QROS_CANDIDATE_BUILD_RECEIPT_V1",{{"candidate_id",c.id},{"program_sha256",p.spec_sha},{"output_sha256",sha256_text(out)},
            {"entrypoint_sha256",self_sha},{"source_root_sha256",qros::build_identity::source_root_sha256},{"mt5_compiled","0"}}));
        std::cout<<program_receipt(p)<<"candidate_id="<<c.id<<"\n";return 0;
    }
    if(cmd=="data-check"||cmd=="verify-conversion"||cmd=="verify-shards") {
        if(argc!=5)fail("usage: data-check|verify-conversion|verify-shards contract sha receipt");
        std::string result;
        if(cmd=="data-check"){const auto d=read_data_spec(argv[2],argv[3]);result=data_receipt(d,walk_data(d,{},false,d.rows));}
        else if(cmd=="verify-conversion")result=verify_conversion(argv[2],argv[3]);else result=verify_shard_chain(argv[2],argv[3]);
        atomic_write_text(argv[4],result);std::cout<<result;return 0;
    }
    if(cmd=="features") {
        if(argc!=10)fail("usage: features program sha birth dataset sha vault sha output");
        const auto p=read_program(argv[2],argv[3]);const auto c=compile_candidate(p,natural(argv[4]));const auto d=read_data_spec(argv[5],argv[6]);
        infrastructure_only(p,d);enforce_vault(d,argv[7],argv[8],"DEVELOPMENT",c.id);FeatureGraph graph(c.nodes);
        std::string out="seq";for(const auto& node:c.nodes)out+=","+node.name;out+="\n";
        (void)walk_data(d,[&](const Tick& tick,const SessionBoundary&){
            out+=std::to_string(tick.seq);for(const auto& v:graph.update(tick))out+=","+(v.valid?std::to_string(v.value):"NA");out+="\n";
            if(out.size()>64U*1024U*1024U)fail("FEATURE_EXPORT_BUDGET");
        },true,d.rows);
        atomic_write_text(argv[9],out);std::cout<<"feature_store_sha256="<<sha256_text(out)<<"\n";return 0;
    }
    if(cmd=="gates") {
        if(argc!=7)fail("usage: gates ledger sha policy sha report");
        const auto out=gate_report(argv[2],argv[3],argv[4],argv[5]);atomic_write_text(argv[6],out);std::cout<<out;return 0;
    }
    if(cmd=="supergate"||cmd=="mt5-parity") {
        if(argc!=5)fail("usage: supergate|mt5-parity plan sha report");
        const auto out=cmd=="supergate"?supergate_report(argv[2],argv[3]):mt5_parity(argv[2],argv[3]);atomic_write_text(argv[4],out);std::cout<<out;
        return cmd=="mt5-parity"&&out.find("status=PARITY_FAIL\n")!=std::string::npos?2:0;
    }
    if(cmd=="portfolio") {
        if(argc!=6)fail("usage: portfolio plan sha ledger report");
        const auto out=portfolio_report(argv[2],argv[3],argv[4]);atomic_write_text(argv[5],out);std::cout<<out;return 0;
    }
    if(cmd=="vault-check") {
        if(argc!=7)fail("usage: vault-check dataset sha vault sha candidate_sha");
        enforce_vault(read_data_spec(argv[2],argv[3]),argv[4],argv[5],"DEVELOPMENT",argv[6]);std::cout<<"DEVELOPMENT_ACCESS_ALLOWED\n";return 0;
    }
    if(cmd=="vault-consume") {
        if(argc!=7)fail("usage: vault-consume policy sha grant sha receipt_store");
        std::cout<<consume_holdout_grant(argv[2],argv[3],argv[4],argv[5],argv[6]);return 0;
    }
    if(cmd=="capabilities") {
        if(argc!=2)fail("usage: capabilities");
        std::cout<<fields_text("QROS_SOFTWARE_CAPABILITIES_V1",{{"version",qros::build_identity::engine_version},{"language","CXX20_NATIVE"},
            {"production_research_ready","0"},{"data","STREAMING_CSV5_PACKED17_HASH_BOUND_SESSIONS_SHARD_V3"},
            {"compiler","CLOSED_TYPED_DAG_LAZY_FINITE_AXES"},{"miner","DETERMINISTIC_BIRTH_CHUNKS_SHARED_FEATURE_GRAPHS"},
            {"store","LOCAL_FLOCK_FENCING_CAS_IMMUTABLE_HASH_CHAIN"},{"gates","BH_BY_YEAR_BLOCK_SCREEN"},{"holdout","DEVELOPMENT_DENIAL_SINGLE_CONSUMPTION_PRIMITIVE"},
            {"portfolio","TEST_ONLY_LEDGER_ALLOCATION_NOT_JOINT_REPLAY"},{"mt5","EXPORT_AND_PARITY_INFRASTRUCTURE_EXTERNAL_EXECUTION_NOT_VERIFIED"}});return 0;
    }
    return -1;
}
} // namespace qros::pipeline
