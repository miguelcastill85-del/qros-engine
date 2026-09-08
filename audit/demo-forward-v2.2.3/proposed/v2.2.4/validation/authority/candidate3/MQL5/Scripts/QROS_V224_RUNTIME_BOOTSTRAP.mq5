//+------------------------------------------------------------------+
//| QROS_V224_RUNTIME_BOOTSTRAP.mq5                                  |
//| Runtime certification for v2.2.4 safety candidate.               |
//| No order API.                                                     |
//+------------------------------------------------------------------+
#property strict
#property script_show_inputs

#include <QROS_DEMO_BUS_v2_2_4.mqh>

input int    InpMaxWaitSeconds=1800;
input int    InpHeartbeatMaxAgeMs=5000;
input int    InpFreshTickMaxAgeSec=60;
input int    InpExpectedArmed=0;
input int    InpRequiredBuild=6182;
input long   InpExpectedManifestToken=224223002;
input string InpResultFile="QROS_V224_RUNTIME.csv";
input string InpCertReceiptFile="QROS_V224_CERT_RECEIPT.csv";
input bool   InpAllowChartProvision=false; // default: audit existing V224 charts only; never close unrelated charts

const long QROS_EXEC_SOURCE_TOKEN=224201;
const long QROS_XAU_SOURCE_TOKEN=224101;
const long QROS_NQX_SOURCE_TOKEN=224102;
const long QROS_DIV3_SOURCE_TOKEN=224103;
const long QROS_EXACT_DOUBLE_MAX=9007199254740991LL;

long ExpectedModuleSource(const int module_id)
  {
   if(module_id==QROS_MOD_XAU) return QROS_XAU_SOURCE_TOKEN;
   if(module_id==QROS_MOD_NQX) return QROS_NQX_SOURCE_TOKEN;
   if(module_id==QROS_MOD_DIV3) return QROS_DIV3_SOURCE_TOKEN;
   return 0;
  }

long ExecAge()
  {
   string key="Q24.EXEC.HB";
   if(!GlobalVariableCheck(key)) return LONG_MAX;
   long then=(long)GlobalVariableGet(key);
   long now=(long)GetTickCount64();
   if(then<0 || now<then) return LONG_MAX;
   return now-then;
  }

bool DemoGate(string &reason)
  {
   if((ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO)
     {reason="ACCOUNT_NOT_DEMO";return false;}
   if(AccountInfoString(ACCOUNT_SERVER)!="Darwinex-Demo")
     {reason="WRONG_SERVER";return false;}
   if(AccountInfoString(ACCOUNT_CURRENCY)!="USD")
     {reason="WRONG_CURRENCY";return false;}
   return true;
  }

string ExpertName(const long chart_id)
  {
   if(chart_id<=0) return "";
   return ChartGetString(chart_id,CHART_EXPERT_NAME);
  }

int CountQrosPositions()
  {
   int count=0;
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      long magic=(long)PositionGetInteger(POSITION_MAGIC);
      if(magic==560101 || magic==560217 || magic==560231 || magic==560300) count++;
     }
   return count;
  }

int CountQrosOrders()
  {
   int count=0;
   for(int i=OrdersTotal()-1;i>=0;i--)
     {
      ulong ticket=OrderGetTicket(i);if(ticket==0) continue;
      long magic=(long)OrderGetInteger(ORDER_MAGIC);
      if(magic==560101 || magic==560217 || magic==560231 || magic==560300) count++;
     }
   return count;
  }

bool TickState(const string symbol,const long utc_offset_sec,double &bid,double &ask,long &age_sec,long &tick_msc)
  {
   MqlTick tick;bid=0.0;ask=0.0;age_sec=LONG_MAX;tick_msc=0;
   if(!SymbolInfoTick(symbol,tick)) return false;
   bid=tick.bid;ask=tick.ask;tick_msc=tick.time_msc;
   long expected_server=(long)TimeGMT()+utc_offset_sec;
   age_sec=expected_server-(long)tick.time;
   return (tick.bid>0.0 && tick.ask>tick.bid && age_sec>=-5 && age_sec<=InpFreshTickMaxAgeSec);
  }

