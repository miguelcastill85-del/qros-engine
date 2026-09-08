//+------------------------------------------------------------------+
//| QROS_DEMO_PORTFOLIO_EXECUTOR_v1.mq5                              |
//| DEMO-only central ordering controller for frozen 3-module cohort. |
//| LIVE accounts fail closed. Default is unarmed CANARY mode.        |
//+------------------------------------------------------------------+
#property strict
#property version "2.00"
#property description "QROS Darwinex-Demo only. Central controller. Fail-closed."
#include <Trade/Trade.mqh>
#include <QROS_RISK_KERNEL_APPROVED_v15420.mqh>
#include <QROS_DEMO_BUS_v2.mqh>

input bool   InpArmDemoOrders=false;
input string InpArmToken="";
input double InpRiskPctBalance=0.50;
input double InpMaxReservedRiskPct=1.00;
input int    InpMaxNewEntriesPerServerDay=3;
input int    InpHeartbeatMaxAgeMs=5000;
input int    InpPriorityBufferMs=300;
input string InpAuditPrefix="QROS_DEMO_EXECUTOR_v1";

const string QROS_REQUIRED_SERVER="Darwinex-Demo";
const string QROS_REQUIRED_CURRENCY="USD";
const string QROS_ARM_TOKEN="QROS_DEMO_ARM_v1_8af000_2d6ebd";
const long MAGIC_XAU=560101;
const long MAGIC_NQX17=560217;
const long MAGIC_NQX31=560231;
const long MAGIC_DIV3=560300;

CTrade g_trade;
int g_log=INVALID_HANDLE;
long g_last_seq[4]={0,0,0,0};
bool g_fault=false;
bool g_recovery_lock=false;
string g_fault_reason="";
long g_last_accepted_event_ms=-1;
int g_last_day_key=-1;
int g_day_entries=0;

struct PendingEntry
  {
   QrosBusEvent ev;
   long received_uptime_ms;
  };
PendingEntry g_pending[];

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

void LogRow(const string stage,const string decision,const QrosBusEvent &ev,
            const string reason,const string symbol,const double bid,const double ask,
            const double volume,const double sl,const double tp,const ulong ticket=0)
  {
   if(g_log==INVALID_HANDLE) return;
   FileWrite(g_log,
      TimeToString(TimeTradeServer(),TIME_DATE|TIME_SECONDS),
      (long)GetTickCount64(),stage,decision,reason,
      ev.module_id,ev.profile,ev.seq,ev.event_ms,ev.action,
      symbol,bid,ask,volume,sl,tp,(long)ticket,
      AccountInfoString(ACCOUNT_SERVER),(long)AccountInfoInteger(ACCOUNT_LOGIN),
      DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE),2));
   FileFlush(g_log);
  }

void SetFault(const string reason)
  {
   g_fault=true;g_fault_reason=reason;
   Print("QROS DEMO EXECUTOR FAULT: ",reason);
  }

bool DemoAccountGate()
  {
   if((ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO)
     { SetFault("ACCOUNT_NOT_DEMO"); return false; }
   if(AccountInfoString(ACCOUNT_SERVER)!=QROS_REQUIRED_SERVER)
     { SetFault("WRONG_SERVER_"+AccountInfoString(ACCOUNT_SERVER)); return false; }
   if(AccountInfoString(ACCOUNT_CURRENCY)!=QROS_REQUIRED_CURRENCY)
     { SetFault("WRONG_CURRENCY_"+AccountInfoString(ACCOUNT_CURRENCY)); return false; }
   return true;
  }

bool ArmGate()
  {
   if(!InpArmDemoOrders) return false;
   if(InpArmToken!=QROS_ARM_TOKEN){ SetFault("INVALID_ARM_TOKEN"); return false; }
   if(!MQLInfoInteger(MQL_TRADE_ALLOWED)){ SetFault("MQL_TRADE_NOT_ALLOWED"); return false; }
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)){ SetFault("TERMINAL_TRADE_NOT_ALLOWED"); return false; }
   return true;
  }

bool RuntimeCertified()
  {
   string k="QDB1.EXEC.CERT";
   return (GlobalVariableCheck(k) && (int)GlobalVariableGet(k)==1);
  }

