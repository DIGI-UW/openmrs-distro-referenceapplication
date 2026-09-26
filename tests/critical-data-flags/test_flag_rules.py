"""Critical data flag migration suite: seeds a matrix, evaluates, asserts."""
import json, urllib.request, urllib.error, urllib.parse, base64, sys, time
from datetime import date, timedelta

B = "http://localhost/openmrs/ws/rest/v1"
AUTH = "Basic " + base64.b64encode(b"admin:Admin123").decode()
T = date.today()

IDT = "240f85fa-46e1-540e-9234-2796c623f7ea"; LOC = "73e6a40f-b1b2-5dcc-883e-70ac8a8f4703"
ENC_IANDO = "c9b87090-8768-50be-987e-8ca0a8983429"
ENC_PREG  = "ce6b111e-9beb-5a91-91ad-ec5043976fd5"
ENC_CONS  = "c2503561-c00d-5460-8157-43d594472b4a"
ENC_INR   = "b4bb88a3-9a04-5142-85bd-bb63c270f632"
ENC_BPG   = "04cf03db-3b8e-5020-84b0-50b06338767a"

DX       = "1a5aa050-661d-5e89-95d7-c1eba476df22"
SAP      = "668e0221-8b41-5669-9ad8-78e193d42494"
Q28      = "50be4b26-6c5b-5aaa-9254-3bfd313b4522"
Q21      = "2f3ee632-dd14-51b0-a4ec-de10e7958019"
ORAL_PEN = "b9884219-358a-594b-94f5-f8a8863a25f3"
INJ      = "183fb30e-b861-5b7c-806f-7118a40f2b51"
PROC     = "7a54d2d6-0d34-5e5d-b8e7-84a3cf7e9dca"
DEATH    = "2567da9f-864e-5408-b5ae-6686f80d0a99"
DHOME    = "98ea6c57-5f77-549b-97ca-32604c5b9220"
TRANSFER = "8a4f573d-ebc2-5073-b396-39ebe01fe56d"
DDATE    = "d4317b82-5d37-5b59-ac32-4922f18cd65b"
FUDATE   = "49f9238d-2ca4-5efd-a5cb-f00a0b44828d"
PERF     = "1c14c3f1-1532-51b0-8680-d761e7f25ad5"
SITE     = "15e033f6-704e-5bde-ac1d-b401294f416c"
SEPS     = "86c4348a-1ec0-5ca2-a9a6-15f0f282cb95"
ANTI     = "d5421303-4a78-57ca-a274-a4d90ea99b28"
WARF     = "5e97fe35-58df-4925-bba7-7c49d75268a1"
RIVA     = "a84e7a9b-31c6-5c6f-8257-45c140f661fc"
INRT     = "0778ce12-ddba-5e22-b5fd-92424e8747b4"
INRV     = "d894d89a-04bd-5fc0-91a0-5dc3ddd8802b"
EDD      = "3ad5133c-80d0-5007-ba1a-c5be27cbb10c"
DMODE    = "2c13856b-5622-500f-b986-f1509c424056"
DMODEV   = "155884AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
ALIVE    = "726b7eaa-3ecf-5c6b-ba21-cd81c58d6a0d"
NO       = "1066AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
MPREG    = "d476b4e0-5c24-5d99-9588-26aadc1e35c6"

RHD_A="7cfaaf46-1939-5437-8d40-31095cb29812"; RHD_B="2a648c80-594c-5442-bdfc-70e7472ef5b7"
RHD_C="5458f2f7-9eba-5ba4-b2a8-6c736d574ca9"; RHD_D="19fb7b40-528e-5b1c-a610-f2e624c98038"
ARF="cbfcf051-bee3-549d-b233-e5be0e7d691a"; OTHER_HD="7c42e9be-5828-5d4c-8a6e-f713efe8a945"
CONGENITAL="365e75bb-35bc-503f-b8db-53bea2528d1b"; SCREEN="27f33ebe-77fb-575f-b737-00aa47dae6d8"

