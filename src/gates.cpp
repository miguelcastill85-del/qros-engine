#include "qros/pipeline.hpp"
#include "qros/sha256.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <numeric>

namespace qros::pipeline {
Metrics metrics(const std::vector<TradeRecord>& trades) {
    Metrics m;i64 equity=0,peak=0;long double sum=0,squares=0;
    for(const auto& r:trades) {
        ++m.trades;m.net_u=add(m.net_u,r.net_u);equity=add(equity,r.net_u);peak=std::max(peak,equity);
        m.max_dd_u=std::max(m.max_dd_u,sub(peak,equity));
        if(r.net_u>0){++m.wins;m.gross_profit_u=add(m.gross_profit_u,r.net_u);}
        if(r.net_u<0){++m.losses;m.gross_loss_u=sub(m.gross_loss_u,r.net_u);}
        auto& year=m.annual_net[r.trade.entry_day/10000];year=add(year,r.net_u);
        const auto rr=static_cast<long double>(r.net_u)/static_cast<long double>(r.trade.r_den);
        sum+=rr;squares+=rr*rr;
    }
    for(const auto& [year,net]:m.annual_net){(void)year;if(net<0)++m.negative_years;else if(net>0)++m.positive_years;}
    m.expectancy_r=m.trades?sum/static_cast<long double>(m.trades):0;
    m.win_rate=m.trades?static_cast<long double>(m.wins)/static_cast<long double>(m.trades):0;
    m.profit_factor=m.gross_loss_u?static_cast<long double>(m.gross_profit_u)/static_cast<long double>(m.gross_loss_u):
        (m.gross_profit_u?std::numeric_limits<long double>::infinity():std::numeric_limits<long double>::quiet_NaN());
    m.trade_sharpe=std::numeric_limits<long double>::quiet_NaN();
    if(m.trades>1){const auto variance=(squares-sum*sum/static_cast<long double>(m.trades))/static_cast<long double>(m.trades-1);
        if(variance>0)m.trade_sharpe=m.expectancy_r/std::sqrt(variance);}
    return m;
}
std::vector<long double> adjust_pvalues(const std::vector<long double>& p,u64 n_tests,bool by) {
    if(n_tests==0||n_tests<p.size())fail("MULTIPLICITY_FAMILY_UNDERCOUNT");
    for(auto value:p)if(!std::isfinite(value)||value<0||value>1)fail("INVALID_PVALUE");
    std::vector<std::size_t> order(p.size());std::iota(order.begin(),order.end(),0);
    std::stable_sort(order.begin(),order.end(),[&](auto a,auto b){return p[a]<p[b];});
    long double factor=1;
    if(by){
        factor=0;
        if(n_tests<=1000000)for(u64 i=1;i<=n_tests;++i)factor+=1.0L/static_cast<long double>(i);
        else {const auto n=static_cast<long double>(n_tests);factor=std::log(n)+0.57721566490153286060651209L+1/(2*n)-1/(12*n*n);}
    }
    std::vector<long double> q(p.size());long double previous=1;
    for(std::size_t i=order.size();i>0;--i) {
        const auto index=order[i-1];
        const auto adjusted=p[index]*static_cast<long double>(n_tests)*factor/static_cast<long double>(i);
        previous=std::min(previous,std::min(1.0L,adjusted));q[index]=previous;
    }
    return q;
}
namespace {
struct Rng {
    u64 state;
    u64 next(){state^=state>>12U;state^=state<<25U;state^=state>>27U;return state*2685821657736338717ULL;}
};
long double year_sign_pvalue(const std::vector<TradeRecord>& trades,u64 repetitions,u64 seed) {
    if(trades.empty())return 1;
    std::map<i64,long double> blocks;
    for(const auto& t:trades)blocks[t.trade.entry_day/10000]+=static_cast<long double>(t.net_u)/static_cast<long double>(t.trade.r_den);
    long double observed=0;for(const auto& [year,total]:blocks){(void)year;observed+=total;}
    if(observed<=0)return 1;
    Rng rng{seed};u64 greater=0;
    for(u64 i=0;i<repetitions;++i){long double sample=0;for(const auto& [year,total]:blocks){(void)year;sample+=(rng.next()&1U)?total:-total;}if(sample>=observed)++greater;}
    return static_cast<long double>(greater+1)/static_cast<long double>(repetitions+1);
}
}
std::string gate_report(const std::filesystem::path& ledger,const std::string& ledger_sha,const std::filesystem::path& policy,const std::string& policy_sha) {
    const auto f=read_fields(policy,"QROS_GATE_POLICY_V1",policy_sha);
    exact_keys(f,{"program_path","program_sha256","completion_path","completion_sha256","min_trades","min_pf_ppm","max_dd_u",
        "max_negative_years","min_positive_years","alpha_ppm","n_tests","correction","repetitions","rng_seed","method"});
    const auto program=read_program(safe_relative(policy.parent_path(),f.at("program_path")),f.at("program_sha256"));
    const auto completion=read_fields(safe_relative(policy.parent_path(),f.at("completion_path")),"QROS_MINING_COMPLETION_V1",f.at("completion_sha256"));
    if(completion.at("program_sha256")!=program.spec_sha||completion.at("ledger_sha256")!=ledger_sha||natural(completion.at("coverage_end"))!=program.births||completion.at("unresolved")!="0")fail("GATE_INCOMPLETE_OR_UNBOUND_COVERAGE");
    const u64 n=natural(f.at("n_tests")),repetitions=natural(f.at("repetitions")),seed=natural(f.at("rng_seed"));
    if(n!=program.births||repetitions<99||repetitions>1000000||seed==0)fail("GATE_DECLARED_FAMILY_OR_RNG");
    if(f.at("correction")!="BH"&&f.at("correction")!="BY")fail("GATE_CORRECTION");
    if(f.at("method")!="YEAR_BLOCK_SIGN_FLIP_V1")fail("UNSUPPORTED_STATISTICAL_METHOD");
    const auto all=read_ledger(ledger,ledger_sha);std::map<std::string,std::vector<TradeRecord>> grouped;
    for(const auto& t:all)grouped[t.candidate_id].push_back(t);
    if(grouped.size()>100000||(!grouped.empty()&&repetitions>50000000ULL/grouped.size()))fail("STATISTICAL_WORK_BUDGET");
    std::vector<std::string> ids;std::vector<Metrics> ms;std::vector<long double> p;
    for(const auto& [id,trades]:grouped){
        const auto candidate=compile_candidate(program,trades.front().birth);
        if(candidate.id!=id||!candidate.eligible||candidate.symbol!=trades.front().symbol)fail("GATE_CANDIDATE_IDENTITY");
        for(const auto& trade:trades)if(trade.birth!=candidate.birth||trade.symbol!=candidate.symbol||trade.trade.side!=candidate.side||
            trade.trade.r_den!=candidate.stop_u||trade.commission_u!=candidate.commission_u||trade.bar_ms!=candidate.bar_ms)fail("GATE_LEDGER_EXECUTION_SPEC_MISMATCH");
        ids.push_back(id);ms.push_back(metrics(trades));p.push_back(year_sign_pvalue(trades,repetitions,seed));
    }
    const auto q=adjust_pvalues(p,n,f.at("correction")=="BY");
    const auto alpha=static_cast<long double>(natural(f.at("alpha_ppm")))/1000000;
    if(alpha<=0||alpha>=1)fail("ALPHA_RANGE");
    std::string result=fields_text("QROS_GATE_REPORT_V1",{{"policy_sha256",policy_sha},{"ledger_sha256",ledger_sha},{"program_sha256",program.spec_sha},
        {"n_tests",std::to_string(n)},{"candidates_with_trades",std::to_string(ids.size())},{"zero_trade_hypotheses","PVALUE_ONE"},
        {"method",f.at("method")},{"method_assumptions","SYMMETRIC_INDEPENDENT_YEAR_BLOCKS_NOT_AUTOMATICALLY_VERIFIED"},
        {"correction",f.at("correction")},{"purpose",program.purpose},{"research_approved","0"},{"decision_scope","CONFIGURED_SCREEN_ONLY"},{"policy_preregistration_verified","0"}});
    result+="candidate_id,trades,net_u,pf,dd_u,expectancy_r,trade_sharpe,negative_years,p_value,q_value,screen\n";
    for(std::size_t i=0;i<ids.size();++i) {
        const auto& m=ms[i];
        const bool pass=m.trades>=natural(f.at("min_trades"))&&m.profit_factor>=static_cast<long double>(natural(f.at("min_pf_ppm")))/1000000&&
            m.max_dd_u<=integer(f.at("max_dd_u"))&&m.negative_years<=natural(f.at("max_negative_years"))&&m.positive_years>=natural(f.at("min_positive_years"))&&q[i]<=alpha;
        result+=ids[i]+","+std::to_string(m.trades)+","+std::to_string(m.net_u)+","+number(m.profit_factor)+","+std::to_string(m.max_dd_u)+","+
            number(m.expectancy_r)+","+number(m.trade_sharpe)+","+std::to_string(m.negative_years)+","+number(p[i])+","+number(q[i])+","+(pass?"PASS":"FAIL")+"\n";
    }
    return result;
}
std::string supergate_report(const std::filesystem::path& plan,const std::string& plan_sha) {
    const auto f=read_fields(plan,"QROS_SUPERGATE_PLAN_V1",plan_sha);
    exact_keys(f,{"candidate_id","frozen_spec_sha256","gate_path","gate_sha256","oos_path","oos_sha256","robustness_path","robustness_sha256",
        "holdout_path","holdout_sha256","forward_path","forward_sha256","mt5_path","mt5_sha256"});
    if(!hash_valid(f.at("candidate_id"))||!hash_valid(f.at("frozen_spec_sha256")))fail("SUPERGATE_SPEC_IDENTITY");
    Fields report={{"plan_sha256",plan_sha},{"candidate_id",f.at("candidate_id")},{"frozen_spec_sha256",f.at("frozen_spec_sha256")},
        {"research_approved","0"},{"decision_scope","EVIDENCE_INTEGRITY_AGGREGATION"}};
    u64 missing=0;
    for(const auto* role:{"gate","oos","robustness","holdout","forward","mt5"}) {
        const std::string key(role);
        if(f.at(key+"_path")=="UNAVAILABLE") {report[key]="MISSING";++missing;continue;}
        const auto raw=bounded_text(safe_relative(plan.parent_path(),f.at(key+"_path")));
        if(sha256_text(raw)!=f.at(key+"_sha256"))fail("SUPERGATE_EVIDENCE_HASH:"+key);
        if(raw.find("\ncandidate_id="+f.at("candidate_id")+"\n")==std::string::npos||raw.find("\nfrozen_spec_sha256="+f.at("frozen_spec_sha256")+"\n")==std::string::npos)fail("SUPERGATE_EVIDENCE_SCOPE:"+key);
        report[key]="HASH_AND_SCOPE_BOUND_NOT_INDEPENDENTLY_REEXECUTED";
    }
    report["missing"]=std::to_string(missing);
    report["status"]=missing?"BLOCKED_MISSING_VALIDATIONS":"READY_FOR_SCIENTIFIC_REVIEW_NOT_AUTOMATIC_APPROVAL";
    return fields_text("QROS_SUPERGATE_RECEIPT_V1",report);
}
} // namespace qros::pipeline
