//+------------------------------------------------------------------+
//| QROS_DEMO_PORTFOLIO_EXECUTOR_v2_2_4.mq5                          |
//| Safety descendant of frozen v2.2.3 executor.                     |
//| No alpha/risk/priority changes. Darwinex-Demo only.               |
//+------------------------------------------------------------------+
#property strict
#property version "2.24"
#property description "QROS Darwinex-Demo v2.2.4 safety candidate. Fail-closed entries; durable reconciliation."

#include <Trade/Trade.mqh>
#include <QROS_RISK_KERNEL_APPROVED_v15420.mqh>
#include <QROS_DEMO_BUS_v2_2_4.mqh>

input bool   InpArmDemoOrders=false;
input string InpArmToken="";
input double InpRiskPctBalance=0.50;
input double InpMaxReservedRiskPct=1.00;
input int    InpMaxNewEntriesPerServerDay=3;
input int    InpHeartbeatMaxAgeMs=5000;
input int    InpPriorityBufferMs=300;
input int    InpEventMaxAgeMs=300000;
input int    InpSessionCloseLeadSec=0; // BLOCKED until native Darwinex execution-latency gate freezes an authoritative value
input long   InpExpectedCertManifestToken=224223002;
input string InpAuditPrefix="QROS_DEMO_EXECUTOR_v224";

const string QROS_REQUIRED_SERVER="Darwinex-Demo";
const string QROS_REQUIRED_CURRENCY="USD";
const string QROS_ARM_TOKEN="QROS_DEMO_ARM_v224_8af000_2d6ebd";
const long MAGIC_XAU=560101;
const long MAGIC_NQX17=560217;
const long MAGIC_NQX31=560231;
const long MAGIC_DIV3=560300;
const int QROS_INTENT_SLOTS=32;
const int QROS_MGMT_SLOTS=32;
const long QROS_EXACT_DOUBLE_MAX=9007199254740991LL;
const long QROS_EXEC_SOURCE_TOKEN=224201;
const long QROS_XAU_SOURCE_TOKEN=224101;
const long QROS_NQX_SOURCE_TOKEN=224102;
const long QROS_DIV3_SOURCE_TOKEN=224103;
const int  QROS_RECERT_STABLE_MS=2000;

// Entry intent states. Terminal states are >=70.
enum QrosIntentState
  {
   QI_EMPTY=0,
   QI_RESERVED=10,
   QI_SENT_UNKNOWN=20,
   QI_WORKING=30,
   QI_PARTIAL=40,
   QI_FILLED_PROTECTED=50,
   QI_CLOSING=60,
   QI_CLOSED=70,
   QI_REJECTED=80,
   QI_CANCELLED=90,
   QI_UPDATING=99
  };

enum QrosMgmtState
  {
   QM_EMPTY=0,
   QM_PENDING=10,
   QM_ESCALATED=20,
   QM_DONE=70,
   QM_UPDATING=99
  };

struct PendingEntry
  {
   QrosBusEvent ev;
   long received_uptime_ms;
  };

struct QrosIntent
  {
   bool used;
   int slot;
   long id;
   int state;
   int module_id;
   int profile;
   long event_ms;
   long magic;
   double risk_usd;
   double volume;
   double sl;
   double tp;
   ulong order_ticket;
   ulong deal_ticket;
   ulong position_ticket;
   int day_key;
   int counted;
   long created_uptime_ms;
   int reconcile_attempts;
  };

struct QrosMgmtIntent
  {
   bool used;
   int slot;
   long id;
   int state;
   int action;
   int module_id;
   int profile;
   long event_ms;
   long entry_intent_id;
   ulong position_ticket;
   ulong order_ticket;
   double sl;
   double tp;
   int attempts;
   long next_retry_uptime_ms;
  };

CTrade g_trade;
int g_log=INVALID_HANDLE;
int g_instance_lock=INVALID_HANDLE;
long g_instance_token=0;
long g_last_seq[4]={0,0,0,0};
long g_last_head_seen[4]={0,0,0,0};
bool g_entry_fault=false;
bool g_bus_fault=false;
bool g_mgmt_fault=false;
bool g_recovery_lock=false;
bool g_history_ready=false;
bool g_recert_required=false;
bool g_trade_tx_pending=false;
string g_recert_reason="";
string g_entry_fault_reason="";
string g_bus_fault_reason="";
string g_mgmt_fault_reason="";
long g_last_accepted_event_ms=-1;
int g_last_day_key=-1;
int g_day_entries=0;
long g_boot_offset_sec=0;
long g_last_offset_seen=0;
int g_offset_stable_samples=0;
long g_recert_healthy_since_ms=0;
bool g_was_connected=false;
long g_bound_owner[4]={0,0,0,0};
long g_bound_epoch[4]={0,0,0,0};
ulong g_counted_orders[];

PendingEntry g_pending[];
QrosIntent g_intents[QROS_INTENT_SLOTS];
QrosMgmtIntent g_mgmt[QROS_MGMT_SLOTS];

bool IsQrosMagic(const long m)
  {
   return (m==MAGIC_XAU || m==MAGIC_NQX17 || m==MAGIC_NQX31 || m==MAGIC_DIV3);
  }

long MagicFor(const int module_id,const int profile)
  {
   if(module_id==QROS_MOD_XAU) return MAGIC_XAU;
   if(module_id==QROS_MOD_DIV3) return MAGIC_DIV3;
   if(module_id==QROS_MOD_NQX && profile==17) return MAGIC_NQX17;
   if(module_id==QROS_MOD_NQX && profile==31) return MAGIC_NQX31;
   return -1;
  }

string SymbolFor(const int module_id)
  {
   if(module_id==QROS_MOD_XAU) return "XAUUSD";
   if(module_id==QROS_MOD_NQX || module_id==QROS_MOD_DIV3) return "NDX";
   return "";
  }

int PriorityFor(const int module_id)
  {
   if(module_id==QROS_MOD_XAU) return 0;
   if(module_id==QROS_MOD_NQX) return 1;
   if(module_id==QROS_MOD_DIV3) return 2;
   return 99;
  }

bool ExactLongForDouble(const long v)
  {
   return (v>=0 && v<=QROS_EXACT_DOUBLE_MAX);
  }

int ServerDayKey()
  {
   datetime t=TimeTradeServer();
   MqlDateTime s; TimeToStruct(t,s);
   return s.year*10000+s.mon*100+s.day;
  }

datetime ServerDayStart()
  {
   datetime t=TimeTradeServer();
   MqlDateTime s; TimeToStruct(t,s);
   s.hour=0;s.min=0;s.sec=0;
   return StructToTime(s);
  }

int ServerSecondsOfDay()
  {
   MqlDateTime s;TimeToStruct(TimeTradeServer(),s);
   return s.hour*3600+s.min*60+s.sec;
  }

bool FinalTradeSessionEndSec(const string symbol,int &end_sec)
  {
   end_sec=-1;
   MqlDateTime now;TimeToStruct(TimeTradeServer(),now);
   ENUM_DAY_OF_WEEK dow=(ENUM_DAY_OF_WEEK)now.day_of_week;
   for(uint idx=0;idx<32;idx++)
     {
      datetime from=0,to=0;
      if(!SymbolInfoSessionTrade(symbol,dow,idx,from,to)) break;
      MqlDateTime ts;TimeToStruct(to,ts);
      int sec=ts.hour*3600+ts.min*60+ts.sec;
      // MT5 represents a session ending at next midnight as 00:00.
      if(sec==0) sec=86400;
      if(sec>end_sec) end_sec=sec;
     }
   return (end_sec>0 && end_sec<=86400);
  }

bool SessionEntrySafe(const string symbol)
  {
   int end_sec=-1;
   if(!FinalTradeSessionEndSec(symbol,end_sec)) return false;
   if(InpSessionCloseLeadSec<=0) return false;
   return (ServerSecondsOfDay()<end_sec-InpSessionCloseLeadSec);
  }

long CurrentOffsetSec(bool &ok)
  {
   ok=false;
   datetime srv=TimeTradeServer();
   datetime gmt=TimeGMT();
   if(srv<=0 || gmt<=0) return 0;
   long raw=(long)(srv-gmt);
   long rounded=(long)MathRound((double)raw/3600.0)*3600L;
   if(MathAbs((double)(raw-rounded))>10.0) return rounded;
   if(rounded!=7200 && rounded!=10800) return rounded;
   ok=true;
   return rounded;
  }

bool GvSet(const string key,const double value)
  {
   if(!MathIsValidNumber(value)) return false;
   ResetLastError();
   datetime r=GlobalVariableSet(key,value);
   if(r==0)
     {
      PrintFormat("QROS V224 GlobalVariableSet failed key=%s err=%d",key,GetLastError());
      return false;
     }
   if(!GlobalVariableCheck(key)) return false;
   double observed=GlobalVariableGet(key);
   if(!MathIsValidNumber(observed) || observed!=value) return false;
   return true;
  }

bool GvGetExactLong(const string key,long &out)
  {
   out=0;
   if(!GlobalVariableCheck(key)) return false;
   double v=GlobalVariableGet(key);
   if(!MathIsValidNumber(v) || v<0.0 || v>(double)QROS_EXACT_DOUBLE_MAX) return false;
   if(v!=MathFloor(v)) return false;
   out=(long)v;
   return true;
  }

bool GvGetRequiredDouble(const string key,double &out)
  {
   out=0.0;
   if(!GlobalVariableCheck(key)) return false;
   out=GlobalVariableGet(key);
   return MathIsValidNumber(out);
  }

bool GvSetUlong(const string prefix,const ulong value)
  {
   ulong hi=value/4294967296;
   ulong lo=value%4294967296;
   return (GvSet(prefix+"H",(double)hi) && GvSet(prefix+"L",(double)lo));
  }

bool GvGetUlong(const string prefix,ulong &value)
  {
   long hi=0,lo=0;
   value=0;
   if(!GvGetExactLong(prefix+"H",hi) || !GvGetExactLong(prefix+"L",lo)) return false;
   if(hi<0 || lo<0 || hi>4294967295LL || lo>4294967295LL) return false;
   value=(ulong)hi*4294967296+(ulong)lo;
   return true;
  }

long SourceTokenFor(const int module_id)
  {
   if(module_id==QROS_MOD_XAU) return QROS_XAU_SOURCE_TOKEN;
   if(module_id==QROS_MOD_NQX) return QROS_NQX_SOURCE_TOKEN;
   if(module_id==QROS_MOD_DIV3) return QROS_DIV3_SOURCE_TOKEN;
   return 0;
  }

bool ModuleProfileForMagic(const long magic,int &module_id,int &profile)
  {
   module_id=0;profile=0;
   if(magic==MAGIC_XAU){module_id=QROS_MOD_XAU;profile=0;return true;}
   if(magic==MAGIC_DIV3){module_id=QROS_MOD_DIV3;profile=0;return true;}
   if(magic==MAGIC_NQX17){module_id=QROS_MOD_NQX;profile=17;return true;}
   if(magic==MAGIC_NQX31){module_id=QROS_MOD_NQX;profile=31;return true;}
   return false;
  }

int DayKeyFromMs(const long event_ms)
  {
   if(event_ms<=0) return -1;
   datetime t=(datetime)(event_ms/1000L);
   MqlDateTime s;TimeToStruct(t,s);
   return s.year*10000+s.mon*100+s.day;
  }

void InvalidateCert()
  {
   GlobalVariableSet("Q24.EXEC.CERT",0.0);
   GlobalVariableSet("Q24.EXEC.HEALTH",0.0);
  }

void RequireRecert(const string reason)
  {
   if(!g_recert_required || g_recert_reason!=reason)
     {
      g_recert_required=true;
      g_recert_reason=reason;
      g_recert_healthy_since_ms=0;
      Print("QROS V224 RECERT REQUIRED: ",reason);
     }
   InvalidateCert();
   GlobalVariableSet("Q24.EXEC.RECERT",1.0);
  }

void SetEntryFault(const string reason)
  {
   if(!g_entry_fault)
     {
      g_entry_fault=true;
      g_entry_fault_reason=reason;
      Print("QROS V224 ENTRY FAULT: ",reason);
     }
   InvalidateCert();
   GlobalVariableSet("Q24.EXEC.ENTRYFAULT",1.0);
  }

void SetBusFault(const string reason)
  {
   if(!g_bus_fault)
     {
      g_bus_fault=true;
      g_bus_fault_reason=reason;
      Print("QROS V224 BUS FAULT: ",reason);
     }
   SetEntryFault("BUS_"+reason);
   GlobalVariableSet("Q24.EXEC.BUSFAULT",1.0);
  }

void SetMgmtFault(const string reason)
  {
   if(!g_mgmt_fault)
     {
      g_mgmt_fault=true;
      g_mgmt_fault_reason=reason;
      Print("QROS V224 MANAGEMENT FAULT: ",reason);
     }
   InvalidateCert();
   GlobalVariableSet("Q24.EXEC.MGMTFAULT",1.0);
  }

bool DemoAccountGate()
  {
   if((ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO)
     {SetEntryFault("ACCOUNT_NOT_DEMO");return false;}
   if(AccountInfoString(ACCOUNT_SERVER)!=QROS_REQUIRED_SERVER)
     {SetEntryFault("WRONG_SERVER_"+AccountInfoString(ACCOUNT_SERVER));return false;}
   if(AccountInfoString(ACCOUNT_CURRENCY)!=QROS_REQUIRED_CURRENCY)
     {SetEntryFault("WRONG_CURRENCY_"+AccountInfoString(ACCOUNT_CURRENCY));return false;}
   return true;
  }

bool EntryTradeGate()
  {
   if(!InpArmDemoOrders) return false;
   if(InpArmToken!=QROS_ARM_TOKEN){SetEntryFault("INVALID_ARM_TOKEN");return false;}
   if(!MQLInfoInteger(MQL_TRADE_ALLOWED)){RequireRecert("MQL_TRADE_NOT_ALLOWED");return false;}
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)){RequireRecert("TERMINAL_TRADE_NOT_ALLOWED");return false;}
   if(!TerminalInfoInteger(TERMINAL_CONNECTED)){RequireRecert("TERMINAL_DISCONNECTED");return false;}
   return true;
  }

