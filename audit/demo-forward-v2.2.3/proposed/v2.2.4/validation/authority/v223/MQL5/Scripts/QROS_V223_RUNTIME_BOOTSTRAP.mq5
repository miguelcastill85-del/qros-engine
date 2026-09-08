//+------------------------------------------------------------------+
//| QROS_V223_RUNTIME_BOOTSTRAP.mq5                                  |
//| Runtime certification only. No order API.                         |
//+------------------------------------------------------------------+
#property strict
#property script_show_inputs

#include <QROS_DEMO_BUS_v2.mqh>

input int    InpMaxWaitSeconds=21600;
input int    InpHeartbeatMaxAgeMs=5000;
input int    InpFreshTickMaxAgeSec=60;
input int    InpExpectedArmed=0;
input string InpResultFile="QROS_V223_RUNTIME.csv";

long ExecAge()
  {
   string key="QDB1.EXEC.HB";
   if(!GlobalVariableCheck(key))
      return LONG_MAX;

   long then=(long)GlobalVariableGet(key);
   long now=(long)GetTickCount64();

   if(then<0 || now<then)
      return LONG_MAX;

   return now-then;
  }

bool DemoGate(string &reason)
  {
   if((ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO)
     {
      reason="ACCOUNT_NOT_DEMO";
      return false;
     }

   if(AccountInfoString(ACCOUNT_SERVER)!="Darwinex-Demo")
     {
      reason="WRONG_SERVER";
      return false;
     }

   if(AccountInfoString(ACCOUNT_CURRENCY)!="USD")
     {
      reason="WRONG_CURRENCY";
      return false;
     }

   return true;
  }

string ExpertName(const long chart_id)
  {
   if(chart_id<=0)
      return "";
   return ChartGetString(chart_id,CHART_EXPERT_NAME);
  }

int CountQrosPositions()
  {
   int count=0;

   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket))
         continue;

      long magic=(long)PositionGetInteger(POSITION_MAGIC);
      if(magic==560101 || magic==560217 || magic==560231 || magic==560300)
         count++;
     }

   return count;
  }

bool TickState(const string symbol,
               const long utc_offset_sec,
               double &bid,
               double &ask,
               long &age_sec,
               long &tick_msc)
  {
   MqlTick tick;
   bid=0.0;
   ask=0.0;
   age_sec=LONG_MAX;
   tick_msc=0;

   if(!SymbolInfoTick(symbol,tick))
      return false;

   bid=tick.bid;
   ask=tick.ask;
   tick_msc=tick.time_msc;

   long expected_server=(long)TimeGMT()+utc_offset_sec;
   age_sec=expected_server-(long)tick.time;

   return (tick.bid>0.0 &&
           tick.ask>tick.bid &&
           age_sec>=-5 &&
           age_sec<=InpFreshTickMaxAgeSec);
  }

bool SeriesCurrent(const string symbol,
                   const ENUM_TIMEFRAMES timeframe,
                   const long utc_offset_sec,
                   const long max_age_sec,
                   long &last_bar,
                   long &sync_flag)
  {
   last_bar=(long)iTime(symbol,timeframe,0);
   sync_flag=(long)SeriesInfoInteger(symbol,timeframe,SERIES_SYNCHRONIZED);

   if(last_bar<=0 || sync_flag!=1)
      return false;

   long server_now=(long)TimeGMT()+utc_offset_sec;
   long age=server_now-last_bar;

   return (age>=-5 && age<=max_age_sec);
  }

void CloseOtherCharts()
  {
   long me=ChartID();
   long chart=ChartFirst();

   while(chart>=0)
     {
      long next=ChartNext(chart);
      if(chart!=me)
         ChartClose(chart);
      chart=next;
     }
  }

