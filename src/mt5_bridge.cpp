#include "qros/pipeline.hpp"
#include "qros/sha256.hpp"
#include "qros/mt5_template.hpp"
#include <algorithm>

namespace qros::pipeline {
std::string export_mt5(const Candidate& c) {
    if(c.slippage_u!=0)fail("MT5_EXPORT_REQUIRES_EXPLICIT_ZERO_SLIPPAGE_REFERENCE_CONFIG");
    const std::vector<std::string> ops={"BID","ASK","SPREAD","CONST","OPEN","HIGH","LOW","CLOSE","ADD","SUB","MIN","MAX","GT","GE","LT","LE","EQ","AND","OR","NOT","LAG","EMA","HIGHEST","LOWEST","CROSS_UP","CROSS_DOWN"};
    std::string out="// QROS generated candidate; requires real MT5 compilation and independent parity.\n#property strict\n#include <Trade/Trade.mqh>\n";
    out+="const string CandidateId=\""+c.id+"\";\nconst string FrozenSpec=\""+c.program_sha+"\";\n";
    out+="const string InternalSymbol=\""+c.symbol+"\";\nconst long Birth="+std::to_string(c.birth)+";\n";
    out+="const int NodeCount="+std::to_string(c.nodes.size())+";\nconst int SignalNode="+std::to_string(c.signal_node)+";\n";
    for(const auto* field:{"Op","Left","Right","Param"}) {
        const std::string key(field);out+=(key=="Param"?"long ":"int ")+key+"[]={";
        for(std::size_t i=0;i<c.nodes.size();++i) {
            if(i)out+=",";
            const auto& n=c.nodes[i];
            if(key=="Op") {
                const auto it=std::find(ops.begin(),ops.end(),n.op);if(it==ops.end())fail("MT5_UNSUPPORTED_OPCODE");
                out+=std::to_string(it-ops.begin());
            } else if(key=="Left")out+=n.inputs.empty()?"-1":std::to_string(n.inputs[0]);
            else if(key=="Right")out+=n.inputs.size()<2?"-1":std::to_string(n.inputs[1]);
            else {if(n.parameter < -1000000000000LL||n.parameter>1000000000000LL)fail("MT5_NUMERIC_DOMAIN_LIMIT");out+=std::to_string(n.parameter);}
        }
        out+="};\n";
    }
    out+="const bool IsBuy="+std::string(c.side==Side::Buy?"true":"false")+";\n";
    out+="const bool EachUpdate="+std::string(c.signal_mode=="EACH_UPDATE"?"true":"false")+";\n";
    for(const auto& [key,value]:Fields{{"StopU",std::to_string(c.stop_u)},{"TargetU",std::to_string(c.target_u)},
        {"BePpm",std::to_string(c.be_trigger_ppm)},{"BeOffsetU",std::to_string(c.be_offset_u)},{"TrailingU",std::to_string(c.trailing_u)},
        {"DailyLimit",std::to_string(c.daily_limit)},{"BarMs",std::to_string(c.bar_ms)},{"ExpiryRecords",std::to_string(c.expiry_records)}})out+="const long "+key+"="+value+";\n";
    out+="const int PriceDecimals="+std::string(c.symbol=="XAUUSD"?"2":"1")+";\n";
    out+=std::string(mt5_runtime);return out;
}

std::string mt5_parity(const std::filesystem::path& plan,const std::string& hash) {
    const auto f=read_fields(plan,"QROS_MT5_PARITY_PLAN_V1",hash);
    exact_keys(f,{"candidate_id","frozen_spec_sha256","expected_path","expected_sha256","observed_path","observed_sha256","provenance_path","provenance_sha256"});
    if(!hash_valid(f.at("candidate_id"))||!hash_valid(f.at("frozen_spec_sha256")))fail("MT5_CANDIDATE_BINDING");
    const auto expected=read_ledger(safe_relative(plan.parent_path(),f.at("expected_path")),f.at("expected_sha256"));
    const auto observed=read_ledger(safe_relative(plan.parent_path(),f.at("observed_path")),f.at("observed_sha256"));
    if(expected.empty()||observed.empty())fail("MT5_PARITY_REQUIRES_OBSERVED_TRADES");
    const auto provenance_path=safe_relative(plan.parent_path(),f.at("provenance_path"));
    const auto p=read_fields(provenance_path,"QROS_MT5_PROVENANCE_V1",f.at("provenance_sha256"));
    exact_keys(p,{"purpose","candidate_id","frozen_spec_sha256","terminal_build","tester_agent_build","broker_server","mode",
        "mq5_path","mq5_sha256","ex5_path","ex5_sha256","set_path","set_sha256","symbol_spec_path","symbol_spec_sha256",
        "observed_ticks_path","observed_ticks_sha256","expected_ticks_sha256","raw_deals_path","raw_deals_sha256"});
    if(p.at("candidate_id")!=f.at("candidate_id")||p.at("frozen_spec_sha256")!=f.at("frozen_spec_sha256"))fail("MT5_PROVENANCE_SCOPE");
    const bool external=p.at("purpose")=="EXTERNAL_MT5";
    if(!external&&p.at("purpose")!="TEST_ONLY")fail("MT5_PROVENANCE_PURPOSE");
    for(const auto* role:{"mq5","ex5","set","symbol_spec","observed_ticks","raw_deals"}) {
        const std::string name(role);const auto file=safe_relative(provenance_path.parent_path(),p.at(name+"_path"));
        if(!hash_valid(p.at(name+"_sha256"))||sha256_file(file)!=p.at(name+"_sha256"))fail("MT5_ARTIFACT_HASH:"+name);
    }
    if(external&&(natural(p.at("terminal_build"))==0||natural(p.at("tester_agent_build"))==0||p.at("mode")!="EVERY_TICK_BASED_ON_REAL_TICKS"))fail("MT5_RUNTIME_PROVENANCE");
    Fields counts={{"DATA","0"},{"SIGNAL","0"},{"FILL","0"},{"COST","0"},{"SESSION","0"}};
    const auto bump=[&](const std::string& key){counts[key]=std::to_string(natural(counts[key])+1);};
    if(expected.size()!=observed.size())bump("DATA");
    if(p.at("expected_ticks_sha256")!=p.at("observed_ticks_sha256"))bump("DATA");
    for(const auto* records:{&expected,&observed})for(const auto& r:*records)if(r.candidate_id!=f.at("candidate_id"))fail("MT5_LEDGER_CANDIDATE_MISMATCH");
    for(std::size_t i=0;i<std::min(expected.size(),observed.size());++i) {
        const auto& a=expected[i];const auto& b=observed[i];const auto& x=a.trade;const auto& y=b.trade;
        if(a.symbol!=b.symbol||x.entry_day!=y.entry_day||x.entry_seq!=y.entry_seq||x.exit_seq!=y.exit_seq||x.entry_ts_ns!=y.entry_ts_ns||x.exit_ts_ns!=y.exit_ts_ns)bump("DATA");
        if(x.side!=y.side||a.birth!=b.birth)bump("SIGNAL");
        if(x.entry_price_u!=y.entry_price_u||x.exit_price_u!=y.exit_price_u)bump("FILL");
        if(a.net_u!=b.net_u||x.pnl_u!=y.pnl_u||a.commission_u!=b.commission_u)bump("COST");
        if(x.reason!=y.reason)bump("SESSION");
        if(x.r_den!=y.r_den||a.mae_u!=b.mae_u||a.mfe_u!=b.mfe_u||a.bar_ms!=b.bar_ms)bump("SIGNAL");
    }
    u64 differences=0;for(const auto& [key,count]:counts){(void)key;differences+=natural(count);}
    counts["plan_sha256"]=hash;counts["candidate_id"]=f.at("candidate_id");counts["frozen_spec_sha256"]=f.at("frozen_spec_sha256");
    counts["expected_trades"]=std::to_string(expected.size());counts["observed_trades"]=std::to_string(observed.size());
    counts["status"]=differences?"PARITY_FAIL":external?"EXTERNAL_RECORDED_PARITY_PASS":"FIXTURE_PARITY_PASS";
    counts["mt5_runtime_independently_executed_here"]="0";counts["provenance_class"]=external?"EXTERNAL_ARTIFACTS_SUPPLIED":"SYNTHETIC_FIXTURE";
    counts["research_approved"]="0";return fields_text("QROS_MT5_PARITY_RECEIPT_V1",counts);
}
} // namespace qros::pipeline
