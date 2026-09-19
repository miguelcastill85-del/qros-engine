from qros_manifest_first_recovery_guard_v1 import validate

def base():
    m={'XAUUSD':{'parts':[{'file':'a.zip','zip_sha256':'aa','zip_bytes':10},{'file':'b.zip','zip_sha256':'bb','zip_bytes':20}]}}
    r={'schema':'QROS_RUNTIME_NEUTRAL_CARRIER_LOCATOR_1.0','resolution_mode':'MANIFEST_FIRST_DIRECT_MATERIALIZE','broad_recursive_search_allowed':False,'entries':[
        {'file':'a.zip','expected_sha256':'aa','expected_bytes':10,'file_id':'f1','library_file_id':'l1','path':'/a.zip'},
        {'file':'b.zip','expected_sha256':'bb','expected_bytes':20,'file_id':'f2','library_file_id':'l2','path':'/b.zip'}]}
    return m,r

def main():
    cases=[]
    m,r=base(); cases.append(validate(m,r)['status']=='PASS')
    m,r=base(); r['broad_recursive_search_allowed']=True; cases.append('BROAD_SEARCH_NOT_FORBIDDEN' in validate(m,r)['errors'])
    m,r=base(); r['entries'][0]['expected_sha256']='xx'; cases.append('SHA:a.zip' in validate(m,r)['errors'])
    m,r=base(); r['entries'][0]['expected_bytes']=11; cases.append('SIZE:a.zip' in validate(m,r)['errors'])
    m,r=base(); r['entries']=r['entries'][:1]; cases.append('MISSING:b.zip' in validate(m,r)['errors'])
    m,r=base(); r['entries'][0]['file_id']=''; cases.append('LOCATOR:a.zip' in validate(m,r)['errors'])
    m,r=base(); r['entries'].append(dict(r['entries'][0])); cases.append('DUPLICATE_REGISTRY_FILE' in validate(m,r)['errors'])
    m,r=base(); r['resolution_mode']='SEARCH_FIRST'; cases.append('RESOLUTION_MODE' in validate(m,r)['errors'])
    assert all(cases),cases
    print('PASS 8/8')
if __name__=='__main__': main()