bool HasOpenQrosPosition()
  {
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      if(IsQrosMagic((long)PositionGetInteger(POSITION_MAGIC))) return true;
     }
   return false;
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

double GridNormalize(const string symbol,const double price)
  {
   double ts=SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_SIZE);
   if(!(ts>0.0)) ts=SymbolInfoDouble(symbol,SYMBOL_POINT);
   int digits=(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS);
   if(!(ts>0.0)) return NormalizeDouble(price,digits);
   return NormalizeDouble(MathRound(price/ts)*ts,digits);
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

ulong FindQrosPosition(const string symbol,const long magic)
  {
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL)!=symbol) continue;
      if((long)PositionGetInteger(POSITION_MAGIC)==magic) return ticket;
     }
   return 0;
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
      string sym=PositionGetString(POSITION_SYMBOL);
      double openp=PositionGetDouble(POSITION_PRICE_OPEN);
      double sl=PositionGetDouble(POSITION_SL);
      double vol=PositionGetDouble(POSITION_VOLUME);
      long ptype=(long)PositionGetInteger(POSITION_TYPE);
      if(!(sl>0.0) || !(vol>0.0)){ok=false;return 0.0;}
      ENUM_ORDER_TYPE ot=(ptype==POSITION_TYPE_BUY?ORDER_TYPE_BUY:ORDER_TYPE_SELL);
      double p=0.0;
      if(!OrderCalcProfit(ot,sym,vol,openp,sl,p)){ok=false;return 0.0;}
      total+=MathAbs(p);
     }
   return total;
  }

void RebuildDailyCount()
  {
   g_day_entries=0;
   datetime from=ServerDayStart();
   datetime to=TimeTradeServer()+60;
   if(!HistorySelect(from,to)) return;
   long seen[];
   ArrayResize(seen,0);
   int n=HistoryDealsTotal();
   for(int i=0;i<n;i++)
     {
      ulong d=HistoryDealGetTicket(i);
      if(d==0) continue;
      long magic=(long)HistoryDealGetInteger(d,DEAL_MAGIC);
      if(!IsQrosMagic(magic)) continue;
      long entry=(long)HistoryDealGetInteger(d,DEAL_ENTRY);
      if(entry!=DEAL_ENTRY_IN && entry!=DEAL_ENTRY_INOUT) continue;
      long pid=(long)HistoryDealGetInteger(d,DEAL_POSITION_ID);
      bool exists=false;
      for(int j=0;j<ArraySize(seen);j++) if(seen[j]==pid){exists=true;break;}
      if(!exists)
        {
         int z=ArraySize(seen);ArrayResize(seen,z+1);seen[z]=pid;g_day_entries++;
        }
     }
   g_last_day_key=ServerDayKey();
   string kday="QDB1.EXEC.DAY";
   string kev="QDB1.EXEC.LASTEV";
   if(GlobalVariableCheck(kday) && (int)GlobalVariableGet(kday)==g_last_day_key && GlobalVariableCheck(kev))
      g_last_accepted_event_ms=(long)GlobalVariableGet(kev);
   else
      g_last_accepted_event_ms=-1;
  }

void RefreshDay()
  {
   int dk=ServerDayKey();
   if(dk!=g_last_day_key)
     {
      RebuildDailyCount();
      g_last_accepted_event_ms=-1;
      GlobalVariableSet("QDB1.EXEC.DAY",(double)dk);
      GlobalVariableSet("QDB1.EXEC.LASTEV",-1.0);
     }
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
      PendingEntry key=g_pending[i];
      int j=i-1;
      while(j>=0 && Before(key,g_pending[j])){g_pending[j+1]=g_pending[j];j--;}
      g_pending[j+1]=key;
     }
  }

