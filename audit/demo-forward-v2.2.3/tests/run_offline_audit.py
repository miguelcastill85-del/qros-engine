#!/usr/bin/env python3
"""TEST_ONLY. Translate this frozen MQL subset to JS and inject deterministic APIs.

This is NOT MetaEditor, Trade.mqh, a broker simulator certification, or EX5 parity.
No network/terminal APIs are invoked. The original source hashes are mandatory.
The emitted JS is retained for inspection. Integer fidelity is limited to 2**53-1;
tests at that boundary concern terminal-global doubles, not native MQL long overflow.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

BASE = Path(__file__).resolve().parents[1]
TYPES = r'(?:bool|int|long|ulong|uint|double|string|datetime|ENUM_\w+|MqlTick|MqlDateTime|QrosBusEvent|QrosRiskResult|PendingEntry|CTrade)'
OBJECTS = {'MqlTick', 'MqlDateTime', 'QrosBusEvent', 'QrosRiskResult', 'PendingEntry', 'CTrade'}


def verify_sources():
    receipt = json.loads((BASE / 'FROZEN_SOURCE_RECEIPT.json').read_text())
    rows = []
    for f in receipt['files']:
        p = BASE / 'frozen' / f['path']
        row = {'path': f['path']}
        if not p.is_file():
            row.update(classification='BLOCKED', status='BLOCKED_PENDING_EXACT_SOURCE_IMPORT')
        else:
            b = p.read_bytes()
            row.update(bytes=len(b), sha256=hashlib.sha256(b).hexdigest(),
                       git_blob_sha1=hashlib.sha1(b'blob ' + str(len(b)).encode() + b'\0' + b).hexdigest())
            if any(row[k] != f[k] for k in ('bytes', 'sha256', 'git_blob_sha1')):
                raise RuntimeError('Frozen source identity mismatch: ' + f['path'])
            row.update(classification='TEST_PROVEN', status='PASS')
        rows.append(row)
    return rows


def close_at(s, start, op='(', cl=')'):
    depth = 0
    for i in range(start, len(s)):
        if s[i] == op:
            depth += 1
        elif s[i] == cl:
            depth -= 1
            if depth == 0:
                return i
    raise ValueError('unbalanced source')


def function_text(src, name):
    m = re.search(r'\b' + TYPES + r'\s+' + name + r'\s*\(', src)
    if not m:
        m = re.search(r'\bvoid\s+' + name + r'\s*\(', src)
    if not m:
        raise ValueError(name)
    begin = src.index('{', m.end())
    return src[m.start():close_at(src, begin, '{', '}') + 1]


def translate(src):
    # Protect literal strings before lexical changes; comments have no semantics.
    strings = []
    def protect(m):
        if m.group().startswith(('//', '/*')):
            return '\n' * m.group().count('\n')
        strings.append(m.group())
        return f'QSTR{len(strings)-1}TOKEN'
    src = re.sub(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*[\s\S]*?\*/', protect, src)
    src = re.sub(r'^\s*#define\s+(\w+)\s+([0-9]+)\s*$', r'const \1=\2;', src, flags=re.M)
    src = re.sub(r'^\s*#.*$', '', src, flags=re.M)
    def struct(m):
        name, fields = m.groups()
        assigns = []
        for typ, field in re.findall(r'(' + TYPES + r')\s+(\w+)\s*;', fields):
            val = f'new {typ}()' if typ in OBJECTS else ('""' if typ == 'string' else '0')
            assigns.append(f'this.{field}={val};')
        return 'function ' + name + '(){' + ''.join(assigns) + '}'
    src = re.sub(r'struct\s+(\w+)\s*\{([\s\S]*?)\};', struct, src)
    # Primitive reference parameters become mutable boxes. Object refs are direct.
    pat = re.compile(r'\b(?:void|' + TYPES + r')\s+(\w+)\s*\(([^()]*)\)\s*\{')
    offset = 0
    while (m := pat.search(src, offset)):
        end = close_at(src, m.end()-1, '{', '}')
        body = src[m.end():end]
        params = []
        for p in m.group(2).split(','):
            if not p.strip():
                continue
            pm = re.fullmatch(r'\s*(?:const\s+)?(' + TYPES + r')\s*(&?)\s*(\w+)(.*)', p)
            if not pm:
                raise ValueError('parameter ' + p)
            typ, ref, name, default = pm.groups()
            params.append(name + default)
            if ref and typ not in OBJECTS:
                body = re.sub(r'\b' + name + r'\b', name + '.value', body)
        replacement = 'function ' + m.group(1) + '(' + ','.join(params) + '){' + body + '}'
        src = src[:m.start()] + replacement + src[end+1:]
        offset = m.start() + len(replacement)
    # Preserve cast-to-integer behavior for this source's primary expressions.
    cast = re.compile(r'\((int|long|ulong|uint|double|datetime|ENUM_\w+)\)\s*')
    while (m := cast.search(src)):
        start = m.end()
        if src[start] == '(':
            end = close_at(src, start) + 1
        else:
            operand = re.match(r'[\w.]+', src[start:])
            if not operand:
                raise ValueError('cast operand ' + src[start:start+40])
            end = start + operand.end()
            if end < len(src) and src[end] == '(':
                end = close_at(src, end) + 1
        value = src[start:end]
        if m.group(1) in ('int', 'long', 'ulong', 'uint'):
            value = 'Math.trunc(' + value + ')'
        src = src[:m.start()] + value + src[end:]
    src = re.sub(r'(\d)L\b', r'\1', src)
    src = re.sub(r'\b(?:input\s+)?(?:const\s+)?(' + TYPES + r')\s+(\w+)\[(\d*)\](?:=\{([^}]*)\})?;',
                 lambda m: 'let ' + m[2] + '=[' + (m[4] or '') + '];', src)
    src = re.sub(r'\b(?:input\s+)?(?:const\s+)?(' + TYPES + r')\s+(\w+)\s*;',
                 lambda m: 'let ' + m[2] + '=' + (f'new {m[1]}()' if m[1] in OBJECTS else ('""' if m[1] == 'string' else '0')) + ';', src)
    src = re.sub(r'\b(?:input\s+)?(?:const\s+)?' + TYPES + r'\s+(\w+)', r'let \1', src)
    # Adapt primitive output arguments at call sites without hand-editing formulas.
    for name in ('OrderCalcProfit', 'ReservedRiskUsd'):
        offset = 0
        while (m := re.search(r'\b' + name + r'\(', src[offset:])):
            start = offset + m.end() - 1
            end = close_at(src, start)
            if src[max(0, offset+m.start()-9):offset+m.start()] == 'function ':
                offset = end + 1
                continue
            args = src[start+1:end]
            last = args.rsplit(',', 1)[-1].strip()
            if not re.fullmatch(r'\w+', last):
                raise ValueError('output argument ' + last)
            args = args[:len(args)-len(last)] + '{set value(v){' + last + '=v;}}'
            src = src[:start+1] + args + src[end:]
            offset = start + len(args) + 2
    for i, literal in enumerate(strings):
        src = src.replace(f'QSTR{i}TOKEN', literal)
    return src


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--node', required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--proposal', action='store_true')
    args = ap.parse_args()
    rows = verify_sources()
    out = args.out.resolve()
    if not out.is_relative_to(BASE.resolve()):
        raise SystemExit('Output must remain inside this audit directory')
    out.mkdir(parents=True, exist_ok=False)
    paths = [BASE/'frozen/MQL5/Include/QROS_DEMO_BUS_v2.mqh',
             BASE/'frozen/MQL5/Include/QROS_RISK_KERNEL_APPROVED_v15420.mqh',
             BASE/'frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5']
    if args.proposal:
        paths[-1] = BASE/'proposed/v2.2.4/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5'
    parts = [(p, p.read_text()) for p in paths]
    bp = BASE/'frozen/MQL5/Scripts/QROS_V223_RUNTIME_BOOTSTRAP.mq5'
    boot = bp.read_text()
    chosen = ['ExecAge', 'DemoGate', 'ExpertName', 'CountQrosPositions', 'TickState', 'SeriesCurrent', 'RuntimeFailure']
    offset_body = boot[boot.index('long raw_offset='):boot.index('long exec_age=')]
    offset_probe = ('int OffsetProbe(const long prior,const int stable,const bool have) {'
                    'long last_offset=prior;int offset_stable=stable;bool have_offset=have;' + offset_body + 'return offset_stable;}')
    parts.append((bp, '\n'.join(function_text(boot, n) for n in chosen) + '\n' + offset_probe))
    script = (BASE/'tests/stubs.js').read_text() + '\n'
    for path, source in parts:
        script += '\n// SOURCE: ' + path.relative_to(BASE).as_posix() + '\n' + translate(source)
    script += '\nconst PROPOSAL=' + str(args.proposal).lower() + ';\n'
    script += (BASE/'tests/scenarios.js').read_text()
    (out/'translated_probe.js').write_text(script, encoding='utf-8')
    p = subprocess.run([args.node, str(out/'translated_probe.js')], capture_output=True, text=True)
    (out/('stdout.json' if p.returncode == 0 else 'stdout.txt')).write_text(p.stdout, encoding='utf-8')
    (out/'stderr.txt').write_text(p.stderr, encoding='utf-8')
    metadata = {'scope': 'TEST_ONLY_MQL_SUBSET_TRANSLATION_WITH_SCRIPTED_API',
                'mt5_executed': False, 'network_used': False, 'proposal': args.proposal,
                'python': sys.version, 'node': subprocess.check_output([args.node, '--version'], text=True).strip(),
                'sources': rows, 'translated_js_sha256': hashlib.sha256(script.encode()).hexdigest(),
                'translated_js_hash_representation': 'logical_utf8_lf_before_platform_text_output',
                'translated_js_file_sha256': hashlib.sha256((out/'translated_probe.js').read_bytes()).hexdigest(),
                'process_exit_code': p.returncode}
    (out/'RUN_RECEIPT.json').write_text(json.dumps(metadata, indent=2)+'\n')
    if p.returncode:
        print(p.stderr)
        return p.returncode
    result = json.loads(p.stdout)
    print(json.dumps({'tests': len(result), 'PASS': sum(x['status']=='PASS' for x in result),
                      'FAIL': sum(x['status']=='FAIL' for x in result), 'output': str(out)}))
    # 0 only means the probe completed. Product failures remain FAIL in evidence.
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