bool MgmtTradeGate()
  {
   if(!InpArmDemoOrders) return false;
   if(InpArmToken!=QROS_ARM_TOKEN) return false;
   if((ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO) return false;
   if(AccountInfoString(ACCOUNT_SERVER)!=QROS_REQUIRED_SERVER) return false;
   if(!MQLInfoInteger(MQL_TRADE_ALLOWED)) return false;
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)) return false;
   if(!TerminalInfoInteger(TERMINAL_CONNECTED)) return false;
   return true;
  }

bool RuntimeCertified()
  {
   if(InpSessionCloseLeadSec<=0) return false;
   if(g_entry_fault || g_bus_fault || g_mgmt_fault || g_recovery_lock || g_recert_required) return false;
   if(!GlobalVariableCheck("Q24.EXEC.CERT") || GlobalVariableGet("Q24.EXEC.CERT")!=1.0) return false;
   long v=0;
   if(!GvGetExactLong("Q24.EXEC.CERT_INSTANCE",v) || v!=g_instance_token) return false;
   if(!GvGetExactLong("Q24.EXEC.CERT_BUILD",v) || v!=(long)TerminalInfoInteger(TERMINAL_BUILD)) return false;
   if(!GvGetExactLong("Q24.EXEC.CERT_LOGIN",v) || v!=(long)AccountInfoInteger(ACCOUNT_LOGIN)) return false;
   if(!GvGetExactLong("Q24.EXEC.CERT_MANIFEST",v) || v!=InpExpectedCertManifestToken) return false;
   if(!GvGetExactLong("Q24.EXEC.CERT_EXEC_SOURCE",v) || v!=QROS_EXEC_SOURCE_TOKEN) return false;
   bool ook=false;long off=CurrentOffsetSec(ook);
   if(!ook) return false;
   if(!GvGetExactLong("Q24.EXEC.CERT_OFFSET",v) || v!=off) return false;
   for(int m=1;m<=3;m++)
     {
      long owner=QrosBusProducerOwner(m),epoch=QrosBusProducerEpoch(m),src=0;
      if(owner<=0 || epoch<=0 || g_bound_owner[m]!=owner || g_bound_epoch[m]!=epoch) return false;
      if(!GvGetExactLong("Q24.EXEC.CERT_M"+IntegerToString(m)+"_OWNER",v) || v!=owner) return false;
      if(!GvGetExactLong("Q24.EXEC.CERT_M"+IntegerToString(m)+"_EPOCH",v) || v!=epoch) return false;
      if(!GvGetExactLong(QrosBusKey(m,"SOURCE_TOKEN"),src) || src!=SourceTokenFor(m)) return false;
      if(!GvGetExactLong("Q24.EXEC.CERT_M"+IntegerToString(m)+"_SOURCE",v) || v!=src) return false;
     }
   return true;
  }

bool HeartbeatsReady()
  {
   for(int m=1;m<=3;m++)
     {
      if(QrosBusState(m)!=QROS_STATE_READY) return false;
      long age=QrosBusHeartbeatAgeMs(m);
      if(age<0 || age>InpHeartbeatMaxAgeMs) return false;
     }
   return true;
  }

bool PositiveSpread(const string symbol,MqlTick &tick)
  {
   if(!SymbolInfoTick(symbol,tick)) return false;
   if(!(tick.bid>0.0) || !(tick.ask>0.0)) return false;
   return tick.ask>tick.bid;
  }

bool FreshExecutableTick(const string symbol,MqlTick &tick)
  {
   if(!PositiveSpread(symbol,tick)) return false;
   long nowms=(long)TimeTradeServer()*1000L;
   long age=nowms-tick.time_msc;
   return (age>=-2000 && age<=5000);
  }

bool BarriersTradableBuy(const string symbol,const double bid,const double ask,const double sl,const double tp)
  {
   if(!MathIsValidNumber(bid) || !MathIsValidNumber(ask) || !MathIsValidNumber(sl) || !MathIsValidNumber(tp)) return false;
   // BUY enters Ask; SL/TP are observed on Bid. Require positive spread geometry and positive target after spread.
   if(!(sl>0.0) || !(tp>0.0) || !(bid>0.0) || !(ask>bid) || sl>=bid || tp<=ask) return false;
   double point=SymbolInfoDouble(symbol,SYMBOL_POINT);
   long stops=(long)SymbolInfoInteger(symbol,SYMBOL_TRADE_STOPS_LEVEL);
   long freeze=(long)SymbolInfoInteger(symbol,SYMBOL_TRADE_FREEZE_LEVEL);
   long level=(stops>freeze?stops:freeze);
   if(point>0.0 && level>0)
     {
      double d=(double)level*point;
      if(bid-sl<d || tp-bid<d) return false;
     }
   return true;
  }

bool ProtectionAtLeastRequestedBuy(const string symbol,const double observed_sl,const double observed_tp,
                                    const double requested_sl,const double requested_tp)
  {
   if(!(observed_sl>0.0) || !(observed_tp>0.0)) return false;
   double ts=SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_SIZE);
   if(!(ts>0.0)) ts=SymbolInfoDouble(symbol,SYMBOL_POINT);
   double tol=(ts>0.0?ts*0.51:1e-8);
   if(observed_sl+tol<requested_sl) return false; // a tighter/higher BUY stop is acceptable
   return PriceSameGrid(symbol,observed_tp,requested_tp);
  }

double GridNormalize(const string symbol,const double price)
  {
   double ts=SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_SIZE);
   if(!(ts>0.0)) ts=SymbolInfoDouble(symbol,SYMBOL_POINT);
   int digits=(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS);
   if(!(ts>0.0)) return NormalizeDouble(price,digits);
   return NormalizeDouble(MathRound(price/ts)*ts,digits);
  }

bool PriceSameGrid(const string symbol,const double a,const double b)
  {
   double ts=SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_SIZE);
   if(!(ts>0.0)) ts=SymbolInfoDouble(symbol,SYMBOL_POINT);
   if(!(ts>0.0)) return MathAbs(a-b)<1e-8;
   return MathAbs(a-b)<=ts*0.51;
  }

long MakeInstanceToken()
  {
   long login=(long)AccountInfoInteger(ACCOUNT_LOGIN);
   long t=(long)TimeLocal();
   long up=(long)GetTickCount64();
   long v=(login%100000000LL)*10000000LL+(t%100000LL)*100LL+(up%97LL);
   if(v<=0) v=224000001;
   if(v>QROS_EXACT_DOUBLE_MAX) v%=QROS_EXACT_DOUBLE_MAX;
   return v;
  }

bool AcquireInstanceFence()
  {
   long login=(long)AccountInfoInteger(ACCOUNT_LOGIN);
   string name="QROS_V224_EXECUTOR_"+IntegerToString(login)+"_"+AccountInfoString(ACCOUNT_SERVER)+".lock";
   ResetLastError();
   g_instance_lock=FileOpen(name,FILE_READ|FILE_WRITE|FILE_BIN|FILE_COMMON);
   if(g_instance_lock==INVALID_HANDLE)
     {
      PrintFormat("QROS V224 executor fencing lock failed err=%d",GetLastError());
      return false;
     }
   g_instance_token=MakeInstanceToken();
   FileSeek(g_instance_lock,0,SEEK_SET);
   FileWriteLong(g_instance_lock,g_instance_token);
   FileFlush(g_instance_lock);
   if(!GvSet("Q24.EXEC.INSTANCE",(double)g_instance_token)) return false;
   GlobalVariablesFlush();
   return true;
  }

void ReleaseInstanceFence()
  {
   if(GlobalVariableCheck("Q24.EXEC.INSTANCE") && (long)GlobalVariableGet("Q24.EXEC.INSTANCE")==g_instance_token)
      GlobalVariableSet("Q24.EXEC.INSTANCE",0.0);
   if(g_instance_lock!=INVALID_HANDLE)
     {
      FileClose(g_instance_lock);
      g_instance_lock=INVALID_HANDLE;
     }
  }

bool OpenAppendLedger()
  {
   string file=InpAuditPrefix+"_LEDGER.csv";
   g_log=FileOpen(file,FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,',');
   if(g_log==INVALID_HANDLE) return false;
   if(FileSize(g_log)==0)
     {
      uint w=FileWrite(g_log,"server_time","uptime_ms","stage","decision","reason","module_id","profile","seq","event_ms","action","intent_id","state","symbol","bid","ask","volume","sl","tp","order","deal","position","retcode","server","login","balance");
      if(w==0) return false;
     }
   FileSeek(g_log,0,SEEK_END);
   FileFlush(g_log);
   return true;
  }

bool LogRow(const string stage,const string decision,const QrosBusEvent &ev,
            const string reason,const long intent_id,const int state,const string symbol,
            const double bid,const double ask,const double volume,const double sl,const double tp,
            const ulong order=0,const ulong deal=0,const ulong position=0,const uint retcode=0)
  {
   if(g_log==INVALID_HANDLE) return false;
   uint w=FileWrite(g_log,
      TimeToString(TimeTradeServer(),TIME_DATE|TIME_SECONDS),(long)GetTickCount64(),
      stage,decision,reason,ev.module_id,ev.profile,ev.seq,ev.event_ms,ev.action,
      intent_id,state,symbol,bid,ask,volume,sl,tp,(long)order,(long)deal,(long)position,(long)retcode,
      AccountInfoString(ACCOUNT_SERVER),(long)AccountInfoInteger(ACCOUNT_LOGIN),
      DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE),2));
   FileFlush(g_log);
   if(w==0)
     {
      SetEntryFault("LEDGER_WRITE_FAILED");
      return false;
     }
   return true;
  }

string IKey(const int slot,const string field)
  {
   return "Q24.I"+IntegerToString(slot)+"."+field;
  }

string MKey(const int slot,const string field)
  {
   return "Q24.M"+IntegerToString(slot)+"."+field;
  }

bool SaveIntent(const int i)
  {
   if(i<0 || i>=QROS_INTENT_SLOTS || !g_intents[i].used) return false;
   QrosIntent x=g_intents[i];
   bool ok=true;
   ok=ok && GvSet(IKey(i,"ST"),(double)QI_UPDATING);
   ok=ok && GvSet(IKey(i,"ID"),(double)x.id);
   ok=ok && GvSet(IKey(i,"MO"),(double)x.module_id);
   ok=ok && GvSet(IKey(i,"PR"),(double)x.profile);
   ok=ok && GvSet(IKey(i,"EV"),(double)x.event_ms);
   ok=ok && GvSet(IKey(i,"MA"),(double)x.magic);
   ok=ok && GvSet(IKey(i,"RI"),x.risk_usd);
   ok=ok && GvSet(IKey(i,"VO"),x.volume);
   ok=ok && GvSet(IKey(i,"SL"),x.sl);
   ok=ok && GvSet(IKey(i,"TP"),x.tp);
   ok=ok && GvSetUlong(IKey(i,"OR"),x.order_ticket);
   ok=ok && GvSetUlong(IKey(i,"DE"),x.deal_ticket);
   ok=ok && GvSetUlong(IKey(i,"PO"),x.position_ticket);
   ok=ok && GvSet(IKey(i,"DY"),(double)x.day_key);
   ok=ok && GvSet(IKey(i,"CO"),(double)x.counted);
   ok=ok && GvSet(IKey(i,"CR"),(double)x.created_uptime_ms);
   ok=ok && GvSet(IKey(i,"AT"),(double)x.reconcile_attempts);
   ok=ok && GvSet(IKey(i,"VR"),(double)x.id);
   ok=ok && GvSet(IKey(i,"ST"),(double)x.state);
   GlobalVariablesFlush();
   if(!ok) SetEntryFault("INTENT_PERSIST_FAILED");
   return ok;
  }

void ClearIntent(const int i)
  {
   if(i<0 || i>=QROS_INTENT_SLOTS) return;
   GlobalVariableSet(IKey(i,"ST"),0.0);
   GlobalVariableSet(IKey(i,"VR"),0.0);
   GlobalVariablesFlush();
   ZeroMemory(g_intents[i]);
   g_intents[i].slot=i;
  }

bool SaveMgmt(const int i)
  {
   if(i<0 || i>=QROS_MGMT_SLOTS || !g_mgmt[i].used) return false;
   QrosMgmtIntent x=g_mgmt[i];
   bool ok=true;
   ok=ok && GvSet(MKey(i,"ST"),(double)QM_UPDATING);
   ok=ok && GvSet(MKey(i,"ID"),(double)x.id);
   ok=ok && GvSet(MKey(i,"AC"),(double)x.action);
   ok=ok && GvSet(MKey(i,"MO"),(double)x.module_id);
   ok=ok && GvSet(MKey(i,"PR"),(double)x.profile);
   ok=ok && GvSet(MKey(i,"EV"),(double)x.event_ms);
   ok=ok && GvSet(MKey(i,"II"),(double)x.entry_intent_id);
   ok=ok && GvSetUlong(MKey(i,"PO"),x.position_ticket);
   ok=ok && GvSetUlong(MKey(i,"OR"),x.order_ticket);
   ok=ok && GvSet(MKey(i,"SL"),x.sl);
   ok=ok && GvSet(MKey(i,"TP"),x.tp);
   ok=ok && GvSet(MKey(i,"AT"),(double)x.attempts);
   ok=ok && GvSet(MKey(i,"NX"),(double)x.next_retry_uptime_ms);
   ok=ok && GvSet(MKey(i,"VR"),(double)x.id);
   ok=ok && GvSet(MKey(i,"ST"),(double)x.state);
   GlobalVariablesFlush();
   if(!ok) SetMgmtFault("MGMT_PERSIST_FAILED");
   return ok;
  }

void ClearMgmt(const int i)
  {
   if(i<0 || i>=QROS_MGMT_SLOTS) return;
   GlobalVariableSet(MKey(i,"ST"),0.0);
   GlobalVariableSet(MKey(i,"VR"),0.0);
   GlobalVariablesFlush();
   ZeroMemory(g_mgmt[i]);
   g_mgmt[i].slot=i;
  }

