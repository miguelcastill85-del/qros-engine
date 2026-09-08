//+------------------------------------------------------------------+
//| QROS_DEMO_BUS_v2_2_4.mqh                                        |
//| Hardened terminal-global ring bus for v2.2.4.                    |
//| Infrastructure only: no signal/economic logic.                   |
//+------------------------------------------------------------------+
#ifndef __QROS_DEMO_BUS_V2_2_4__
#define __QROS_DEMO_BUS_V2_2_4__

#define QROS_MOD_XAU  1
#define QROS_MOD_NQX  2
#define QROS_MOD_DIV3 3

#define QROS_ACT_ENTRY     1
#define QROS_ACT_MODIFY_SL 2
#define QROS_ACT_CLOSE     3

#define QROS_BUS_SLOTS 32

#define QROS_STATE_OFF   0
#define QROS_STATE_INIT  1
#define QROS_STATE_READY 2
#define QROS_STATE_FAULT 3

#define QROS_BUS_EXACT_DOUBLE_MAX 9007199254740991LL

struct QrosBusEvent
  {
   long   seq;
   int    module_id;
   int    action;
   int    profile;
   long   event_ms;
   double entry_ref;
   double sl;
   double tp;
   double aux1;
   double aux2;
   long   publish_uptime_ms;
   long   producer_epoch;
   long   producer_owner;
  };

int  g_qros_bus_lock_handle=INVALID_HANDLE;
int  g_qros_bus_module=0;
long g_qros_bus_owner=0;
long g_qros_bus_epoch=0;

string QrosBusKey(const int module_id,const string suffix)
  {
   return "Q24."+IntegerToString(module_id)+"."+suffix;
  }

string QrosBusSlotKey(const int module_id,const int slot,const string field)
  {
   return "Q24."+IntegerToString(module_id)+".S"+IntegerToString(slot)+"."+field;
  }

bool QrosBusExactInteger(const long v)
  {
   return (v>=0 && v<=QROS_BUS_EXACT_DOUBLE_MAX);
  }

bool QrosGvGetExactLong(const string key,long &out)
  {
   out=0;
   if(!GlobalVariableCheck(key)) return false;
   double v=GlobalVariableGet(key);
   if(!MathIsValidNumber(v) || v<0.0 || v>(double)QROS_BUS_EXACT_DOUBLE_MAX) return false;
   double r=MathFloor(v);
   if(v!=r) return false;
   out=(long)r;
   return true;
  }

bool QrosGvGetFinite(const string key,double &out)
  {
   out=0.0;
   if(!GlobalVariableCheck(key)) return false;
   out=GlobalVariableGet(key);
   return MathIsValidNumber(out);
  }

bool QrosGvSetChecked(const string key,const double value)
  {
   if(!MathIsValidNumber(value)) return false;
   ResetLastError();
   datetime r=GlobalVariableSet(key,value);
   if(r==0)
     {
      PrintFormat("QROS BUS GV write failed key=%s err=%d",key,GetLastError());
      return false;
     }
   if(!GlobalVariableCheck(key)) return false;
   double observed=GlobalVariableGet(key);
   if(!MathIsValidNumber(observed) || observed!=value)
     {
      PrintFormat("QROS BUS GV readback mismatch key=%s",key);
      return false;
     }
   return true;
  }

long QrosBusMakeOwnerToken(const int module_id)
  {
   long login=(long)AccountInfoInteger(ACCOUNT_LOGIN);
   long now=(long)TimeLocal();
   long up=(long)GetTickCount64();
   long token=(login%100000000LL)*10000000LL+(now%100000LL)*100LL+module_id;
   token^=(up%9973LL);
   if(token<=0) token=1000000LL+module_id;
   if(token>QROS_BUS_EXACT_DOUBLE_MAX) token%=QROS_BUS_EXACT_DOUBLE_MAX;
   return token;
  }

long QrosBusMakeEpoch(const int module_id)
  {
   long t=(long)TimeTradeServer();
   if(t<=0) t=(long)TimeLocal();
   long e=t*10LL+module_id;
   if(e<=0 || !QrosBusExactInteger(e)) e=100000LL+module_id;
   return e;
  }

void QrosBusProducerRelease()
  {
   if(MQLInfoInteger(MQL_TESTER)) return;
   if(g_qros_bus_module>=QROS_MOD_XAU && g_qros_bus_module<=QROS_MOD_DIV3)
     {
      string ownerk=QrosBusKey(g_qros_bus_module,"OWNER");
      string lockk=QrosBusKey(g_qros_bus_module,"LOCK");
      long held=0;
      if(QrosGvGetExactLong(lockk,held) && held==g_qros_bus_owner)
         GlobalVariableSet(lockk,0.0);
      long owner=0;
      if(QrosGvGetExactLong(ownerk,owner) && owner==g_qros_bus_owner)
         GlobalVariableSet(ownerk,0.0);
     }
   if(g_qros_bus_lock_handle!=INVALID_HANDLE)
     {
      FileClose(g_qros_bus_lock_handle);
      g_qros_bus_lock_handle=INVALID_HANDLE;
     }
   g_qros_bus_module=0;
   g_qros_bus_owner=0;
   g_qros_bus_epoch=0;
  }

