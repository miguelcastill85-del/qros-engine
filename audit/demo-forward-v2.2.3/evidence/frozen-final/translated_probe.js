// TEST_ONLY scripted boundary. No filesystem/network/MT5 access in these stubs.
const LONG_MAX=9223372036854775807, INVALID_HANDLE=-1;
const INIT_FAILED=-1,INIT_PARAMETERS_INCORRECT=-2,INIT_SUCCEEDED=0;
const FILE_WRITE=1,FILE_CSV=2,FILE_ANSI=4,FILE_COMMON=8;
const TIME_DATE=1,TIME_SECONDS=2,TIME_MINUTES=4;
const ACCOUNT_TRADE_MODE='mode',ACCOUNT_TRADE_MODE_DEMO=0,ACCOUNT_SERVER='server',ACCOUNT_CURRENCY='currency',ACCOUNT_LOGIN='login',ACCOUNT_BALANCE='balance';
const MQL_TRADE_ALLOWED='mql_allowed',TERMINAL_TRADE_ALLOWED='trade_allowed';
const SYMBOL_TRADE_TICK_SIZE='grid',SYMBOL_POINT='point',SYMBOL_DIGITS='digits',SYMBOL_VOLUME_MIN='min',SYMBOL_VOLUME_MAX='max',SYMBOL_VOLUME_STEP='step';
const POSITION_MAGIC='magic',POSITION_SYMBOL='symbol',POSITION_PRICE_OPEN='open',POSITION_SL='sl',POSITION_TP='tp',POSITION_VOLUME='volume',POSITION_TYPE='type',POSITION_TIME='time';
const POSITION_TYPE_BUY=0,ORDER_TYPE_BUY=0,ORDER_TYPE_SELL=1;
const DEAL_MAGIC='magic',DEAL_ENTRY='entry',DEAL_POSITION_ID='pid',DEAL_ENTRY_IN=0,DEAL_ENTRY_INOUT=2;
const TRADE_RETCODE_DONE=10009,TRADE_RETCODE_DONE_PARTIAL=10010,TRADE_RETCODE_PLACED=10008;
const REJECT=10006,TIMEOUT=10012,CHART_EXPERT_NAME=0,SERIES_SYNCHRONIZED=0;
let InpFreshTickMaxAgeSec=60,InpExpectedArmed=1;
let S;
function MqlTick(){this.bid=0;this.ask=0;this.time=0;this.time_msc=0;}
function MqlDateTime(){this.year=0;this.mon=0;this.day=0;this.hour=0;this.min=0;this.sec=0;}
function MathAbs(x){return Math.abs(x)}
function MathPow(x,y){return Math.pow(x,y)}
function MathMin(x,y){return Math.min(x,y)}
function MathRound(x){return Math.sign(x)*Math.floor(Math.abs(x)+0.5)}
function MathFloor(x){return Math.floor(x)}
function MathIsValidNumber(x){return Number.isFinite(x)}
function NormalizeDouble(x,d){return Number(x.toFixed(d))}
function IntegerToString(x){return String(x)}
function DoubleToString(x,d){return x.toFixed(d)}
function ArraySize(x){return x.length}
function ArrayResize(x,n){x.length=n;return n}
function ZeroMemory(x){for(const k of Object.keys(x))x[k]=typeof x[k]==='string'?'':0}
function ResetLastError(){}
function GetLastError(){return 999}
function Print(){}
function GetTickCount64(){return S.uptime}
function TimeTradeServer(){return S.now}
function TimeGMT(){return S.now-S.offset}
function TimeToStruct(t,s){let d=new Date(t*1000);Object.assign(s,{year:d.getUTCFullYear(),mon:d.getUTCMonth()+1,day:d.getUTCDate(),hour:d.getUTCHours(),min:d.getUTCMinutes(),sec:d.getUTCSeconds()});return true}
function StructToTime(s){return Date.UTC(s.year,s.mon-1,s.day,s.hour,s.min,s.sec)/1000}
function TimeToString(t){return new Date(t*1000).toISOString()}
function AccountInfoInteger(k){return S.account[k]}
function AccountInfoString(k){return S.account[k]}
function AccountInfoDouble(k){return S.account[k]}
function MQLInfoInteger(k){return S[k]}
function TerminalInfoInteger(k){return S[k]}
function GlobalVariableCheck(k){return S.gv.has(k)}
function GlobalVariableGet(k){if(S.onGet)S.onGet(k);return S.gv.get(k)??0}
function GlobalVariableSet(k,v){if(S.onSet && S.onSet(k,v)===false)return 0;S.gv.set(k,Number(v));return 1}
function GlobalVariableDel(k){return S.gv.delete(k)}
function SymbolInfoTick(sym,tick){if(!S.ticks[sym])return false;Object.assign(tick,S.ticks[sym]);return true}
function SymbolInfoDouble(sym,k){return S.spec[k]}
function SymbolInfoInteger(sym,k){return S.spec[k]}
function OrderCalcProfit(type,sym,vol,entry,stop,out){S.profit_calls++;if(!S.profit_ok)return false;out.value=S.profit_nan_after && S.profit_calls>=S.profit_nan_after?NaN:(stop-entry)*vol*(type===ORDER_TYPE_BUY?1:-1)*S.spec.multiplier;return true}
function PositionsTotal(){return S.positions.length}
function PositionGetTicket(i){S.selected=S.positions[i];return S.selected?.ticket??0}
function PositionSelectByTicket(t){S.selected=S.positions.find(p=>p.ticket===t);return !!S.selected}
function PositionGetInteger(k){return S.selected?.[k]??0}
function PositionGetDouble(k){return S.selected?.[k]??0}
function PositionGetString(k){return S.selected?.[k]??''}
function HistorySelect(){return S.history_ok}
function HistoryDealsTotal(){return S.deals.length}
function HistoryDealGetTicket(i){return i+1}
function HistoryDealGetInteger(t,k){return S.deals[t-1][k]}
function FileOpen(){if(!S.file_open)return -1;S.rows=[];return 1}
function FileWrite(handle,...args){if(!S.file_write)return 0;S.rows.push(args);return 1}
function FileFlush(){}
function FileClose(){}
function EventSetMillisecondTimer(){return S.timer_ok}
function EventKillTimer(){}
function ChartGetString(id){return S.charts[id]??''}
function iTime(sym,tf){return S.now-(S.series_age??0)}
function SeriesInfoInteger(){return S.series_sync}
function CTrade(){this.rc=0;this.order=0;this.deal=0;this.magic=0;}
CTrade.prototype.SetExpertMagicNumber=function(m){this.magic=m};
CTrade.prototype.SetTypeFillingBySymbol=function(){return true};
CTrade.prototype.SetAsyncMode=function(){};
CTrade.prototype.ResultRetcode=function(){return this.rc};
CTrade.prototype.ResultOrder=function(){return this.order};
CTrade.prototype.ResultDeal=function(){return this.deal};
CTrade.prototype.Buy=function(volume,symbol,price,sl,tp,comment){
  const response=S.responses.shift()??{ok:true,rc:TRADE_RETCODE_DONE,visible:1};
  this.rc=response.rc;this.order=100+S.requests.length;this.deal=response.visible?this.order+1000:0;
  const req={volume,symbol,price,sl,tp,comment,magic:this.magic,order:this.order,rc:this.rc};
  S.requests.push(req);
  if(response.visible){S.positions.push({ticket:this.order,magic:this.magic,symbol,volume:volume*response.visible,open:S.ticks[symbol].ask+(response.slippage??0),sl:response.unprotected?0:sl,tp,type:0,time:S.now});}
  if(response.pending)S.orders.push({...req,volume:volume*(1-(response.visible??0))});
  return response.ok;
};
CTrade.prototype.PositionModify=function(t,sl,tp){this.rc=S.modify.rc;S.modify_calls++;if(S.modify.apply && PositionSelectByTicket(t)){S.selected.sl=sl;S.selected.tp=tp}return S.modify.ok};
CTrade.prototype.PositionClose=function(t){this.rc=S.close.rc;S.close_calls++;if(S.close.apply)S.positions=S.positions.filter(p=>p.ticket!==t);return S.close.ok};