void InitSlots()
  {
   ArrayResize(g_counted_orders,0);
   for(int i=0;i<QROS_INTENT_SLOTS;i++)
     {
      ZeroMemory(g_intents[i]);
      g_intents[i].slot=i;
     }
   for(int i=0;i<QROS_MGMT_SLOTS;i++)
     {
      ZeroMemory(g_mgmt[i]);
      g_mgmt[i].slot=i;
     }
  }

bool LoadIntentSlot(const int i,QrosIntent &x)
  {
   long st=0,id=0,mo=0,pr=0,ev=0,ma=0,dy=0,co=0,cr=0,at=0,vr=0;
   double ri=0.0,vo=0.0,sl=0.0,tp=0.0;
   if(!GvGetExactLong(IKey(i,"ST"),st)) return false;
   if(st==QI_EMPTY) return false;
   if(st==QI_UPDATING) return false;
   if(!GvGetExactLong(IKey(i,"ID"),id) || !GvGetExactLong(IKey(i,"MO"),mo) ||
      !GvGetExactLong(IKey(i,"PR"),pr) || !GvGetExactLong(IKey(i,"EV"),ev) ||
      !GvGetExactLong(IKey(i,"MA"),ma) || !GvGetExactLong(IKey(i,"DY"),dy) ||
      !GvGetExactLong(IKey(i,"CO"),co) || !GvGetExactLong(IKey(i,"CR"),cr) ||
      !GvGetExactLong(IKey(i,"AT"),at) || !GvGetExactLong(IKey(i,"VR"),vr)) return false;
   if(!GvGetRequiredDouble(IKey(i,"RI"),ri) || !GvGetRequiredDouble(IKey(i,"VO"),vo) ||
      !GvGetRequiredDouble(IKey(i,"SL"),sl) || !GvGetRequiredDouble(IKey(i,"TP"),tp)) return false;
   ulong ord=0,deal=0,pos=0;
   if(!GvGetUlong(IKey(i,"OR"),ord) || !GvGetUlong(IKey(i,"DE"),deal) || !GvGetUlong(IKey(i,"PO"),pos)) return false;
   if(id<=0 || vr!=id || ev<=0 || mo<QROS_MOD_XAU || mo>QROS_MOD_DIV3 || co<0 || co>1) return false;
   if(ma!=MagicFor((int)mo,(int)pr)) return false;
   if(!(st==QI_RESERVED || st==QI_SENT_UNKNOWN || st==QI_WORKING || st==QI_PARTIAL ||
        st==QI_FILLED_PROTECTED || st==QI_CLOSING || st==QI_CLOSED || st==QI_REJECTED || st==QI_CANCELLED)) return false;
   ZeroMemory(x);x.used=true;x.slot=i;x.state=(int)st;x.id=id;x.module_id=(int)mo;x.profile=(int)pr;
   x.event_ms=ev;x.magic=ma;x.risk_usd=ri;x.volume=vo;x.sl=sl;x.tp=tp;x.order_ticket=ord;x.deal_ticket=deal;
   x.position_ticket=pos;x.day_key=(int)dy;x.counted=(int)co;x.created_uptime_ms=cr;x.reconcile_attempts=(int)at;
   return true;
  }

bool LoadMgmtSlot(const int i,QrosMgmtIntent &x)
  {
   long st=0,id=0,ac=0,mo=0,pr=0,ev=0,ii=0,at=0,nx=0,vr=0;
   double sl=0.0,tp=0.0;
   if(!GvGetExactLong(MKey(i,"ST"),st)) return false;
   if(st==QM_EMPTY) return false;
   if(st==QM_UPDATING) return false;
   if(!GvGetExactLong(MKey(i,"ID"),id) || !GvGetExactLong(MKey(i,"AC"),ac) ||
      !GvGetExactLong(MKey(i,"MO"),mo) || !GvGetExactLong(MKey(i,"PR"),pr) ||
      !GvGetExactLong(MKey(i,"EV"),ev) || !GvGetExactLong(MKey(i,"II"),ii) ||
      !GvGetExactLong(MKey(i,"AT"),at) || !GvGetExactLong(MKey(i,"NX"),nx) ||
      !GvGetExactLong(MKey(i,"VR"),vr)) return false;
   if(!GvGetRequiredDouble(MKey(i,"SL"),sl) || !GvGetRequiredDouble(MKey(i,"TP"),tp)) return false;
   ulong pos=0,ord=0;
   if(!GvGetUlong(MKey(i,"PO"),pos) || !GvGetUlong(MKey(i,"OR"),ord)) return false;
   if(id<=0 || vr!=id || ev<=0 || mo<QROS_MOD_XAU || mo>QROS_MOD_DIV3) return false;
   if(ac!=QROS_ACT_MODIFY_SL && ac!=QROS_ACT_CLOSE) return false;
   if(st!=QM_PENDING && st!=QM_ESCALATED && st!=QM_DONE) return false;
   ZeroMemory(x);x.used=true;x.slot=i;x.id=id;x.state=(int)st;x.action=(int)ac;x.module_id=(int)mo;x.profile=(int)pr;
   x.event_ms=ev;x.entry_intent_id=ii;x.position_ticket=pos;x.order_ticket=ord;x.sl=sl;x.tp=tp;
   x.attempts=(int)at;x.next_retry_uptime_ms=0; // uptime is process-local; retry immediately after recovery
   return true;
  }

void LoadPersistentState()
  {
   for(int i=0;i<QROS_INTENT_SLOTS;i++)
     {
      string sk=IKey(i,"ST");
      if(!GlobalVariableCheck(sk)) continue;
      long st=0;
      if(!GvGetExactLong(sk,st) || st==QI_UPDATING)
        {SetEntryFault("INTENT_RECOVERY_TORN_SLOT");continue;}
      if(st==QI_EMPTY) continue;
      QrosIntent x;
      if(!LoadIntentSlot(i,x)){SetEntryFault("INTENT_RECOVERY_INVALID_SLOT");continue;}
      g_intents[i]=x;
     }
   for(int i=0;i<QROS_MGMT_SLOTS;i++)
     {
      string sk=MKey(i,"ST");
      if(!GlobalVariableCheck(sk)) continue;
      long st=0;
      if(!GvGetExactLong(sk,st) || st==QM_UPDATING)
        {SetMgmtFault("MGMT_RECOVERY_TORN_SLOT");continue;}
      if(st==QM_EMPTY) continue;
      QrosMgmtIntent x;
      if(!LoadMgmtSlot(i,x)){SetMgmtFault("MGMT_RECOVERY_INVALID_SLOT");continue;}
      g_mgmt[i]=x;
     }
  }

bool IntentTerminal(const int state)
  {
   return (state==QI_CLOSED || state==QI_REJECTED || state==QI_CANCELLED);
  }

long IntentId(const QrosBusEvent &ev)
  {
   if(ev.event_ms<=0) return 0;
   long v=ev.event_ms*1000LL+(long)ev.module_id*100LL+(long)(ev.profile+50);
   if(v<=0 || !ExactLongForDouble(v)) return 0;
   return v;
  }

string IntentComment(const long id)
  {
   return "Q224_"+IntegerToString(id);
  }

int FindIntentById(const long id)
  {
   for(int i=0;i<QROS_INTENT_SLOTS;i++) if(g_intents[i].used && g_intents[i].id==id) return i;
   return -1;
  }

int FindFreeIntentSlot()
  {
   for(int i=0;i<QROS_INTENT_SLOTS;i++) if(!g_intents[i].used) return i;
   int dk=ServerDayKey();
   // Preserve same-day terminal tombstones so a duplicate event cannot be re-executed.
   for(int i=0;i<QROS_INTENT_SLOTS;i++)
      if(g_intents[i].used && IntentTerminal(g_intents[i].state) && g_intents[i].day_key!=dk) return i;
   return -1;
  }

int FindActiveIntentForModuleProfile(const int module_id,const int profile,const long at_or_before_ms)
  {
   int best=-1;long bestms=-1;
   for(int i=0;i<QROS_INTENT_SLOTS;i++)
     {
      if(!g_intents[i].used || IntentTerminal(g_intents[i].state)) continue;
      if(g_intents[i].module_id!=module_id || g_intents[i].profile!=profile) continue;
      if(g_intents[i].event_ms>at_or_before_ms) continue;
      if(g_intents[i].event_ms>bestms){best=i;bestms=g_intents[i].event_ms;}
     }
   return best;
  }

bool ActiveIntentOnAsset(const string symbol)
  {
   for(int i=0;i<QROS_INTENT_SLOTS;i++)
     {
      if(!g_intents[i].used || IntentTerminal(g_intents[i].state)) continue;
      if(SymbolFor(g_intents[i].module_id)==symbol) return true;
     }
   return false;
  }

bool ActiveIntentAtTimestamp(const long event_ms)
  {
   for(int i=0;i<QROS_INTENT_SLOTS;i++)
      if(g_intents[i].used && !IntentTerminal(g_intents[i].state) && g_intents[i].event_ms==event_ms) return true;
   return false;
  }

bool AnyPositionOnAsset(const string symbol)
  {
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL)==symbol) return true;
     }
   return false;
  }

ulong FindQrosPosition(const string symbol,const long magic,const string comment="")
  {
   ulong fallback=0;
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL)!=symbol) continue;
      if((long)PositionGetInteger(POSITION_MAGIC)!=magic) continue;
      if(comment!="" && PositionGetString(POSITION_COMMENT)==comment) return ticket;
      if(fallback==0) fallback=ticket;
     }
   return fallback;
  }

ulong FindCurrentOrder(const string symbol,const long magic,const string comment="")
  {
   ulong fallback=0;
   for(int i=OrdersTotal()-1;i>=0;i--)
     {
      ulong ticket=OrderGetTicket(i);
      if(ticket==0) continue;
      if(OrderGetString(ORDER_SYMBOL)!=symbol) continue;
      if((long)OrderGetInteger(ORDER_MAGIC)!=magic) continue;
      if(comment!="" && OrderGetString(ORDER_COMMENT)==comment) return ticket;
      if(fallback==0) fallback=ticket;
     }
   return fallback;
  }

bool IsOrderLinkedToIntent(const ulong order_ticket)
  {
   if(order_ticket==0) return false;
   for(int i=0;i<QROS_INTENT_SLOTS;i++)
      if(g_intents[i].used && !IntentTerminal(g_intents[i].state) && g_intents[i].order_ticket==order_ticket) return true;
   return false;
  }

double PositionRiskUsd(const ulong ticket,bool &ok)
  {
   ok=false;
   if(ticket==0 || !PositionSelectByTicket(ticket)) return 0.0;
   string sym=PositionGetString(POSITION_SYMBOL);
   double openp=PositionGetDouble(POSITION_PRICE_OPEN);
   double sl=PositionGetDouble(POSITION_SL);
   double vol=PositionGetDouble(POSITION_VOLUME);
   long ptype=(long)PositionGetInteger(POSITION_TYPE);
   if(!(sl>0.0) || !(vol>0.0)) return 0.0;
   ENUM_ORDER_TYPE ot=(ptype==POSITION_TYPE_BUY?ORDER_TYPE_BUY:ORDER_TYPE_SELL);
   double p=0.0;
   if(!OrderCalcProfit(ot,sym,vol,openp,sl,p) || !MathIsValidNumber(p)) return 0.0;
   ok=true;
   return MathAbs(p);
  }

double OrderRiskUsd(const ulong ticket,bool &ok)
  {
   ok=false;
   if(ticket==0 || !OrderSelect(ticket)) return 0.0;
   string sym=OrderGetString(ORDER_SYMBOL);
   double openp=OrderGetDouble(ORDER_PRICE_OPEN);
   double sl=OrderGetDouble(ORDER_SL);
   double vol=OrderGetDouble(ORDER_VOLUME_CURRENT);
   if(!(vol>0.0)) vol=OrderGetDouble(ORDER_VOLUME_INITIAL);
   if(!(sl>0.0) || !(vol>0.0) || !(openp>0.0)) return 0.0;
   ENUM_ORDER_TYPE typ=(ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
   ENUM_ORDER_TYPE calc=(typ==ORDER_TYPE_SELL || typ==ORDER_TYPE_SELL_LIMIT || typ==ORDER_TYPE_SELL_STOP || typ==ORDER_TYPE_SELL_STOP_LIMIT)?ORDER_TYPE_SELL:ORDER_TYPE_BUY;
   double p=0.0;
   if(!OrderCalcProfit(calc,sym,vol,openp,sl,p) || !MathIsValidNumber(p)) return 0.0;
   ok=true;
   return MathAbs(p);
  }

double IntentResidualRiskUsd(const QrosIntent &x)
  {
   if(x.state!=QI_RESERVED && x.state!=QI_SENT_UNKNOWN && x.state!=QI_WORKING && x.state!=QI_PARTIAL) return 0.0;
   if(!(x.risk_usd>=0.0) || !MathIsValidNumber(x.risk_usd)) return 1.0e308;
   if(x.state!=QI_PARTIAL) return x.risk_usd;
   double filled=0.0;
   ulong pt=x.position_ticket;
   if(pt==0) pt=FindQrosPosition(SymbolFor(x.module_id),x.magic,IntentComment(x.id));
   if(pt>0 && PositionSelectByTicket(pt)) filled=PositionGetDouble(POSITION_VOLUME);
   if(!(x.volume>0.0) || filled<=0.0) return x.risk_usd;
   double remaining=MathMax(0.0,x.volume-filled);
   return x.risk_usd*(remaining/x.volume);
  }

int FindIntentForPosition(const ulong ticket,const long magic)
  {
   for(int i=0;i<QROS_INTENT_SLOTS;i++)
     {
      if(!g_intents[i].used || IntentTerminal(g_intents[i].state)) continue;
      if(g_intents[i].position_ticket==ticket) return i;
      if(g_intents[i].magic==magic && g_intents[i].state>=QI_PARTIAL) return i;
     }
   return -1;
  }

double ReservedRiskUsd(bool &ok)
  {
   ok=true;
   double total=0.0;

   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      long magic=(long)PositionGetInteger(POSITION_MAGIC);
      if(!IsQrosMagic(magic)) continue;
      bool rok=false;double r=PositionRiskUsd(ticket,rok);
      if(!rok){ok=false;return 0.0;}
      int ix=FindIntentForPosition(ticket,magic);
      if(ix>=0 && g_intents[ix].volume>0.0 && g_intents[ix].risk_usd>=0.0)
        {
         double pv=PositionGetDouble(POSITION_VOLUME);
         double floor_r=g_intents[ix].risk_usd*MathMin(1.0,MathMax(0.0,pv/g_intents[ix].volume));
         if(floor_r>r) r=floor_r;
        }
      total+=r;
     }

   for(int i=OrdersTotal()-1;i>=0;i--)
     {
      ulong ticket=OrderGetTicket(i);
      if(ticket==0) continue;
      long magic=(long)OrderGetInteger(ORDER_MAGIC);
      if(!IsQrosMagic(magic)) continue;
      if(IsOrderLinkedToIntent(ticket)) continue;
      bool rok=false;double r=OrderRiskUsd(ticket,rok);
      if(!rok){ok=false;return 0.0;}
      total+=r;
     }

   for(int i=0;i<QROS_INTENT_SLOTS;i++)
     {
      if(!g_intents[i].used || IntentTerminal(g_intents[i].state)) continue;
      double r=IntentResidualRiskUsd(g_intents[i]);
      if(r==1.0e308 || !MathIsValidNumber(r)){ok=false;return 0.0;}
      total+=r;
     }
   return total;
  }

