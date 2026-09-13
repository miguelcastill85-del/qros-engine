//+------------------------------------------------------------------+
//| QROS_RUNNER_ENV_QUALIFIER_v1.mq5                                |
//| Native environment qualifier only. No Candidate3, no trade API.  |
//+------------------------------------------------------------------+
#property strict
#property version   "1.00"
#property description "QROS runner native environment qualification harness. No trading."

#include <Trade/Trade.mqh> // compile-time proof that the standard include tree is valid

input int    InpMode=1;
input string InpPrefix="QROS_R2_UNSET";
input int    InpHoldMs=180000;
input long   InpExpectedToken=0;

int   g_lock=INVALID_HANDLE;
ulong g_hold_start=0;
long  g_token=0;

string Name(const string suffix){return InpPrefix+"_"+suffix;}

bool WriteCsv1(const string file,const string h1,const string h2,const string h3,
               const string v1,const string v2,const string v3)
  {
   int f=FileOpen(file,FILE_COMMON|FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(f==INVALID_HANDLE) return false;
   bool ok=(FileWrite(f,h1,h2,h3)>0 && FileWrite(f,v1,v2,v3)>0);
   FileFlush(f);FileClose(f);return ok;
  }

bool WriteResult(const string id,const string status,const string detail)
  {
   int f=FileOpen(Name("RESULTS.csv"),FILE_COMMON|FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(f==INVALID_HANDLE) return false;
   bool ok=(FileWrite(f,"test_id","status","detail","mql_tester","terminal_build","server")>0 &&
            FileWrite(f,id,status,detail,(int)MQLInfoInteger(MQL_TESTER),(int)TerminalInfoInteger(TERMINAL_BUILD),AccountInfoString(ACCOUNT_SERVER))>0);
   FileFlush(f);FileClose(f);return ok;
  }

long MakeToken()
  {
   long a=(long)(GetTickCount64()%1000000000ULL);
   long b=(long)(TimeLocal()%1000000000);
   long v=(a*1000003L+b)%9000000000000000L;
   if(v<=0) v=224000001;
   return v;
  }

bool AcquireFence()
  {
   string lockname=Name("FENCE.lock");
   ResetLastError();
   g_lock=FileOpen(lockname,FILE_COMMON|FILE_READ|FILE_WRITE|FILE_BIN);
   if(g_lock==INVALID_HANDLE) return false;
   g_token=MakeToken();
   FileSeek(g_lock,0,SEEK_SET);
   FileWriteLong(g_lock,g_token);
   FileFlush(g_lock);
   return true;
  }

void ReleaseFence()
  {
   if(g_lock!=INVALID_HANDLE){FileClose(g_lock);g_lock=INVALID_HANDLE;}
  }

int OnInit()
  {
   if(MQLInfoInteger(MQL_TESTER)!=1)
     {
      WriteResult("R2_TESTER_ENV","FAIL","NOT_STRATEGY_TESTER");
      return INIT_FAILED;
     }

   if(InpMode==1) // native materialization smoke
     {
      if(!WriteResult("R2_MQL_SMOKE","PASS","NO_TRADING_MATERIALIZATION")) return INIT_FAILED;
      return INIT_SUCCEEDED;
     }

   if(InpMode==2) // holder
     {
      if(!AcquireFence())
        {
         WriteResult("R2_FENCE_HOLDER","FAIL","LOCK_NOT_ACQUIRED");
         return INIT_FAILED;
        }
      if(!WriteCsv1(Name("HOLDER_READY.csv"),"ok","token","build","1",IntegerToString(g_token),IntegerToString((int)TerminalInfoInteger(TERMINAL_BUILD))))
        {ReleaseFence();return INIT_FAILED;}
      g_hold_start=GetTickCount64();
      if(!EventSetMillisecondTimer(100)){ReleaseFence();return INIT_FAILED;}
      return INIT_SUCCEEDED;
     }

   if(InpMode==3) // probe must be denied while holder owns the exact common file
     {
      bool got=AcquireFence();
      if(got)
        {
         ReleaseFence();
         WriteResult("R2_FENCE_PROBE","FAIL","SECOND_LOCK_ACQUIRED");
        }
      else
         WriteResult("R2_FENCE_PROBE","PASS","SECOND_LOCK_DENIED");
      return INIT_SUCCEEDED;
     }

   if(InpMode==4) // reacquire after holder release
     {
      bool got=AcquireFence();
      if(got)
        {
         long t=g_token;ReleaseFence();
         WriteCsv1(Name("REACQUIRE.csv"),"ok","token","build","1",IntegerToString(t),IntegerToString((int)TerminalInfoInteger(TERMINAL_BUILD)));
         WriteResult("R2_FENCE_REACQUIRE","PASS","LOCK_REACQUIRED_AFTER_RELEASE");
        }
      else WriteResult("R2_FENCE_REACQUIRE","FAIL","LOCK_STILL_UNAVAILABLE");
      return INIT_SUCCEEDED;
     }

   if(InpMode==5) // restart writer
     {
      long token=MakeToken();
      int f=FileOpen(Name("STATE.csv"),FILE_COMMON|FILE_WRITE|FILE_CSV|FILE_ANSI,',');
      if(f==INVALID_HANDLE){WriteResult("R2_RESTART_WRITE","FAIL","STATE_OPEN_FAILED");return INIT_FAILED;}
      bool ok=(FileWrite(f,"token","build")>0 && FileWrite(f,token,(int)TerminalInfoInteger(TERMINAL_BUILD))>0);
      FileFlush(f);FileClose(f);
      if(!ok){WriteResult("R2_RESTART_WRITE","FAIL","STATE_WRITE_FAILED");return INIT_FAILED;}
      WriteCsv1(Name("STATE_TOKEN.csv"),"token","build","ok",IntegerToString(token),IntegerToString((int)TerminalInfoInteger(TERMINAL_BUILD)),"1");
      WriteResult("R2_RESTART_WRITE","PASS","STATE_DURABLE");
      return INIT_SUCCEEDED;
     }

   if(InpMode==6) // restart reader in a new terminal/tester process
     {
      int f=FileOpen(Name("STATE.csv"),FILE_COMMON|FILE_READ|FILE_CSV|FILE_ANSI,',');
      if(f==INVALID_HANDLE){WriteResult("R2_RESTART_READ","FAIL","STATE_MISSING");return INIT_FAILED;}
      string h1=FileReadString(f),h2=FileReadString(f);
      long token=(long)FileReadNumber(f);long build=(long)FileReadNumber(f);FileClose(f);
      bool ok=(h1=="token" && h2=="build" && token==InpExpectedToken && build>0);
      WriteResult("R2_RESTART_READ",ok?"PASS":"FAIL",ok?"STATE_RECONSTRUCTED":"STATE_MISMATCH");
      return ok?INIT_SUCCEEDED:INIT_FAILED;
     }

   WriteResult("R2_MODE","FAIL","UNKNOWN_MODE");
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
   WriteCsv1(Name("RELEASED.csv"),"released","token","build","1",IntegerToString(t),IntegerToString((int)TerminalInfoInteger(TERMINAL_BUILD)));
   WriteResult("R2_FENCE_HOLDER","PASS","LOCK_HELD_WALLCLOCK_AND_RELEASED");
   ExpertRemove();
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   ReleaseFence();
  }

void OnTick(){}