function reset(){
 S={now:Date.UTC(2026,8,7,12)/1000,offset:10800,uptime:100000,gv:new Map(),positions:[],orders:[],deals:[],requests:[],rows:[],responses:[],
 account:{mode:0,server:'Darwinex-Demo',currency:'USD',login:1,balance:10000},mql_allowed:true,trade_allowed:true,connected:true,
 spec:{grid:0.01,point:0.01,digits:2,min:0.01,max:100,step:0.01,multiplier:100},
 profit_ok:true,profit_calls:0,history_ok:true,file_open:true,file_write:true,timer_ok:true,series_sync:1,
 modify:{ok:true,rc:TRADE_RETCODE_DONE,apply:true},close:{ok:true,rc:TRADE_RETCODE_DONE,apply:true},modify_calls:0,close_calls:0,
 charts:{1:'QROS_XAU_M1_DEMO_EMITTER_v2',2:'QROS_NQX_17_31_DEMO_EMITTER_v2',3:'QROS_DIV3_R3_DEMO_EMITTER_v2_1'}};
 S.ticks={XAUUSD:{bid:99,ask:100,time:S.now,time_msc:S.now*1000},NDX:{bid:99,ask:100,time:S.now,time_msc:S.now*1000}};
 g_trade=new CTrade();g_log=1;g_last_seq=[0,0,0,0];g_fault=false;g_recovery_lock=false;g_fault_reason='';g_last_accepted_event_ms=-1;g_last_day_key=-1;g_day_entries=0;g_pending=[];
 InpArmDemoOrders=true;InpArmToken=QROS_ARM_TOKEN;InpRiskPctBalance=0.50;InpMaxReservedRiskPct=1;InpMaxNewEntriesPerServerDay=3;InpHeartbeatMaxAgeMs=5000;InpPriorityBufferMs=300;
 S.gv.set('QDB1.EXEC.CERT',1);S.gv.set('QDB1.EXEC.HB',S.uptime);S.gv.set('QDB1.EXEC.ARMED',1);
 for(let m=1;m<=3;m++){QrosBusSetState(m,2);QrosBusHeartbeat(m)}
 RebuildDailyCount();
}
function event(m=1,t=S.now*1000,p=m===2?17:0,a=1){return Object.assign(new QrosBusEvent(),{module_id:m,event_ms:t,profile:p,action:a,sl:99,tp:102})}
function position(m=1,extra={}){const ev=event(m);const p={ticket:500+S.positions.length,magic:MagicFor(m,ev.profile),symbol:SymbolFor(m),volume:0.5,open:100,sl:99,tp:102,time:S.now,type:0,...extra};S.positions.push(p);return p}
function risk(){return S.positions.reduce((a,p)=>a+Math.abs((p.open-p.sl)*p.volume*S.spec.multiplier),0)+S.orders.reduce((a,p)=>a+(100-p.sl)*p.volume*S.spec.multiplier,0)}
function publish(ev){return QrosBusPublish(ev.module_id,ev.action,ev.profile,ev.event_ms,ev.entry_ref,ev.sl,ev.tp,ev.aux1,ev.aux2)}
function decision(){return S.rows.at(-1)?.[3]??'NONE'}


// SOURCE: frozen/MQL5/Include/QROS_DEMO_BUS_v2.mqh


const QROS_MOD_XAU=1;
const QROS_MOD_NQX=2;
const QROS_MOD_DIV3=3;const QROS_ACT_ENTRY=1;
const QROS_ACT_MODIFY_SL=2;
const QROS_ACT_CLOSE=3;const QROS_BUS_SLOTS=32;const QROS_STATE_OFF=0;
const QROS_STATE_INIT=1;
const QROS_STATE_READY=2;
const QROS_STATE_FAULT=3;
function QrosBusEvent(){this.seq=0;this.module_id=0;this.action=0;this.profile=0;this.event_ms=0;this.entry_ref=0;this.sl=0;this.tp=0;this.aux1=0;this.aux2=0;this.publish_uptime_ms=0;}

function QrosBusKey(module_id,suffix){
   return "QDB1."+IntegerToString(module_id)+"."+suffix;
  }

function QrosBusSlotKey(module_id,slot,field){
   return "QDB1."+IntegerToString(module_id)+".S"+IntegerToString(slot)+"."+field;
  }


function QrosBusSetState(module_id,state){
   GlobalVariableSet(QrosBusKey(module_id,"STATE"),state);
  }

function QrosBusState(module_id){
   let k=QrosBusKey(module_id,"STATE");
   if(!GlobalVariableCheck(k)) return QROS_STATE_OFF;
   return Math.trunc(GlobalVariableGet(k));
  }

function QrosBusClearRuntime(module_id){
   GlobalVariableDel(QrosBusKey(module_id,"HB"));
   GlobalVariableDel(QrosBusKey(module_id,"STATE"));
  }

function QrosBusHead(module_id){
   let k=QrosBusKey(module_id,"HEAD");
   if(!GlobalVariableCheck(k)) return 0;
   return Math.trunc(GlobalVariableGet(k));
  }

function QrosBusHeartbeat(module_id){
   GlobalVariableSet(QrosBusKey(module_id,"HB"),GetTickCount64());
  }

function QrosBusHeartbeatAgeMs(module_id){
   let k=QrosBusKey(module_id,"HB");
   if(!GlobalVariableCheck(k)) return LONG_MAX;
   let then=Math.trunc(GlobalVariableGet(k));
   let now=Math.trunc(GetTickCount64());
   if(now<then) return LONG_MAX;
   return now-then;
  }

function QrosBusPublish(module_id,action,profile,event_ms,entry_ref,sl,tp,aux1=0.0,aux2=0.0){
   if(module_id<QROS_MOD_XAU || module_id>QROS_MOD_DIV3) return false;
   if(action<QROS_ACT_ENTRY || action>QROS_ACT_CLOSE) return false;
   let seq=QrosBusHead(module_id)+1;
   let slot=Math.trunc((seq%QROS_BUS_SLOTS));

   GlobalVariableSet(QrosBusSlotKey(module_id,slot,"A"),action);
   GlobalVariableSet(QrosBusSlotKey(module_id,slot,"P"),profile);
   GlobalVariableSet(QrosBusSlotKey(module_id,slot,"T"),event_ms);
   GlobalVariableSet(QrosBusSlotKey(module_id,slot,"E"),entry_ref);
   GlobalVariableSet(QrosBusSlotKey(module_id,slot,"SL"),sl);
   GlobalVariableSet(QrosBusSlotKey(module_id,slot,"TP"),tp);
   GlobalVariableSet(QrosBusSlotKey(module_id,slot,"X1"),aux1);
   GlobalVariableSet(QrosBusSlotKey(module_id,slot,"X2"),aux2);
   GlobalVariableSet(QrosBusSlotKey(module_id,slot,"UP"),GetTickCount64());

   
   GlobalVariableSet(QrosBusSlotKey(module_id,slot,"SEQ"),seq);
   GlobalVariableSet(QrosBusKey(module_id,"HEAD"),seq);
   QrosBusHeartbeat(module_id);
   return true;
  }

function QrosBusRead(module_id,seq,ev){
   if(seq<=0) return false;
   let slot=Math.trunc((seq%QROS_BUS_SLOTS));
   let sk=QrosBusSlotKey(module_id,slot,"SEQ");
   if(!GlobalVariableCheck(sk)) return false;
   let committed=Math.trunc(GlobalVariableGet(sk));
   if(committed!=seq) return false;

   ev.seq=seq;
   ev.module_id=module_id;
   ev.action=Math.trunc(GlobalVariableGet(QrosBusSlotKey(module_id,slot,"A")));
   ev.profile=Math.trunc(GlobalVariableGet(QrosBusSlotKey(module_id,slot,"P")));
   ev.event_ms=Math.trunc(GlobalVariableGet(QrosBusSlotKey(module_id,slot,"T")));
   ev.entry_ref=GlobalVariableGet(QrosBusSlotKey(module_id,slot,"E"));
   ev.sl=GlobalVariableGet(QrosBusSlotKey(module_id,slot,"SL"));
   ev.tp=GlobalVariableGet(QrosBusSlotKey(module_id,slot,"TP"));
   ev.aux1=GlobalVariableGet(QrosBusSlotKey(module_id,slot,"X1"));
   ev.aux2=GlobalVariableGet(QrosBusSlotKey(module_id,slot,"X2"));
   ev.publish_uptime_ms=Math.trunc(GlobalVariableGet(QrosBusSlotKey(module_id,slot,"UP")));

   
   return (Math.trunc(GlobalVariableGet(sk))==seq);
  }


// SOURCE: frozen/MQL5/Include/QROS_RISK_KERNEL_APPROVED_v15420.mqh



function QrosRiskResult(){this.ok=0;this.reason="";this.balance=0;this.target_pct=0;this.target_usd=0;this.loss_1lot_usd=0;this.raw_volume=0;this.volume=0;this.actual_risk_usd=0;this.utilization=0;}

function QrosVolumeDigits(step){
   if(step<=0.0) return 8;
   for(let d=0; d<=8; d++)
   {
      let x=step*MathPow(10.0,d);
      if(MathAbs(x-MathRound(x))<1e-9) return d;
   }
   return 8;
}

function QrosFloorVolume(symbol,raw){
   let vmin=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN);
   let vmax=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MAX);
   let step=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);
   if(vmin<=0.0 || vmax<vmin || step<=0.0 || raw<=0.0) return 0.0;

   let capped=MathMin(raw,vmax);
   let n=MathFloor((capped+1e-12)/step);
   let v=n*step;
   v=NormalizeDouble(v,QrosVolumeDigits(step));
   if(v+1e-12<vmin) return 0.0;
   if(v>vmax) v=vmax;
   return v;
}