bool SendEntry(const QrosBusEvent &ev)
  {
   string symbol=SymbolFor(ev.module_id);
   long magic=MagicFor(ev.module_id,ev.profile);
   MqlTick tick;
   if(symbol=="" || magic<0){LogRow("ENTRY","BLOCKED",ev,"INVALID_MODULE_PROFILE",symbol,0,0,0,ev.sl,ev.tp);return false;}
   if(g_fault){LogRow("ENTRY","BLOCKED",ev,g_fault_reason,symbol,0,0,0,ev.sl,ev.tp);return false;}
   if(g_recovery_lock){LogRow("ENTRY","BLOCKED",ev,"RECOVERY_LOCK",symbol,0,0,0,ev.sl,ev.tp);return false;}
   if(InpArmDemoOrders && !RuntimeCertified())
     {LogRow("ENTRY","BLOCKED",ev,"RUNTIME_NOT_CERTIFIED",symbol,0,0,0,ev.sl,ev.tp);return false;}
   if(!HeartbeatsReady()){LogRow("ENTRY","BLOCKED",ev,"HEARTBEAT_NOT_READY",symbol,0,0,0,ev.sl,ev.tp);return false;}
   if(!PositiveSpread(symbol,tick)){LogRow("ENTRY","BLOCKED",ev,"NON_EXECUTABLE_SPREAD",symbol,tick.bid,tick.ask,0,ev.sl,ev.tp);return false;}

   RefreshDay();
   if(g_day_entries>=InpMaxNewEntriesPerServerDay){LogRow("ENTRY","BLOCKED",ev,"DAILY_CAP_3",symbol,tick.bid,tick.ask,0,ev.sl,ev.tp);return false;}
   if(ev.event_ms==g_last_accepted_event_ms){LogRow("ENTRY","BLOCKED",ev,"SIMULTANEOUS_ENTRY",symbol,tick.bid,tick.ask,0,ev.sl,ev.tp);return false;}
   if(AnyPositionOnAsset(symbol)){LogRow("ENTRY","BLOCKED",ev,"ASSET_POSITION_OPEN",symbol,tick.bid,tick.ask,0,ev.sl,ev.tp);return false;}

   double sl=GridNormalize(symbol,ev.sl);
   double tp=GridNormalize(symbol,ev.tp);
   if(!(sl>0.0) || !(tp>0.0) || sl>=tick.ask || tp<=tick.ask)
     {LogRow("ENTRY","BLOCKED",ev,"INVALID_BARRIERS_AT_REQUEST",symbol,tick.bid,tick.ask,0,sl,tp);return false;}

   QrosRiskResult rr;
   double bal=AccountInfoDouble(ACCOUNT_BALANCE);
   if(!QrosRiskSize(symbol,ORDER_TYPE_BUY,tick.ask,sl,bal,InpRiskPctBalance,rr))
     {LogRow("ENTRY","BLOCKED",ev,"RISK_"+rr.reason,symbol,tick.bid,tick.ask,0,sl,tp);return false;}

   bool rok=false;
   double reserved=ReservedRiskUsd(rok);
   if(!rok){SetFault("RESERVED_RISK_UNKNOWN");LogRow("ENTRY","BLOCKED",ev,g_fault_reason,symbol,tick.bid,tick.ask,0,sl,tp);return false;}
   double maxr=bal*(InpMaxReservedRiskPct/100.0);
   if(reserved+rr.actual_risk_usd>maxr+0.01)
     {LogRow("ENTRY","BLOCKED",ev,"MAX_RESERVED_RISK_1PCT",symbol,tick.bid,tick.ask,rr.volume,sl,tp);return false;}

   if(!InpArmDemoOrders)
     {LogRow("ENTRY","CANARY_BLOCKED",ev,"ORDERS_NOT_ARMED",symbol,tick.bid,tick.ask,rr.volume,sl,tp);return false;}
   if(!ArmGate())
     {LogRow("ENTRY","BLOCKED",ev,g_fault_reason,symbol,tick.bid,tick.ask,rr.volume,sl,tp);return false;}

   g_trade.SetExpertMagicNumber((ulong)magic);
   g_trade.SetTypeFillingBySymbol(symbol);
   g_trade.SetAsyncMode(false);
   string comment="QROS "+IntegerToString(ev.module_id)+"/"+IntegerToString(ev.profile);
   ResetLastError();
   bool sent=g_trade.Buy(rr.volume,symbol,0.0,sl,tp,comment);
   ulong order=g_trade.ResultOrder();
   ulong deal=g_trade.ResultDeal();
   uint rc=g_trade.ResultRetcode();
   if(!sent || (rc!=TRADE_RETCODE_DONE && rc!=TRADE_RETCODE_DONE_PARTIAL && rc!=TRADE_RETCODE_PLACED))
     {
      LogRow("ENTRY","BROKER_REJECT",ev,"RETCODE_"+IntegerToString((int)rc),symbol,tick.bid,tick.ask,rr.volume,sl,tp,order);
      return false;
     }

   g_day_entries++;
   g_last_accepted_event_ms=ev.event_ms;
   GlobalVariableSet("QDB1.EXEC.DAY",(double)ServerDayKey());
   GlobalVariableSet("QDB1.EXEC.LASTEV",(double)ev.event_ms);
   LogRow("ENTRY","EXECUTED",ev,"PASS",symbol,tick.bid,tick.ask,rr.volume,sl,tp,(deal>0?deal:order));
   return true;
  }