void WriteState(const string decision,
                const string reason,
                const long cx,
                const long cn,
                const long cd,
                const long exec_age,
                const long xau_age,
                const long nqx_age,
                const long div3_age,
                const long utc_offset,
                const int offset_stable,
                const int armed,
                const double xau_bid,
                const double xau_ask,
                const long xau_tick_age,
                const double ndx_bid,
                const double ndx_ask,
                const long ndx_tick_age,
                const long xau_m1_last,
                const long ndx_m15_last,
                const long ndx_h1_last,
                const long xau_m1_sync,
                const long ndx_m15_sync,
                const long ndx_h1_sync)
  {
   int file=FileOpen(InpResultFile,
                     FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ|FILE_SHARE_WRITE,
                     ',');

   if(file==INVALID_HANDLE)
      return;

   int cert=-1;
   if(GlobalVariableCheck("QDB1.EXEC.CERT"))
      cert=(int)GlobalVariableGet("QDB1.EXEC.CERT");

   FileWrite(file,
             "decision","reason",
             "server","company","currency","trade_mode","login",
             "server_time","gmt_time",
             "utc_offset_sec","offset_stable",
             "expected_armed","executor_armed","cert","qros_positions",
             "xau_expert","nqx_expert","div3_expert",
             "xau_state","nqx_state","div3_state",
             "exec_hb_age","xau_hb_age","nqx_hb_age","div3_hb_age",
             "xau_bid","xau_ask","xau_tick_age",
             "ndx_bid","ndx_ask","ndx_tick_age",
             "xau_m1_lastbar","ndx_m15_lastbar","ndx_h1_lastbar",
             "xau_m1_sync_flag","ndx_m15_sync_flag","ndx_h1_sync_flag",
             "build","connected","trade_allowed");

   FileWrite(file,
             decision,reason,
             AccountInfoString(ACCOUNT_SERVER),
             AccountInfoString(ACCOUNT_COMPANY),
             AccountInfoString(ACCOUNT_CURRENCY),
             (long)AccountInfoInteger(ACCOUNT_TRADE_MODE),
             (long)AccountInfoInteger(ACCOUNT_LOGIN),
             TimeToString(TimeTradeServer(),TIME_DATE|TIME_SECONDS),
             TimeToString(TimeGMT(),TIME_DATE|TIME_SECONDS),
             utc_offset,offset_stable,
             InpExpectedArmed,armed,cert,CountQrosPositions(),
             ExpertName(cx),ExpertName(cn),ExpertName(cd),
             QrosBusState(QROS_MOD_XAU),
             QrosBusState(QROS_MOD_NQX),
             QrosBusState(QROS_MOD_DIV3),
             exec_age,xau_age,nqx_age,div3_age,
             xau_bid,xau_ask,xau_tick_age,
             ndx_bid,ndx_ask,ndx_tick_age,
             TimeToString((datetime)xau_m1_last,TIME_DATE|TIME_MINUTES),
             TimeToString((datetime)ndx_m15_last,TIME_DATE|TIME_MINUTES),
             TimeToString((datetime)ndx_h1_last,TIME_DATE|TIME_MINUTES),
             xau_m1_sync,ndx_m15_sync,ndx_h1_sync,
             (long)TerminalInfoInteger(TERMINAL_BUILD),
             (long)TerminalInfoInteger(TERMINAL_CONNECTED),
             (long)TerminalInfoInteger(TERMINAL_TRADE_ALLOWED));

   FileFlush(file);
   FileClose(file);
  }

void WriteEarlyFail(const string reason)
  {
   WriteState("FAIL",reason,
              0,0,0,
              LONG_MAX,LONG_MAX,LONG_MAX,LONG_MAX,
              0,0,-1,
              0.0,0.0,LONG_MAX,
              0.0,0.0,LONG_MAX,
              0,0,0,
              0,0,0);
  }

