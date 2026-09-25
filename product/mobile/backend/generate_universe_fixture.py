import json
from pathlib import Path
from universe_contract import derive_oracle

base=Path(__file__).resolve().parent
raw={
 'symbol': 'SIM_XAUUSD','sides':['SELL','BUY'],
 'timeframes':['M15','M5'], 'lookback_bars':[15,5,10],
 'confirmation_bars':[2,1],'stop_ratios':['3/2','1/1','2/1'],
 'maximum_holding_bars':[12,8], 'observability':'CLOSED_BAR_ONLY',
 'max_entries_per_day':3,'overnight_allowed':False,
}
fixture={'schema':'QROS_G1_CROSS_LANGUAGE_TEST_V1','raw_input':raw,'oracle':derive_oracle(raw)}
output=base.parent/'flutter_app'/'test'/'fixtures'/'universe_oracle.json'
output.write_text(json.dumps(fixture,sort_keys=True,indent=2,ensure_ascii=False)+'\n')
print(f"TEST_ONLY_FIXTURE {output} raw_births={fixture['oracle']['raw_births']} canonical_sha256={fixture['oracle']['canonical_sha256']} toy_sha256={fixture['oracle']['toy_enumeration_sha256']}")
