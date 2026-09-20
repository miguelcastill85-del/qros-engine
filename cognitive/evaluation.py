"""Offline benchmark bookkeeping and conditional statistics, never model attestation."""
import math
import os
import stat
import sqlite3
from pathlib import Path
from .runtime import ContractError, canonical, parse_json, require, require_hash, sha256

GATES = ('ONTOLOGY_FROZEN','RISE_FIXED_POINT','UNIT_PASS','INTEGRATION_PASS','REGRESSION_PASS',
         'FAULT_INJECTION_PASS','CONTINUITY_PASS','BENCHMARK_DEVELOPMENT_PASS','BENCHMARK_VALIDATION_PASS',
         'VERSION_FROZEN','SEALED_EVALUATION','SHADOW_PASS','CANARY_PASS')
DIMENSIONS = ('CORRECTNESS','CRITICAL_ERROR_RATE','TASK_COMPLETION','STATE_RECOVERY','REPRODUCIBILITY',
              'PROGRAMMING','QUANT_REASONING','CAUSAL_REASONING','TOOL_USE','CONTINUITY','AUTOCORRECTION','EFFICIENCY')


class BenchmarkLedger:
    """Independent benchmark registry: a child inherits all ancestor exposures."""
    def __init__(self,path: Path):
        # POSIX host-owned directory is the trust boundary. Reject linked parents;
        # retain its descriptor so renaming a parent cannot redirect SQLite.
        path=Path(path).absolute()
        require('..' not in path.parts,'BENCHMARK_LEDGER_PATH')
        self._dir_fd=None;self.db=None
        try:
            fd=os.open(path.anchor,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            self._dir_fd=fd
            for part in path.parts[1:-1]:
                new=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
                os.close(fd);fd=new;self._dir_fd=fd
            info=os.fstat(fd)
            require(info.st_uid==os.geteuid() and not info.st_mode & 0o022,'BENCHMARK_LEDGER_UNTRUSTED_DIRECTORY')
            for suffix in ('','-journal','-wal','-shm'):
                try:info=os.stat(path.name+suffix,dir_fd=fd,follow_symlinks=False)
                except FileNotFoundError:continue
                require(not stat.S_ISLNK(info.st_mode),'BENCHMARK_LEDGER_SYMLINK')
                require(stat.S_ISREG(info.st_mode) and info.st_uid==os.geteuid() and info.st_nlink==1 and not info.st_mode & 0o022,'BENCHMARK_LEDGER_UNSAFE_FILE')
            require(Path('/proc/self/fd').is_dir(),'BENCHMARK_LEDGER_HOST_UNSUPPORTED')
            self.db=sqlite3.connect(f'/proc/self/fd/{fd}/{path.name}',timeout=2,isolation_level=None)
            self.db.execute('PRAGMA trusted_schema=OFF')
            self.db.execute('PRAGMA foreign_keys=ON')
            self.db.execute('PRAGMA synchronous=FULL')
            self.db.execute('CREATE TABLE IF NOT EXISTS family(id TEXT PRIMARY KEY,parent TEXT REFERENCES family(id))')
            self.db.execute('CREATE TABLE IF NOT EXISTS exposure(family TEXT REFERENCES family(id),case_hash TEXT,receipt_hash TEXT,PRIMARY KEY(family,case_hash))')
        except OSError as error:
            self.close();raise ContractError('BENCHMARK_LEDGER_SYMLINK','unsafe or unavailable path') from error
        except Exception:
            self.close();raise

    def close(self):
        if self.db is not None:self.db.close();self.db=None
        if self._dir_fd is not None:os.close(self._dir_fd);self._dir_fd=None

    def register(self,identity,parent=None):
        require(isinstance(identity,str) and 0<len(identity)<=128,'FAMILY_ID')
        require(parent is None or isinstance(parent,str),'FAMILY_PARENT')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            existing=self.db.execute('SELECT parent FROM family WHERE id=?',(identity,)).fetchone()
            if existing:require(existing==(parent,),'FAMILY_PARENT_IMMUTABLE')
            else:
                require(parent!=identity,'FAMILY_CYCLE')
                if parent is not None:require(self.db.execute('SELECT 1 FROM family WHERE id=?',(parent,)).fetchone() is not None,'UNKNOWN_PARENT')
                self.db.execute('INSERT INTO family VALUES(?,?)',(identity,parent))
            self.db.commit()
        except Exception:self.db.rollback();raise

    def lineage(self,identity):
        result=[]
        while identity is not None:
            require(identity not in result,'FAMILY_CYCLE')
            row=self.db.execute('SELECT parent FROM family WHERE id=?',(identity,)).fetchone()
            require(row is not None,'UNKNOWN_FAMILY');result.append(identity);identity=row[0]
        return result

    def expose(self,identity,case_hash,receipt_hash):
        require_hash(case_hash);require_hash(receipt_hash)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            # Conservatively expose the entire registered root genealogy, including siblings.
            root=self.lineage(identity)[-1]
            self.db.execute('INSERT OR IGNORE INTO exposure VALUES(?,?,?)',(root,case_hash,receipt_hash))
            self.db.commit()
        except Exception:self.db.rollback();raise

    def status(self,identity,case_hash):
        require_hash(case_hash)
        for family in self.lineage(identity):
            if self.db.execute('SELECT 1 FROM exposure WHERE family=? AND case_hash=?',(family,case_hash)).fetchone():return 'EXPOSED'
        # Absence of exposure is not proof of secrecy or a sealed evaluation.
        return 'NO_RECORDED_EXPOSURE_NOT_SEALED_CERTIFICATION'


def paired_statistics(raw: bytes, protocol: dict, protocol_sha256: str):
    """Hoeffding bounds for fixed-n independent task-cluster paired differences [-1,1].

    Inputs are submitted bytes, not proof of model identity, execution or independence.
    Every score must already be oriented higher-is-better and normalized by a frozen rubric.
    """
    require_hash(protocol_sha256);require(sha256(canonical(protocol))==protocol_sha256,'PROTOCOL_ANCHOR_MISMATCH')
    require(protocol.get('schema')=='QRCEL_PAIRED_BOUNDED_PROTOCOL_V1','PROTOCOL_SCHEMA')
    dims=protocol.get('dimensions');require(isinstance(dims,dict) and set(dims)==set(DIMENSIONS),'DIMENSION_COVERAGE')
    alpha=protocol.get('alpha');require(type(alpha) in (int,float) and math.isfinite(alpha) and 0<alpha<1,'ALPHA')
    n=protocol.get('fixed_n');require(type(n) is int and 1<=n<=100000,'FIXED_N')
    require(protocol.get('sampling_unit')=='INDEPENDENT_TASK_CLUSTER','SAMPLING_UNIT')
    for margin in dims.values():require(type(margin) in (int,float) and math.isfinite(margin) and 0<=margin<=1,'MARGIN')
    require(type(raw) is bytes and len(raw)<=16*1024*1024,'SCORE_INPUT_SIZE')
    data=parse_json(raw);require(isinstance(data,dict) and set(data)=={'schema','rows','hard_vetoes'},'DATA_SCHEMA')
    require(data['schema']=='QRCEL_SUBMITTED_PAIRED_SCORES_V1','DATA_SCHEMA')
    rows=data['rows'];require(isinstance(rows,list) and len(rows)==n,'FIXED_N_MISMATCH')
    veto=data['hard_vetoes'];require(isinstance(veto,list) and all(isinstance(x,str) and x for x in veto),'VETO_SCHEMA')
    ids=set();differences={d:[] for d in dims}
    for row in rows:
        require(isinstance(row,dict) and set(row)=={'cluster_id','candidate','reference'},'ROW_SCHEMA')
        identity=row['cluster_id'];require(isinstance(identity,str) and identity and identity not in ids,'DUPLICATE_OR_INVALID_CLUSTER');ids.add(identity)
        for role in ('candidate','reference'):
            scores=row[role];require(isinstance(scores,dict) and set(scores)==set(dims),'SCORE_COVERAGE')
            for score in scores.values():require(type(score) in (int,float) and math.isfinite(score) and 0<=score<=1,'SCORE_RANGE')
        for d in dims:differences[d].append(row['candidate'][d]-row['reference'][d])
    radius=math.sqrt(2*math.log(2*len(dims)/alpha)/n)
    results={}
    for d,values in differences.items():
        mean=math.fsum(values)/n;lower=max(-1,mean-radius);upper=min(1,mean+radius)
        results[d]={'mean_paired_difference':mean,'lower':lower,'upper':upper,'margin':dims[d],
                    'conditional_noninferiority':lower>=-dims[d]}
    return {'scope':'SUBMITTED_SCORES_CONDITIONAL_STATISTICS_ONLY','protocol_sha256':protocol_sha256,
            'scores_sha256':sha256(raw),'n_clusters':n,'method':'HOEFFDING_TWO_SIDED_BONFERRONI_FIXED_N',
            'dimensions':results,'hard_vetoes':veto,'conditional_all_dimensions_pass':not veto and all(x['conditional_noninferiority'] for x in results.values()),
            'assumptions_verified':False,'model_execution_verified':False,'sealed_verified':False,
            'parity':'INSUFFICIENT_EVIDENCE','promotion_authorized':False}


def promotion_inventory(receipts: dict):
    """Inventory only. A claimed PASS, even hashed, is not an attested gate result."""
    require(isinstance(receipts,dict) and set(receipts)<=set(GATES),'GATE_SCHEMA')
    rows={}
    for gate in GATES:
        entry=receipts.get(gate)
        if entry is None:rows[gate]={'status':'MISSING_EVIDENCE'};continue
        require(isinstance(entry,dict) and set(entry)=={'artifact_sha256','claimed_result','scope'},'RECEIPT_SCHEMA')
        require_hash(entry['artifact_sha256'])
        require(entry['claimed_result'] in ('PASS','FAIL','BLOCKED'),'GATE_RESULT')
        require(isinstance(entry['scope'],str) and entry['scope'],'GATE_SCOPE')
        rows[gate]={'status':'SUBMITTED_UNATTESTED','receipt':entry}
    return {'gates':rows,'decision':'PROMOTION_NOT_AUTHORIZED','scientific_authority':False,
            'reason':'Independent gate-specific evidence verification and existing QROS authorization remain required.'}
