#!/usr/bin/env python3
"""Seeds 23 fictional RHD patients whose records raise every RHD critical data flag and fill the ACT screens.

Run it once OpenMRS has started and Initializer has loaded the distro configuration:

    python3 scripts/seed-rhd-demo.py              # http://localhost, admin / Admin123
    python3 scripts/seed-rhd-demo.py --base http://localhost:8180 --password <admin password>

Each patient gets an RHD ID from the distro's generator, an RHD Registry enrolment, and one RHD Clinic
Visit per clinic day, holding the same form encounters a clinician would save (RHD Patient
Information, Consultation Visit, BPG Delivery, Anticoagulation, INR Monitoring, Procedures and
Outcomes, Pregnancy, Oral Adherence). Dates are relative to today, so the time-based flags are due
whenever it runs. Four patients also get interventional recommendations on a consultation, for the
procedural waiting list, and three screened positive, for the screen positive, pending confirmation list.

The script is safe to run again: a patient who already exists (same name and birthdate) is skipped.
It then runs the RHD Patient Flag Refresh and RHD Prophylaxis Adherence Refresh tasks, so the patient
lists, BPG status and adherence fill at once rather than at the next daily run, and checks each
patient's flags against the flags the scenario should raise.
Only the Python standard library is used.
"""
import argparse
import base64
import datetime
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# Metadata from distro/configuration.
RHD_ID_TYPE = "240f85fa-46e1-540e-9234-2796c623f7ea"
RHD_ID_SOURCE = "f1c4a7be-160e-5d9b-ae5a-345cb15186dc"
RHD_REGISTRY = "7d73e143-a550-5a9d-aecd-dd771add098d"
CLINIC_VISIT = "bf86d5a7-9511-5c11-acb1-8f8718775cd5"
LOC = {
    "tertiary": "5b5f6fb2-eb04-5d3b-a9cd-acea2027f5ad",  # Uganda Heart Institute Tertiary
    "district": "f8cf700a-2e5d-594e-86e0-061fedae2c6d",  # Kitgum General Hospital
    "community": "9aacad7c-bbc5-5669-977d-4c20e31aa6e8",  # Akunalaber HCIII
}
# Each clinic its own hours, so same-day visits do not overlap.
WINDOW = {"tertiary": 6, "district": 11, "community": 16}
# Form name -> encounter type uuid.
FORM = {
    "RHD Patient Information": "c2503561-c00d-5460-8157-43d594472b4a",
    "RHD Consultation Visit": "c2503561-c00d-5460-8157-43d594472b4a",
    "RHD Anticoagulation": "c2503561-c00d-5460-8157-43d594472b4a",
    "RHD BPG Delivery": "04cf03db-3b8e-5020-84b0-50b06338767a",
    "RHD INR Monitoring": "b4bb88a3-9a04-5142-85bd-bb63c270f632",
    "Procedures and Outcomes": "c9b87090-8768-50be-987e-8ca0a8983429",
    "RHD Pregnancy": "ce6b111e-9beb-5a91-91ad-ec5043976fd5",
    "RHD Oral Adherence": "55271793-ef37-58da-9d86-1d9092a5a809",
}
C = {
    "diagnosis": "1a5aa050-661d-5e89-95d7-c1eba476df22",
    "consult_date": "c3edefd2-5777-5084-b01e-fd4ca0e40162",
    "sap": "668e0221-8b41-5669-9ad8-78e193d42494",
    "sap_started": "5bcc7d12-b279-5955-815c-090a1f392071",
    "injection_date": "183fb30e-b861-5b7c-806f-7118a40f2b51",
    "anticoag": "d5421303-4a78-57ca-a274-a4d90ea99b28",
    "anticoag_date": "3edc315c-1914-5bc3-a587-ebb7271435a4",
    "inr_indication": "6e8ed53f-15e6-5b00-9ed0-44b11bd2d638",
    "inr_info": "0778ce12-ddba-5e22-b5fd-92424e8747b4",
    "inr_date": "be9041b1-3948-5de0-a8b1-974e84b95715",
    "inr": "161482AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    "procedure_date": "6cbb5176-144a-576b-9b3d-c9e9d6bc5f5a",
    "procedure_type": "3a576b80-744a-59ee-9515-d9fdca06f3d7",
    "surgery_type": "46f4af80-b783-59f4-beb1-81144ccf3084",
    "outcome": "7a54d2d6-0d34-5e5d-b8e7-84a3cf7e9dca",
    "discharge_date": "d4317b82-5d37-5b59-ac32-4922f18cd65b",
    "death_date": "07534416-c1c2-5772-83d8-76a429986ec0",
    "perfusion": "1c14c3f1-1532-51b0-8680-d761e7f25ad5",
    "site_infection": "15e033f6-704e-5bde-ac1d-b401294f416c",
    "sepsis": "86c4348a-1ec0-5ca2-a9a6-15f0f282cb95",
    "follow_up_date": "49f9238d-2ca4-5efd-a5cb-f00a0b44828d",
    "edd": "3ad5133c-80d0-5007-ba1a-c5be27cbb10c",
    "delivery_mode": "2c13856b-5622-500f-b986-f1509c424056",
    "date_diagnosed": "159948AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    "adherence_estimate": "8edff8dc-4af6-5d0f-bf1d-8e349c7a1b15",
    "prescription_duration": "cd03af00-de81-5c08-9a02-92f95c00e1ce",
}
A = {
    "ARF": "cbfcf051-bee3-549d-b233-e5be0e7d691a",
    "RHD A": "7cfaaf46-1939-5437-8d40-31095cb29812",
    "RHD B": "2a648c80-594c-5442-bdfc-70e7472ef5b7",
    "RHD C": "5458f2f7-9eba-5ba4-b2a8-6c736d574ca9",
    "Q28": "50be4b26-6c5b-5aaa-9254-3bfd313b4522",
    "Q21": "2f3ee632-dd14-51b0-a4ec-de10e7958019",
    "Oral penicillin V": "b9884219-358a-594b-94f5-f8a8863a25f3",
    "Warfarin": "5e97fe35-58df-4925-bba7-7c49d75268a1",
    "INR 2.5-3.5": "ea841a3a-f9cb-5761-aac6-939ffb158d94",
    "Surgery": "aa5fefb0-cf61-5f36-82e6-31dbbdf3f616",
    "Mitral valve replacement": "7af8595d-407e-5705-bd8a-812735e2f188",
    "Discharge to home": "98ea6c57-5f77-549b-97ca-32604c5b9220",
    "In-hospital death": "2567da9f-864e-5408-b5ae-6686f80d0a99",
    "Yes": "cf82933b-3f3f-45e7-a5ab-5d31aaee3da3",
    "No": "488b58ff-64f5-4f8a-8979-fa79940b1594",
    "Vaginal birth": "302eda9b-16f5-5b84-81ab-623990616233",
    "Screen + pending confirmatory echo": "27f33ebe-77fb-575f-b737-00aa47dae6d8",
    "3 months": "30f01ae8-2fc0-5ac2-be59-a573b38d73d5",
}
TODAY = datetime.date.today()


