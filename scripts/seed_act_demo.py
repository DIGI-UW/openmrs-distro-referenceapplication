#!/usr/bin/env python3
"""
Seed an ACT 3 stack with demo data: test users, two research studies and the 26 patients of
docs/demo-data-2026-10-20.md, each built around one edge case (overdue, never started, on hold,
lost to follow-up, warfarin and INR, waiting list, screen positive, duplicates, deaths, studies), then a
population of 180 more generated patients across eight health centres and four cardiac clinics, so the Dashboard
and Reports have real distributions: registrations over 18 months, screening and how each case was found,
diagnoses, statuses, prophylaxis adherence from good to stopped, procedures, warfarin and INR, pregnancies and
admissions. The population comes from a fixed random seed, so every run makes the same people.

Safe to run again. Dates are relative to the day it runs, so a fresh run gives the same scenarios.

  python3 scripts/seed_act_demo.py                 # seed http://localhost (skips if already seeded)
  python3 scripts/seed_act_demo.py --reset         # void the seeded patients, then seed afresh
  python3 scripts/seed_act_demo.py --reset-only    # only void the seeded patients
  python3 scripts/seed_act_demo.py --population 0  # only the 26 scenarios (default --population 180)
  python3 scripts/seed_act_demo.py --url https://demo.example.org --user admin --password ...

Test users (password Act12345 unless --user-password): cc community clinician, dc data clerk,
cl clinician, sa site administrator (Acimi HCIII), ia instance administrator, ga global administrator.
Needs only the Python 3 standard library.
"""
import argparse, base64, datetime, json, sys, urllib.error, urllib.request

ARGS = None

def call(method, path, body=None, user=None, pw=None):
    req = urllib.request.Request(ARGS.url.rstrip("/") + "/openmrs/ws/rest/v1" + path, method=method)
    token = base64.b64encode(f"{user or ARGS.user}:{pw or ARGS.password}".encode()).decode()
    req.add_header("Authorization", "Basic " + token)
    req.add_header("Accept", "application/json")
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data, timeout=180) as response:
            raw = response.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            err = json.loads(raw).get("error", {})
        except Exception:
            err = {"message": raw[:300]}
        return {"__error__": e.code, "message": err.get("message"),
                "detail": str(err.get("globalErrors") or err.get("fieldErrors") or "")[:400]}

def must(result, what):
    if isinstance(result, dict) and "__error__" in result:
        print(f"FAILED {what}: {result}")
        sys.exit(1)
    return result

TODAY = datetime.date.today()
def D(n): return TODAY - datetime.timedelta(days=n)
def iso(d, hour=9): return f"{d.isoformat()}T{hour:02d}:00:00.000+0300"

ACIMI="73e6a40f-b1b2-5dcc-883e-70ac8a8f4703"; AKUNA="9aacad7c-bbc5-5669-977d-4c20e31aa6e8"; KITMAT="96f0e6ec-228c-58a2-940d-d1be2f9cbe1c"
UHI="5b5f6fb2-eb04-5d3b-a9cd-acea2027f5ad"; GULU="029d10e9-db48-5f6f-a8e8-74a647c66455"; LIRA="292284c9-3d3a-57cc-bd4e-e7f6431460bd"
ACTID="240f85fa-46e1-540e-9234-2796c623f7ea"; IDSRC="f1c4a7be-160e-5d9b-ae5a-345cb15186dc"; NATID="fdd6f720-743b-57fc-915a-87c0f571097b"
SELF="edebe52c-de16-5ba7-ad1c-9f0d6a2bb323"; GUARDIAN="3667d093-11ca-5dc5-8734-ec2dec08fcec"
YES="1065AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"; NO="1066AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
VT="bf86d5a7-9511-5c11-acb1-8f8718775cd5"; PROV="ba1e27d3-2c89-49fc-9851-3b509abcce93"; ROLE="240b26f9-dd88-4172-823d-4a8bfeb7841f"
AT=dict(pcc="695f2990-236f-5d7c-b8aa-ddbdb22400f4", cardiac="fe261119-2911-5b36-be40-8f9827826987", consent="e15bf9b7-249e-5d75-907d-937b8d9b0c46",
        consentDate="b29617e3-c49e-5893-8dc7-e06b125a0264", consentRel="23f7173b-bec5-5fac-81db-cbbb1046e05e", consentPerson="a8ff9d47-dcdc-579a-a9b3-1d883c4d344b",
        phone="542c6fd2-05ca-53e3-a4f5-cd23bc1abd8f", phoneOwner="ea3cb7ae-ffbe-5aee-8343-44977898f675", optIn="a78f6ae3-faec-5db8-9493-53877985ca7f")
FORM=dict(pi="a6646c51-130d-3b59-a442-959bea93487d", consult="4b063fc7-996f-3001-8500-8940e201be8f", bpg="0119d2e6-e2e1-391c-9b88-d59a10b0780d",
          oral="ba29e982-ce18-302a-9fc4-d4b2c3983465", inr="fe4848b2-a0b4-329f-a6a3-6ffc298e09a9", proc="bf762810-2bf1-3ca3-bdbe-8bd71fd5d59a",
          echo="88e54fb0-1243-3f7a-b925-f64648ca6635", preg="a4f9103b-8396-3087-8cf4-e91610ec7c2d", hosp="949d365b-95ef-3ec9-bd8a-effcf1e6696c")
