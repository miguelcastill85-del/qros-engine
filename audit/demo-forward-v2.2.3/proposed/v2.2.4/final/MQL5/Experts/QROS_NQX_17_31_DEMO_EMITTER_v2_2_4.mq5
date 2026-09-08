#property strict
#property version "2.24"
#property description "QROS NQX Multiscale 17/31 production-shadow candidate. NO REAL ORDERS."
#property description "PnL-blind medoids 17/31; exact v6 causal mechanics + approved risk diagnostics."

input int    ResearchYear      = 2026;
input int    WarmupYear        = 2025;
input string OutputPrefix      = "QROS_NQX_SHADOW_17_31";
input double RiskPctBalance    = 0.50;
input bool   UseCommonFolder   = true;
input int    EndMonth          = 7;
input int    EndDay            = 27;
input int    EndHour           = 9;
input int    EndMinute         = 11;
input int    EndSecond         = 12;
input int    EndMillisecond    = 709;
input bool   ForwardProspectiveMode = true;

#define PROFILE_COUNT 2
#define OPT_POS16  1
#define OPT_RET8   2
#define OPT_DISTLO 3
#include <QROS_RISK_KERNEL_APPROVED_v15420.mqh>
#include <QROS_DEMO_BUS_v2_2_4.mqh>
const long QROS_V224_EMITTER_SOURCE_TOKEN=224102;

struct ConfigDef
{
   int cohort_id;
   double h1_pos32_max;
   double spread_risk_max;
   double entry_offset_min;
   int optional_code;
   double optional_threshold;
};
struct ProfileState
{
   bool active;
   int entries_today;
   long entry_ms;
   datetime entry_bar_time;
   double entry_bid;
   double entry_ask;
   double initial_risk;
   double ref_low;
   double ref_high;
   double tp;
   double stop;
   bool b_finalized;
   double b_low_final;
   double b_close_final;
   bool stop_move_checked;
   double h1_pos32;
   double pos16;
   double ret8_atr;
   double distlo16_atr;
   double spread;
   double spread_risk;
   double entry_offset_sec;
   bool risk_size_ok;
   string risk_size_reason;
   double target_risk_usd;
   double raw_volume;
   double rounded_volume;
   double actual_risk_usd;
};
ConfigDef CFG[PROFILE_COUNT];
ProfileState PS[PROFILE_COUNT];

int g_trades=INVALID_HANDLE, g_candidates=INVALID_HANDLE, g_env=INVALID_HANDLE;
datetime g_last_m15_bar=0, g_last_h1_bar=0;
int g_current_day_key=-1;
double g_last_exec_bid=0.0;
long g_last_exec_ms=0;
bool g_end_closed=false;

bool g_setup_valid=false, g_swept=false, g_consumed=false;
double g_ref_low=0.0,g_ref_high=0.0,g_min_bid=0.0;
datetime g_b_start=0;
long g_sweep_ms=0;
double g_feature_h1_pos32=EMPTY_VALUE,g_feature_pos16=EMPTY_VALUE;
double g_feature_ret8_atr=EMPTY_VALUE,g_feature_distlo16_atr=EMPTY_VALUE;

int g_m15_count=0;
double g_ema9=0.0,g_ema50=0.0;
double g_m15_close[80],g_m15_high[80],g_m15_low[80],g_m15_tr[80];
int g_h1_count=0;
double g_h1_close[40],g_h1_high[40],g_h1_low[40];

long g_ticks_total=0,g_ticks_bidflag=0,g_ticks_askflag=0,g_ticks_exec=0,g_ticks_zero=0,g_ticks_crossed=0;