def ago(days):
    return (TODAY - datetime.timedelta(days=days)).isoformat()


def value(concept, v):
    return {"concept": C[concept], "value": A.get(v, v)}


def group(concept, *members):
    return {"concept": C[concept], "groupMembers": list(members)}


# --- What each form records ------------------------------------------------------------------------

def patient_information(diagnosis):
    return "RHD Patient Information", [value("diagnosis", diagnosis)]


def consultation(days, regimen=None):
    obs = [value("consult_date", ago(days))]
    if regimen:
        obs.append(group("sap", value("sap", regimen), value("sap_started", ago(days))))
    return "RHD Consultation Visit", obs


def injection(days):
    return "RHD BPG Delivery", [value("injection_date", ago(days))]


def warfarin(days):
    return "RHD Anticoagulation", [value("anticoag_date", ago(days)), group("anticoag", value("anticoag", "Warfarin"))]


def inr_monitoring(days, with_target):
    obs = [value("inr_indication", "Mechanical mitral valve")]
    if with_target:
        obs.append(group("inr_info", value("inr_info", "INR 2.5-3.5"), value("inr_date", ago(days)), value("inr", 2.8)))
    return "RHD INR Monitoring", obs


def valve_surgery(days, outcome, discharged_days=None, outcomes=None, follow_up_days=None):
    """Mitral valve replacement; ``outcomes`` names the Hospitalization Outcomes recorded (all No)."""
    obs = [value("procedure_date", ago(days)),
           group("procedure_type", value("procedure_type", "Surgery")),
           group("surgery_type", value("surgery_type", "Mitral valve replacement")),
           value("outcome", outcome)]
    if outcome == "Discharge to home":
        obs.append(value("discharge_date", ago(discharged_days)))
    else:
        obs.append(value("death_date", ago(days)))
    for field in outcomes if outcomes is not None else ("perfusion", "site_infection", "sepsis"):
        obs.append(value(field, "No"))
    if follow_up_days is not None:
        obs.append(value("follow_up_date", ago(follow_up_days)))
    return "Procedures and Outcomes", obs