function QrosRiskSize(symbol,order_type,entry,stop,account_balance,target_risk_pct,out){
   out.ok=false;
   out.reason="";
   out.balance=account_balance;
   out.target_pct=target_risk_pct;
   out.target_usd=0.0;
   out.loss_1lot_usd=0.0;
   out.raw_volume=0.0;
   out.volume=0.0;
   out.actual_risk_usd=0.0;
   out.utilization=0.0;

   if(order_type!=ORDER_TYPE_BUY && order_type!=ORDER_TYPE_SELL)
   {
      out.reason="INVALID_ORDER_TYPE";
      return false;
   }
   if(entry<=0.0 || stop<=0.0 || MathAbs(entry-stop)<=0.0)
   {
      out.reason="INVALID_ENTRY_OR_STOP";
      return false;
   }
   if(account_balance<=0.0 || target_risk_pct<=0.0)
   {
      out.reason="INVALID_BALANCE_OR_TARGET";
      return false;
   }

   out.target_usd=account_balance*(target_risk_pct/100.0);

   let p1=0.0;
   ResetLastError();
   if(!OrderCalcProfit(order_type,symbol,1.0,entry,stop,{set value(v){p1=v;}}))
   {
      out.reason="ORDERCALCPROFIT_1LOT_FAILED_"+IntegerToString(GetLastError());
      return false;
   }
   out.loss_1lot_usd=MathAbs(p1);
   if(out.loss_1lot_usd<=0.0 || !MathIsValidNumber(out.loss_1lot_usd))
   {
      out.reason="INVALID_1LOT_LOSS";
      return false;
   }

   out.raw_volume=out.target_usd/out.loss_1lot_usd;
   out.volume=QrosFloorVolume(symbol,out.raw_volume);
   if(out.volume<=0.0)
   {
      out.reason="MIN_VOLUME_EXCEEDS_TARGET";
      return false;
   }

   let vmin=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN);
   let step=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);
   let vd=QrosVolumeDigits(step);

   for(let guard=0; guard<100000; guard++)
   {
      let pv=0.0;
      ResetLastError();
      if(!OrderCalcProfit(order_type,symbol,out.volume,entry,stop,{set value(v){pv=v;}}))
      {
         out.reason="ORDERCALCPROFIT_VOLUME_FAILED_"+IntegerToString(GetLastError());
         return false;
      }
      out.actual_risk_usd=MathAbs(pv);
      if(out.actual_risk_usd<=out.target_usd+0.01)
         break;

      let next=NormalizeDouble(out.volume-step,vd);
      if(next+1e-12<vmin)
      {
         out.reason="CANNOT_ROUND_DOWN_WITHOUT_EXCEEDING_TARGET";
         return false;
      }
      out.volume=next;
   }

   if(out.actual_risk_usd>out.target_usd+0.01)
   {
      out.reason="RISK_STILL_ABOVE_TARGET";
      return false;
   }

   out.utilization=(out.target_usd>0.0 ? out.actual_risk_usd/out.target_usd : 0.0);
   out.ok=true;
   out.reason="PASS";
   return true;
}


// SOURCE: frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5







let InpArmDemoOrders=false;
let InpArmToken="";
let InpRiskPctBalance=0.50;
let InpMaxReservedRiskPct=1.00;
let InpMaxNewEntriesPerServerDay=3;
let InpHeartbeatMaxAgeMs=5000;
let InpPriorityBufferMs=300;
let InpAuditPrefix="QROS_DEMO_EXECUTOR_v1";

let QROS_REQUIRED_SERVER="Darwinex-Demo";
let QROS_REQUIRED_CURRENCY="USD";
let QROS_ARM_TOKEN="QROS_DEMO_ARM_v1_8af000_2d6ebd";
let MAGIC_XAU=560101;
let MAGIC_NQX17=560217;
let MAGIC_NQX31=560231;
let MAGIC_DIV3=560300;

let g_trade=new CTrade();
let g_log=INVALID_HANDLE;
let g_last_seq=[0,0,0,0];
let g_fault=false;
let g_recovery_lock=false;
let g_fault_reason="";
let g_last_accepted_event_ms=-1;
let g_last_day_key=-1;
let g_day_entries=0;

function PendingEntry(){this.ev=new QrosBusEvent();this.received_uptime_ms=0;}
let g_pending=[];

function IsQrosMagic(m){
   return (m==MAGIC_XAU || m==MAGIC_NQX17 || m==MAGIC_NQX31 || m==MAGIC_DIV3);
  }

function MagicFor(module_id,profile){
   if(module_id==QROS_MOD_XAU) return MAGIC_XAU;
   if(module_id==QROS_MOD_DIV3) return MAGIC_DIV3;
   if(module_id==QROS_MOD_NQX && profile==17) return MAGIC_NQX17;
   if(module_id==QROS_MOD_NQX && profile==31) return MAGIC_NQX31;
   return -1;
  }

function SymbolFor(module_id){
   if(module_id==QROS_MOD_XAU) return "XAUUSD";
   if(module_id==QROS_MOD_NQX || module_id==QROS_MOD_DIV3) return "NDX";
   return "";
  }

function PriorityFor(module_id){
   if(module_id==QROS_MOD_XAU) return 0;
   if(module_id==QROS_MOD_NQX) return 1;
   if(module_id==QROS_MOD_DIV3) return 2;
   return 99;
  }

function ServerDayKey(){
   let t=TimeTradeServer();
   let s=new MqlDateTime(); TimeToStruct(t,s);
   return s.year*10000+s.mon*100+s.day;
  }

function ServerDayStart(){
   let t=TimeTradeServer();
   let s=new MqlDateTime(); TimeToStruct(t,s);
   s.hour=0;s.min=0;s.sec=0;
   return StructToTime(s);
  }

function LogRow(stage,decision,ev,reason,symbol,bid,ask,volume,sl,tp,ticket=0){
   if(g_log==INVALID_HANDLE) return;
   FileWrite(g_log,
      TimeToString(TimeTradeServer(),TIME_DATE|TIME_SECONDS),
      Math.trunc(GetTickCount64()),stage,decision,reason,
      ev.module_id,ev.profile,ev.seq,ev.event_ms,ev.action,
      symbol,bid,ask,volume,sl,tp,Math.trunc(ticket),
      AccountInfoString(ACCOUNT_SERVER),Math.trunc(AccountInfoInteger(ACCOUNT_LOGIN)),
      DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE),2));
   FileFlush(g_log);
  }

function SetFault(reason){
   g_fault=true;g_fault_reason=reason;
   Print("QROS DEMO EXECUTOR FAULT: ",reason);
  }

function DemoAccountGate(){
   if(AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO)
     { SetFault("ACCOUNT_NOT_DEMO"); return false; }
   if(AccountInfoString(ACCOUNT_SERVER)!=QROS_REQUIRED_SERVER)
     { SetFault("WRONG_SERVER_"+AccountInfoString(ACCOUNT_SERVER)); return false; }
   if(AccountInfoString(ACCOUNT_CURRENCY)!=QROS_REQUIRED_CURRENCY)
     { SetFault("WRONG_CURRENCY_"+AccountInfoString(ACCOUNT_CURRENCY)); return false; }
   return true;
  }

function ArmGate(){
   if(!InpArmDemoOrders) return false;
   if(InpArmToken!=QROS_ARM_TOKEN){ SetFault("INVALID_ARM_TOKEN"); return false; }
   if(!MQLInfoInteger(MQL_TRADE_ALLOWED)){ SetFault("MQL_TRADE_NOT_ALLOWED"); return false; }
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)){ SetFault("TERMINAL_TRADE_NOT_ALLOWED"); return false; }
   return true;
  }

function RuntimeCertified(){
   let k="QDB1.EXEC.CERT";
   return (GlobalVariableCheck(k) && Math.trunc(GlobalVariableGet(k))==1);
  }

function HasOpenQrosPosition(){
   for(let i=PositionsTotal()-1;i>=0;i--)
     {
      let ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      if(IsQrosMagic(Math.trunc(PositionGetInteger(POSITION_MAGIC)))) return true;
     }
   return false;
  }

function HeartbeatsReady(){
   for(let m=1;m<=3;m++)
     {
      if(QrosBusState(m)!=QROS_STATE_READY) return false;
      let age=QrosBusHeartbeatAgeMs(m);
      if(age<0 || age>InpHeartbeatMaxAgeMs) return false;
     }
   return true;
  }

function PositiveSpread(symbol,tick){
   if(!SymbolInfoTick(symbol,tick)) return false;
   if(!(tick.bid>0.0) || !(tick.ask>0.0)) return false;
   return tick.ask>tick.bid;
  }

function GridNormalize(symbol,price){
   let ts=SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_SIZE);
   if(!(ts>0.0)) ts=SymbolInfoDouble(symbol,SYMBOL_POINT);
   let digits=Math.trunc(SymbolInfoInteger(symbol,SYMBOL_DIGITS));
   if(!(ts>0.0)) return NormalizeDouble(price,digits);
   return NormalizeDouble(MathRound(price/ts)*ts,digits);
  }

function AnyPositionOnAsset(symbol){
   for(let i=PositionsTotal()-1;i>=0;i--)
     {
      let ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL)==symbol) return true;
     }
   return false;
  }

function FindQrosPosition(symbol,magic){
   for(let i=PositionsTotal()-1;i>=0;i--)
     {
      let ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL)!=symbol) continue;
      if(Math.trunc(PositionGetInteger(POSITION_MAGIC))==magic) return ticket;
     }
   return 0;
  }

function ReservedRiskUsd(ok){
   ok.value=true;
   let total=0.0;
   for(let i=PositionsTotal()-1;i>=0;i--)
     {
      let ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      let magic=Math.trunc(PositionGetInteger(POSITION_MAGIC));
      if(!IsQrosMagic(magic)) continue;
      let sym=PositionGetString(POSITION_SYMBOL);
      let openp=PositionGetDouble(POSITION_PRICE_OPEN);
      let sl=PositionGetDouble(POSITION_SL);
      let vol=PositionGetDouble(POSITION_VOLUME);
      let ptype=Math.trunc(PositionGetInteger(POSITION_TYPE));
      if(!(sl>0.0) || !(vol>0.0)){ok.value=false;return 0.0;}
      let ot=(ptype==POSITION_TYPE_BUY?ORDER_TYPE_BUY:ORDER_TYPE_SELL);
      let p=0.0;
      if(!OrderCalcProfit(ot,sym,vol,openp,sl,{set value(v){p=v;}})){ok.value=false;return 0.0;}
      total+=MathAbs(p);
     }
   return total;
  }