void HandleModify(const QrosBusEvent &ev)
  {
   string symbol=SymbolFor(ev.module_id);long magic=MagicFor(ev.module_id,ev.profile);
   ulong ticket=FindQrosPosition(symbol,magic);
   if(ticket==0) return;
   if(!PositionSelectByTicket(ticket)) return;
   double oldsl=PositionGetDouble(POSITION_SL);
   double oldtp=PositionGetDouble(POSITION_TP);
   double sl=GridNormalize(symbol,ev.sl);
   double tp=(ev.tp>0.0?GridNormalize(symbol,ev.tp):oldtp);
   if(sl<=oldsl) return;
   if(!InpArmDemoOrders){LogRow("MODIFY","CANARY_BLOCKED",ev,"ORDERS_NOT_ARMED",symbol,0,0,0,sl,tp,ticket);return;}
   if(!ArmGate()) return;
   g_trade.SetExpertMagicNumber((ulong)magic);
   bool ok=g_trade.PositionModify(ticket,sl,tp);
   LogRow("MODIFY",ok?"EXECUTED":"BROKER_REJECT",ev,ok?"PASS":"RETCODE_"+IntegerToString((int)g_trade.ResultRetcode()),symbol,0,0,0,sl,tp,ticket);
  }

void HandleClose(const QrosBusEvent &ev,const string reason="MODULE_CLOSE")
  {
   string symbol=SymbolFor(ev.module_id);long magic=MagicFor(ev.module_id,ev.profile);
   ulong ticket=FindQrosPosition(symbol,magic);
   if(ticket==0) return;
   if(!InpArmDemoOrders){LogRow("CLOSE","CANARY_BLOCKED",ev,"ORDERS_NOT_ARMED",symbol,0,0,0,0,0,ticket);return;}
   if(!ArmGate()) return;
   g_trade.SetExpertMagicNumber((ulong)magic);
   g_trade.SetTypeFillingBySymbol(symbol);
   bool ok=g_trade.PositionClose(ticket);
   LogRow("CLOSE",ok?"EXECUTED":"BROKER_REJECT",ev,ok?reason:"RETCODE_"+IntegerToString((int)g_trade.ResultRetcode()),symbol,0,0,0,0,0,ticket);
  }

void ForceNoOvernight()
  {
   int dk=ServerDayKey();
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      long magic=(long)PositionGetInteger(POSITION_MAGIC);
      if(!IsQrosMagic(magic)) continue;
      datetime pt=(datetime)PositionGetInteger(POSITION_TIME);
      MqlDateTime s;TimeToStruct(pt,s);
      int pdk=s.year*10000+s.mon*100+s.day;
      if(pdk==dk) continue;
      QrosBusEvent ev;ZeroMemory(ev);ev.event_ms=(long)TimeTradeServer()*1000L;
      if(magic==MAGIC_XAU){ev.module_id=QROS_MOD_XAU;ev.profile=0;}
      else if(magic==MAGIC_DIV3){ev.module_id=QROS_MOD_DIV3;ev.profile=0;}
      else {ev.module_id=QROS_MOD_NQX;ev.profile=(magic==MAGIC_NQX17?17:31);}
      if(InpArmDemoOrders && ArmGate())
        {
         g_trade.SetExpertMagicNumber((ulong)magic);
         g_trade.SetTypeFillingBySymbol(PositionGetString(POSITION_SYMBOL));
         bool ok=g_trade.PositionClose(ticket);
         LogRow("FORCE_CLOSE",ok?"EXECUTED":"BROKER_REJECT",ev,"SERVER_DAY_BOUNDARY",PositionGetString(POSITION_SYMBOL),0,0,0,0,0,ticket);
        }
     }
  }

