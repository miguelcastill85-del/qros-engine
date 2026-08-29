#include "qros/pipeline.hpp"
#include "qros/sha256.hpp"
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>

using namespace qros;
using namespace qros::pipeline;
namespace {
u64 checks=0;
void check(bool value,const std::string& label){++checks;if(!value)throw std::runtime_error(label);}
template<class Fn> void rejects(Fn fn,const std::string& label){bool rejected=false;try{fn();}catch(const std::exception&){rejected=true;}check(rejected,label);}
void put(const std::filesystem::path& p,const std::string& text){std::ofstream f(p,std::ios::binary|std::ios::trunc);f<<text;if(!f)throw std::runtime_error("test file write");}
Fields base_program(){return {{"name","SYNTHETIC_TEST"},{"symbol","NQX"},{"purpose","TEST_ONLY"},{"seed_sha256",sha256_text("synthetic fixture")},
    {"side","BUY"},{"signal","sig"},{"signal_mode","RISING"},{"stop_u","10"},{"target_u","10"},{"be_trigger_ppm","0"},{"be_offset_u","0"},
    {"trailing_u","0"},{"daily_limit","3"},{"commission_u","0"},{"slippage_u","0"},{"bar_ms","1000"},{"expiry_records","10"},
    {"node.bid","BID"},{"node.zero","CONST:0"},{"node.sig","GT:bid:zero"}};}
Candidate candidate(const std::filesystem::path& root,Fields fields){const auto text=fields_text("QROS_PROGRAM_V1",fields);put(root/"program",text);return compile_candidate(read_program(root/"program",sha256_text(text)),0);}
Tick tick(u64 seq,i64 bid,i64 ask){return {seq,static_cast<i64>(seq)*1000000000,20260105,bid,ask};}
SessionBoundary session(u64 n){return {20260105,1,n,1000000000,static_cast<i64>(n)*1000000000,0};}
std::string chunk(u64 start,u64 end){std::string s="QROS_RESULT_CHUNK_V1\nstart="+std::to_string(start)+"\nend="+std::to_string(end)+"\nDATA,"+sha256_text("synthetic data")+"\n";for(u64 i=start;i<end;++i)s+="BIRTH,"+std::to_string(i)+","+sha256_text(std::to_string(i))+",EXECUTED,0\n";return s;}
}
int main(){
    auto stem=(std::filesystem::temp_directory_path()/"qros-pipeline-XXXXXX").string();
    char* temp=::mkdtemp(stem.data());if(temp==nullptr)return 1;const std::filesystem::path root(temp);
    try {
        check(add(2,3)==5&&sub(2,3)==-1&&mul(-3,4)==-12,"checked arithmetic");
        rejects([]{(void)add(std::numeric_limits<i64>::max(),1);},"add overflow");
        rejects([]{(void)sub(std::numeric_limits<i64>::min(),1);},"sub overflow");
        rejects([]{(void)mul(std::numeric_limits<i64>::max(),2);},"mul overflow");
        rejects([]{(void)natural("-1");},"negative natural");
        rejects([]{(void)integer("1x");},"integer suffix");
        rejects([]{(void)parse_fields("X\na=1\na=2\n","X");},"duplicate field");
        auto f=base_program();auto c=candidate(root,f);
        check(c.nodes.size()==3&&c.signal_node==2,"typed graph compiler");
        f["axis.stop"]="10,10,20";f["stop_u"]="$stop";
        auto raw=fields_text("QROS_PROGRAM_V1",f);put(root/"axes",raw);auto p=read_program(root/"axes",sha256_text(raw));
        check(p.births==3,"raw birth count retains aliases");
        check(compile_candidate(p,0).id==compile_candidate(p,1).id,"exact alias identity");
        check(compile_candidate(p,0).id!=compile_candidate(p,2).id,"risk affects identity");
        rejects([&]{(void)compile_candidate(p,3);},"birth range");
        f["require.risk"]="LT:$stop:20";raw=fields_text("QROS_PROGRAM_V1",f);put(root/"constraint",raw);p=read_program(root/"constraint",sha256_text(raw));
        check(!compile_candidate(p,2).eligible,"causal exclusion retained");
        f=base_program();f["node.bid"]="ADD:sig:zero";rejects([&]{(void)candidate(root,f);},"DAG cycle");
        f=base_program();f["node.sig"]="AND:bid:zero";rejects([&]{(void)candidate(root,f);},"type mismatch");
        f=base_program();f["node.extra"]="BID";rejects([&]{(void)candidate(root,f);},"unused node");
        f=base_program();f["node.sig"]="EXEC:bid:zero";rejects([&]{(void)candidate(root,f);},"no executable DSL");
        {
            FeatureGraph g({{"bid","BID",{},0,ValueType::Number},{"lag","LAG",{0},1,ValueType::Number},{"ema","EMA",{0},2,ValueType::Number}});
            auto v=g.update(tick(1,10,11));check(!v[1].valid&&!v[2].valid,"warmup unavailable");
            v=g.update(tick(2,13,14));check(v[1].valid&&v[1].value==10&&v[2].value==12,"lag and integer EMA");
            v=g.update(tick(3,19,20));check(v[1].value==13&&v[2].value==16,"EMA state carried");
        }
        {
            FeatureGraph g({{"close","CLOSE",{},1000,ValueType::Number}});
            Tick a{1,1100000000,20260105,100,101},b{2,1900000000,20260105,105,106},d{3,2100000000,20260105,90,91};
            check(!g.update(a)[0].valid&&!g.update(b)[0].valid,"open bar not visible");
            const auto v=g.update(d)[0];check(v.valid&&v.value==105&&v.version==2,"closed bar without lookahead");
        }
        {
            auto config=candidate(root,base_program());config.target_u=4;BacktestState s(config,20);
            s.update(tick(1,100,101),session(4),{1,true,1});s.update(tick(2,100,101),session(4),{1,true,1});
            s.update(tick(3,105,106),session(4),{1,true,1});s.update(tick(4,106,107),session(4),{1,true,1});s.finish();
            const auto& v=s.trades();check(v.size()==1&&v[0].trade.entry_seq==2&&v[0].trade.exit_seq==3,"next-record causality");
            check(v[0].trade.entry_price_u==101&&v[0].trade.exit_price_u==105&&v[0].trade.reason==ExitReason::TakeProfit,"BUY Ask Bid target");
        }
        {
            auto config=candidate(root,base_program());config.be_trigger_ppm=600000;config.be_offset_u=2;BacktestState s(config,20);
            s.update(tick(1,100,101),session(5),{1,true,1});s.update(tick(2,100,101),session(5),{1,true,1});
            s.update(tick(3,107,108),session(5),{1,true,1});s.update(tick(4,102,103),session(5),{1,true,1});s.update(tick(5,100,101),session(5),{1,true,1});s.finish();
            check(s.trades().size()==1&&s.trades()[0].trade.exit_seq==4&&s.trades()[0].trade.pnl_u==1,"BE next quote and gap observed fill");
        }
        {
            auto config=candidate(root,base_program());config.side=Side::Sell;config.target_u=4;BacktestState s(config,20);
            s.update(tick(1,100,101),session(4),{1,true,1});s.update(tick(2,100,101),session(4),{1,true,1});
            s.update(tick(3,94,95),session(4),{1,true,1});s.update(tick(4,93,94),session(4),{1,true,1});s.finish();
            check(s.trades()[0].trade.entry_price_u==100&&s.trades()[0].trade.exit_price_u==95&&s.trades()[0].trade.pnl_u==5,"SELL Bid Ask target");
        }
        {
            auto config=candidate(root,base_program());BacktestState s(config,20);
            s.update(tick(1,100,101),session(4),{1,true,1});s.update(tick(2,100,100),session(4),{1,true,1});
            s.update(tick(3,100,101),session(4),{1,true,1});s.update(tick(4,100,100),session(4),{1,true,1});s.finish();
            check(s.unresolved()==1&&s.trades().empty(),"zero spread no fabricated close");
        }
        {
            const auto q=adjust_pvalues({0.01L,0.04L,0.03L},3,false);
            check(std::fabs(q[0]-0.03L)<1e-15L&&std::fabs(q[1]-0.04L)<1e-15L&&std::fabs(q[2]-0.04L)<1e-15L,"BH exact known example");
            const auto by=adjust_pvalues({0.01L,0.04L,0.03L},3,true);check(std::fabs(by[0]-0.055L)<1e-15L,"BY harmonic factor");
            rejects([]{(void)adjust_pvalues({0.1L,0.2L},1,false);},"multiplicity undercount denied");
            rejects([]{(void)adjust_pvalues({-0.1L},1,false);},"invalid pvalue denied");
        }
        {
            const auto first=sha256_text("portfolio first"),second=sha256_text("portfolio second");
            const auto a=ledger_header()+first+",0,NQX,BUY,2,2000000000,20260105,100,3,3000000000,110,TP,10,10,0,10,0,10,1000\n";
            const auto b=ledger_header()+second+",1,XAUUSD,BUY,2,2000000000,20260105,100,3,3000000000,90,SL,-10,-10,0,10,-10,0,1000\n";
            put(root/"portfolio-a.csv",a);put(root/"portfolio-b.csv",b);
            const auto members="candidate_id,ledger_path,ledger_sha256,priority,usd_micro_per_unit\n"+first+",portfolio-a.csv,"+sha256_text(a)+",0,1\n"+second+",portfolio-b.csv,"+sha256_text(b)+",1,1\n";
            put(root/"members.csv",members);
            const auto plan=fields_text("QROS_PORTFOLIO_PLAN_V1",{{"members_path","members.csv"},{"members_sha256",sha256_text(members)},
                {"per_asset_daily_limit","3"},{"global_daily_limit","5"},{"purpose","TEST_ONLY"},{"time_basis","SHARED_UTC"},{"initial_capital_usd_micro","1000"}});
            put(root/"portfolio.plan",plan);
            const auto report=parse_fields(portfolio_report(root/"portfolio.plan",sha256_text(plan),root/"allocated.csv"),"QROS_PORTFOLIO_RECEIPT_V1");
            check(report.at("accepted_trades")=="2"&&report.at("final_capital_usd_micro")=="1000"&&report.at("settled_drawdown_usd_micro")=="0","simultaneous cross-asset settlements are atomic");
        }
        const auto self=sha256_text("unit-test-entrypoint"),binding=sha256_text("unit-test-input");
        std::string head;
        {
            ResultStore store(root/"store","TEST",self,binding);
            rejects([&]{ResultStore competing(root/"store","TEST",self,binding);},"same scope ownership");
            rejects([&]{store.commit(0,1,chunk(0,1)+"TRADE,malformed\n",store.committed_head());},"malformed trade not committed");
            rejects([&]{auto text=chunk(0,1);text.replace(text.find("EXECUTED,0"),10,"EXECUTED,1");store.commit(0,1,text,store.committed_head());},"declared trade count enforced");
            store.commit(0,2,chunk(0,2),store.committed_head());head=store.committed_head();
            rejects([&]{store.commit(2,3,chunk(2,3),std::string(64,'0'));},"stale head CAS");
        }
        {ResultStore store(root/"store","TEST",self,binding);check(store.committed_end()==2&&store.committed_head()==head,"exact resume");}
        rejects([&]{ResultStore store(root/"store","TEST",self,sha256_text("other-input"));},"input drift denied");
        put(root/"store/control/HEAD",fields_text("QROS_RESULT_HEAD_V1",{{"seq","0"},{"end","0"},{"head_sha256",std::string(64,'0')}}));
        {ResultStore store(root/"store","TEST",self,binding);check(store.committed_end()==2&&store.committed_head()==head,"durable orphan commit recovered");}
        put(root/"store/chunks/0-2.chunk","corrupted\n");rejects([&]{ResultStore store(root/"store","TEST",self,binding);},"corrupt chunk denied");
        std::cout<<"PIPELINE_TESTS_PASS checks="<<checks<<"\n";
        std::filesystem::remove_all(root);return 0;
    }catch(const std::exception& e){std::cerr<<"PIPELINE_TESTS_FAIL: "<<e.what()<<" fixture="<<root<<"\n";return 1;}
}
