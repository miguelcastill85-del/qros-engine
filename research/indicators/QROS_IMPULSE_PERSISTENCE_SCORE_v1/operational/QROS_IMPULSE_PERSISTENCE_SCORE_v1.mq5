//+------------------------------------------------------------------+
//| QROS_IMPULSE_PERSISTENCE_SCORE_v1.mq5                            |
//| QROS/RISE research instrument - XAUUSD                           |
//| Measures impulse persistence quality. DOES NOT PLACE ORDERS.     |
//+------------------------------------------------------------------+
#property strict
#property indicator_separate_window
#property indicator_buffers 4
#property indicator_plots   4
#property indicator_minimum 0
#property indicator_maximum 100
#property indicator_level1 35
#property indicator_level2 50
#property indicator_level3 65
#property indicator_level4 80
#property indicator_levelcolor clrDimGray
#property indicator_levelstyle STYLE_DOT

#property indicator_label1  "IPS Score"
#property indicator_type1   DRAW_LINE
#property indicator_color1  clrWhite
#property indicator_width1  2

#property indicator_label2  "IPS BUY"
#property indicator_type2   DRAW_ARROW
#property indicator_color2  clrLimeGreen
#property indicator_width2  2

#property indicator_label3  "IPS SELL"
#property indicator_type3   DRAW_ARROW
#property indicator_color3  clrTomato
#property indicator_width3  2

#property indicator_label4  "IPS Direction"
#property indicator_type4   DRAW_NONE

input int    InpReplayDays      = 5;      // Tick replay on initialization
input int    InpResearchScale   = 100;    // Canonical XAU carrier scale
input double InpHighThreshold   = 65.0;   // Frozen research threshold
input bool   InpShowAllEvents   = true;   // Plot score for all eligible events

double ScoreBuffer[];
double BuyBuffer[];
double SellBuffer[];
double DirectionBuffer[];

const long DAY_MS  = 86400000;
const long M15_MS  = 900000;
const long M5_MS   = 300000;
const long PBWIN_MS= 1200000;
const long CONF_MS = 10000;

struct ImpulseState
{
   bool active;
   bool armed;
   bool pending;
   bool buy;
   long impulse_bar;
   long obs_start;
   long expire;
   long extreme_ts;
   long reaccel_ts;
   long confirm_ts;
   long io,ih,il,ic,extreme;
   double body;
   double atr;
   double body_atr;
   double eff;
   double disp_q;
   double eff_q;
   double reaccel_level;
};

struct IndicatorEvent
{
   long entry_msc;
   int  side;       // +1 BUY, -1 SELL
   double score;
   bool eligible;
};

ImpulseState g_state[2]; // 0 SELL, 1 BUY

bool g_have_day=false;
long g_cur_day=0;

bool g_have15=false;
long g_cur15=0;
long g_h15=0,g_l15=0,g_c15=0,g_prev_close=0;
bool g_have_prev_close=false;
int  g_tr_count=0;
double g_tr_sum=0.0,g_atr=0.0;
bool g_atr_ready=false;
int g_spread_hist[65536];
long g_spread_count=0;
int g_spread_p50=0;

bool g_have5=false;
long g_cur5=0;
long g_o5=0,g_h5=0,g_l5=0,g_c5=0;

int g_micro_ring[64];
int g_micro_count=0,g_micro_pos=0;
bool g_have_mid=false;
long g_prev_mid=0;

IndicatorEvent g_events[];
long g_last_msc=-1;
int  g_same_msc_processed=0;

double Clip01(const double x)
{
   if(x<=0.0) return 0.0;
   if(x>=1.0) return 1.0;
   return x;
}

double TriPullback(const double x)
{
   const double l=0.15,p=0.30,r=0.50;
   if(x<=l || x>=r) return 0.0;
   if(x==p) return 1.0;
   if(x<p) return (x-l)/(p-l);
   return (r-x)/(r-p);
}

long Px(const double price)
{
   return (long)MathRound(price*(double)InpResearchScale);
}

