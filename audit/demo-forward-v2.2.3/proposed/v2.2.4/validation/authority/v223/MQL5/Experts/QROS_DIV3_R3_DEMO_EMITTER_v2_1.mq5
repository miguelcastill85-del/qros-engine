//+------------------------------------------------------------------+
//| QROS DIV3 NQX MT5 parity harness v1                              |
//| NON-TRADING: independent signal/execution replay on real ticks   |
//| Frozen module: NQX_DIV3_R3_FAILED_BREAK_MA_CROSS_LWMA_M15        |
//+------------------------------------------------------------------+
#property strict
#property version   "2.10"
#property description "QROS DIV3 profile-0 prospective DEMO signal emitter; no order calls"

#include <QROS_DEMO_BUS_v2.mqh>

input bool     InpForwardProspectiveMode = true;
input int      InpHistoryStartYear = 2018;
input int      InpHistoryStartMonth = 1;
input int      InpHistoryStartDay = 25;
input int      InpValidationStartYear = 2022;
input int      InpValidationStartMonth = 1;
input int      InpValidationStartDay = 1;
input int      InpValidationEndYear = 2025;
input int      InpValidationEndMonth = 1;
input int      InpValidationEndDay = 1;
input double   InpResearchUnit = 0.1;      // one integer unit = 0.1 NDX point
input bool     InpWriteFullBarAudit = true;
input string   InpPrefix = "QROS_DIV3_MT5_v1";

#define PROFILE_COUNT 4
#define BAR_MS 900000
#define DAY_MS 86400000

#define QROS_DIV3_BAR_RESERVE      262144
#define QROS_DIV3_PENDING_RESERVE    8192
#define QROS_DIV3_EVENT_RESERVE     32768
#define QROS_DIV3_PROGRESS_EVERY      256

struct QBar
  {
   datetime time;
   long time_ms;
   int o,h,l,c;
   long vol;
   double ema5,ema13,macd,rsi7,mfi7,atr14,lwma9,lwma50;
   double rsi_ag,rsi_al;
   double posflow,negflow,tr;
   bool pivot_low;
  };

struct PendingEvent
  {
   int profile;
   int l1;
   int l2;
   int start_bar;
   int expire_bar;
  };

struct SignalEvent
  {
   int profile;
   int l1;
   int l2;
   int rec;
   long signal_ms;
   bool consumed;
  };

struct PState
  {
   bool active;
   long entry_ms;
   long active_day;
   int entry_bid_u;
   int entry_ask_u;
   int exit_u;
   int sl_u;
   int tp_u;
   int risk_u;
   int l1,l2,rec;
   double min_side;
   double max_side;
   long last_valid_ms;
   int last_valid_side_u;
   long controller_day;
   int day_entries;
   long trades;
   long overlap_skips;
   long dailycap_skips;
  };

QBar g_bars[];
PendingEvent g_pending[];
SignalEvent g_events[];
PState g_ps[PROFILE_COUNT];
int g_event_cursor=0;
datetime g_last_open=0;
double g_unit=0.1;
datetime g_history_start=0,g_validation_start=0,g_validation_end=0;
int g_fbars=INVALID_HANDLE,g_fsignals=INVALID_HANDLE,g_ftrades=INVALID_HANDLE,g_fsummary=INVALID_HANDLE,g_fenv=INVALID_HANDLE;
long g_ticks_total=0,g_ticks_exec=0,g_ticks_zero=0,g_ticks_crossed=0,g_ticks_nonpositive=0;
long g_forward_start_ms=0;
long g_signal_count[PROFILE_COUNT]={0,0,0,0};
string g_cfg[PROFILE_COUNT]=
  {
   "BUY_R3_PIVOT_CONFIRMED_MIN8_MAX64_W2_MA_CROSS_CONFIRMATION_LWMA",
   "BUY_R3_PIVOT_CONFIRMED_MIN8_MAX32_W2_MA_CROSS_CONFIRMATION_LWMA",
   "BUY_R3_PIVOT_CONFIRMED_MIN8_MAX32_W8_MA_CROSS_CONFIRMATION_LWMA",
   "BUY_R3_PIVOT_CONFIRMED_MIN8_MAX64_W8_MA_CROSS_CONFIRMATION_LWMA"
  };
