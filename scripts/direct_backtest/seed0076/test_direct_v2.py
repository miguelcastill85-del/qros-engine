import sys,unittest,numpy as np
sys.path.insert(0,'/mnt/data/seed0076_direct_dev')
import seed0076_direct_dev_backtest_v2 as s

class DirectSemantics(unittest.TestCase):
    def test_tie_and_observability(self):
        h=np.array([1,2,5,2,4,1,3,2],dtype=float);l=-h
        sh,sl,hid,lid=s.fractal_levels(h,l,3,0)
        self.assertTrue(np.isnan(sh[3])) # center p=1 is not max, no future leakage
        self.assertEqual(sh[4],5.0) # 3-bar window [1,2,3] completed at 3, available at bar4
        self.assertEqual(hid[4],2)
        self.assertTrue(np.isnan(sh[3]))
    def test_tie_asymmetric(self):
        h=np.array([0,5,5,3,3,3],dtype=float);l=-h
        x=s.fractal_levels(h,l,3,0)[2];y=s.fractal_levels(h,l,3,1)[2]
        # asymmetric permits same-valued older high; strict rejects all ties
        self.assertTrue(np.any(x!=y))
    def test_one_per_level_consumed_before_ema(self):
        # Same structural high reused across two breakouts; first raw breakout fails trend.
        c=np.array([1,1,5,3,6,4,7,2],dtype=np.int32)
        sh=np.array([np.nan,np.nan,4,4,4,4,4,4]);sl=np.array([np.nan,np.nan,0,0,0,0,0,0]);hid=np.array([-1,-1,1,1,1,1,1,1]);lid=hid.copy()
        efast=np.array([0,0,0,0,0,5,5,5],dtype=float);emid=np.ones(8);eslow=np.zeros(8)
        ix,stop=s.close_break_signals(c,np.arange(8,dtype=np.int64),sh,sl,hid,lid,efast,emid,eslow,1)
        self.assertEqual(len(ix),0)
    def test_live_quote_and_day_cap(self):
        dtype=s.DTYPE
        day=18001
        # Every tick valid, two signals spaced during the same 23:50 preclose session.
        base=day*s.DAY
        ts=np.array([base+s.OPEN+60000*i for i in range(8)]+[base+s.FLAT,base+s.FLAT+1000],dtype=np.int64)
        b=np.array([100,101,102,103,104,105,106,107,108,108],np.int32);a=b+1
        tick=np.zeros(len(ts),dtype=dtype);tick['ts']=ts;tick['bid']=b;tick['ask']=a
        # side BUY: entry at Ask, stop 95, scheduled flat at 108 Bid, R=(108-101)/(101-95).
        tr,re,un=s.simulate(tick,np.array([0,1,2,3],dtype=np.int64),np.array([1]*4,dtype=np.int8),np.array([95]*4,dtype=np.int32),np.array([0]*4,dtype=np.int8))
        self.assertEqual(len(tr),1) # active until flat prohibits overlapping entries
        self.assertAlmostEqual(tr[0,8],7/6)
        self.assertEqual(int(tr[0,9]),2)
        self.assertEqual(int(re[0]),3)
    def test_zero_spread_rejected(self):
        day=18001;tick=np.zeros(3,dtype=s.DTYPE)
        tick['ts']=np.array([day*s.DAY+s.OPEN, day*s.DAY+s.OPEN+100, day*s.DAY+s.FLAT],np.int64)
        tick['bid']=np.array([100,100,102]);tick['ask']=np.array([100,101,103])
        tr,re,un=s.simulate(tick,np.array([0],dtype=np.int64),np.array([1],dtype=np.int8),np.array([80],np.int32),np.array([0],np.int8))
        self.assertEqual(int(tr[0,3]),1)
    def test_stop_first_and_executable_gap(self):
        day=18001;tick=np.zeros(3,dtype=s.DTYPE)
        tick['ts']=np.array([day*s.DAY+s.OPEN,day*s.DAY+s.OPEN+500,day*s.DAY+s.FLAT])
        tick['bid']=np.array([100,88,100]);tick['ask']=np.array([101,89,101])
        tr,re,un=s.simulate(tick,np.array([0],np.int64),np.array([1],np.int8),np.array([95],np.int32),np.array([0],np.int8))
        self.assertEqual(int(tr[0,7]),88)
        self.assertEqual(int(tr[0,9]),1)
    def test_future_mutation(self):
        n=90;h=np.arange(n,dtype=np.float64)%7+100;l=h-3;c=h.copy();first=np.arange(n,dtype=np.int64)
        a=np.arange(n,dtype=float)+1;b=a-1;z=a-2
        sh,sl,hid,lid=s.fractal_levels(h,l,3,0)
        x,y=s.close_break_signals(c,first,sh,sl,hid,lid,a,b,z,1)
        h2=h.copy();l2=l.copy();c2=c.copy();h2[60:]+=10000;l2[60:]-=10000;c2[60:]+=10000
        p,q,i,j=s.fractal_levels(h2,l2,3,0)
        xx,yy=s.close_break_signals(c2,first,p,q,i,j,a,b,z,1)
        self.assertTrue(np.array_equal(x[x<60],xx[xx<60]));self.assertTrue(np.array_equal(y[x<60],yy[xx<60]))

if __name__=='__main__':unittest.main(verbosity=2)
