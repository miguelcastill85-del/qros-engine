#!/usr/bin/env python3
"""Evidence-native lane frontier reconciler: never chase unrelated main.
Input must be assembled by fresh GitHub + Google Drive connector readbacks, then
SHA-pinned outside the snapshot before calling this deterministic offline check.
"""
import argparse,hashlib,json,pathlib,re,sys
H40=re.compile('^[a-f0-9]{40}$');H64=re.compile('^[a-f0-9]{64}$')
class AuthorityIncident(ValueError):pass
def stop(m):raise AuthorityIncident(m)
def reconcile(snapshot_path,snapshot_external_sha256,live_branch_tree_sha):
    raw=pathlib.Path(snapshot_path).read_bytes()
    if not H64.fullmatch(snapshot_external_sha256) or hashlib.sha256(raw).hexdigest()!=snapshot_external_sha256:stop('SNAPSHOT_EXTERNAL_PIN_MISMATCH')
    snap=json.loads(raw)
    if snap.get('schema')!='QROS_CONNECTED_AUTHORITY_SNAPSHOT_V2_1':stop('SNAPSHOT_SCHEMA_FAIL')
    lane=snap.get('lane',{})
    if not lane.get('branch') or lane['branch']=='main' or lane.get('scope')!='SEED0076_DIRECT_DEV':stop('WRONG_LANE_MAIN_SCIENCE_MIX')
    if not H40.fullmatch(lane.get('branch_tree_sha','')) or live_branch_tree_sha!=lane['branch_tree_sha']:stop('STALE_BRANCH_TREE_REQUIRE_FRESH_READBACK')
    rows=snap.get('records',[])
    if not rows or any(r.get('seq')!=i for i,r in enumerate(rows,1)):stop('NONCONTIGUOUS_CHECKPOINT_CHAIN')
    if len(set(r.get('stage') for r in rows))!=len(rows):stop('DUPLICATE_STAGE_IDENTITY')
    base=snap.get('baseline',{})
    if not H40.fullmatch(base.get('git_blob_sha1','')) or not H64.fullmatch(base.get('zip_sha256','')):stop('BASELINE_PIN_MISSING')
    bm=base.get('drive_connector_readback',{})
    if bm.get('id')!=base.get('drive_id') or bm.get('size')!=str(base.get('zip_bytes')) or bm.get('parent_id')!=snap['drive_folder_id']:stop('BASELINE_DRIVE_READBACK_MISMATCH')
    if not isinstance(base.get('cumulative_configs'),int) or not isinstance(base.get('cumulative_masks'),int):stop('BASELINE_COUNTS_MISSING')
    cumulative_config=base['cumulative_configs'];cumulative_masks=base['cumulative_masks']
    for r in rows:
        if r.get('status')!='PASS':stop('UNVERIFIED_STAGE_IN_COMPLETED_CHAIN:'+r.get('stage','?'))
        if not H40.fullmatch(r.get('git_blob_sha1','')) or not r.get('git_path') or not r.get('drive_id'):stop('MISSING_GIT_OR_DRIVE_ID')
        obs=r.get('drive_connector_readback',{})
        if obs.get('id')!=r['drive_id'] or obs.get('size')!=str(r['zip_bytes']) or obs.get('parent_id')!=snap['drive_folder_id']:stop('DRIVE_METADATA_MISMATCH:'+r['stage'])
        if not H64.fullmatch(r.get('zip_sha256','')):stop('MISSING_CARRIER_HASH:'+r['stage'])
        if r.get('new_configs',0)<0 or r.get('new_masks',0)<0:stop('NEGATIVE_COUNTER')
        cumulative_config+=r.get('new_configs',0);cumulative_masks+=r.get('new_masks',0)
        if r.get('cumulative_configs')!=cumulative_config or r.get('cumulative_masks')!=cumulative_masks:stop('COUNTER_CHAIN_BREAK:'+r['stage'])
    last=rows[-1]
    if last.get('next_action')!=snap.get('preregistered_next_action'):stop('NEXT_ACTION_NOT_FROM_LATEST_CHECKPOINT')
    if snap.get('holdout_open') is not False or snap.get('new_old_shard_ga1_authorized') is not False:stop('SCIENTIFIC_FIREWALL')
    return {'schema':'QROS_RECONCILED_FRONTIER_V2_1','lane':lane['branch'],'closed_stages':[base['stage']]+[x['stage'] for x in rows],
            'last_closed_stage':last['stage'],'next_automatic_action':last['next_action'],'next_action_already_completed':False,
            'completed_configurations':cumulative_config,'completed_physical_masks':cumulative_masks,
            'snap_sha256':snapshot_external_sha256,'branch_tree_sha':live_branch_tree_sha,
            'main_stable_science_pointer':'UNTOUCHED_SEPARATE_AUTHORITY','holdout_open':False,'status':'TECHNICALLY_RECONCILED_NO_ECONOMIC_PROMOTION',
            'caveat':'Metadata readback is not a substitute for rehashing downloaded Drive carrier bytes. Snapshot SHA must be externally pinned to be authoritative.'}
def main():
    a=argparse.ArgumentParser();a.add_argument('--snapshot',required=True);a.add_argument('--snapshot-external-sha256',required=True);a.add_argument('--live-branch-tree-sha',required=True);v=a.parse_args()
    try:print(json.dumps(reconcile(v.snapshot,v.snapshot_external_sha256,v.live_branch_tree_sha),sort_keys=True))
    except Exception as e:print(json.dumps({'status':'FAIL_CLOSED','incident':'STALE_AUTHORITY_OR_PROVENANCE','reason':str(e)},sort_keys=True),file=sys.stderr);sys.exit(5)
if __name__=='__main__':main()