string g_mask[PROFILE_COUNT]=
  {
   "248924e7d6ad360fa8126e767a78149c37531145d007a30f3994fe36529414e8",
   "b2c4d0e7498175f1c5a85fbe104a995d1597da1247c7a69ff7efb8deac9ae1e5",
   "2af1aa7b053ab5f88f18d61ccb55bd2bcc89fc8d71aa72eaead8cd4ef505250f",
   "889cedbf877a5fae5de7200aac0a9bb35faee127b6f7d717a7cf383a71d9c2c1"
  };
int g_maxsep[PROFILE_COUNT]={64,32,32,64};
int g_window[PROFILE_COUNT]={2,2,8,8};

int PriceToU(const double p){ return (int)MathRound(p/g_unit); }
long DayId(const long ms){ return ms/DAY_MS; }

bool IsFiniteD(const double x){ return MathIsValidNumber(x); }

void CsvHeaders()
  {
   if(g_fbars!=INVALID_HANDLE)
      FileWrite(g_fbars,"bar_idx","bucket_ms","open_u","high_u","low_u","close_u","tick_volume");
   if(g_fsignals!=INVALID_HANDLE)
      FileWrite(g_fsignals,"profile_id","mask_sha256","config_id","event_seq","l1_bar","l2_bar","reclaim_bar","signal_close_ms");
   if(g_ftrades!=INVALID_HANDLE)
      FileWrite(g_ftrades,"profile_id","mask_sha256","config_id","l1_bar","l2_bar","reclaim_bar","entry_ts_ms","exit_ts_ms","entry_bid_u","entry_ask_u","exit_u","sl_u","tp_u","risk_u","pnl_R","mae_R","mfe_R","reason");
  }

void AddPending(const int profile,const int l1,const int l2)
  {
   PendingEvent p;
   p.profile=profile;p.l1=l1;p.l2=l2;p.start_bar=l2+3;p.expire_bar=l2+g_window[profile]+1;
   int n=ArraySize(g_pending);ArrayResize(g_pending,n+1,QROS_DIV3_PENDING_RESERVE);g_pending[n]=p;
  }

void AddSignal(const int profile,const int l1,const int l2,const int rec)
  {
   long sm=g_bars[rec].time_ms+BAR_MS;
   if(InpForwardProspectiveMode)
     {
      if(sm<=g_forward_start_ms) return;
     }
   else
     {
      if(sm<(long)g_validation_start*1000 || sm>=(long)g_validation_end*1000) return;
     }
   SignalEvent e;e.profile=profile;e.l1=l1;e.l2=l2;e.rec=rec;e.signal_ms=sm;e.consumed=false;
   int n=ArraySize(g_events);ArrayResize(g_events,n+1,QROS_DIV3_EVENT_RESERVE);g_events[n]=e;
   long seq=g_signal_count[profile]++;
   if(g_fsignals!=INVALID_HANDLE)
      FileWrite(g_fsignals,profile,g_mask[profile],g_cfg[profile],seq,l1,l2,rec,sm);
  }

bool PivotLowAt(const int i)
  {
   if(i<3 || i+3>=ArraySize(g_bars)) return false;
   int x=g_bars[i].l;
   for(int j=i-3;j<i;j++) if(!(x<g_bars[j].l)) return false;
   for(int j=i+1;j<=i+3;j++) if(!(x<=g_bars[j].l)) return false;
   return true;
  }

int FindL1(const int l2,const int maxsep)
  {
   for(int j=l2-8;j>=l2-maxsep;j--)
     {
      if(j>=0 && g_bars[j].pivot_low) return j;
     }
   return -1;
  }

bool DivergenceOK(const int l1,const int l2)
  {
   if(l1<49 || l2<49) return false;
   return (g_bars[l2].l<g_bars[l1].l &&
           g_bars[l2].macd>g_bars[l1].macd &&
           g_bars[l2].rsi7>g_bars[l1].rsi7 &&
           g_bars[l2].mfi7>g_bars[l1].mfi7);
  }

void ProcessPendingAtBar(const int q)
  {
   int n=ArraySize(g_pending);
   int w=0;
   for(int i=0;i<n;i++)
     {
      PendingEvent p=g_pending[i];
      bool keep=true;
      if(q>=p.start_bar && q<=p.expire_bar)
        {
         // Frozen research semantics: the FIRST structural reclaim consumes the
         // event. MA9/50 is evaluated only on that reclaim; a later reclaim is
         // never substituted after seeing the first one fail the MA context.
         if(g_bars[q].c>g_bars[p.l1].l)
           {
            if(g_bars[q].lwma9>g_bars[q].lwma50)
               AddSignal(p.profile,p.l1,p.l2,q);
            keep=false;
           }
        }
      if(q>=p.expire_bar && keep) keep=false;
      if(keep){ if(w!=i) g_pending[w]=g_pending[i]; w++; }
     }
   if(w<n) ArrayResize(g_pending,w);
  }