def pregnancy(due_days_ago, delivered):
    obs = [value("edd", ago(due_days_ago))]
    if delivered:
        obs.append(value("delivery_mode", "Vaginal birth"))
    return "RHD Pregnancy", obs


def bpg_history(regimen_days, last_days, count=4, since=None):
    """Injections every ``regimen_days`` days, the latest ``last_days`` ago: ``count`` of them, or every
    one since the prescription ``since`` days ago, for a patient kept on schedule."""
    if since is not None:
        count = (since - last_days) // regimen_days + 1
    return [(last_days + i * regimen_days, injection(last_days + i * regimen_days)) for i in range(count)]


def oral_adherence(percent):
    return "RHD Oral Adherence", [value("adherence_estimate", percent), value("prescription_duration", "3 months")]


def screened(days, category="Screen + pending confirmatory echo"):
    """Patient Information recording a category at diagnosis and its date."""
    return days, "district", ("RHD Patient Information", [value("diagnosis", category), value("date_diagnosed", ago(days))])


# --- The patients ----------------------------------------------------------------------------------
# (given, family, gender, birthdate, story, expected flags, [(days ago, location, (form, obs)), ...])

def registered(days, diagnosis, regimen, loc="district"):
    """The first visit: Patient Information and a Consultation Visit on the same day."""
    return [(days, loc, patient_information(diagnosis)), (days, loc, consultation(days, regimen))]


def at(loc, entries):
    return [(d, loc, e) for d, e in entries]


