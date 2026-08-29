#pragma once
#include <string_view>
namespace qros::pipeline {
inline constexpr std::string_view mt5_runtime=R"MQ5(
// Tester-only strategy implementation. Never enable this EA on a live chart.
// Runtime compilation, broker symbol/volume binding and trade parity are external gates.
input string ExpectedBrokerSymbol="";
input double LotsForOneContract=0.0;
input string ClockContractSha256="";
input string SessionFile="QrosSessions.csv";
input long FirstSequence=1;
input ulong Magic=81062026;

struct FeatureState {
   long value,version,input_version,count;
   bool valid,initialized,bar_initialized;
   long previous_a,previous_b,bucket,day,open,high,low,close,last_seq;
   long history[];
};
struct Session {long day,open_seq,close_seq,open_ns,close_ns,offset;};
FeatureState F[];
Session Sessions[];
CTrade Trader;
long Sequence=0,Day=0,Entries=0,LastEntryBar=-1,SignalVersion=0,PendingSeq=0,PendingAge=0,Best=0;
bool Pending=false,PreviousSignal=false,Failed=false;
int SessionIndex=0,TicksFile=INVALID_HANDLE,DealsFile=INVALID_HANDLE;
double Scale=1.0;

void AbortRun(string message) {Failed=true;Print("QROS_REJECT: ",message);ExpertRemove();}
bool TradeSucceeded() {
   uint code=Trader.ResultRetcode();
   if(code!=TRADE_RETCODE_DONE) {AbortRun("trade retcode "+IntegerToString((long)code));return false;}
   return true;
}
long PriceUnits(double price) {
   double scaled=price*Scale;long u=(long)MathRound(scaled);
   if(MathAbs(scaled-(double)u)>0.00001 || u<=0 || u>1000000000000) AbortRun("price scale/domain");
   return u;
}
bool ReadSessions() {
   int file=FileOpen(SessionFile,FILE_READ|FILE_CSV|FILE_ANSI,',',CP_UTF8);
   if(file==INVALID_HANDLE)return false;
   string header[6]={"session_day","open_seq","close_seq","open_ts_ns","close_ts_ns","utc_offset_seconds"};
   for(int i=0;i<6;i++)if(FileReadString(file)!=header[i]){FileClose(file);return false;}
   while(!FileIsEnding(file)) {
      string first=FileReadString(file);if(first==""&&FileIsEnding(file))break;
      Session s;s.day=StringToInteger(first);s.open_seq=StringToInteger(FileReadString(file));s.close_seq=StringToInteger(FileReadString(file));
      s.open_ns=StringToInteger(FileReadString(file));s.close_ns=StringToInteger(FileReadString(file));s.offset=StringToInteger(FileReadString(file));
      int n=ArraySize(Sessions);if(s.open_seq<=0||s.close_seq<s.open_seq||s.open_ns<=0||s.close_ns<s.open_ns){FileClose(file);return false;}
      if(n>0&&(s.day<=Sessions[n-1].day||s.open_seq!=Sessions[n-1].close_seq+1)){FileClose(file);return false;}
      if(ArrayResize(Sessions,n+1)!=n+1){FileClose(file);return false;}Sessions[n]=s;
   }
   FileClose(file);return ArraySize(Sessions)>0;
}
void UpdateFeatures(long bid,long ask,long ts_ns,long day) {
   for(int i=0;i<NodeCount;i++) {
      int op=Op[i];long value=0,version=Sequence;bool valid=true;
      if(op<=2)value=(op==0?bid:(op==1?ask:ask-bid));
      else if(op==3){value=Param[i];version=1;}
      else if(op>=4&&op<=7) {
         long bucket=ts_ns/(Param[i]*1000000);
         if(F[i].bar_initialized&&(F[i].bucket!=bucket||F[i].day!=day)) {
            F[i].value=(op==4?F[i].open:(op==5?F[i].high:(op==6?F[i].low:F[i].close)));
            F[i].valid=true;F[i].version=F[i].last_seq;F[i].bar_initialized=false;
         }
         if(!F[i].bar_initialized){F[i].bucket=bucket;F[i].day=day;F[i].open=bid;F[i].high=bid;F[i].low=bid;F[i].bar_initialized=true;}
         F[i].high=MathMax(F[i].high,bid);F[i].low=MathMin(F[i].low,bid);F[i].close=bid;F[i].last_seq=Sequence;continue;
      } else {
         int left=Left[i],right=Right[i];valid=F[left].valid&&(right<0||F[right].valid);
         version=F[left].version;if(right>=0)version=MathMax(version,F[right].version);
         if(!valid){F[i].valid=false;F[i].version=version;continue;}
         if(version==F[i].input_version)continue;F[i].input_version=version;
         long a=F[left].value,b=(right>=0?F[right].value:0);
         if(op==8)value=a+b;else if(op==9)value=a-b;else if(op==10)value=MathMin(a,b);else if(op==11)value=MathMax(a,b);
         else if(op==12)value=(a>b);else if(op==13)value=(a>=b);else if(op==14)value=(a<b);else if(op==15)value=(a<=b);else if(op==16)value=(a==b);
         else if(op==17)value=(a!=0&&b!=0);else if(op==18)value=(a!=0||b!=0);else if(op==19)value=(a==0);
         else if(op>=20&&op<=23) {
            int capacity=(int)Param[i]+1;int pos=(int)(F[i].count%capacity);F[i].history[pos]=a;F[i].count++;
            if(op==20){valid=F[i].count>Param[i];if(valid)value=F[i].history[(int)((F[i].count-1-Param[i])%capacity)];}
            else if(op==21){value=F[i].initialized?F[i].value+(2*(a-F[i].value))/(Param[i]+1):a;F[i].initialized=true;valid=F[i].count>=Param[i];}
            else {valid=F[i].count>=Param[i];value=a;long n=MathMin(F[i].count,Param[i]);for(long k=0;k<n;k++){long v=F[i].history[(int)((F[i].count-1-k)%capacity)];value=(op==22?MathMax(value,v):MathMin(value,v));}}
         } else if(op==24||op==25){valid=F[i].initialized;value=(op==24?(F[i].previous_a<=F[i].previous_b&&a>b):(F[i].previous_a>=F[i].previous_b&&a<b));F[i].previous_a=a;F[i].previous_b=b;F[i].initialized=true;}
         else {AbortRun("unsupported opcode");return;}
      }
      if(value < -1000000000000 || value>1000000000000){AbortRun("feature numeric domain");return;}
      F[i].value=value;F[i].valid=valid;F[i].version=version;
   }
}
int OnInit() {
   if(!MQLInfoInteger(MQL_TESTER)||MQLInfoInteger(MQL_OPTIMIZATION))return INIT_FAILED;
   if(ExpectedBrokerSymbol==""||_Symbol!=ExpectedBrokerSymbol||LotsForOneContract<=0||StringLen(ClockContractSha256)!=64||FirstSequence<1)return INIT_PARAMETERS_INCORRECT;
   if(PositionsTotal()!=0||OrdersTotal()!=0)return INIT_FAILED;
   double min_volume=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN),step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP),max_volume=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   if(step<=0||LotsForOneContract<min_volume||LotsForOneContract>max_volume||MathAbs(LotsForOneContract/step-MathRound(LotsForOneContract/step))>0.000001)return INIT_PARAMETERS_INCORRECT;
   if(!ReadSessions()||Sessions[0].open_seq!=FirstSequence)return INIT_FAILED;
   Scale=MathPow(10.0,PriceDecimals);Sequence=FirstSequence-1;
   ArrayResize(F,NodeCount);
   for(int i=0;i<NodeCount;i++)if(Op[i]>=20&&Op[i]<=23)if(ArrayResize(F[i].history,(int)Param[i]+1)!=(int)Param[i]+1)return INIT_FAILED;
   Trader.SetExpertMagicNumber(Magic);Trader.SetAsyncMode(false);Trader.SetTypeFillingBySymbol(_Symbol);
   TicksFile=FileOpen("QrosObservedTicks.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',',CP_UTF8);
   DealsFile=FileOpen("QrosObservedDeals.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',',CP_UTF8);
   if(TicksFile==INVALID_HANDLE||DealsFile==INVALID_HANDLE)return INIT_FAILED;
   FileWrite(TicksFile,"seq","ts_ns","session_day","bid_u","ask_u");
   FileWrite(DealsFile,"candidate_id","birth","symbol","deal_id","position_id","entry","type","time_msc","price_u","volume","profit","commission","swap","reason");
   Print("QROS candidate=",CandidateId," spec=",FrozenSpec," clock=",ClockContractSha256);
   return INIT_SUCCEEDED;
}
void OnTick() {
   if(Failed)return;MqlTick tick;if(!SymbolInfoTick(_Symbol,tick)){AbortRun("no quote");return;}
   Sequence++;while(SessionIndex<ArraySize(Sessions)&&Sequence>Sessions[SessionIndex].close_seq)SessionIndex++;
   if(SessionIndex>=ArraySize(Sessions)){AbortRun("extra ticks outside session authority");return;}
   Session session=Sessions[SessionIndex];long ts=tick.time_msc*1000000,bid=PriceUnits(tick.bid),ask=PriceUnits(tick.ask);
   if(Failed)return;
   if(ask<bid||ts<session.open_ns||ts>session.close_ns||(Sequence==session.open_seq&&ts!=session.open_ns)||(Sequence==session.close_seq&&ts!=session.close_ns)){AbortRun("tick/session authority mismatch");return;}
   FileWrite(TicksFile,Sequence,ts,session.day,bid,ask);
   if(Day!=session.day){if(PositionSelect(_Symbol)){AbortRun("overnight position");return;}Day=session.day;Entries=0;LastEntryBar=-1;Pending=false;}
   UpdateFeatures(bid,ask,ts,Day);if(Failed)return;
   long bar=ts/(BarMs*1000000);
   bool has_position=PositionSelect(_Symbol);
   if(Sequence==session.close_seq) {
      if(has_position){if(ask<=bid){AbortRun("no executable session close");return;}if(!Trader.PositionClose(_Symbol)||!TradeSucceeded()){AbortRun("close rejected");return;}}
      Pending=false;SignalVersion=F[SignalNode].version;PreviousSignal=F[SignalNode].valid&&F[SignalNode].value!=0;return;
   }
   if(has_position&&ask>bid) {
      long entry=PriceUnits(PositionGetDouble(POSITION_PRICE_OPEN));long price=(IsBuy?bid:ask);
      Best=(IsBuy?MathMax(Best,price):MathMin(Best,price));long favorable=(IsBuy?price-entry:entry-price);
      long old_stop=PriceUnits(PositionGetDouble(POSITION_SL)),new_stop=old_stop;
      if(BePpm>0&&favorable>0&&favorable*1000000>=TargetU*BePpm){long level=(IsBuy?entry+BeOffsetU:entry-BeOffsetU);new_stop=(IsBuy?MathMax(new_stop,level):MathMin(new_stop,level));}
      if(TrailingU>0){long level=(IsBuy?Best-TrailingU:Best+TrailingU);new_stop=(IsBuy?MathMax(new_stop,level):MathMin(new_stop,level));}
      if(new_stop!=old_stop){if(!Trader.PositionModify(_Symbol,(double)new_stop/Scale,PositionGetDouble(POSITION_TP))||!TradeSucceeded()){AbortRun("management rejected");return;}}
   }
   if(Pending&&Sequence>PendingSeq) {
      PendingAge++;if(PendingAge>ExpiryRecords)Pending=false;
      else if(!has_position&&ask>bid&&Entries<DailyLimit&&bar!=LastEntryBar) {
         long quote=(IsBuy?ask:bid),stop=(IsBuy?quote-StopU:quote+StopU),target=(IsBuy?quote+TargetU:quote-TargetU);
         bool sent=IsBuy?Trader.Buy(LotsForOneContract,_Symbol,0.0,(double)stop/Scale,(double)target/Scale,StringSubstr(CandidateId,0,24)):
                          Trader.Sell(LotsForOneContract,_Symbol,0.0,(double)stop/Scale,(double)target/Scale,StringSubstr(CandidateId,0,24));
         if(!sent||!TradeSucceeded()||Trader.ResultDeal()==0){AbortRun("entry rejected");return;}
         if(!PositionSelect(_Symbol)){AbortRun("missing filled position");return;}
         long actual=PriceUnits(PositionGetDouble(POSITION_PRICE_OPEN));
         if(actual!=quote){AbortRun("fill differs from zero-slippage contract");return;}
         Best=actual;Entries++;LastEntryBar=bar;Pending=false;has_position=true;
      }
   }
   if(SignalVersion!=F[SignalNode].version) {
      bool truth=F[SignalNode].valid&&F[SignalNode].value!=0;
      if(truth&&(EachUpdate||!PreviousSignal)&&!has_position&&!Pending&&Entries<DailyLimit&&bar!=LastEntryBar){Pending=true;PendingSeq=Sequence;PendingAge=0;}
      PreviousSignal=truth;SignalVersion=F[SignalNode].version;
   }
}
void OnTradeTransaction(const MqlTradeTransaction& transaction,const MqlTradeRequest& request,const MqlTradeResult& result) {
   if(transaction.type!=TRADE_TRANSACTION_DEAL_ADD||!HistoryDealSelect(transaction.deal))return;
   if((ulong)HistoryDealGetInteger(transaction.deal,DEAL_MAGIC)!=Magic)return;
   ulong deal=transaction.deal;long reason=HistoryDealGetInteger(deal,DEAL_REASON);
   string exit_reason=(reason==DEAL_REASON_SL?"SL":(reason==DEAL_REASON_TP?"TP":"SESSION_CLOSE"));
   FileWrite(DealsFile,CandidateId,Birth,InternalSymbol,deal,HistoryDealGetInteger(deal,DEAL_POSITION_ID),HistoryDealGetInteger(deal,DEAL_ENTRY),
      HistoryDealGetInteger(deal,DEAL_TYPE),HistoryDealGetInteger(deal,DEAL_TIME_MSC),PriceUnits(HistoryDealGetDouble(deal,DEAL_PRICE)),
      HistoryDealGetDouble(deal,DEAL_VOLUME),HistoryDealGetDouble(deal,DEAL_PROFIT),HistoryDealGetDouble(deal,DEAL_COMMISSION),HistoryDealGetDouble(deal,DEAL_SWAP),exit_reason);
   FileFlush(DealsFile);
}
void OnDeinit(const int reason) {
   if(ArraySize(Sessions)==0)Print("QROS_VALIDATION_NOT_INITIALIZED");
   else if(Sequence!=Sessions[ArraySize(Sessions)-1].close_seq||PositionSelect(_Symbol))Print("QROS_VALIDATION_INCOMPLETE");
   if(TicksFile!=INVALID_HANDLE){FileFlush(TicksFile);FileClose(TicksFile);}if(DealsFile!=INVALID_HANDLE){FileFlush(DealsFile);FileClose(DealsFile);}
   Print("QROS_END reason=",reason," failed=",Failed," observed_last_seq=",Sequence);
}
)MQ5";
} // namespace qros::pipeline