bool CountedOrderContains(const ulong order_ticket)
  {
   if(order_ticket==0) return false;
   for(int i=0;i<ArraySize(g_counted_orders);i++) if(g_counted_orders[i]==order_ticket) return true;
   return false;
  }

void CountedOrderAppend(const ulong order_ticket)
  {
   if(order_ticket==0 || CountedOrderContains(order_ticket)) return;
   int n=ArraySize(g_counted_orders);ArrayResize(g_counted_orders,n+1);g_counted_orders[n]=order_ticket;
  }

ulong FindHistoricalEntryOrderForIntent(const QrosIntent &x)
  {
   datetime from=(datetime)(x.event_ms/1000L)-120;
   datetime to=TimeTradeServer()+120;
   if(!HistorySelect(from,to)) return 0;
   string comment=IntentComment(x.id);
   int n=HistoryDealsTotal();
   for(int k=0;k<n;k++)
     {
      ulong d=HistoryDealGetTicket(k);if(d==0) continue;
      if((long)HistoryDealGetInteger(d,DEAL_MAGIC)!=x.magic) continue;
      long entry=(long)HistoryDealGetInteger(d,DEAL_ENTRY);
      if(entry!=DEAL_ENTRY_IN && entry!=DEAL_ENTRY_INOUT) continue;
      string c=HistoryDealGetString(d,DEAL_COMMENT);
      ulong ord=(ulong)HistoryDealGetInteger(d,DEAL_ORDER);
      if(c==comment || (x.order_ticket>0 && ord==x.order_ticket)) return ord;
     }
   return 0;
  }


ulong FindHistoricalOrderForIntent(const QrosIntent &x)
  {
   datetime from=(datetime)(x.event_ms/1000L)-120;
   datetime to=TimeTradeServer()+120;
   if(!HistorySelect(from,to)) return 0;
   if(x.order_ticket>0 && HistoryOrderSelect(x.order_ticket)) return x.order_ticket;
   string comment=IntentComment(x.id);
   int n=HistoryOrdersTotal();
   for(int k=0;k<n;k++)
     {
      ulong o=HistoryOrderGetTicket(k);if(o==0) continue;
      if((long)HistoryOrderGetInteger(o,ORDER_MAGIC)!=x.magic) continue;
      string c=HistoryOrderGetString(o,ORDER_COMMENT);
      long oms=(long)HistoryOrderGetInteger(o,ORDER_TIME_SETUP_MSC);
      if(c==comment || MathAbs((double)(oms-x.event_ms))<=120000.0) return o;
     }
   return 0;
  }

bool RebuildDailyCount()
  {
   datetime from=ServerDayStart();
   datetime to=TimeTradeServer()+60;
   if(!HistorySelect(from,to))
     {
      g_history_ready=false;
      SetEntryFault("HISTORY_UNAVAILABLE");
      return false;
     }

   ulong seen[];ArrayResize(seen,0);
   ArrayResize(g_counted_orders,0);
   int count=0;
   int n=HistoryDealsTotal();
   for(int i=0;i<n;i++)
     {
      ulong d=HistoryDealGetTicket(i);
      if(d==0) continue;
      long magic=(long)HistoryDealGetInteger(d,DEAL_MAGIC);
      if(!IsQrosMagic(magic)) continue;
      long entry=(long)HistoryDealGetInteger(d,DEAL_ENTRY);
      if(entry!=DEAL_ENTRY_IN && entry!=DEAL_ENTRY_INOUT) continue;
      ulong ord=(ulong)HistoryDealGetInteger(d,DEAL_ORDER);
      if(ord==0) ord=d;
      bool exists=false;
      for(int j=0;j<ArraySize(seen);j++) if(seen[j]==ord){exists=true;break;}
      if(!exists)
        {
         int z=ArraySize(seen);ArrayResize(seen,z+1);seen[z]=ord;CountedOrderAppend(ord);count++;
        }
     }
   g_day_entries=count;
   g_last_day_key=ServerDayKey();
   g_history_ready=true;

   string kday="Q24.EXEC.DAY";
   string kev="Q24.EXEC.LASTEV";
   long pday=0,pev=0;
   if(GvGetExactLong(kday,pday) && pday==g_last_day_key && GvGetExactLong(kev,pev))
      g_last_accepted_event_ms=pev;
   else
      g_last_accepted_event_ms=-1;
   return true;
  }

void RefreshDay()
  {
   int dk=ServerDayKey();
   if(dk!=g_last_day_key)
     {
      if(!RebuildDailyCount()) return;
      g_last_accepted_event_ms=-1;
      if(!GvSet("Q24.EXEC.DAY",(double)dk)) SetEntryFault("DAY_STATE_WRITE_FAILED");
      if(!GvSet("Q24.EXEC.LASTEV",-1.0)) SetEntryFault("LASTEV_STATE_WRITE_FAILED");
      GlobalVariablesFlush();
     }
  }

int ReservedEntrySlotsToday()
  {
   int dk=ServerDayKey();int n=0;
   for(int i=0;i<QROS_INTENT_SLOTS;i++)
     {
      if(!g_intents[i].used || IntentTerminal(g_intents[i].state)) continue;
      if(g_intents[i].day_key!=dk || g_intents[i].counted!=0) continue;
      if(g_intents[i].state==QI_RESERVED || g_intents[i].state==QI_SENT_UNKNOWN || g_intents[i].state==QI_WORKING || g_intents[i].state==QI_PARTIAL) n++;
     }
   return n;
  }

bool ReserveIntent(const QrosBusEvent &ev,const long magic,const double risk_usd,const double volume,const double sl,const double tp,int &slot)
  {
   slot=-1;
   long id=IntentId(ev);
   if(id<=0) return false;
   int existing=FindIntentById(id);
   if(existing>=0)
     {
      slot=existing;
      return false;
     }
   int s=FindFreeIntentSlot();
   if(s<0){SetEntryFault("INTENT_SLOTS_EXHAUSTED");return false;}
   if(g_intents[s].used) ClearIntent(s);
   QrosIntent x;ZeroMemory(x);
   x.used=true;x.slot=s;x.id=id;x.state=QI_RESERVED;x.module_id=ev.module_id;x.profile=ev.profile;
   x.event_ms=ev.event_ms;x.magic=magic;x.risk_usd=risk_usd;x.volume=volume;x.sl=sl;x.tp=tp;
   x.day_key=ServerDayKey();x.counted=0;x.created_uptime_ms=(long)GetTickCount64();x.reconcile_attempts=0;
   g_intents[s]=x;
   if(!SaveIntent(s)){ClearIntent(s);return false;}
   slot=s;
   return true;
  }

void MarkIntentTerminal(const int i,const int state,const string reason)
  {
   if(i<0 || i>=QROS_INTENT_SLOTS || !g_intents[i].used) return;
   g_intents[i].state=state;
   if(!SaveIntent(i)) return;
   QrosBusEvent ev;ZeroMemory(ev);ev.module_id=g_intents[i].module_id;ev.profile=g_intents[i].profile;ev.event_ms=g_intents[i].event_ms;
   LogRow("INTENT","TERMINAL",ev,reason,g_intents[i].id,state,SymbolFor(g_intents[i].module_id),0,0,g_intents[i].volume,g_intents[i].sl,g_intents[i].tp,g_intents[i].order_ticket,g_intents[i].deal_ticket,g_intents[i].position_ticket,0);
   // Keep a same-day tombstone. FindFreeIntentSlot only recycles terminal slots from prior server days.
  }

int FindFreeMgmtSlot()
  {
   for(int i=0;i<QROS_MGMT_SLOTS;i++) if(!g_mgmt[i].used || g_mgmt[i].state==QM_DONE) return i;
   return -1;
  }

int FindMgmt(const int action,const long entry_intent_id,const ulong ticket)
  {
   for(int i=0;i<QROS_MGMT_SLOTS;i++)
     {
      if(!g_mgmt[i].used || g_mgmt[i].state==QM_DONE) continue;
      if(g_mgmt[i].action!=action) continue;
      if(entry_intent_id>0 && g_mgmt[i].entry_intent_id==entry_intent_id) return i;
      if(ticket>0 && g_mgmt[i].position_ticket==ticket) return i;
     }
   return -1;
  }

bool EnqueueMgmt(const QrosBusEvent &ev,const int action,const long entry_intent_id,const ulong ticket,const ulong order_ticket,const double sl,const double tp)
  {
   int old=FindMgmt(action,entry_intent_id,ticket);
   if(old>=0)
     {
      if(action==QROS_ACT_MODIFY_SL && sl>g_mgmt[old].sl){g_mgmt[old].sl=sl;g_mgmt[old].tp=tp;SaveMgmt(old);}
      return true;
     }
   int s=FindFreeMgmtSlot();
   if(s<0){SetMgmtFault("MGMT_SLOTS_EXHAUSTED");return false;}
   if(g_mgmt[s].used) ClearMgmt(s);
   QrosMgmtIntent m;ZeroMemory(m);
   m.used=true;m.slot=s;m.state=QM_PENDING;m.action=action;m.module_id=ev.module_id;m.profile=ev.profile;m.event_ms=ev.event_ms;
   m.entry_intent_id=entry_intent_id;m.position_ticket=ticket;m.order_ticket=order_ticket;m.sl=sl;m.tp=tp;m.attempts=0;m.next_retry_uptime_ms=0;
   long base=(ev.event_ms>0?ev.event_ms:(long)TimeTradeServer()*1000L);
   m.id=base*1000LL+(long)action*100LL+(long)(s+1);
   if(!ExactLongForDouble(m.id)) m.id=224000000LL+s;
   g_mgmt[s]=m;
   return SaveMgmt(s);
  }

void CancelPendingEntriesForModule(const int module_id,const int profile,const long close_ms)
  {
   int w=0;
   for(int i=0;i<ArraySize(g_pending);i++)
     {
      bool cancel=(g_pending[i].ev.module_id==module_id && g_pending[i].ev.profile==profile && g_pending[i].ev.event_ms<=close_ms);
      if(!cancel)
        {
         if(w!=i) g_pending[w]=g_pending[i];
         w++;
        }
     }
   if(w<ArraySize(g_pending)) ArrayResize(g_pending,w);
  }

bool CancelWorkingOrder(const ulong ticket,uint &rc)
  {
   rc=0;
   if(ticket==0 || !OrderSelect(ticket)) return true;
   if(!MgmtTradeGate()) return false;
   ResetLastError();
   bool ok=g_trade.OrderDelete(ticket);
   rc=g_trade.ResultRetcode();
   if(ok && (rc==TRADE_RETCODE_DONE || rc==TRADE_RETCODE_NO_CHANGES) && !OrderSelect(ticket)) return true;
   return false;
  }

