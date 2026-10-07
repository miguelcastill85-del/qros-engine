import {test} from 'node:test';
import assert from 'node:assert/strict';
import {validCostGate} from './check_cost_gate.mjs';
test('paid, stale, future, overlong and wrong-scope confirmation cannot authorize provider writes',()=>{
 const now=Date.now();
 const g={schema:'QROS_G12_COST_AUTHORIZATION_V1',status:'CONFIRMED_BY_USER',classification:'REPORTADO',workers_plan:'FREE',paid_services_allowed:false,scope:'G12_SYNTHETIC_TEST_ONLY_EXISTING_CLOUDFLARE_ACCOUNT',confirmed_at:new Date(now-1000).toISOString(),valid_until:new Date(now+1000).toISOString()};
 assert(validCostGate(g,now));
 for(const patch of [{workers_plan:'PAID'},{paid_services_allowed:true},{status:'PENDING_CURRENT_FREE_PLAN_CONFIRMATION'},{classification:'VERIFICADO'},{scope:'SCIENCE'},{confirmed_at:new Date(now+1).toISOString()},{valid_until:new Date(now).toISOString()},{valid_until:new Date(now+3600001).toISOString()},{confirmed_at:null}]) assert(!validCostGate({...g,...patch},now));
});
