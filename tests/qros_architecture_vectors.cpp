#include "qros/research_architecture.hpp"
#include <iostream>
using namespace qros::architecture;
int main(){
    const Quote q{1,100,20260105,100,101};
    std::cout<<"BUY_ENTRY="<<entry_fill(q,Side::Buy,2)<<"\n";
    std::cout<<"SELL_ENTRY="<<entry_fill(q,Side::Sell,2)<<"\n";
    std::cout<<"BUY_EXIT="<<exit_fill(q,Side::Buy,2)<<"\n";
    std::cout<<"SELL_EXIT="<<exit_fill(q,Side::Sell,2)<<"\n";
    const auto b=resolve_bar_exit({100,120,80,110},Side::Buy,90,115);
    std::cout<<"BUY_AMBIG_REASON="<<static_cast<int>(b.reason)<<"\n";
    std::cout<<"BUY_AMBIG_PRICE="<<b.executable_price_u<<"\n";
    const auto g=resolve_bar_exit({85,100,80,95},Side::Buy,90,115);
    std::cout<<"BUY_GAP_PRICE="<<g.executable_price_u<<"\n";
    ExecutionAdmission d(3);
    std::cout<<"ADMIT1="<<d.admit_and_open(20260105,1)<<"\n";
    std::cout<<"ADMIT_WHILE_OPEN="<<d.admit_and_open(20260105,2)<<"\n";
    d.close_position();
    std::cout<<"ADMIT2="<<d.admit_and_open(20260105,2)<<"\n";
    AdapterSession s;
    s.submit("R",2);
    s.apply("R",{7,s.epoch(),OrderEventKind::Ack,0});
    s.disconnect();s.reconnect();
    s.apply("R",{1,s.epoch(),OrderEventKind::PartialFill,1});
    std::cout<<"RECONNECT_FILLED="<<s.order("R").filled()<<"\n";
    return 0;
}