SAP_MISSING="RHD prophylaxis not prescribed"; INR_MISSING="RHD INR target missing"
PERF_MISSING="RHD perfusion issues not recorded"; SITE_MISSING="RHD site infection not recorded"
SEPS_MISSING="RHD bacterial sepsis not recorded"; FU_DUE="RHD 30-day follow-up due"
DELIV="RHD delivery outcome overdue"; DEAD="RHD death not recorded on patient"
OVERDUE="RHD prophylaxis overdue"; LTFU="RHD lost to follow-up"
HOSP3 = {PERF_MISSING, SITE_MISSING, SEPS_MISSING}


def call(path, payload=None, method=None):
    req = urllib.request.Request(B + "/" + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        method=method or ("POST" if payload is not None else "GET"))
    req.add_header("Authorization", AUTH); req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return {"__error": e.read().decode()[:300]}


def d(days_ago):
    return (T - timedelta(days=days_ago)).isoformat()


def mk(ident, label):
    r = call("patient", {"person": {"names": [{"givenName": "CDF", "familyName": label}],
             "gender": "F", "birthdate": "1995-05-05"},
             "identifiers": [{"identifier": ident, "identifierType": IDT, "location": LOC, "preferred": True}]})
    if r.get("uuid"):
        return r["uuid"]
    found = call("patient?q=%s&v=custom:(uuid)" % ident).get("results", [])
    return found[0]["uuid"] if found else None


_forms = {}


def form(name):
    """The uuid of a form by name, as the form engine records it on the encounter."""
    if name not in _forms:
        hits = [f for f in call("form?q=%s&v=custom:(uuid,name)" % urllib.parse.quote(name)).get("results", [])
                if f["name"] == name]
        _forms[name] = hits[0]["uuid"] if hits else None
    return _forms[name]


def enc(pu, etype, days_ago, obs, form_name=None):
    payload = {"patient": pu, "encounterType": etype, "location": LOC,
               "encounterDatetime": d(days_ago) + "T09:00:00.000+0000", "obs": obs}
    if form_name:
        payload["form"] = form(form_name)
    return call("encounter", payload)


def consult(pu, days_ago, obs, form_name="RHD Consultation Visit"):
    return enc(pu, ENC_CONS, days_ago, obs, form_name)


def injection(pu, days_ago):
    return enc(pu, ENC_BPG, days_ago, [D(INJ, days_ago)], "RHD BPG Delivery")


C = lambda c, v: {"concept": c, "value": v}
D = lambda c, days: {"concept": c, "value": d(days)}

