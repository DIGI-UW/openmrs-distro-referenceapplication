"""Lifecycle and integrity: does a flag clear when the gap is filled, and is the store sane."""
import json, urllib.request, urllib.error, base64, sys, time
from datetime import date, timedelta

B="http://localhost/openmrs/ws/rest/v1"; AUTH="Basic "+base64.b64encode(b"admin:Admin123").decode()
T=date.today()
IDT="240f85fa-46e1-540e-9234-2796c623f7ea"; LOC="73e6a40f-b1b2-5dcc-883e-70ac8a8f4703"
ENC_IANDO="c9b87090-8768-50be-987e-8ca0a8983429"; ENC_PREG="ce6b111e-9beb-5a91-91ad-ec5043976fd5"
ENC_CONS="c2503561-c00d-5460-8157-43d594472b4a"; ENC_INR="b4bb88a3-9a04-5142-85bd-bb63c270f632"
DX="1a5aa050-661d-5e89-95d7-c1eba476df22"; SAP="668e0221-8b41-5669-9ad8-78e193d42494"
Q28="50be4b26-6c5b-5aaa-9254-3bfd313b4522"; RHD_A="7cfaaf46-1939-5437-8d40-31095cb29812"
PROC="7a54d2d6-0d34-5e5d-b8e7-84a3cf7e9dca"; DHOME="98ea6c57-5f77-549b-97ca-32604c5b9220"
DDATE="d4317b82-5d37-5b59-ac32-4922f18cd65b"; FUDATE="49f9238d-2ca4-5efd-a5cb-f00a0b44828d"
PERF="1c14c3f1-1532-51b0-8680-d761e7f25ad5"
ANTI="d5421303-4a78-57ca-a274-a4d90ea99b28"; WARF="5e97fe35-58df-4925-bba7-7c49d75268a1"
INRT="0778ce12-ddba-5e22-b5fd-92424e8747b4"; INRV="d894d89a-04bd-5fc0-91a0-5dc3ddd8802b"
EDD="3ad5133c-80d0-5007-ba1a-c5be27cbb10c"; DMODE="2c13856b-5622-500f-b986-f1509c424056"
DMODEV="155884AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"

def call(path,payload=None,method=None):
    req=urllib.request.Request(B+"/"+path,
        data=json.dumps(payload).encode() if payload is not None else None,
        method=method or ("POST" if payload is not None else "GET"))
    req.add_header("Authorization",AUTH); req.add_header("Content-Type","application/json")
    try:
        with urllib.request.urlopen(req,timeout=90) as r: return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e: return {"__error":e.read().decode()[:300]}

def d(n): return (T-timedelta(days=n)).isoformat()
def mk(ident,label):
    r=call("patient",{"person":{"names":[{"givenName":"LC","familyName":label}],"gender":"F","birthdate":"1995-05-05"},
        "identifiers":[{"identifier":ident,"identifierType":IDT,"location":LOC,"preferred":True}]})
    if r.get("uuid"): return r["uuid"]
    f=call("patient?q=%s&v=custom:(uuid)"%ident).get("results",[])
    return f[0]["uuid"] if f else None
def reset(pu):
    """Void everything recorded for this patient so a re-run starts in the gap state again.
    The previous run's clearing step would otherwise leave the gap already filled."""
    for e in call("encounter?patient=%s&v=custom:(uuid)"%pu).get("results",[]):
        call("encounter/%s"%e["uuid"], None, "DELETE")
    for o in call("obs?patient=%s&v=custom:(uuid)"%pu).get("results",[]):
        call("obs/%s"%o["uuid"], None, "DELETE")

def enc(pu,et,n,obs):
    return call("encounter",{"patient":pu,"encounterType":et,"location":LOC,
        "encounterDatetime":d(n)+"T09:00:00.000+0000","obs":obs})
def evaluate():
    for f in call("patientflags/flag?v=custom:(uuid,enabled)").get("results",[]):
        if f.get("enabled"): call("patientflags/flag/%s"%f["uuid"],{"enabled":True})
    time.sleep(12)
def flags(pu):
    return {r["flag"]["display"] for r in call("patientflags/patientflag?patient=%s&v=full"%pu).get("results",[])}