bool TryMgmtIntent(const int i)
  {
   if(i<0 || i>=QROS_MGMT_SLOTS || !g_mgmt[i].used) return true;
   QrosMgmtIntent m=g_mgmt[i];
   string symbol=SymbolFor(m.module_id);
   long magic=MagicFor(m.module_id,m.profile);
   if(symbol=="" || magic<0){SetMgmtFault("MGMT_INVALID_MODULE");return false;}

   int ix=(m.entry_intent_id>0?FindIntentById(m.entry_intent_id):-1);
   if(m.order_ticket==0 && ix>=0) m.order_ticket=g_intents[ix].order_ticket;
   if(m.position_ticket==0 && ix>=0) m.position_ticket=g_intents[ix].position_ticket;
   if(m.position_ticket==0) m.position_ticket=FindQrosPosition(symbol,magic,(ix>=0?IntentComment(g_intents[ix].id):""));
   if(m.order_ticket==0 && ix>=0) m.order_ticket=FindCurrentOrder(symbol,magic,IntentComment(g_intents[ix].id));

   QrosBusEvent ev;ZeroMemory(ev);ev.module_id=m.module_id;ev.profile=m.profile;ev.event_ms=m.event_ms;ev.action=m.action;
   uint rc=0;

   if(m.action==QROS_ACT_CLOSE)
     {
      if(m.order_ticket>0 && OrderSelect(m.order_ticket))
        {
         if(!CancelWorkingOrder(m.order_ticket,rc))
           {
            m.attempts++;m.next_retry_uptime_ms=(long)GetTickCount64()+(m.attempts<5?2000:30000);g_mgmt[i]=m;SaveMgmt(i);
            LogRow("CLOSE","ORDER_CANCEL_RETRY",ev,"RETCODE_"+IntegerToString((int)rc),m.entry_intent_id,m.state,symbol,0,0,0,0,0,m.order_ticket,0,m.position_ticket,rc);
            return false;
           }
         m.order_ticket=0;g_mgmt[i]=m;SaveMgmt(i);
        }

      ulong ticket=m.position_ticket;
      if(ticket==0 || !PositionSelectByTicket(ticket))
        {
         ticket=FindQrosPosition(symbol,magic,(ix>=0?IntentComment(g_intents[ix].id):""));
         m.position_ticket=ticket;
        }
      if(ticket==0 || !PositionSelectByTicket(ticket))
        {
         m.state=QM_DONE;g_mgmt[i]=m;SaveMgmt(i);ClearMgmt(i);
         if(ix>=0) MarkIntentTerminal(ix,QI_CLOSED,"POSITION_CONFIRMED_CLOSED");
         return true;
        }
      if(!MgmtTradeGate())
        {
         m.attempts++;m.next_retry_uptime_ms=(long)GetTickCount64()+2000;g_mgmt[i]=m;SaveMgmt(i);
         return false;
        }
      g_trade.SetExpertMagicNumber((ulong)magic);
      if(!g_trade.SetTypeFillingBySymbol(symbol)){SetMgmtFault("CLOSE_FILLING_MODE_UNAVAILABLE");return false;}
      ResetLastError();
      bool ok=g_trade.PositionClose(ticket);
      rc=g_trade.ResultRetcode();
      bool gone=!PositionSelectByTicket(ticket);
      if(ok && (rc==TRADE_RETCODE_DONE || rc==TRADE_RETCODE_DONE_PARTIAL) && gone)
        {
         LogRow("CLOSE","CONFIRMED",ev,"POSITION_ABSENT",m.entry_intent_id,QM_DONE,symbol,0,0,0,0,0,m.order_ticket,0,ticket,rc);
         m.state=QM_DONE;g_mgmt[i]=m;SaveMgmt(i);ClearMgmt(i);
         if(ix>=0) MarkIntentTerminal(ix,QI_CLOSED,"CLOSE_CONFIRMED");
         return true;
        }
      m.attempts++;
      if(m.attempts>=5){m.state=QM_ESCALATED;SetMgmtFault("CLOSE_NOT_CONFIRMED");}
      m.next_retry_uptime_ms=(long)GetTickCount64()+(m.attempts<5?2000:30000);g_mgmt[i]=m;SaveMgmt(i);
      LogRow("CLOSE","RETRY",ev,"RETCODE_"+IntegerToString((int)rc),m.entry_intent_id,m.state,symbol,0,0,0,0,0,m.order_ticket,0,ticket,rc);
      return false;
     }

   if(m.action==QROS_ACT_MODIFY_SL)
     {
      ulong ticket=m.position_ticket;
      if(ticket==0 || !PositionSelectByTicket(ticket))
        {
         ticket=FindQrosPosition(symbol,magic,(ix>=0?IntentComment(g_intents[ix].id):""));
         m.position_ticket=ticket;
        }
      if(ticket==0 || !PositionSelectByTicket(ticket))
        {
         // Position may not be visible yet; keep the management intent while entry is unresolved.
         if(ix>=0 && !IntentTerminal(g_intents[ix].state))
           {m.next_retry_uptime_ms=(long)GetTickCount64()+1000;g_mgmt[i]=m;SaveMgmt(i);return false;}
         m.state=QM_DONE;g_mgmt[i]=m;SaveMgmt(i);ClearMgmt(i);return true;
        }
      double oldsl=PositionGetDouble(POSITION_SL);
      double oldtp=PositionGetDouble(POSITION_TP);
      double sl=GridNormalize(symbol,m.sl);
      double tp=(m.tp>0.0?GridNormalize(symbol,m.tp):oldtp);
      if(oldsl>0.0 && oldsl>=sl && PriceSameGrid(symbol,oldtp,tp))
        {m.state=QM_DONE;g_mgmt[i]=m;SaveMgmt(i);ClearMgmt(i);return true;}
      if(!MgmtTradeGate())
        {m.attempts++;m.next_retry_uptime_ms=(long)GetTickCount64()+2000;g_mgmt[i]=m;SaveMgmt(i);return false;}
      g_trade.SetExpertMagicNumber((ulong)magic);
      MqlTick mt;if(!FreshExecutableTick(symbol,mt)){m.attempts++;m.next_retry_uptime_ms=(long)GetTickCount64()+2000;g_mgmt[i]=m;SaveMgmt(i);return false;}
      if(!BarriersTradableBuy(symbol,mt.bid,mt.ask,sl,tp)){m.attempts++;m.next_retry_uptime_ms=(long)GetTickCount64()+2000;g_mgmt[i]=m;SaveMgmt(i);return false;}
      ResetLastError();
      bool ok=g_trade.PositionModify(ticket,sl,tp);
      rc=g_trade.ResultRetcode();
      bool observed=false;
      if(PositionSelectByTicket(ticket))
        {
         double nsl=PositionGetDouble(POSITION_SL),ntp=PositionGetDouble(POSITION_TP);
         observed=(nsl>0.0 && nsl>=sl && PriceSameGrid(symbol,ntp,tp));
        }
      if(ok && (rc==TRADE_RETCODE_DONE || rc==TRADE_RETCODE_NO_CHANGES) && observed)
        {
         LogRow("MODIFY","CONFIRMED",ev,"BARRIER_OBSERVED",m.entry_intent_id,QM_DONE,symbol,0,0,0,sl,tp,0,0,ticket,rc);
         m.state=QM_DONE;g_mgmt[i]=m;SaveMgmt(i);ClearMgmt(i);return true;
        }
      m.attempts++;
      if(m.attempts>=3)
        {
         // Protection could not be confirmed. Escalate to close, which only reduces risk.
         m.action=QROS_ACT_CLOSE;m.state=QM_ESCALATED;m.attempts=0;m.next_retry_uptime_ms=(long)GetTickCount64()+1000;
         g_mgmt[i]=m;SaveMgmt(i);SetMgmtFault("PROTECTION_NOT_CONFIRMED_ESCALATE_CLOSE");
         return false;
        }
      m.next_retry_uptime_ms=(long)GetTickCount64()+2000;g_mgmt[i]=m;SaveMgmt(i);
      LogRow("MODIFY","RETRY",ev,"RETCODE_"+IntegerToString((int)rc),m.entry_intent_id,m.state,symbol,0,0,0,sl,tp,0,0,ticket,rc);
      return false;
     }
   return false;
  }

void ProcessMgmt()
  {
   long now=(long)GetTickCount64();
   for(int i=0;i<QROS_MGMT_SLOTS;i++)
     {
      if(!g_mgmt[i].used || g_mgmt[i].state==QM_DONE) continue;
      if(g_mgmt[i].next_retry_uptime_ms>now) continue;
      TryMgmtIntent(i);
     }
  }

void ConfirmIntentCounted(const int i)
  {
   if(i<0 || i>=QROS_INTENT_SLOTS || !g_intents[i].used || g_intents[i].counted!=0) return;
   ulong ord=g_intents[i].order_ticket;
   if(ord==0) ord=FindHistoricalEntryOrderForIntent(g_intents[i]);
   if(ord>0 && g_intents[i].order_ticket==0) g_intents[i].order_ticket=ord;

   // RebuildDailyCount may already have counted this broker entry after a crash.
   // Never double-increment the daily cap for the same broker order.
   if(ord==0 || !CountedOrderContains(ord))
     {
      g_day_entries++;
      if(ord>0) CountedOrderAppend(ord);
     }
   g_intents[i].counted=1;
   g_last_accepted_event_ms=g_intents[i].event_ms;
   if(!GvSet("Q24.EXEC.DAY",(double)ServerDayKey()) || !GvSet("Q24.EXEC.LASTEV",(double)g_last_accepted_event_ms))
      SetEntryFault("DAILY_COUNT_PERSIST_FAILED");
   SaveIntent(i);
  }

void CheckPostFillRisk(const int i)
  {
   if(i<0 || i>=QROS_INTENT_SLOTS || !g_intents[i].used) return;
   if(g_intents[i].position_ticket>0)
     {
      bool pok=false;double pr=PositionRiskUsd(g_intents[i].position_ticket,pok);
      if(!pok){SetEntryFault("POST_FILL_POSITION_RISK_UNKNOWN");return;}
      if(pr>g_intents[i].risk_usd+0.01)
        {
         SetEntryFault("POST_FILL_SINGLE_TRADE_RISK_OVER_PLAN");
         QrosBusEvent cev;ZeroMemory(cev);cev.module_id=g_intents[i].module_id;cev.profile=g_intents[i].profile;cev.event_ms=(long)TimeTradeServer()*1000L;cev.action=QROS_ACT_CLOSE;
         EnqueueMgmt(cev,QROS_ACT_CLOSE,g_intents[i].id,g_intents[i].position_ticket,g_intents[i].order_ticket,0,0);
        }
     }
   bool ok=false;double total=ReservedRiskUsd(ok);
   double bal=AccountInfoDouble(ACCOUNT_BALANCE);
   double maxr=bal*(InpMaxReservedRiskPct/100.0);
   if(!ok || !MathIsValidNumber(total))
     {
      SetEntryFault("POST_FILL_RISK_UNKNOWN");
      return;
     }
   if(total>maxr+0.01)
     {
      SetEntryFault("POST_FILL_RESERVED_RISK_OVER_1PCT");
      QrosBusEvent ev;ZeroMemory(ev);ev.module_id=g_intents[i].module_id;ev.profile=g_intents[i].profile;ev.event_ms=(long)TimeTradeServer()*1000L;ev.action=QROS_ACT_CLOSE;
      EnqueueMgmt(ev,QROS_ACT_CLOSE,g_intents[i].id,g_intents[i].position_ticket,g_intents[i].order_ticket,0,0);
     }
  }

void ReconcileIntent(const int i)
  {
   if(i<0 || i>=QROS_INTENT_SLOTS || !g_intents[i].used || IntentTerminal(g_intents[i].state)) return;
   QrosIntent x=g_intents[i];
   string symbol=SymbolFor(x.module_id);
   string comment=IntentComment(x.id);

   if(x.state==QI_RESERVED)
     {
      // RESERVED is persisted before SENT_UNKNOWN. A restart in RESERVED means no broker send was authorized yet.
      MarkIntentTerminal(i,QI_CANCELLED,"RESERVED_BEFORE_SEND_RECOVERY");
      return;
     }

   ulong pos=x.position_ticket;
   if(pos==0 || !PositionSelectByTicket(pos)) pos=FindQrosPosition(symbol,x.magic,comment);
   ulong ord=x.order_ticket;
   if(ord==0 || !OrderSelect(ord)) ord=FindCurrentOrder(symbol,x.magic,comment);
   if(pos>0) x.position_ticket=pos;
   if(ord>0) x.order_ticket=ord;

   bool position_exists=(pos>0 && PositionSelectByTicket(pos));
   bool order_exists=(ord>0 && OrderSelect(ord));

   if(position_exists)
     {
      double pvol=PositionGetDouble(POSITION_VOLUME);
      double psl=PositionGetDouble(POSITION_SL);
      double ptp=PositionGetDouble(POSITION_TP);
      bool protected_ok=ProtectionAtLeastRequestedBuy(symbol,psl,ptp,x.sl,x.tp);
      ConfirmIntentCounted(i);
      if(!protected_ok)
        {
         SetEntryFault("POSITION_NOT_PROTECTED_AS_REQUESTED");
         QrosBusEvent ev;ZeroMemory(ev);ev.module_id=x.module_id;ev.profile=x.profile;ev.event_ms=(long)TimeTradeServer()*1000L;ev.action=QROS_ACT_MODIFY_SL;
         EnqueueMgmt(ev,QROS_ACT_MODIFY_SL,x.id,pos,ord,x.sl,x.tp);
        }
      if(order_exists && pvol<x.volume)
         x.state=QI_PARTIAL;
      else if(protected_ok)
         x.state=QI_FILLED_PROTECTED;
      else
         x.state=QI_PARTIAL;
      x.reconcile_attempts++;
      g_intents[i]=x;SaveIntent(i);
      CheckPostFillRisk(i);
      return;
     }

   if(order_exists)
     {
      double cur=OrderGetDouble(ORDER_VOLUME_CURRENT);
      double ini=OrderGetDouble(ORDER_VOLUME_INITIAL);
      x.state=(cur<ini?QI_PARTIAL:QI_WORKING);
      x.reconcile_attempts++;g_intents[i]=x;SaveIntent(i);return;
     }

   // Current inventory is absent. Consult history only after a successful HistorySelect.
   datetime from=(datetime)(x.event_ms/1000L)-120;
   datetime to=TimeTradeServer()+120;
   if(!HistorySelect(from,to))
     {
      SetEntryFault("RECONCILE_HISTORY_UNAVAILABLE");
      x.reconcile_attempts++;g_intents[i]=x;SaveIntent(i);return;
     }

   bool deal_seen=false;
   if(x.deal_ticket>0 && HistoryDealSelect(x.deal_ticket)) deal_seen=true;
   if(!deal_seen)
     {
      int n=HistoryDealsTotal();
      for(int k=0;k<n;k++)
        {
         ulong d=HistoryDealGetTicket(k);if(d==0) continue;
         if((long)HistoryDealGetInteger(d,DEAL_MAGIC)!=x.magic) continue;
         string c=HistoryDealGetString(d,DEAL_COMMENT);
         ulong dor=(ulong)HistoryDealGetInteger(d,DEAL_ORDER);
         if(c==comment || (x.order_ticket>0 && dor==x.order_ticket)){x.deal_ticket=d;if(x.order_ticket==0)x.order_ticket=dor;deal_seen=true;break;}
        }
     }

   if(deal_seen)
     {
      ConfirmIntentCounted(i);
      MarkIntentTerminal(i,QI_CLOSED,"HISTORY_DEAL_POSITION_ALREADY_CLOSED");
      return;
     }

   ulong hist_order=FindHistoricalOrderForIntent(x);
   if(hist_order>0 && HistoryOrderSelect(hist_order))
     {
      x.order_ticket=hist_order;g_intents[i]=x;SaveIntent(i);
      ENUM_ORDER_STATE st=(ENUM_ORDER_STATE)HistoryOrderGetInteger(hist_order,ORDER_STATE);
      if(st==ORDER_STATE_CANCELED || st==ORDER_STATE_EXPIRED)
        {MarkIntentTerminal(i,QI_CANCELLED,"HISTORY_ORDER_CANCELLED");return;}
      if(st==ORDER_STATE_REJECTED)
        {MarkIntentTerminal(i,QI_REJECTED,"HISTORY_ORDER_REJECTED");return;}
     }

   x.reconcile_attempts++;
   g_intents[i]=x;SaveIntent(i);
   long age=(long)TimeTradeServer()*1000L-x.event_ms;
   if(age>300000)
     {
      // Lost ACK without authoritative cancellation remains reserved and blocks new risk.
      SetEntryFault("SENT_UNKNOWN_UNRESOLVED");
     }
  }

