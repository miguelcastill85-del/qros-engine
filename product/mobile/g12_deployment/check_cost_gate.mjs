import {readFile,appendFile} from 'node:fs/promises';
const g=JSON.parse(await readFile('product/mobile/g12_deployment/cost_gate.json','utf8'));
const now=Date.now();const start=Date.parse(g.confirmed_at),end=Date.parse(g.valid_until);
const ok=g.schema==='QROS_G12_COST_AUTHORIZATION_V1'&&g.status==='CONFIRMED_BY_USER'&&
 g.classification==='REPORTADO'&&g.workers_plan==='FREE'&&g.paid_services_allowed===false&&
 g.scope==='G12_SYNTHETIC_TEST_ONLY_EXISTING_CLOUDFLARE_ACCOUNT'&&
 Number.isFinite(start)&&Number.isFinite(end)&&start<=now&&now<end&&end-start<=3600000;
if(process.env.GITHUB_OUTPUT)await appendFile(process.env.GITHUB_OUTPUT,'free_confirmed='+ok+'\n');
console.log(JSON.stringify({free_confirmed:ok,classification:ok?'REPORTADO':'NO_DISPONIBLE',paid_services_allowed:false}));