ETYPE={}
C=dict(diagGroup="594b4495-36dc-52a6-9810-15a9e2e2dcb9", category="1a5aa050-661d-5e89-95d7-c1eba476df22", catRHD="4e529463-2036-5327-ad69-7cbd39df86a1", catCHD="365e75bb-35bc-503f-b8db-53bea2528d1b",
 detailsRHD="cfe17bb5-4a76-5f3a-9e1c-7b1e9b84a8e3", rhdA="1c4a12e2-1f80-5176-bd8f-0e3a0154ce0b", rhdB="5e019f88-6b33-5749-8804-d9686ae680d5", rhdCD="8c2f337a-99b3-5f76-8312-1cee4336309c",
 active="b1b5d279-8013-5ae4-83a7-0f2bd9bc8457", started="62321320-695e-5319-a306-40dfd6ad94b7",
 screenPos="82a5fbb5-038d-57b8-82d1-3fd0ac95673d", screenDate="96d6d328-87ba-5a2e-bb71-2d1cd73b3e90", screenSite="a5be20e6-88c0-42b0-9557-54771e06e644", screenFU="c25c84d9-1f23-4426-8d43-ad1e3829cbb7", echoBooked="6bcba113-f828-4635-9c47-bcf14b605532",
 consultDate="c3edefd2-5777-5084-b01e-fd4ca0e40162", nyha="2f51b894-383c-53bb-9997-583e9761d132", nyha1="9b905331-5cd5-5624-9f02-a88efaf771d6", nyha2="e4a2da4b-cca3-5bd6-bfc6-8e206dc339e9", nyha3="fea16333-1c36-5478-9ebf-ca9f6201f753",
 sap="668e0221-8b41-5669-9ad8-78e193d42494", q28="50be4b26-6c5b-5aaa-9254-3bfd313b4522", q21="2f3ee632-dd14-51b0-a4ec-de10e7958019", q14="91230c88-6a90-5d45-af50-fa6155fe5dd7", oralPenV="b9884219-358a-594b-94f5-f8a8863a25f3", oralEry="fb8b6676-689b-5daa-83f7-1456210c587f",
 dateStarted="5bcc7d12-b279-5955-815c-090a1f392071", dateStopped="d75edc42-3213-5a06-9228-4e5735b9594b", reasonStopped="fa21e431-e64d-5493-b18c-9a1eaf7ee16a", anaph="148888AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
 med="0734567e-4f0a-5090-9d74-b953921a30e6", warfarin="5e97fe35-58df-4925-bba7-7c49d75268a1", aspirin="71617AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", dosing="8879385e-d35e-50a3-a3d0-4333d95d4878",
 rec="ce93d393-1df5-587f-bf11-c373eac2ccf4", procType="3a576b80-744a-59ee-9515-d9fdca06f3d7", surgery="aa5fefb0-cf61-5f36-82e6-31dbbdf3f616", mvr="7af8595d-407e-5705-bd8a-812735e2f188",
 urgency="7b8eda07-34b6-55f2-ab6c-1b295f41918b", emergent="1fe15210-4490-58b0-a38c-bb0386e98482", urgent="33bf504a-15f2-5504-9bdc-ddded0b5eb00", completed="1632f8dc-195d-5d67-a52e-6c7a057cb536", contraMech="b393b00a-8641-5013-bcc7-dec1334a1252",
 nextAmt="ba4b8a87-2ce8-559e-9a30-45504a9b6c1f", nextPeriod="1732AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", months="1074AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
 injDate="183fb30e-b861-5b7c-806f-7118a40f2b51", dose="6a52b6aa-2427-4fa2-93cb-18956f50c16a", dose12="0cd38c13-17ac-48da-a946-1b21789e5027", tolerance="9684b2da-a340-5a70-b8c5-114ba0b1ebcc", tolerated="384326ed-1860-5756-b6d2-9c05b7952b32", bpgGiven="b3aad474-e04e-407c-9fbd-28e25a394f27",
 lateWhy="f7cbfcdc-58bb-5e85-86ab-ffce26a08615", transport="56fb6a9e-a90e-5bad-b701-88199d74f7a9", stockout="76cd4ace-1a6f-5e2c-b69f-d9dfc157afa2", facility="01e6dd39-b8ba-5b0a-bcd7-6b8d5973c1bc",
 adhDate="99512ab5-208e-5c37-8f7b-8f72abe2a0db", adhEst="8edff8dc-4af6-5d0f-bf1d-8e349c7a1b15", adhBasis="4313005d-d5b2-5d20-bf33-39aab1bf90c0", patientReport="1795c346-64df-54e3-aca1-a2855c8cc740", pillCount="204eaab6-8380-5d21-8b4a-a066eb17dcca", rxDur="cd03af00-de81-5c08-9a02-92f95c00e1ce", m1="87bdee8a-aaf8-56e7-9e34-2b668873787d",
 inrInd="6e8ed53f-15e6-5b00-9ed0-44b11bd2d638", mech="6f68aab6-4053-5476-9e12-b53b8709d87f", inrTarget="0778ce12-ddba-5e22-b5fd-92424e8747b4", t2535="ea841a3a-f9cb-5761-aac6-939ffb158d94", inrGroup="bd88ecf3-eac2-516a-8949-a93f90d6483b", inrDate="be9041b1-3948-5de0-a8b1-974e84b95715", inrVal="161482AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", nextInr="5096AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
 procDate="6cbb5176-144a-576b-9b3d-c9e9d6bc5f5a", discharge="d4317b82-5d37-5b59-ac32-4922f18cd65b", surgGroup="46f4af80-b783-59f4-beb1-81144ccf3084", mvrSurg="7af8595d-407e-5705-bd8a-812735e2f188", avr="cd9c582a-71f9-5441-97a8-6d50d7dc15c8", procOutcome="7a54d2d6-0d34-5e5d-b8e7-84a3cf7e9dca", dischargeHome="98ea6c57-5f77-549b-97ca-32604c5b9220", inHospDeath="2567da9f-864e-5408-b5ae-6686f80d0a99", dateOfDeath="07534416-c1c2-5772-83d8-76a429986ec0", perfusion="1c14c3f1-1532-51b0-8680-d761e7f25ad5", siteInf="15e033f6-704e-5bde-ac1d-b401294f416c", sepsis="86c4348a-1ec0-5ca2-a9a6-15f0f282cb95",
 echoDate="911be530-9457-54be-8515-4bbcdb832ccb", mr="d6ab05e2-1ece-5f8f-893d-74739aa66ce5", moderate="1499AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", severe="1500AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", ef="ed630fda-8451-53c0-929e-40eafd9bca9b", suitRepair="8d6e9ea5-aa27-57d6-bf43-198aca63a951",
 pregDate="f287af86-af54-5c49-b716-9737c4f022b1", edd="3ad5133c-80d0-5007-ba1a-c5be27cbb10c", gravidity="06ffd716-291b-5aa2-bb50-b029e58cdcae",
 admitDate="c437c2be-0520-5920-9bd7-26104bc229a4", admitReason="e60fcf3b-1057-5d1f-a8be-679411b48ba9", rhdHF="27f70da6-ee9e-5919-8b68-9977312f9ada", admitOutcome="ae69bb65-cd0a-5035-aee5-ba5521e7b889", dischargeDate="f17fbfad-6208-53ee-a97a-17583d2f6259")

def check():
    missing=[k for k,u in C.items() if "__error__" in call("GET",f"/concept/{u}?v=custom:(uuid)")]
    for k,u in FORM.items():
        f=call("GET",f"/form/{u}?v=custom:(uuid,encounterType:(uuid))")
        if "__error__" in f: missing.append("form:"+k)
        else: ETYPE[k]=f["encounterType"]["uuid"]
    return missing