PATIENTS = [
    # Seven patients whose care is up to date, each injection on time: no flag.
    ("Esther", "Nambi", "F", "2012-01-30", "Up to date on 28-day BPG", [],
     registered(150, "RHD B", "Q28") + at("community", bpg_history(28, 10, since=150))),
    ("Brian", "Mugisha", "M", "2010-04-18", "Up to date on 21-day BPG", [],
     registered(120, "RHD A", "Q21") + at("community", bpg_history(21, 7, since=120))),
    ("Patience", "Akello", "F", "2008-09-02", "Warfarin with an INR target", [],
     registered(200, "RHD C", "Q28") + at("community", bpg_history(28, 12, since=200)) +
     [(90, "tertiary", warfarin(90)), (30, "district", inr_monitoring(30, with_target=True))]),
    ("Daniel", "Ssempijja", "M", "2004-06-11", "Valve surgery, all outcomes and follow-up recorded", [],
     registered(300, "RHD C", "Q28") + at("community", bpg_history(28, 3, since=300)) +
     [(70, "tertiary", valve_surgery(70, "Discharge to home", 60, follow_up_days=25))]),
    ("Florence", "Atim", "F", "1999-12-05", "Pregnancy with delivery recorded, next injection due in 4 days", [],
     registered(250, "RHD B", "Q28") + at("community", bpg_history(28, 24, since=250)) +
     [(200, "district", pregnancy(60, delivered=True))]),
    ("Irene", "Kyomuhendo", "F", "2014-02-21", "Newly registered, first injection given", [],
     registered(2, "RHD A", "Q28") + [(2, "district", injection(2))]),
    ("Emmanuel", "Wanyama", "M", "2011-08-14", "Acute rheumatic fever on oral penicillin, 90% adherent", [],
     registered(60, "ARF", "Oral penicillin V") + [(30, "community", oral_adherence(90))]),

    # Thirteen patients who each raise at least one flag.
    ("Grace", "Achieng", "F", "2011-03-14", "21-day BPG, last injection 40 days ago",
     ["RHD prophylaxis overdue"],
     registered(160, "RHD B", "Q21") + at("community", bpg_history(21, 40))),
    ("Moses", "Ochieng", "M", "2007-10-09", "28-day BPG, last injection 45 days ago",
     ["RHD prophylaxis overdue"],
     registered(210, "RHD B", "Q28") + at("community", bpg_history(28, 45))),
    ("Joseph", "Opio", "M", "2006-05-09", "No consultation or injection for 8 months",
     ["RHD lost to follow-up", "RHD prophylaxis overdue"],
     registered(330, "RHD C", "Q28") + at("community", bpg_history(28, 240, count=3))),
    ("Samuel", "Okello", "M", "2009-07-02", "RHD B diagnosis, consultation saved without prophylaxis",
     ["RHD prophylaxis not prescribed"],
     [(20, "district", patient_information("RHD B")), (20, "district", consultation(20))]),
    ("Agnes", "Apio", "F", "2013-11-27", "Acute rheumatic fever, not yet seen in consultation",
     ["RHD prophylaxis not prescribed"],
     [(6, "district", patient_information("ARF"))]),
    ("Ruth", "Nakato", "F", "1998-11-23", "Discharged 45 days ago, 30-day follow-up not recorded",
     ["RHD 30-day follow-up due"],
     registered(400, "RHD C", "Q28") + at("community", bpg_history(28, 9)) +
     [(52, "tertiary", valve_surgery(52, "Discharge to home", 45))]),
    ("Charles", "Ssali", "M", "2002-01-19", "Discharged 80 days ago, 30-day follow-up not recorded",
     ["RHD 30-day follow-up due"],
     registered(380, "RHD C", "Q28") + at("community", bpg_history(28, 15)) +
     [(88, "tertiary", valve_surgery(88, "Discharge to home", 80))]),
    ("Peter", "Kato", "M", "2001-03-30", "On warfarin, INR monitoring saved without an INR target",
     ["RHD INR target missing"],
     registered(180, "RHD C", "Q28") + at("community", bpg_history(28, 11)) +
     [(100, "tertiary", warfarin(100)), (14, "district", inr_monitoring(14, with_target=False))]),
    ("Sarah", "Nansubuga", "F", "2003-05-16", "Discharged 14 days ago, no hospitalization outcomes",
     ["RHD perfusion issues not recorded", "RHD site infection not recorded", "RHD bacterial sepsis not recorded"],
     registered(260, "RHD C", "Q28") + at("community", bpg_history(28, 8)) +
     [(20, "tertiary", valve_surgery(20, "Discharge to home", 14, outcomes=()))]),
    ("Isaac", "Tumusiime", "M", "2000-09-08", "Discharged 10 days ago, bacterial sepsis not recorded",
     ["RHD bacterial sepsis not recorded"],
     registered(240, "RHD C", "Q28") + at("community", bpg_history(28, 6)) +
     [(16, "tertiary", valve_surgery(16, "Discharge to home", 10, outcomes=("perfusion", "site_infection")))]),
    ("Harriet", "Adong", "F", "1997-07-12", "Due date passed 50 days ago, no delivery recorded",
     ["RHD delivery outcome overdue"],
     registered(300, "RHD B", "Q28") + at("community", bpg_history(28, 18)) +
     [(250, "district", pregnancy(50, delivered=False))]),
    ("Robert", "Ouma", "M", "1995-02-03", "In-hospital death on a form, still alive on the record",
     ["RHD death not recorded on patient"],
     registered(420, "RHD C", "Q28") + at("community", bpg_history(28, 12)) +
     [(12, "tertiary", valve_surgery(12, "In-hospital death"))]),
    ("Winnie", "Auma", "F", "2005-08-25", "Valve replacement: injection, INR target and follow-up all due",
     ["RHD prophylaxis overdue", "RHD INR target missing", "RHD 30-day follow-up due"],
     registered(360, "RHD C", "Q28") + at("community", bpg_history(28, 50)) +
     [(70, "tertiary", valve_surgery(70, "Discharge to home", 62)), (62, "tertiary", warfarin(62)),
      (40, "district", inr_monitoring(40, with_target=False))]),

    # Three who screened positive, for the screen positive, pending confirmation list.
    ("Ruth", "Apio", "F", "2013-05-09", "Screened positive 12 days ago, echo pending", [], [screened(12)]),
    ("Simon", "Odongo", "M", "2009-11-23", "Screened positive 45 days ago, echo pending", [], [screened(45)]),
    ("Joyce", "Adong", "F", "2011-07-17", "Screened positive 90 days ago, confirmed RHD A 30 days ago: off the list",
     ["RHD prophylaxis not prescribed"], [screened(90), screened(30, "RHD A")]),
]


