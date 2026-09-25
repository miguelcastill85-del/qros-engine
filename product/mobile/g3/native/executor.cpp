// QROS G3 independent C++20 synthetic quote oracle. NO broker feeds, real PnL or live execution.
// Input contract QROS_G3_SYNTHETIC_TIMELINE_V1. No third-party JSON, no shared Python logic.
#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <limits>
#include <map>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using I=std::int64_t;
constexpr I MAXP=100000000;
[[noreturn]] void reject(const std::string& s){throw std::runtime_error(s);}
std::vector<std::string> split(const std::string& s){
  std::vector<std::string> out; std::size_t start=0;
  while(true){const auto p=s.find('|',start);out.push_back(s.substr(start,p==std::string::npos?std::string::npos:p-start));
    if(p==std::string::npos)break;
    start=p+1;
  }
  return out;
}
I number(const std::string& s,I min,I max){
  if(s.empty()||(s.size()>1&&s[0]=='0'))reject("INTEGER_CANONICAL");
  I n=0;
  for(const unsigned char c:s){
    if(c<'0'||c>'9')reject("INTEGER_CANONICAL");
    if(n>(max-static_cast<I>(c-'0'))/10)reject("INTEGER_RANGE");
    n=n*10+static_cast<I>(c-'0');
  }
  if(n<min||n>max)reject("INTEGER_RANGE");
  return n;
}
bool validId(const std::string& s){
  if(s.empty()||s.size()>32)return false;
  for(const unsigned char c:s)if(!((c>='A'&&c<='Z')||(c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='_'||c=='-'))return false;
  return true;
}
struct Tick{I t,bid,ask,bl,bh,al,ah,session;bool end;};
struct Plan{std::string id,side;I signal,entry,stop,target;};
struct Scenario{std::vector<Tick> ticks;std::vector<Plan> plans;};
Scenario readScenario(){
  std::string raw,line;std::size_t input_bytes=0;std::vector<std::string> lines;
  while(std::getline(std::cin,line)){
    input_bytes+=line.size()+1;
    if(input_bytes>4000000||line.find('\r')!=std::string::npos)reject("INPUT_ENCODING_OR_SIZE");
    lines.push_back(line);
  }
  std::size_t i=0;
  if(lines.empty()||lines[i++]!="QROS_G3_SYNTHETIC_TIMELINE_V1")reject("HEADER");
  auto count=[&](const std::string& key,I max)->I{
    if(i>=lines.size())reject("COUNT_"+key);
    auto fields=split(lines[i++]);
    if(fields.size()!=2||fields[0]!=key)reject("COUNT_"+key);
    return number(fields[1],1,max);
  };
  Scenario sc;const I n=count("TICKS",20000);sc.ticks.reserve(static_cast<std::size_t>(n));
  for(I k=0;k<n;k++){
    if(i>=lines.size())reject("TRUNCATED_TICKS");
    const auto f=split(lines[i++]);if(f.size()!=9)reject("TICK_FIELDS");
    Tick t{number(f[0],1,9999999999999LL),number(f[1],1,MAXP),number(f[2],1,MAXP),
      number(f[3],1,MAXP),number(f[4],1,MAXP),number(f[5],1,MAXP),number(f[6],1,MAXP),
      number(f[7],1,9999999),number(f[8],0,1)==1};
    if(!(t.bl<=t.bid&&t.bid<=t.bh&&t.al<=t.ask&&t.ask<=t.ah&&t.ask>t.bid))reject("PRICE_OR_RANGE");
    if(!sc.ticks.empty()){
      const Tick& last=sc.ticks.back();
      if(t.t<=last.t||t.session<last.session)reject("TEMPORAL_ORDER");
      if(t.session!=last.session&&!last.end)reject("UNSIGNALED_SESSION_BOUNDARY");
      if(t.session==last.session&&last.end)reject("SESSION_AFTER_END");
    }
    sc.ticks.push_back(t);
  }
  if(!sc.ticks.back().end)reject("LAST_SESSION_NOT_CLOSED");
  const I m=count("PLANS",10000);sc.plans.reserve(static_cast<std::size_t>(m));
  std::set<std::string> seen;
  for(I k=0;k<m;k++){
    if(i>=lines.size())reject("TRUNCATED_PLANS");
    const auto f=split(lines[i++]);
    if(f.size()!=6)reject("PLAN_FIELDS");
    if(!validId(f[0])||!seen.insert(f[0]).second||(f[1]!="BUY"&&f[1]!="SELL"))reject("PLAN_ID_OR_SIDE");
    Plan p{f[0],f[1],number(f[2],0,n-1),number(f[3],0,n-1),number(f[4],1,100000),number(f[5],1,100000)};
    if(p.signal>=p.entry||sc.ticks[static_cast<std::size_t>(p.signal)].session!=sc.ticks[static_cast<std::size_t>(p.entry)].session||sc.ticks[static_cast<std::size_t>(p.entry)].end)
      reject("LOOKAHEAD_OR_OVERNIGHT_ENTRY");
    sc.plans.push_back(p);
  }
  if(i+1!=lines.size()||lines.back()!="END")reject("TRAILING_DATA");
  return sc;
}
struct Open{Plan p;I entered,price,sl,tp;};
std::string run(const Scenario& s){
  std::vector<Plan> pending=s.plans;
  std::sort(pending.begin(),pending.end(),[](const Plan& a,const Plan& b){
    if(a.entry!=b.entry)return a.entry<b.entry;
    return a.id<b.id;
  });
  std::map<std::string,std::string> outcomes;
  std::map<I,I> daily;
  std::optional<Open> pos;
  I lastExit=-1;std::size_t cursor=0;
  for(std::size_t index=0;index<s.ticks.size();index++){
    const I ix=static_cast<I>(index);const auto& q=s.ticks[index];
    if(pos.has_value()&&ix>pos->entered){
      const Open& p=*pos;bool stop=false,target=false;I exit=0;std::string why;
      if(p.p.side=="BUY"){
        stop=q.bl<=p.sl;target=q.bh>=p.tp;
        if(stop){exit=std::min(p.sl,q.bid);why="SL_FIRST";}
        else if(target){exit=std::max(p.tp,q.bid);why="TP";}
        else if(q.end){exit=q.bid;why="SESSION_CLOSE";}
      }else{
        stop=q.ah>=p.sl;target=q.al<=p.tp;
        if(stop){exit=std::max(p.sl,q.ask);why="SL_FIRST";}
        else if(target){exit=std::min(p.tp,q.ask);why="TP";}
        else if(q.end){exit=q.ask;why="SESSION_CLOSE";}
      }
      if(!why.empty()){
        outcomes[p.p.id]="FILL|"+p.p.id+"|"+p.p.side+"|"+std::to_string(p.entered)+"|"+std::to_string(p.price)+"|"+std::to_string(p.sl)+"|"+std::to_string(p.tp)+"|"+std::to_string(ix)+"|"+std::to_string(exit)+"|"+why;
        pos.reset();lastExit=ix;
      }
    }
    while(cursor<pending.size()&&pending[cursor].entry==ix){
      Plan p=pending[cursor++];if(q.end)reject("ENTRY_ON_END_TICK");
      std::string why;
      if(pos.has_value())why="POSITION_BUSY";
      else if(lastExit==ix)why="SAME_TICK_REENTRY";
      else if(daily[q.session]>=3)why="DAILY_LIMIT";
      if(!why.empty()){outcomes[p.id]="SKIP|"+p.id+"|"+p.side+"|"+why;continue;}
      const I entry=p.side=="BUY"?q.ask:q.bid;
      const I sl=p.side=="BUY"?entry-p.stop:entry+p.stop;
      const I tp=p.side=="BUY"?entry+p.target:entry-p.target;
      if(sl<=0||tp<=0){outcomes[p.id]="SKIP|"+p.id+"|"+p.side+"|PRICE_LEVEL_INVALID";continue;}
      pos=Open{p,ix,entry,sl,tp};daily[q.session]++;
    }
  }
  if(pos.has_value())reject("UNCLOSED_POSITION");
  if(outcomes.size()!=s.plans.size())reject("UNRECORDED_PLAN");
  std::string result="QROS_G3_RESULTS_V1\n";
  for(const auto& [id,row]:outcomes){(void)id;result+=row+'\n';}
  return result;
}
}
int main(){
  try{std::cout<<run(readScenario());return 0;}
  catch(const std::exception& e){std::cerr<<"QROS_G3_REJECTED:"<<e.what()<<'\n';return 2;}
}