int YearOf(datetime t){ MqlDateTime s; TimeToStruct(t,s); return s.year; }
int DayKey(datetime t){ MqlDateTime s; TimeToStruct(t,s); return s.year*10000+s.mon*100+s.day; }
double PriceTickSize()
{
   double ts=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(!(ts>0.0)) ts=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   return ts;
}
long PriceGridIndex(double price)
{
   double ts=PriceTickSize();
   if(!(ts>0.0)) return 0;
   return (long)MathRound(price/ts);
}
double PriceGridNormalize(double price)
{
   double ts=PriceTickSize();
   int digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   if(!(ts>0.0)) return NormalizeDouble(price,digits);
   return NormalizeDouble((double)PriceGridIndex(price)*ts,digits);
}
bool PriceLEGrid(double lhs,double rhs){ return PriceGridIndex(lhs)<=PriceGridIndex(rhs); }
bool PriceGEGrid(double lhs,double rhs){ return PriceGridIndex(lhs)>=PriceGridIndex(rhs); }
bool AtOrBeforeResearchEnd(MqlTick &tick)
{
   MqlDateTime s; TimeToStruct(tick.time,s);
   if(s.year<ResearchYear) return true;
   if(s.year>ResearchYear) return false;
   if(s.mon<EndMonth) return true; if(s.mon>EndMonth) return false;
   if(s.day<EndDay) return true; if(s.day>EndDay) return false;
   if(s.hour<EndHour) return true; if(s.hour>EndHour) return false;
   if(s.min<EndMinute) return true; if(s.min>EndMinute) return false;
   if(s.sec<EndSecond) return true; if(s.sec>EndSecond) return false;
   int ms=(int)(tick.time_msc%1000); if(ms<0) ms+=1000;
   return ms<=EndMillisecond;
}
string StampMsc(datetime t,long msc)
{
   MqlDateTime s; TimeToStruct(t,s); int ms=(int)(msc%1000); if(ms<0) ms+=1000;
   return StringFormat("%04d.%02d.%02d %02d:%02d:%02d.%03d",s.year,s.mon,s.day,s.hour,s.min,s.sec,ms);
}
int FileFlags(){ int f=FILE_WRITE|FILE_CSV|FILE_ANSI; if(UseCommonFolder) f|=FILE_COMMON; return f; }
void ShiftInsert(double &a[],int n,double v){ int lim=MathMin(n-1,ArraySize(a)-1); for(int i=lim;i>0;i--) a[i]=a[i-1]; a[0]=v; }
double MaxN(double &a[],int n){ double v=-DBL_MAX; for(int i=0;i<n;i++) if(a[i]>v)v=a[i]; return v; }
double MinN(double &a[],int n){ double v= DBL_MAX; for(int i=0;i<n;i++) if(a[i]<v)v=a[i]; return v; }
double MeanN(double &a[],int n){ double s=0.0; for(int i=0;i<n;i++)s+=a[i]; return s/n; }
void ResetResearchState()
{
   g_m15_count=0;g_h1_count=0;g_ema9=0.0;g_ema50=0.0;
   ArrayInitialize(g_m15_close,0.0);ArrayInitialize(g_m15_high,0.0);ArrayInitialize(g_m15_low,0.0);ArrayInitialize(g_m15_tr,0.0);
   ArrayInitialize(g_h1_close,0.0);ArrayInitialize(g_h1_high,0.0);ArrayInitialize(g_h1_low,0.0);
   g_setup_valid=false;g_swept=false;g_consumed=false;
}
void InitConfigs()
{
   // PnL-blind medoids frozen by signal-topology consolidation v15100.
   CFG[0].cohort_id=17;
   CFG[0].h1_pos32_max=0.5939716312056776;
   CFG[0].spread_risk_max=0.0404624277456664;
   CFG[0].entry_offset_min=116.026;
   CFG[0].optional_code=OPT_DISTLO;
   CFG[0].optional_threshold=1.1448733154265076;

   CFG[1].cohort_id=31;
   CFG[1].h1_pos32_max=0.6502379333786539;
   CFG[1].spread_risk_max=0.0404624277456664;
   CFG[1].entry_offset_min=116.026;
   CFG[1].optional_code=OPT_POS16;
   CFG[1].optional_threshold=0.32188521241830753;

   for(int i=0;i<PROFILE_COUNT;i++)
   {
      PS[i].active=false;
      PS[i].entries_today=0;
      PS[i].risk_size_ok=false;
      PS[i].risk_size_reason="";
   }
}
bool PushH1(MqlRates &A)
{
   int y=YearOf(A.time); if((!ForwardProspectiveMode && (y<WarmupYear || y>ResearchYear)) || (ForwardProspectiveMode && y<WarmupYear))return false;
   ShiftInsert(g_h1_close,40,A.close);ShiftInsert(g_h1_high,40,A.high);ShiftInsert(g_h1_low,40,A.low);g_h1_count++;return true;
}
bool UpdateH1ClosedBar()
{
   MqlRates r[];ArraySetAsSeries(r,true);if(CopyRates(_Symbol,PERIOD_H1,0,2,r)<2)return false;return PushH1(r[1]);
}
double CurrentH1Pos32()
{
   if(g_h1_count<32)return EMPTY_VALUE;double hi=MaxN(g_h1_high,32),lo=MinN(g_h1_low,32);if(!(hi>lo))return EMPTY_VALUE;return(g_h1_close[0]-lo)/(hi-lo);
}
bool PushM15(MqlRates &A)
{
   int y=YearOf(A.time);if((!ForwardProspectiveMode && (y<WarmupYear || y>ResearchYear)) || (ForwardProspectiveMode && y<WarmupYear))return false;
   double tr=A.high-A.low;if(g_m15_count>0){double pc=g_m15_close[0];tr=MathMax(tr,MathAbs(A.high-pc));tr=MathMax(tr,MathAbs(A.low-pc));}
   ShiftInsert(g_m15_close,80,A.close);ShiftInsert(g_m15_high,80,A.high);ShiftInsert(g_m15_low,80,A.low);ShiftInsert(g_m15_tr,80,tr);
   double a9=2.0/10.0,a50=2.0/51.0;if(g_m15_count==0){g_ema9=A.close;g_ema50=A.close;}else{g_ema9=a9*A.close+(1.0-a9)*g_ema9;g_ema50=a50*A.close+(1.0-a50)*g_ema50;}
   g_m15_count++;return true;
}
void ComputeM15Features()
{
   g_feature_pos16=EMPTY_VALUE;g_feature_ret8_atr=EMPTY_VALUE;g_feature_distlo16_atr=EMPTY_VALUE;if(g_m15_count<50)return;
   double atr14=MeanN(g_m15_tr,14);if(!(atr14>0.0))return;double hi16=MaxN(g_m15_high,16),lo16=MinN(g_m15_low,16);
   if(hi16>lo16)g_feature_pos16=(g_m15_close[0]-lo16)/(hi16-lo16);
   g_feature_ret8_atr=(g_m15_close[0]-g_m15_close[8])/atr14;g_feature_distlo16_atr=(g_m15_close[0]-lo16)/atr14;
}
void FinalizeEntryBars(MqlRates &prev)
{
   for(int i=0;i<PROFILE_COUNT;i++)if(PS[i].active&&!PS[i].b_finalized&&PS[i].entry_bar_time==prev.time){PS[i].b_low_final=prev.low;PS[i].b_close_final=prev.close;PS[i].b_finalized=true;}
}
void BuildOrWarmCurrentM15(datetime current_start)
{
   g_setup_valid=false;g_swept=false;g_consumed=false;g_sweep_ms=0;g_b_start=current_start;
   MqlRates r[];ArraySetAsSeries(r,true);if(CopyRates(_Symbol,PERIOD_M15,0,3,r)<3)return;MqlRates A=r[1],Z=r[2];
   FinalizeEntryBars(A);if(!PushM15(A))return;ComputeM15Features();
   if(!ForwardProspectiveMode && YearOf(current_start)!=ResearchYear)return;
   if(g_m15_count<50||!(g_ema9>g_ema50)||!(A.close<A.open))return;
   MqlRates ref=A;if(Z.close<Z.open&&A.high<=Z.high&&A.low>=Z.low)ref=Z;
   g_feature_h1_pos32=CurrentH1Pos32();if(g_feature_h1_pos32==EMPTY_VALUE)return;
   if(g_feature_pos16==EMPTY_VALUE||g_feature_ret8_atr==EMPTY_VALUE||g_feature_distlo16_atr==EMPTY_VALUE)return;
   g_ref_low=ref.low;g_ref_high=ref.high;if(!(g_ref_high>g_ref_low))return;g_setup_valid=true;
}
bool OptionalPass(int i)
{
   if(CFG[i].optional_code==OPT_POS16)return g_feature_pos16>=CFG[i].optional_threshold;
   if(CFG[i].optional_code==OPT_RET8)return g_feature_ret8_atr>=CFG[i].optional_threshold;
   if(CFG[i].optional_code==OPT_DISTLO)return g_feature_distlo16_atr>=CFG[i].optional_threshold;return false;
}
void LogExit(int i,double exit_bid,string reason,long exit_ms)
{
   double R=(exit_bid-PS[i].entry_ask)/PS[i].initial_risk;
   FileWrite(g_trades,
      CFG[i].cohort_id,
      PS[i].entry_ms,
      StampMsc((datetime)(PS[i].entry_ms/1000),PS[i].entry_ms),
      PS[i].entry_bid,PS[i].entry_ask,
      exit_ms,StampMsc((datetime)(exit_ms/1000),exit_ms),exit_bid,R,reason,
      PS[i].initial_risk,PS[i].ref_low,PS[i].ref_high,PS[i].tp,PS[i].stop,
      PS[i].spread,PS[i].spread_risk,PS[i].entry_offset_sec,PS[i].h1_pos32,
      PS[i].pos16,PS[i].ret8_atr,PS[i].distlo16_atr,
      PS[i].risk_size_ok ? 1:0,PS[i].risk_size_reason,
      PS[i].target_risk_usd,PS[i].raw_volume,PS[i].rounded_volume,PS[i].actual_risk_usd);
   if(!MQLInfoInteger(MQL_TESTER))
      QrosBusPublish(QROS_MOD_NQX,QROS_ACT_CLOSE,CFG[i].cohort_id,exit_ms,exit_bid,PS[i].stop,PS[i].tp,0.0,0.0);
   PS[i].active=false;
}
void CloseAllAtLastExecutable(){if(g_last_exec_ms<=0)return;for(int i=0;i<PROFILE_COUNT;i++)if(PS[i].active)LogExit(i,g_last_exec_bid,"EOD",g_last_exec_ms);}
void HandleDayChange(MqlTick &tick)
{
   int dk=DayKey(tick.time);if(g_current_day_key<0){g_current_day_key=dk;return;}if(dk!=g_current_day_key){CloseAllAtLastExecutable();for(int i=0;i<PROFILE_COUNT;i++)PS[i].entries_today=0;g_last_exec_bid=0.0;g_last_exec_ms=0;g_current_day_key=dk;}
}
void EnterEligibleProfiles(MqlTick &tick)
{
   double risk=g_ref_high-tick.ask;
   if(!(tick.ask>tick.bid) || !(risk>0.0)) return;

   double spread=tick.ask-tick.bid;
   double sr=spread/risk;
   double off=((double)tick.time_msc-(double)((long)g_b_start*1000L))/1000.0;

   for(int i=0;i<PROFILE_COUNT;i++)
   {
      if(PS[i].active || PS[i].entries_today>=3) continue;
      if(!(g_feature_h1_pos32<=CFG[i].h1_pos32_max)) continue;
      if(!(sr<=CFG[i].spread_risk_max)) continue;
      if(!(off>=CFG[i].entry_offset_min)) continue;
      if(!OptionalPass(i)) continue;

      PS[i].active=true;
      PS[i].entries_today++;
      PS[i].entry_ms=tick.time_msc;
      PS[i].entry_bar_time=g_b_start;
      PS[i].entry_bid=tick.bid;
      PS[i].entry_ask=tick.ask;
      PS[i].initial_risk=risk;
      PS[i].ref_low=g_ref_low;
      PS[i].ref_high=g_ref_high;
      PS[i].tp=PriceGridNormalize(g_ref_high);
      PS[i].stop=PriceGridNormalize(tick.ask-risk);
      PS[i].b_finalized=false;
      PS[i].stop_move_checked=false;
      PS[i].h1_pos32=g_feature_h1_pos32;
      PS[i].pos16=g_feature_pos16;
      PS[i].ret8_atr=g_feature_ret8_atr;
      PS[i].distlo16_atr=g_feature_distlo16_atr;
      PS[i].spread=spread;
      PS[i].spread_risk=sr;
      PS[i].entry_offset_sec=off;

      QrosRiskResult rr;
      double bal=AccountInfoDouble(ACCOUNT_BALANCE);
      bool rok=QrosRiskSize(_Symbol,ORDER_TYPE_BUY,tick.ask,PS[i].stop,bal,RiskPctBalance,rr);
      PS[i].risk_size_ok=rok;
      PS[i].risk_size_reason=rr.reason;
      PS[i].target_risk_usd=rr.target_usd;
      PS[i].raw_volume=rr.raw_volume;
      PS[i].rounded_volume=rr.volume;
      PS[i].actual_risk_usd=rr.actual_risk_usd;

      FileWrite(g_candidates,
         CFG[i].cohort_id,tick.time_msc,tick.bid,tick.ask,PS[i].stop,PS[i].tp,
         spread,sr,off,g_feature_h1_pos32,g_feature_pos16,g_feature_ret8_atr,
         g_feature_distlo16_atr,rok?1:0,rr.reason,rr.target_usd,rr.raw_volume,
         rr.volume,rr.actual_risk_usd);
      if(!MQLInfoInteger(MQL_TESTER))
         QrosBusPublish(QROS_MOD_NQX,QROS_ACT_ENTRY,CFG[i].cohort_id,tick.time_msc,tick.ask,PS[i].stop,PS[i].tp,rr.volume,rr.actual_risk_usd);
   }
}
void ProcessActive(MqlTick &tick)
{
   if(!(tick.ask>tick.bid))return;
   for(int i=0;i<PROFILE_COUNT;i++)
   {
      if(!PS[i].active)continue;
      if(PS[i].b_finalized&&!PS[i].stop_move_checked)
      {
         PS[i].stop_move_checked=true;
         if(PS[i].b_close_final>=PS[i].ref_low&&PS[i].b_close_final<=PS[i].ref_high)
         {
            double cand=PriceGridNormalize(PS[i].b_low_final-2.0);
            if(PriceGridIndex(cand)>PriceGridIndex(PS[i].stop))
            {
               PS[i].stop=cand;
               if(!MQLInfoInteger(MQL_TESTER))
                  QrosBusPublish(QROS_MOD_NQX,QROS_ACT_MODIFY_SL,CFG[i].cohort_id,tick.time_msc,0.0,PS[i].stop,PS[i].tp,0.0,0.0);
            }
         }
      }
      if(PriceLEGrid(tick.bid,PS[i].stop))LogExit(i,tick.bid,"SL",tick.time_msc);
      else if(PriceGEGrid(tick.bid,PS[i].tp))LogExit(i,tick.bid,"TP",tick.time_msc);
   }
}

