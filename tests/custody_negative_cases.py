#!/usr/bin/env python3
import hashlib, os, shutil, subprocess, sys, tempfile
from pathlib import Path

if len(sys.argv) != 3:
    raise SystemExit('usage: custody_negative_cases.py <qros-bin> <project-root>')
BIN=Path(sys.argv[1]); ROOT=Path(sys.argv[2])
PROFILE=ROOT/'examples/custody_v1/profile.custody'
SOURCE=ROOT/'examples/custody_v1/source'

def run(profile: Path, source: Path, out: Path):
    cp=subprocess.run([str(BIN),'source-custody',str(profile),str(source),str(out)],text=True,capture_output=True)
    return cp.returncode, cp.stdout, cp.stderr

def check(name, fn):
    try: fn(); print(f'PASS {name}')
    except Exception as e: print(f'FAIL {name}: {e}'); raise

def copy_fixture(td: Path):
    src=td/'source'; shutil.copytree(SOURCE,src)
    prof=td/'profile.custody'; shutil.copy2(PROFILE,prof)
    return prof,src

def expect_fail_mutator(mutator, needle=None):
    with tempfile.TemporaryDirectory() as t:
        td=Path(t); prof,src=copy_fixture(td); mutator(prof,src)
        rc,out,err=run(prof,src,td/'receipt')
        assert rc != 0, (rc,out,err)
        text=out+err
        if needle: assert needle in text, text

def positive():
    with tempfile.TemporaryDirectory() as t:
        td=Path(t); prof,src=copy_fixture(td)
        rc,out,err=run(prof,src,td/'receipt')
        assert rc==0,(rc,out,err)
        assert 'archive_custody_verified=1' in out
        assert 'decoded_bytes_verified=1' in out
        assert 'decode_lineage_verified=1' in out
        assert 'production_source_provenance_ready=0' in out
        assert 'status=TEST_PROVENANCE_READY' in out

def profile_cmd_mutator(mutator, needle):
    with tempfile.TemporaryDirectory() as t:
        td=Path(t); prof=td/'profile.custody'; shutil.copy2(PROFILE,prof); mutator(prof)
        cp=subprocess.run([str(BIN),'custody-profile-check',str(prof)],text=True,capture_output=True)
        assert cp.returncode!=0,(cp.stdout,cp.stderr)
        assert needle in cp.stderr,cp.stderr

check('positive',positive)
check('missing_part',lambda: expect_fail_mutator(lambda p,s:(s/'SYNTH_SOURCE.part02.bin').unlink(),'missing_files=1'))
check('same_length_mutation',lambda: expect_fail_mutator(lambda p,s:(s/'SYNTH_SOURCE.part01.bin').write_bytes(b'ALPHA-part-001\n'),'wrong_hash=1'))
check('truncated_part',lambda: expect_fail_mutator(lambda p,s:(s/'SYNTH_SOURCE.part02.bin').write_bytes(b'beta\n'),'wrong_size=1'))
check('swapped_equal_size_parts',lambda: expect_fail_mutator(lambda p,s: ((lambda a,b:(a.write_bytes(b.read_bytes()),b.write_bytes(b'alpha-part-001\n')))(s/'SYNTH_SOURCE.part01.bin',s/'SYNTH_SOURCE.part03.bin')),'wrong_hash=2'))
check('extra_namespace_file',lambda: expect_fail_mutator(lambda p,s:(s/'SYNTH_SOURCE.part04.bin').write_bytes(b'extra'),'unexpected_namespace_files=1'))

def symlink_part(p,s):
    q=s/'SYNTH_SOURCE.part02.bin'; q.unlink(); q.symlink_to(s/'SYNTH_SOURCE.part01.bin')
check('symlink_part',lambda: expect_fail_mutator(symlink_part,'symlinks_rejected=1'))

def hardlink_alias(p,s):
    q=s/'SYNTH_SOURCE.part03.bin'; q.unlink(); os.link(s/'SYNTH_SOURCE.part01.bin',q)
check('hardlink_alias',lambda: expect_fail_mutator(hardlink_alias,'inode_aliases=1'))
check('casefold_collision',lambda: expect_fail_mutator(lambda p,s:(s/'SYNTH_SOURCE.PART01.bin').write_bytes(b'x'),'casefold_collisions=1'))
check('decoded_mutation',lambda: expect_fail_mutator(lambda p,s:(s/'SYNTH_SOURCE.decoded.bin').write_bytes(b'X'+(s/'SYNTH_SOURCE.decoded.bin').read_bytes()[1:]),'decoded_hash_match=0'))