LOG=[]; PATIENTS={}; VISITS={}
def obs(c,v): return {"concept":C.get(c,c),"value":(C.get(v,v) if isinstance(v,str) else v)}
def dobs(c,d): return {"concept":C[c],"value":iso(d)}
def tobs(c,text): return {"concept":C.get(c,c),"value":text}
def grp(c,members): return {"concept":C[c],"groupMembers":members}
def enc(pat, kind, day, obsl, loc=ACIMI):
    # One visit per patient and day: OpenMRS refuses overlapping visits.
    visit=VISITS.get((pat,day))
    if not visit:
        visit=must(call("POST","/visit?v=custom:(uuid)",{"patient":pat,"visitType":VT,"location":loc,"startDatetime":iso(day,8),
                                          "stopDatetime":iso(day,17)}),f"visit for {kind}")
        VISITS[(pat,day)]=visit
    e=call("POST","/encounter?v=custom:(uuid)",{"patient":pat,"encounterType":ETYPE[kind],"form":FORM[kind],"location":loc,"encounterDatetime":iso(day),"visit":visit["uuid"],
        "encounterProviders":[{"provider":PROV,"encounterRole":ROLE}],"obs":obsl})
    must(e, f"{kind} encounter on {day}")
    return e["uuid"]
def patient(key,given,family,gender,bdate,consent=YES,consentDate=None,pcc=ACIMI,cardiac=UHI,rel=SELF,guardian=None,phone=None,optIn=None,nationalId=None,quiet=False):
    if consentDate is None and consent==YES: consentDate=D(30)
    ident=call("POST",f"/idgen/identifiersource/{IDSRC}/identifier",{})["identifier"]
    attrs=[{"attributeType":AT["pcc"],"value":pcc},{"attributeType":AT["cardiac"],"value":cardiac}]
    if consent: attrs.append({"attributeType":AT["consent"],"value":consent})
    if consentDate: attrs.append({"attributeType":AT["consentDate"],"value":consentDate.isoformat()})
    if rel: attrs.append({"attributeType":AT["consentRel"],"value":rel})
    if guardian: attrs.append({"attributeType":AT["consentPerson"],"value":guardian})
    if phone: attrs+=[{"attributeType":AT["phone"],"value":phone},{"attributeType":AT["phoneOwner"],"value":guardian or f"{given} {family}"}]
    if optIn: attrs.append({"attributeType":AT["optIn"],"value":optIn})
    ids=[{"identifier":ident,"identifierType":ACTID,"location":pcc,"preferred":True}]
    if nationalId: ids.append({"identifier":nationalId,"identifierType":NATID,"location":pcc,"preferred":False})
    p=call("POST","/patient?v=custom:(uuid)",{"person":{"names":[{"givenName":given,"familyName":family}],"gender":gender,"birthdate":bdate,
        "addresses":[{"country":"Uganda","stateProvince":"Northern Region","countyDistrict":"Gulu","cityVillage":"Laroo"}],"attributes":attrs},"identifiers":ids})
    must(p, f"patient {given} {family}")
    PATIENTS[key]=p["uuid"]
    if not quiet:
        LOG.append((f"{given} {family}",ident,p["uuid"])); print(f"{ident} {given} {family}")
    return p["uuid"]
def PI(pat, day, details="rhdB", cat="catRHD", screen=None, loc=ACIMI):
    o=[]
    if screen:
        o+=[obs("screenPos",YES),dobs("screenDate",screen),tobs("screenSite","Gulu Primary School"),obs("screenFU","echoBooked")]
    if cat:
        m=[obs("category",cat),obs("active",YES),dobs("started",day)]
        if details: m.append(obs("detailsRHD",details))
        o.append(grp("diagGroup",m))
    return enc(pat,"pi",day,o,loc)
def consult(pat, day, regimen="q28", start=None, extra=None, nextMonths=6, loc=UHI, nyha="nyha1", nyha_concept=None):
    o=[dobs("consultDate",day),obs("nyha",nyha_concept or nyha),obs("nextAmt",nextMonths),obs("nextPeriod","months")]
    if regimen: o.append(grp("sap",[obs("sap",regimen),dobs("dateStarted",start or day)]))
    return enc(pat,"consult",day,o+(extra or []),loc)
def bpg(pat, day, loc=ACIMI, late=None):
    o=[dobs("injDate",day),obs("dose","dose12"),obs("tolerance","tolerated"),obs("bpgGiven",YES),obs("facility",loc)]
    if late: o.append(obs("lateWhy",late))
    return enc(pat,"bpg",day,o,loc)
def bpg_anaph(pat, day, loc=ACIMI): return enc(pat,"bpg",day,[obs("tolerance","anaph"),obs("bpgGiven",NO)],loc)
def oral(pat, day, est=100, basis=("patientReport",), loc=ACIMI):
    return enc(pat,"oral",day,[dobs("adhDate",day),obs("adhEst",est),obs("rxDur","m1")]+[obs("adhBasis",b) for b in basis],loc)
def echo(pat, day, mrv="moderate", ef=60, repair=YES): return enc(pat,"echo",day,[dobs("echoDate",day),obs("mr",mrv),obs("ef",ef),obs("suitRepair",repair)],UHI)