bool QrosForwardWarmup()
{
   if(!ForwardProspectiveMode) return true;
   datetime cur_m15=iTime(_Symbol,PERIOD_M15,0);
   datetime cur_h1=iTime(_Symbol,PERIOD_H1,0);
   if(cur_m15<=0 || cur_h1<=0) return false;

   MqlDateTime ss; TimeToStruct(cur_m15,ss);
   ss.year=WarmupYear;ss.mon=1;ss.day=1;ss.hour=0;ss.min=0;ss.sec=0;
   datetime start=StructToTime(ss);

   MqlRates hr[];ArraySetAsSeries(hr,false);
   int gh=CopyRates(_Symbol,PERIOD_H1,start,cur_h1-1,hr);
   if(gh<=0) return false;
   for(int i=0;i<gh;i++) PushH1(hr[i]);

   MqlRates mr[];ArraySetAsSeries(mr,false);
   datetime replay_to=cur_m15-901;
   int gm=CopyRates(_Symbol,PERIOD_M15,start,replay_to,mr);
   if(gm<=0) return false;
   for(int i=0;i<gm;i++) PushM15(mr[i]);

   g_last_h1_bar=cur_h1;
   g_last_m15_bar=cur_m15;
   BuildOrWarmCurrentM15(cur_m15);
   return (g_m15_count>=50 && g_h1_count>=32);
}