def symlink_decoded(p,s):
    q=s/'SYNTH_SOURCE.decoded.bin'; q.unlink(); q.symlink_to(s/'SYNTH_SOURCE.part01.bin')
check('symlink_decoded',lambda: expect_fail_mutator(symlink_decoded,'symlinks_rejected=1'))
check('unknown_decoder_is_pending',lambda: expect_fail_mutator(lambda p,s:p.write_text(p.read_text().replace('decoder_id=QROS_CONCAT_V1','decoder_id=UNKNOWN_DECODER_V1')),'status=BYTES_VERIFIED_DECODE_LINEAGE_PENDING'))
# Real directory symlink rejection is a direct command-level test.
with tempfile.TemporaryDirectory() as t:
    td=Path(t); prof,src=copy_fixture(td); alias=td/'alias'; alias.symlink_to(src, target_is_directory=True)
    cp=subprocess.run([str(BIN),'source-custody',str(prof),str(alias),str(td/'r')],text=True,capture_output=True)
    assert cp.returncode!=0 and 'real directory' in cp.stderr
print('PASS source_directory_symlink_real')

with tempfile.TemporaryDirectory() as t:
    td=Path(t); prof,src=copy_fixture(td); q=src/'SYNTH_SOURCE.part02.bin'; q.unlink(); os.mkfifo(q)
    cp=subprocess.run([str(BIN),'source-custody',str(prof),str(src),str(td/'r')],text=True,capture_output=True,timeout=10)
    assert cp.returncode!=0 and 'non_regular_files=1' in cp.stdout,(cp.returncode,cp.stdout,cp.stderr)
print('PASS non_regular_fifo')

check('profile_total_mismatch',lambda: profile_cmd_mutator(lambda p:p.write_text(p.read_text().replace('total_bytes=60','total_bytes=61')),'sum(part.bytes)'))
check('profile_part_order',lambda: profile_cmd_mutator(lambda p:p.write_text(p.read_text().replace('part=2,','part=3,',1)),'contiguous'))
check('profile_duplicate_name',lambda: profile_cmd_mutator(lambda p:p.write_text(p.read_text().replace('SYNTH_SOURCE.part02.bin','SYNTH_SOURCE.part01.bin')),'duplicate part filename'))
check('profile_traversal',lambda: profile_cmd_mutator(lambda p:p.write_text(p.read_text().replace('SYNTH_SOURCE.part02.bin','../evil.bin')),'unsafe part basename'))
def uppercase_decoded_hash(p):
    text=p.read_text()
    value=next(line.split('=',1)[1] for line in text.splitlines() if line.startswith('decoded_sha256='))
    p.write_text(text.replace('decoded_sha256='+value,'decoded_sha256='+value.upper()))
check('profile_bad_hash_case',lambda: profile_cmd_mutator(uppercase_decoded_hash,'decoded contract invalid'))

def immutable_conflict():
    with tempfile.TemporaryDirectory() as t:
        td=Path(t); prof,src=copy_fixture(td); out=td/'receipt'
        rc,stdout,stderr=run(prof,src,out); assert rc==0,(stdout,stderr)
        # Change build-independent profile identity while keeping a valid profile.
        prof.write_text(prof.read_text().replace('profile_id=SYNTH_CUSTODY_V1','profile_id=SYNTH_CUSTODY_V1B'))
        rc,stdout,stderr=run(prof,src,out)
        assert rc!=0 and 'immutable output conflict' in stderr,(rc,stdout,stderr)
check('immutable_receipt_conflict',immutable_conflict)

# Profile input itself must be a stable regular file, not a symlink.
with tempfile.TemporaryDirectory() as t:
    td=Path(t); prof,src=copy_fixture(td); real=td/'profile.real'; prof.rename(real); prof.symlink_to(real)
    cp=subprocess.run([str(BIN),'source-custody',str(prof),str(src),str(td/'r')],text=True,capture_output=True)
    assert cp.returncode!=0 and 'symlink rejected' in cp.stderr,(cp.stdout,cp.stderr)
print('PASS custody_profile_symlink_rejected')

# Resource bound protects the profile parser from unbounded text allocation.
with tempfile.TemporaryDirectory() as t:
    td=Path(t); prof,src=copy_fixture(td); prof.write_bytes(b'X'*(1_048_577))
    cp=subprocess.run([str(BIN),'source-custody',str(prof),str(src),str(td/'r')],text=True,capture_output=True)
    assert cp.returncode!=0 and 'byte limit exceeded' in cp.stderr,(cp.stdout,cp.stderr)
print('PASS custody_profile_size_bound')

print('CUSTODY_NEGATIVE_CASES_PASS=22')