bool SeriesCurrent(const string symbol,const ENUM_TIMEFRAMES timeframe,const long utc_offset_sec,const long max_age_sec,long &last_bar,long &sync_flag)
  {
   last_bar=(long)iTime(symbol,timeframe,0);
   sync_flag=(long)SeriesInfoInteger(symbol,timeframe,SERIES_SYNCHRONIZED);
   if(last_bar<=0 || sync_flag!=1) return false;
   long server_now=(long)TimeGMT()+utc_offset_sec;
   long age=server_now-last_bar;
   return (age>=-5 && age<=max_age_sec);
  }

long FindChartByExpert(const string expected)
  {
   long chart=ChartFirst();
   while(chart>=0)
     {
      if(ExpertName(chart)==expected) return chart;
      chart=ChartNext(chart);
     }
   return 0;
  }

long ProvisionOrFindChart(const string symbol,const ENUM_TIMEFRAMES tf,const string template_name,const string expected)
  {
   long chart=FindChartByExpert(expected);
   if(chart>0) return chart;
   if(!InpAllowChartProvision) return 0;
   chart=ChartOpen(symbol,tf);
   if(chart<=0) return 0;
   Sleep(500);
   if(!ChartApplyTemplate(chart,template_name))
     {
      ChartClose(chart);
      return 0;
     }
   return chart;
  }

bool GvExactLong(const string key,long &out)
  {
   out=0;
   if(!GlobalVariableCheck(key)) return false;
   double v=GlobalVariableGet(key);
   if(!MathIsValidNumber(v) || v<0.0 || v>(double)QROS_EXACT_DOUBLE_MAX || v!=MathFloor(v)) return false;
   out=(long)v;return true;
  }

long GvLong(const string key,const long fallback=-1)
  {
   long v=0;return (GvExactLong(key,v)?v:fallback);
  }

double GvDouble(const string key,const double fallback=-1.0)
  {
   if(!GlobalVariableCheck(key)) return fallback;
   return GlobalVariableGet(key);
  }

bool WriteState(const string decision,const string reason,const long cx,const long cn,const long cd,
                const long exec_age,const long xau_age,const long nqx_age,const long div3_age,
                const long utc_offset,const int offset_stable,const int armed,
                const double xau_bid,const double xau_ask,const long xau_tick_age,
                const double ndx_bid,const double ndx_ask,const long ndx_tick_age,
                const long xau_m1_last,const long ndx_m15_last,const long ndx_h1_last,
                const long xau_m1_sync,const long ndx_m15_sync,const long ndx_h1_sync)
  {
   int file=FileOpen(InpResultFile,FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ|FILE_SHARE_WRITE,',');
   if(file==INVALID_HANDLE) return false;
   uint w=FileWrite(file,
      "decision","reason","server","company","currency","trade_mode","login","server_time","gmt_time",
      "utc_offset_sec","offset_stable","expected_armed","executor_armed","cert","health","entry_fault","bus_fault","mgmt_fault","recovery",
      "instance","source_token","qros_positions","qros_orders",
      "xau_expert","nqx_expert","div3_expert","xau_owner","nqx_owner","div3_owner","xau_epoch","nqx_epoch","div3_epoch",
      "xau_state","nqx_state","div3_state","exec_hb_age","xau_hb_age","nqx_hb_age","div3_hb_age",
      "xau_bid","xau_ask","xau_tick_age","ndx_bid","ndx_ask","ndx_tick_age",
      "xau_m1_lastbar","ndx_m15_lastbar","ndx_h1_lastbar","xau_m1_sync_flag","ndx_m15_sync_flag","ndx_h1_sync_flag",
      "build","connected","trade_allowed");
   if(w==0){FileClose(file);return false;}
   w=FileWrite(file,
      decision,reason,AccountInfoString(ACCOUNT_SERVER),AccountInfoString(ACCOUNT_COMPANY),AccountInfoString(ACCOUNT_CURRENCY),
      (long)AccountInfoInteger(ACCOUNT_TRADE_MODE),(long)AccountInfoInteger(ACCOUNT_LOGIN),
      TimeToString(TimeTradeServer(),TIME_DATE|TIME_SECONDS),TimeToString(TimeGMT(),TIME_DATE|TIME_SECONDS),
      utc_offset,offset_stable,InpExpectedArmed,GvLong("Q24.EXEC.ARMED"),GvDouble("Q24.EXEC.CERT"),GvDouble("Q24.EXEC.HEALTH"),
      GvDouble("Q24.EXEC.ENTRYFAULT"),GvDouble("Q24.EXEC.BUSFAULT"),GvDouble("Q24.EXEC.MGMTFAULT"),GvDouble("Q24.EXEC.RECOVERY"),
      GvLong("Q24.EXEC.INSTANCE"),GvLong("Q24.EXEC.SOURCE_TOKEN"),CountQrosPositions(),CountQrosOrders(),
      ExpertName(cx),ExpertName(cn),ExpertName(cd),QrosBusProducerOwner(QROS_MOD_XAU),QrosBusProducerOwner(QROS_MOD_NQX),QrosBusProducerOwner(QROS_MOD_DIV3),
      QrosBusProducerEpoch(QROS_MOD_XAU),QrosBusProducerEpoch(QROS_MOD_NQX),QrosBusProducerEpoch(QROS_MOD_DIV3),
      QrosBusState(QROS_MOD_XAU),QrosBusState(QROS_MOD_NQX),QrosBusState(QROS_MOD_DIV3),
      exec_age,xau_age,nqx_age,div3_age,xau_bid,xau_ask,xau_tick_age,ndx_bid,ndx_ask,ndx_tick_age,
      TimeToString((datetime)xau_m1_last,TIME_DATE|TIME_MINUTES),TimeToString((datetime)ndx_m15_last,TIME_DATE|TIME_MINUTES),TimeToString((datetime)ndx_h1_last,TIME_DATE|TIME_MINUTES),
      xau_m1_sync,ndx_m15_sync,ndx_h1_sync,(long)TerminalInfoInteger(TERMINAL_BUILD),(long)TerminalInfoInteger(TERMINAL_CONNECTED),(long)TerminalInfoInteger(TERMINAL_TRADE_ALLOWED));
   FileFlush(file);FileClose(file);return (w>0);
  }

