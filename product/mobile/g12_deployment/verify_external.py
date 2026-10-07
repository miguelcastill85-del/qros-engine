"""Independent Python HTTPS observation and synthetic receipt digest verifier."""
import hashlib,json,pathlib,sys,urllib.request,urllib.error,re

receipt=json.loads(pathlib.Path(sys.argv[1]).read_text())
assert receipt['status']=='PASS_TEST_ONLY_EXTERNAL_HTTPS'
result=dict(receipt['synthetic_result'])
expected=result.pop('result_sha256')
actual=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
assert actual==expected
assert all(result[k] is False for k in ('scientific_approval','holdout_open','ga2_open','mt5_executed'))
assert result['economic_tests']==0 and result['classification']=='TEST_ONLY_SYNTHETIC_INFRASTRUCTURE'
assert re.fullmatch(r'https://qros-mobile-g12-test-only\.[a-z0-9-]+\.workers\.dev',receipt['public_origin'])
url=receipt['public_origin']+'/v1/session/refresh'
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None
opener=urllib.request.build_opener(NoRedirect)
try:
    opener.open(urllib.request.Request(url,method='POST'),timeout=20)
    raise AssertionError('unauthenticated request accepted')
except urllib.error.HTTPError as e:
    assert e.code==401
    assert 'no-store' in e.headers.get('Cache-Control','')
    assert 'Access-Control-Allow-Origin' not in e.headers
out={'schema':'QROS_G12_PYTHON_EXTERNAL_VERIFICATION_V1','status':'PASS_TEST_ONLY',
     'https_certificate_validation':'DEFAULT_SYSTEM_TRUST_ENABLED',
     'unauthenticated_http_status':401,'result_sha256':actual,'scientific_authority':False}
pathlib.Path(sys.argv[2]).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
print(json.dumps(out))