# (id, label, builder, expected flag names)
CASES = [
 ("rhd95001","sap_rhd_a",      lambda p: enc(p,ENC_CONS,5,[C(DX,RHD_A)]),                    {SAP_MISSING}),
 ("rhd95002","sap_rhd_b",      lambda p: enc(p,ENC_CONS,5,[C(DX,RHD_B)]),                    {SAP_MISSING}),
 ("rhd95003","sap_rhd_c",      lambda p: enc(p,ENC_CONS,5,[C(DX,RHD_C)]),                    {SAP_MISSING}),
 ("rhd95004","sap_rhd_d",      lambda p: enc(p,ENC_CONS,5,[C(DX,RHD_D)]),                    {SAP_MISSING}),
 ("rhd95005","sap_arf",        lambda p: enc(p,ENC_CONS,5,[C(DX,ARF)]),                      {SAP_MISSING}),
 ("rhd95006","sap_other_hd",   lambda p: enc(p,ENC_CONS,5,[C(DX,OTHER_HD)]),                 set()),
 ("rhd95007","sap_congenital", lambda p: enc(p,ENC_CONS,5,[C(DX,CONGENITAL)]),               set()),
 ("rhd95008","sap_screening",  lambda p: enc(p,ENC_CONS,5,[C(DX,SCREEN)]),                   set()),
 ("rhd95009","sap_present",    lambda p: enc(p,ENC_CONS,5,[C(DX,RHD_A),C(SAP,Q28)]),         set()),
 ("rhd95010","sap_no_dx",      lambda p: enc(p,ENC_CONS,5,[]),                               set()),

 ("rhd95011","inr_warfarin_no_target", lambda p: enc(p,ENC_INR,5,[C(ANTI,WARF)]),            {INR_MISSING}),
 ("rhd95012","inr_warfarin_target",    lambda p: enc(p,ENC_INR,5,[C(ANTI,WARF),C(INRT,INRV)]), set()),
 ("rhd95013","inr_rivaroxaban",        lambda p: enc(p,ENC_INR,5,[C(ANTI,RIVA)]),            set()),
 ("rhd95014","inr_no_anticoag",        lambda p: enc(p,ENC_INR,5,[]),                        set()),

 ("rhd95015","hosp_death_blank",   lambda p: enc(p,ENC_IANDO,20,[C(PROC,DEATH)]),                    HOSP3|{DEAD}),
 ("rhd95016","hosp_home_past",     lambda p: enc(p,ENC_IANDO,20,[C(PROC,DHOME),D(DDATE,15)]),        HOSP3),
 ("rhd95017","hosp_home_future",   lambda p: enc(p,ENC_IANDO,2,[C(PROC,DHOME),{"concept":DDATE,"value":(T+timedelta(days=5)).isoformat()}]), set()),
 ("rhd95018","hosp_all_recorded",  lambda p: enc(p,ENC_IANDO,20,[C(PROC,DHOME),D(DDATE,15),C(PERF,False),C(SITE,False),C(SEPS,False)]), set()),
 ("rhd95019","hosp_transfer",      lambda p: enc(p,ENC_IANDO,20,[C(PROC,TRANSFER),D(DDATE,15)]),     set()),
 ("rhd95020","hosp_partial",       lambda p: enc(p,ENC_IANDO,20,[C(PROC,DHOME),D(DDATE,15),C(PERF,False)]), {SITE_MISSING,SEPS_MISSING}),

 ("rhd95021","fu_overdue",         lambda p: enc(p,ENC_IANDO,45,[D(DDATE,40)]),                      {FU_DUE}),
 ("rhd95022","fu_recorded",        lambda p: enc(p,ENC_IANDO,45,[D(DDATE,40),D(FUDATE,5)]),          set()),
 ("rhd95023","fu_too_soon",        lambda p: enc(p,ENC_IANDO,12,[D(DDATE,10)]),                      set()),
 ("rhd95024","fu_boundary_30",     lambda p: enc(p,ENC_IANDO,32,[D(DDATE,30)]),                      set()),
 ("rhd95025","fu_boundary_31",     lambda p: enc(p,ENC_IANDO,33,[D(DDATE,31)]),                      {FU_DUE}),
 ("rhd95026","fu_patient_died",    lambda p: enc(p,ENC_IANDO,45,[C(PROC,DEATH),D(DDATE,40)]),        HOSP3|{DEAD}),

 ("rhd95027","deliv_overdue",      lambda p: enc(p,ENC_PREG,60,[D(EDD,40)]),                          {DELIV}),
 ("rhd95028","deliv_recorded",     lambda p: enc(p,ENC_PREG,60,[D(EDD,40),C(DMODE,DMODEV)]),          set()),
 ("rhd95029","deliv_too_soon",     lambda p: enc(p,ENC_PREG,15,[D(EDD,10)]),                          set()),
 ("rhd95030","deliv_boundary_30",  lambda p: enc(p,ENC_PREG,35,[D(EDD,30)]),                          set()),

 ("rhd95031","death_proc_outcome", lambda p: enc(p,ENC_IANDO,20,[C(PROC,DEATH),C(PERF,False),C(SITE,False),C(SEPS,False)]), {DEAD}),
 ("rhd95032","death_alive_no",     lambda p: enc(p,ENC_CONS,5,[C(ALIVE,False)]),                      {DEAD}),
 ("rhd95033","death_maternal",     lambda p: enc(p,ENC_PREG,20,[C(MPREG,"Maternal Death during labour")]), {DEAD}),
 ("rhd95034","death_alive_yes",    lambda p: enc(p,ENC_CONS,5,[C(ALIVE,True)]),                       set()),
 ("rhd95035","death_transfer",     lambda p: enc(p,ENC_IANDO,20,[C(PROC,TRANSFER),C(PERF,False),C(SITE,False),C(SEPS,False)]), set()),

 # Overdue follows the regimen on the latest prescription, as ACT 2.0's Not Covered filter does.
 ("rhd95036","ov_q28_overdue",     lambda p: [consult(p,40,[C(SAP,Q28)]), injection(p,40)],                 {OVERDUE}),
 ("rhd95037","ov_q28_covered",     lambda p: [consult(p,40,[C(SAP,Q28)]), injection(p,10)],                 set()),
 ("rhd95038","ov_switched_to_oral",lambda p: [consult(p,100,[C(SAP,Q28)]), consult(p,20,[C(SAP,ORAL_PEN)]), injection(p,60)], set()),
 ("rhd95039","ov_q21_then_q28",    lambda p: [consult(p,100,[C(SAP,Q21)]), consult(p,10,[C(SAP,Q28)]), injection(p,25)], set()),

 # Lost to follow-up counts only consultations, as ACT 2.0's most_recent_rhd_consultation does.
 ("rhd95040","ltfu_no_contact",    lambda p: [consult(p,240,[C(SAP,Q28)]), injection(p,240)],               {OVERDUE,LTFU}),
 ("rhd95041","ltfu_consent_only",  lambda p: [consult(p,240,[C(SAP,Q28)]), injection(p,240), consult(p,10,[],"RHD Consent")], {OVERDUE,LTFU}),
 ("rhd95042","ltfu_allergies_only",lambda p: [consult(p,240,[C(SAP,Q28)]), injection(p,240), consult(p,10,[],"RHD Allergies")], {OVERDUE,LTFU}),
 ("rhd95043","ltfu_recent_consult",lambda p: [consult(p,240,[C(SAP,Q28)]), injection(p,240), consult(p,100,[])], {OVERDUE}),
 ("rhd95044","ltfu_recent_update", lambda p: [consult(p,240,[C(SAP,Q28)]), injection(p,240), consult(p,10,[],"RHD Consultation Update")], {OVERDUE}),
]


