#property strict
#property version   "2.00"
#property description "QROS XAU M1 PDH Accepted Retest v101 production-safe shadow. NO REAL ORDERS."
#property description "Exact 200s causal rule; zero/crossed spread entry fail-closed; 0.50% balance risk diagnostic."
#include <QROS_RISK_KERNEL_APPROVED_v15420.mqh>
#include <QROS_DEMO_BUS_v2.mqh>

input string OutputPrefix       = "QROS_XAU_M1_SHADOW";
input bool   UseCommonFolder    = true;
input double RiskPctBalance     = 0.50;
input double ExtraCostR        = 0.02;
input int    ResearchClockOffsetSec = 0; // frozen parity candidate; must be proven vs golden.
input bool   ExcludeYear2025    = false; // final holdout-opened canonical setting.

#define BAR_SEC 200
#define ATR_N 36
#define RETEST_MAX_BARS 6
#define HOLD_BARS 72

struct Bar200
{
   long start_sec;
   double bid_o,bid_h,bid_l,bid_c;
   double ask_o,ask_h,ask_l,ask_c;
   bool initialized;
};

int g_trades=INVALID_HANDLE,g_events=INVALID_HANDLE,g_env=INVALID_HANDLE;
Bar200 g_bar;
bool g_have_bar=false;
long g_last_bar_start=-1;
long g_bar_index=-1;
long g_last_closed_bar_index=-1;

// ATR state from CLOSED bid bars only.
double g_tr[ATR_N];
int g_tr_count=0;
int g_tr_pos=0;
double g_prev_bid_close=0.0;
bool g_have_prev_close=false;
double g_atr36=EMPTY_VALUE;

// observed UTC-date state (not broker-server date).
int g_current_date_key=-1;
double g_current_day_high=-DBL_MAX;
int g_current_day_bars=0;
double g_prev_observed_day_high=EMPTY_VALUE;
int g_prev_observed_day_bars=0;

// one-attempt/day signal state
bool g_day_eligible=false;
bool g_breakout_found=false;
long g_breakout_idx=-1;
int g_bars_after_breakout=0;
bool g_day_consumed=false;
double g_prev_high_for_day=EMPTY_VALUE;

// scheduled next-bar entry
bool g_pending_entry=false;
long g_signal_idx=-1;
long g_signal_start=-1;
double g_signal_atr=0.0;
double g_signal_extension=0.0;
double g_signal_close_pos=0.0;
double g_signal_range_atr=0.0;
int g_signal_latency_bars=0;

// shadow trade
bool g_active=false;
long g_entry_idx=-1,g_entry_epoch=-1;
double g_entry_ask=0.0,g_stop_dist=0.0,g_sl=0.0,g_tp=0.0;
int g_hold_count=0;
double g_entry_spread=0.0,g_entry_spread_atr=0.0;
bool g_risk_ok=false;
string g_risk_reason="";
double g_target_risk=0.0,g_raw_volume=0.0,g_volume=0.0,g_actual_risk=0.0;

long g_ticks=0,g_invalid_crossed=0,g_zero_spread=0,g_executable=0;
long g_events_eligible=0,g_reject_zero=0,g_reject_spread=0,g_reject_gap=0,g_shadow_trades=0;