void ReconcileAllIntents()
  {
   for(int i=0;i<QROS_INTENT_SLOTS;i++) if(g_intents[i].used && !IntentTerminal(g_intents[i].state)) ReconcileIntent(i);
  }

void AddPending(const QrosBusEvent &ev)
  {
   PendingEntry p;p.ev=ev;p.received_uptime_ms=(long)GetTickCount64();
   int n=ArraySize(g_pending);ArrayResize(g_pending,n+1);g_pending[n]=p;
  }

bool Before(const PendingEntry &a,const PendingEntry &b)
  {
   if(a.ev.event_ms!=b.ev.event_ms) return a.ev.event_ms<b.ev.event_ms;
   int pa=PriorityFor(a.ev.module_id),pb=PriorityFor(b.ev.module_id);
   if(pa!=pb) return pa<pb;
   return a.ev.profile<b.ev.profile;
  }

void SortPending()
  {
   int n=ArraySize(g_pending);
   for(int i=1;i<n;i++)
     {
      PendingEntry key=g_pending[i];int j=i-1;
      while(j>=0 && Before(key,g_pending[j])){g_pending[j+1]=g_pending[j];j--;}
      g_pending[j+1]=key;
     }
  }

bool CohortReady(const long event_ms)
  {
   for(int m=1;m<=3;m++) if(QrosBusWatermarkMs(m)<event_ms) return false;
   return true;
  }

bool EventAgeSafe(const long event_ms)
  {
   long nowms=(long)TimeTradeServer()*1000L;
   long age=nowms-event_ms;
   if(age<-2000) return false;
   return age<=InpEventMaxAgeMs;
  }

bool HasOldDayQrosInventory()
  {
   int dk=ServerDayKey();
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong t=PositionGetTicket(i);if(t==0 || !PositionSelectByTicket(t)) continue;
      if(!IsQrosMagic((long)PositionGetInteger(POSITION_MAGIC))) continue;
      long pms=(long)PositionGetInteger(POSITION_TIME_MSC);
      if(pms<=0) pms=(long)PositionGetInteger(POSITION_TIME)*1000L;
      if(DayKeyFromMs(pms)!=dk) return true;
     }
   for(int i=OrdersTotal()-1;i>=0;i--)
     {
      ulong t=OrderGetTicket(i);if(t==0) continue;
      if(!IsQrosMagic((long)OrderGetInteger(ORDER_MAGIC))) continue;
      long oms=(long)OrderGetInteger(ORDER_TIME_SETUP_MSC);
      if(oms<=0) oms=(long)OrderGetInteger(ORDER_TIME_SETUP)*1000L;
      if(DayKeyFromMs(oms)!=dk) return true;
     }
   return false;
  }

bool SendEntry(const QrosBusEvent &ev)
  {
   string symbol=SymbolFor(ev.module_id);
   long magic=MagicFor(ev.module_id,ev.profile);
   MqlTick tick;
   if(symbol=="" || magic<0){LogRow("ENTRY","BLOCKED",ev,"INVALID_MODULE_PROFILE",0,0,symbol,0,0,0,ev.sl,ev.tp);return false;}
   if(g_entry_fault || g_bus_fault){LogRow("ENTRY","BLOCKED",ev,(g_entry_fault?g_entry_fault_reason:g_bus_fault_reason),0,0,symbol,0,0,0,ev.sl,ev.tp);return false;}
   if(g_recert_required){LogRow("ENTRY","BLOCKED",ev,"RECERT_REQUIRED",0,0,symbol,0,0,0,ev.sl,ev.tp);return false;}
   if(g_recovery_lock || HasOldDayQrosInventory()){LogRow("ENTRY","BLOCKED",ev,"RECOVERY_OR_OLD_DAY_INVENTORY",0,0,symbol,0,0,0,ev.sl,ev.tp);return false;}
   if(!SessionEntrySafe(symbol)){LogRow("ENTRY","BLOCKED",ev,"SESSION_DEADLINE_UNKNOWN_OR_REACHED",0,0,symbol,0,0,0,ev.sl,ev.tp);return false;}
   if(!EventAgeSafe(ev.event_ms)){LogRow("ENTRY","BLOCKED",ev,"STALE_OR_FUTURE_EVENT",0,0,symbol,0,0,0,ev.sl,ev.tp);return false;}
   if(InpArmDemoOrders && !RuntimeCertified()){LogRow("ENTRY","BLOCKED",ev,"RUNTIME_NOT_CERTIFIED",0,0,symbol,0,0,0,ev.sl,ev.tp);return false;}
   if(!HeartbeatsReady()){LogRow("ENTRY","BLOCKED",ev,"HEARTBEAT_NOT_READY",0,0,symbol,0,0,0,ev.sl,ev.tp);return false;}
   if(!FreshExecutableTick(symbol,tick)){LogRow("ENTRY","BLOCKED",ev,"NON_EXECUTABLE_OR_STALE_TICK",0,0,symbol,tick.bid,tick.ask,0,ev.sl,ev.tp);return false;}

   RefreshDay();
   if(g_entry_fault || !g_history_ready) return false;
   if(g_day_entries+ReservedEntrySlotsToday()>=InpMaxNewEntriesPerServerDay)
     {LogRow("ENTRY","BLOCKED",ev,"DAILY_CAP_3_RESERVED",0,0,symbol,tick.bid,tick.ask,0,ev.sl,ev.tp);return false;}
   if(ev.event_ms==g_last_accepted_event_ms || ActiveIntentAtTimestamp(ev.event_ms))
     {LogRow("ENTRY","BLOCKED",ev,"SIMULTANEOUS_ENTRY",0,0,symbol,tick.bid,tick.ask,0,ev.sl,ev.tp);return false;}
   if(AnyPositionOnAsset(symbol) || ActiveIntentOnAsset(symbol))
     {LogRow("ENTRY","BLOCKED",ev,"ASSET_OCCUPIED_OR_RESERVED",0,0,symbol,tick.bid,tick.ask,0,ev.sl,ev.tp);return false;}

   double sl=GridNormalize(symbol,ev.sl);
   double tp=GridNormalize(symbol,ev.tp);
   if(!BarriersTradableBuy(symbol,tick.bid,tick.ask,sl,tp))
     {LogRow("ENTRY","BLOCKED",ev,"INVALID_OR_UNTRADABLE_BARRIERS",0,0,symbol,tick.bid,tick.ask,0,sl,tp);return false;}

   QrosRiskResult rr;
   double bal=AccountInfoDouble(ACCOUNT_BALANCE);
   if(!QrosRiskSize(symbol,ORDER_TYPE_BUY,tick.ask,sl,bal,InpRiskPctBalance,rr))
     {LogRow("ENTRY","BLOCKED",ev,"RISK_"+rr.reason,0,0,symbol,tick.bid,tick.ask,0,sl,tp);return false;}
   if(!MathIsValidNumber(rr.actual_risk_usd) || !MathIsValidNumber(rr.volume) || !(rr.actual_risk_usd>0.0) || !(rr.volume>0.0))
     {SetEntryFault("RISK_RESULT_NONFINITE");return false;}

   bool rok=false;double reserved=ReservedRiskUsd(rok);
   if(!rok){SetEntryFault("RESERVED_RISK_UNKNOWN");return false;}
   double maxr=bal*(InpMaxReservedRiskPct/100.0);
   if(reserved+rr.actual_risk_usd>maxr+0.01)
     {LogRow("ENTRY","BLOCKED",ev,"MAX_RESERVED_RISK_1PCT",0,0,symbol,tick.bid,tick.ask,rr.volume,sl,tp);return false;}

   if(!InpArmDemoOrders)
     {LogRow("ENTRY","CANARY_BLOCKED",ev,"ORDERS_NOT_ARMED",0,0,symbol,tick.bid,tick.ask,rr.volume,sl,tp);return false;}
   if(!EntryTradeGate()) return false;
   g_trade.SetExpertMagicNumber((ulong)magic);
   if(!g_trade.SetTypeFillingBySymbol(symbol)){RequireRecert("FILLING_MODE_UNAVAILABLE");return false;}
   g_trade.SetAsyncMode(false);

   // Revalidate quote/spread/session immediately before reserving and sending.
   MqlTick sendtick;
   if(!FreshExecutableTick(symbol,sendtick) || !SessionEntrySafe(symbol) || !BarriersTradableBuy(symbol,sendtick.bid,sendtick.ask,sl,tp))
     {LogRow("ENTRY","BLOCKED",ev,"PRE_SEND_REVALIDATION_FAILED",0,0,symbol,sendtick.bid,sendtick.ask,rr.volume,sl,tp);return false;}
   QrosRiskResult rr_send;
   if(!QrosRiskSize(symbol,ORDER_TYPE_BUY,sendtick.ask,sl,bal,InpRiskPctBalance,rr_send))
     {LogRow("ENTRY","BLOCKED",ev,"PRE_SEND_RISK_"+rr_send.reason,0,0,symbol,sendtick.bid,sendtick.ask,0,sl,tp);return false;}
   if(rr_send.actual_risk_usd>rr.actual_risk_usd+0.01 || rr_send.volume>rr.volume+1e-12)
     {rr=rr_send;reserved=ReservedRiskUsd(rok);if(!rok || reserved+rr.actual_risk_usd>maxr+0.01) return false;}
   else rr=rr_send;

   int slot=-1;
   if(!ReserveIntent(ev,magic,rr.actual_risk_usd,rr.volume,sl,tp,slot))
     {LogRow("ENTRY","BLOCKED",ev,"INTENT_RESERVATION_FAILED",0,0,symbol,tick.bid,tick.ask,rr.volume,sl,tp);return false;}
   QrosIntent x=g_intents[slot];

   // Timestamp is durably consumed when a broker send is about to occur, not after ACK.
   g_last_accepted_event_ms=ev.event_ms;
   if(!GvSet("Q24.EXEC.DAY",(double)ServerDayKey()) || !GvSet("Q24.EXEC.LASTEV",(double)ev.event_ms))
     {SetEntryFault("ENTRY_DEDUPE_PERSIST_FAILED");return false;}
   GlobalVariablesFlush();

   x.state=QI_SENT_UNKNOWN;
   g_intents[slot]=x;
   if(!SaveIntent(slot)) return false;

   string comment=IntentComment(x.id);
   ResetLastError();
   bool sent=g_trade.Buy(rr.volume,symbol,0.0,sl,tp,comment);
   uint rc=g_trade.ResultRetcode();
   x.order_ticket=g_trade.ResultOrder();
   x.deal_ticket=g_trade.ResultDeal();
   g_intents[slot]=x;SaveIntent(slot);
   LogRow("ENTRY","BROKER_RETURN",ev,"RETCODE_"+IntegerToString((int)rc),x.id,x.state,symbol,sendtick.bid,sendtick.ask,rr.volume,sl,tp,x.order_ticket,x.deal_ticket,0,rc);

   if(!sent || (rc!=TRADE_RETCODE_DONE && rc!=TRADE_RETCODE_DONE_PARTIAL && rc!=TRADE_RETCODE_PLACED))
     {
      // Only release after authoritative rejection and absence of broker inventory.
      ulong p=FindQrosPosition(symbol,magic,comment);
      ulong o=FindCurrentOrder(symbol,magic,comment);
      if(p==0 && o==0 && (rc==TRADE_RETCODE_REJECT || rc==TRADE_RETCODE_INVALID || rc==TRADE_RETCODE_INVALID_VOLUME || rc==TRADE_RETCODE_INVALID_PRICE || rc==TRADE_RETCODE_INVALID_STOPS || rc==TRADE_RETCODE_TRADE_DISABLED || rc==TRADE_RETCODE_MARKET_CLOSED || rc==TRADE_RETCODE_NO_MONEY))
        {MarkIntentTerminal(slot,QI_REJECTED,"AUTHORITATIVE_REJECT");return false;}
      SetEntryFault("BROKER_SEND_UNCERTAIN");
      ReconcileIntent(slot);
      return false;
     }

   ReconcileIntent(slot);
   return true;
  }

void HandleModify(const QrosBusEvent &ev)
  {
   string symbol=SymbolFor(ev.module_id);long magic=MagicFor(ev.module_id,ev.profile);
   int ix=FindActiveIntentForModuleProfile(ev.module_id,ev.profile,ev.event_ms);
   ulong ticket=(ix>=0?g_intents[ix].position_ticket:0);
   if(ticket==0) ticket=FindQrosPosition(symbol,magic,(ix>=0?IntentComment(g_intents[ix].id):""));
   if(ticket>0 && PositionSelectByTicket(ticket))
     {
      double oldsl=PositionGetDouble(POSITION_SL);
      double sl=GridNormalize(symbol,ev.sl);
      if(oldsl>0.0 && sl<=oldsl) return;
     }
   EnqueueMgmt(ev,QROS_ACT_MODIFY_SL,(ix>=0?g_intents[ix].id:0),ticket,(ix>=0?g_intents[ix].order_ticket:0),ev.sl,ev.tp);
  }

void HandleClose(const QrosBusEvent &ev)
  {
   CancelPendingEntriesForModule(ev.module_id,ev.profile,ev.event_ms);
   string symbol=SymbolFor(ev.module_id);long magic=MagicFor(ev.module_id,ev.profile);
   int ix=FindActiveIntentForModuleProfile(ev.module_id,ev.profile,ev.event_ms);
   ulong ticket=(ix>=0?g_intents[ix].position_ticket:0);
   ulong order=(ix>=0?g_intents[ix].order_ticket:0);
   if(ticket==0) ticket=FindQrosPosition(symbol,magic,(ix>=0?IntentComment(g_intents[ix].id):""));
   if(order==0 && ix>=0) order=FindCurrentOrder(symbol,magic,IntentComment(g_intents[ix].id));
   EnqueueMgmt(ev,QROS_ACT_CLOSE,(ix>=0?g_intents[ix].id:0),ticket,order,0,0);
  }