# --- Interventional recommendations, for the procedural waiting list --------------------------------
# Each is saved in an RHD Consultation Visit as the form saves it: an obs group with its procedure type,
# procedure, urgency and Completed answer, each tagged with the form field it came from, so the form
# can edit it later.

# Interventional Recommendation(s); its procedure member shares the concept.
GROUP = "ce93d393-1df5-587f-bf11-c373eac2ccf4"
URGENCY = "7b8eda07-34b6-55f2-ab6c-1b295f41918b"
COMPLETED = "1632f8dc-195d-5d67-a52e-6c7a057cb536"
SURGERY, CATHETERIZATION = "aa5fefb0-cf61-5f36-82e6-31dbbdf3f616", "91a4d13f-4bc8-54b0-a107-f4ab84cb7d60"
PROCEDURES = {
    "Mitral valve repair/replacement": (SURGERY, "7af8595d-407e-5705-bd8a-812735e2f188"),
    "Aortic valve repair/replacement": (SURGERY, "cd9c582a-71f9-5441-97a8-6d50d7dc15c8"),
    "Mitral balloon valvuloplasty": (CATHETERIZATION, "af9429ff-1b76-55f3-81ca-a9f775d93fb4"),
}
URGENCIES = {
    "1 week": "406285f2-be72-5594-8664-c8568ad9bc88",
    "1 month": "82c5209b-c183-5bc9-941c-890eba821a44",
    "3 months": "925610f9-1c3c-5396-880f-02a5fe309d53",
    "6 months": "57e3873e-018e-5ed6-b7d4-5f73ef464cbd",
}


def field(obs, question_id):
    """Tags an obs with the form field it answers, as the form engine does."""
    return {**obs, "formFieldNamespace": "rfe-forms", "formFieldPath": f"rfe-forms-{question_id}"}


def recommendation(procedure, urgency, completed=False):
    kind, answer = PROCEDURES[procedure]
    select = "interventional_recommendation_surgery" if kind == SURGERY else "interventional_recommendation_catheterization"
    return field({"concept": GROUP, "groupMembers": [
        field({"concept": C["procedure_type"], "value": kind}, "procedureType"),
        field({"concept": GROUP, "value": answer}, select),
        field({"concept": URGENCY, "value": URGENCIES[urgency]}, "urgency"),
        field({"concept": COMPLETED, "value": A["Yes" if completed else "No"]}, "interventional_recommendation_completed"),
    ]}, "interventionalRecommendationEntry")


# (given, family, [(days ago, [recommendations])]); the last consultation is the one the waiting list reads.
RECOMMENDATIONS = [
    ("Esther", "Nambi", [(40, [recommendation("Mitral valve repair/replacement", "1 month")]),
                         (20, [recommendation("Mitral valve repair/replacement", "1 month")])]),
    ("Brian", "Mugisha", [(10, [recommendation("Mitral balloon valvuloplasty", "1 week")])]),
    ("Patience", "Akello", [(15, [recommendation("Aortic valve repair/replacement", "3 months"),
                                  recommendation("Mitral balloon valvuloplasty", "1 week", completed=True)])]),
    ("Daniel", "Ssempijja", [(5, [recommendation("Mitral valve repair/replacement", "6 months")])]),
]


def has_recommendation(api, patient, form):
    encounters = api.get(f"/encounter?patient={patient}&v=custom:(form:(uuid),obs:(concept:(uuid)))")["results"]
    return any(e.get("form") and e["form"]["uuid"] == form and any(o["concept"]["uuid"] == GROUP for o in e["obs"])
               for e in encounters)


def visit_on(api, patient, day):
    """The patient's visit that day, else a new clinic visit, with a time inside it for the consultation."""
    for v in api.get(f"/visit?patient={patient}&includeInactive=true&v=custom:(uuid,startDatetime)")["results"]:
        if v["startDatetime"].startswith(day):
            return v["uuid"], v["startDatetime"]
    start = f"{day}T17:00:00.000+0000"
    visit = api.post("/visit", {"patient": patient, "visitType": CLINIC_VISIT, "location": LOC["district"],
                                "startDatetime": start, "stopDatetime": f"{day}T23:00:00.000+0000"})["uuid"]
    return visit, start