string CertReceiptPath(const long instance)
  {
   string base=InpCertReceiptFile;
   int dot=StringFind(base,".csv");
   if(dot>=0) base=StringSubstr(base,0,dot);
   return base+"_I"+IntegerToString(instance)+".csv";
  }

bool WriteCertReceipt(const long utc_offset,const long instance,string &path)
  {
   path=CertReceiptPath(instance);
   int file=FileOpen(path,FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,',');
   if(file==INVALID_HANDLE) return false;
   uint w=FileWrite(file,"decision","server","login","build","offset","instance","manifest_token","source_token","utc");
   if(w==0){FileClose(file);return false;}
   w=FileWrite(file,"PASS_PRE_CERT",AccountInfoString(ACCOUNT_SERVER),(long)AccountInfoInteger(ACCOUNT_LOGIN),(long)TerminalInfoInteger(TERMINAL_BUILD),utc_offset,instance,InpExpectedManifestToken,GvLong("Q24.EXEC.SOURCE_TOKEN"),TimeToString(TimeGMT(),TIME_DATE|TIME_SECONDS));
   FileFlush(file);FileClose(file);if(w==0) return false;

   // Reopen and verify the exact binding row before CERT can latch.
   file=FileOpen(path,FILE_READ|FILE_CSV|FILE_ANSI|FILE_COMMON,',');
   if(file==INVALID_HANDLE) return false;
   for(int i=0;i<9;i++) FileReadString(file);
   string decision=FileReadString(file);
   string server=FileReadString(file);
   long login=(long)StringToInteger(FileReadString(file));
   long build=(long)StringToInteger(FileReadString(file));
   long off=(long)StringToInteger(FileReadString(file));
   long inst=(long)StringToInteger(FileReadString(file));
   long manifest=(long)StringToInteger(FileReadString(file));
   long source=(long)StringToInteger(FileReadString(file));
   string utc=FileReadString(file);
   FileClose(file);
   return (decision=="PASS_PRE_CERT" && server==AccountInfoString(ACCOUNT_SERVER) &&
           login==(long)AccountInfoInteger(ACCOUNT_LOGIN) && build==InpRequiredBuild && off==utc_offset &&
           inst==instance && manifest==InpExpectedManifestToken && source==QROS_EXEC_SOURCE_TOKEN && utc!="");
  }