void EnsureNoOvernightIntents()
  {
   int dk=ServerDayKey();
   long nowms=(long)TimeTradeServer()*1000L;
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      long magic=(long)PositionGetInteger(POSITION_MAGIC);
      if(!IsQrosMagic(magic)) continue;
      string symbol=PositionGetString(POSITION_SYMBOL);
      long pms=(long)PositionGetInteger(POSITION_TIME_MSC);if(pms<=0)pms=(long)PositionGetInteger(POSITION_TIME)*1000L;
      bool old_day=(DayKeyFromMs(pms)!=dk);
      int end_sec=-1;
      bool have_session=FinalTradeSessionEndSec(symbol,end_sec);
      bool deadline=have_session && (InpSessionCloseLeadSec<=0 || ServerSecondsOfDay()>=end_sec-InpSessionCloseLeadSec);
      if(!have_session)
        {
         SetMgmtFault("SESSION_SCHEDULE_UNKNOWN_WITH_OPEN_POSITION");
         deadline=true; // risk-reducing close; never invent a synthetic fill
        }
      if(!old_day && !deadline) continue;
      if(old_day){g_recovery_lock=true;GvSet("Q24.EXEC.RECOVERY",1.0);}
      QrosBusEvent ev;ZeroMemory(ev);ev.event_ms=nowms;ev.action=QROS_ACT_CLOSE;
      int module_id=0,profile=0;if(!ModuleProfileForMagic(magic,module_id,profile)) continue;
      ev.module_id=module_id;ev.profile=profile;
      int ix=FindActiveIntentForModuleProfile(module_id,profile,nowms);
      EnqueueMgmt(ev,QROS_ACT_CLOSE,(ix>=0?g_intents[ix].id:0),ticket,(ix>=0?g_intents[ix].order_ticket:0),0,0);
     }

   // Working orders must not survive an old server day or the final trade-session boundary.
   for(int i=OrdersTotal()-1;i>=0;i--)
     {
      ulong ticket=OrderGetTicket(i);if(ticket==0) continue;
      long magic=(long)OrderGetInteger(ORDER_MAGIC);if(!IsQrosMagic(magic)) continue;
      string symbol=OrderGetString(ORDER_SYMBOL);
      long oms=(long)OrderGetInteger(ORDER_TIME_SETUP_MSC);if(oms<=0)oms=(long)OrderGetInteger(ORDER_TIME_SETUP)*1000L;
      bool old_day=(DayKeyFromMs(oms)!=dk);
      int end_sec=-1;bool have_session=FinalTradeSessionEndSec(symbol,end_sec);
      bool deadline=have_session && (InpSessionCloseLeadSec<=0 || ServerSecondsOfDay()>=end_sec-InpSessionCloseLeadSec);
      if(!have_session){SetMgmtFault("SESSION_SCHEDULE_UNKNOWN_WITH_WORKING_ORDER");deadline=true;}
      if(!old_day && !deadline) continue;
      if(old_day){g_recovery_lock=true;GvSet("Q24.EXEC.RECOVERY",1.0);}
      int module_id=0,profile=0;if(!ModuleProfileForMagic(magic,module_id,profile)) continue;
      QrosBusEvent ev;ZeroMemory(ev);ev.module_id=module_id;ev.profile=profile;ev.event_ms=nowms;ev.action=QROS_ACT_CLOSE;
      int ix=-1;for(int j=0;j<QROS_INTENT_SLOTS;j++) if(g_intents[j].used && !IntentTerminal(g_intents[j].state) && g_intents[j].order_ticket==ticket){ix=j;break;}
      EnqueueMgmt(ev,QROS_ACT_CLOSE,(ix>=0?g_intents[ix].id:0),(ix>=0?g_intents[ix].position_ticket:0),ticket,0,0);
     }
  }

void EscalateBusFaultInventory()
  {
   if(!g_bus_fault) return;
   ArrayResize(g_pending,0); // never execute an entry after management-bus integrity was lost
   long nowms=(long)TimeTradeServer()*1000L;
   for(int i=OrdersTotal()-1;i>=0;i--)
     {
      ulong o=OrderGetTicket(i);if(o==0) continue;long magic=(long)OrderGetInteger(ORDER_MAGIC);if(!IsQrosMagic(magic)) continue;
      int module_id=0,profile=0;if(!ModuleProfileForMagic(magic,module_id,profile)) continue;
      QrosBusEvent ev;ZeroMemory(ev);ev.module_id=module_id;ev.profile=profile;ev.event_ms=nowms;ev.action=QROS_ACT_CLOSE;
      EnqueueMgmt(ev,QROS_ACT_CLOSE,0,0,o,0,0);
     }
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong p=PositionGetTicket(i);if(p==0 || !PositionSelectByTicket(p)) continue;long magic=(long)PositionGetInteger(POSITION_MAGIC);if(!IsQrosMagic(magic)) continue;
      int module_id=0,profile=0;if(!ModuleProfileForMagic(magic,module_id,profile)) continue;
      QrosBusEvent ev;ZeroMemory(ev);ev.module_id=module_id;ev.profile=profile;ev.event_ms=nowms;ev.action=QROS_ACT_CLOSE;
      int ix=FindIntentForPosition(p,magic);
      EnqueueMgmt(ev,QROS_ACT_CLOSE,(ix>=0?g_intents[ix].id:0),p,(ix>=0?g_intents[ix].order_ticket:0),0,0);
     }
  }

void PollBus()
  {
   if(g_bus_fault) return;
   for(int m=1;m<=3;m++)
     {
      long head=QrosBusHead(m);
      if(head<0){SetBusFault("HEAD_INVALID_MODULE_"+IntegerToString(m));continue;}
      if(head<g_last_head_seen[m]){SetBusFault("HEAD_ROLLBACK_MODULE_"+IntegerToString(m));continue;}
      g_last_head_seen[m]=head;
      if(head-g_last_seq[m]>QROS_BUS_SLOTS)
        {SetBusFault("OVERFLOW_MODULE_"+IntegerToString(m));g_last_seq[m]=head;continue;}
      for(long s=g_last_seq[m]+1;s<=head;s++)
        {
         QrosBusEvent ev;
         if(!QrosBusRead(m,s,ev)){SetBusFault("TORN_OR_MISSING_MODULE_"+IntegerToString(m));break;}
         g_last_seq[m]=s;
         if(ev.action==QROS_ACT_ENTRY) AddPending(ev);
         else if(ev.action==QROS_ACT_MODIFY_SL) HandleModify(ev);
         else if(ev.action==QROS_ACT_CLOSE) HandleClose(ev);
        }
     }
  }

void ProcessPending()
  {
   if(ArraySize(g_pending)==0) return;
   SortPending();
   long now=(long)GetTickCount64();
   int w=0;
   int i=0;
   while(i<ArraySize(g_pending))
     {
      long ts=g_pending[i].ev.event_ms;
      int j=i;
      long first_received=g_pending[i].received_uptime_ms;
      while(j<ArraySize(g_pending) && g_pending[j].ev.event_ms==ts)
        {if(g_pending[j].received_uptime_ms<first_received) first_received=g_pending[j].received_uptime_ms;j++;}

      bool matured=(now-first_received>=InpPriorityBufferMs);
      bool cohort=CohortReady(ts);
      bool timed_out=(now-first_received>=InpEventMaxAgeMs);
      if(!matured || (!cohort && !timed_out))
        {
         // Preserve this and all later cohorts; causal order cannot advance past an incomplete earlier cohort.
         for(int k=i;k<ArraySize(g_pending);k++){if(w!=k)g_pending[w]=g_pending[k];w++;}
         break;
        }

      if(!cohort && timed_out)
        {
         for(int k=i;k<j;k++) LogRow("ENTRY","BLOCKED",g_pending[k].ev,"COHORT_WATERMARK_TIMEOUT",0,0,SymbolFor(g_pending[k].ev.module_id),0,0,0,g_pending[k].ev.sl,g_pending[k].ev.tp);
        }
      else
        {
         for(int k=i;k<j;k++) SendEntry(g_pending[k].ev);
        }
      i=j;
     }
   if(w<ArraySize(g_pending)) ArrayResize(g_pending,w);
  }

void RecoverRecentManagementBus()
  {
   if(!g_recovery_lock) return;
   long oldest_ms=(long)TimeTradeServer()*1000L;
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong t=PositionGetTicket(i);if(t==0 || !PositionSelectByTicket(t)) continue;
      if(!IsQrosMagic((long)PositionGetInteger(POSITION_MAGIC))) continue;
      long pms=(long)PositionGetInteger(POSITION_TIME_MSC);
      if(pms>0 && pms<oldest_ms) oldest_ms=pms;
     }
   for(int m=1;m<=3;m++)
     {
      long head=QrosBusHead(m);if(head<=0) continue;
      long start=(head-QROS_BUS_SLOTS+1>1 ? head-QROS_BUS_SLOTS+1 : 1);
      for(long s=start;s<=head;s++)
        {
         QrosBusEvent ev;if(!QrosBusRead(m,s,ev)) continue;
         if(ev.event_ms<oldest_ms || ev.action==QROS_ACT_ENTRY) continue;
         if(ev.action==QROS_ACT_MODIFY_SL) HandleModify(ev);
         else if(ev.action==QROS_ACT_CLOSE) HandleClose(ev);
        }
     }
  }

void RecoverUnknownBrokerInventory()
  {
   long nowms=(long)TimeTradeServer()*1000L;
   // Reconstruct QROS positions not represented by durable intent.
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      long magic=(long)PositionGetInteger(POSITION_MAGIC);if(!IsQrosMagic(magic)) continue;
      int module_id=0,profile=0;if(!ModuleProfileForMagic(magic,module_id,profile)) continue;
      bool represented=false;
      for(int j=0;j<QROS_INTENT_SLOTS;j++) if(g_intents[j].used && !IntentTerminal(g_intents[j].state) && (g_intents[j].position_ticket==ticket || g_intents[j].magic==magic)){represented=true;break;}
      if(represented) continue;

      int s=FindFreeIntentSlot();if(s<0){SetEntryFault("RECOVERY_NO_INTENT_SLOT");continue;}
      QrosIntent x;ZeroMemory(x);x.used=true;x.slot=s;x.module_id=module_id;x.profile=profile;x.magic=magic;x.position_ticket=ticket;
      x.event_ms=(long)PositionGetInteger(POSITION_TIME_MSC);if(x.event_ms<=0)x.event_ms=(long)PositionGetInteger(POSITION_TIME)*1000L;
      QrosBusEvent iev;ZeroMemory(iev);iev.module_id=module_id;iev.profile=profile;iev.event_ms=x.event_ms;
      x.id=IntentId(iev);if(x.id<=0)x.id=2240000000000LL+s;
      x.volume=PositionGetDouble(POSITION_VOLUME);x.sl=PositionGetDouble(POSITION_SL);x.tp=PositionGetDouble(POSITION_TP);x.day_key=DayKeyFromMs(x.event_ms);x.counted=1;x.created_uptime_ms=(long)GetTickCount64();
      bool rok=false;x.risk_usd=PositionRiskUsd(ticket,rok);
      bool protected_ok=(rok && x.sl>0.0 && x.tp>0.0);
      x.state=(protected_ok?QI_FILLED_PROTECTED:QI_PARTIAL);
      if(!rok)x.risk_usd=0.0;
      g_intents[s]=x;SaveIntent(s);
      g_recovery_lock=true;RequireRecert("RECOVERED_POSITION_REQUIRES_RECERTIFICATION");
      if(!protected_ok) SetMgmtFault("RECOVERED_POSITION_UNPROTECTED_OR_RISK_UNKNOWN");
      // Exact module-generation state cannot be reconstructed from broker inventory alone.
      // Fail-safe is a durable close request; no new risk is introduced.
      QrosBusEvent ev;ZeroMemory(ev);ev.module_id=module_id;ev.profile=profile;ev.event_ms=nowms;ev.action=QROS_ACT_CLOSE;
      EnqueueMgmt(ev,QROS_ACT_CLOSE,x.id,ticket,0,0,0);
      PrintFormat("QROS V224 recovered position ticket=%I64u scheduled_for_close=1",ticket);
     }

   // Reconstruct each unowned QROS working order as a durable reservation shell, then cancel it.
   for(int i=OrdersTotal()-1;i>=0;i--)
     {
      ulong ticket=OrderGetTicket(i);if(ticket==0) continue;
      long magic=(long)OrderGetInteger(ORDER_MAGIC);if(!IsQrosMagic(magic)) continue;
      bool represented=false;
      for(int j=0;j<QROS_INTENT_SLOTS;j++) if(g_intents[j].used && !IntentTerminal(g_intents[j].state) && g_intents[j].order_ticket==ticket){represented=true;break;}
      if(represented) continue;
      int module_id=0,profile=0;if(!ModuleProfileForMagic(magic,module_id,profile)){SetEntryFault("RECOVERY_ORDER_MAGIC_UNKNOWN");continue;}
      int s=FindFreeIntentSlot();if(s<0){SetEntryFault("RECOVERY_NO_INTENT_SLOT_FOR_ORDER");continue;}
      QrosIntent x;ZeroMemory(x);x.used=true;x.slot=s;x.module_id=module_id;x.profile=profile;x.magic=magic;x.order_ticket=ticket;
      x.event_ms=(long)OrderGetInteger(ORDER_TIME_SETUP_MSC);if(x.event_ms<=0)x.event_ms=(long)OrderGetInteger(ORDER_TIME_SETUP)*1000L;
      QrosBusEvent iev;ZeroMemory(iev);iev.module_id=module_id;iev.profile=profile;iev.event_ms=x.event_ms;
      x.id=IntentId(iev);if(x.id<=0 || FindIntentById(x.id)>=0)x.id=2241000000000LL+s;
      x.state=QI_WORKING;x.volume=OrderGetDouble(ORDER_VOLUME_INITIAL);x.sl=OrderGetDouble(ORDER_SL);x.tp=OrderGetDouble(ORDER_TP);x.day_key=DayKeyFromMs(x.event_ms);x.counted=0;x.created_uptime_ms=(long)GetTickCount64();
      bool rok=false;x.risk_usd=OrderRiskUsd(ticket,rok);if(!rok)x.risk_usd=0.0;
      g_intents[s]=x;SaveIntent(s);
      g_recovery_lock=true;RequireRecert("RECOVERED_WORKING_ORDER_REQUIRES_RECERTIFICATION");
      if(!rok) SetMgmtFault("RECOVERED_ORDER_RISK_UNKNOWN");
      QrosBusEvent ev;ZeroMemory(ev);ev.module_id=module_id;ev.profile=profile;ev.event_ms=nowms;ev.action=QROS_ACT_CLOSE;
      EnqueueMgmt(ev,QROS_ACT_CLOSE,x.id,0,ticket,0,0);
      PrintFormat("QROS V224 recovered working order ticket=%I64u",ticket);
     }
  }

