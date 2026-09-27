"""Gap queries: does each critical data flag's gap look-up name the encounter and question to complete."""
import base64, json, sys, urllib.parse, urllib.request

B = "http://localhost/openmrs/ws/rest/v1"
H = {"Authorization": "Basic " + base64.b64encode(b"admin:Admin123").decode(), "Content-Type": "application/json"}
IDT = "240f85fa-46e1-540e-9234-2796c623f7ea"; LOC = "73e6a40f-b1b2-5dcc-883e-70ac8a8f4703"
CONS = "c2503561-c00d-5460-8157-43d594472b4a"; INR = "b4bb88a3-9a04-5142-85bd-bb63c270f632"
IANDO = "c9b87090-8768-50be-987e-8ca0a8983429"; PREG = "ce6b111e-9beb-5a91-91ad-ec5043976fd5"
DX = "1a5aa050-661d-5e89-95d7-c1eba476df22"; RHD_B = "2a648c80-594c-5442-bdfc-70e7472ef5b7"
ANTI = "d5421303-4a78-57ca-a274-a4d90ea99b28"; WARF = "5e97fe35-58df-4925-bba7-7c49d75268a1"
PROC = "7a54d2d6-0d34-5e5d-b8e7-84a3cf7e9dca"; DEATH = "2567da9f-864e-5408-b5ae-6686f80d0a99"
DDATE = "d4317b82-5d37-5b59-ac32-4922f18cd65b"; EDD = "3ad5133c-80d0-5007-ba1a-c5be27cbb10c"
SAP_FLAG = "b1f7a2c0-0005-4a00-9000-000000000005"; FU_FLAG = "b1f7a2c0-0006-4a00-9000-000000000006"
INR_FLAG = "b1f7a2c0-0009-4a00-9000-000000000009"; PERF_FLAG = "b1f7a2c0-0010-4a00-9000-000000000010"
DELIV_FLAG = "b1f7a2c0-0013-4a00-9000-000000000013"; DEAD_FLAG = "b1f7a2c0-0014-4a00-9000-000000000014"


def call(path, body=None, method=None):
    req = urllib.request.Request(B + path, data=json.dumps(body).encode() if body is not None else None,
                                 method=method or ("POST" if body is not None else "GET"), headers=H)
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read() or b"{}")


def form(name):
    hits = call("/form?q=%s&v=custom:(uuid,name)" % urllib.parse.quote(name))["results"]
    return [f["uuid"] for f in hits if f["name"] == name][0]


def patient(ident, label):
    found = call("/patient?q=%s&v=custom:(uuid)" % ident)["results"]
    if found:
        uuid = found[0]["uuid"]
        for e in call("/encounter?patient=%s&v=custom:(uuid)" % uuid)["results"]:
            call("/encounter/%s" % e["uuid"], None, "DELETE")
        return uuid
    return call("/patient", {"person": {"names": [{"givenName": "Gap", "familyName": label}], "gender": "F",
                             "birthdate": "1995-01-01"},
                             "identifiers": [{"identifier": ident, "identifierType": IDT, "location": LOC,
                                              "preferred": True}]})["uuid"]


def enc(p, etype, date, form_name, obs):
    return call("/encounter", {"patient": p, "encounterType": etype, "location": LOC, "form": form(form_name),
                               "encounterDatetime": date + "T09:00:00.000+0000", "obs": obs})["uuid"]


def C(concept, value):
    return {"concept": concept, "value": value}


def gaps(p, flag):
    g = call("/rhdflags/gap?patient=%s&flag=%s" % (p, flag))
    return g["configured"], [(r["encounter"], r["form"]["display"] if r["form"] else None, r["concept"]["display"])
                             for r in g["results"]]


def case_sap_consult():
    p = patient("rhd97001", "sap_consult")
    enc(p, CONS, "2026-08-01", "RHD Patient Information", [C(DX, RHD_B)])
    older = enc(p, CONS, "2026-08-15", "RHD Consultation Visit", [])
    latest = enc(p, CONS, "2026-09-01", "RHD Consultation Visit", [])
    return gaps(p, SAP_FLAG), (True, [(latest, "RHD Consultation Visit", "Secondary Antibiotic Prophylaxis")])


def case_sap_no_consult():
    p = patient("rhd97003", "sap_no_consult")
    enc(p, CONS, "2026-08-01", "RHD Patient Information", [C(DX, RHD_B)])
    return gaps(p, SAP_FLAG), (True, [])


def case_inr_monitoring():
    p = patient("rhd97002", "inr_monitoring")
    enc(p, CONS, "2026-08-15", "RHD Anticoagulation", [C(ANTI, WARF)])
    e = enc(p, INR, "2026-09-05", "RHD INR Monitoring", [])
    return gaps(p, INR_FLAG), (True, [(e, "RHD INR Monitoring", "INR Target")])


def case_outcome_per_encounter():
    p = patient("rhd97004", "outcome_two")
    first = enc(p, IANDO, "2026-09-10", "Procedures and Outcomes", [C(PROC, DEATH)])
    second = enc(p, IANDO, "2026-09-20", "Procedures and Outcomes", [C(PROC, DEATH)])
    return gaps(p, PERF_FLAG), (True, [(first, "Procedures and Outcomes", "Perfusion Issues"),
                                       (second, "Procedures and Outcomes", "Perfusion Issues")])


def case_follow_up():
    p = patient("rhd97005", "follow_up")
    e = enc(p, IANDO, "2026-07-01", "Procedures and Outcomes", [C(DDATE, "2026-07-05")])
    return gaps(p, FU_FLAG), (True, [(e, "Procedures and Outcomes", "Date of Patient Follow-up Contact")])


def case_delivery():
    p = patient("rhd97006", "delivery")
    e = enc(p, PREG, "2026-05-01", "RHD Pregnancy", [C(EDD, "2026-06-01")])
    return gaps(p, DELIV_FLAG), (True, [(e, "RHD Pregnancy", "Delivery mode")])


def case_death_has_no_query():
    p = patient("rhd97007", "death")
    enc(p, IANDO, "2026-09-10", "Procedures and Outcomes", [C(PROC, DEATH)])
    return gaps(p, DEAD_FLAG), (False, [])


CASES = [case_sap_consult, case_sap_no_consult, case_inr_monitoring, case_outcome_per_encounter,
         case_follow_up, case_delivery, case_death_has_no_query]


def main():
    fails = 0
    for case in CASES:
        got, expected = case()
        ok = got == expected
        fails += not ok
        print("%-4s %s" % ("PASS" if ok else "FAIL", case.__name__))
        if not ok:
            print("     expected %s\n     got      %s" % (expected, got))
    print("\n%d/%d passed" % (len(CASES) - fails, len(CASES)))
    return 1 if fails else 0


sys.exit(main())