void ComputeNewBarFeatures(const int i)
  {
   g_bars[i].ema5=0.0;g_bars[i].ema13=0.0;g_bars[i].macd=0.0;g_bars[i].rsi7=0.0;g_bars[i].mfi7=0.0;g_bars[i].atr14=0.0;g_bars[i].lwma9=0.0;g_bars[i].lwma50=0.0;g_bars[i].rsi_ag=0.0;g_bars[i].rsi_al=0.0;
   // TR
   if(i==0) g_bars[i].tr=(double)(g_bars[i].h-g_bars[i].l);
   else g_bars[i].tr=MathMax((double)(g_bars[i].h-g_bars[i].l),MathMax(MathAbs((double)g_bars[i].h-g_bars[i-1].c),MathAbs((double)g_bars[i].l-g_bars[i-1].c)));
   // EMA 5 / 13: SMA seed then recursive, identical to research Python.
   if(i==4){double s=0;for(int k=0;k<5;k++)s+=g_bars[k].c;g_bars[i].ema5=s/5.0;}
   else if(i>4) g_bars[i].ema5=(2.0/6.0)*g_bars[i].c+(1.0-2.0/6.0)*g_bars[i-1].ema5;
   if(i==12){double s=0;for(int k=0;k<13;k++)s+=g_bars[k].c;g_bars[i].ema13=s/13.0;}
   else if(i>12) g_bars[i].ema13=(2.0/14.0)*g_bars[i].c+(1.0-2.0/14.0)*g_bars[i-1].ema13;
   if(i>=12) g_bars[i].macd=g_bars[i].ema5-g_bars[i].ema13;
   // RSI7 Wilder: preserve recursive average gain/loss as explicit state.
   if(i==7)
     {
      double ag=0,al=0;
      for(int k=1;k<=7;k++){double d=g_bars[k].c-g_bars[k-1].c;if(d>0)ag+=d;else if(d<0)al-=d;}
      ag/=7.0;al/=7.0;g_bars[i].rsi_ag=ag;g_bars[i].rsi_al=al;
      g_bars[i].rsi7=(al==0.0?(ag>0.0?100.0:50.0):100.0-100.0/(1.0+ag/al));
     }
   else if(i>7)
     {
      double d=g_bars[i].c-g_bars[i-1].c;double gg=(d>0?d:0.0),ll=(d<0?-d:0.0);
      double ag=(g_bars[i-1].rsi_ag*6.0+gg)/7.0;double al=(g_bars[i-1].rsi_al*6.0+ll)/7.0;
      g_bars[i].rsi_ag=ag;g_bars[i].rsi_al=al;
      g_bars[i].rsi7=(al==0.0?(ag>0.0?100.0:50.0):100.0-100.0/(1.0+ag/al));
     }
   // MFI7 exact rolling raw flow.
   double tp=((double)g_bars[i].h+g_bars[i].l+g_bars[i].c)/3.0;
   g_bars[i].posflow=0.0;g_bars[i].negflow=0.0;
   if(i>0){double ptp=((double)g_bars[i-1].h+g_bars[i-1].l+g_bars[i-1].c)/3.0;double mf=tp*(double)g_bars[i].vol;if(tp>ptp)g_bars[i].posflow=mf;else if(tp<ptp)g_bars[i].negflow=mf;}
   if(i>=7){double ps=0,ns=0;for(int k=i-6;k<=i;k++){ps+=g_bars[k].posflow;ns+=g_bars[k].negflow;}g_bars[i].mfi7=(ns==0.0?(ps>0.0?100.0:50.0):100.0-100.0/(1.0+ps/ns));}
   // ATR14 Wilder.
   if(i==13){double s=0;for(int k=0;k<14;k++)s+=g_bars[k].tr;g_bars[i].atr14=s/14.0;}
   else if(i>13) g_bars[i].atr14=(g_bars[i-1].atr14*13.0+g_bars[i].tr)/14.0;
   // LWMA9 / LWMA50.
   if(i>=8){double s=0;for(int k=0;k<9;k++)s+=(k+1)*g_bars[i-8+k].c;g_bars[i].lwma9=s/45.0;}
   if(i>=49){double s=0;for(int k=0;k<50;k++)s+=(k+1)*g_bars[i-49+k].c;g_bars[i].lwma50=s/1275.0;}
  }