bool QrosBusProducerInit(const int module_id)
  {
   if(module_id<QROS_MOD_XAU || module_id>QROS_MOD_DIV3) return false;
   if(MQLInfoInteger(MQL_TESTER))
     {
      g_qros_bus_module=module_id;
      g_qros_bus_owner=module_id;
      g_qros_bus_epoch=module_id;
      return true;
     }
   if(g_qros_bus_lock_handle!=INVALID_HANDLE) return (g_qros_bus_module==module_id);

   long login=(long)AccountInfoInteger(ACCOUNT_LOGIN);
   string lockname="QROS_V224_BUS_M"+IntegerToString(module_id)+"_"+IntegerToString(login)+"_"+AccountInfoString(ACCOUNT_SERVER)+".lock";
   ResetLastError();
   g_qros_bus_lock_handle=FileOpen(lockname,FILE_READ|FILE_WRITE|FILE_BIN|FILE_COMMON);
   if(g_qros_bus_lock_handle==INVALID_HANDLE)
     {
      PrintFormat("QROS BUS producer lock failed module=%d err=%d",module_id,GetLastError());
      return false;
     }

   g_qros_bus_module=module_id;
   g_qros_bus_owner=QrosBusMakeOwnerToken(module_id);
   g_qros_bus_epoch=QrosBusMakeEpoch(module_id);

   FileSeek(g_qros_bus_lock_handle,0,SEEK_SET);
   FileWriteLong(g_qros_bus_lock_handle,g_qros_bus_owner);
   FileWriteLong(g_qros_bus_lock_handle,g_qros_bus_epoch);
   FileFlush(g_qros_bus_lock_handle);

   long head=0;
   string headk=QrosBusKey(module_id,"HEAD");
   if(GlobalVariableCheck(headk) && !QrosGvGetExactLong(headk,head))
     {
      PrintFormat("QROS BUS invalid persisted HEAD module=%d",module_id);
      QrosBusProducerRelease();
      return false;
     }
   if(!GlobalVariableCheck(headk) && !QrosGvSetChecked(headk,0.0))
     {
      QrosBusProducerRelease();
      return false;
     }

   // The exclusive FILE_COMMON handle proves the previous producer process is gone.
   // Reset only ephemeral publication ownership; preserve monotonic HEAD.
   bool ok=true;
   ok=ok && QrosGvSetChecked(QrosBusKey(module_id,"OWNER"),(double)g_qros_bus_owner);
   ok=ok && QrosGvSetChecked(QrosBusKey(module_id,"EPOCH"),(double)g_qros_bus_epoch);
   ok=ok && QrosGvSetChecked(QrosBusKey(module_id,"LOCK"),0.0);
   ok=ok && QrosGvSetChecked(QrosBusKey(module_id,"WM"),0.0);
   ok=ok && QrosGvSetChecked(QrosBusKey(module_id,"HB"),(double)GetTickCount64());
   if(!ok)
     {
      QrosBusProducerRelease();
      return false;
     }
   GlobalVariablesFlush();
   return true;
  }

bool QrosBusProducerHealthy(const int module_id)
  {
   if(MQLInfoInteger(MQL_TESTER)) return true;
   if(g_qros_bus_lock_handle==INVALID_HANDLE || g_qros_bus_module!=module_id) return false;
   long owner=0,epoch=0;
   if(!QrosGvGetExactLong(QrosBusKey(module_id,"OWNER"),owner)) return false;
   if(!QrosGvGetExactLong(QrosBusKey(module_id,"EPOCH"),epoch)) return false;
   return (owner==g_qros_bus_owner && epoch==g_qros_bus_epoch);
  }

void QrosBusSetState(const int module_id,const int state)
  {
   if(!QrosGvSetChecked(QrosBusKey(module_id,"STATE"),(double)state))
      PrintFormat("QROS BUS STATE write failed module=%d",module_id);
  }

int QrosBusState(const int module_id)
  {
   long state=0;
   if(!QrosGvGetExactLong(QrosBusKey(module_id,"STATE"),state)) return QROS_STATE_OFF;
   if(state<QROS_STATE_OFF || state>QROS_STATE_FAULT) return QROS_STATE_FAULT;
   return (int)state;
  }