function RebuildDailyCount(){
   g_day_entries=0;
   let from=ServerDayStart();
   let to=TimeTradeServer()+60;
   if(!HistorySelect(from,to)) return;
   let seen=[];
   ArrayResize(seen,0);
   let n=HistoryDealsTotal();
   for(let i=0;i<n;i++)
     {
      let d=HistoryDealGetTicket(i);
      if(d==0) continue;
      let magic=Math.trunc(HistoryDealGetInteger(d,DEAL_MAGIC));
      if(!IsQrosMagic(magic)) continue;
      let entry=Math.trunc(HistoryDealGetInteger(d,DEAL_ENTRY));
      if(entry!=DEAL_ENTRY_IN && entry!=DEAL_ENTRY_INOUT) continue;
      let pid=Math.trunc(HistoryDealGetInteger(d,DEAL_POSITION_ID));
      let exists=false;
      for(let j=0;j<ArraySize(seen);j++) if(seen[j]==pid){exists=true;break;}
      if(!exists)
        {
         let z=ArraySize(seen);ArrayResize(seen,z+1);seen[z]=pid;g_day_entries++;
        }
     }
   g_last_day_key=ServerDayKey();
   let kday="QDB1.EXEC.DAY";
   let kev="QDB1.EXEC.LASTEV";
   if(GlobalVariableCheck(kday) && Math.trunc(GlobalVariableGet(kday))==g_last_day_key && GlobalVariableCheck(kev))
      g_last_accepted_event_ms=Math.trunc(GlobalVariableGet(kev));
   else
      g_last_accepted_event_ms=-1;
  }

function RefreshDay(){
   let dk=ServerDayKey();
   if(dk!=g_last_day_key)
     {
      RebuildDailyCount();
      g_last_accepted_event_ms=-1;
      GlobalVariableSet("QDB1.EXEC.DAY",dk);
      GlobalVariableSet("QDB1.EXEC.LASTEV",-1.0);
     }
  }

function AddPending(ev){
   let p=new PendingEntry();p.ev=ev;p.received_uptime_ms=Math.trunc(GetTickCount64());
   let n=ArraySize(g_pending);ArrayResize(g_pending,n+1);g_pending[n]=p;
  }

function Before(a,b){
   if(a.ev.event_ms!=b.ev.event_ms) return a.ev.event_ms<b.ev.event_ms;
   let pa=PriorityFor(a.ev.module_id),pb=PriorityFor(b.ev.module_id);
   if(pa!=pb) return pa<pb;
   return a.ev.profile<b.ev.profile;
  }

function SortPending(){
   let n=ArraySize(g_pending);
   for(let i=1;i<n;i++)
     {
      let key=g_pending[i];
      let j=i-1;
      while(j>=0 && Before(key,g_pending[j])){g_pending[j+1]=g_pending[j];j--;}
      g_pending[j+1]=key;
     }
  }

function SendEntry(ev){
   let symbol=SymbolFor(ev.module_id);
   let magic=MagicFor(ev.module_id,ev.profile);
   let tick=new MqlTick();
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

   let sl=GridNormalize(symbol,ev.sl);
   let tp=GridNormalize(symbol,ev.tp);
   if(!(sl>0.0) || !(tp>0.0) || sl>=tick.ask || tp<=tick.ask)
     {LogRow("ENTRY","BLOCKED",ev,"INVALID_BARRIERS_AT_REQUEST",symbol,tick.bid,tick.ask,0,sl,tp);return false;}

   let rr=new QrosRiskResult();
   let bal=AccountInfoDouble(ACCOUNT_BALANCE);
   if(!QrosRiskSize(symbol,ORDER_TYPE_BUY,tick.ask,sl,bal,InpRiskPctBalance,rr))
     {LogRow("ENTRY","BLOCKED",ev,"RISK_"+rr.reason,symbol,tick.bid,tick.ask,0,sl,tp);return false;}

   let rok=false;
   let reserved=ReservedRiskUsd({set value(v){rok=v;}});
   if(!rok){SetFault("RESERVED_RISK_UNKNOWN");LogRow("ENTRY","BLOCKED",ev,g_fault_reason,symbol,tick.bid,tick.ask,0,sl,tp);return false;}
   let maxr=bal*(InpMaxReservedRiskPct/100.0);
   if(reserved+rr.actual_risk_usd>maxr+0.01)
     {LogRow("ENTRY","BLOCKED",ev,"MAX_RESERVED_RISK_1PCT",symbol,tick.bid,tick.ask,rr.volume,sl,tp);return false;}

   if(!InpArmDemoOrders)
     {LogRow("ENTRY","CANARY_BLOCKED",ev,"ORDERS_NOT_ARMED",symbol,tick.bid,tick.ask,rr.volume,sl,tp);return false;}
   if(!ArmGate())
     {LogRow("ENTRY","BLOCKED",ev,g_fault_reason,symbol,tick.bid,tick.ask,rr.volume,sl,tp);return false;}

   g_trade.SetExpertMagicNumber(Math.trunc(magic));
   g_trade.SetTypeFillingBySymbol(symbol);
   g_trade.SetAsyncMode(false);
   let comment="QROS "+IntegerToString(ev.module_id)+"/"+IntegerToString(ev.profile);
   ResetLastError();
   let sent=g_trade.Buy(rr.volume,symbol,0.0,sl,tp,comment);
   let order=g_trade.ResultOrder();
   let deal=g_trade.ResultDeal();
   let rc=g_trade.ResultRetcode();
   if(!sent || (rc!=TRADE_RETCODE_DONE && rc!=TRADE_RETCODE_DONE_PARTIAL && rc!=TRADE_RETCODE_PLACED))
     {
      LogRow("ENTRY","BROKER_REJECT",ev,"RETCODE_"+IntegerToString(Math.trunc(rc)),symbol,tick.bid,tick.ask,rr.volume,sl,tp,order);
      return false;
     }

   g_day_entries++;
   g_last_accepted_event_ms=ev.event_ms;
   GlobalVariableSet("QDB1.EXEC.DAY",ServerDayKey());
   GlobalVariableSet("QDB1.EXEC.LASTEV",ev.event_ms);
   LogRow("ENTRY","EXECUTED",ev,"PASS",symbol,tick.bid,tick.ask,rr.volume,sl,tp,(deal>0?deal:order));
   return true;
  }

function HandleModify(ev){
   let symbol=SymbolFor(ev.module_id);let magic=MagicFor(ev.module_id,ev.profile);
   let ticket=FindQrosPosition(symbol,magic);
   if(ticket==0) return;
   if(!PositionSelectByTicket(ticket)) return;
   let oldsl=PositionGetDouble(POSITION_SL);
   let oldtp=PositionGetDouble(POSITION_TP);
   let sl=GridNormalize(symbol,ev.sl);
   let tp=(ev.tp>0.0?GridNormalize(symbol,ev.tp):oldtp);
   if(sl<=oldsl) return;
   if(!InpArmDemoOrders){LogRow("MODIFY","CANARY_BLOCKED",ev,"ORDERS_NOT_ARMED",symbol,0,0,0,sl,tp,ticket);return;}
   if(!ArmGate()) return;
   g_trade.SetExpertMagicNumber(Math.trunc(magic));
   let ok=g_trade.PositionModify(ticket,sl,tp);
   LogRow("MODIFY",ok?"EXECUTED":"BROKER_REJECT",ev,ok?"PASS":"RETCODE_"+IntegerToString(Math.trunc(g_trade.ResultRetcode())),symbol,0,0,0,sl,tp,ticket);
  }

function HandleClose(ev,reason="MODULE_CLOSE"){
   let symbol=SymbolFor(ev.module_id);let magic=MagicFor(ev.module_id,ev.profile);
   let ticket=FindQrosPosition(symbol,magic);
   if(ticket==0) return;
   if(!InpArmDemoOrders){LogRow("CLOSE","CANARY_BLOCKED",ev,"ORDERS_NOT_ARMED",symbol,0,0,0,0,0,ticket);return;}
   if(!ArmGate()) return;
   g_trade.SetExpertMagicNumber(Math.trunc(magic));
   g_trade.SetTypeFillingBySymbol(symbol);
   let ok=g_trade.PositionClose(ticket);
   LogRow("CLOSE",ok?"EXECUTED":"BROKER_REJECT",ev,ok?reason:"RETCODE_"+IntegerToString(Math.trunc(g_trade.ResultRetcode())),symbol,0,0,0,0,0,ticket);
  }

function ForceNoOvernight(){
   let dk=ServerDayKey();
   for(let i=PositionsTotal()-1;i>=0;i--)
     {
      let ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      let magic=Math.trunc(PositionGetInteger(POSITION_MAGIC));
      if(!IsQrosMagic(magic)) continue;
      let pt=PositionGetInteger(POSITION_TIME);
      let s=new MqlDateTime();TimeToStruct(pt,s);
      let pdk=s.year*10000+s.mon*100+s.day;
      if(pdk==dk) continue;
      let ev=new QrosBusEvent();ZeroMemory(ev);ev.event_ms=Math.trunc(TimeTradeServer())*1000;
      if(magic==MAGIC_XAU){ev.module_id=QROS_MOD_XAU;ev.profile=0;}
      else if(magic==MAGIC_DIV3){ev.module_id=QROS_MOD_DIV3;ev.profile=0;}
      else {ev.module_id=QROS_MOD_NQX;ev.profile=(magic==MAGIC_NQX17?17:31);}
      if(InpArmDemoOrders && ArmGate())
        {
         g_trade.SetExpertMagicNumber(Math.trunc(magic));
         g_trade.SetTypeFillingBySymbol(PositionGetString(POSITION_SYMBOL));
         let ok=g_trade.PositionClose(ticket);
         LogRow("FORCE_CLOSE",ok?"EXECUTED":"BROKER_REJECT",ev,"SERVER_DAY_BOUNDARY",PositionGetString(POSITION_SYMBOL),0,0,0,0,0,ticket);
        }
     }
  }

