#include "qros/pipeline.hpp"
#include "qros/sha256.hpp"
#include <algorithm>
#include <sstream>

namespace qros::pipeline {
std::string portfolio_report(const std::filesystem::path& plan,const std::string& hash,const std::filesystem::path& output) {
    const auto f=read_fields(plan,"QROS_PORTFOLIO_PLAN_V1",hash);
    exact_keys(f,{"members_path","members_sha256","per_asset_daily_limit","global_daily_limit","purpose","time_basis","initial_capital_usd_micro"});
    if(f.at("purpose")!="TEST_ONLY") fail("PRODUCTION_PORTFOLIO_REQUIRES_JOINT_REPLAY_VALIDATION");
    if(f.at("time_basis")!="SHARED_UTC") fail("PORTFOLIO_TIME_BASIS_REQUIRED");
    const auto asset_limit=natural(f.at("per_asset_daily_limit")),global_limit=natural(f.at("global_daily_limit"));
    const auto capital=integer(f.at("initial_capital_usd_micro"));
    if((asset_limit!=3&&asset_limit!=5)||global_limit<1||global_limit>10||capital<=0) fail("PORTFOLIO_LIMITS");
    const auto text=bounded_text(safe_relative(plan.parent_path(),f.at("members_path")));
    if(sha256_text(text)!=f.at("members_sha256")) fail("PORTFOLIO_MEMBERS_HASH");
    std::istringstream input(text);std::string line;
    if(!std::getline(input,line)||line!="candidate_id,ledger_path,ledger_sha256,priority,usd_micro_per_unit") fail("PORTFOLIO_MEMBERS_HEADER");
    struct Item {TradeRecord trade;i64 priority{},money_per_unit{};};
    std::vector<Item> items;std::set<std::string> members;
    while(std::getline(input,line)) {
        const auto c=split(line,',');if(c.size()!=5||!hash_valid(c[0])||!members.insert(c[0]).second) fail("PORTFOLIO_MEMBER_DUPLICATE_OR_SCHEMA");
        const auto priority=integer(c[3]),money=integer(c[4]);if(priority<0||money<=0) fail("PORTFOLIO_SCALE_OR_PRIORITY");
        bool found=false;
        for(const auto& t:read_ledger(safe_relative(plan.parent_path(),c[1]),c[2])) if(t.candidate_id==c[0]) {items.push_back({t,priority,money});found=true;}
        if(!found) fail("PORTFOLIO_CANDIDATE_ABSENT");
    }
    std::sort(items.begin(),items.end(),[](const Item& a,const Item& b){
        if(a.trade.trade.entry_ts_ns!=b.trade.trade.entry_ts_ns)return a.trade.trade.entry_ts_ns<b.trade.trade.entry_ts_ns;
        if(a.priority!=b.priority)return a.priority<b.priority;
        return a.trade.candidate_id<b.trade.candidate_id;
    });
    std::map<std::string,i64> busy_until,last_bar;
    std::map<std::pair<std::string,i64>,u64> asset_count;
    std::map<i64,u64> global_count;
    u64 accepted=0,overlap=0,bar_conflict=0,daily_conflict=0;
    std::vector<std::pair<i64,i64>> settlements;
    std::string ledger=ledger_header();
    for(const auto& item:items) {
        const auto& r=item.trade;const auto& t=r.trade;
        const auto bar=t.entry_ts_ns/mul(r.bar_ms,1000000);
        if(busy_until.contains(r.symbol)&&t.entry_ts_ns<=busy_until[r.symbol]){++overlap;continue;}
        // Different bar periods are compared using entry timestamps within each incoming bar.
        if(last_bar.contains(r.symbol)&&last_bar[r.symbol]/mul(r.bar_ms,1000000)==bar){++bar_conflict;continue;}
        const auto key=std::make_pair(r.symbol,t.entry_day);
        if(asset_count[key]>=asset_limit||global_count[t.entry_day]>=global_limit){++daily_conflict;continue;}
        ++accepted;++asset_count[key];++global_count[t.entry_day];busy_until[r.symbol]=t.exit_ts_ns;last_bar[r.symbol]=t.entry_ts_ns;
        settlements.emplace_back(t.exit_ts_ns,mul(r.net_u,item.money_per_unit));ledger+=ledger_row(r);
    }
    std::sort(settlements.begin(),settlements.end());i64 equity=capital,peak=capital,dd=0;
    for(std::size_t i=0;i<settlements.size();) {
        const auto ts=settlements[i].first;i64 pnl=0;
        do{pnl=add(pnl,settlements[i].second);++i;}while(i<settlements.size()&&settlements[i].first==ts);
        equity=add(equity,pnl);peak=std::max(peak,equity);dd=std::max(dd,sub(peak,equity));
    }
    atomic_write_text(output,ledger);
    return fields_text("QROS_PORTFOLIO_RECEIPT_V1",{{"plan_sha256",hash},{"ledger_sha256",sha256_text(ledger)},
        {"offered_trades",std::to_string(items.size())},{"accepted_trades",std::to_string(accepted)},{"overlap_rejections",std::to_string(overlap)},
        {"same_bar_rejections",std::to_string(bar_conflict)},{"daily_limit_rejections",std::to_string(daily_conflict)},
        {"initial_capital_usd_micro",std::to_string(capital)},{"final_capital_usd_micro",std::to_string(equity)},{"settled_drawdown_usd_micro",std::to_string(dd)},
        {"quantity_contracts","1"},{"purpose","TEST_ONLY"},{"scope","DETERMINISTIC_LEDGER_ALLOCATION_DIAGNOSTIC"},{"settlement_order","SUM_ALL_CASHFLOWS_PER_TIMESTAMP"},
        {"joint_strategy_replay_validated","0"},{"mark_to_market_drawdown","NOT_COMPUTED"},{"research_approved","0"}});
}
} // namespace qros::pipeline
