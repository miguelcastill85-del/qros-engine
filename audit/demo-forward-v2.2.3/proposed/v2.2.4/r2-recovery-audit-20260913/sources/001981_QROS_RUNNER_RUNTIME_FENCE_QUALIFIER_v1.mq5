//+------------------------------------------------------------------+
//| QROS_RUNNER_RUNTIME_FENCE_QUALIFIER_v1.mq5                      |
//| Actual terminal runtime qualifier. NO TRADE API.                 |
//+------------------------------------------------------------------+
#property strict
#property version "1.00"
#property description "QROS actual-terminal fence/restart qualifier. No trading."

input int    InpMode=1;
input string InpPrefix="QROS_R2T_UNSET";
input int    InpHoldMs=120000;
input long   InpExpectedToken=0;

int   g_lock=INVALID_HANDLE;
ulong g_hold_start=0;
long  g_token=0;

string LName(const string s){ return InpPrefix+"_"+s; }
string CName(const string s){ return InpPrefix+"_"+s; }

long MakeToken()
{
   long a=(long)(GetTickCount64()%1000000000ULL);
   long b=(long)(TimeLocal()%1000000000);
   long v=(a*1000003L+b)%9000000000000000L;
   if(v<=0) v=224000001;
   return v;
}

bool WriteLocalRow(const string file,const string test_id,const string status,const string detail,const long token=0,const int err=0)
{
   int f=FileOpen(file,FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(f==INVALID_HANDLE) return false;
   bool ok=(FileWrite(f,"test_id","status","detail","token","error","mql_tester","build","common_path","data_path","server")>0 &&
            FileWrite(f,test_id,status,detail,token,err,(int)MQLInfoInteger(MQL_TESTER),
                      (int)TerminalInfoInteger(TERMINAL_BUILD),
                      TerminalInfoString(TERMINAL_COMMONDATA_PATH),
                      TerminalInfoString(TERMINAL_DATA_PATH),
                      AccountInfoString(ACCOUNT_SERVER))>0);
   FileFlush(f); FileClose(f); return ok;
}

bool WriteCommonState(const string file,const long token)
{
   int f=FileOpen(file,FILE_COMMON|FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(f==INVALID_HANDLE) return false;
   bool ok=(FileWrite(f,"token","build")>0 && FileWrite(f,token,(int)TerminalInfoInteger(TERMINAL_BUILD))>0);
   FileFlush(f); FileClose(f); return ok;
}

bool ReadCommonState(const string file,long &token,long &build)
{
   token=0;build=0;
   int f=FileOpen(file,FILE_COMMON|FILE_READ|FILE_CSV|FILE_ANSI,',');
   if(f==INVALID_HANDLE) return false;
   string h1=FileReadString(f), h2=FileReadString(f);
   token=(long)FileReadNumber(f); build=(long)FileReadNumber(f);
   FileClose(f);
   return (h1=="token" && h2=="build" && token>0 && build>0);
}

bool AcquireFence()
{
   ResetLastError();
   g_lock=FileOpen(CName("FENCE.lock"),FILE_COMMON|FILE_READ|FILE_WRITE|FILE_BIN);
   if(g_lock==INVALID_HANDLE) return false;
   g_token=MakeToken();
   FileSeek(g_lock,0,SEEK_SET);
   FileWriteLong(g_lock,g_token);
   FileFlush(g_lock);
   return true;
}

void ReleaseFence()
{
   if(g_lock!=INVALID_HANDLE){ FileClose(g_lock); g_lock=INVALID_HANDLE; }
}

int OnInit()
{
   // This qualifier must execute in normal terminal runtime, never Strategy Tester.
   if(MQLInfoInteger(MQL_TESTER)==1)
   {
      WriteLocalRow(LName("RESULT.csv"),"R2T_RUNTIME","FAIL","UNEXPECTED_STRATEGY_TESTER");
      return INIT_FAILED;
   }

   if(InpMode==1) // startup smoke
   {
      WriteLocalRow(LName("RESULT.csv"),"R2T_SMOKE","PASS","NORMAL_TERMINAL_NO_TRADE_API");
      return INIT_SUCCEEDED;
   }

   if(InpMode==2) // holder
   {
      if(!AcquireFence())
      {
         int e=GetLastError();
         WriteLocalRow(LName("RESULT.csv"),"R2T_HOLDER","FAIL","LOCK_NOT_ACQUIRED",0,e);
         return INIT_FAILED;
      }
      if(!WriteLocalRow(LName("HOLDER_READY.csv"),"R2T_HOLDER_READY","PASS","LOCK_HELD",g_token,0))
      {
         ReleaseFence(); return INIT_FAILED;
      }
      g_hold_start=GetTickCount64();
      if(!EventSetMillisecondTimer(100)){ ReleaseFence(); return INIT_FAILED; }
      return INIT_SUCCEEDED;
   }

   if(InpMode==3) // probe while holder is alive
   {
      ResetLastError();
      bool got=AcquireFence();
      int e=GetLastError();
      if(got)
      {
         long t=g_token; ReleaseFence();
         WriteLocalRow(LName("RESULT.csv"),"R2T_FENCE_PROBE","FAIL","SECOND_LOCK_ACQUIRED",t,e);
      }
      else
      {
         WriteLocalRow(LName("RESULT.csv"),"R2T_FENCE_PROBE","PASS","SECOND_LOCK_DENIED",0,e);
      }
      return INIT_SUCCEEDED;
   }

   if(InpMode==4) // reacquire after release
   {
      ResetLastError();
      bool got=AcquireFence();
      int e=GetLastError();
      if(got)
      {
         long t=g_token; ReleaseFence();
         WriteLocalRow(LName("RESULT.csv"),"R2T_FENCE_REACQUIRE","PASS","LOCK_REACQUIRED_AFTER_RELEASE",t,e);
      }
      else
      {
         WriteLocalRow(LName("RESULT.csv"),"R2T_FENCE_REACQUIRE","FAIL","LOCK_STILL_UNAVAILABLE",0,e);
      }
      return INIT_SUCCEEDED;
   }

   if(InpMode==5) // durable common-state writer
   {
      long t=MakeToken();
      bool ok=WriteCommonState(CName("STATE.csv"),t);
      WriteLocalRow(LName("RESULT.csv"),"R2T_RESTART_WRITE",ok?"PASS":"FAIL",ok?"COMMON_STATE_WRITTEN":"COMMON_STATE_WRITE_FAILED",t,GetLastError());
      return ok?INIT_SUCCEEDED:INIT_FAILED;
   }

   if(InpMode==6) // common-state reader after process restart
   {
      long t=0,b=0; bool ok=ReadCommonState(CName("STATE.csv"),t,b);
      bool pass=(ok && t==InpExpectedToken);
      WriteLocalRow(LName("RESULT.csv"),"R2T_RESTART_READ",pass?"PASS":"FAIL",pass?"COMMON_STATE_RECONSTRUCTED":"COMMON_STATE_MISMATCH",t,GetLastError());
      return pass?INIT_SUCCEEDED:INIT_FAILED;
   }

   WriteLocalRow(LName("RESULT.csv"),"R2T_MODE","FAIL","UNKNOWN_MODE");
   return INIT_FAILED;
}

void OnTimer()
{
   if(InpMode!=2 || g_lock==INVALID_HANDLE) return;
   ulong elapsed=GetTickCount64()-g_hold_start;
   if(elapsed<(ulong)InpHoldMs) return;
   long t=g_token;
   EventKillTimer();
   ReleaseFence();
   WriteLocalRow(LName("RELEASED.csv"),"R2T_RELEASED","PASS","LOCK_RELEASED",t,0);
   ExpertRemove();
}
void OnDeinit(const int reason){ EventKillTimer(); ReleaseFence(); }
void OnTick(){}