void QrosBusClearRuntime(const int module_id)
  {
   GlobalVariableDel(QrosBusKey(module_id,"HB"));
   GlobalVariableDel(QrosBusKey(module_id,"STATE"));
   GlobalVariableDel(QrosBusKey(module_id,"WM"));
  }

long QrosBusHead(const int module_id)
  {
   long h=0;
   if(!GlobalVariableCheck(QrosBusKey(module_id,"HEAD"))) return 0;
   if(!QrosGvGetExactLong(QrosBusKey(module_id,"HEAD"),h)) return -1;
   return h;
  }

long QrosBusProducerEpoch(const int module_id)
  {
   long v=0;
   if(!QrosGvGetExactLong(QrosBusKey(module_id,"EPOCH"),v)) return 0;
   return v;
  }

long QrosBusProducerOwner(const int module_id)
  {
   long v=0;
   if(!QrosGvGetExactLong(QrosBusKey(module_id,"OWNER"),v)) return 0;
   return v;
  }

void QrosBusHeartbeat(const int module_id)
  {
   QrosGvSetChecked(QrosBusKey(module_id,"HB"),(double)GetTickCount64());
  }

void QrosBusWatermark(const int module_id,const long event_ms)
  {
   if(event_ms<=0 || !QrosBusExactInteger(event_ms)) return;
   string k=QrosBusKey(module_id,"WM");
   long old=0;
   if(GlobalVariableCheck(k) && !QrosGvGetExactLong(k,old)) return;
   if(event_ms>old) QrosGvSetChecked(k,(double)event_ms);
  }

long QrosBusWatermarkMs(const int module_id)
  {
   long v=0;
   if(!QrosGvGetExactLong(QrosBusKey(module_id,"WM"),v)) return 0;
   return v;
  }

long QrosBusHeartbeatAgeMs(const int module_id)
  {
   long then=0;
   if(!QrosGvGetExactLong(QrosBusKey(module_id,"HB"),then)) return LONG_MAX;
   long now=(long)GetTickCount64();
   if(now<then) return LONG_MAX;
   return now-then;
  }

bool QrosBusAcquirePublishLock(const int module_id)
  {
   if(!QrosBusProducerHealthy(module_id)) return false;
   string lk=QrosBusKey(module_id,"LOCK");
   if(!GlobalVariableCheck(lk))
      if(!QrosGvSetChecked(lk,0.0)) return false;

   for(int i=0;i<50;i++)
     {
      if(GlobalVariableSetOnCondition(lk,(double)g_qros_bus_owner,0.0)) return true;
      long held=0;
      if(!QrosGvGetExactLong(lk,held)) return false;
      if(held==g_qros_bus_owner) return true;
      Sleep(2);
     }
   return false;
  }

void QrosBusReleasePublishLock(const int module_id)
  {
   string lk=QrosBusKey(module_id,"LOCK");
   long held=0;
   if(QrosGvGetExactLong(lk,held) && held==g_qros_bus_owner)
      GlobalVariableSet(lk,0.0);
  }

bool QrosBusPublish(const int module_id,
                    const int action,
                    const int profile,
                    const long event_ms,
                    const double entry_ref,
                    const double sl,
                    const double tp,
                    const double aux1=0.0,
                    const double aux2=0.0)
  {
   if(module_id<QROS_MOD_XAU || module_id>QROS_MOD_DIV3) return false;
   if(action<QROS_ACT_ENTRY || action>QROS_ACT_CLOSE) return false;
   if(event_ms<=0 || !QrosBusExactInteger(event_ms)) return false;
   if(!MathIsValidNumber(entry_ref) || !MathIsValidNumber(sl) || !MathIsValidNumber(tp) ||
      !MathIsValidNumber(aux1) || !MathIsValidNumber(aux2)) return false;
   if(!QrosBusAcquirePublishLock(module_id)) return false;

   bool ok=true;
   long head=QrosBusHead(module_id);
   if(head<0 || head>=QROS_BUS_EXACT_DOUBLE_MAX-1) ok=false;
   long seq=head+1;
   int slot=(int)(seq%QROS_BUS_SLOTS);
   string sk=QrosBusSlotKey(module_id,slot,"SEQ");
   string vk=QrosBusSlotKey(module_id,slot,"VER");

   // Invalidate the previous commit before any payload field is changed.
   if(ok) ok=QrosGvSetChecked(sk,0.0);
   if(ok) ok=QrosGvSetChecked(vk,0.0);
   if(ok) ok=QrosGvSetChecked(QrosBusSlotKey(module_id,slot,"A"),(double)action);
   if(ok) ok=QrosGvSetChecked(QrosBusSlotKey(module_id,slot,"P"),(double)profile);
   if(ok) ok=QrosGvSetChecked(QrosBusSlotKey(module_id,slot,"T"),(double)event_ms);
   if(ok) ok=QrosGvSetChecked(QrosBusSlotKey(module_id,slot,"E"),entry_ref);
   if(ok) ok=QrosGvSetChecked(QrosBusSlotKey(module_id,slot,"SL"),sl);
   if(ok) ok=QrosGvSetChecked(QrosBusSlotKey(module_id,slot,"TP"),tp);
   if(ok) ok=QrosGvSetChecked(QrosBusSlotKey(module_id,slot,"X1"),aux1);
   if(ok) ok=QrosGvSetChecked(QrosBusSlotKey(module_id,slot,"X2"),aux2);
   if(ok) ok=QrosGvSetChecked(QrosBusSlotKey(module_id,slot,"UP"),(double)GetTickCount64());
   if(ok) ok=QrosGvSetChecked(QrosBusSlotKey(module_id,slot,"EP"),(double)g_qros_bus_epoch);
   if(ok) ok=QrosGvSetChecked(QrosBusSlotKey(module_id,slot,"OWN"),(double)g_qros_bus_owner);

   // Version + sequence + HEAD are the commit chain, in that order.
   if(ok) ok=QrosGvSetChecked(vk,(double)seq);
   if(ok) ok=QrosGvSetChecked(sk,(double)seq);
   if(ok) ok=QrosGvSetChecked(QrosBusKey(module_id,"HEAD"),(double)seq);
   if(ok)
     {
      QrosBusWatermark(module_id,event_ms);
      QrosBusHeartbeat(module_id);
      GlobalVariablesFlush();
     }
   else
     {
      GlobalVariableSet(sk,0.0);
      GlobalVariableSet(vk,0.0);
      QrosBusSetState(module_id,QROS_STATE_FAULT);
     }

   QrosBusReleasePublishLock(module_id);
   return ok;
  }