bool AppendRate(const MqlRates &r)
  {
   int n=ArraySize(g_bars);ArrayResize(g_bars,n+1,QROS_DIV3_BAR_RESERVE);
   QBar b;b.time=r.time;b.time_ms=(long)r.time*1000;b.o=PriceToU(r.open);b.h=PriceToU(r.high);b.l=PriceToU(r.low);b.c=PriceToU(r.close);b.vol=(long)r.tick_volume;b.pivot_low=false;
   g_bars[n]=b;ComputeNewBarFeatures(n);
   if(g_fbars!=INVALID_HANDLE) FileWrite(g_fbars,n,g_bars[n].time_ms,g_bars[n].o,g_bars[n].h,g_bars[n].l,g_bars[n].c,g_bars[n].vol);
   int l2=n-3;
   if(l2>=0)
     {
      bool pv=PivotLowAt(l2);g_bars[l2].pivot_low=pv;
      if(pv && l2>=55)
        {
         for(int p=0;p<PROFILE_COUNT;p++)
           {
            int l1=FindL1(l2,g_maxsep[p]);
            if(l1>=0 && DivergenceOK(l1,l2)) AddPending(p,l1,l2);
           }
        }
     }
   ProcessPendingAtBar(n);
   return true;
  }

datetime QrosBuildDate(const int y,const int m,const int d)
  {
   if(y<2000 || y>2100 || m<1 || m>12 || d<1 || d>31) return 0;
   MqlDateTime s;ZeroMemory(s);s.year=y;s.mon=m;s.day=d;
   return StructToTime(s);
  }

bool LoadHistoryTo(const datetime exclusive_time)
  {
   MqlRates rr[];
   ArraySetAsSeries(rr,false);

   datetime to=exclusive_time-1;
   ResetLastError();
   int got=CopyRates(_Symbol,PERIOD_M15,g_history_start,to,rr);

   if(got<=0)
     {
      PrintFormat("[DIV3] CopyRates init failed err=%d",GetLastError());
      return false;
     }

   if(!MQLInfoInteger(MQL_TESTER))
     {
      GlobalVariableSet("QDB1.3.INIT_TOTAL",(double)got);
      GlobalVariableSet("QDB1.3.INIT_DONE",0.0);
      QrosBusHeartbeat(QROS_MOD_DIV3);
     }

   for(int i=0;i<got;i++)
     {
      AppendRate(rr[i]);

      if(!MQLInfoInteger(MQL_TESTER) &&
         ((i+1)%QROS_DIV3_PROGRESS_EVERY==0 || i+1==got))
        {
         GlobalVariableSet("QDB1.3.INIT_DONE",(double)(i+1));
         QrosBusHeartbeat(QROS_MOD_DIV3);
        }
     }

   g_last_open=g_bars[ArraySize(g_bars)-1].time;

   if(!MQLInfoInteger(MQL_TESTER))
     {
      GlobalVariableSet("QDB1.3.INIT_DONE",(double)got);
      QrosBusHeartbeat(QROS_MOD_DIV3);
     }

   PrintFormat("[DIV3] init bars=%d last=%s",
               ArraySize(g_bars),
               TimeToString(g_last_open,TIME_DATE|TIME_MINUTES));

   return true;
  }

void AppendClosedBars(const datetime current_open)
  {
   if(current_open<=g_last_open) return;
   MqlRates rr[];ArraySetAsSeries(rr,false);
   int got=CopyRates(_Symbol,PERIOD_M15,g_last_open+1,current_open-1,rr);
   if(got>0)
      for(int i=0;i<got;i++) if(rr[i].time>g_last_open){AppendRate(rr[i]);g_last_open=rr[i].time;}
  }