string RuntimeFailure(const long cx,
                      const long cn,
                      const long cd,
                      const long exec_age,
                      const long xau_age,
                      const long nqx_age,
                      const long div3_age,
                      const bool xau_tick_ok,
                      const bool ndx_tick_ok,
                      const bool xau_m1_ok,
                      const bool ndx_m15_ok,
                      const bool ndx_h1_ok,
                      const int offset_stable,
                      const int armed)
  {
   if(ExpertName(cx)!="QROS_XAU_M1_DEMO_EMITTER_v2")
      return "XAU_ID";

   if(ExpertName(cn)!="QROS_NQX_17_31_DEMO_EMITTER_v2")
      return "NQX_ID";

   if(ExpertName(cd)!="QROS_DIV3_R3_DEMO_EMITTER_v2_1")
      return "DIV3_ID";

   if(QrosBusState(QROS_MOD_XAU)!=QROS_STATE_READY)
      return "XAU_STATE";

   if(QrosBusState(QROS_MOD_NQX)!=QROS_STATE_READY)
      return "NQX_STATE";

   if(QrosBusState(QROS_MOD_DIV3)!=QROS_STATE_READY)
      return "DIV3_STATE";

   if(exec_age>InpHeartbeatMaxAgeMs)
      return "EXEC_HB";

   if(xau_age>InpHeartbeatMaxAgeMs)
      return "XAU_HB";

   if(nqx_age>InpHeartbeatMaxAgeMs)
      return "NQX_HB";

   if(div3_age>InpHeartbeatMaxAgeMs)
      return "DIV3_HB";

   if(offset_stable<10)
      return "OFFSET";

   if(!xau_tick_ok)
      return "XAU_FRESH_TICK";

   if(!ndx_tick_ok)
      return "NDX_FRESH_TICK";

   if(!xau_m1_ok)
      return "XAU_M1_NOT_CURRENT";

   if(!ndx_m15_ok)
      return "NDX_M15_NOT_CURRENT";

   if(!ndx_h1_ok)
      return "NDX_H1_NOT_CURRENT";

   if(armed!=InpExpectedArmed)
      return "ARM_STATE";

   if(CountQrosPositions()!=0)
      return "QROS_POSITION_PRESENT";

   return "RUNTIME_READY";
  }