def seed():
    p=patient("abebe","Abebe","Okot","M","2010-05-01",phone="+256772000101",guardian="Rose Okot",rel=GUARDIAN); PI(p,D(100)); consult(p,D(90)); echo(p,D(90)); [bpg(p,D(n)) for n in (90,62,40)]
    p=patient("grace","Grace","Akello","F","2012-03-02",pcc=AKUNA); consult(p,D(60)); [bpg(p,D(n),AKUNA) for n in (60,36)]
    p=patient("sarah","Sarah","Apio","F","2008-07-07"); PI(p,D(130)); consult(p,D(120),"oralPenV"); oral(p,D(90),90); oral(p,D(60),50)
    p=patient("faith","Faith","Auma","F","2011-01-15",phone="+256701000104",rel=GUARDIAN,guardian="Mary Auma"); PI(p,D(70)); consult(p,D(60)); bpg(p,D(58)); bpg_anaph(p,D(2))
    p=patient("samuel","Samuel","Ocen","M","2013-09-09"); PI(p,D(22))
    p=patient("ruth","Ruth","Lamwaka","F","1995-02-02",cardiac=GULU,phone="+256782000106"); PI(p,D(80),details="rhdCD")
    consult(p,D(70),nyha="nyha3",extra=[grp("rec",[obs("procType","surgery"),obs("rec","mvr"),obs("urgency","urgent"),obs("completed",NO)]),obs("contraMech",NO)],loc=GULU); echo(p,D(70),"severe",48,YES); [bpg(p,D(n)) for n in (70,42,14)]
    p=patient("joan","Joan","Adong","F","2000-04-04",pcc=KITMAT); PI(p,D(410)); consult(p,D(400),"oralPenV"); oral(p,D(330),100,loc=KITMAT); oral(p,D(300),90,loc=KITMAT)
    p=patient("peter","Peter","Opio","M","2005-05-05",phone="+256752000108"); PI(p,D(410)); consult(p,D(400)); bpg(p,D(400)); bpg(p,D(372)); bpg_anaph(p,D(345))
    consult(p,D(250),regimen=None,extra=[grp("sap",[obs("sap","q28"),dobs("dateStarted",D(400)),dobs("dateStopped",D(250)),obs("reasonStopped","anaph")]),grp("sap",[obs("sap","oralEry"),dobs("dateStarted",D(250))])])
    for n in range(220,20,-30): oral(p,D(n),100)
    oral(p,D(5),95,basis=("patientReport","pillCount"))
    p=patient("mary","Mary","Adong","F","1990-06-06",phone="+256772000109"); PI(p,D(400),details="rhdCD")
    consult(p,D(50),nyha="nyha2",extra=[grp("med",[obs("med","warfarin"),tobs("dosing","5 mg daily"),dobs("dateStarted",D(50))]),grp("med",[obs("med","aspirin"),dobs("dateStarted",D(50))])])
    enc(p,"inr",D(45),[obs("inrInd","mech"),obs("inrTarget","t2535"),grp("inrGroup",[dobs("inrDate",D(45)),obs("inrVal",2.4)]),dobs("nextInr",D(10))],UHI); [bpg(p,D(n)) for n in (50,22)]
    patient("esther","Esther","Nambi","F","2001-08-08",consentDate=False)
    p=patient("james","James","Okello","M","2012-11-11",rel=GUARDIAN,guardian="Peter Okello",phone="+256701000111"); PI(p,D(230)); consult(p,D(220)); [bpg(p,D(n)) for n in range(220,0,-28)]
    p=patient("hellen","Hellen","Akot","F","2013-05-20",pcc=AKUNA,cardiac=GULU,rel=GUARDIAN,guardian="Grace Akot",phone="+256774000112"); PI(p,D(0),screen=D(0),loc=AKUNA); consult(p,D(0),loc=GULU); echo(p,D(0)); bpg(p,D(0),AKUNA)
    p=patient("lucy","Lucy","Aber","F","2014-02-20",rel=GUARDIAN,guardian="Agnes Aber"); PI(p,D(10),cat=None,screen=D(35))
    p=patient("betty","Betty","Amony","F","1992-12-12"); PI(p,D(110),details="rhdCD"); consult(p,D(100))
    enc(p,"proc",D(50),[dobs("procDate",D(50)),grp("surgGroup",[obs("surgGroup","mvrSurg")]),obs("procOutcome","dischargeHome"),dobs("discharge",D(45)),obs("siteInf",NO),obs("sepsis",NO)],UHI); [bpg(p,D(n)) for n in (100,72,44,16)]
    p=patient("noah","Noah","Komakech","M","2009-09-19",consent=NO,consentDate=False,rel=None); PI(p,D(20)); consult(p,D(15)); bpg(p,D(15))
    p=patient("zara","Zara","Lakot","F","2003-03-03",pcc=AKUNA); PI(p,D(310)); consult(p,D(300),"oralPenV")
    p=patient("kato","Kato","Odong","M","2004-04-04",pcc=AKUNA); PI(p,D(310)); consult(p,D(300))
    p=patient("daniel","Daniel","Opio","M","2007-10-10",phone="+256783000117"); PI(p,D(200)); consult(p,D(190),"q21")
    for n,why in ((190,None),(160,"transport"),(130,"stockout"),(95,"transport"),(60,None),(30,"transport"),(8,None)): bpg(p,D(n),late=why)
    p=patient("agnes","Agnes","Achola","F","1997-01-30",optIn=YES,phone="+256772000118",nationalId="CF970130ACHOLA"); PI(p,D(150),details="rhdA"); consult(p,D(140),"q14"); [bpg(p,D(n)) for n in range(140,8,-14)]
    p=patient("brian","Brian","Oyet","M","2006-06-16",optIn=YES); PI(p,D(120)); consult(p,D(110)); [bpg(p,D(n)) for n in (110,82,54,26)]
    p=patient("isaac","Isaac","Okumu","M","1980-03-03"); PI(p,D(200),details="rhdCD"); consult(p,D(190),nyha="nyha3",extra=[grp("rec",[obs("procType","surgery"),obs("rec","mvr"),obs("urgency","emergent"),obs("completed",YES)])]); bpg(p,D(190))
    enc(p,"proc",D(100),[dobs("procDate",D(100)),grp("surgGroup",[obs("surgGroup","avr")]),obs("procOutcome","inHospDeath"),dobs("dateOfDeath",D(98)),obs("perfusion",YES),obs("siteInf",NO),obs("sepsis",YES)],UHI)
    p=patient("rose","Rose","Atim","F","1975-07-07",optIn=YES,cardiac=GULU); PI(p,D(300),details="rhdCD"); consult(p,D(290),nyha="nyha3",loc=GULU); [bpg(p,D(n)) for n in (290,262,234)]
    p=patient("christine","Christine","Lamaro","F","2002-09-09",phone="+256701000122"); PI(p,D(260)); consult(p,D(250)); [bpg(p,D(n)) for n in range(250,0,-28)]
    enc(p,"preg",D(200),[dobs("pregDate",D(200)),dobs("edd",D(40)),obs("gravidity",1)],UHI)
    p=patient("moses1","Moses","Okello","M","2011-04-21"); PI(p,D(30)); consult(p,D(25)); bpg(p,D(25))
    p=patient("moses2","Moses","Okello","M","2011-04-21",pcc=KITMAT); PI(p,D(12),loc=KITMAT)
    p=patient("denis","Denis","Ojok","M","1986-02-14",cardiac=LIRA,pcc=KITMAT); PI(p,D(180)); consult(p,D(170),nyha="nyha2",loc=LIRA)
    enc(p,"hosp",D(40),[dobs("admitDate",D(40)),obs("admitReason","rhdHF"),obs("admitOutcome","dischargeHome"),dobs("dischargeDate",D(33))],LIRA); [bpg(p,D(n),KITMAT) for n in range(170,0,-28)]