function PollBus(){
   for(let m=1;m<=3;m++)
     {
      let head=QrosBusHead(m);
      if(head-g_last_seq[m]>QROS_BUS_SLOTS)
        {
         SetFault("BUS_OVERFLOW_MODULE_"+IntegerToString(m));
         g_last_seq[m]=head;
         continue;
        }
      for(let s=g_last_seq[m]+1;s<=head;s++)
        {
         let ev=new QrosBusEvent();
         if(!QrosBusRead(m,s,ev)){SetFault("BUS_TORN_OR_MISSING_MODULE_"+IntegerToString(m));break;}
         g_last_seq[m]=s;
         if(ev.action==QROS_ACT_ENTRY) AddPending(ev);
         else if(ev.action==QROS_ACT_MODIFY_SL) HandleModify(ev);
         else if(ev.action==QROS_ACT_CLOSE) HandleClose(ev);
        }
     }
  }

function ProcessPending(){
   if(ArraySize(g_pending)==0) return;
   SortPending();
   let now=Math.trunc(GetTickCount64());
   let w=0;
   for(let i=0;i<ArraySize(g_pending);i++)
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

function OnInit(){
   let flags=FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON;
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

   for(let m=1;m<=3;m++) g_last_seq[m]=QrosBusHead(m); 
   RebuildDailyCount();

   if(InpArmDemoOrders && !ArmGate()) return INIT_FAILED;
   GlobalVariableSet("QDB1.EXEC.HB",GetTickCount64());
   GlobalVariableSet("QDB1.EXEC.ARMED",InpArmDemoOrders?1.0:0.0);
   EventSetMillisecondTimer(100);
   let iev=new QrosBusEvent();ZeroMemory(iev);
   LogRow("INIT","PASS",iev,InpArmDemoOrders?"ARMED_DEMO":"UNARMED_CANARY","",0,0,0,0,0);
   Print("QROS DEMO EXECUTOR initialized. armed=",InpArmDemoOrders?"true":"false");
   return INIT_SUCCEEDED;
  }

function OnTimer(){
   GlobalVariableSet("QDB1.EXEC.HB",GetTickCount64());
   GlobalVariableSet("QDB1.EXEC.ARMED",InpArmDemoOrders?1.0:0.0);
   if(g_fault) { GlobalVariableSet("QDB1.EXEC.CERT",0.0); return; }
   RefreshDay();
   ForceNoOvernight();
   PollBus();
   ProcessPending();
  }

function OnTick(){
   
   if(!g_fault){PollBus();ProcessPending();}
  }

function OnDeinit(reason){
   EventKillTimer();
   GlobalVariableSet("QDB1.EXEC.ARMED",0.0);
   GlobalVariableSet("QDB1.EXEC.CERT",0.0);
   GlobalVariableSet("QDB1.EXEC.HB",-1.0);
   if(g_log!=INVALID_HANDLE)
     {
      let ev=new QrosBusEvent();ZeroMemory(ev);
      LogRow("DEINIT","INFO",ev,"REASON_"+IntegerToString(reason),"",0,0,0,0,0);
      FileClose(g_log);
     }
  }

// SOURCE: frozen/MQL5/Scripts/QROS_V223_RUNTIME_BOOTSTRAP.mq5
function ExecAge(){
   let key="QDB1.EXEC.HB";
   if(!GlobalVariableCheck(key))
      return LONG_MAX;

   let then=Math.trunc(GlobalVariableGet(key));
   let now=Math.trunc(GetTickCount64());

   if(then<0 || now<then)
      return LONG_MAX;

   return now-then;
  }
function DemoGate(reason){
   if(AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO)
     {
      reason.value="ACCOUNT_NOT_DEMO";
      return false;
     }

   if(AccountInfoString(ACCOUNT_SERVER)!="Darwinex-Demo")
     {
      reason.value="WRONG_SERVER";
      return false;
     }

   if(AccountInfoString(ACCOUNT_CURRENCY)!="USD")
     {
      reason.value="WRONG_CURRENCY";
      return false;
     }

   return true;
  }
function ExpertName(chart_id){
   if(chart_id<=0)
      return "";
   return ChartGetString(chart_id,CHART_EXPERT_NAME);
  }
function CountQrosPositions(){
   let count=0;

   for(let i=PositionsTotal()-1;i>=0;i--)
     {
      let ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket))
         continue;

      let magic=Math.trunc(PositionGetInteger(POSITION_MAGIC));
      if(magic==560101 || magic==560217 || magic==560231 || magic==560300)
         count++;
     }

   return count;
  }
function TickState(symbol,utc_offset_sec,bid,ask,age_sec,tick_msc){
   let tick=new MqlTick();
   bid.value=0.0;
   ask.value=0.0;
   age_sec.value=LONG_MAX;
   tick_msc.value=0;

   if(!SymbolInfoTick(symbol,tick))
      return false;

   bid.value=tick.bid.value;
   ask.value=tick.ask.value;
   tick_msc.value=tick.time_msc;

   let expected_server=Math.trunc(TimeGMT())+utc_offset_sec;
   age_sec.value=expected_server-Math.trunc(tick.time);

   return (tick.bid.value>0.0 &&
           tick.ask.value>tick.bid.value &&
           age_sec.value>=-5 &&
           age_sec.value<=InpFreshTickMaxAgeSec);
  }
function SeriesCurrent(symbol,timeframe,utc_offset_sec,max_age_sec,last_bar,sync_flag){
   last_bar.value=Math.trunc(iTime(symbol,timeframe,0));
   sync_flag.value=Math.trunc(SeriesInfoInteger(symbol,timeframe,SERIES_SYNCHRONIZED));

   if(last_bar.value<=0 || sync_flag.value!=1)
      return false;

   let server_now=Math.trunc(TimeGMT())+utc_offset_sec;
   let age=server_now-last_bar.value;

   return (age>=-5 && age<=max_age_sec);
  }