void OnStart()
  {
   GlobalVariableSet("QDB1.EXEC.CERT",0.0);

   string why="";
   if(!DemoGate(why))
     {
      WriteEarlyFail(why);
      return;
     }

   if(CountQrosPositions()!=0)
     {
      WriteEarlyFail("OPEN_QROS_POSITION_BEFORE_CERT");
      return;
     }

   CloseOtherCharts();

   QrosBusClearRuntime(QROS_MOD_XAU);
   QrosBusClearRuntime(QROS_MOD_NQX);
   QrosBusClearRuntime(QROS_MOD_DIV3);

   if(!SymbolSelect("XAUUSD",true) || !SymbolSelect("NDX",true))
     {
      WriteEarlyFail("SYMBOL_SELECT");
      return;
     }

   long cx=ChartOpen("XAUUSD",PERIOD_M1);
   long cn=ChartOpen("NDX",PERIOD_M15);
   long cd=ChartOpen("NDX",PERIOD_M15);

   if(cx==0 || cn==0 || cd==0)
     {
      WriteEarlyFail("CHART_OPEN");
      return;
     }

   Sleep(1200);

   bool template_x=ChartApplyTemplate(cx,"QROS_V2_XAU_NATIVE");
   bool template_n=ChartApplyTemplate(cn,"QROS_V2_NQX_NATIVE");
   bool template_d=ChartApplyTemplate(cd,"QROS_V2_DIV3_NATIVE");

   if(!template_x || !template_n || !template_d)
     {
      WriteEarlyFail("TEMPLATE_APPLY");
      return;
     }

   long deadline=(long)GetTickCount64()+((long)InpMaxWaitSeconds*1000L);
   long last_offset=0;
   bool have_offset=false;
   int offset_stable=0;
   long last_report=0;

   while((long)GetTickCount64()<deadline && !IsStopped())
     {
      long raw_offset=(long)(TimeTradeServer()-TimeGMT());
      long rounded_offset=(long)MathRound((double)raw_offset/3600.0)*3600L;

      if(MathAbs((double)(raw_offset-rounded_offset))<=10.0)
        {
         if(have_offset && rounded_offset==last_offset)
            offset_stable++;
         else
           {
            last_offset=rounded_offset;
            have_offset=true;
            offset_stable=1;
           }
        }
      else
         offset_stable=0;

      long exec_age=ExecAge();
      long xau_age=QrosBusHeartbeatAgeMs(QROS_MOD_XAU);
      long nqx_age=QrosBusHeartbeatAgeMs(QROS_MOD_NQX);
      long div3_age=QrosBusHeartbeatAgeMs(QROS_MOD_DIV3);

      int armed=-1;
      if(GlobalVariableCheck("QDB1.EXEC.ARMED"))
         armed=(int)GlobalVariableGet("QDB1.EXEC.ARMED");

      double xau_bid=0.0;
      double xau_ask=0.0;
      double ndx_bid=0.0;
      double ndx_ask=0.0;

      long xau_tick_age=LONG_MAX;
      long ndx_tick_age=LONG_MAX;
      long xau_tick_msc=0;
      long ndx_tick_msc=0;

      bool xau_tick_ok=TickState("XAUUSD",last_offset,
                                 xau_bid,xau_ask,
                                 xau_tick_age,xau_tick_msc);

      bool ndx_tick_ok=TickState("NDX",last_offset,
                                 ndx_bid,ndx_ask,
                                 ndx_tick_age,ndx_tick_msc);

      long xau_m1_last=0;
      long ndx_m15_last=0;
      long ndx_h1_last=0;

      long xau_m1_sync=0;
      long ndx_m15_sync=0;
      long ndx_h1_sync=0;

      bool xau_m1_ok=SeriesCurrent("XAUUSD",PERIOD_M1,last_offset,180,
                                   xau_m1_last,xau_m1_sync);

      bool ndx_m15_ok=SeriesCurrent("NDX",PERIOD_M15,last_offset,1800,
                                    ndx_m15_last,ndx_m15_sync);

      bool ndx_h1_ok=SeriesCurrent("NDX",PERIOD_H1,last_offset,7200,
                                   ndx_h1_last,ndx_h1_sync);

      string failure=RuntimeFailure(cx,cn,cd,
                                    exec_age,xau_age,nqx_age,div3_age,
                                    xau_tick_ok,ndx_tick_ok,
                                    xau_m1_ok,ndx_m15_ok,ndx_h1_ok,
                                    offset_stable,armed);

      if(failure=="RUNTIME_READY")
        {
         if(InpExpectedArmed==1)
            GlobalVariableSet("QDB1.EXEC.CERT",1.0);

         WriteState("PASS","RUNTIME_READY",
                    cx,cn,cd,
                    exec_age,xau_age,nqx_age,div3_age,
                    last_offset,offset_stable,armed,
                    xau_bid,xau_ask,xau_tick_age,
                    ndx_bid,ndx_ask,ndx_tick_age,
                    xau_m1_last,ndx_m15_last,ndx_h1_last,
                    xau_m1_sync,ndx_m15_sync,ndx_h1_sync);
         return;
        }

      long now_uptime=(long)GetTickCount64();
      if(now_uptime-last_report>=5000)
        {
         WriteState("WAITING",failure,
                    cx,cn,cd,
                    exec_age,xau_age,nqx_age,div3_age,
                    last_offset,offset_stable,armed,
                    xau_bid,xau_ask,xau_tick_age,
                    ndx_bid,ndx_ask,ndx_tick_age,
                    xau_m1_last,ndx_m15_last,ndx_h1_last,
                    xau_m1_sync,ndx_m15_sync,ndx_h1_sync);
         last_report=now_uptime;
        }

      Sleep(500);
     }

   GlobalVariableSet("QDB1.EXEC.CERT",0.0);

   WriteState("FAIL","RUNTIME_TIMEOUT",
              cx,cn,cd,
              ExecAge(),
              QrosBusHeartbeatAgeMs(QROS_MOD_XAU),
              QrosBusHeartbeatAgeMs(QROS_MOD_NQX),
              QrosBusHeartbeatAgeMs(QROS_MOD_DIV3),
              last_offset,offset_stable,
              (GlobalVariableCheck("QDB1.EXEC.ARMED") ?
               (int)GlobalVariableGet("QDB1.EXEC.ARMED") : -1),
              0.0,0.0,LONG_MAX,
              0.0,0.0,LONG_MAX,
              0,0,0,
              0,0,0);
  }
