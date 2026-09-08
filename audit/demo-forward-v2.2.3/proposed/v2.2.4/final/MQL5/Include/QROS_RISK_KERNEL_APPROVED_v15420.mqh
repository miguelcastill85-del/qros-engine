//+------------------------------------------------------------------+
//| QROS_RISK_KERNEL_v15400.mqh                                      |
//| Deterministic risk sizing: never rounds volume upward.            |
//+------------------------------------------------------------------+
#ifndef __QROS_RISK_KERNEL_V15400__
#define __QROS_RISK_KERNEL_V15400__

struct QrosRiskResult
{
   bool   ok;
   string reason;
   double balance;
   double target_pct;
   double target_usd;
   double loss_1lot_usd;
   double raw_volume;
   double volume;
   double actual_risk_usd;
   double utilization;
};

int QrosVolumeDigits(const double step)
{
   if(step<=0.0) return 8;
   for(int d=0; d<=8; d++)
   {
      double x=step*MathPow(10.0,d);
      if(MathAbs(x-MathRound(x))<1e-9) return d;
   }
   return 8;
}

double QrosFloorVolume(const string symbol,const double raw)
{
   const double vmin=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN);
   const double vmax=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MAX);
   const double step=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);
   if(vmin<=0.0 || vmax<vmin || step<=0.0 || raw<=0.0) return 0.0;

   double capped=MathMin(raw,vmax);
   double n=MathFloor((capped+1e-12)/step);
   double v=n*step;
   v=NormalizeDouble(v,QrosVolumeDigits(step));
   if(v+1e-12<vmin) return 0.0;
   if(v>vmax) v=vmax;
   return v;
}

bool QrosRiskSize(const string symbol,
                  const ENUM_ORDER_TYPE order_type,
                  const double entry,
                  const double stop,
                  const double account_balance,
                  const double target_risk_pct,
                  QrosRiskResult &out)
{
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

   double p1=0.0;
   ResetLastError();
   if(!OrderCalcProfit(order_type,symbol,1.0,entry,stop,p1))
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

   const double vmin=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN);
   const double step=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);
   const int vd=QrosVolumeDigits(step);

   for(int guard=0; guard<100000; guard++)
   {
      double pv=0.0;
      ResetLastError();
      if(!OrderCalcProfit(order_type,symbol,out.volume,entry,stop,pv))
      {
         out.reason="ORDERCALCPROFIT_VOLUME_FAILED_"+IntegerToString(GetLastError());
         return false;
      }
      out.actual_risk_usd=MathAbs(pv);
      if(out.actual_risk_usd<=out.target_usd+0.01)
         break;

      double next=NormalizeDouble(out.volume-step,vd);
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
#endif
