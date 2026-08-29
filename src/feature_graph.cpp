#include "qros/pipeline.hpp"
#include <algorithm>

namespace qros::pipeline {
FeatureGraph::FeatureGraph(std::vector<Node> nodes):nodes_(std::move(nodes)),states_(nodes_.size()),values_(nodes_.size()) {
    u64 state_values=0;
    for(std::size_t i=0;i<nodes_.size();++i) {
        const auto& n=nodes_[i];
        for(const auto input:n.inputs) if(input>=i) fail("FEATURE_DAG_NOT_TOPOLOGICAL");
        if(n.op=="OPEN"||n.op=="HIGH"||n.op=="LOW"||n.op=="CLOSE") bars_.try_emplace(n.parameter,Bar{});
        if(n.op=="LAG"||n.op=="EMA"||n.op=="HIGHEST"||n.op=="LOWEST") state_values+=static_cast<u64>(n.parameter)+1;
    }
    if(state_values>2000000) fail("FEATURE_STATE_BUDGET_EXCEEDED");
}
const std::vector<Value>& FeatureGraph::update(const Tick& tick) {
    for(auto& [period,bar]:bars_) {
        const i64 bucket=tick.ts_ns/mul(period,1000000);
        if(bar.initialized&&(bar.bucket!=bucket||bar.day!=tick.session_day)) {
            bar.closed_open={bar.open,true,bar.last_seq};bar.closed_high={bar.high,true,bar.last_seq};
            bar.closed_low={bar.low,true,bar.last_seq};bar.closed_close={bar.close,true,bar.last_seq};
            bar.initialized=false;
        }
        if(!bar.initialized) {
            bar.bucket=bucket;bar.day=tick.session_day;bar.open=tick.bid_u;bar.high=tick.bid_u;bar.low=tick.bid_u;bar.initialized=true;
        }
        bar.high=std::max(bar.high,tick.bid_u);bar.low=std::min(bar.low,tick.bid_u);bar.close=tick.bid_u;bar.last_seq=tick.seq;
    }
    for(std::size_t i=0;i<nodes_.size();++i) {
        const auto& n=nodes_[i];auto& state=states_[i];Value out{};
        if(n.op=="BID") out={tick.bid_u,true,tick.seq};
        else if(n.op=="ASK") out={tick.ask_u,true,tick.seq};
        else if(n.op=="SPREAD") out={sub(tick.ask_u,tick.bid_u),true,tick.seq};
        else if(n.op=="CONST") out={n.parameter,true,1};
        else if(n.op=="OPEN") out=bars_.at(n.parameter).closed_open;
        else if(n.op=="HIGH") out=bars_.at(n.parameter).closed_high;
        else if(n.op=="LOW") out=bars_.at(n.parameter).closed_low;
        else if(n.op=="CLOSE") out=bars_.at(n.parameter).closed_close;
        else {
            bool ready=true;u64 version=0;
            for(auto input:n.inputs){ready=ready&&values_[input].valid;version=std::max(version,values_[input].version);}
            if(!ready){values_[i]={0,false,version};continue;}
            if(version==state.last_version){values_[i]=state.output;continue;}
            state.last_version=version;
            const i64 a=values_[n.inputs[0]].value;
            const i64 b=n.inputs.size()>1?values_[n.inputs[1]].value:0;
            out={0,true,version};
            if(n.op=="ADD") out.value=add(a,b);
            else if(n.op=="SUB") out.value=sub(a,b);
            else if(n.op=="MIN") out.value=std::min(a,b);
            else if(n.op=="MAX") out.value=std::max(a,b);
            else if(n.op=="GT") out.value=a>b;
            else if(n.op=="GE") out.value=a>=b;
            else if(n.op=="LT") out.value=a<b;
            else if(n.op=="LE") out.value=a<=b;
            else if(n.op=="EQ") out.value=a==b;
            else if(n.op=="AND") out.value=a!=0&&b!=0;
            else if(n.op=="OR") out.value=a!=0||b!=0;
            else if(n.op=="NOT") out.value=a==0;
            else if(n.op=="CROSS_UP"||n.op=="CROSS_DOWN") {
                out.valid=state.initialized;
                out.value=n.op=="CROSS_UP"?(state.previous_a<=state.previous_b&&a>b):(state.previous_a>=state.previous_b&&a<b);
                state.previous_a=a;state.previous_b=b;state.initialized=true;
            } else if(n.op=="LAG"||n.op=="EMA"||n.op=="HIGHEST"||n.op=="LOWEST") {
                state.history.push_back({a,true,version});const auto window=static_cast<std::size_t>(n.parameter);
                if(n.op=="LAG") {
                    out.valid=state.history.size()>window;
                    if(out.valid){out.value=state.history.front().value;state.history.pop_front();}
                } else if(n.op=="EMA") {
                    out.value=state.initialized?add(state.output.value,mul(2,sub(a,state.output.value))/add(n.parameter,1)):a;
                    state.initialized=true;out.valid=state.history.size()>=window;
                    if(state.history.size()>window) state.history.pop_front();
                } else {
                    if(state.history.size()>window) state.history.pop_front();
                    out.valid=state.history.size()==window;out.value=a;
                    for(const auto& v:state.history) out.value=n.op=="HIGHEST"?std::max(out.value,v.value):std::min(out.value,v.value);
                }
            } else fail("FEATURE_OPCODE_UNIMPLEMENTED:"+n.op);
        }
        state.output=out;values_[i]=out;
    }
    return values_;
}
} // namespace qros::pipeline