void DetectAndContainAssetMultiplicity()
  {
   string assets[2]={"XAUUSD","NDX"};
   long nowms=(long)TimeTradeServer()*1000L;
   for(int a=0;a<2;a++)
     {
      int n=0;
      for(int i=PositionsTotal()-1;i>=0;i--)
        {ulong t=PositionGetTicket(i);if(t>0 && PositionSelectByTicket(t) && PositionGetString(POSITION_SYMBOL)==assets[a] && IsQrosMagic((long)PositionGetInteger(POSITION_MAGIC))) n++;}
      for(int i=OrdersTotal()-1;i>=0;i--)
        {ulong t=OrderGetTicket(i);if(t>0 && OrderGetString(ORDER_SYMBOL)==assets[a] && IsQrosMagic((long)OrderGetInteger(ORDER_MAGIC))) n++;}
      if(n<=1) continue;
      SetEntryFault("MULTIPLE_QROS_INVENTORY_ON_ASSET_"+assets[a]);
      SetMgmtFault("MULTIPLE_QROS_INVENTORY_CONTAINMENT_"+assets[a]);
      g_recovery_lock=true;GvSet("Q24.EXEC.RECOVERY",1.0);
      for(int i=OrdersTotal()-1;i>=0;i--)
        {
         ulong o=OrderGetTicket(i);if(o==0 || OrderGetString(ORDER_SYMBOL)!=assets[a]) continue;
         long magic=(long)OrderGetInteger(ORDER_MAGIC);if(!IsQrosMagic(magic)) continue;
         int m=0,pf=0;if(!ModuleProfileForMagic(magic,m,pf)) continue;
         QrosBusEvent ev;ZeroMemory(ev);ev.module_id=m;ev.profile=pf;ev.event_ms=nowms;ev.action=QROS_ACT_CLOSE;EnqueueMgmt(ev,QROS_ACT_CLOSE,0,0,o,0,0);
        }
      for(int i=PositionsTotal()-1;i>=0;i--)
        {
         ulong t=PositionGetTicket(i);if(t==0 || !PositionSelectByTicket(t) || PositionGetString(POSITION_SYMBOL)!=assets[a]) continue;
         long magic=(long)PositionGetInteger(POSITION_MAGIC);if(!IsQrosMagic(magic)) continue;
         int m=0,pf=0;if(!ModuleProfileForMagic(magic,m,pf)) continue;
         QrosBusEvent ev;ZeroMemory(ev);ev.module_id=m;ev.profile=pf;ev.event_ms=nowms;ev.action=QROS_ACT_CLOSE;int ix=FindIntentForPosition(t,magic);EnqueueMgmt(ev,QROS_ACT_CLOSE,(ix>=0?g_intents[ix].id:0),t,(ix>=0?g_intents[ix].order_ticket:0),0,0);
        }
     }
  }

void UpdateRecoveryLock()
  {
   bool inventory=false;
   for(int i=PositionsTotal()-1;i>=0;i--)
     {ulong t=PositionGetTicket(i);if(t>0 && PositionSelectByTicket(t) && IsQrosMagic((long)PositionGetInteger(POSITION_MAGIC))){inventory=true;break;}}
   if(!inventory)
     for(int i=OrdersTotal()-1;i>=0;i--)
       {ulong t=OrderGetTicket(i);if(t>0 && IsQrosMagic((long)OrderGetInteger(ORDER_MAGIC))){inventory=true;break;}}
   if(!inventory)
     for(int i=0;i<QROS_INTENT_SLOTS;i++) if(g_intents[i].used && !IntentTerminal(g_intents[i].state)){inventory=true;break;}

   if(g_recovery_lock && !inventory && g_history_ready)
     {
      // Recovery inventory is clean, but a restart invalidates CERT. External recertification is still required.
      g_recovery_lock=false;
      GlobalVariableSet("Q24.EXEC.RECOVERY",0.0);
      InvalidateCert();
      Print("QROS V224 recovery inventory clean; CERT remains 0 until external recertification");
     }
  }

bool ProducersHealthyAndBound()
  {
   for(int m=1;m<=3;m++)
     {
      if(QrosBusState(m)!=QROS_STATE_READY || QrosBusHeartbeatAgeMs(m)>InpHeartbeatMaxAgeMs) return false;
      long owner=QrosBusProducerOwner(m),epoch=QrosBusProducerEpoch(m),src=0;
      if(owner<=0 || epoch<=0) return false;
      if(!GvGetExactLong(QrosBusKey(m,"SOURCE_TOKEN"),src) || src!=SourceTokenFor(m))
        {SetEntryFault("MODULE_SOURCE_TOKEN_MISMATCH_M"+IntegerToString(m));return false;}
      if(g_bound_owner[m]==0 && g_bound_epoch[m]==0){g_bound_owner[m]=owner;g_bound_epoch[m]=epoch;}
      else if(g_bound_owner[m]!=owner || g_bound_epoch[m]!=epoch)
        {
         g_bound_owner[m]=owner;g_bound_epoch[m]=epoch;
         RequireRecert("PRODUCER_IDENTITY_CHANGED_M"+IntegerToString(m));
         return false;
        }
     }
   return true;
  }

void ContinuousSafetyGate()
  {
   bool connected=(bool)TerminalInfoInteger(TERMINAL_CONNECTED);
   if(!connected)
     {
      RequireRecert("TERMINAL_DISCONNECTED");
      g_was_connected=false;
      return;
     }
   if(!g_was_connected && InpArmDemoOrders) RequireRecert("TERMINAL_RECONNECTED");
   g_was_connected=true;

   if(!DemoAccountGate()) return;
   bool ook=false;long off=CurrentOffsetSec(ook);
   if(!ook){RequireRecert("OFFSET_OUTSIDE_DARWINEX_CONTRACT");return;}
   if(g_last_offset_seen!=0 && off!=g_last_offset_seen) RequireRecert("OFFSET_TRANSITION");
   g_last_offset_seen=off;

   if(InpArmDemoOrders && (!MQLInfoInteger(MQL_TRADE_ALLOWED) || !TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)))
     {RequireRecert("TRADE_PERMISSION_LOST");return;}
   if(!ProducersHealthyAndBound())
     {if(!g_entry_fault) RequireRecert("MODULE_HEALTH_OR_IDENTITY_NOT_READY");return;}

   bool hard_ok=(!g_entry_fault && !g_bus_fault && !g_mgmt_fault && !g_recovery_lock);
   if(!hard_ok)
     {GvSet("Q24.EXEC.HEALTH",0.0);return;}

   if(g_recert_required)
     {
      long now=(long)GetTickCount64();
      if(g_recert_healthy_since_ms==0) g_recert_healthy_since_ms=now;
      if(now-g_recert_healthy_since_ms>=QROS_RECERT_STABLE_MS)
        {
         g_recert_required=false;g_recert_reason="";g_recert_healthy_since_ms=0;g_boot_offset_sec=off;
         GvSet("Q24.EXEC.RECERT",0.0);
         // CERT deliberately remains 0 until the external bootstrap rebinds and receipts this epoch.
        }
     }
   GvSet("Q24.EXEC.HEALTH",(!g_recert_required?1.0:0.0));
  }

void OnTradeTransaction(const MqlTradeTransaction &trans,const MqlTradeRequest &request,const MqlTradeResult &result)
  {
   // Never send/modify/close recursively inside the broker transaction callback.
   // The authoritative timer performs reconciliation and management.
   g_trade_tx_pending=true;
  }

int OnInit()
  {
   InitSlots();
   GlobalVariableSet("Q24.EXEC.CERT",0.0);
   GlobalVariableSet("Q24.EXEC.HEALTH",0.0);
   GlobalVariableSet("Q24.EXEC.ENTRYFAULT",0.0);
   GlobalVariableSet("Q24.EXEC.BUSFAULT",0.0);
   GlobalVariableSet("Q24.EXEC.MGMTFAULT",0.0);
   GlobalVariableSet("Q24.EXEC.RECOVERY",0.0);
   GlobalVariableSet("Q24.EXEC.RECERT",1.0);
   GlobalVariableSet("Q24.EXEC.SOURCE_TOKEN",(double)QROS_EXEC_SOURCE_TOKEN);
   GlobalVariableSet("Q24.EXEC.SESSION_LEAD",(double)InpSessionCloseLeadSec);

   if(!DemoAccountGate()) return INIT_FAILED;
   if(InpRiskPctBalance!=0.50 || InpMaxReservedRiskPct!=1.00 || InpMaxNewEntriesPerServerDay!=3)
     {SetEntryFault("FROZEN_RISK_OR_CAP_MISMATCH");return INIT_PARAMETERS_INCORRECT;}
   if(!AcquireInstanceFence()) return INIT_FAILED;
   if(!OpenAppendLedger()){ReleaseInstanceFence();return INIT_FAILED;}

   LoadPersistentState();
   RebuildDailyCount();
   RecoverUnknownBrokerInventory();
   DetectAndContainAssetMultiplicity();

   bool has_inventory=false;
   for(int i=PositionsTotal()-1;i>=0;i--)
     {ulong t=PositionGetTicket(i);if(t>0 && PositionSelectByTicket(t) && IsQrosMagic((long)PositionGetInteger(POSITION_MAGIC))){has_inventory=true;break;}}
   if(!has_inventory)
     for(int i=OrdersTotal()-1;i>=0;i--)
       {ulong t=OrderGetTicket(i);if(t>0 && IsQrosMagic((long)OrderGetInteger(ORDER_MAGIC))){has_inventory=true;break;}}
   if(has_inventory) g_recovery_lock=true;
   GlobalVariableSet("Q24.EXEC.RECOVERY",g_recovery_lock?1.0:0.0);

   for(int m=1;m<=3;m++)
     {
      long h=QrosBusHead(m);
      if(h<0){SetBusFault("INITIAL_HEAD_INVALID_MODULE_"+IntegerToString(m));h=0;}
      g_last_seq[m]=h;
      g_last_head_seen[m]=h;
     }
   RecoverRecentManagementBus();

   if(InpArmDemoOrders && !EntryTradeGate())
     {
      // Do not fail initialization if inventory needs management; entries remain fail-closed.
      InvalidateCert();
     }

   bool ook=false;g_boot_offset_sec=CurrentOffsetSec(ook);
   if(!ook) RequireRecert("INITIAL_OFFSET_NOT_READY");
   else g_last_offset_seen=g_boot_offset_sec;
   g_was_connected=(bool)TerminalInfoInteger(TERMINAL_CONNECTED);
   RequireRecert("INITIAL_CERTIFICATION_REQUIRED");

   GvSet("Q24.EXEC.HB",(double)GetTickCount64());
   GvSet("Q24.EXEC.ARMED",InpArmDemoOrders?1.0:0.0);
   GvSet("Q24.EXEC.INSTANCE",(double)g_instance_token);
   if(!EventSetMillisecondTimer(100)){SetMgmtFault("TIMER_REGISTRATION_FAILED");return INIT_FAILED;}

   QrosBusEvent iev;ZeroMemory(iev);
   LogRow("INIT","PASS",iev,InpArmDemoOrders?"ARMED_DEMO_V224":"UNARMED_CANARY_V224",0,0,"",0,0,0,0,0);
   Print("QROS V224 executor initialized. armed=",InpArmDemoOrders?"true":"false"," recovery=",g_recovery_lock?"true":"false");
   return INIT_SUCCEEDED;
  }

void OnTimer()
  {
   GlobalVariableSet("Q24.EXEC.HB",(double)GetTickCount64());
   GlobalVariableSet("Q24.EXEC.ARMED",InpArmDemoOrders?1.0:0.0);
   ContinuousSafetyGate();
   RefreshDay();
   if(g_trade_tx_pending) g_trade_tx_pending=false;
   ReconcileAllIntents();
   DetectAndContainAssetMultiplicity();
   EnsureNoOvernightIntents();
   EscalateBusFaultInventory();
   ProcessMgmt();
   UpdateRecoveryLock();

   // Bus failure blocks bus consumption, but never broker-inventory management.
   if(!g_bus_fault) PollBus();
   ProcessMgmt();
   if(!g_entry_fault && !g_bus_fault && !g_mgmt_fault && !g_recovery_lock) ProcessPending();
  }

void OnTick()
  {
   ReconcileAllIntents();
   DetectAndContainAssetMultiplicity();
   EnsureNoOvernightIntents();
   EscalateBusFaultInventory();
   ProcessMgmt();
   if(!g_bus_fault) PollBus();
   if(!g_entry_fault && !g_bus_fault && !g_mgmt_fault && !g_recovery_lock) ProcessPending();
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   GlobalVariableSet("Q24.EXEC.ARMED",0.0);
   GlobalVariableSet("Q24.EXEC.CERT",0.0);
   GlobalVariableSet("Q24.EXEC.HB",-1.0);
   GlobalVariableSet("Q24.EXEC.HEALTH",0.0);
   QrosBusEvent ev;ZeroMemory(ev);
   LogRow("DEINIT","INFO",ev,"REASON_"+IntegerToString(reason),0,0,"",0,0,0,0,0);
   if(g_log!=INVALID_HANDLE){FileClose(g_log);g_log=INVALID_HANDLE;}
   ReleaseInstanceFence();
  }