C=lambda c,v:{"concept":c,"value":v}
D=lambda c,n:{"concept":c,"value":d(n)}

results=[]
def check(name, cond, detail=""):
    results.append((name,cond,detail))
    print("%-4s %-34s %s" % ("PASS" if cond else "FAIL", name, detail))

# --- build patients that each carry one gap
P={}
for key,ident in (("sap","rhd96001"),("inr","rhd96002"),("perf","rhd96003"),
                  ("fu","rhd96004"),("deliv","rhd96005")):
    P[key]=mk(ident,key); reset(P[key])
enc(P['sap'],ENC_CONS,5,[C(DX,RHD_A)])
enc(P['inr'],ENC_INR,5,[C(ANTI,WARF)])
e3=enc(P['perf'],ENC_IANDO,20,[C(PROC,DHOME),D(DDATE,15)])
e4=enc(P['fu'],ENC_IANDO,45,[D(DDATE,40)])
e5=enc(P['deliv'],ENC_PREG,60,[D(EDD,40)])
evaluate()

SAPM="RHD prophylaxis not prescribed"; INRM="RHD INR target missing"
PERFM="RHD perfusion issues not recorded"; FUD="RHD 30-day follow-up due"
DELIVM="RHD delivery outcome overdue"

print("\n--- the gap is present ---")
check("raise: sap",   SAPM  in flags(P['sap']))
check("raise: inr",   INRM  in flags(P['inr']))
check("raise: perf",  PERFM in flags(P['perf']))
check("raise: fu",    FUD   in flags(P['fu']))
check("raise: deliv", DELIVM in flags(P['deliv']))

print("\n--- a clinician fills the gap ---")
call("obs",{"person":P['sap'],"concept":SAP,"value":Q28,"obsDatetime":d(0)+"T10:00:00.000+0000"})
call("obs",{"person":P['inr'],"concept":INRT,"value":INRV,"obsDatetime":d(0)+"T10:00:00.000+0000"})
call("obs",{"person":P['perf'],"concept":PERF,"value":False,"obsDatetime":d(0)+"T10:00:00.000+0000",
            "encounter":e3.get("uuid")})
call("obs",{"person":P['fu'],"concept":FUDATE,"value":d(1),"obsDatetime":d(0)+"T10:00:00.000+0000",
            "encounter":e4.get("uuid")})
call("obs",{"person":P['deliv'],"concept":DMODE,"value":DMODEV,"obsDatetime":d(0)+"T10:00:00.000+0000",
            "encounter":e5.get("uuid")})
evaluate()
check("clear: sap",   SAPM  not in flags(P['sap']))
check("clear: inr",   INRM  not in flags(P['inr']))
check("clear: perf",  PERFM not in flags(P['perf']))
check("clear: fu",    FUD   not in flags(P['fu']))
check("clear: deliv", DELIVM not in flags(P['deliv']))

print("\n--- voided data must not count as recorded ---")
sap_obs=[o for o in call("obs?patient=%s&concept=%s&v=custom:(uuid)"%(P['sap'],SAP)).get("results",[])]
for o in sap_obs: call("obs/%s"%o["uuid"],None,"DELETE")
evaluate()
check("voided obs re-raises sap", SAPM in flags(P['sap']),
      "voided SAP should not satisfy the rule")

print("\n--- idempotence ---")
# Count against a patient that is actually carrying flags; a cleared patient has none and
# would make this pass without exercising anything.
P['idem']=mk("rhd96006","idem"); reset(P['idem'])
enc(P['idem'],ENC_IANDO,20,[C(PROC,DHOME),D(DDATE,15)])
evaluate()
before=call("patientflags/patientflag?patient=%s&v=full"%P['idem']).get("results",[])
evaluate(); evaluate()
after=call("patientflags/patientflag?patient=%s&v=full"%P['idem']).get("results",[])
check("carries flags to count", len(before)>0, "rows=%d"%len(before))
check("no duplicates after 2 more passes", len(after)==len(before),
      "before=%d after=%d"%(len(before),len(after)))

ok=sum(1 for _,c,_ in results if c)
print("\n%d/%d passed"%(ok,len(results)))
sys.exit(0 if ok==len(results) else 1)