void ResetImpulse(ImpulseState &x)
{
   x.active=false; x.armed=false; x.pending=false; x.buy=false;
   x.impulse_bar=0; x.obs_start=0; x.expire=0; x.extreme_ts=0;
   x.reaccel_ts=0; x.confirm_ts=0;
   x.io=0; x.ih=0; x.il=0; x.ic=0; x.extreme=0;
   x.body=0; x.atr=0; x.body_atr=0; x.eff=0;
   x.disp_q=0; x.eff_q=0; x.reaccel_level=0;
}

void ResetAllState()
{
   for(int i=0;i<2;i++) ResetImpulse(g_state[i]);
   g_have_day=false; g_cur_day=0;

   g_have15=false; g_cur15=0; g_h15=0; g_l15=0; g_c15=0;
   g_prev_close=0; g_have_prev_close=false;
   g_tr_count=0; g_tr_sum=0.0; g_atr=0.0; g_atr_ready=false;
   ArrayInitialize(g_spread_hist,0);
   g_spread_count=0; g_spread_p50=0;

   g_have5=false; g_cur5=0; g_o5=0; g_h5=0; g_l5=0; g_c5=0;

   ArrayInitialize(g_micro_ring,0);
   g_micro_count=0; g_micro_pos=0; g_have_mid=false; g_prev_mid=0;

   ArrayResize(g_events,0);
   g_last_msc=-1;
   g_same_msc_processed=0;
}

void SpreadAdd(const int sp)
{
   if(sp<=0) return;
   int k=sp;
   if(k>65535) k=65535;
   g_spread_hist[k]++;
   g_spread_count++;
}

int SpreadMedianPositive()
{
   if(g_spread_count<=0) return 0;
   long k1=(g_spread_count-1)/2;
   long k2=g_spread_count/2;
   long c=0;
   int a=-1,b=-1;
   for(int i=1;i<65536;i++)
   {
      c+=g_spread_hist[i];
      if(a<0 && c>k1) a=i;
      if(c>k2){b=i;break;}
   }
   if(a<0) return 0;
   if(b<0) b=a;
   return (a+b)/2;
}

void FinalizeM15()
{
   if(!g_have15) return;
   long tr=g_h15-g_l15;
   if(g_have_prev_close)
   {
      long a=(long)MathAbs((double)(g_h15-g_prev_close));
      long b=(long)MathAbs((double)(g_l15-g_prev_close));
      if(a>tr) tr=a;
      if(b>tr) tr=b;
   }
   g_tr_count++;
   if(g_tr_count<=14)
   {
      g_tr_sum+=(double)tr;
      if(g_tr_count==14)
      {
         g_atr=g_tr_sum/14.0;
         g_atr_ready=true;
      }
   }
   else
      g_atr=(g_atr*13.0+(double)tr)/14.0;

   g_prev_close=g_c15;
   g_have_prev_close=true;
   g_spread_p50=SpreadMedianPositive();
   ArrayInitialize(g_spread_hist,0);
   g_spread_count=0;
}

void MicroUpdate(const long bid,const long ask)
{
   long mid=bid+ask; // 2*mid; direction is invariant to scale factor
   if(g_have_mid && mid!=g_prev_mid)
   {
      g_micro_ring[g_micro_pos]=(mid>g_prev_mid ? 1 : -1);
      g_micro_pos=(g_micro_pos+1)%64;
      if(g_micro_count<64) g_micro_count++;
   }
   g_prev_mid=mid;
   g_have_mid=true;
}

double MicroQ(const bool buy)
{
   if(g_micro_count<=0) return 0.5;
   int sum=0;
   for(int i=0;i<g_micro_count;i++) sum+=g_micro_ring[i];
   double z=(double)sum/(double)g_micro_count;
   if(!buy) z=-z;
   return Clip01((z+1.0)/2.0);
}

