#include "qros/pipeline.hpp"
#include "qros/sha256.hpp"
#include <algorithm>
#include <limits>

namespace qros::pipeline {
namespace {
const std::set<std::string> required={"name","symbol","purpose","seed_sha256","side","signal","signal_mode","stop_u","target_u",
    "be_trigger_ppm","be_offset_u","trailing_u","daily_limit","commission_u","slippage_u","bar_ms","expiry_records"};
const std::set<std::string> binary={"ADD","SUB","MIN","MAX","GT","GE","LT","LE","EQ","AND","OR","CROSS_UP","CROSS_DOWN"};
const std::set<std::string> windowed={"LAG","EMA","HIGHEST","LOWEST"};
const std::set<std::string> bars={"OPEN","HIGH","LOW","CLOSE"};
std::string resolve(const std::string& s,const Fields& parameters) {
    if(!s.empty()&&s[0]=='$') {
        const auto it=parameters.find(s.substr(1));if(it==parameters.end()) fail("UNKNOWN_PARAMETER:"+s);
        return it->second;
    }
    return s;
}
}
Program read_program(const std::filesystem::path& path,const std::string& hash) {
    if(!hash_valid(hash)) fail("EXPECTED_PROGRAM_HASH_REQUIRED");
    Program p;p.fields=read_fields(path,"QROS_PROGRAM_V1",hash);p.spec_sha=hash;
    u64 node_count=0;
    for(const auto& key:required) if(!p.fields.contains(key)) fail("PROGRAM_MISSING_KEY:"+key);
    for(const auto& [key,value]:p.fields) {
        if(required.contains(key)) continue;
        if(key.starts_with("node.")) {if(!identifier(key.substr(5))) fail("INVALID_NODE_NAME");if(++node_count>1024)fail("FEATURE_NODE_LIMIT");}
        else if(key.starts_with("axis.")) {
            if(!identifier(key.substr(5))) fail("INVALID_AXIS_NAME");
            std::vector<i64> axis;
            for(const auto& token:split(value,',')) axis.push_back(integer(token));
            if(axis.size()>100000||p.axes.size()>=32||p.births>std::numeric_limits<u64>::max()/axis.size()) fail("UNIVERSE_SIZE_OVERFLOW");
            p.births*=axis.size();p.axis_names.push_back(key.substr(5));p.axes.push_back(std::move(axis));
        } else if(key.starts_with("require.")) {
            if(!identifier(key.substr(8)))fail("INVALID_CONSTRAINT_NAME");
            const auto c=split(value,':');if(c.size()!=3||(c[0]!="LT"&&c[0]!="LE"&&c[0]!="NE"&&c[0]!="EQ")) fail("INVALID_UNIVERSE_CONSTRAINT");
        } else fail("PROGRAM_UNKNOWN_KEY:"+key);
    }
    p.name=p.fields.at("name");p.symbol=p.fields.at("symbol");p.purpose=p.fields.at("purpose");p.seed_sha=p.fields.at("seed_sha256");
    if(!identifier(p.name)||(p.symbol!="NQX"&&p.symbol!="XAUUSD")||!hash_valid(p.seed_sha)) fail("PROGRAM_ID_SYMBOL_OR_SEED");
    if(p.purpose!="TEST_ONLY"&&p.purpose!="RESEARCH") fail("PROGRAM_PURPOSE");
    if(p.fields.at("signal_mode")!="RISING"&&p.fields.at("signal_mode")!="EACH_UPDATE") fail("SIGNAL_MODE");
    return p;
}
Candidate compile_candidate(const Program& p,u64 birth) {
    if(birth>=p.births) fail("BIRTH_OUT_OF_RANGE");
    Candidate c;c.birth=birth;c.program_sha=p.spec_sha;c.seed_sha=p.seed_sha;c.name=p.name;c.symbol=p.symbol;c.purpose=p.purpose;
    u64 remainder=birth;
    for(std::size_t i=p.axes.size();i>0;--i){const auto j=i-1;const auto n=p.axes[j].size();c.parameters[p.axis_names[j]]=std::to_string(p.axes[j][remainder%n]);remainder/=n;}
    const auto val=[&](const std::string& key){return resolve(p.fields.at(key),c.parameters);};
    const auto numeric=[&](const std::string& key){return integer(val(key));};
    const auto side=val("side");if(side=="BUY"||side=="1")c.side=Side::Buy;else if(side=="SELL"||side=="-1")c.side=Side::Sell;else fail("SIDE_INVALID");
    c.stop_u=numeric("stop_u");c.target_u=numeric("target_u");c.be_trigger_ppm=numeric("be_trigger_ppm");c.be_offset_u=numeric("be_offset_u");
    c.trailing_u=numeric("trailing_u");c.daily_limit=numeric("daily_limit");c.commission_u=numeric("commission_u");c.slippage_u=numeric("slippage_u");
    c.bar_ms=numeric("bar_ms");c.expiry_records=numeric("expiry_records");c.signal_mode=val("signal_mode");
    if(c.stop_u<=0||c.target_u<=0||c.be_trigger_ppm<0||c.be_trigger_ppm>1000000||c.be_offset_u<0||c.trailing_u<0||c.commission_u<0||c.slippage_u<0||
       c.bar_ms<=0||c.bar_ms>86400000||c.expiry_records<1||(c.daily_limit!=3&&c.daily_limit!=5)) fail("EXECUTION_PARAMETER_RANGE");
    if(c.be_trigger_ppm==0)c.be_offset_u=0;
    for(const auto& [key,value]:p.fields) if(key.starts_with("require.")) {
        const auto x=split(value,':');const i64 a=integer(resolve(x[1],c.parameters)),b=integer(resolve(x[2],c.parameters));
        const bool ok=x[0]=="LT"?a<b:x[0]=="LE"?a<=b:x[0]=="NE"?a!=b:a==b;
        if(!ok){c.eligible=false;c.exclusion="CAUSAL_CONSTRAINT_"+key.substr(8);}
    }
    std::map<std::string,int> color;std::map<std::string,std::size_t> indices;
    std::function<std::size_t(const std::string&)> visit=[&](const std::string& name)->std::size_t {
        if(color[name]==1) fail("FEATURE_CYCLE");
        if(color[name]==2) return indices.at(name);
        const auto it=p.fields.find("node."+name);if(it==p.fields.end()) fail("UNKNOWN_FEATURE:"+name);
        color[name]=1;const auto tokens=split(it->second,':');Node n;n.name=name;n.op=tokens[0];
        const auto push=[&](std::size_t at){n.inputs.push_back(visit(tokens.at(at)));};
        if(n.op=="BID"||n.op=="ASK"||n.op=="SPREAD") {if(tokens.size()!=1)fail("SOURCE_ARITY");}
        else if(n.op=="CONST"||bars.contains(n.op)) {
            if(tokens.size()!=2)fail("CONSTANT_BAR_ARITY");
            n.parameter=integer(resolve(tokens[1],c.parameters));
            if(bars.contains(n.op)&&(n.parameter<1||n.parameter>86400000))fail("BAR_PERIOD_RANGE");
        } else if(windowed.contains(n.op)) {
            if(tokens.size()!=3)fail("WINDOW_ARITY");
            push(1);n.parameter=integer(resolve(tokens[2],c.parameters));
            if(n.parameter<1||n.parameter>100000)fail("FEATURE_WINDOW_RANGE");
            n.type=c.nodes[n.inputs[0]].type;
            if(n.op!="LAG"&&n.type!=ValueType::Number)fail("NUMERIC_WINDOW_REQUIRED");
        } else if(binary.contains(n.op)) {
            if(tokens.size()!=3)fail("BINARY_ARITY");
            push(1);push(2);
            const auto a=c.nodes[n.inputs[0]].type,b=c.nodes[n.inputs[1]].type;
            if(n.op=="AND"||n.op=="OR") {if(a!=ValueType::Boolean||b!=ValueType::Boolean)fail("BOOLEAN_OPERANDS_REQUIRED");n.type=ValueType::Boolean;}
            else {if(a!=ValueType::Number||b!=ValueType::Number)fail("NUMERIC_OPERANDS_REQUIRED");
                if(n.op=="GT"||n.op=="GE"||n.op=="LT"||n.op=="LE"||n.op=="EQ"||n.op=="CROSS_UP"||n.op=="CROSS_DOWN")n.type=ValueType::Boolean;}
        } else if(n.op=="NOT") {
            if(tokens.size()!=2)fail("NOT_ARITY");
            push(1);if(c.nodes[n.inputs[0]].type!=ValueType::Boolean)fail("NOT_BOOLEAN_REQUIRED");n.type=ValueType::Boolean;
        } else fail("UNKNOWN_OPCODE:"+n.op);
        const auto index=c.nodes.size();if(index>=1024)fail("FEATURE_NODE_LIMIT");
        c.nodes.push_back(std::move(n));indices[name]=index;color[name]=2;return index;
    };
    c.signal_node=visit(val("signal"));
    if(c.nodes[c.signal_node].type!=ValueType::Boolean)fail("SIGNAL_MUST_BE_BOOLEAN");
    // Reject unused definitions, which otherwise disguise misspellings or alter reported ontology.
    for(const auto& [key,value]:p.fields) { (void)value;if(key.starts_with("node.")&&!indices.contains(key.substr(5)))fail("UNUSED_FEATURE:"+key.substr(5)); }
    std::string graph="QROS_FEATURE_GRAPH_V1\n";
    for(const auto& n:c.nodes){graph+=n.op+":"+std::to_string(n.parameter);for(auto input:n.inputs)graph+=":"+std::to_string(input);graph+='\n';}
    c.graph_id=sha256_text(graph);
    Fields identity={{"program_sha256",p.spec_sha},{"seed_sha256",p.seed_sha},{"graph_sha256",c.graph_id},{"signal",std::to_string(c.signal_node)},
        {"side",c.side==Side::Buy?"BUY":"SELL"},{"symbol",c.symbol},{"stop_u",std::to_string(c.stop_u)},{"target_u",std::to_string(c.target_u)},
        {"be_trigger_ppm",std::to_string(c.be_trigger_ppm)},{"be_offset_u",std::to_string(c.be_offset_u)},{"trailing_u",std::to_string(c.trailing_u)},
        {"daily_limit",std::to_string(c.daily_limit)},{"commission_u",std::to_string(c.commission_u)},{"slippage_u",std::to_string(c.slippage_u)},
        {"bar_ms",std::to_string(c.bar_ms)},{"expiry_records",std::to_string(c.expiry_records)},{"signal_mode",c.signal_mode},
        {"event_policy","NEXT_RECORD_V1"},{"management_policy","POST_EXECUTION_NEXT_QUOTE_V1"},{"quantity_contracts","1"}};
    c.canonical=fields_text("QROS_CANDIDATE_IR_V1",identity);c.id=sha256_text(c.canonical);
    return c;
}
std::string program_receipt(const Program& p) {
    return fields_text("QROS_COMPILE_RECEIPT_V1",{{"program_sha256",p.spec_sha},{"seed_sha256",p.seed_sha},{"name",p.name},
        {"symbol",p.symbol},{"purpose",p.purpose},{"raw_births",std::to_string(p.births)},{"axis_count",std::to_string(p.axes.size())},
        {"enumeration","AXIS_NAME_LEXICOGRAPHIC_LAST_AXIS_FASTEST_DECLARED_VALUE_ORDER"},{"scientific_ontology_frozen","0"},{"status","PROGRAM_PARSED"}});
}
} // namespace qros::pipeline
