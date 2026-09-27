#!/usr/bin/env python3
"""Fail-closed cloud loader: execute only exact SHA-pinned W5 release from private R2."""
import hashlib,json,os,pathlib,sys,zipfile
RELEASE='QROS_W5_CLOUD_GITHUB_HOSTED_CANDIDATE_v2_20260927.zip'
RELEASE_SHA='565a8fcd826f1c33d0f5de83b338608301407732c2cdb2f3bf8ac02d2311b831'
BOOT_SHA='1055459de141e7729841bd4074a4e59b7dbf58c2bcd2424af8277efce41fba17'
PREFIX='qros-w5/'
def require(ok,why):
    if not ok:raise RuntimeError(why)
def fetch_release(directory):
    required=('R2_ACCOUNT_ID','R2_ACCESS_KEY_ID','R2_SECRET_ACCESS_KEY','R2_BUCKET')
    require(all(os.environ.get(k) for k in required),'MISSING_PRIVATE_R2_SECRETS')
    import boto3
    from botocore.config import Config
    s3=boto3.client('s3',endpoint_url='https://'+os.environ['R2_ACCOUNT_ID']+'.r2.cloudflarestorage.com',
        aws_access_key_id=os.environ['R2_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'],region_name='auto',
        config=Config(signature_version='s3v4'))
    obj=[]
    for page in s3.get_paginator('list_objects_v2').paginate(Bucket=os.environ['R2_BUCKET'],Prefix=PREFIX):
        obj.extend(x for x in page.get('Contents',[]) if x['Key'].endswith('/'+RELEASE))
    require(len(obj)==1,'CLOUD_PACKAGE_MISSING_OR_AMBIGUOUS')
    path=pathlib.Path(directory)/RELEASE;path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('wb') as out:s3.download_fileobj(os.environ['R2_BUCKET'],obj[0]['Key'],out)
    require(path.stat().st_size==obj[0]['Size'] and hashlib.sha256(path.read_bytes()).hexdigest()==RELEASE_SHA,
            'CLOUD_PACKAGE_SHA256_OR_SIZE_DRIFT')
    return path
def main():
    require(len(sys.argv)==2,'USAGE: loader.py DATA_ROOT')
    root=pathlib.Path(sys.argv[1]);root.mkdir(parents=True,exist_ok=True)
    package=fetch_release(root/'r2_package')
    with zipfile.ZipFile(package) as z:
        matches=[n for n in z.namelist() if n.endswith('/qros_w5_cloud_bootstrap_v2.py')]
        require(len(matches)==1,'RELEASE_BOOTSTRAP_AMBIGUOUS')
        source=z.read(matches[0])
    require(hashlib.sha256(source).hexdigest()==BOOT_SHA,'RELEASE_BOOTSTRAP_BYTE_DRIFT')
    target=root/'verified_cloud_bootstrap.py';target.write_bytes(source)
    os.environ['QROS_W5_PINNED_RELEASE_SHA256']=RELEASE_SHA
    os.execv(sys.executable,[sys.executable,str(target),'--data-root',str(root)])
if __name__=='__main__':
    try:main()
    except Exception as ex:
        print(json.dumps({'status':'FAIL_CLOSED','reason':str(ex),
                          'economic_PNL_read':False,'holdout_open':False},sort_keys=True),file=sys.stderr)
        raise SystemExit(3)