# ---------------------------------------------------------------------------------------------------------------------
# The population: about 180 more patients across eight health centres and their cardiac clinics, so the Dashboard,
# Reports and lists have real distributions to show. Generated from a fixed random seed with fixed birth dates, so every
# run makes the same people and --reset finds them again; visit dates are relative to the day it runs.
# ---------------------------------------------------------------------------------------------------------------------
import random, threading
from concurrent.futures import ThreadPoolExecutor

CLINIC_PAIRS = [  # (primary care clinic, its cardiac clinic, weight)
    ("73e6a40f-b1b2-5dcc-883e-70ac8a8f4703", UHI, 5), ("9aacad7c-bbc5-5669-977d-4c20e31aa6e8", UHI, 4),
    ("0786e91b-a732-5f1d-a904-c7648430962d", GULU, 3), ("2b40aa4f-4482-5f6c-a36b-d4ceb8fcf160", GULU, 3),
    ("96f0e6ec-228c-58a2-940d-d1be2f9cbe1c", "f8cf700a-2e5d-594e-86e0-061fedae2c6d", 3), ("a977debf-e337-54af-ac88-dc99d137eb2d", "f8cf700a-2e5d-594e-86e0-061fedae2c6d", 2),
    ("24aa669e-7b7b-5bc8-84e6-72c4184414d0", LIRA, 2), ("c51207a0-7473-5d26-a5e3-8f96778c4d4d", "b59eab2d-ed25-5a42-9e60-7c4d8b395fac", 2)]
GIVEN_F = ["Akello","Apio","Atim","Auma","Adong","Lamwaka","Aber","Amony","Lakot","Achola","Lamaro","Akot","Nambi","Aciro","Ayaa",
           "Abalo","Anena","Acan","Akumu","Aol","Ajok","Alanyo","Akidi","Laker","Atoo","Aryemo","Kidega","Abwola"]
GIVEN_M = ["Okot","Opio","Ocen","Okello","Odong","Oyet","Okumu","Ojok","Komakech","Otim","Ochieng","Olweny","Onen","Obol","Odoch",
           "Ocaya","Opiyo","Ogwang","Oryem","Kilama","Ojara","Oloya","Ongom","Abonga","Okwir","Ochola","Owor","Lutwama"]
FAMILY = ["Acaye","Ayella","Oketch","Lagu","Odongo","Akena","Obita","Olanya","Ongwen","Oringa","Lukwiya","Okeny","Onyango",
          "Oweka","Ogen","Aboda","Labeja","Okema","Langoya","Amone","Ochan","Oyoo","Kitara","Lalobo","Anywar","Okidi"]
DETECTED = {"school": "5b7d5eb4-4c6a-52cb-95f3-ac5033708fc9", "community": "24b5320c-bf9b-5c3b-a43c-d700cc1134e1",
            "clinical": "28452410-f2a2-5ad7-9590-43e47df1d254", "pregnancy": "06d80315-eaf9-5c71-a4c7-cb9759f93fe1",
            "facility": "9e861499-cebe-5371-a893-5747f365da73", "coincidental": "fdecbe0d-8c8d-545d-a3b8-b2fd31704db1"}
STATE = {"Deceased": "5df302f6-cd64-50ea-b428-a89c211977a6", "Voluntary inactivity": "407a4a4d-bc47-51e2-aa48-32e9a8d5634f",
         "Confirmatory echo normal": "04d752ed-94cc-52eb-b9fb-ef74ac112cdc", "Physical relocation": "dcefbf92-d833-5333-93b0-41b72a84459e",
         "Lost to follow-up": "560d1825-63f8-5903-a891-5c45be204e68", "CHD spontaneous resolution": "fb7baa98-7bb2-52ce-8547-bd2350cfa768"}
CAT = {"rhd": "4e529463-2036-5327-ad69-7cbd39df86a1", "chd": "365e75bb-35bc-503f-b8db-53bea2528d1b",
       "other": "7c42e9be-5828-5d4c-8a6e-f713efe8a945", "normal": "1115AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"}
