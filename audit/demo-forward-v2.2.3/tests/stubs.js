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
