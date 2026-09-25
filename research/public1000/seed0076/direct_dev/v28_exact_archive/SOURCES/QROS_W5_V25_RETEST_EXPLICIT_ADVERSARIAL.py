#!/usr/bin/env python3
"""Assertion-led causal retest fixtures independent of sampled agreement and PnL."""
import sys,pathlib,hashlib,json
import numpy as np
R=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(R))
from QROS_W5_V25_RETEST_REAL_CAUSAL_ORACLES import primary_one, oracle_one, hash_file
B=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')]);first=np.array([0,4,8,12],np.int64);last=first+3

def case(bid,ask,ids,side,retest,window,cancel,want,label):
 close=bid[last];th=100.0
 vals=[int(f(bid,ask,first,last,close,ids,0,0,cancel,th,side,window,retest)) for f in (primary_one,oracle_one)]
 assert vals==[want,want],(label,vals,want)
 return label

def main():
 checks=[]
 buy=np.array([10100,10020,9950,10050,10010,9980,10020,10030,10020,9950,10010,10040,10100,9900,10020,10050],np.int32)
 sell=np.array([9900,9990,10050,9950,9990,10020,9980,9970,9990,10060,9980,9940,9900,10100,9980,9950],np.int32)
 A=buy+2;S=sell+2;lids=np.array([9,9,9,10],np.int64)
 checks.append(case(buy,A,lids,1,1,1,-1,3,'BUY_valid_touch_then_reclaim_same_bar'))
 checks.append(case(buy,A,lids,1,2,1,-1,4,'BUY_close_reclaim_first_next_bar_source'))
 checks.append(case(sell,S,lids,-1,1,1,-1,3,'SELL_valid_touch_then_reclaim_same_bar'))
 checks.append(case(sell,S,lids,-1,2,1,-1,4,'SELL_close_reclaim_first_next_bar_source'))
 invalidbuy=A.copy();invalidbuy[2]=buy[2]
 checks.append(case(buy,invalidbuy,lids,1,1,1,-1,-1,'BUY_zero_spread_touch_rejected_no_reclaim_window1'))
 checks.append(case(buy,invalidbuy,lids,1,1,3,-1,6,'BUY_invalid_touch_ignored_then_future_valid_touch'))
 checks.append(case(buy,invalidbuy,lids,1,2,1,-1,-1,'BUY_invalid_touch_does_not_confirm_close'))
 checks.append(case(buy,invalidbuy,lids,1,2,3,-1,8,'BUY_close_confirmation_at_second_next_bar'))
 invalidsell=S.copy();invalidsell[2]=sell[2]-1
 checks.append(case(sell,invalidsell,lids,-1,1,1,-1,-1,'SELL_crossed_quote_touch_rejected'))
 checks.append(case(sell,invalidsell,lids,-1,1,3,-1,6,'SELL_valid_later_touch_reclaim'))
 checks.append(case(buy,A,lids,1,1,1,3,-1,'BUY_opposite_cancellation_before_reclaim'))
 checks.append(case(sell,S,lids,-1,1,1,3,-1,'SELL_opposite_cancellation_before_reclaim'))
 replaced=np.array([9,10,10,10],np.int64)
 checks.append(case(buy,A,replaced,1,2,1,-1,-1,'BUY_replacement_at_next_bar_cancels_close'))
 checks.append(case(sell,S,replaced,-1,2,1,-1,-1,'SELL_replacement_at_next_bar_cancels_close'))
 checks.append(case(buy,A,lids,1,2,1,4,-1,'BUY_cancellation_at_next_availability_preempts_close'))
 checks.append(case(sell,S,lids,-1,2,1,4,-1,'SELL_cancellation_at_next_availability_preempts_close'))
 checks.append(case(buy,A,lids,1,1,1,2,-1,'BUY_cancel_before_touch'))
 checks.append(case(buy,A,lids,1,1,1,-1,3,'BUY_no_prior_signal_reaction_only_after_start'))
 checks.append(case(buy,invalidbuy,lids,1,1,3,5,-1,'BUY_cancel_at_first_later_valid_touch'))
 receipt={'schema':'QROS_W5_V25_EXPLICIT_ADVERSARIAL_RETEST_FIXTURES','status':'PASS','tests_passed':len(checks),'named_expected_cases':checks,'requires_original_source_verification':'V220_SHA1_805044c9918a87456a95e150a1c9a1292112cf4c','economics_read':False,'holdout_open':False}
 out=R/'V25_RETEST_ADVERSARIAL_FIXTURE_RECEIPT.json';out.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
 print(json.dumps({'status':receipt['status'],'tests_passed':len(checks)}))
if __name__=='__main__':main()