void ArmImpulse(const long next_tick_ts,const long next_day)
{
   if(!g_have5 || !g_atr_ready || g_atr<=0.0) return;
   long bar_day=(g_cur5*M5_MS)/DAY_MS;
   if(bar_day!=next_day) return;

   double body=(double)(g_c5-g_o5);
   double ab=MathAbs(body);
   double range=(double)(g_h5-g_l5);
   if(body==0.0 || range<=0.0) return;

   double ba=ab/g_atr;
   double ef=ab/range;
   if(ba<0.35 || ba>1.20 || ef<0.60) return;

   bool buy=(body>0.0);
   double close_loc=buy ? ((double)(g_h5-g_c5)/range)
                        : ((double)(g_c5-g_l5)/range);
   if(close_loc>0.20) return;

   int s=buy ? 1 : 0;
   if(g_state[s].active || g_state[s].pending) return;

   ImpulseState x;
   ResetImpulse(x);
   x.active=true;
   x.buy=buy;
   x.impulse_bar=g_cur5;
   x.obs_start=next_tick_ts;
   x.expire=next_tick_ts+PBWIN_MS;
   x.extreme_ts=next_tick_ts;
   x.io=g_o5; x.ih=g_h5; x.il=g_l5; x.ic=g_c5;
   x.extreme=g_c5;
   x.body=ab;
   x.atr=g_atr;
   x.body_atr=ba;
   x.eff=ef;
   x.disp_q=Clip01((ba-0.35)/(0.90-0.35));
   x.eff_q=Clip01((ef-0.60)/(0.95-0.60));
   x.reaccel_level=buy ? ((double)g_c5-0.10*ab)
                       : ((double)g_c5+0.10*ab);
   g_state[s]=x;
}

void FinalizeM5(const long next_tick_ts,const long next_day)
{
   if(!g_have5) return;
   ArmImpulse(next_tick_ts,next_day);
}

void AddEvent(const long entry_msc,const int side,const double score,const bool eligible)
{
   int n=ArraySize(g_events);
   ArrayResize(g_events,n+1);
   g_events[n].entry_msc=entry_msc;
   g_events[n].side=side;
   g_events[n].score=score;
   g_events[n].eligible=eligible;
}

void ConfirmState(const int s,const long ts,const long bid,const long ask,const int sp)
{
   ImpulseState x=g_state[s];
   if(!x.pending || ts<x.confirm_ts || sp<=0 || g_spread_p50<=0) return;

   bool buy=x.buy;
   double retr=MathAbs((double)(x.ic-x.extreme))/x.body;
   if(retr<0.15 || retr>0.50)
   {
      g_state[s].pending=false;
      return;
   }

   double pbd=MathAbs((double)(x.ic-x.extreme));
   double pbs=MathMax((double)(x.extreme_ts-x.obs_start)/1000.0,1e-6);
   double rd=MathAbs(x.reaccel_level-(double)x.extreme);
   double rs=MathMax((double)(x.reaccel_ts-x.extreme_ts)/1000.0,1e-6);
   double recovery_q=Clip01(((rd/rs)/(pbd/pbs))/2.0);

   double pullback_q=TriPullback(retr);
   double micro_q=MicroQ(buy);
   double spread_q=Clip01(1.0-(double)sp/(2.0*(double)g_spread_p50));
   double score=20.0*x.disp_q + 15.0*x.eff_q + 20.0*pullback_q
               +20.0*recovery_q + 15.0*micro_q + 10.0*spread_q;

   double entry=(double)(buy ? ask : bid);
   double buf=0.03*x.atr;
   double stop,risk;
   if(buy)
   {
      stop=(double)x.extreme-buf;
      risk=entry-stop;
   }
   else
   {
      stop=(double)x.extreme+buf;
      risk=stop-entry;
   }
   bool eligible=(risk>0.0);
   AddEvent(ts,buy ? 1 : -1,score,eligible);
   g_state[s].pending=false;
}

void UpdateState(const int s,const long ts,const long bid)
{
   ImpulseState x=g_state[s];
   if(!x.active) return;
   if(ts>x.expire)
   {
      g_state[s].active=false;
      return;
   }

   double retr=0.0;
   if(x.buy)
   {
      if(bid<x.extreme)
      {
         x.extreme=bid;
         x.extreme_ts=ts;
      }
      retr=((double)x.ic-(double)x.extreme)/x.body;
   }
   else
   {
      if(bid>x.extreme)
      {
         x.extreme=bid;
         x.extreme_ts=ts;
      }
      retr=((double)x.extreme-(double)x.ic)/x.body;
   }

   if(retr>0.60)
   {
      x.active=false;
      g_state[s]=x;
      return;
   }
   if(retr>=0.15) x.armed=true;
   if(!x.armed)
   {
      g_state[s]=x;
      return;
   }

   bool cross=x.buy ? ((double)bid>=x.reaccel_level)
                    : ((double)bid<=x.reaccel_level);
   if(cross)
   {
      if(retr<=0.50)
      {
         x.active=false;
         x.pending=true;
         x.reaccel_ts=ts;
         x.confirm_ts=ts+CONF_MS;
      }
      else
         x.active=false;
   }
   g_state[s]=x;
}