int FileFlags()
{
   int f=FILE_WRITE|FILE_CSV|FILE_ANSI;
   if(UseCommonFolder) f|=FILE_COMMON;
   return f;
}
int DateKeyUTC(const long epoch_sec)
{
   datetime t=(datetime)(epoch_sec+ResearchClockOffsetSec);
   MqlDateTime s; TimeToStruct(t,s);
   return s.year*10000+s.mon*100+s.day;
}
int YearUTC(const long epoch_sec)
{
   datetime t=(datetime)(epoch_sec+ResearchClockOffsetSec);
   MqlDateTime s; TimeToStruct(t,s); return s.year;
}
string Stamp(const long epoch_sec)
{
   return TimeToString((datetime)(epoch_sec+ResearchClockOffsetSec),TIME_DATE|TIME_SECONDS);
}
long BarStart(const long epoch_sec)
{
   long t=epoch_sec+ResearchClockOffsetSec;
   long b=(t/BAR_SEC)*BAR_SEC;
   return b-ResearchClockOffsetSec;
}
double MeanTR()
{
   if(g_tr_count<ATR_N) return EMPTY_VALUE;
   double s=0.0; for(int i=0;i<ATR_N;i++) s+=g_tr[i];
   return s/ATR_N;
}
void PushTR(const double v)
{
   g_tr[g_tr_pos]=v;
   g_tr_pos=(g_tr_pos+1)%ATR_N;
   if(g_tr_count<ATR_N)g_tr_count++;
   g_atr36=MeanTR();
}
void ResetBar(Bar200 &b,const long start,const double bid,const double ask)
{
   b.start_sec=start;b.bid_o=bid;b.bid_h=bid;b.bid_l=bid;b.bid_c=bid;
   b.ask_o=ask;b.ask_h=ask;b.ask_l=ask;b.ask_c=ask;b.initialized=true;
}
void UpdateBar(Bar200 &b,const double bid,const double ask)
{
   if(bid>b.bid_h)b.bid_h=bid;if(bid<b.bid_l)b.bid_l=bid;b.bid_c=bid;
   if(ask>b.ask_h)b.ask_h=ask;if(ask<b.ask_l)b.ask_l=ask;b.ask_c=ask;
}
void ResetObservedDay(const int dk,const double first_high)
{
   if(g_current_date_key!=-1)
   {
      g_prev_observed_day_high=g_current_day_high;
      g_prev_observed_day_bars=g_current_day_bars;
   }
   g_current_date_key=dk;
   g_current_day_high=first_high;
   g_current_day_bars=0;

   g_prev_high_for_day=g_prev_observed_day_high;
   g_day_eligible=(g_prev_observed_day_bars>=300 && g_prev_high_for_day!=EMPTY_VALUE);
   g_breakout_found=false;
   g_breakout_idx=-1;
   g_bars_after_breakout=0;
   g_day_consumed=false;
   g_pending_entry=false;
}
void LogEvent(const string event,const string reason,const long bar_start,
              const double v1=0.0,const double v2=0.0,const double v3=0.0,const double v4=0.0)
{
   FileWrite(g_events,event,reason,g_bar_index,bar_start,Stamp(bar_start),v1,v2,v3,v4);
}
void CloseShadow(const long exit_idx,const long exit_epoch,const double exit_price,const string reason)
{
   double gross=(exit_price-g_entry_ask)/g_stop_dist;
   double net=gross-ExtraCostR;
   FileWrite(g_trades,
      g_entry_idx,g_entry_epoch,Stamp(g_entry_epoch),g_entry_ask,
      g_stop_dist,g_sl,g_tp,
      exit_idx,exit_epoch,Stamp(exit_epoch),exit_price,gross,net,reason,
      g_entry_spread,g_entry_spread_atr,
      g_signal_idx,g_signal_start,Stamp(g_signal_start),g_prev_high_for_day,
      g_signal_atr,g_signal_extension,g_signal_close_pos,g_signal_range_atr,g_signal_latency_bars,
      g_risk_ok?1:0,g_risk_reason,g_target_risk,g_raw_volume,g_volume,g_actual_risk);
   if(!MQLInfoInteger(MQL_TESTER))
      QrosBusPublish(QROS_MOD_XAU,QROS_ACT_CLOSE,0,exit_epoch*1000L,exit_price,g_sl,g_tp,0.0,0.0);
   g_active=false;g_shadow_trades++;
}
void ProcessActiveClosedBar(const Bar200 &b,const long idx,const bool segment_ends)
{
   if(!g_active)return;

   bool hit_sl=(b.bid_l<=g_sl+1e-12);
   bool hit_tp=(b.bid_h>=g_tp-1e-12);

   if(hit_sl)
   {
      CloseShadow(idx,b.start_sec,g_sl,"SL");
      return;
   }
   if(hit_tp)
   {
      CloseShadow(idx,b.start_sec,g_tp,"TP");
      return;
   }

   g_hold_count++;
   if(segment_ends)
   {
      CloseShadow(idx,b.start_sec,b.bid_c,"GAP_TIME");
      return;
   }
   if(g_hold_count>=HOLD_BARS)
   {
      CloseShadow(idx,b.start_sec,b.bid_c,"TIME");
      return;
   }
}
bool SignalFiltersPass(const Bar200 &b)
{
   if(g_atr36==EMPTY_VALUE || !(g_atr36>0.0)) return false;
   double rng=b.bid_h-b.bid_l; if(!(rng>0.0)) return false;
   g_signal_atr=g_atr36;
   g_signal_extension=(b.bid_c-g_prev_high_for_day)/g_atr36;
   g_signal_close_pos=(b.bid_c-b.bid_l)/rng;
   g_signal_range_atr=rng/g_atr36;

   if(g_signal_extension<0.25-1e-12 || g_signal_extension>1.50+1e-12)return false;
   if(g_signal_close_pos<0.50-1e-12)return false;
   if(g_signal_range_atr<1.50-1e-12)return false;
   if(b.bid_c<b.bid_o-1e-12)return false;
   return true;
}
void EvaluateSignalOnClosedBar(const Bar200 &b,const long idx)
{
   int dk=DateKeyUTC(b.start_sec);
   if(dk!=g_current_date_key) ResetObservedDay(dk,b.bid_h);

   if(b.bid_h>g_current_day_high)g_current_day_high=b.bid_h;
   g_current_day_bars++;

   if(!g_day_eligible || g_day_consumed)return;

   if(!g_breakout_found)
   {
      if(b.bid_c>g_prev_high_for_day)
      {
         g_breakout_found=true;
         g_breakout_idx=idx;
         g_bars_after_breakout=0;
         LogEvent("BREAKOUT","FIRST_CLOSE_ABOVE_PDH",b.start_sec,g_prev_high_for_day,b.bid_c,0,0);
      }
      return;
   }

   g_bars_after_breakout++;
   if(g_bars_after_breakout>RETEST_MAX_BARS)
   {
      g_day_consumed=true;
      LogEvent("DAY_CONSUMED","NO_RETEST_WITHIN_6",b.start_sec,g_prev_high_for_day,0,0,0);
      return;
   }

   if(b.bid_l<=g_prev_high_for_day+1e-12 && b.bid_c>g_prev_high_for_day)
   {
      // First reclaim consumes the opportunity whether filters pass or not.
      g_day_consumed=true;
      g_signal_idx=idx;
      g_signal_start=b.start_sec;
      g_signal_latency_bars=(int)(idx-g_breakout_idx);

      if(!SignalFiltersPass(b))
      {
         LogEvent("SIGNAL_REJECTED","STRUCTURAL_FILTER",b.start_sec,
                  g_signal_extension,g_signal_close_pos,g_signal_range_atr,g_signal_atr);
         return;
      }

      g_pending_entry=true;
      g_events_eligible++;
      LogEvent("SIGNAL_ACCEPTED","WAIT_NEXT_200S_OPEN",b.start_sec,
               g_signal_extension,g_signal_close_pos,g_signal_range_atr,g_signal_atr);
   }
}
void AttemptEntryAtNewBar(const Bar200 &newbar,const long new_idx,const long previous_start)
{
   if(!g_pending_entry)return;
   g_pending_entry=false;

   if(newbar.start_sec-g_signal_start>400)
   {
      g_reject_gap++;
      LogEvent("ENTRY_REJECTED","ENTRY_GAP_GT_400",newbar.start_sec,
               (double)(newbar.start_sec-g_signal_start),0,0,0);
      return;
   }

   double spread=newbar.ask_o-newbar.bid_o;
   if(!(newbar.ask_o>newbar.bid_o))
   {
      g_reject_zero++;
      LogEvent("ENTRY_REJECTED","ZERO_OR_CROSSED_SPREAD",newbar.start_sec,
               newbar.bid_o,newbar.ask_o,spread,0);
      return;
   }

   double spread_atr=spread/g_signal_atr;
   if(spread_atr>0.50+1e-12)
   {
      g_reject_spread++;
      LogEvent("ENTRY_REJECTED","SPREAD_ATR_GT_0P50",newbar.start_sec,
               spread,spread_atr,g_signal_atr,0);
      return;
   }

   if(g_active)
   {
      LogEvent("ENTRY_REJECTED","INTERNAL_M1_POSITION_OPEN",newbar.start_sec,0,0,0,0);
      return;
   }

   g_entry_idx=new_idx;
   g_entry_epoch=newbar.start_sec;
   g_entry_ask=newbar.ask_o;
   g_stop_dist=6.0*g_signal_atr;
   g_sl=g_entry_ask-g_stop_dist;
   g_tp=g_entry_ask+3.0*g_stop_dist;
   g_entry_spread=spread;
   g_entry_spread_atr=spread_atr;
   g_hold_count=0;

   QrosRiskResult rr;
   double bal=AccountInfoDouble(ACCOUNT_BALANCE);
   g_risk_ok=QrosRiskSize(_Symbol,ORDER_TYPE_BUY,g_entry_ask,g_sl,bal,RiskPctBalance,rr);
   g_risk_reason=rr.reason;g_target_risk=rr.target_usd;g_raw_volume=rr.raw_volume;
   g_volume=rr.volume;g_actual_risk=rr.actual_risk_usd;

   if(!MQLInfoInteger(MQL_TESTER))
      QrosBusPublish(QROS_MOD_XAU,QROS_ACT_ENTRY,0,newbar.start_sec*1000L,g_entry_ask,g_sl,g_tp,g_volume,g_actual_risk);

   g_active=true;
   LogEvent("SHADOW_ENTRY","NO_ORDER_SENT",newbar.start_sec,
            g_entry_ask,g_sl,g_tp,g_volume);
}
void FinalizeClosedBar(const Bar200 &b,const long idx,const bool segment_ends)
{
   // Management uses the complete 200s Bid bar; SL first if both touched.
   ProcessActiveClosedBar(b,idx,segment_ends);

   // TR/ATR for this closed bar.
   double tr=b.bid_h-b.bid_l;
   if(g_have_prev_close)
   {
      tr=MathMax(tr,MathAbs(b.bid_h-g_prev_bid_close));
      tr=MathMax(tr,MathAbs(b.bid_l-g_prev_bid_close));
   }
   g_prev_bid_close=b.bid_c;g_have_prev_close=true;
   PushTR(tr);

   EvaluateSignalOnClosedBar(b,idx);
   g_last_closed_bar_index=idx;
}
int OnInit()
{
   if(!MQLInfoInteger(MQL_TESTER))
     {
      if(_Symbol!="XAUUSD"){Print("QROS XAU emitter requires XAUUSD");return INIT_PARAMETERS_INCORRECT;}
      QrosBusSetState(QROS_MOD_XAU,QROS_STATE_INIT);
      QrosBusHeartbeat(QROS_MOD_XAU);
     }
   ArrayInitialize(g_tr,0.0);
   string tf=OutputPrefix+"_TRADES_v15700.csv";
   string ef=OutputPrefix+"_EVENTS_v15700.csv";
   string vf=OutputPrefix+"_ENV_v15700.csv";
   g_trades=FileOpen(tf,FileFlags(),',');
   g_events=FileOpen(ef,FileFlags(),',');
   g_env=FileOpen(vf,FileFlags(),',');
   if(g_trades==INVALID_HANDLE||g_events==INVALID_HANDLE||g_env==INVALID_HANDLE)
   {
      Print("QROS XAU M1 shadow FileOpen failed ",GetLastError());
      if(!MQLInfoInteger(MQL_TESTER)) QrosBusSetState(QROS_MOD_XAU,QROS_STATE_FAULT);
      return INIT_FAILED;
   }
   FileWrite(g_trades,
      "entry_idx","entry_epoch","entry_stamp","entry_price","stop_points","stop_price","target_price",
      "exit_idx","exit_epoch","exit_stamp","exit_price","gross_r","pnl_r","exit_reason",
      "spread_open","spread_open_atr","signal_idx","signal_epoch","signal_stamp","level","atr",
      "extension_atr","close_position","range_atr","latency_bars",
      "risk_size_ok","risk_size_reason","target_risk_usd","raw_volume","rounded_volume","actual_risk_usd");
   FileWrite(g_events,"event","reason","bar_idx","bar_epoch","bar_stamp","v1","v2","v3","v4");
   FileWrite(g_env,"key","value");
   FileWrite(g_env,"schema","QROS_XAU_M1_SHADOW_v15700");
   FileWrite(g_env,"symbol",_Symbol);
   FileWrite(g_env,"account_server",AccountInfoString(ACCOUNT_SERVER));
   FileWrite(g_env,"terminal_build",(long)TerminalInfoInteger(TERMINAL_BUILD));
   FileWrite(g_env,"mql_tester",(long)MQLInfoInteger(MQL_TESTER));
   FileWrite(g_env,"clock_offset_sec",ResearchClockOffsetSec);
   FileWrite(g_env,"exclude_year_2025",ExcludeYear2025?1:0);
   FileWrite(g_env,"risk_pct_balance",DoubleToString(RiskPctBalance,4));
   FileWrite(g_env,"orders_sent",0);
   if(!MQLInfoInteger(MQL_TESTER))
     {
      QrosBusSetState(QROS_MOD_XAU,QROS_STATE_READY);
      QrosBusHeartbeat(QROS_MOD_XAU);
      EventSetTimer(1);
     }
   return INIT_SUCCEEDED;
}
void OnTimer()
{
   if(!MQLInfoInteger(MQL_TESTER)) QrosBusHeartbeat(QROS_MOD_XAU);
}
void OnTick()
{
   if(!MQLInfoInteger(MQL_TESTER)) QrosBusHeartbeat(QROS_MOD_XAU);
   MqlTick t;if(!SymbolInfoTick(_Symbol,t))return;
   g_ticks++;
   if(!(t.bid>0.0) || !(t.ask>0.0))return;
   if(t.ask<t.bid){g_invalid_crossed++;return;}
   if(t.ask==t.bid)g_zero_spread++;
   else g_executable++;

   long sec=(long)(t.time_msc/1000);
   long bs=BarStart(sec);

   if(!g_have_bar)
   {
      ResetBar(g_bar,bs,t.bid,t.ask);
      g_have_bar=true;
      g_last_bar_start=bs;
      g_bar_index=0;
      return;
   }

   if(bs==g_last_bar_start)
   {
      UpdateBar(g_bar,t.bid,t.ask);
      return;
   }

   if(bs<g_last_bar_start)
   {
      // Temporal disorder is never used.
      return;
   }

   bool gap=(bs-g_last_bar_start>400);
   FinalizeClosedBar(g_bar,g_bar_index,gap);

   ResetBar(g_bar,bs,t.bid,t.ask);
   g_last_bar_start=bs;
   g_bar_index++;

   // Final canonical rule includes 2025; input remains explicit for audit compatibility.
   if(ExcludeYear2025 && YearUTC(bs)==2025)
   {
      g_pending_entry=false;
      return;
   }

   AttemptEntryAtNewBar(g_bar,g_bar_index,g_bar.start_sec-BAR_SEC);
}
void OnDeinit(const int reason)
{
   if(!MQLInfoInteger(MQL_TESTER))
     {
      EventKillTimer();
      QrosBusSetState(QROS_MOD_XAU,QROS_STATE_OFF);
     }
   if(g_have_bar)
   {
      FinalizeClosedBar(g_bar,g_bar_index,true);
   }
   if(g_env!=INVALID_HANDLE)
   {
      FileWrite(g_env,"ticks_total",g_ticks);
      FileWrite(g_env,"ticks_executable_positive_spread",g_executable);
      FileWrite(g_env,"ticks_zero_spread",g_zero_spread);
      FileWrite(g_env,"ticks_crossed",g_invalid_crossed);
      FileWrite(g_env,"eligible_signals",g_events_eligible);
      FileWrite(g_env,"reject_zero_or_crossed_entry",g_reject_zero);
      FileWrite(g_env,"reject_spread",g_reject_spread);
      FileWrite(g_env,"reject_entry_gap",g_reject_gap);
      FileWrite(g_env,"shadow_trades",g_shadow_trades);
      FileWrite(g_env,"status","FINISHED");
      FileWrite(g_env,"deinit_reason",reason);
      FileClose(g_env);
   }
   if(g_events!=INVALID_HANDLE)FileClose(g_events);
   if(g_trades!=INVALID_HANDLE)FileClose(g_trades);
}