function RuntimeFailure(cx,cn,cd,exec_age,xau_age,nqx_age,div3_age,xau_tick_ok,ndx_tick_ok,xau_m1_ok,ndx_m15_ok,ndx_h1_ok,offset_stable,armed){
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
function OffsetProbe(prior,stable,have){let last_offset=prior;let offset_stable=stable;let have_offset=have;let raw_offset=Math.trunc((TimeTradeServer()-TimeGMT()));
      let rounded_offset=Math.trunc(MathRound(raw_offset/3600.0))*3600;

      if(MathAbs((raw_offset-rounded_offset))<=10.0)
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

      return offset_stable;}
const PROPOSAL=false;
// Every PASS/FAIL is against a safety expectation, never against reproducing a bug.
const RESULTS=[];
function test(id,title,expected,fn){reset();const r=fn();RESULTS.push({id,title,expected_result:expected,observed_result:r.observed,status:r.safe?'PASS':'FAIL',classification:'TEST_PROVEN',scope:'TEST_ONLY_SOURCE_TRANSLATION_SCRIPTED_API'});}
function outcome(safe,observed){return {safe,observed};}
function accepted(){return S.rows.filter(r=>r[2]==='ENTRY'&&r[3]==='EXECUTED').length;}
function boot(overrides={}){return RuntimeFailure(1,2,3,0,0,0,0,true,true,true,true,true,10,1,...[]);}

test('T01','Demo account gate','Reject live mode',()=>{S.account.mode=2;return outcome(!DemoAccountGate()&&g_fault,{fault:g_fault,reason:g_fault_reason});});
test('T02','Server and currency gates','Reject wrong server and currency',()=>{S.account.server='other';let a=!DemoAccountGate();reset();S.account.currency='EUR';let b=!DemoAccountGate();return outcome(a&&b,{wrong_server_blocked:a,wrong_currency_blocked:b});});
test('T03','Armed certification gate','No Buy with CERT=0 or arm=false',()=>{S.gv.set('QDB1.EXEC.CERT',0);let a=!SendEntry(event());reset();InpArmDemoOrders=false;let b=!SendEntry(event());return outcome(a&&b&&S.requests.length===0,{cert_blocks:a,unarmed_blocks:b});});
test('T04','Runtime certificate exact value','Reject fractional CERT value',()=>{S.gv.set('QDB1.EXEC.CERT',1.5);let sent=SendEntry(event());return outcome(!sent,{cert:1.5,sent});});
test('T05','Zero and crossed spread','Reject both before Buy',()=>{S.ticks.XAUUSD.ask=99;let a=!SendEntry(event());S.ticks.XAUUSD.ask=98;let b=!SendEntry(event());return outcome(a&&b&&!S.requests.length,{zero_blocked:a,crossed_blocked:b,requests:S.requests.length});});
test('T06','Fresh executable quote after certification','Stale positive spread must block',()=>{S.ticks.XAUUSD.time-=3600;S.ticks.XAUUSD.time_msc-=3600000;let sent=SendEntry(event());return outcome(!sent,{quote_age_sec:3600,sent});});
test('T07','BUY Ask and floor volume','Risk sized at Ask <=50 USD with volume floor',()=>{S.spec.step=0.03;S.spec.min=0.03;let sent=SendEntry(event());return outcome(sent&&S.requests[0].volume===0.48&&risk()<=50,{volume:S.requests[0]?.volume,initial_risk:risk(),buy_price_argument:S.requests[0]?.price});});
test('T08','Minimum size exceeds risk','Reject rather than increase minimum volume',()=>{S.spec.min=1;let sent=SendEntry(event());return outcome(!sent&&!S.requests.length,{sent,decision:decision()});});
test('T09','OrderCalcProfit failure','Block sizing failure',()=>{S.profit_ok=false;let sent=SendEntry(event());return outcome(!sent&&!S.requests.length,{sent});});
test('T10','Risk cap visible positions','Reject 60 USD reserved + 50 USD proposed',()=>{position(1,{volume:0.6});let sent=SendEntry(event(2));return outcome(!sent,{reserved:risk(),sent});});
test('T11','One visible position per asset','Block NDX entry if any NDX position exists',()=>{position(2,{magic:999});let sent=SendEntry(event(3));return outcome(!sent,{sent,positions:S.positions.length});});
test('T12','Three entries then fourth','Fourth sequential entry blocked',()=>{for(let i=0;i<3;i++){SendEntry(event(1,S.now*1000+i));S.positions=[];}let fourth=SendEntry(event(1,S.now*1000+4));return outcome(!fourth&&S.requests.length===3,{fourth,requests:S.requests.length,count:g_day_entries});});
test('T13','Same millisecond and cohort priority','XAU wins and only one entry accepted',()=>{AddPending(event(3));AddPending(event(2));AddPending(event(1));S.uptime+=300;ProcessPending();return outcome(S.requests.length===1&&S.requests[0].symbol==='XAUUSD',{requests:S.requests.map(x=>x.symbol),accepted:accepted()});});
test('T14','Priority across buffer ages','Do not send lower priority while known same-ms XAU waits',()=>{AddPending(event(2));S.uptime+=100;AddPending(event(1));S.uptime+=200;ProcessPending();return outcome(!S.requests.length||S.requests[0].symbol==='XAUUSD',{requests:S.requests.map(x=>x.symbol),pending:g_pending.length});});
test('T15','Nonmonotonic repeated timestamp','Timestamp A accepted once even after timestamp B',()=>{const a=S.now*1000;SendEntry(event(1,a));S.positions=[];SendEntry(event(1,a+1));S.positions=[];let again=SendEntry(event(1,a));return outcome(!again,{again,requests:S.requests.length,last:g_last_accepted_event_ms});});
test('T16','Broker rejection','No daily state committed after explicit rejection',()=>{S.responses.push({ok:true,rc:REJECT});let sent=SendEntry(event());return outcome(!sent&&g_day_entries===0&&g_last_accepted_event_ms===-1,{sent,count:g_day_entries,last:g_last_accepted_event_ms});});
test('T17','PLACED delayed visibility risk and asset reservation','Outstanding orders reserve asset and risk; maximum 100 USD',()=>{for(let i=0;i<3;i++){S.responses.push({ok:true,rc:TRADE_RETCODE_PLACED,pending:true});SendEntry(event(i===0?1:2,S.now*1000+i));}return outcome(S.orders.filter(o=>o.symbol==='NDX').length<=1&&risk()<=100,{orders:S.orders.length,positions:S.positions.length,total_initial_reserved:risk(),count:g_day_entries});});
test('T18','DONE_PARTIAL and remaining volume','Reserve unfilled remainder, plus all other outstanding orders',()=>{S.responses.push({ok:true,rc:TRADE_RETCODE_DONE_PARTIAL,pending:true,visible:0.5});SendEntry(event());for(let i=1;i<=2;i++){S.responses.push({ok:true,rc:TRADE_RETCODE_PLACED,pending:true});SendEntry(event(2,S.now*1000+i));}return outcome(risk()<=100&&S.orders.filter(o=>o.symbol==='NDX').length<=1,{risk:risk(),position_volume:S.positions[0].volume,pending_volumes:S.orders.map(o=>o.volume)});});
test('T19','Disconnect after send before acknowledgement','Ambiguous send reserves asset until reconciliation',()=>{S.responses.push({ok:false,rc:TIMEOUT,pending:true});SendEntry(event());let second=SendEntry(event(1,S.now*1000+1));return outcome(!second,{second,outstanding_orders:S.orders.length,positions:S.positions.length,count:g_day_entries});});
test('T20','PLACED later cancelled','Reconcile accepted entry count to broker terminal outcome',()=>{S.responses.push({ok:true,rc:TRADE_RETCODE_PLACED,pending:true});SendEntry(event());S.orders=[];OnTimer();return outcome(g_day_entries===0,{count:g_day_entries,actual_deals:S.deals.length});});
test('T21','Actual fill price risk','Reconcile slippage before certifying 0.5 percent initial risk',()=>{S.responses.push({ok:true,rc:TRADE_RETCODE_DONE,visible:1,slippage:2});let sent=SendEntry(event());return outcome(!sent||risk()<=50,{sent,logged:decision(),actual_initial_risk:risk()});});
test('T22','DONE without protection','Do not declare execution complete without reconciling actual SL/TP',()=>{S.responses.push({ok:true,rc:TRADE_RETCODE_DONE,visible:1,unprotected:true});SendEntry(event());OnTimer();return outcome(S.positions.length===0||S.positions[0].sl>0,{positions:S.positions.length,sl:S.positions[0]?.sl,fault:g_fault,entry_executed:accepted()});});
test('T23','PositionModify server rejection','Never log EXECUTED when retcode rejects and SL unchanged',()=>{position();S.modify={ok:true,rc:REJECT,apply:false};let e=event();e.sl=99.5;HandleModify(e);return outcome(decision()!=='EXECUTED',{decision:decision(),retcode:g_trade.ResultRetcode(),sl:S.positions[0].sl});});
test('T24','PositionClose server rejection','Never log EXECUTED while position remains open',()=>{position();S.close={ok:true,rc:REJECT,apply:false};HandleClose(event());return outcome(decision()!=='EXECUTED',{decision:decision(),retcode:g_trade.ResultRetcode(),positions:S.positions.length});});
test('T25','PositionClose partial response','Remaining position is unresolved, not EXECUTED',()=>{position();S.close={ok:true,rc:TRADE_RETCODE_DONE_PARTIAL,apply:false};HandleClose(event());return outcome(decision()!=='EXECUTED',{decision:decision(),positions:S.positions.length});});
test('T26','Acknowledged modify/close','Verify normal successful management',()=>{position();let e=event();e.sl=99.5;HandleModify(e);let modified=S.positions[0].sl===99.5;HandleClose(e);return outcome(modified&&!S.positions.length,{modified,positions:S.positions.length});});
test('T27','Fault with open position at day boundary','Emergency management still closes prior-day position',()=>{position(1,{time:S.now-86400});SetFault('BUS_OVERFLOW_MODULE_1');OnTimer();return outcome(!S.positions.length,{positions:S.positions.length,close_calls:S.close_calls,cert:S.gv.get('QDB1.EXEC.CERT')});});
test('T28','Fault blocks module close','Consume close while entry path faulted',()=>{position();SetFault('BUS_TORN_OR_MISSING_MODULE_1');publish(event(1,S.now*1000,0,3));OnTimer();return outcome(!S.positions.length,{positions:S.positions.length,head:QrosBusHead(1),consumed:g_last_seq[1]});});
test('T29','Temporary terminal trade disabled then restored','Resume safe management after permission restoration',()=>{position();S.trade_allowed=false;HandleClose(event());S.trade_allowed=true;S.positions[0].time-=86400;OnTimer();return outcome(!S.positions.length,{fault:g_fault,positions:S.positions.length,close_calls:S.close_calls});});
test('T30','Restart open position remains module-manageable','Recovery lock blocks entry but does not itself block new close event',()=>{position();let init=OnInit();publish(event(1,S.now*1000,0,3));OnTimer();return outcome(init===0&&g_recovery_lock&&!S.positions.length,{init,recovery_lock:g_recovery_lock,positions:S.positions.length,cert:S.gv.get('QDB1.EXEC.CERT')});});
test('T31','Recovery lock release flat plus recertification','Flat and recertified executor has reachable unlock',()=>{position();OnInit();S.positions=[];S.gv.set('QDB1.EXEC.CERT',1);OnTimer();let sent=SendEntry(event());return outcome(sent,{recovery_lock:g_recovery_lock,sent});});
test('T32','Restart unprotected position same day','Detect and reconcile missing SL before leaving position unmanaged',()=>{position(1,{sl:0});OnInit();OnTimer();return outcome(S.positions.length===0||S.positions[0].sl>0,{recovery_lock:g_recovery_lock,fault:g_fault,positions:S.positions.length,sl:S.positions[0]?.sl});});
test('T33','Restart discards stale entry ring','No stale startup entry replay',()=>{publish(event());OnInit();OnTimer();S.uptime+=300;ProcessPending();return outcome(!S.requests.length,{head:QrosBusHead(1),last_seq:g_last_seq[1],requests:S.requests.length});});
test('T34','Restart discards queued close','Existing position is reconciled despite startup queue discard',()=>{position();publish(event(1,S.now*1000,0,3));OnInit();OnTimer();return outcome(!S.positions.length,{positions:S.positions.length,last_seq:g_last_seq[1]});});
test('T35','Successful history rebuild counts unique position IDs','Partial deal split counts one entry; fourth remains blocked',()=>{S.deals=[{magic:560101,entry:0,pid:1},{magic:560101,entry:0,pid:1},{magic:560217,entry:0,pid:2},{magic:560300,entry:0,pid:3}];RebuildDailyCount();let sent=SendEntry(event());return outcome(g_day_entries===3&&!sent,{count:g_day_entries,sent});});
test('T36','History unavailable after restart','HistorySelect failure blocks entry until authoritative rebuild',()=>{S.history_ok=false;S.deals=[1,2,3].map(pid=>({magic:560101,entry:0,pid}));RebuildDailyCount();let sent=SendEntry(event());return outcome(!sent,{sent,count:g_day_entries,actual_prior_entries:S.deals.length,fault:g_fault});});
test('T37','No overnight before server midnight','Position must be flat before crossing server day',()=>{S.now=Date.UTC(2026,8,7,23,59,59)/1000;position();OnTimer();return outcome(!S.positions.length,{positions_at_235959:S.positions.length,close_calls:S.close_calls});});
test('T38','First timer after midnight','Healthy prior-day position closes on first next-day timer',()=>{position(1,{time:S.now-86400});OnTimer();return outcome(!S.positions.length,{positions:S.positions.length,close_calls:S.close_calls});});
test('T39','Midnight close rejection','No false forced-close success',()=>{position(1,{time:S.now-86400});S.close={ok:true,rc:REJECT,apply:false};OnTimer();return outcome(decision()!=='EXECUTED',{positions:S.positions.length,decision:decision(),retcode:g_trade.ResultRetcode()});});
test('T40','Server day rollover','Count rebuilds for new server day',()=>{g_day_entries=3;S.now+=86400;RefreshDay();return outcome(g_day_entries===0,{count:g_day_entries,day:g_last_day_key});});
test('T41','Bus ordinary duplicate polling','Each sequence consumed once',()=>{publish(event());PollBus();PollBus();return outcome(g_pending.length===1,{pending:g_pending.length,last_seq:g_last_seq[1]});});
test('T42','Torn or missing SEQ','Fault on committed-head missing slot',()=>{S.gv.set(QrosBusKey(1,'HEAD'),1);PollBus();return outcome(g_fault&&!S.requests.length,{fault:g_fault,reason:g_fault_reason});});
test('T43','Overflow 33 records','Detect overflow and block entries',()=>{for(let i=0;i<33;i++)publish(event(1,S.now*1000+i));PollBus();return outcome(g_fault&&!S.requests.length,{fault:g_fault,reason:g_fault_reason,head:QrosBusHead(1)});});
test('T44','Old commit during ring overwrite','Reject payload overwritten before SEQ invalidation',()=>{for(let i=1;i<=32;i++)publish(event(1,i));S.onSet=(k,v)=>{if(k===QrosBusSlotKey(1,1,'SEQ'))throw Error('scheduled_pause_before_commit');};try{publish(event(1,33));}catch(e){if(e.message!=='scheduled_pause_before_commit')throw e;}S.onSet=null;let ev=new QrosBusEvent();let read=QrosBusRead(1,1,ev);return outcome(!read||ev.event_ms===1,{accepted:read,requested_sequence:1,returned_sequence:ev.seq,returned_event_ms:ev.event_ms,head:QrosBusHead(1)});});
test('T45','Crash after slot commit before HEAD','Unannounced record must not be falsely acknowledged as published',()=>{S.onSet=(k,v)=>k===QrosBusKey(1,'HEAD')?false:true;let ok=publish(event());PollBus();return outcome(!ok,{publisher_success:ok,head:QrosBusHead(1),pending:g_pending.length,committed_slot:S.gv.get(QrosBusSlotKey(1,1,'SEQ'))});});
test('T46','Same-module concurrent publishers','Two successful publications occupy distinct sequences',()=>{let injected=false;S.onSet=(k,v)=>{if(!injected&&k===QrosBusSlotKey(1,1,'A')){injected=true;publish(event(1,2));}return true;};let ok=publish(event(1,1));S.onSet=null;return outcome(QrosBusHead(1)===2,{outer_success:ok,both_invoked:injected,head:QrosBusHead(1)});});
test('T47','Different modules independent rings','All three modules have independent heads',()=>{for(let m=1;m<=3;m++)publish(event(m));PollBus();return outcome(g_pending.length===3&&[1,2,3].every(m=>QrosBusHead(m)===1),{pending:g_pending.length,heads:[1,2,3].map(QrosBusHead)});});
test('T48','HEAD regression after persistence rollback','Detect head less than already consumed sequence',()=>{g_last_seq[1]=10;S.gv.set(QrosBusKey(1,'HEAD'),2);PollBus();return outcome(g_fault,{fault:g_fault,last_seq:g_last_seq[1],head:QrosBusHead(1)});});
test('T49','Stale newly sequenced event','Reject old event/publish timestamp on new sequence',()=>{publish(event(1,(S.now-86400)*1000));PollBus();S.uptime+=300;ProcessPending();return outcome(!S.requests.length,{requests:S.requests.length,event_age_days:1});});
test('T50','Ring timestamp precision current epoch','Epoch milliseconds and nearby sequences retain integer precision',()=>{const t=1788782400123;publish(event(1,t));let ev=new QrosBusEvent();let ok=QrosBusRead(1,1,ev);return outcome(ok&&ev.event_ms===t,{read:ok,event_ms:ev.event_ms});});
test('T51','Double sequence upper boundary','Explicitly reject unsafe integer sequence before loss of progress',()=>{S.gv.set(QrosBusKey(1,'HEAD'),2**53);let ok=publish(event());return outcome(!ok,{success:ok,head:QrosBusHead(1),double_2pow53_plus1:2**53+1});});
test('T52','Close after buffered entry in same bus poll','Close/cancellation cannot be lost while entry waits',()=>{publish(event());publish(event(1,S.now*1000+1,0,3));PollBus();S.uptime+=300;ProcessPending();return outcome(!S.positions.length,{positions:S.positions.length,close_calls:S.close_calls,requests:S.requests.length});});
test('T53','Delayed close bound only to magic','Stale close must not close a later position generation',()=>{let e=event(1,S.now*1000-1000,0,3);position();HandleClose(e);return outcome(S.positions.length===1,{positions:S.positions.length,close_calls:S.close_calls});});
test('T54','Heartbeat expiry and late init','Block entry unless all modules READY and fresh',()=>{QrosBusSetState(3,1);let a=!SendEntry(event());QrosBusSetState(3,2);S.gv.set(QrosBusKey(3,'HB'),S.uptime-5001);let b=!SendEntry(event());return outcome(a&&b,{init_blocked:a,expired_blocked:b});});
test('T55','Windows uptime reset with globals','Reject heartbeat from future uptime',()=>{S.gv.set(QrosBusKey(1,'HB'),S.uptime+1);return outcome(!HeartbeatsReady(),{age:QrosBusHeartbeatAgeMs(1),ready:HeartbeatsReady()});});
test('T56','Bootstrap identities READY bars and protection','Ready gates pass baseline and reject each varied gate',()=>{let ready=boot();S.charts[3]='wrong';let identity=boot();S.charts[3]='QROS_DIV3_R3_DEMO_EMITTER_v2_1';position();let pos=boot();return outcome(ready==='RUNTIME_READY'&&identity==='DIV3_ID'&&pos==='QROS_POSITION_PRESENT',{ready,identity,position:pos});});
test('T57','Bootstrap freshness and synchronized bars','Reject stale ticks/unsynchronized series',()=>{let b={},a={},age={},ts={},bar={},sync={};S.ticks.XAUUSD.time-=61;let tick=TickState('XAUUSD',10800,b,a,age,ts);S.series_sync=0;let series=SeriesCurrent('NDX',15,10800,1800,bar,sync);return outcome(!tick&&!series,{tick,age:age.value,series});});
test('T58','Bootstrap executor identity and faults','Executor fault must invalidate runtime readiness',()=>{SetFault('BUS_OVERFLOW_MODULE_1');let r=boot();return outcome(r!=='RUNTIME_READY',{runtime_failure:r,fault:g_fault,exec_heartbeat_age:ExecAge()});});
test('T59','Bootstrap disconnected/trade forbidden','Reject certification when disconnected or trading disabled',()=>{S.connected=false;S.trade_allowed=false;let r=boot();return outcome(r!=='RUNTIME_READY',{runtime_failure:r,connected:false,trade_allowed:false});});
test('T60','CSV unavailable on init','Fail init if ledger cannot be opened',()=>{S.file_open=false;let r=OnInit();return outcome(r===INIT_FAILED,{init:r});});
test('T61','CSV write failure after init','Detect ledger persistence failure',()=>{S.file_write=false;let sent=SendEntry(event());return outcome(!sent||g_fault,{sent,fault:g_fault,rows:S.rows.length});});
test('T62','Ledger append across restart','Keep prior ledger rows on restart',()=>{S.rows.push(['prior_audit_record']);OnInit();return outcome(S.rows.some(r=>r[0]==='prior_audit_record'),{old_row_retained:S.rows.some(r=>r[0]==='prior_audit_record')});});
test('T63','Timer registration failure','Do not initialize authoritative-timer runtime if timer fails',()=>{S.timer_ok=false;let r=OnInit();return outcome(r!==INIT_SUCCEEDED,{init:r,timer_ok:S.timer_ok});});
test('T64','Missing SL discovered during entry risk scan','Block new entry on unknown reserved risk',()=>{position(1,{sl:0});let sent=SendEntry(event(2));return outcome(!sent&&g_fault,{sent,fault:g_fault,reason:g_fault_reason,open_unprotected:S.positions.length});});
test('T65','Unprotected restart blocks new entry','Recovery lock and CERT=0 prevent additional exposure',()=>{position(1,{sl:0});OnInit();let sent=SendEntry(event(2));return outcome(!sent,{sent,lock:g_recovery_lock,cert:S.gv.get('QDB1.EXEC.CERT')});});
test('T66','Duplicate executor instances in one terminal','Second executor init must be fenced even without a position',()=>{let first=OnInit();let second=OnInit();return outcome(first===0&&second!==0,{first,second,exclusive_lease:false});});
test('T67','Profit at moved SL is not initial risk','Retain original reservation independently of current SL',()=>{position(1,{sl:100});let ok=false;let reserved=ReservedRiskUsd({set value(v){ok=v}});return outcome(reserved===50,{calculation_ok:ok,original_initial_risk:50,reported_reserved:reserved});});
test('T68','Finite total reserved risk','Invalid numeric valuation must block new exposure',()=>{position();S.profit_nan_after=3;let sent=SendEntry(event(2));return outcome(!sent,{sent,profit_calls:S.profit_calls});});

test('T69','UTC plus 2 and plus 3 stable offsets','Both contract offsets stabilize after ten observations',()=>{let values=[];for(const off of [7200,10800]){S.offset=off;values.push(OffsetProbe(off,9,true));}return outcome(values.every(x=>x===10),{stable_counts:values});});
test('T70','Out-of-contract server UTC offset','Reject stable UTC, UTC+1 and UTC-5',()=>{let values=[];for(const off of [0,3600,-18000]){S.offset=off;values.push(OffsetProbe(off,9,true));}return outcome(values.every(x=>x<10),{offsets:[0,3600,-18000],stable_counts:values});});
test('T71','Offset transition before certification','DST offset change resets observation count',()=>{let values=[];for(const [prior,next] of [[7200,10800],[10800,7200]]){S.offset=next;values.push(OffsetProbe(prior,10,true));}return outcome(values.every(x=>x===1),{transition_counts:values});});
test('T72','Nonintegral hour offset','Reject offset outside ten-second tolerance',()=>{S.offset=10811;let n=OffsetProbe(10800,9,true);return outcome(n===0,{stable_count:n});});
test('T73','Post-certification DST transition','Revalidate CERT on server offset transition',()=>{S.offset=7200;S.gv.set('QDB1.EXEC.CERT',1);S.offset=10800;OnTimer();return outcome(S.gv.get('QDB1.EXEC.CERT')!==1,{cert:S.gv.get('QDB1.EXEC.CERT'),offset:S.offset});});
test('T74','Server day independent of host timezone','Day key follows synthetic server UTC+2/+3 timestamps',()=>{let out=[];for(const off of [7200,10800]){S.now=Date.UTC(2026,8,7,22,30)/1000+off;out.push(ServerDayKey());}return outcome(out.every(x=>x===20260908),{server_day_keys:out});});
test('T75','Independent terminal namespaces','Two independently certified controllers need account-wide ownership',()=>{SendEntry(event());let first=S.requests.length;reset();let second=SendEntry(event());return outcome(!(first&&second),{first_requests:first,second_sent:second,scope:'Independent snapshots model delayed visibility; no actual terminal instances run'});});
test('T76','Delayed position visibility with DONE','Do not treat DONE as reconciled position',()=>{S.responses.push({ok:true,rc:TRADE_RETCODE_DONE,pending:true});SendEntry(event());let second=SendEntry(event(1,S.now*1000+1));return outcome(!second,{second,orders:S.orders.length,positions:S.positions.length});});
test('T77','Close broker rejection without a fresh module event','Retry or retain unresolved close intent',()=>{position();S.close={ok:false,rc:REJECT,apply:false};HandleClose(event());S.close={ok:true,rc:TRADE_RETCODE_DONE,apply:true};OnTimer();return outcome(!S.positions.length,{positions:S.positions.length,close_calls:S.close_calls});});
test('T78','Restart with an outstanding order and zero positions','Do not unlock entry while an unreconciled order exists',()=>{S.orders.push({symbol:'XAUUSD',volume:0.5,sl:99,magic:560101});OnInit();S.gv.set('QDB1.EXEC.CERT',1);let sent=SendEntry(event());return outcome(!sent,{sent,recovery_lock:g_recovery_lock,orders:S.orders.length});});
test('T79','Missing bus payload key with matching SEQ','Reject incomplete payload even if SEQ and HEAD match',()=>{publish(event());S.gv.delete(QrosBusSlotKey(1,1,'SL'));let e=new QrosBusEvent();let read=QrosBusRead(1,1,e);return outcome(!read,{read,sl:e.sl});});
test('T80','Delayed modify is dropped after broker rejection','Retain desired protection until confirmed or escalated',()=>{position();let e=event();e.sl=99.5;S.modify={ok:false,rc:REJECT,apply:false};HandleModify(e);S.modify={ok:true,rc:TRADE_RETCODE_DONE,apply:true};OnTimer();return outcome(S.positions[0].sl===99.5,{sl:S.positions[0].sl,modify_calls:S.modify_calls});});

test('T81','New-day OnTick before forced close timer','No new entry before resolving prior-day exposure',()=>{position(1,{time:S.now-86400});publish(event(2));PollBus();S.uptime+=300;OnTick();return outcome(!S.requests.length,{requests:S.requests.length,prior_day_still_open:S.positions.some(p=>p.time<S.now-3600),close_calls:S.close_calls});});
test('T82','Runtime freshness after disconnect','Block send with disconnected terminal despite fresh module heartbeats',()=>{S.connected=false;let sent=SendEntry(event());return outcome(!sent,{sent,connected:false,scope:'Stub accepts request; real broker disconnect response remains external BLOCKED'});});
test('T83','Initial risk kernel BUY and SELL controls','Both sides size at or below 50 USD on synthetic linear symbol',()=>{let a=new QrosRiskResult(),b=new QrosRiskResult();let x=QrosRiskSize('XAUUSD',0,100,99,10000,0.5,a);let y=QrosRiskSize('XAUUSD',1,100,101,10000,0.5,b);return outcome(x&&y&&a.actual_risk_usd<=50&&b.actual_risk_usd<=50,{buy_risk:a.actual_risk_usd,sell_risk:b.actual_risk_usd});});
test('T84','Risk target property sweep','Volume stays on step and bounded in representative finite cases',()=>{let checked=0,violations=[];for(const step of [0.01,0.03,0.1,0.25])for(const balance of [100,1000,10000])for(const dist of [0.1,1,7]){S.spec.step=step;S.spec.min=step;let rr=new QrosRiskResult();let ok=QrosRiskSize('XAUUSD',0,100,100-dist,balance,0.5,rr);checked++;if(ok&&(rr.actual_risk_usd>balance*0.005+0.01||Math.abs(rr.volume/step-Math.round(rr.volume/step))>1e-8))violations.push({step,balance,dist});}return outcome(!violations.length,{checked,violations});});
test('T85','Ordinary close then new entry ordering','Confirmed earlier close frees visible asset before mature entry',()=>{position();publish(event(1,S.now*1000,0,3));publish(event(1,S.now*1000+1));PollBus();S.uptime+=300;ProcessPending();return outcome(S.close_calls===1&&S.requests.length===1&&S.positions.length===1,{close_calls:S.close_calls,requests:S.requests.length,positions:S.positions.length});});
test('T86','Double sequence commit changes during read','Reject changed commit in final recheck',()=>{publish(event());let fired=false;S.onGet=k=>{if(!fired&&k===QrosBusSlotKey(1,1,'SL')){fired=true;S.gv.set(QrosBusSlotKey(1,1,'SEQ'),33);}};let e=new QrosBusEvent();let read=QrosBusRead(1,1,e);return outcome(!read,{read,commit:S.gv.get(QrosBusSlotKey(1,1,'SEQ'))});});
test('T87','Continuous faults stop every later timer','Every declared runtime fault reason leaves day-boundary fallback available',()=>{const reasons=['BUS_OVERFLOW_MODULE_1','BUS_TORN_OR_MISSING_MODULE_1','RESERVED_RISK_UNKNOWN','MQL_TRADE_NOT_ALLOWED','TERMINAL_TRADE_NOT_ALLOWED','INVALID_ARM_TOKEN','ACCOUNT_NOT_DEMO','WRONG_SERVER_x','WRONG_CURRENCY_x','FROZEN_RISK_OR_CAP_MISMATCH'];let results=[];for(const reason of reasons){reset();position(1,{time:S.now-86400});SetFault(reason);OnTimer();results.push({reason,remaining:S.positions.length,close_calls:S.close_calls});}return outcome(results.every(x=>x.remaining===0),{results,scope:'Reasons injected after init with authorized demo arm state restored; not a claim that all are naturally reachable during forward'});});
process.stdout.write(JSON.stringify(RESULTS,null,2)+'\n');


