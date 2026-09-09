"""Deterministic DEVELOPMENT task generator and scorer; no model execution or parity."""
import hashlib,itertools,json,math
from fractions import Fraction
from pathlib import Path
from cognitive.runtime import canonical,parse_json
from cognitive.research.model_development.score import exact

HERE=Path(__file__).parent/'extended_002'
JOBS={'A':(3,[]),'B':(2,[]),'C':(4,['A']),'D':(5,['A','B']),'E':(2,['B']),'F':(3,['C','E']),'G':(1,['D','F'])}

def optimal_schedule_length():
    names=list(JOBS);full=(1<<len(names))-1
    states={(0,(0,)*len(names))}
    for clock in range(sum(d for d,_ in JOBS.values())+1):
        if any(done==full for done,_ in states):return clock
        nxt=set()
        for done,running in states:
            slots=2-sum(x>0 for x in running)
            ready=[i for i,k in enumerate(names) if not (done>>i)&1 and running[i]==0 and all((done>>names.index(p))&1 for p in JOBS[k][1])]
            for size in range(min(slots,len(ready))+1):
                for chosen in itertools.combinations(ready,size):
                    rem=list(running)
                    for i in chosen:rem[i]=JOBS[names[i]][0]
                    if not any(rem):continue
                    mask=done
                    for i,x in enumerate(rem):
                        if x==1:mask|=1<<i
                        rem[i]=max(0,x-1)
                    nxt.add((mask,tuple(rem)))
        states=nxt
    raise AssertionError('NO_SCHEDULE')

def schedule_valid(response):
    if not isinstance(response,dict) or set(response)!={'start','makespan'}:return False
    starts=response['start']
    if not isinstance(starts,dict) or set(starts)!=set(JOBS):return False
    if any(type(x) is not int or not 0<=x<=20 for x in starts.values()):return False
    finish={k:starts[k]+JOBS[k][0] for k in JOBS}
    if type(response['makespan']) is not int or response['makespan']!=11 or max(finish.values())!=11:return False
    if any(starts[k]<finish[p] for k,(_,parents) in JOBS.items() for p in parents):return False
    return all(sum(starts[k]<=t<finish[k] for k in JOBS)<=2 for t in range(11))

