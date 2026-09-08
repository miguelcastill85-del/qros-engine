#!/usr/bin/env python3
"""Validate deliverable scope and immutable Git bytes before staging."""
from pathlib import Path
import hashlib,json,subprocess
BASE=Path(__file__).resolve().parents[1]
ROOT=BASE.parents[1]
REL=BASE.relative_to(ROOT).as_posix()
HEAD='3c92d2ca50fb08d3b51d19f6f042f328797460e4'
BRANCH='audit/demo-forward-v2.2.3-frozen-20260907'
def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT)
def require(value,message):
 if not value: raise RuntimeError(message)
def sha(b): return hashlib.sha256(b).hexdigest()
require(git('branch','--show-current').decode().strip()==BRANCH,'wrong branch')
require(git('rev-parse','HEAD').decode().strip()==HEAD,'wrong precommit HEAD')
original=git('ls-tree','-r','--name-only',HEAD,'--',REL).decode().splitlines()
checks=[]
for name in original:
 current=(ROOT/name).read_bytes(); prior=git('show',HEAD+':'+name)
 require(current==prior,'changed original file '+name)
 checks.append(dict(path=name,bytes=len(current),sha256=sha(current),git_baseline_bytes_equal=True))
require(len(checks)==9,'unexpected original audit inventory')
changed=git('diff','--name-only','--diff-filter=MDRTUXB',HEAD).decode().splitlines()
require(not changed,'preexisting tracked paths modified: '+repr(changed))
source_receipt=json.loads((BASE/'FROZEN_SOURCE_RECEIPT.json').read_text())
for f in source_receipt['files']:
 if not f['mirrored_exact_on_branch']: continue
 b=(BASE/'frozen'/f['path']).read_bytes()
 blob=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
 require(len(b)==f['bytes'] and sha(b)==f['sha256'] and blob==f['git_blob_sha1'],'receipt mismatch')
m=json.loads((BASE/'CODEX_AUDIT_TEST_MATRIX.json').read_text())
d=json.loads((BASE/'CODEX_AUDIT_DECISION.json').read_text())
f=json.loads((BASE/'CODEX_AUDIT_FINDINGS.json').read_text())
require(d['decision']=='CRITICAL_REPLACEMENT_REQUIRED','decision mismatch')
require(len(m['tests'])==103 and m['summary']=={'PASS':38,'FAIL':49,'BLOCKED':16},'matrix counts')
ids={t['id'] for t in m['tests']}
require(len(ids)==103,'duplicate test ids')
require(len(m['required_D_coverage'])==20,'mandatory coverage')
for cov in m['required_D_coverage']: require(set(cov['test_ids'])<=ids,'unknown coverage ids')
for t in m['tests']:
 require(t['classification'] in ['STATIC_PROVEN','TEST_PROVEN','INFERRED','BLOCKED'],'unclassified test')
 if t['status']=='BLOCKED': require(t['observed_result'] is None,'fabricated blocked observation')
for row in f['findings']:
 require(row['classification'] in ['STATIC_PROVEN','TEST_PROVEN','INFERRED','BLOCKED'],'unclassified finding')
 for loc in row['locations']:
  lines=(BASE/loc['file']).read_text().splitlines()
  require(0<loc['line']<=len(lines),'bad source line')
 require(set(row['test_ids'])<=ids,'unknown finding tests')
require(not m['proposal']['regressed_expectations'],'proposal regression')
require(m['proposal']['summary']=={'PASS':49,'FAIL':38,'BLOCKED':0},'proposal count')
# Generated evidence stays audit-local. Every JSON must parse.
json_count=0
for p in BASE.rglob('*.json'):
 json.loads(p.read_text(encoding='utf-8-sig'));json_count+=1
rows=[]
for line in git('status','--porcelain','--untracked-files=all').decode().splitlines():
 path=line[3:].strip('"')
 require(path.startswith(REL+'/'),'out-of-scope path '+path)
 require(not path.startswith(REL+'/frozen/'),'frozen mutation')
 rows.append(path)
integrity=dict(schema='QROS_V223_AUDIT_INTEGRITY_1',classification='TEST_PROVEN',audited_head=HEAD,branch=BRANCH,original_audit_files=checks,original_file_count=9,frozen_file_count=6,exact_source_receipt_matches=4,git_diff_tracked_paths=changed,new_artifact_paths=rows,all_original_audit_bytes_unchanged=True,all_frozen_v223_bytes_unchanged=True,all_existing_repository_tracked_paths_unchanged=True,parsed_json_count=json_count,matrix_consistent=True,proposal_pass_to_fail_regressions=0,scope='PRECOMMIT_READ_ONLY_GIT_AND_ARTIFACT_VERIFICATION')
(BASE/'evidence/INTEGRITY_FINAL.json').write_text(json.dumps(integrity,indent=2)+'\n')
manifest=[]
for p in sorted(BASE.rglob('*')):
 if not p.is_file() or p.name=='ARTIFACT_MANIFEST.json' or '__pycache__' in p.parts: continue
 rel=p.relative_to(ROOT).as_posix()
 if rel in original: continue
 data=p.read_bytes();manifest.append(dict(path=p.relative_to(BASE).as_posix(),bytes=len(data),sha256=sha(data)))
(BASE/'evidence/ARTIFACT_MANIFEST.json').write_text(json.dumps(dict(schema='QROS_V223_AUDIT_ARTIFACT_MANIFEST_1',classification='TEST_PROVEN',self_excluded=True,original_sources_bound_by='INTEGRITY_FINAL.json',files=manifest),indent=2)+'\n')
print(json.dumps(dict(status='AUDIT_DELIVERY_VALIDATED',original_files_unchanged=len(checks),frozen_unchanged=6,manifest_entries=len(manifest),test_summary=m['summary'],proposal_summary=m['proposal']['summary'])))
