import {DurableObject} from 'cloudflare:workers';
import {handle} from './core.mjs';
export class ReplayGate extends DurableObject {
  async consume(hash, grant, now) {
    // One named object for this bounded canary, all isolates share atomic storage.
    return this.ctx.storage.transaction(async tx=>{
      const seen=await tx.get('seen')||{};
      for(const [k,exp] of Object.entries(seen))if(exp<=now)delete seen[k];
      if(seen[hash])return 409;
      const bucket=Math.floor(now/60);
      const limit=await tx.get('rate')||{bucket,n:0};
      if(limit.bucket!==bucket){limit.bucket=bucket;limit.n=0;}
      if(limit.n>=10||Object.keys(seen).length>=100)return 429;
      seen[hash]=grant.exp;limit.n++;
      await tx.put({seen,rate:limit});
      return 200;
    });
  }
}
export default {async fetch(req,env){
  return handle(req,env,async(hash,g,now)=>{
    const gate=env.REPLAY_GATE.get(env.REPLAY_GATE.idFromName('g9-single-canary-v1'));
    return gate.consume(hash,g,now);
  });
}};