void ProcessTick(const long ts,const long bid,const long ask)
{
   int sp=(int)(ask-bid);
   if(sp<0) return; // crossed quote ignored exactly as research

   long d=ts/DAY_MS;
   long b15=ts/M15_MS;
   long b5=ts/M5_MS;

   if(!g_have_day)
   {
      g_have_day=true;
      g_cur_day=d;
   }
   else if(d!=g_cur_day)
   {
      ResetImpulse(g_state[0]);
      ResetImpulse(g_state[1]);
      g_cur_day=d;
   }

   if(!g_have15)
   {
      g_have15=true;
      g_cur15=b15;
      g_h15=g_l15=g_c15=bid;
      ArrayInitialize(g_spread_hist,0);
      g_spread_count=0;
      SpreadAdd(sp);
   }
   else if(b15!=g_cur15)
   {
      FinalizeM15();
      g_cur15=b15;
      g_h15=g_l15=g_c15=bid;
      SpreadAdd(sp);
   }
   else
   {
      if(bid>g_h15) g_h15=bid;
      if(bid<g_l15) g_l15=bid;
      g_c15=bid;
      SpreadAdd(sp);
   }

   if(!g_have5)
   {
      g_have5=true;
      g_cur5=b5;
      g_o5=g_h5=g_l5=g_c5=bid;
   }
   else if(b5!=g_cur5)
   {
      FinalizeM5(ts,d);
      g_cur5=b5;
      g_o5=g_h5=g_l5=g_c5=bid;
   }
   else
   {
      if(bid>g_h5) g_h5=bid;
      if(bid<g_l5) g_l5=bid;
      g_c5=bid;
   }

   MicroUpdate(bid,ask);

   ConfirmState(0,ts,bid,ask,sp);
   ConfirmState(1,ts,bid,ask,sp);

   UpdateState(0,ts,bid);
   UpdateState(1,ts,bid);
}

void CursorUpdate(const long ts)
{
   if(ts==g_last_msc)
      g_same_msc_processed++;
   else
   {
      g_last_msc=ts;
      g_same_msc_processed=1;
   }
}

bool ReplayRange(const long from_msc,const long to_msc)
{
   if(to_msc<from_msc) return true;
   MqlTick ticks[];
   int copied=CopyTicksRange(_Symbol,ticks,COPY_TICKS_ALL,(ulong)from_msc,(ulong)to_msc);
   if(copied<0)
   {
      Print("IPS ReplayRange CopyTicksRange error=",GetLastError(),
            " from=",from_msc," to=",to_msc);
      return false;
   }
   for(int i=0;i<copied;i++)
   {
      long ts=(long)ticks[i].time_msc;
      ProcessTick(ts,Px(ticks[i].bid),Px(ticks[i].ask));
      CursorUpdate(ts);
   }
   return true;
}

bool InitialReplay()
{
   ResetAllState();
   datetime now=TimeTradeServer();
   if(now<=0) now=TimeCurrent();
   long end_msc=(long)now*1000;
   long start_msc=end_msc-(long)InpReplayDays*DAY_MS;

   // Six-hour chunks bound memory and make failures explicit.
   const long CHUNK=6*60*60*1000;
   long a=start_msc;
   while(a<=end_msc)
   {
      long b=MathMin(a+CHUNK-1,end_msc);
      if(!ReplayRange(a,b)) return false;
      a=b+1;
   }
   return true;
}

