#include "qros/research_architecture.hpp"
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>

using namespace qros::architecture;

namespace {
std::uint64_t checks=0;
void check(bool v,const char* label){++checks;if(!v)throw std::runtime_error(label);}
template<class F> void rejects(F&& f,const char* label){bool ok=false;try{f();}catch(const std::exception&){ok=true;}check(ok,label);}
std::string h(char c){return std::string(64,c);}
}

int main(){
    try{
        ResearchEvidence e;
        e.hypothesis_id="H1";e.seed_sha256=h('a');
        ResearchLineage lineage(e);
        auto next=e;
        lineage.advance(ResearchStage::CausalScope,next);
        rejects([&]{ResearchLineage x(e);x.advance(ResearchStage::UniverseBuilt,next);},"stage skip");
        next.rise_fixed_point=true;
        lineage.advance(ResearchStage::UniverseBuilt,next);
        lineage.advance(ResearchStage::RiseFixedPoint,next);
        next.ontology_frozen=true;next.ontology_sha256=h('b');
        lineage.advance(ResearchStage::OntologyFrozen,next);
        next.config_frozen=true;next.config_root_sha256=h('c');next.n_tests=100;
        lineage.advance(ResearchStage::ConfigFrozen,next);
        next.independent_parity=true;
        lineage.advance(ResearchStage::IndependentParity,next);
        next.dataset_sha256=h('d');next.unit_binding_pass=true;
        lineage.advance(ResearchStage::DevelopmentBacktest,next);
        next.economic_pnl_read=true;
        lineage.advance(ResearchStage::GateA,next);
        rejects([&]{auto bad=next;bad.holdout_authorized=false;lineage.advance(ResearchStage::HoldoutAuthorized,bad);},"holdout auth");
        auto drift=next;drift.holdout_authorized=true;drift.n_tests=101;
        rejects([&]{lineage.advance(ResearchStage::HoldoutAuthorized,drift);},"n_tests drift");
        next.holdout_authorized=true;
        lineage.advance(ResearchStage::HoldoutAuthorized,next);
        next.supergate_pass=true;
        lineage.advance(ResearchStage::Supergate,next);
        lineage.advance(ResearchStage::FinalDecision,next);
        rejects([&]{ResearchEvidence x=e;x.ga2_open=true;ResearchLineage bad(x);},"preregister ga2 firewall");

        Quote q1{1,100,20260105,100,101},q2{2,100,20260105,102,103},q3{3,101,20260105,99,100};
        CausalClock clock;clock.observe(q1);clock.observe(q2);clock.observe(q3);
        rejects([&]{clock.observe(q3);},"seq replay");
        check(entry_fill(q1,Side::Buy,2)==103,"buy ask entry");
        check(entry_fill(q1,Side::Sell,2)==98,"sell bid entry");
        check(exit_fill(q1,Side::Buy,2)==98,"buy bid exit");
        check(exit_fill(q1,Side::Sell,2)==103,"sell ask exit");
        rejects([&]{validate_executable_quote({1,1,20260105,100,100});},"zero spread");
        rejects([&]{(void)entry_fill({1,1,20260105,std::numeric_limits<std::int64_t>::max()-1,std::numeric_limits<std::int64_t>::max()},Side::Buy,4);},"overflow");

        const auto both_buy=resolve_bar_exit({100,120,80,110},Side::Buy,90,115);
        check(both_buy.reason==ExitReason::StopLoss&&both_buy.executable_price_u==90,"SL first buy ambiguity");
        const auto gap_buy=resolve_bar_exit({85,100,80,95},Side::Buy,90,115);
        check(gap_buy.reason==ExitReason::StopLoss&&gap_buy.executable_price_u==85,"buy gap first executable");
        const auto both_sell=resolve_bar_exit({100,120,80,90},Side::Sell,115,85);
        check(both_sell.reason==ExitReason::StopLoss&&both_sell.executable_price_u==115,"SL first sell ambiguity");
        const auto gap_sell=resolve_bar_exit({120,125,100,110},Side::Sell,115,85);
        check(gap_sell.reason==ExitReason::StopLoss&&gap_sell.executable_price_u==120,"sell gap first executable");

        ExecutionAdmission d(3);
        check(d.admit_and_open(20260105,1),"entry 1");
        check(!d.admit_and_open(20260105,2),"one position per asset");
        rejects([&]{d.validate_day_rollover(20260106);},"overnight rejected");
        d.close_position();
        check(!d.admit_and_open(20260105,1),"same bar rejected");
        check(d.admit_and_open(20260105,2),"entry 2");d.close_position();
        check(d.admit_and_open(20260105,3),"entry 3");d.close_position();
        check(!d.admit_and_open(20260105,4),"daily cap");
        d.validate_day_rollover(20260106);
        check(d.admit_and_open(20260106,1),"new day reset");d.close_position();

        AdapterSession s;
        s.submit("A",10);
        rejects([&]{s.submit("A",10);},"duplicate client id");
        s.apply("A",{1,s.epoch(),OrderEventKind::Ack,0});
        s.apply("A",{2,s.epoch(),OrderEventKind::PartialFill,4});
        check(s.order("A").filled()==4&&s.order("A").status()==OrderStatus::PartFilled,"partial");
        rejects([&]{s.apply("A",{2,s.epoch(),OrderEventKind::PartialFill,1});},"event replay");
        rejects([&]{s.apply("A",{3,s.epoch(),OrderEventKind::Fill,7});},"overfill");
        s.apply("A",{3,s.epoch(),OrderEventKind::Fill,6});
        check(s.order("A").terminal()&&s.order("A").filled()==10,"final fill");
        rejects([&]{s.apply("A",{4,s.epoch(),OrderEventKind::Cancel,0});},"terminal immutable");
        s.disconnect();
        rejects([&]{s.submit("B",1);},"submit disconnected");
        const auto old_epoch=s.epoch();
        s.reconnect();
        s.submit("B",1);
        rejects([&]{s.apply("B",{1,old_epoch,OrderEventKind::Ack,0});},"stale epoch");
        s.apply("B",{1,s.epoch(),OrderEventKind::Ack,0});
        AdapterSession capped(1);
        capped.submit("ONE",1);
        rejects([&]{capped.submit("TWO",1);},"adapter order resource cap");
        AdapterSession reconnecting;
        reconnecting.submit("R",2);
        reconnecting.apply("R",{7,reconnecting.epoch(),OrderEventKind::Ack,0});
        reconnecting.disconnect();
        reconnecting.reconnect();
        reconnecting.apply("R",{1,reconnecting.epoch(),OrderEventKind::PartialFill,1});
        check(reconnecting.order("R").filled()==1,"sequence resets only across fenced epoch");

        std::mt19937_64 rng(20260920ULL);
        for(std::uint64_t i=0;i<50000U;++i){
            const auto low=static_cast<std::int64_t>(80+(rng()%10U));
            const auto high=static_cast<std::int64_t>(120+(rng()%10U));
            const BarEnvelope b{100,high,low,100};
            const auto r=resolve_bar_exit(b,Side::Buy,90,115);
            check(r.reason==ExitReason::StopLoss,"random ambiguity preserves stop first");
        }

        SupergateEvidence g{true,true,true,true,true,true,true,true,true,true,true,true};
        check(evaluate_supergate(g).pass,"supergate full pass");
        g.sanitizer_pass=false;
        const auto blocked=evaluate_supergate(g);
        check(!blocked.pass&&!blocked.missing.empty()&&blocked.decision=="BLOCKED_SUPERGATE","supergate fail closed");

        std::cout<<"ARCHITECTURE_TESTS_PASS checks="<<checks<<"\n";
        return 0;
    }catch(const std::exception& ex){
        std::cerr<<"ARCHITECTURE_TESTS_FAIL "<<ex.what()<<" checks="<<checks<<"\n";
        return 1;
    }
}
