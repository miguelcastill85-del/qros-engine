#!/usr/bin/env python3
"""Authenticated GitHub Git-Data CAS transport for QROS WAL, no dependency on PC.

Can be invoked by an authorized runtime with GITHUB_TOKEN, or mirrored using the
connected GitHub plugin's create_blob/tree/commit/update_ref/readback methods.
No implicit retry: uncertain remote state requires a readback before another write.
"""
from __future__ import annotations
import base64,hashlib,json,os,re,sys,urllib.error,urllib.parse,urllib.request

H40=re.compile(r'^[0-9a-f]{40}$');PATH=re.compile(r'^[A-Za-z0-9_.\-/]+$')
class CASStop(RuntimeError):pass

def git_sha(data:bytes)->str:return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
def sha256(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def safe_path(path:str)->str:
    if not isinstance(path,str) or not PATH.fullmatch(path) or path.startswith('/') or any(x in ('','.','..') for x in path.split('/')):
        raise CASStop('UNSAFE_GIT_PATH')
    return path

class GitHubHTTP:
    def __init__(self,repo:str,token:str|None=None,base='https://api.github.com'):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):raise CASStop('INVALID_REPO')
        self.repo=repo;self.token=token or os.environ.get('GITHUB_TOKEN')
        if not self.token:raise CASStop('GITHUB_TOKEN_REQUIRED_FOR_NATIVE_HTTP_MODE')
        self.base=base.rstrip('/')+'/repos/'+repo
    def request(self,method:str,path:str,obj=None):
        body=None if obj is None else json.dumps(obj,separators=(',',':'),allow_nan=False).encode()
        hdr={'Accept':'application/vnd.github+json','Authorization':'Bearer '+self.token,'X-GitHub-Api-Version':'2022-11-28'}
        if body is not None:hdr['Content-Type']='application/json'
        req=urllib.request.Request(self.base+path,data=body,headers=hdr,method=method)
        try:
            with urllib.request.urlopen(req,timeout=30) as reply:
                return json.loads(reply.read())
        except urllib.error.HTTPError as e:
            # No automatic retry. A timeout after server acceptance is ambiguous.
            raise CASStop('GITHUB_HTTP_'+str(e.code)+':'+method+':'+path) from e
        except (TimeoutError,urllib.error.URLError) as e:raise CASStop('GITHUB_UNKNOWN_OUTCOME_READBACK_REQUIRED:'+method+':'+path) from e
    def head(self,branch):return self.request('GET','/git/ref/heads/'+urllib.parse.quote(branch,safe=''))['object']['sha']
    def commit(self,sha):return self.request('GET','/git/commits/'+sha)
    def blob(self,sha):return self.request('GET','/git/blobs/'+sha)
    def create_blob(self,b:bytes):return self.request('POST','/git/blobs',{'content':base64.b64encode(b).decode('ascii'),'encoding':'base64'})['sha']
    def create_tree(self,base_tree,elements):return self.request('POST','/git/trees',{'base_tree':base_tree,'tree':elements})['sha']
    def create_commit(self,tree,parent,message):return self.request('POST','/git/commits',{'message':message,'tree':tree,'parents':[parent]})['sha']
    def move_ref(self,branch,commit):return self.request('PATCH','/git/refs/heads/'+urllib.parse.quote(branch,safe=''),{'sha':commit,'force':False})
    def fetch_path(self,branch,path):
        v=self.request('GET','/contents/'+urllib.parse.quote(path,safe='/')+'?ref='+urllib.parse.quote(branch,safe=''))
        if v['type']!='file':raise CASStop('REMOTE_NOT_FILE')
        return v['sha']

class AtomicCAS:
    def __init__(self,transport,branch):
        self.api=transport;self.branch=branch
    def publish(self,expected_parent:str,files:dict[str,bytes],message:str,expected_previous_blobs:dict[str,str|None]|None=None):
        if not H40.fullmatch(expected_parent):raise CASStop('EXPECTED_PARENT_NOT_SHA1')
        if not files or len(files)>20:raise CASStop('FILE_TRANSACTION_CARDINALITY')
        for path in files:safe_path(path)
        if expected_previous_blobs is not None:
            if set(expected_previous_blobs)!=set(files):raise CASStop('PREVIOUS_BLOB_CONTRACT_INCOMPLETE')
        actual=self.api.head(self.branch)
        if actual!=expected_parent:raise CASStop('BRANCH_TIP_CHANGED_BEFORE_UPLOAD')
        if expected_previous_blobs is not None:
            for path,pin in expected_previous_blobs.items():
                if pin is None:
                    try:previous=self.api.fetch_path(self.branch,path)
                    except CASStop as e:
                        if 'GITHUB_HTTP_404:' not in str(e):raise
                    else:raise CASStop('IMMUTABLE_PATH_ALREADY_EXISTS:'+path+':'+previous)
                else:
                    if self.api.fetch_path(self.branch,path)!=pin:raise CASStop('PREVIOUS_BLOB_DRIFT:'+path)
        commit=self.api.commit(expected_parent)
        objects={}
        for path,b in files.items():
            expected=git_sha(b);actual=self.api.create_blob(b)
            if actual!=expected:raise CASStop('BLOB_CREATION_SHA_MISMATCH:'+path)
            remote=self.api.blob(actual)
            if remote['sha']!=expected or remote.get('encoding')!='base64' or base64.b64decode(remote['content'],validate=False)!=b:
                raise CASStop('REMOTE_BLOB_READBACK_FAILED:'+path)
            objects[path]={'sha':expected,'sha256':sha256(b),'bytes':len(b)}
        if self.api.head(self.branch)!=expected_parent:raise CASStop('BRANCH_DRIFT_BEFORE_TREE')
        elements=[{'path':p,'mode':'100644','type':'blob','sha':o['sha']} for p,o in objects.items()]
        tree=self.api.create_tree(commit['tree']['sha'],elements)
        new_commit=self.api.create_commit(tree,expected_parent,message)
        if self.api.head(self.branch)!=expected_parent:raise CASStop('BRANCH_DRIFT_BEFORE_CAS')
        self.api.move_ref(self.branch,new_commit) # force=false, must be FF
        if self.api.head(self.branch)!=new_commit:raise CASStop('CAS_OUTCOME_UNVERIFIED')
        for path,o in objects.items():
            if self.api.fetch_path(self.branch,path)!=o['sha']:raise CASStop('BRANCH_PATH_READBACK_FAILED:'+path)
        return {'status':'ATOMIC_GIT_CAS_REMOTE_READBACK_PASS','commit':new_commit,'parent':expected_parent,'blobs':objects}