def add_recommendations(api, forms, uuids):
    """A patient who already has a recommendation on a consultation is skipped."""
    form = forms["RHD Consultation Visit"]
    for given, family, consultations in RECOMMENDATIONS:
        patient = uuids[(given, family)]
        if has_recommendation(api, patient, form):
            continue
        for days, recommendations in consultations:
            visit, at_time = visit_on(api, patient, ago(days))
            api.post("/encounter", {"patient": patient, "visit": visit, "location": LOC["district"], "form": form,
                                    "encounterType": FORM["RHD Consultation Visit"], "encounterDatetime": at_time,
                                    "obs": [field(value("consult_date", ago(days)), "date_of_review"), *recommendations]})
        print(f"            {given} {family}: {len(consultations[-1][1])} recommendation(s) on the latest consultation")


# --- REST ------------------------------------------------------------------------------------------

class Api:
    def __init__(self, base, user, password):
        self.base = base.rstrip("/") + "/openmrs/ws/rest/v1"
        self.auth = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()

    def call(self, method, path, body=None):
        req = urllib.request.Request(self.base + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": self.auth, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            sys.exit(f"{method} {path} failed with {e.code}: {e.read().decode(errors='replace')[:800]}")

    def get(self, path):
        return self.call("GET", path)

    def post(self, path, body):
        return self.call("POST", path, body)


def wait_for_server(api, minutes):
    deadline = time.time() + minutes * 60
    while True:
        try:
            req = urllib.request.Request(api.base + "/session", headers={"Authorization": api.auth})
            with urllib.request.urlopen(req, timeout=10) as r:
                if json.loads(r.read()).get("authenticated"):
                    return
                sys.exit("The server answered, but did not accept the username and password.")
        except (urllib.error.URLError, ConnectionError, TimeoutError, ValueError):
            if time.time() > deadline:
                sys.exit(f"OpenMRS did not answer at {api.base} within {minutes} minutes.")
            time.sleep(10)


def ensure_boolean_concepts(api):
    """Core stores a Yes/No answer to a Boolean question as the concepts these two properties name.

    Without them, Procedures and Outcomes cannot be saved once Perfusion Issues, Site Infection,
    Bacterial Sepsis or Is Patient Alive is answered, from this script or from the form. Concepts 1 and
    2 are core's own True and False, the answers those questions offer.
    """
    rows = api.get("/systemsetting?q=concept&limit=100&v=custom:(property,value)")["results"]
    have = {r["property"]: r["value"] for r in rows}
    for prop, concept_id in (("concept.true", "1"), ("concept.false", "2")):
        if not have.get(prop):
            api.post("/systemsetting", {"property": prop, "value": concept_id})
            print(f"Set the missing {prop} global property to {concept_id}, core's own "
                  f"{'True' if concept_id == '1' else 'False'} concept.")


def ensure_provider(api, user):
    """O3 forms save the signed-in user as the encounter's provider, so a user without one cannot save any."""
    session = api.get("/session?v=custom:(user:(person:(uuid)),currentProvider:(uuid))")
    if session.get("currentProvider"):
        return
    person = session["user"]["person"]["uuid"]
    if not api.get(f"/provider?user={urllib.parse.quote(user)}&v=custom:(uuid)")["results"]:
        api.post("/provider", {"person": person, "identifier": f"{user}-provider"})
        print(f"Made {user} a provider, so {user} can save forms in O3.")


def form_uuids(api):
    found = {f["name"]: f["uuid"] for f in api.get("/form?v=custom:(uuid,name)&limit=100")["results"]}
    missing = [name for name in FORM if name not in found]
    if missing:
        sys.exit(f"These forms are not loaded yet: {', '.join(missing)}. Wait for Initializer to finish.")
    return {name: found[name] for name in FORM}


def existing_patient(api, given, family, birthdate):
    q = urllib.parse.quote(f"{given} {family}")
    for p in api.get(f"/patient?q={q}&v=custom:(uuid,person:(birthdate,preferredName:(givenName,familyName)))")["results"]:
        name = p["person"]["preferredName"]
        if (name["givenName"], name["familyName"]) == (given, family) and (p["person"]["birthdate"] or "").startswith(birthdate):
            return p["uuid"]
    return None


def create_patient(api, forms, given, family, gender, birthdate, visits):
    rhd_id = api.post(f"/idgen/identifiersource/{RHD_ID_SOURCE}/identifier", {})["identifier"]
    patient = api.post("/patient", {
        "person": {"names": [{"givenName": given, "familyName": family}], "gender": gender, "birthdate": birthdate,
                   "addresses": [{"country": "Uganda"}]},
        "identifiers": [{"identifier": rhd_id, "identifierType": RHD_ID_TYPE, "preferred": True}]})["uuid"]
    first = max(days for days, _, _ in visits)
    api.post("/programenrollment", {"patient": patient, "program": RHD_REGISTRY, "dateEnrolled": ago(first),
                                    "location": LOC["district"]})
    by_day = {}
    for days, loc, (form, obs) in visits:
        by_day.setdefault((days, loc), []).append((form, obs))
    for (days, loc), encounters in sorted(by_day.items(), key=lambda kv: -kv[0][0]):
        visit = api.post("/visit", {"patient": patient, "visitType": CLINIC_VISIT, "location": LOC[loc],
                                    "startDatetime": f"{ago(days)}T{WINDOW[loc]:02d}:00:00.000+0000",
                                    "stopDatetime": f"{ago(days)}T{WINDOW[loc] + 4:02d}:59:00.000+0000"})["uuid"]
        for n, (form, obs) in enumerate(encounters):
            api.post("/encounter", {"patient": patient, "visit": visit, "location": LOC[loc],
                                    "encounterType": FORM[form], "form": forms[form],
                                    "encounterDatetime": f"{ago(days)}T{WINDOW[loc] + n:02d}:00:00.000+0000", "obs": obs})
    return patient, rhd_id


def run_refresh(api):
    api.post("/taskaction", {"action": "runtask", "tasks": ["RHD Patient Flag Refresh", "RHD Prophylaxis Adherence Refresh"]})


def flags_of(api, patient):
    rows = api.get(f"/patientflags/patientflag?patient={patient}&v=custom:(voided,flag:(display))")["results"]
    return sorted(r["flag"]["display"] for r in rows if not r.get("voided") and r["flag"]["display"].startswith("RHD "))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="http://localhost", help="where OpenMRS is served (default %(default)s)")
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password", default="Admin123")
    ap.add_argument("--wait", type=int, default=30, metavar="MINUTES", help="how long to wait for the server")
    ap.add_argument("--no-refresh", action="store_true", help="leave the lists to the next daily run")
    args = ap.parse_args()

    api = Api(args.base, args.user, args.password)
    wait_for_server(api, args.wait)
    ensure_boolean_concepts(api)
    ensure_provider(api, args.user)
    forms = form_uuids(api)

    seeded = []
    for given, family, gender, birthdate, story, expected, visits in PATIENTS:
        uuid = existing_patient(api, given, family, birthdate)
        created = not uuid
        if created:
            uuid, rhd_id = create_patient(api, forms, given, family, gender, birthdate, visits)
        else:
            rhd_id = "(existing)"
        print(f"{rhd_id:>10}  {given} {family}: {story}")
        seeded.append((given, family, uuid, sorted(expected), created))

    print("\nInterventional recommendations, for the procedural waiting list:")
    add_recommendations(api, forms, {(given, family): uuid for given, family, uuid, _, _ in seeded})

    if not args.no_refresh:
        print("\nRunning the flag and adherence refresh tasks, so the patient lists and BPG status fill now.")
        # taskaction runs both tasks within the request, so they have finished when it returns.
        run_refresh(api)

    # A patient seeded on an earlier day has aged since, so their time-based flags may differ; only the
    # patients created now are held to their scenario.
    print("\nFlags per patient:")
    wrong = checked = 0
    for given, family, uuid, expected, created in seeded:
        actual = flags_of(api, uuid)
        if not created:
            print(f"      {given} {family}: {', '.join(actual) or 'no flag'}   (seeded before, not checked)")
            continue
        checked += 1
        ok = actual == expected
        wrong += not ok
        print(f"  {'ok ' if ok else 'BAD'} {given} {family}: {', '.join(actual) or 'no flag'}"
              + ("" if ok else f"   (expected: {', '.join(expected) or 'no flag'})"))
    if wrong:
        sys.exit(f"\n{wrong} patient(s) do not carry the flags their scenario should raise.")
    if checked:
        print(f"\nAll {checked} patients created now carry the flags their scenario should raise.")
    else:
        print(f"\nEvery patient was already there, so none was created or checked.")


if __name__ == "__main__":
    main()
