#include "qros/pipeline.hpp"
#include "qros/sha256.hpp"
#include <algorithm>
#include <chrono>
#include <sstream>
#include <tuple>

namespace qros::pipeline {
BacktestState::BacktestState(Candidate c,u64 max_trades):candidate_(std::move(c)),max_trades_(max_trades) {
    if(max_trades==0||max_trades>10000000) fail("TRADE_BUDGET_RANGE");
}
void BacktestState::close(const Tick& tick,ExitReason reason) {
    auto& s=state_;auto& t=s.trade;const auto& c=candidate_;
    if(!s.open||tick.seq<=t.entry_seq||tick.ask_u<=tick.bid_u) fail("INVALID_CLOSE_EVENT");
    t.exit_seq=tick.seq;t.exit_ts_ns=tick.ts_ns;
    t.exit_price_u=c.side==Side::Buy?sub(tick.bid_u,c.slippage_u):add(tick.ask_u,c.slippage_u);
    if(t.exit_price_u<=0) fail("NONPOSITIVE_EXIT_FILL");
    t.reason=reason;t.pnl_u=c.side==Side::Buy?sub(t.exit_price_u,t.entry_price_u):sub(t.entry_price_u,t.exit_price_u);
    t.r_num=t.pnl_u;t.r_den=c.stop_u;
    if(trades_.size()>=max_trades_) fail("TRADE_BUDGET_EXCEEDED");
    trades_.push_back({c.id,c.symbol,c.birth,t,sub(t.pnl_u,c.commission_u),c.commission_u,s.mae,s.mfe,c.bar_ms});
    s.open=false;s.has_last_exec=false;
}
void BacktestState::update(const Tick& tick,const SessionBoundary& session,const Value& signal) {
    auto& s=state_;const auto& c=candidate_;
    if(tick.session_day!=s.active_day) {
        if(s.open) fail("OVERNIGHT_POSITION_FORBIDDEN");
        s.pending=false;s.entries_today=0;s.active_day=tick.session_day;s.last_entry_bar=-1;
    }
    const auto bar=tick.ts_ns/mul(c.bar_ms,1000000);
    // Existing protective orders are evaluated before management changes at this quote.
    // Changes to BE/trailing become effective on a subsequent record, never retroactively.
    if(s.open&&tick.seq>s.trade.entry_seq&&tick.ask_u>tick.bid_u) {
        s.last_exec=tick;s.has_last_exec=true;
        const i64 price=c.side==Side::Buy?tick.bid_u:tick.ask_u;
        const i64 favorable=c.side==Side::Buy?sub(price,s.trade.entry_price_u):sub(s.trade.entry_price_u,price);
        s.mae=std::min(s.mae,favorable);s.mfe=std::max(s.mfe,favorable);
        const bool stop=c.side==Side::Buy?price<=s.stop:price>=s.stop;
        const bool target=c.side==Side::Buy?price>=s.target:price<=s.target;
        if(stop) close(tick,ExitReason::StopLoss);
        else if(target) close(tick,ExitReason::TakeProfit);
        else {
            if(c.side==Side::Buy)s.best=std::max(s.best,price);else s.best=std::min(s.best,price);
            if(c.be_trigger_ppm>0&&favorable>0&&mul(favorable,1000000)>=mul(c.target_u,c.be_trigger_ppm)) {
                const auto level=c.side==Side::Buy?add(s.trade.entry_price_u,c.be_offset_u):sub(s.trade.entry_price_u,c.be_offset_u);
                s.stop=c.side==Side::Buy?std::max(s.stop,level):std::min(s.stop,level);
            }
            if(c.trailing_u>0) {
                const auto level=c.side==Side::Buy?sub(s.best,c.trailing_u):add(s.best,c.trailing_u);
                s.stop=c.side==Side::Buy?std::max(s.stop,level):std::min(s.stop,level);
            }
        }
    }
    if(tick.seq==session.close_seq) {
        if(s.open) {
            if(s.has_last_exec) close(s.last_exec,ExitReason::SessionClose);
            else {++unresolved_;s.open=false;}
        }
        s.pending=false;
        // A session close cannot initiate an order that would require tomorrow's quote.
        s.signal_version=signal.version;s.signal_was_true=signal.valid&&signal.value!=0;
        return;
    }
    if(s.pending&&tick.seq>s.signal_seq) {
        ++s.pending_records;
        if(s.pending_records>c.expiry_records||s.signal_day!=tick.session_day) s.pending=false;
        else if(!s.open&&tick.ask_u>tick.bid_u&&s.entries_today<c.daily_limit&&bar!=s.last_entry_bar) {
            s.trade=Trade{};s.trade.entered=true;s.trade.side=c.side;s.trade.entry_seq=tick.seq;s.trade.entry_ts_ns=tick.ts_ns;
            s.trade.entry_day=tick.session_day;s.trade.entry_price_u=c.side==Side::Buy?add(tick.ask_u,c.slippage_u):sub(tick.bid_u,c.slippage_u);
            if(s.trade.entry_price_u<=0) fail("NONPOSITIVE_FILL");
            s.stop=c.side==Side::Buy?sub(s.trade.entry_price_u,c.stop_u):add(s.trade.entry_price_u,c.stop_u);
            s.target=c.side==Side::Buy?add(s.trade.entry_price_u,c.target_u):sub(s.trade.entry_price_u,c.target_u);
            if(s.stop<=0||s.target<=0)fail("NONPOSITIVE_PROTECTIVE_ORDER");
            s.best=s.trade.entry_price_u;s.mae=0;s.mfe=0;s.open=true;s.pending=false;s.has_last_exec=false;
            ++s.entries_today;s.last_entry_bar=bar;s.last_entry_seq=tick.seq;
        }
    }
    if(signal.version!=s.signal_version) {
        const bool truth=signal.valid&&signal.value!=0;
        const bool trigger=truth&&(c.signal_mode=="EACH_UPDATE"||!s.signal_was_true);
        if(trigger&&!s.open&&!s.pending&&s.entries_today<c.daily_limit&&bar!=s.last_entry_bar) {
            s.pending=true;s.signal_seq=tick.seq;s.signal_day=tick.session_day;s.pending_records=0;
        }
        s.signal_was_true=truth;s.signal_version=signal.version;
    }
}
void BacktestState::finish() {
    if(state_.open) fail("MISSING_AUTHORITATIVE_CLOSE");
    if(state_.pending) fail("MISSING_SESSION_END");
}
std::string ledger_header() {
    return "candidate_id,birth,symbol,side,entry_seq,entry_ts_ns,entry_day,entry_price_u,exit_seq,exit_ts_ns,exit_price_u,exit_reason,gross_u,net_u,commission_u,risk_u,mae_u,mfe_u,bar_ms\n";
}
std::string ledger_row(const TradeRecord& r) {
    const auto& t=r.trade;
    return r.candidate_id+","+std::to_string(r.birth)+","+r.symbol+","+(t.side==Side::Buy?"BUY":"SELL")+","+
        std::to_string(t.entry_seq)+","+std::to_string(t.entry_ts_ns)+","+std::to_string(t.entry_day)+","+std::to_string(t.entry_price_u)+","+
        std::to_string(t.exit_seq)+","+std::to_string(t.exit_ts_ns)+","+std::to_string(t.exit_price_u)+","+std::string(exit_reason_name(t.reason))+","+
        std::to_string(t.pnl_u)+","+std::to_string(r.net_u)+","+std::to_string(r.commission_u)+","+std::to_string(t.r_den)+","+
        std::to_string(r.mae_u)+","+std::to_string(r.mfe_u)+","+std::to_string(r.bar_ms)+"\n";
}
std::vector<TradeRecord> read_ledger(const std::filesystem::path& path,const std::string& hash) {
    const auto text=bounded_text(path,128U*1024U*1024U);
    if(!hash_valid(hash)||sha256_text(text)!=hash) fail("LEDGER_HASH_MISMATCH");
    return parse_ledger(text);
}
std::vector<TradeRecord> parse_ledger(const std::string& text) {
    if(text.size()>128U*1024U*1024U||text.empty()||text.back()!='\n')fail("LEDGER_SIZE_OR_UNTERMINATED_LINE");
    std::istringstream in(text);std::string line;
    if(!std::getline(in,line)||line+'\n'!=ledger_header()) fail("LEDGER_HEADER");
    std::vector<TradeRecord> out;
    std::map<std::string,u64> previous_exit;
    std::set<std::pair<std::string,u64>> entries;
    std::map<std::string,std::string> identities;
    std::set<std::tuple<std::string,i64,i64>> bars;
    while(std::getline(in,line)) {
        const auto c=split(line,',');if(c.size()!=19) fail("LEDGER_COLUMNS");
        TradeRecord r;r.candidate_id=c[0];r.birth=natural(c[1]);r.symbol=c[2];
        if(!hash_valid(r.candidate_id)||(r.symbol!="NQX"&&r.symbol!="XAUUSD")||(c[3]!="BUY"&&c[3]!="SELL")) fail("LEDGER_IDENTITIES");
        auto& t=r.trade;t.entered=true;t.side=c[3]=="BUY"?Side::Buy:Side::Sell;
        t.entry_seq=natural(c[4]);t.entry_ts_ns=integer(c[5]);t.entry_day=integer(c[6]);t.entry_price_u=integer(c[7]);
        t.exit_seq=natural(c[8]);t.exit_ts_ns=integer(c[9]);t.exit_price_u=integer(c[10]);
        if(c[11]=="TP")t.reason=ExitReason::TakeProfit;else if(c[11]=="SL")t.reason=ExitReason::StopLoss;else if(c[11]=="SESSION_CLOSE")t.reason=ExitReason::SessionClose;else fail("UNRESOLVED_LEDGER_TRADE");
        t.pnl_u=integer(c[12]);r.net_u=integer(c[13]);r.commission_u=integer(c[14]);t.r_den=integer(c[15]);t.r_num=t.pnl_u;
        r.mae_u=integer(c[16]);r.mfe_u=integer(c[17]);r.bar_ms=integer(c[18]);
        if(t.entry_seq==0||t.exit_seq<=t.entry_seq||t.entry_ts_ns<=0||t.exit_ts_ns<t.entry_ts_ns||t.entry_price_u<=0||t.exit_price_u<=0||t.r_den<=0||r.bar_ms<=0||r.bar_ms>86400000||r.commission_u<0||t.entry_day<19700101||t.entry_day>22001231) fail("LEDGER_TRADE_RANGE");
        const std::chrono::year_month_day day{std::chrono::year(static_cast<int>(t.entry_day/10000)),
            std::chrono::month(static_cast<unsigned>((t.entry_day/100)%100)),std::chrono::day(static_cast<unsigned>(t.entry_day%100))};
        if(!day.ok())fail("LEDGER_CALENDAR_DATE");
        const auto movement=t.side==Side::Buy?sub(t.exit_price_u,t.entry_price_u):sub(t.entry_price_u,t.exit_price_u);
        if(t.pnl_u!=movement||r.net_u!=sub(t.pnl_u,r.commission_u)||r.mae_u>0||r.mfe_u<0) fail("LEDGER_ACCOUNTING_MISMATCH");
        const auto key=r.candidate_id+"_"+r.symbol;
        const auto identity=c[1]+","+c[2]+","+c[3]+","+c[14]+","+c[15]+","+c[18];
        if(identities.contains(r.candidate_id)&&identities.at(r.candidate_id)!=identity)fail("LEDGER_CANDIDATE_METADATA_DRIFT");
        identities[r.candidate_id]=identity;
        if(!bars.emplace(key,t.entry_day,t.entry_ts_ns/mul(r.bar_ms,1000000)).second)fail("LEDGER_REPEATED_ENTRY_BAR");
        if(previous_exit.contains(key)&&t.entry_seq<=previous_exit[key]) fail("LEDGER_POSITION_OVERLAP_OR_ORDER");
        if(!entries.emplace(key,t.entry_seq).second)fail("DUPLICATE_LEDGER_TRADE");
        previous_exit[key]=t.exit_seq;out.push_back(r);
    }
    return out;
}
} // namespace qros::pipeline
