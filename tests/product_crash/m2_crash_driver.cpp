#include "qros/research_ledger.hpp"
#include <iostream>
#include <string>
int main(int argc,char**argv){
 using namespace qros::product;
 if(argc!=3)return 2;
 try {
 ResearchTransitionLedger ledger(argv[2]);
 const std::string mode(argv[1]);
 if(mode=="inspect"){
  const auto h=ledger.inspect();std::cout<<"SEQUENCE="<<h.sequence<<" DIGEST="<<h.digest<<"\n";return 0;
 }
 if(mode=="anchor-genesis"){
  ResearchLedgerHead genesis{}; const auto h=ledger.verify_anchor(genesis);
  std::cout<<"TRUSTED_GENESIS_MATCH="<<h.sequence<<"\n";return 0;
 }
 if(mode=="write"){
  ResearchTransitionRequest r{};r.project_id="FAULT_TEST";r.campaign_id="FAULT_TEST_1";r.authority_ref="TEST_ONLY:controlled_fixture";r.evidence_sha256=std::string(64,'a');
  r.from=ScientificState::New;r.requested=ScientificState::PreregisteredNoResults;r.actor=TransitionActor::QrosCore;r.context.data_audit_pass=true;r.context.preregistration_frozen=true;r.context.evidence_semantics_pass=true;
  auto h=ledger.inspect(); const auto committed=ledger.append(r,h); std::cout<<"COMMITTED="<<committed.head.sequence<<" DIGEST="<<committed.head.digest<<"\n";return committed.decision.allowed?0:3;
 }
 return 2;
 }catch(const std::exception&e){std::cerr<<"DRIVER_FAIL:"<<e.what()<<"\n";return 1;}
}