void FinalizeTrade(const int p,const long exit_ms,const int exit_u,const int reason)
  {
   PState s=g_ps[p];
   double pnl=((double)exit_u-s.entry_ask_u)/s.risk_u;
   double mae=((double)s.entry_ask_u-s.min_side)/s.risk_u;
   double mfe=(s.max_side-(double)s.entry_ask_u)/s.risk_u;
   if(g_ftrades!=INVALID_HANDLE)
      FileWrite(g_ftrades,p,g_mask[p],g_cfg[p],s.l1,s.l2,s.rec,s.entry_ms,exit_ms,s.entry_bid_u,s.entry_ask_u,exit_u,s.sl_u,s.tp_u,s.risk_u,DoubleToString(pnl,15),DoubleToString(mae,15),DoubleToString(mfe,15),reason);
   if(p==0 && !MQLInfoInteger(MQL_TESTER))
      QrosBusPublish(QROS_MOD_DIV3,QROS_ACT_CLOSE,0,exit_ms,(double)exit_u*g_unit,(double)s.sl_u*g_unit,(double)s.tp_u*g_unit,(double)reason,0.0);
   g_ps[p].active=false;g_ps[p].trades++;
  }

void HandleDayBoundary(const long now_ms)
  {
   long d=DayId(now_ms);
   for(int p=0;p<PROFILE_COUNT;p++)
     {
      if(g_ps[p].controller_day!=d){g_ps[p].controller_day=d;g_ps[p].day_entries=0;}
      if(g_ps[p].active && d>g_ps[p].active_day)
        {
         if(g_ps[p].last_valid_ms>=0) FinalizeTrade(p,g_ps[p].last_valid_ms,g_ps[p].last_valid_side_u,3);
        }
     }
  }

void ConsumeDueEvents(const MqlTick &tick,const int bid_u,const int ask_u)
  {
   long now=tick.time_msc;
   int n=ArraySize(g_events);
   while(g_event_cursor<n && g_events[g_event_cursor].signal_ms<now)
     {
      SignalEvent e=g_events[g_event_cursor];int p=e.profile;g_events[g_event_cursor].consumed=true;g_event_cursor++;
      if(g_ps[p].active){g_ps[p].overlap_skips++;continue;}
      long d=DayId(now);
      if(g_ps[p].controller_day!=d){g_ps[p].controller_day=d;g_ps[p].day_entries=0;}
      if(g_ps[p].day_entries>=3){g_ps[p].dailycap_skips++;continue;}
      int sl=(int)MathFloor((double)g_bars[e.l2].l-0.10*g_bars[e.l2].atr14);
      int risk=ask_u-sl;
      if(risk<=0){PrintFormat("[DIV3] invalid risk p=%d at %I64d",p,now);continue;}
      PState s=g_ps[p];s.active=true;s.entry_ms=now;s.active_day=d;s.entry_bid_u=bid_u;s.entry_ask_u=ask_u;s.sl_u=sl;s.risk_u=risk;s.tp_u=ask_u+2*risk;s.l1=e.l1;s.l2=e.l2;s.rec=e.rec;s.min_side=bid_u;s.max_side=bid_u;s.last_valid_ms=now;s.last_valid_side_u=bid_u;s.day_entries++;
      g_ps[p]=s;
      if(p==0 && !MQLInfoInteger(MQL_TESTER))
         QrosBusPublish(QROS_MOD_DIV3,QROS_ACT_ENTRY,0,now,(double)ask_u*g_unit,(double)sl*g_unit,(double)s.tp_u*g_unit,0.0,0.0);
     }
  }

void UpdateAndExit(const MqlTick &tick,const int bid_u)
  {
   for(int p=0;p<PROFILE_COUNT;p++)
     {
      if(!g_ps[p].active) continue;
      if(DayId(tick.time_msc)!=g_ps[p].active_day) continue;
      if(bid_u<g_ps[p].min_side) g_ps[p].min_side=bid_u;
      if(bid_u>g_ps[p].max_side) g_ps[p].max_side=bid_u;
      g_ps[p].last_valid_ms=tick.time_msc;g_ps[p].last_valid_side_u=bid_u;
      // SL first, exactly as research replay
      if(bid_u<=g_ps[p].sl_u){FinalizeTrade(p,tick.time_msc,bid_u,1);continue;}
      if(bid_u>=g_ps[p].tp_u){FinalizeTrade(p,tick.time_msc,bid_u,2);continue;}
     }
  }