void PollBus()
  {
   for(int m=1;m<=3;m++)
     {
      long head=QrosBusHead(m);
      if(head-g_last_seq[m]>QROS_BUS_SLOTS)
        {
         SetFault("BUS_OVERFLOW_MODULE_"+IntegerToString(m));
         g_last_seq[m]=head;
         continue;
        }
      for(long s=g_last_seq[m]+1;s<=head;s++)
        {
         QrosBusEvent ev;
         if(!QrosBusRead(m,s,ev)){SetFault("BUS_TORN_OR_MISSING_MODULE_"+IntegerToString(m));break;}
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
   for(int i=0;i<ArraySize(g_pending);i++)
     {
      if(now-g_pending[i].received_uptime_ms<InpPriorityBufferMs)
        {
         if(w!=i)g_pending[w]=g_pending[i];
         w++;
         continue;
        }
      SendEntry(g_pending[i].ev);
     }
   if(w<ArraySize(g_pending)) ArrayResize(g_pending,w);
  }

int OnInit()
  {
   int flags=FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON;
   g_log=FileOpen(InpAuditPrefix+"_LEDGER.csv",flags,',');
   if(g_log==INVALID_HANDLE) return INIT_FAILED;
   FileWrite(g_log,"server_time","uptime_ms","stage","decision","reason","module_id","profile","seq","event_ms","action","symbol","bid","ask","volume","sl","tp","ticket","server","login","balance");

   GlobalVariableSet("QDB1.EXEC.CERT",0.0);
   if(!DemoAccountGate()) return INIT_FAILED;
   if(HasOpenQrosPosition())
     {
      g_recovery_lock=true;
      Print("QROS recovery lock: existing QROS position; no new entries until flat + recertification");
     }
   if(InpRiskPctBalance!=0.50 || InpMaxReservedRiskPct!=1.00 || InpMaxNewEntriesPerServerDay!=3)
     {SetFault("FROZEN_RISK_OR_CAP_MISMATCH");return INIT_PARAMETERS_INCORRECT;}

   for(int m=1;m<=3;m++) g_last_seq[m]=QrosBusHead(m); // never replay stale candidates
   RebuildDailyCount();

   if(InpArmDemoOrders && !ArmGate()) return INIT_FAILED;
   GlobalVariableSet("QDB1.EXEC.HB",(double)GetTickCount64());
   GlobalVariableSet("QDB1.EXEC.ARMED",InpArmDemoOrders?1.0:0.0);
   EventSetMillisecondTimer(100);
   QrosBusEvent iev;ZeroMemory(iev);
   LogRow("INIT","PASS",iev,InpArmDemoOrders?"ARMED_DEMO":"UNARMED_CANARY","",0,0,0,0,0);
   Print("QROS DEMO EXECUTOR initialized. armed=",InpArmDemoOrders?"true":"false");
   return INIT_SUCCEEDED;
  }

void OnTimer()
  {
   GlobalVariableSet("QDB1.EXEC.HB",(double)GetTickCount64());
   GlobalVariableSet("QDB1.EXEC.ARMED",InpArmDemoOrders?1.0:0.0);
   if(g_fault) { GlobalVariableSet("QDB1.EXEC.CERT",0.0); return; }
   RefreshDay();
   ForceNoOvernight();
   PollBus();
   ProcessPending();
  }

void OnTick()
  {
   // Timer is authoritative; tick only accelerates processing without changing ordering.
   if(!g_fault){PollBus();ProcessPending();}
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   GlobalVariableSet("QDB1.EXEC.ARMED",0.0);
   GlobalVariableSet("QDB1.EXEC.CERT",0.0);
   GlobalVariableSet("QDB1.EXEC.HB",-1.0);
   if(g_log!=INVALID_HANDLE)
     {
      QrosBusEvent ev;ZeroMemory(ev);
      LogRow("DEINIT","INFO",ev,"REASON_"+IntegerToString(reason),"",0,0,0,0,0);
      FileClose(g_log);
     }
  }