def seed():
    made = {}
    for ident, label, build, expected in CASES:
        pu = mk(ident, label)
        if not pu:
            print("  SEED FAIL %s" % ident); continue
        r = build(pu)
        for one in r if isinstance(r, list) else [r]:
            if isinstance(one, dict) and not one.get("uuid"):
                print("  ENC FAIL %s: %s" % (ident, one.get("__error", "")[:160]))
        made[ident] = pu
    return made


def evaluate():
    flags = call("patientflags/flag?v=custom:(uuid,enabled)").get("results", [])
    for f in flags:
        if f.get("enabled"):
            call("patientflags/flag/%s" % f["uuid"], {"enabled": True})
    time.sleep(12)


def actual(pu):
    res = call("patientflags/patientflag?patient=%s&v=full" % pu).get("results", [])
    return {r["flag"]["display"] for r in res}


def main():
    print("seeding %d cases" % len(CASES))
    made = seed()
    print("evaluating")
    evaluate()
    print()
    fails = []
    for ident, label, build, expected in CASES:
        pu = made.get(ident)
        if not pu:
            continue
        got = actual(pu)
        ok = got == expected
        if not ok:
            fails.append((ident, label, expected, got))
        print("%-4s %-9s %-22s exp=%-46s got=%s" % ("PASS" if ok else "FAIL", ident[-5:], label,
              ",".join(sorted(e[4:] for e in expected)) or "-",
              ",".join(sorted(g[4:] for g in got)) or "-"))
    print()
    print("%d/%d passed" % (len(CASES) - len(fails), len(CASES)))
    if fails:
        print("\nFAILURES")
        for ident, label, exp, got in fails:
            print("  %s %s" % (ident, label))
            print("     missing: %s" % (sorted(exp - got) or "-"))
            print("     extra:   %s" % (sorted(got - exp) or "-"))
    return 1 if fails else 0


sys.exit(main())