int OnInit()
  {
   if(_Period!=PERIOD_M15){Print("[DIV3] Must run on M15");return INIT_PARAMETERS_INCORRECT;}
   if(!MQLInfoInteger(MQL_TESTER) && _Symbol!="NDX")
     {Print("[DIV3] prospective emitter requires NDX");return INIT_PARAMETERS_INCORRECT;}

   g_history_start=QrosBuildDate(InpHistoryStartYear,InpHistoryStartMonth,InpHistoryStartDay);
   g_validation_start=QrosBuildDate(InpValidationStartYear,InpValidationStartMonth,InpValidationStartDay);
   g_validation_end=QrosBuildDate(InpValidationEndYear,InpValidationEndMonth,InpValidationEndDay);
   if(g_history_start<D'2000.01.01 00:00:00' || g_validation_start<=0 || g_validation_end<=g_validation_start)
     {Print("[DIV3] invalid frozen date components");return INIT_PARAMETERS_INCORRECT;}
   if(InpResearchUnit<=0) return INIT_PARAMETERS_INCORRECT;

   if(!MQLInfoInteger(MQL_TESTER))
     {
      GlobalVariableSet("QDB1.3.INIT_TOTAL",0.0);
      GlobalVariableSet("QDB1.3.INIT_DONE",0.0);
      QrosBusSetState(QROS_MOD_DIV3,QROS_STATE_INIT);
      QrosBusHeartbeat(QROS_MOD_DIV3);
     }

   g_unit=InpResearchUnit;
   int flags=FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON;
   if(InpWriteFullBarAudit) g_fbars=FileOpen(InpPrefix+"_BARS.csv",flags,',');
   g_fsignals=FileOpen(InpPrefix+"_SIGNALS.csv",flags,',');
   g_ftrades=FileOpen(InpPrefix+"_TRADES.csv",flags,',');
   g_fsummary=FileOpen(InpPrefix+"_SUMMARY.csv",flags,',');
   g_fenv=FileOpen(InpPrefix+"_ENV.csv",flags,',');
   if(g_fsignals==INVALID_HANDLE || g_ftrades==INVALID_HANDLE || g_fsummary==INVALID_HANDLE || g_fenv==INVALID_HANDLE)
     {
      PrintFormat("[DIV3] FileOpen failed %d",GetLastError());
      if(!MQLInfoInteger(MQL_TESTER)) QrosBusSetState(QROS_MOD_DIV3,QROS_STATE_FAULT);
      return INIT_FAILED;
     }
   CsvHeaders();
   FileWrite(g_fenv,"key","value");
   FileWrite(g_fenv,"terminal_build",(long)TerminalInfoInteger(TERMINAL_BUILD));
   FileWrite(g_fenv,"account_server",AccountInfoString(ACCOUNT_SERVER));
   FileWrite(g_fenv,"account_company",AccountInfoString(ACCOUNT_COMPANY));
   FileWrite(g_fenv,"account_login",(long)AccountInfoInteger(ACCOUNT_LOGIN));
   FileWrite(g_fenv,"symbol",_Symbol);
   FileWrite(g_fenv,"symbol_digits",(long)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS));
   FileWrite(g_fenv,"symbol_point",DoubleToString(SymbolInfoDouble(_Symbol,SYMBOL_POINT),10));
   FileWrite(g_fenv,"symbol_tick_size",DoubleToString(SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE),10));
   FileWrite(g_fenv,"symbol_contract_size",DoubleToString(SymbolInfoDouble(_Symbol,SYMBOL_TRADE_CONTRACT_SIZE),10));
   FileWrite(g_fenv,"symbol_volume_min",DoubleToString(SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN),10));
   FileWrite(g_fenv,"symbol_volume_step",DoubleToString(SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP),10));
   FileWrite(g_fenv,"symbol_volume_max",DoubleToString(SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX),10));
   FileWrite(g_fenv,"currency_profit",SymbolInfoString(_Symbol,SYMBOL_CURRENCY_PROFIT));
   FileWrite(g_fenv,"history_start",(long)g_history_start);
   FileWrite(g_fenv,"validation_start",(long)g_validation_start);
   FileWrite(g_fenv,"validation_end_exclusive",(long)g_validation_end);
   FileWrite(g_fenv,"history_start_ymd",IntegerToString(InpHistoryStartYear)+"-"+IntegerToString(InpHistoryStartMonth)+"-"+IntegerToString(InpHistoryStartDay));
   FileWrite(g_fenv,"research_unit",DoubleToString(InpResearchUnit,10));
   FileFlush(g_fenv);

   for(int p=0;p<PROFILE_COUNT;p++){g_ps[p].active=false;g_ps[p].controller_day=-1;g_ps[p].day_entries=0;g_ps[p].last_valid_ms=-1;}
   datetime cur=iTime(_Symbol,PERIOD_M15,0);
   if(cur<=0)
     {
      Print("[DIV3] no current M15 bar");
      if(!MQLInfoInteger(MQL_TESTER)) QrosBusSetState(QROS_MOD_DIV3,QROS_STATE_FAULT);
      return INIT_FAILED;
     }
   if(InpForwardProspectiveMode) g_forward_start_ms=(long)cur*1000L;
   if(!LoadHistoryTo(cur))
     {
      if(!MQLInfoInteger(MQL_TESTER)) QrosBusSetState(QROS_MOD_DIV3,QROS_STATE_FAULT);
      return INIT_FAILED;
     }
   if(!MQLInfoInteger(MQL_TESTER))
     {
      QrosBusSetState(QROS_MOD_DIV3,QROS_STATE_READY);
      QrosBusHeartbeat(QROS_MOD_DIV3);
      EventSetTimer(1);
     }
   return INIT_SUCCEEDED;
  }

