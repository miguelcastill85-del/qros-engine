//+------------------------------------------------------------------+
//| QROS_DEMO_BUS_v2.mqh                                             |
//| Terminal-global ring bus. No network, DLL or external service.   |
//+------------------------------------------------------------------+
#ifndef __QROS_DEMO_BUS_V2__
#define __QROS_DEMO_BUS_V2__

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
  };

string QrosBusKey(const int module_id,const string suffix)
  {
   return "QDB1."+IntegerToString(module_id)+"."+suffix;
  }

string QrosBusSlotKey(const int module_id,const int slot,const string field)
  {
   return "QDB1."+IntegerToString(module_id)+".S"+IntegerToString(slot)+"."+field;
  }


void QrosBusSetState(const int module_id,const int state)
  {
   GlobalVariableSet(QrosBusKey(module_id,"STATE"),(double)state);
  }

int QrosBusState(const int module_id)
  {
   string k=QrosBusKey(module_id,"STATE");
   if(!GlobalVariableCheck(k)) return QROS_STATE_OFF;
   return (int)GlobalVariableGet(k);
  }

void QrosBusClearRuntime(const int module_id)
  {
   GlobalVariableDel(QrosBusKey(module_id,"HB"));
   GlobalVariableDel(QrosBusKey(module_id,"STATE"));
  }

long QrosBusHead(const int module_id)
  {
   string k=QrosBusKey(module_id,"HEAD");
   if(!GlobalVariableCheck(k)) return 0;
   return (long)GlobalVariableGet(k);
  }

void QrosBusHeartbeat(const int module_id)
  {
   GlobalVariableSet(QrosBusKey(module_id,"HB"),(double)GetTickCount64());
  }

long QrosBusHeartbeatAgeMs(const int module_id)
  {
   string k=QrosBusKey(module_id,"HB");
   if(!GlobalVariableCheck(k)) return LONG_MAX;
   long then=(long)GlobalVariableGet(k);
   long now=(long)GetTickCount64();
   if(now<then) return LONG_MAX;
   return now-then;
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
   long seq=QrosBusHead(module_id)+1;
   int slot=(int)(seq%QROS_BUS_SLOTS);

   GlobalVariableSet(QrosBusSlotKey(module_id,slot,"A"),(double)action);
   GlobalVariableSet(QrosBusSlotKey(module_id,slot,"P"),(double)profile);
   GlobalVariableSet(QrosBusSlotKey(module_id,slot,"T"),(double)event_ms);
   GlobalVariableSet(QrosBusSlotKey(module_id,slot,"E"),entry_ref);
   GlobalVariableSet(QrosBusSlotKey(module_id,slot,"SL"),sl);
   GlobalVariableSet(QrosBusSlotKey(module_id,slot,"TP"),tp);
   GlobalVariableSet(QrosBusSlotKey(module_id,slot,"X1"),aux1);
   GlobalVariableSet(QrosBusSlotKey(module_id,slot,"X2"),aux2);
   GlobalVariableSet(QrosBusSlotKey(module_id,slot,"UP"),(double)GetTickCount64());

   // Commit slot sequence last, then head last. Readers reject torn slots.
   GlobalVariableSet(QrosBusSlotKey(module_id,slot,"SEQ"),(double)seq);
   GlobalVariableSet(QrosBusKey(module_id,"HEAD"),(double)seq);
   QrosBusHeartbeat(module_id);
   return true;
  }

bool QrosBusRead(const int module_id,const long seq,QrosBusEvent &ev)
  {
   if(seq<=0) return false;
   int slot=(int)(seq%QROS_BUS_SLOTS);
   string sk=QrosBusSlotKey(module_id,slot,"SEQ");
   if(!GlobalVariableCheck(sk)) return false;
   long committed=(long)GlobalVariableGet(sk);
   if(committed!=seq) return false;

   ev.seq=seq;
   ev.module_id=module_id;
   ev.action=(int)GlobalVariableGet(QrosBusSlotKey(module_id,slot,"A"));
   ev.profile=(int)GlobalVariableGet(QrosBusSlotKey(module_id,slot,"P"));
   ev.event_ms=(long)GlobalVariableGet(QrosBusSlotKey(module_id,slot,"T"));
   ev.entry_ref=GlobalVariableGet(QrosBusSlotKey(module_id,slot,"E"));
   ev.sl=GlobalVariableGet(QrosBusSlotKey(module_id,slot,"SL"));
   ev.tp=GlobalVariableGet(QrosBusSlotKey(module_id,slot,"TP"));
   ev.aux1=GlobalVariableGet(QrosBusSlotKey(module_id,slot,"X1"));
   ev.aux2=GlobalVariableGet(QrosBusSlotKey(module_id,slot,"X2"));
   ev.publish_uptime_ms=(long)GlobalVariableGet(QrosBusSlotKey(module_id,slot,"UP"));

   // Re-check commit after payload read.
   return ((long)GlobalVariableGet(sk)==seq);
  }
#endif
