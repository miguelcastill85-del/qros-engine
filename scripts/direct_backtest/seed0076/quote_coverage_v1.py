import sys,collections,datetime,json,numpy as np
from numba import njit
from pathlib import Path
sys.path.insert(0,'/mnt/data/seed0076_direct_dev')
from seed0076_direct_dev_backtest_v1 import RAW,DTYPE,DAY
@njit(cache=True)
def audit(x):
 n=len(x); days=np.empty(1000,np.int64);last=np.empty(1000,np.int64);first=np.empty(1000,np.int64);vcount=np.zeros(1000,np.int64)
 nd=0;prev=-1
 for i in range(n):
  d=x['ts'][i]//DAY
  if d!=prev:
   if nd>=len(days): raise ValueError('DAY_ARRAY_TOO_SHORT')
   days[nd]=d;last[nd]=-1;first[nd]=-1;prev=d;nd+=1
  bid=x['bid'][i];ask=x['ask'][i]
  if bid>0 and ask>bid:
   if first[nd-1]<0:first[nd-1]=x['ts'][i]
   last[nd-1]=x['ts'][i];vcount[nd-1]+=1
 return days[:nd],first[:nd],last[:nd],vcount[:nd]
x=np.memmap(RAW,dtype=DTYPE,mode='r');ds,f,l,c=audit(x)
rows=[];counts=collections.Counter()
for day,a,b,num in zip(ds,f,l,c):
 if num<=0:continue
 w=(int(day)+3)%7
 if w>4:continue
 minute=(int(b)%DAY)//60000
 if minute<1430:
  date=datetime.date(1970,1,1)+datetime.timedelta(days=int(day));counts[int(minute)]+=1
  rows.append({'server_date':str(date),'last_valid_hhmm':f'{minute//60:02d}:{minute%60:02d}','valid_ticks':int(num),'last_tick_time_ms':int(b),'first_tick_time_ms':int(a)})
out={'schema':'QROS_SEED0076_XAU_DEV_DAILY_QUOTE_COVERAGE_1.0','source_dev_sha256':'3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53','days_with_last_valid_quote_before_predeclared_2350':rows,'counts_by_last_minute':dict(sorted(counts.items())),'source_data_audit_only':True,'not_an_economic_filter':True}
Path('/mnt/data/seed0076_direct_dev/quote_coverage_v1.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
print('weekday_sessions_with_last_valid_quote_before_2350',len(rows))
print('first_30',rows[:30])
