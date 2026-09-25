"""One-shot G5 real localhost TLS transport with separately pinned synthetic witness roots.
Test fixture only; uses ephemeral certificates, tenant tokens and signing keys, none shipped.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tests'))
from test_gateway import HttpsTenantGatewayTests as Demo
from data_audit import digest,canonical


def run() -> dict:
    Demo.setUpClass()
    try:
        a=Demo.client().fetch(Demo.origin,Demo.keyA)
        b=Demo.client('tenant_B','project_B','campaign_B',Demo.pubB,Demo.widB).fetch(Demo.origin,Demo.keyB)
        assert a['tenant']=='tenant_A' and b['tenant']=='tenant_B'
        assert a['head']['sequence']==1 and b['head']['sequence']==1
        assert a['head']['sha256']!=b['head']['sha256']
        assert a['scientific_approval'] is False and b['scientific_approval'] is False
        assert a['external_independent_custody']=='NOT_DEPLOYED'
        assert Demo.request(token=Demo.keyA,project='project_B')[0]==403
        assert Demo.request(method='POST',token=Demo.keyA)[0]==405
        assert Demo.request(token=None)[0]==401
        return {'schema':'QROS_MOBILE_G5_TLS_TENANT_DEMO_INTEGRATION_V1',
                'status':'PASS_LOCAL_TLS_SCOPED_SYNTHETIC_ONLY',
                'tenant_isolated_snapshots':2,'signed_witness_sequence_per_tenant':1,
                'tenant_A_audit_sha256':digest(canonical(a['audit_receipt'])),
                'tenant_B_audit_sha256':digest(canonical(b['audit_receipt'])),
                'real_tls_hostname_and_ca_verification':True,
                'cross_project_403':True,'writes_405':True,'missing_bearer_401':True,
                'read_only':True,'production_tenant_auth':'NOT_DEPLOYED',
                'independently_administered_external_witness':'NOT_DEPLOYED',
                'public_https':'NOT_DEPLOYED','physical_android_install':'NOT_RUN',
                'broker_data':'NONE','economic_backtests':0,'holdout_open':False,'ga2_open':False}
    finally:
        Demo.tearDownClass()

if __name__=='__main__':
    print(json.dumps(run(),indent=2,sort_keys=True))