bool CertSetLong(const string key,const long value)
  {
   if(value<0 || value>QROS_EXACT_DOUBLE_MAX) return false;
   return QrosGvSetChecked(key,(double)value);
  }

void WriteEarlyFail(const string reason)
  {
   WriteState("FAIL",reason,0,0,0,LONG_MAX,LONG_MAX,LONG_MAX,LONG_MAX,0,0,-1,0,0,LONG_MAX,0,0,LONG_MAX,0,0,0,0,0,0);
  }

string RuntimeFailure(const long cx,const long cn,const long cd,const long exec_age,const long xau_age,const long nqx_age,const long div3_age,
                      const bool xau_tick_ok,const bool ndx_tick_ok,const bool xau_m1_ok,const bool ndx_m15_ok,const bool ndx_h1_ok,
                      const int offset_stable,const long offset,const int armed)
  {
   if((long)TerminalInfoInteger(TERMINAL_BUILD)!=InpRequiredBuild) return "BUILD_MISMATCH";
   if(ExpertName(cx)!="QROS_XAU_M1_DEMO_EMITTER_v2_2_4") return "XAU_ID";
   if(ExpertName(cn)!="QROS_NQX_17_31_DEMO_EMITTER_v2_2_4") return "NQX_ID";
   if(ExpertName(cd)!="QROS_DIV3_R3_DEMO_EMITTER_v2_2_4") return "DIV3_ID";
   if(QrosBusProducerOwner(QROS_MOD_XAU)<=0 || QrosBusProducerEpoch(QROS_MOD_XAU)<=0) return "XAU_FENCE";
   if(QrosBusProducerOwner(QROS_MOD_NQX)<=0 || QrosBusProducerEpoch(QROS_MOD_NQX)<=0) return "NQX_FENCE";
   if(QrosBusProducerOwner(QROS_MOD_DIV3)<=0 || QrosBusProducerEpoch(QROS_MOD_DIV3)<=0) return "DIV3_FENCE";
   if(QrosBusState(QROS_MOD_XAU)!=QROS_STATE_READY) return "XAU_STATE";
   if(QrosBusState(QROS_MOD_NQX)!=QROS_STATE_READY) return "NQX_STATE";
   if(QrosBusState(QROS_MOD_DIV3)!=QROS_STATE_READY) return "DIV3_STATE";
   if(exec_age>InpHeartbeatMaxAgeMs) return "EXEC_HB";
   if(xau_age>InpHeartbeatMaxAgeMs) return "XAU_HB";
   if(nqx_age>InpHeartbeatMaxAgeMs) return "NQX_HB";
   if(div3_age>InpHeartbeatMaxAgeMs) return "DIV3_HB";
   if(offset_stable<10) return "OFFSET_UNSTABLE";
   if(offset!=7200 && offset!=10800) return "OFFSET_OUTSIDE_CONTRACT";
   if(!xau_tick_ok) return "XAU_FRESH_TICK";
   if(!ndx_tick_ok) return "NDX_FRESH_TICK";
   if(!xau_m1_ok) return "XAU_M1_NOT_CURRENT";
   if(!ndx_m15_ok) return "NDX_M15_NOT_CURRENT";
   if(!ndx_h1_ok) return "NDX_H1_NOT_CURRENT";
   if(armed!=InpExpectedArmed) return "ARM_STATE";
   if(GvLong("Q24.EXEC.SOURCE_TOKEN")!=QROS_EXEC_SOURCE_TOKEN) return "EXECUTOR_SOURCE_TOKEN";
   for(int m=1;m<=3;m++) if(GvLong(QrosBusKey(m,"SOURCE_TOKEN"))!=ExpectedModuleSource(m)) return "MODULE_SOURCE_TOKEN_M"+IntegerToString(m);
   if(GvLong("Q24.EXEC.INSTANCE")<=0) return "EXECUTOR_INSTANCE";
   if(GvDouble("Q24.EXEC.ENTRYFAULT")!=0.0) return "ENTRY_FAULT";
   if(GvDouble("Q24.EXEC.BUSFAULT")!=0.0) return "BUS_FAULT";
   if(GvDouble("Q24.EXEC.MGMTFAULT")!=0.0) return "MGMT_FAULT";
   if(GvDouble("Q24.EXEC.RECOVERY")!=0.0) return "RECOVERY_LOCK";
   if(GvDouble("Q24.EXEC.RECERT")!=0.0) return "RECERT_REQUIRED";
   if(GvDouble("Q24.EXEC.HEALTH")!=1.0) return "EXECUTOR_HEALTH";
   if(!TerminalInfoInteger(TERMINAL_CONNECTED)) return "TERMINAL_DISCONNECTED";
   if(InpExpectedArmed==1 && !TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)) return "TRADE_NOT_ALLOWED";
   if(CountQrosPositions()!=0) return "QROS_POSITION_PRESENT";
   if(CountQrosOrders()!=0) return "QROS_ORDER_PRESENT";
   return "RUNTIME_READY";
  }