int OnInit()
{
   InitConfigs();
   ResetResearchState();
   if(!MQLInfoInteger(MQL_TESTER))
   {
      if(_Symbol!="NDX"){Print("QROS NQX emitter requires NDX");return INIT_PARAMETERS_INCORRECT;}
      if(!QrosBusProducerInit(QROS_MOD_NQX)){Print("QROS NQX producer fencing failed");return INIT_FAILED;}
      if(!QrosGvSetChecked(QrosBusKey(QROS_MOD_NQX,"SOURCE_TOKEN"),(double)QROS_V224_EMITTER_SOURCE_TOKEN)){QrosBusProducerRelease();return INIT_FAILED;}
      QrosBusSetState(QROS_MOD_NQX,QROS_STATE_INIT);
      QrosBusHeartbeat(QROS_MOD_NQX);
   }

   string tf=OutputPrefix+"_TRADES_v15700.csv";
   string cf=OutputPrefix+"_CANDIDATES_v15700.csv";
   string ef=OutputPrefix+"_ENV_v15700.csv";

   g_trades=FileOpen(tf,FileFlags(),',');
   g_candidates=FileOpen(cf,FileFlags(),',');
   g_env=FileOpen(ef,FileFlags(),',');

   if(g_trades==INVALID_HANDLE || g_candidates==INVALID_HANDLE || g_env==INVALID_HANDLE)
   {
      Print("QROS NQX shadow FileOpen failed ",GetLastError());
      if(!MQLInfoInteger(MQL_TESTER)) QrosBusSetState(QROS_MOD_NQX,QROS_STATE_FAULT);
      return INIT_FAILED;
   }

   FileWrite(g_trades,
      "cohort_id","entry_ms","entry_stamp","entry_bid","entry_ask",
      "exit_ms","exit_stamp","exit_bid","R","reason","initial_risk",
      "ref_low","ref_high","tp","final_stop","spread","spread_risk",
      "entry_offset_sec","h1_pos32","pos16","ret8_atr","dist_lo16_atr",
      "risk_size_ok","risk_size_reason","target_risk_usd","raw_volume",
      "rounded_volume","actual_risk_usd");

   FileWrite(g_candidates,
      "cohort_id","entry_ms","entry_bid","entry_ask","initial_stop","tp",
      "spread","spread_risk","entry_offset_sec","h1_pos32","pos16",
      "ret8_atr","dist_lo16_atr","risk_size_ok","risk_size_reason",
      "target_risk_usd","raw_volume","rounded_volume","actual_risk_usd");

   FileWrite(g_env,"key","value");
   FileWrite(g_env,"schema","QROS_NQX_SHADOW_17_31_v15700");
   FileWrite(g_env,"symbol",_Symbol);
   FileWrite(g_env,"account_server",AccountInfoString(ACCOUNT_SERVER));
   FileWrite(g_env,"account_company",AccountInfoString(ACCOUNT_COMPANY));
   FileWrite(g_env,"research_year",ResearchYear);
   FileWrite(g_env,"warmup_year",WarmupYear);
   FileWrite(g_env,"profiles","17,31");
   FileWrite(g_env,"risk_pct_balance",DoubleToString(RiskPctBalance,4));
   FileWrite(g_env,"orders_sent",0);
   FileWrite(g_env,"terminal_build",(long)TerminalInfoInteger(TERMINAL_BUILD));
   FileWrite(g_env,"mql_tester",(long)MQLInfoInteger(MQL_TESTER));
   FileWrite(g_env,"digits",(long)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS));
   FileWrite(g_env,"point",DoubleToString(SymbolInfoDouble(_Symbol,SYMBOL_POINT),10));
   FileWrite(g_env,"tick_size",DoubleToString(SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE),10));
   FileWrite(g_env,"tick_value",DoubleToString(SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE),10));
   FileWrite(g_env,"contract_size",DoubleToString(SymbolInfoDouble(_Symbol,SYMBOL_TRADE_CONTRACT_SIZE),10));
   FileFlush(g_env);
   if(ForwardProspectiveMode && !MQLInfoInteger(MQL_TESTER))
   {
      if(!QrosForwardWarmup())
      {
         Print("QROS NQX forward warmup failed");
         QrosBusSetState(QROS_MOD_NQX,QROS_STATE_FAULT);
         return INIT_FAILED;
      }
   }
   if(!MQLInfoInteger(MQL_TESTER))
   {
      QrosBusSetState(QROS_MOD_NQX,QROS_STATE_READY);
      QrosBusHeartbeat(QROS_MOD_NQX);
      EventSetTimer(1);
   }
   return INIT_SUCCEEDED;
}
void OnTimer()
{
   if(!MQLInfoInteger(MQL_TESTER)) QrosBusHeartbeat(QROS_MOD_NQX);
}
void OnTick()
{
   if(!MQLInfoInteger(MQL_TESTER)) QrosBusHeartbeat(QROS_MOD_NQX);
   MqlTick tick;if(!SymbolInfoTick(_Symbol,tick))return;if(!MQLInfoInteger(MQL_TESTER)) QrosBusWatermark(QROS_MOD_NQX,tick.time_msc);g_ticks_total++;if((tick.flags&TICK_FLAG_BID)!=0)g_ticks_bidflag++;if((tick.flags&TICK_FLAG_ASK)!=0)g_ticks_askflag++;if(tick.ask==tick.bid)g_ticks_zero++;if(tick.ask<tick.bid)g_ticks_crossed++;
   if(!ForwardProspectiveMode && !AtOrBeforeResearchEnd(tick)){if(!g_end_closed){CloseAllAtLastExecutable();g_end_closed=true;}return;}
   HandleDayChange(tick);bool exec=(tick.ask>tick.bid);if(exec){g_ticks_exec++;g_last_exec_bid=tick.bid;g_last_exec_ms=tick.time_msc;}
   datetime h1=iTime(_Symbol,PERIOD_H1,0);if(h1!=0&&h1!=g_last_h1_bar){UpdateH1ClosedBar();g_last_h1_bar=h1;}
   datetime m15=iTime(_Symbol,PERIOD_M15,0);if(m15!=0&&m15!=g_last_m15_bar){BuildOrWarmCurrentM15(m15);g_last_m15_bar=m15;}
   if(!ForwardProspectiveMode && YearOf(tick.time)!=ResearchYear)return;
   if(g_setup_valid&&!g_consumed&&((tick.flags&TICK_FLAG_BID)!=0))
   {
      if(!g_swept){if(tick.bid<g_ref_low){g_swept=true;g_min_bid=tick.bid;g_sweep_ms=tick.time_msc;}}
      else{if(tick.bid<g_min_bid)g_min_bid=tick.bid;if(tick.bid>=g_ref_low){g_consumed=true;EnterEligibleProfiles(tick);}}
   }
   ProcessActive(tick);
}
void OnDeinit(const int reason)
{
   if(!MQLInfoInteger(MQL_TESTER))
   {
      EventKillTimer();
      QrosBusSetState(QROS_MOD_NQX,QROS_STATE_OFF);
      QrosBusProducerRelease();
   }
   if(!g_end_closed) CloseAllAtLastExecutable();
   if(g_env!=INVALID_HANDLE)
   {
      FileWrite(g_env,"ticks_total",g_ticks_total);
      FileWrite(g_env,"ticks_bidflag",g_ticks_bidflag);
      FileWrite(g_env,"ticks_askflag",g_ticks_askflag);
      FileWrite(g_env,"ticks_executable",g_ticks_exec);
      FileWrite(g_env,"ticks_zero_spread",g_ticks_zero);
      FileWrite(g_env,"ticks_crossed",g_ticks_crossed);
      FileWrite(g_env,"end_closed",g_end_closed?1:0);
      FileWrite(g_env,"deinit_reason",reason);
      FileWrite(g_env,"status","FINISHED");
      FileClose(g_env);
   }
   if(g_candidates!=INVALID_HANDLE) FileClose(g_candidates);
   if(g_trades!=INVALID_HANDLE) FileClose(g_trades);
}