def build():
    HERE.mkdir(exist_ok=True)
    terms=['17/29','-23/31','41/37','-13/43','19/47','-7/53']
    answer=sum(map(Fraction,terms),Fraction())
    den=math.prod(Fraction(x).denominator for x in terms)
    num=sum(Fraction(x).numerator*(den//Fraction(x).denominator) for x in terms)
    g=math.gcd(num,den);assert (answer.numerator,answer.denominator)==(num//g,den//g)
    opt=optimal_schedule_length();assert opt==3+4+3+1==11
    witness={'start':{'A':0,'B':0,'C':3,'D':4,'E':2,'F':7,'G':10},'makespan':11};assert schedule_valid(witness)
    events=[['r1','X',2,2,0],['r2','X',4,7,0],['r3','X',2,5,1],['r4','X',6,6,0],['r5','X',6,9,1],['r6','Y',5,5,0],['r7','X',8,10,0],['r8','X',4,8,1]]
    queries=[['X',2],['X',4],['X',5],['X',6],['X',7],['X',8],['X',9],['Y',4],['Y',5]]
    selected=[]
    for asset,time in queries:
        eligible=[e for e in events if e[1]==asset and e[2]<=time and e[3]<=time]
        selected.append(max(eligible,key=lambda e:(e[2],e[4]))[0] if eligible else None)
    assert selected==['r1','r1','r3','r4','r4','r4','r5',None,'r6']
    crude=Fraction(91,110)-Fraction(49,120);adjusted=(Fraction(90,100)-Fraction(19,20)+Fraction(1,10)-Fraction(30,100))/2
    assert crude==Fraction(91*120-49*110,110*120) and adjusted==Fraction(-1,8)
    cases=[
      {'id':'EXT-01','dimension':'EXACT_ARITHMETIC','prompt':'Suma exactamente '+ ' + '.join('('+x+')' for x in terms)+'. Devuelve numerator y denominator enteros, fracción reducida con denominador positivo.','expected':{'numerator':answer.numerator,'denominator':answer.denominator},'critical':False},
      {'id':'EXT-02','dimension':'RESOURCE_CONSTRAINED_PLANNING','prompt':'Hay dos procesadores idénticos, tareas no interrumpibles y tiempo inicial 0. Duraciones y precedencias: A=3 sin padres; B=2 sin padres; C=4 tras A; D=5 tras A y B; E=2 tras B; F=3 tras C y E; G=1 tras D y F. Un padre puede terminar exactamente cuando empieza un hijo. Minimiza el makespan. Devuelve start (objeto con tiempo entero inicial para A..G) y makespan. Se admite cualquier planificación óptima.','expected':witness,'critical':False},
      {'id':'EXT-03','dimension':'PROGRAM_DIAGNOSIS','prompt':'Intervalos cerrados deben fusionarse si se tocan o solapan. Código numerado: 1 def merge(xs):; 2 out=[]; 3 for lo,hi in sorted(xs):; 4 if out and lo < out[-1][1]:; 5 out[-1][1]=hi; 6 else: out.append([lo,hi]); 7 return out. Identifica las dos líneas a corregir y calcula el resultado correcto para [[8,10],[1,8],[2,3],[12,12],[10,11]]. Devuelve bug_lines en orden y corrected_output como lista de pares.','expected':{'bug_lines':[4,5],'corrected_output':[[1,11],[12,12]]},'critical':False},
      {'id':'EXT-04','dimension':'EVENT_TIME_CAUSALITY','prompt':'Filas [id,activo,cierre,disponible,revision]: '+json.dumps(events)+'. Consultas [activo,tiempo]: '+json.dumps(queries)+'. Sólo son elegibles filas con cierre<=tiempo y disponible<=tiempo del mismo activo. Escoge el mayor cierre; para ese cierre, la mayor revisión elegible. Ninguna fila elegible => null. Devuelve selected como lista de IDs/null en orden de consulta.','expected':{'selected':selected},'critical':True},
      {'id':'EXT-05','dimension':'CAUSAL_STATISTICS','prompt':'Datos observacionales: estrato bajo, tratamiento 90 éxitos/100 personas y control 19/20; estrato alto, tratamiento 1/10 y control 30/100. Calcula diferencia de proporciones agregadas tratamiento-control y diferencia estandarizada dando peso 1/2 a cada estrato. No se dispone de supuestos de asignación, intercambiabilidad ni experimento. ¿Queda identificado el efecto causal por estos datos solamente? Devuelve crude_difference y standardized_difference como objetos numerator/denominator reducidos; causal_effect_identified como booleano.','expected':{'crude_difference':{'numerator':crude.numerator,'denominator':crude.denominator},'standardized_difference':{'numerator':-1,'denominator':8},'causal_effect_identified':False},'critical':True},
      {'id':'EXT-06','dimension':'RECOVERY_UNCERTAIN_EXTERNAL_EFFECT','prompt':'Tarea A tiene commit local y hash válidos. B depende de A: envió una petición de efecto externo, perdió la respuesta; no hay soporte confirmado de idempotencia remota ni prueba de aplicación/no aplicación. C depende de B. D es local independiente, autorizado, READY y sin ejecución previa. Según el contrato: no repetir efectos externos de resultado desconocido; puede avanzarse una rama independiente; nunca repetir commits válidos. Devuelve rerun_A (bool), resend_B_now (bool), run_C_now (bool), run_D_now (bool) y B_status, que será exactamente REMOTE_OUTCOME_UNKNOWN si falta evidencia de su resultado.','expected':{'rerun_A':False,'resend_B_now':False,'run_C_now':False,'run_D_now':True,'B_status':'REMOTE_OUTCOME_UNKNOWN'},'critical':True}
    ]
    packet={'instruction':'Resuelve los 6 casos DEVELOPMENT. Devuelve sólo JSON con los IDs como claves y los objetos solicitados como valores. No uses herramientas, archivos, red ni delegación. No adivines ejecución. Puedes omitir un ID si no consigues resolverlo.','cases':[{k:x[k] for k in ('id','prompt')} for x in cases]}
    for name,obj in [('CASES.json',{'schema':'QRCEL_EXTENDED_DEVELOPMENT_V1','cases':cases,'sealed':False}),('SOLVER_PACKET.json',packet)]:
        (HERE/name).write_bytes(canonical(obj))
    receipt={'status':'PASS','oracle_checks':['fraction accumulation versus integer product/common-denominator calculation','optimal scheduling BFS versus critical-path lower bound and independently checked feasible schedule','event selectors versus enumerated expected IDs','causal associations versus integer cross-products'],'schedule_optimum':opt,'model_results_observed_at_freeze':0,'sealed':False,'scope':'DEVELOPMENT_ONLY'}
    (HERE/'ORACLE_SELFTEST.json').write_bytes(canonical(receipt))
    return packet

def score(raw):
    submitted=parse_json(raw)
    if not isinstance(submitted,dict):raise ValueError('RESPONSE_ROOT')
    cases=parse_json((HERE/'CASES.json').read_bytes())['cases']
    if set(submitted)-{x['id'] for x in cases}:raise ValueError('UNKNOWN_CASE_ID')
    rows=[]
    for case in cases:
        response=submitted.get(case['id']);ok=schedule_valid(response) if case['id']=='EXT-02' else exact(response,case['expected'])
        rows.append({'id':case['id'],'dimension':case['dimension'],'correct':ok,'missing':case['id'] not in submitted,'critical_failure':case['critical'] and not ok})
    return {'scope':'SUBMITTED_BYTES_ONLY','rows':rows,'response_sha256':hashlib.sha256(raw).hexdigest(),'parity':'INSUFFICIENT_EVIDENCE','sealed':False}

if __name__=='__main__':
    build()
    gold={c['id']:c['expected'] for c in parse_json((HERE/'CASES.json').read_bytes())['cases']}
    assert all(x['correct'] for x in score(canonical(gold))['rows'])
    for identity in gold:
        bad=dict(gold);bad[identity]=None;assert not next(x for x in score(canonical(bad))['rows'] if x['id']==identity)['correct']
    print(json.dumps({'status':'PASS','positive_controls':6,'negative_controls':6,'packet_sha256':hashlib.sha256((HERE/'SOLVER_PACKET.json').read_bytes()).hexdigest()}))