DETAILS = {"rhd": ("cfe17bb5-4a76-5f3a-9e1c-7b1e9b84a8e3", ["1c4a12e2-1f80-5176-bd8f-0e3a0154ce0b", "5e019f88-6b33-5749-8804-d9686ae680d5", "8c2f337a-99b3-5f76-8312-1cee4336309c"]),
           "chd": ("d3f6e1a2-9c5b-5e84-8f2d-1a6c7b9e0d4f", ["148196AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "f43e9a0e-38a2-58dc-8f6f-42bd5e1db86c", "6f778415-8d94-57cd-81f4-4a0dfedcd90c"]),
           "other": ("b7a2c4d8-5e91-5f3a-8c6d-2b9e4f7a1c0d", ["b0d85202-3ebb-5f7f-bd07-4d1778e68784", "117386AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "b6946c83-6e27-5f91-85ad-2ae2d1ab5593"]),
           "normal": ("e9f3a5c7-6b82-5d4e-9f1a-3c7d8e2b5f4a", ["f48b4ebc-17ef-5747-bc7f-545b8e61e851"])}
NYHA = ["9b905331-5cd5-5624-9f02-a88efaf771d6", "e4a2da4b-cca3-5bd6-bfc6-8e206dc339e9", "fea16333-1c36-5478-9ebf-ca9f6201f753", "77e49ccb-efb0-5364-8dd2-d9e2a5e24924"]
FOLLOW_UP = ["1035a94f-d8c1-4f0c-b376-5f6c5976b737", "6bcba113-f828-4635-9c47-bcf14b605532", "437bd172-c32b-430f-a9d1-acf20e398022"]
URGENCY = ["1fe15210-4490-58b0-a38c-bb0386e98482", "33bf504a-15f2-5504-9bdc-ddded0b5eb00", "2666bf97-7400-57c7-b535-7903e22ced34"]
PROCEDURES = [("surgery", "7af8595d-407e-5705-bd8a-812735e2f188", "7af8595d-407e-5705-bd8a-812735e2f188"),   # mitral valve repair/replacement
              ("91a4d13f-4bc8-54b0-a107-f4ab84cb7d60", "af9429ff-1b76-55f3-81ca-a9f775d93fb4", None),           # mitral balloon valvuloplasty
              ("surgery", "cd9c582a-71f9-5441-97a8-6d50d7dc15c8", "cd9c582a-71f9-5441-97a8-6d50d7dc15c8")]   # aortic valve repair/replacement
LATE = ["56fb6a9e-a90e-5bad-b701-88199d74f7a9", "1e628c9a-0f9c-56ba-a7f8-61da24a538e8", "63dc954c-a3ab-58ec-96fc-c1801ef8aca2",
        "2cfca4a1-4985-5da9-91cb-e9478497e927", "76cd4ace-1a6f-5e2c-b69f-d9dfc157afa2"]
INR_TARGETS = [("d894d89a-04bd-5fc0-91a0-5dc3ddd8802b", 2.0, 3.0), ("ea841a3a-f9cb-5761-aac6-939ffb158d94", 2.5, 3.5)]
DETECTED_CONCEPT = "955632a1-82f7-5b84-a341-de85f95588d1"
REGISTRY = "7d73e143-a550-5a9d-aecd-dd771add098d"
POPULATION_SEED = 2026
REFERENCE_YEAR = 2026   # birth dates are fixed from this, so a later run still finds the same people
_lock = threading.Lock()

def weighted(rng, pairs):
    total = sum(w for _, w in pairs); x = rng.uniform(0, total)
    for value, w in pairs:
        x -= w
        if x <= 0:
            return value
    return pairs[-1][0]

def population_people(n):
    """The population's people, the same list every run: who they are and what happens to them."""
    rng = random.Random(POPULATION_SEED)
    people, used = [], set()
    for i in range(n):
        female = rng.random() < 0.62
        while True:
            given = rng.choice(GIVEN_F if female else GIVEN_M); family = rng.choice(FAMILY)
            if (given, family) not in used:
                used.add((given, family)); break
        age = weighted(rng, [(rng.randint(5, 9), 2), (rng.randint(10, 19), 6), (rng.randint(20, 39), 4), (rng.randint(40, 65), 1)])
        birth = datetime.date(REFERENCE_YEAR - age, rng.randint(1, 12), rng.randint(1, 28))
        pcc, cardiac, _ = weighted(rng, [((a, b, w), w) for a, b, w in CLINIC_PAIRS])
        detected = weighted(rng, [("school", 3), ("community", 2), ("clinical", 4), ("facility", 1), ("coincidental", 1)]
                            + ([("pregnancy", 1)] if female and 18 <= age <= 40 else []))
        screened = detected in ("school", "community", "facility")
        diagnosis = weighted(rng, [("rhd", 7), ("chd", 1), ("other", 1), ("normal", 1)] if not screened
                             else [("rhd", 5), ("normal", 3), ("chd", 1), (None, 2)])
        stage = weighted(rng, [(0, 3), (1, 4), (2, 3)]) if diagnosis == "rhd" else 0
        people.append(dict(i=i, given=given, family=family, gender="F" if female else "M", birth=birth, age=age, pcc=pcc,
                           cardiac=cardiac, detected=detected, screened=screened, diagnosis=diagnosis, stage=stage,
                           registered=rng.randint(15, 540), rng_seed=rng.randint(0, 10**9)))
    return people

def population_seeded_names(n):
    return [(p["given"], p["family"], p["birth"].isoformat()) for p in population_people(n)]

def registry_enrolment(patient_uuid):
    for e in call("GET", f"/programenrollment?patient={patient_uuid}&v=custom:(uuid,program:(uuid),voided)").get("results", []):
        if e["program"]["uuid"] == REGISTRY and not e.get("voided"):
            return e["uuid"]
    return None

def seed_person(p):
    rng = random.Random(p["rng_seed"])
    reg = D(p["registered"])
    key = f"pop{p['i']}"
    pat = patient(key, p["given"], p["family"], p["gender"], p["birth"].isoformat(), pcc=p["pcc"], cardiac=p["cardiac"],
                  consentDate=reg if rng.random() < 0.93 else False,
                  rel=GUARDIAN if p["age"] < 18 else SELF, guardian=f"{rng.choice(GIVEN_F)} {p['family']}" if p["age"] < 18 else None,
                  phone=f"+2567{rng.randint(0, 9)}{rng.randint(1000000, 9999999)}" if rng.random() < 0.8 else None,
                  optIn=YES if rng.random() < 0.3 else None, quiet=True)
    enrolment = registry_enrolment(pat)
    if enrolment:
        must(call("POST", f"/programenrollment/{enrolment}?v=custom:(uuid)", {"dateEnrolled": iso(reg, 8)}), "registration date")
    # Patient Information: how the case was found, the screen, and the diagnosis after the echo.
    pi = [obs(DETECTED_CONCEPT, DETECTED[p["detected"]])]
    if p["screened"]:
        screen = reg + datetime.timedelta(days=-rng.randint(0, 20))
        pi += [obs("screenPos", YES), dobs("screenDate", screen),
               tobs("screenSite", rng.choice(["Laroo Primary School", "Gulu Public School", "Pece Primary School", "Bardege outreach", "Kitgum market outreach"])),
               obs("screenFU", rng.choice(FOLLOW_UP))]
    if p["diagnosis"]:
        concept, answers = DETAILS[p["diagnosis"]]
        detail = answers[p["stage"]] if p["diagnosis"] == "rhd" else rng.choice(answers)
        pi.append(grp("diagGroup", [obs("category", CAT[p["diagnosis"]]), obs("active", YES), dobs("started", reg), {"concept": concept, "value": detail}]))
    enc(pat, "pi", reg, pi, p["pcc"])
    if p["diagnosis"] in ("rhd", "chd", "other"):
        echo(pat, reg + datetime.timedelta(days=rng.randint(0, 25)), ["moderate", "moderate", "severe"][min(p["stage"], 2)] if p["diagnosis"] == "rhd" else "moderate",
             rng.randint(35, 68), YES if p["stage"] == 2 else NO)
    status = None
    if p["diagnosis"] == "normal":
        status = "Confirmatory echo normal" if rng.random() < 0.7 else None
    elif p["diagnosis"] == "chd" and rng.random() < 0.2:
        status = "CHD spontaneous resolution"
    elif rng.random() < 0.13:
        status = rng.choice(["Lost to follow-up", "Lost to follow-up", "Physical relocation", "Voluntary inactivity", "Deceased"])
    if p["diagnosis"] == "rhd":
        seed_care(pat, p, rng, reg, status)
    if status:
        end = D(rng.randint(5, max(6, p["registered"] - 10)))
        if enrolment:
            must(call("POST", f"/programenrollment/{enrolment}?v=custom:(uuid)", {"dateCompleted": iso(end), "states": [{"state": STATE[status], "startDate": iso(end)}]}), f"status {status}")
        if status == "Deceased":
            must(call("POST", f"/person/{pat}?v=custom:(uuid)", {"dead": True, "deathDate": iso(end), "causeOfDeathNonCoded": rng.choice(
                ["Heart failure", "Stroke", "Infective endocarditis", "Malaria", "Complications after surgery"])}), "death")
    return status

def seed_care(pat, p, rng, reg, status):
    """Consultations, prophylaxis with a realistic adherence pattern, and for severe disease procedures, warfarin and INR."""
    first = reg + datetime.timedelta(days=rng.randint(3, 20))
    if first > TODAY:
        first = TODAY
    regimen = weighted(rng, [("q28", 13), ("q21", 1), ("oralPenV", 2), ("oralEry", 1), (None, 1)])
    nyha = NYHA[min(3, p["stage"] + weighted(rng, [(0, 5), (1, 3), (-1, 1)]))] if p["stage"] else NYHA[0]
    extra = []
    severe = p["stage"] == 2
    procedure = rng.choice(PROCEDURES) if severe and rng.random() < 0.7 else None
    done = procedure and rng.random() < 0.35
    if procedure:
        ptype, rec, _ = procedure
        extra.append(grp("rec", [obs("procType", ptype), obs("rec", rec), obs("urgency", rng.choice(URGENCY)), obs("completed", YES if done else NO)]))
    on_warfarin = done and procedure[2] is not None
    if on_warfarin:
        extra.append(grp("med", [obs("med", "warfarin"), tobs("dosing", rng.choice(["2.5 mg daily", "5 mg daily", "7.5 mg daily"])), dobs("dateStarted", first)]))
    months = rng.choice([3, 6, 6, 12])
    consult(pat, first, regimen=regimen, extra=extra, nextMonths=months, loc=p["cardiac"], nyha=None, nyha_concept=nyha)
    # Follow-up consultations for some, so reviews are on time, due or overdue.
    later = first + datetime.timedelta(days=months * 30 + rng.randint(-20, 40))
    if later < D(5) and rng.random() < 0.55:
        consult(pat, later, regimen=None, nextMonths=rng.choice([6, 12]), loc=p["cardiac"], nyha=None, nyha_concept=nyha)
    if done:
        when = first + datetime.timedelta(days=rng.randint(20, 120))
        if when < D(3):
            surgery = [obs("surgGroup", procedure[2])] if procedure[2] else []
            enc(pat, "proc", when, [dobs("procDate", when)] + ([grp("surgGroup", surgery)] if surgery else [])
                + [obs("procOutcome", "dischargeHome"), dobs("discharge", when + datetime.timedelta(days=rng.randint(4, 12))),
                   obs("siteInf", NO), obs("sepsis", NO), obs("perfusion", NO)], UHI)
    if on_warfarin:
        target, low, high = rng.choice(INR_TARGETS)
        test = first + datetime.timedelta(days=30)
        while test < D(10):
            value = round(rng.uniform(low - 0.9, high + 0.8), 1)
            gap = rng.choice([30, 30, 45, 60])
            enc(pat, "inr", test, [obs("inrInd", "mech"), obs("inrTarget", target), grp("inrGroup", [dobs("inrDate", test), obs("inrVal", value)]),
                                   dobs("nextInr", test + datetime.timedelta(days=gap))], p["cardiac"])
            test += datetime.timedelta(days=gap + rng.randint(-3, 25))
    if regimen in ("q28", "q21"):
        interval = 28 if regimen == "q28" else 21
        pattern = weighted(rng, [("good", 5), ("late", 3), ("stopped", 2), ("never", 1)])
        if status in ("Lost to follow-up", "Deceased"):
            pattern = "stopped"
        if pattern == "never":
            return
        day = first
        stop = D(rng.randint(60, 220)) if pattern == "stopped" else TODAY
        while day <= stop and day <= TODAY:
            late = pattern == "late" and rng.random() < 0.35
            if late:
                day += datetime.timedelta(days=rng.randint(4, 18))
                if day > TODAY:
                    break
            bpg(pat, day, p["pcc"], late=rng.choice(LATE) if late else None)
            day += datetime.timedelta(days=interval + rng.randint(-2, 2))
    elif regimen in ("oralPenV", "oralEry"):
        day = first + datetime.timedelta(days=rng.randint(0, 10))
        stop = D(rng.randint(40, 200)) if rng.random() < 0.3 else TODAY
        while day <= stop and day <= TODAY:
            oral(pat, day, weighted(rng, [(100, 5), (90, 3), (50, 2), (20, 1)]), loc=p["pcc"])
            day += datetime.timedelta(days=30 + rng.randint(-3, 12))
    if p["gender"] == "F" and 18 <= p["age"] <= 40 and rng.random() < 0.25:
        start = D(rng.randint(60, 260))
        enc(pat, "preg", start, [dobs("pregDate", start), dobs("edd", start + datetime.timedelta(days=rng.randint(150, 250))), obs("gravidity", rng.randint(1, 4))], p["cardiac"])
    if p["stage"] >= 1 and rng.random() < 0.15:
        admit = D(rng.randint(20, 300))
        enc(pat, "hosp", admit, [dobs("admitDate", admit), obs("admitReason", rng.choice(["rhdHF", "27f70da6-ee9e-5919-8b68-9977312f9ada", "490b4f2a-2421-56d3-b35e-c5c1c2e86ad2"])),
                                 obs("admitOutcome", "dischargeHome"), dobs("dischargeDate", admit + datetime.timedelta(days=rng.randint(3, 14)))], p["cardiac"])

def seed_population(n, workers):
    people = population_people(n)
    statuses = {}
    def one(p):
        try:
            status = seed_person(p)
            with _lock:
                statuses[status or "Active"] = statuses.get(status or "Active", 0) + 1
        except SystemExit:
            raise
        except Exception as e:
            print(f"  population patient {p['given']} {p['family']} failed: {e}")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, people))
    print(f"population: {n} patients, by registry status {dict(sorted(statuses.items()))}")

# The seeded patients, by name and birth date: how a rerun finds them to skip or void.
SEEDED = [("Abebe","Okot","2010-05-01"),("Grace","Akello","2012-03-02"),("Sarah","Apio","2008-07-07"),("Faith","Auma","2011-01-15"),
          ("Samuel","Ocen","2013-09-09"),("Ruth","Lamwaka","1995-02-02"),("Joan","Adong","2000-04-04"),("Peter","Opio","2005-05-05"),
          ("Mary","Adong","1990-06-06"),("Esther","Nambi","2001-08-08"),("James","Okello","2012-11-11"),("Hellen","Akot","2013-05-20"),
          ("Lucy","Aber","2014-02-20"),("Betty","Amony","1992-12-12"),("Noah","Komakech","2009-09-19"),("Zara","Lakot","2003-03-03"),
          ("Kato","Odong","2004-04-04"),("Daniel","Opio","2007-10-10"),("Agnes","Achola","1997-01-30"),("Brian","Oyet","2006-06-16"),
          ("Isaac","Okumu","1980-03-03"),("Rose","Atim","1975-07-07"),("Christine","Lamaro","2002-09-09"),("Moses","Okello","2011-04-21"),
          ("Denis","Ojok","1986-02-14")]

def seeded_patients():
    found = []
    for given, family, birthdate in SEEDED + population_seeded_names(ARGS.population):
        result = call("GET", f"/patient?q={urllib.request.quote(given + ' ' + family)}&v=custom:(uuid,person:(birthdate))&limit=50")
        for p in result.get("results", []):
            if (p["person"].get("birthdate") or "").startswith(birthdate):
                found.append(p["uuid"])
    return sorted(set(found))

def void_seeded():
    uuids = seeded_patients()
    for uuid in uuids:
        must(call("DELETE", f"/patient/{uuid}?reason=Reseeding%20ACT%20demo%20data"), f"void patient {uuid}")
    print(f"voided {len(uuids)} seeded patients")

STUDY_ID = "7840ba5d-d927-52d6-907b-dd070bea6626"
ROLES = {"cc":("Community Clinician","b9ab4b76-e7b9-46a7-b4ec-5b7fdd8fa540"), "dc":("Data Clerk","61e9bb28-11df-4df1-965d-11ef928d5239"),
         "cl":("Clinician","60625a0c-3cea-4fe5-b6ca-615c743ad9d4"), "sa":("Site Administrator","a1295a20-7273-4339-b5df-2f8a3a841c77"),
         "ia":("Instance Administrator","07a7affa-b7de-46d9-9faa-aac4ef2eccba"), "ga":("Global Administrator","c95f35f4-0422-46a3-a593-a6615fab90bc")}

def users():
    for username, (label, role) in ROLES.items():
        existing = call("GET", f"/user?username={username}&v=custom:(uuid)").get("results", [])
        if existing:
            print(f"user {username} exists")
            continue
        clinics = {"cc": ACIMI, "dc": ACIMI, "cl": UHI, "sa": ACIMI}.get(username)
        created = must(call("POST", "/user", {
            "username": username, "password": ARGS.user_password, "roles": [role],
            "person": {"names": [{"givenName": "Test", "familyName": label}], "gender": "F"},
            "userProperties": {"actcore.clinics": clinics} if clinics else {}}), f"user {username}")
        must(call("POST", "/provider", {"person": created["person"]["uuid"], "identifier": username}), f"provider {username}")
        print(f"user {username} ({label}) created")

def studies():
    existing = {s["name"]: s for s in must(call("GET", "/actcore/studies"), "studies").get("results", [])}
    for name in ("RHD Genetics Cohort", "Heart Health Cohort"):
        if name not in existing:
            must(call("POST", "/actcore/studies", {"name": name}), f"study {name}")
            print(f"study {name} created")
    return {s["name"]: s for s in must(call("GET", "/actcore/studies"), "studies")["results"]}

def enrol(patient, study, study_id, days_ago, location=UHI):
    return must(call("POST", "/programenrollment", {"patient": patient, "program": study["uuid"], "dateEnrolled": iso(D(days_ago)),
        "location": location, "attributes": [{"attributeType": STUDY_ID, "value": study_id}]}), f"enrolment {study_id}")

def research_and_deaths(all_studies):
    genetics, heart = all_studies["RHD Genetics Cohort"], all_studies["Heart Health Cohort"]
    enrol(PATIENTS["agnes"], genetics, "GEN-001", 50)
    brian = enrol(PATIENTS["brian"], heart, "HHC-014", 120)
    withdrawn = next(s for s in heart["states"] if "Voluntary" in s["name"])
    must(call("POST", f"/programenrollment/{brian['uuid']}", {"dateCompleted": iso(D(30)),
        "states": [{"state": withdrawn["uuid"], "startDate": iso(D(30))}]}), "Brian's withdrawal")
    enrol(PATIENTS["rose"], heart, "HHC-009", 200)
    # Marking Rose deceased closes her study enrolment (ACT Core); Isaac's death stays only on his procedure form.
    must(call("POST", f"/person/{PATIENTS['rose']}", {"dead": True, "deathDate": iso(D(6)),
        "causeOfDeathNonCoded": "Heart failure from severe mitral regurgitation"}), "Rose's death")
    print("study enrolments and Rose's death recorded")

def main():
    global ARGS
    parser = argparse.ArgumentParser(description="Seed an ACT 3 stack with demo users, studies and 26 scenario patients.")
    parser.add_argument("--url", default="http://localhost", help="the stack's base URL (default http://localhost)")
    parser.add_argument("--user", default="admin")
    parser.add_argument("--password", default="Admin123")
    parser.add_argument("--user-password", default="Act12345", help="password for the cc, dc, cl, sa, ia and ga test users")
    parser.add_argument("--reset", action="store_true", help="void the seeded patients first, then seed afresh")
    parser.add_argument("--reset-only", action="store_true", help="only void the seeded patients")
    parser.add_argument("--population", type=int, default=180, help="how many more generated patients to add (default 180, 0 for none)")
    parser.add_argument("--workers", type=int, default=6, help="patients seeded in parallel (default 6)")
    ARGS = parser.parse_args()

    if "__error__" in call("GET", "/session") or not call("GET", "/session").get("authenticated"):
        print(f"Cannot sign in to {ARGS.url} as {ARGS.user}")
        sys.exit(1)
    missing = check()
    if missing:
        print("These concepts or forms are missing on the server, so the seed would be wrong:", missing)
        sys.exit(1)
    if ARGS.reset or ARGS.reset_only:
        void_seeded()
        if ARGS.reset_only:
            return
    elif seeded_patients():
        print("Already seeded (Abebe Okot and the others exist). Run with --reset to void them and seed afresh.")
        return
    users()
    all_studies = studies()
    seed()
    research_and_deaths(all_studies)
    if ARGS.population:
        print(f"seeding a population of {ARGS.population} more patients across eight clinics ...")
        seed_population(ARGS.population, ARGS.workers)
    refresh = call("POST", "/actcore/refresh", {})
    print("flags and adherence refreshed" if "__error__" not in refresh else f"refresh failed: {refresh}")
    print(f"seeded {len(LOG)} patients:")
    for name, ident, uuid in LOG:
        print(f"  {ident}  {name}  {ARGS.url.rstrip('/')}/openmrs/spa/patient/{uuid}/chart")

if __name__ == "__main__":
    main()
