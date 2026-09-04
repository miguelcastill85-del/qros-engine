#!/usr/bin/env python3
import qros_g30_f06_transactional_v115 as r
r.build_bars_prep=r.base.build_bars_prep
r.load_arr=r.base.load_arr
r.select_a=r.base.select_a
r.ledger_sha=r.base.ledger_sha
import qros_g30_f06_cluster_v116 as c
if __name__=='__main__': c.main()