bool QrosBusRead(const int module_id,const long seq,QrosBusEvent &ev)
  {
   if(seq<=0 || !QrosBusExactInteger(seq)) return false;
   int slot=(int)(seq%QROS_BUS_SLOTS);
   string sk=QrosBusSlotKey(module_id,slot,"SEQ");
   string vk=QrosBusSlotKey(module_id,slot,"VER");

   long seq1=0,ver1=0;
   if(!QrosGvGetExactLong(sk,seq1) || !QrosGvGetExactLong(vk,ver1)) return false;
   if(seq1!=seq || ver1!=seq) return false;

   long action=0,profile=0,event_ms=0,up=0,epoch=0,owner=0;
   if(!QrosGvGetExactLong(QrosBusSlotKey(module_id,slot,"A"),action)) return false;
   if(!QrosGvGetExactLong(QrosBusSlotKey(module_id,slot,"P"),profile)) return false;
   if(!QrosGvGetExactLong(QrosBusSlotKey(module_id,slot,"T"),event_ms)) return false;
   if(!QrosGvGetExactLong(QrosBusSlotKey(module_id,slot,"UP"),up)) return false;
   if(!QrosGvGetExactLong(QrosBusSlotKey(module_id,slot,"EP"),epoch)) return false;
   if(!QrosGvGetExactLong(QrosBusSlotKey(module_id,slot,"OWN"),owner)) return false;

   ev.seq=seq;
   ev.module_id=module_id;
   ev.action=(int)action;
   ev.profile=(int)profile;
   ev.event_ms=event_ms;
   if(!QrosGvGetFinite(QrosBusSlotKey(module_id,slot,"E"),ev.entry_ref)) return false;
   if(!QrosGvGetFinite(QrosBusSlotKey(module_id,slot,"SL"),ev.sl)) return false;
   if(!QrosGvGetFinite(QrosBusSlotKey(module_id,slot,"TP"),ev.tp)) return false;
   if(!QrosGvGetFinite(QrosBusSlotKey(module_id,slot,"X1"),ev.aux1)) return false;
   if(!QrosGvGetFinite(QrosBusSlotKey(module_id,slot,"X2"),ev.aux2)) return false;
   ev.publish_uptime_ms=up;
   ev.producer_epoch=epoch;
   ev.producer_owner=owner;

   long ver2=0,seq2=0;
   if(!QrosGvGetExactLong(vk,ver2) || !QrosGvGetExactLong(sk,seq2)) return false;
   if(seq2!=seq || ver2!=seq) return false;
   if(ev.action<QROS_ACT_ENTRY || ev.action>QROS_ACT_CLOSE) return false;
   if(ev.event_ms<=0 || !QrosBusExactInteger(ev.event_ms)) return false;

   long current_epoch=QrosBusProducerEpoch(module_id);
   long current_owner=QrosBusProducerOwner(module_id);
   if(current_epoch<=0 || current_owner<=0) return false;
   if(ev.producer_epoch!=current_epoch || ev.producer_owner!=current_owner) return false;
   return true;
  }

#endif