void OnTimer()
  {
   if(!MQLInfoInteger(MQL_TESTER)) QrosBusHeartbeat(QROS_MOD_DIV3);
  }

void OnTick()
  {
   if(!MQLInfoInteger(MQL_TESTER)) QrosBusHeartbeat(QROS_MOD_DIV3);
   MqlTick tick;if(!SymbolInfoTick(_Symbol,tick)) return;
   g_ticks_total++;
   datetime cur=iTime(_Symbol,PERIOD_M15,0);if(cur>g_last_open) AppendClosedBars(cur);
   // research rejects zero/crossed spread for executable fills/exits
   if(tick.bid<=0 || tick.ask<=0){g_ticks_nonpositive++;return;}
   if(tick.ask<tick.bid){g_ticks_crossed++;return;}
   if(tick.ask==tick.bid){g_ticks_zero++;return;}
   g_ticks_exec++;
   int bid_u=PriceToU(tick.bid),ask_u=PriceToU(tick.ask);
   HandleDayBoundary(tick.time_msc);
   // Due events are consumed before same-tick SL/TP exit, reproducing et<=active skip.
   ConsumeDueEvents(tick,bid_u,ask_u);
   UpdateAndExit(tick,bid_u);
  }

void OnDeinit(const int reason)
  {
   if(!MQLInfoInteger(MQL_TESTER))
     {
      EventKillTimer();
      QrosBusSetState(QROS_MOD_DIV3,QROS_STATE_OFF);
     }
   MqlTick tick;if(SymbolInfoTick(_Symbol,tick) && tick.ask>tick.bid)
     {
      HandleDayBoundary(tick.time_msc);
      for(int p=0;p<PROFILE_COUNT;p++) if(g_ps[p].active && g_ps[p].last_valid_ms>=0) FinalizeTrade(p,g_ps[p].last_valid_ms,g_ps[p].last_valid_side_u,3);
     }
   if(g_fsummary!=INVALID_HANDLE)
     {
      FileWrite(g_fsummary,"profile_id","mask_sha256","config_id","raw_signals","trades","overlap_skips","dailycap_skips");
      for(int p=0;p<PROFILE_COUNT;p++) FileWrite(g_fsummary,p,g_mask[p],g_cfg[p],g_signal_count[p],g_ps[p].trades,g_ps[p].overlap_skips,g_ps[p].dailycap_skips);
     }
   if(g_fenv!=INVALID_HANDLE)
     {
      FileWrite(g_fenv,"ticks_total",g_ticks_total);
      FileWrite(g_fenv,"ticks_executable",g_ticks_exec);
      FileWrite(g_fenv,"ticks_zero_spread",g_ticks_zero);
      FileWrite(g_fenv,"ticks_crossed_spread",g_ticks_crossed);
      FileWrite(g_fenv,"ticks_nonpositive_quote",g_ticks_nonpositive);
     }
   if(g_fbars!=INVALID_HANDLE)FileClose(g_fbars);if(g_fsignals!=INVALID_HANDLE)FileClose(g_fsignals);if(g_ftrades!=INVALID_HANDLE)FileClose(g_ftrades);if(g_fsummary!=INVALID_HANDLE)FileClose(g_fsummary);if(g_fenv!=INVALID_HANDLE)FileClose(g_fenv);
  }
