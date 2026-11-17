#!/usr/bin/env python3
"""
Seed an ACT 3 stack as scripts/seed_act_demo.py does, with every patient, visit and encounter at a clinic that is not
retired. For a demo that retires all but a few clinics (AR-187), so the Registry, the Procedural waiting list and the
reports show only the clinics people can sign in at.

The same people, scenarios and options as seed_act_demo.py; only the clinics differ. Each retired clinic the seed would
use is replaced by an active one of the same kind, read from the server's location tags:

  RHD Community (primary care)      -> the first active RHD Community clinic (Acimi HCIII on the demo)
  RHD District or Tertiary (cardiac) -> the first active RHD Tertiary clinic, else RHD District (Uganda Heart Institute
                                        Tertiary on the demo)

  python3 scripts/seed_act_demo_active_clinics.py           # seed http://localhost (skips if already seeded)
  python3 scripts/seed_act_demo_active_clinics.py --reset   # void the seeded patients, then seed afresh
  (every option of seed_act_demo.py works the same way)

Run it on a stack whose clinics are already retired. Needs only the Python 3 standard library.
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seed_act_demo as seed  # noqa: E402

PRIMARY_CARE = ("RHD Community",)
CARDIAC = ("RHD Tertiary", "RHD District")

_send = seed.call
_replacements = None


def locations():
    """Every location with whether it is retired and its RHD tags, page by page."""
    found, start = [], 0
    while True:
        page = _send("GET", f"/location?includeAll=true&v=custom:(uuid,display,retired,tags:(display))&limit=100&startIndex={start}")
        if "__error__" in page:
            print(f"FAILED reading the locations: {page}")
            sys.exit(1)
        found += page["results"]
        if not any(link.get("rel") == "next" for link in page.get("links", [])):
            return found
        start += len(page["results"])


def replacements():
    """Each retired clinic's uuid, mapped to the active clinic of its kind."""
    everything = locations()
    tags = {loc["uuid"]: {tag["display"] for tag in loc["tags"]} for loc in everything}
    active = [loc for loc in everything if not loc["retired"]]

    def first_active(kinds):
        for kind in kinds:
            for loc in active:
                if kind in tags[loc["uuid"]]:
                    return loc
        return None

    primary_care, cardiac = first_active(PRIMARY_CARE), first_active(CARDIAC)
    if not primary_care or not cardiac:
        print("No active primary care or cardiac clinic on the server, so there is nowhere to seed.")
        sys.exit(1)
    mapping = {}
    for loc in everything:
        if not loc["retired"]:
            continue
        kinds = tags[loc["uuid"]]
        if kinds & set(PRIMARY_CARE):
            mapping[loc["uuid"]] = primary_care["uuid"]
        elif kinds & set(CARDIAC):
            mapping[loc["uuid"]] = cardiac["uuid"]
    print(f"seeding retired primary care clinics at {primary_care['display']} and retired cardiac clinics at "
          f"{cardiac['display']} ({len(mapping)} retired clinics replaced)")
    return mapping


def call(method, path, body=None, user=None, pw=None):
    """seed_act_demo's call, with every retired clinic in the request swapped for its active one."""
    global _replacements
    if body is None:
        # Reads, including the sign-in and already-seeded checks, go as they are.
        return _send(method, path, body, user, pw)
    if _replacements is None:
        _replacements = replacements()
    text = json.dumps(body)
    for retired, active in _replacements.items():
        text = text.replace(retired, active)
    return _send(method, path, json.loads(text), user, pw)


seed.call = call

if __name__ == "__main__":
    seed.main()