void OnStart()
  {
   GlobalVariableSet("Q24.EXEC.CERT",0.0);
   string why="";if(!DemoGate(why)){WriteEarlyFail(why);return;}
   if((long)TerminalInfoInteger(TERMINAL_BUILD)!=InpRequiredBuild){WriteEarlyFail("BUILD_MISMATCH");return;}
   if(CountQrosPositions()!=0 || CountQrosOrders()!=0){WriteEarlyFail("QROS_INVENTORY_BEFORE_FRESH_CERT");return;}

   if(!SymbolSelect("XAUUSD",true) || !SymbolSelect("NDX",true)){WriteEarlyFail("SYMBOL_SELECT");return;}
   if(InpAllowChartProvision)
     {
      // V224 namespace only. Never clear or mutate legacy v2.2.3 globals/charts.
      QrosBusClearRuntime(QROS_MOD_XAU);QrosBusClearRuntime(QROS_MOD_NQX);QrosBusClearRuntime(QROS_MOD_DIV3);
     }

   long cx=ProvisionOrFindChart("XAUUSD",PERIOD_M1,"QROS_V224_XAU_NATIVE","QROS_XAU_M1_DEMO_EMITTER_v2_2_4");
   long cn=ProvisionOrFindChart("NDX",PERIOD_M15,"QROS_V224_NQX_NATIVE","QROS_NQX_17_31_DEMO_EMITTER_v2_2_4");
   long cd=ProvisionOrFindChart("NDX",PERIOD_M15,"QROS_V224_DIV3_NATIVE","QROS_DIV3_R3_DEMO_EMITTER_v2_2_4");
   if(cx==0 || cn==0 || cd==0)
     {WriteEarlyFail(InpAllowChartProvision?"V224_CHART_PROVISION_FAILED":"V224_CHARTS_NOT_PREPROVISIONED");return;}
   Sleep(1200);

   long deadline=(long)GetTickCount64()+((long)InpMaxWaitSeconds*1000L);
   long last_offset=0;bool have_offset=false;int offset_stable=0;long last_report=0;
   while((long)GetTickCount64()<deadline && !IsStopped())
     {
      long raw=(long)(TimeTradeServer()-TimeGMT());
      long rounded=(long)MathRound((double)raw/3600.0)*3600L;
      if(MathAbs((double)(raw-rounded))<=10.0)
        {
         if(have_offset && rounded==last_offset) offset_stable++;
         else {last_offset=rounded;have_offset=true;offset_stable=1;}
        }
      else offset_stable=0;

      long ea=ExecAge();long xa=QrosBusHeartbeatAgeMs(QROS_MOD_XAU);long na=QrosBusHeartbeatAgeMs(QROS_MOD_NQX);long da=QrosBusHeartbeatAgeMs(QROS_MOD_DIV3);
      int armed=(int)GvLong("Q24.EXEC.ARMED",-1);
      double xb=0,xaask=0,nb=0,naask=0;long xage=LONG_MAX,nage=LONG_MAX,xmsc=0,nmsc=0;
      bool xt=TickState("XAUUSD",last_offset,xb,xaask,xage,xmsc);bool nt=TickState("NDX",last_offset,nb,naask,nage,nmsc);
      long xm1=0,nm15=0,nh1=0,xs=0,m15s=0,h1s=0;
      bool xok=SeriesCurrent("XAUUSD",PERIOD_M1,last_offset,180,xm1,xs);
      bool m15ok=SeriesCurrent("NDX",PERIOD_M15,last_offset,1800,nm15,m15s);
      bool h1ok=SeriesCurrent("NDX",PERIOD_H1,last_offset,7200,nh1,h1s);

      string fail=RuntimeFailure(cx,cn,cd,ea,xa,na,da,xt,nt,xok,m15ok,h1ok,offset_stable,last_offset,armed);
      if(fail=="RUNTIME_READY")
        {
         if(InpExpectedArmed==1)
           {
            long inst=GvLong("Q24.EXEC.INSTANCE",0);
            if(inst<=0){WriteEarlyFail("INSTANCE_MISSING_BEFORE_CERT");return;}
            string receipt="";
            // Durable, reopened receipt first. CERT latch is impossible if this proof fails.
            if(!WriteCertReceipt(last_offset,inst,receipt)){WriteEarlyFail("CERT_RECEIPT_WRITE_OR_VERIFY_FAILED");return;}
            bool bind=true;
            bind=bind && CertSetLong("Q24.EXEC.CERT_INSTANCE",inst);
            bind=bind && CertSetLong("Q24.EXEC.CERT_BUILD",InpRequiredBuild);
            bind=bind && CertSetLong("Q24.EXEC.CERT_LOGIN",(long)AccountInfoInteger(ACCOUNT_LOGIN));
            bind=bind && CertSetLong("Q24.EXEC.CERT_OFFSET",last_offset);
            bind=bind && CertSetLong("Q24.EXEC.CERT_MANIFEST",InpExpectedManifestToken);
            bind=bind && CertSetLong("Q24.EXEC.CERT_EXEC_SOURCE",QROS_EXEC_SOURCE_TOKEN);
            for(int m=1;m<=3 && bind;m++)
              {
               long owner=QrosBusProducerOwner(m),epoch=QrosBusProducerEpoch(m),src=GvLong(QrosBusKey(m,"SOURCE_TOKEN"),0);
               bind=bind && owner>0 && epoch>0 && src==ExpectedModuleSource(m);
               bind=bind && CertSetLong("Q24.EXEC.CERT_M"+IntegerToString(m)+"_OWNER",owner);
               bind=bind && CertSetLong("Q24.EXEC.CERT_M"+IntegerToString(m)+"_EPOCH",epoch);
               bind=bind && CertSetLong("Q24.EXEC.CERT_M"+IntegerToString(m)+"_SOURCE",src);
              }
            bind=bind && CertSetLong("Q24.EXEC.CERT_RECEIPT_INSTANCE",inst);
            GlobalVariablesFlush();
            if(!bind){WriteEarlyFail("CERT_BINDING_WRITE_FAILED");return;}
            if(!QrosGvSetChecked("Q24.EXEC.CERT",1.0)){WriteEarlyFail("CERT_LATCH_WRITE_FAILED");return;}
            GlobalVariablesFlush();
            Sleep(250);
           }
         if(!WriteState("PASS","RUNTIME_READY",cx,cn,cd,ea,xa,na,da,last_offset,offset_stable,armed,xb,xaask,xage,nb,naask,nage,xm1,nm15,nh1,xs,m15s,h1s))
           {GlobalVariableSet("Q24.EXEC.CERT",0.0);return;}
         return;
        }

      long up=(long)GetTickCount64();
      if(up-last_report>=5000)
        {
         WriteState("WAITING",fail,cx,cn,cd,ea,xa,na,da,last_offset,offset_stable,armed,xb,xaask,xage,nb,naask,nage,xm1,nm15,nh1,xs,m15s,h1s);
         last_report=up;
        }
      Sleep(500);
     }

   GlobalVariableSet("Q24.EXEC.CERT",0.0);
   WriteState("FAIL","RUNTIME_TIMEOUT",cx,cn,cd,ExecAge(),QrosBusHeartbeatAgeMs(QROS_MOD_XAU),QrosBusHeartbeatAgeMs(QROS_MOD_NQX),QrosBusHeartbeatAgeMs(QROS_MOD_DIV3),last_offset,offset_stable,(int)GvLong("Q24.EXEC.ARMED",-1),0,0,LONG_MAX,0,0,LONG_MAX,0,0,0,0,0,0);
  }