void ProcessIncrementalTicks()
{
   datetime now=TimeTradeServer();
   if(now<=0) now=TimeCurrent();
   long to_msc=(long)now*1000+999;
   if(g_last_msc<0)
   {
      InitialReplay();
      return;
   }

   MqlTick ticks[];
   int copied=CopyTicksRange(_Symbol,ticks,COPY_TICKS_ALL,(ulong)g_last_msc,(ulong)to_msc);
   if(copied<=0) return;

   int skip_same=0;
   for(int i=0;i<copied;i++)
   {
      long ts=(long)ticks[i].time_msc;
      if(ts==g_last_msc && skip_same<g_same_msc_processed)
      {
         skip_same++;
         continue;
      }
      ProcessTick(ts,Px(ticks[i].bid),Px(ticks[i].ask));
      CursorUpdate(ts);
   }
}

string ZoneName(const double s)
{
   if(s<35.0) return "LOW";
   if(s<50.0) return "WATCH";
   if(s<65.0) return "MEDIUM";
   if(s<80.0) return "HIGH";
   return "VERY_HIGH";
}

void RenderEvents(const int rates_total)
{
   ArrayInitialize(ScoreBuffer,EMPTY_VALUE);
   ArrayInitialize(BuyBuffer,EMPTY_VALUE);
   ArrayInitialize(SellBuffer,EMPTY_VALUE);
   ArrayInitialize(DirectionBuffer,EMPTY_VALUE);

   int n=ArraySize(g_events);
   for(int i=0;i<n;i++)
   {
      if(!g_events[i].eligible) continue;
      datetime t=(datetime)(g_events[i].entry_msc/1000);
      int shift=iBarShift(_Symbol,_Period,t,false);
      if(shift<0 || shift>=rates_total) continue;

      double s=g_events[i].score;
      if(InpShowAllEvents || s>=InpHighThreshold)
      {
         if(ScoreBuffer[shift]==EMPTY_VALUE || s>ScoreBuffer[shift])
            ScoreBuffer[shift]=s;
      }

      if(s>=InpHighThreshold)
      {
         if(g_events[i].side>0)
            BuyBuffer[shift]=s;
         else
            SellBuffer[shift]=s;
         DirectionBuffer[shift]=(double)g_events[i].side;
      }
   }
}

int OnInit()
{
   SetIndexBuffer(0,ScoreBuffer,INDICATOR_DATA);
   SetIndexBuffer(1,BuyBuffer,INDICATOR_DATA);
   SetIndexBuffer(2,SellBuffer,INDICATOR_DATA);
   SetIndexBuffer(3,DirectionBuffer,INDICATOR_DATA);

   ArraySetAsSeries(ScoreBuffer,true);
   ArraySetAsSeries(BuyBuffer,true);
   ArraySetAsSeries(SellBuffer,true);
   ArraySetAsSeries(DirectionBuffer,true);

   PlotIndexSetInteger(1,PLOT_ARROW,233);
   PlotIndexSetInteger(2,PLOT_ARROW,234);
   PlotIndexSetDouble(0,PLOT_EMPTY_VALUE,EMPTY_VALUE);
   PlotIndexSetDouble(1,PLOT_EMPTY_VALUE,EMPTY_VALUE);
   PlotIndexSetDouble(2,PLOT_EMPTY_VALUE,EMPTY_VALUE);

   IndicatorSetString(INDICATOR_SHORTNAME,"QROS IPS v1 [research threshold 65]");
   IndicatorSetInteger(INDICATOR_DIGITS,2);

   if(StringFind(_Symbol,"XAU")<0)
      Print("QROS IPS v1 warning: research authority is XAUUSD; current symbol=",_Symbol);

   bool ok=InitialReplay();
   if(!ok)
      Print("QROS IPS v1 initial replay incomplete. Indicator will continue incrementally.");
   return INIT_SUCCEEDED;
}

int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
{
   ProcessIncrementalTicks();
   RenderEvents(rates_total);

   int n=ArraySize(g_events);
   if(n>0)
   {
      IndicatorEvent e=g_events[n-1];
      string side=(e.side>0 ? "BUY" : "SELL");
      Comment("QROS IPS v1 | last=",DoubleToString(e.score,2),
              " | ",ZoneName(e.score)," | ",side,
              " | eligible=", (e.eligible ? "YES" : "NO"),
              " | threshold=",DoubleToString(InpHighThreshold,1));
   }
   return rates_total;
}
//+------------------------------------------------------------------+
