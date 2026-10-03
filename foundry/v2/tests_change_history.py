"""r248 regression gate: versioned saves and change history. The save itself must be unchanged."""
import copy, json, os, shutil, sys, tempfile


def main():
    sys.path.insert(0, ".")
    p = f = 0
    def ck(name, cond, detail=""):
        nonlocal p, f
        if cond: p += 1; print("  PASS ", name + (f" — {detail}" if detail else ""))
        else: f += 1; print("  FAIL ", name + (f" — {detail}" if detail else ""))
    d = tempfile.mkdtemp(); old_env = os.environ.get("FOUNDRY_DATA_DIR"); os.environ["FOUNDRY_DATA_DIR"] = d
    try:
        from foundry import store
        from foundry.v2.config_diff import history
        c = json.load(open("foundry/fixtures/universal_template_bank.json"))
        r = store.save_engagement(copy.deepcopy(c), slug="Hist Test", user="u1")
        expect = copy.deepcopy(c); expect.setdefault("config_schema_version", store.CONFIG_SCHEMA_VERSION)
        ck("the engagement file is written exactly as before (indent=1, insertion order)",
           open(r["path"], encoding="utf-8").read() == json.dumps(expect, indent=1))
        store.save_engagement(copy.deepcopy(c), slug="Hist Test", user="u1")
        ck("an unchanged re-save records no new version", len(store.list_versions("Hist Test", user="u1")) == 1)
        c2 = copy.deepcopy(c); c2["assumptions"]["lending_products"][0]["yield_ann"] = 0.071
        store.save_engagement(copy.deepcopy(c2), slug="Hist Test", user="u1")
        H = history(store.list_versions("Hist Test", user="u1"))
        ck("a changed save records a version with a readable field-level change",
           len(H) == 2 and H[0]["n_changes"] == 1 and H[0]["changes"][0]["field"] == "yield (annual)"
           and H[0]["changes"][0]["before"] == "6.50%" and H[0]["changes"][0]["after"] == "7.10%" and H[1]["first"])
        store.save_engagement(copy.deepcopy(c2), slug="working-session", user="u1")
        ck("working-session autosaves are not recorded", store.list_versions("working-session", user="u1") == [])
        ck("the engagement listing is unaffected by the history folder",
           sorted(e["slug"] for e in store.list_engagements(user="u1")) == ["hist-test", "working-session"])
        orig = store._record_version
        store._record_version = lambda *a, **k: (_ for _ in ()).throw(OSError("disk full"))
        try:
            c3 = copy.deepcopy(c2); c3["assumptions"]["lending_products"][0]["yield_ann"] = 0.072
            r3 = store.save_engagement(copy.deepcopy(c3), slug="Hist Test", user="u1")
            ck("a history failure never fails the save", r3["slug"] == "hist-test"
               and json.load(open(r3["path"]))["assumptions"]["lending_products"][0]["yield_ann"] == 0.072)
        finally:
            store._record_version = orig
        for k in range(store.HISTORY_KEEP + 5):
            ck_cfg = copy.deepcopy(c); ck_cfg["assumptions"]["lending_products"][0]["yield_ann"] = 0.05 + k * 0.0001
            store._record_version(ck_cfg, "Keep Test", "u1")
        ck("only the newest versions are kept", len(store.list_versions("Keep Test", user="u1")) == store.HISTORY_KEEP)
        # r249: identity-matched lists, tracking marker placement, stamps not counted
        from foundry.v2.config_diff import diff
        c4 = copy.deepcopy(c); feed = list(c4["assumptions"]["cac_feeds"].values())[0]
        del feed["driver_specs"]["attrition_rate"]; c4["assumptions"]["nie_detail"]["workforce"]["roles"].pop(1)
        D = diff(c, c4)
        ck("a deleted schedule and a deleted role are one 'removed' line each (no positional cascade)",
           len(D) == 2 and all(x["kind"] == "removed" for x in D) and "12 values" in D[0]["before"])
        store.start_tracking("Keep Test", user="u1")
        for k in range(store.HISTORY_KEEP + 3):
            cc = copy.deepcopy(c); cc["assumptions"]["lending_products"][0]["yield_ann"] = 0.06 + k * 0.0001
            store._record_version(cc, "Keep Test", "u1")
        ck("the tracking marker sits outside the versions folder and survives pruning",
           store.get_tracking("Keep Test", user="u1") is not None
           and all(not str(v.get("id", "")).startswith("_") for v in store.list_versions("Keep Test", user="u1")))
        for k, v in (("FOUNDRY_USER", "klaros"), ("FOUNDRY_PASS", "test123"), ("FOUNDRY_COOKIE_SECURE", "0")):
            os.environ.setdefault(k, v)
        import app as A
        A.app.dependency_overrides[A.gate] = lambda: "u1"
        try:
            from fastapi.testclient import TestClient
            cl = TestClient(A.app)
            live = copy.deepcopy(c)        # no client / proposed_bank / schema stamps, like the page
            st = cl.post("/api/v31/engagement/hist-test/status", json={"config": live}).json()
            ck("status reports saved, untracked engagements without a pending count", st["saved"] and st["tracking"] is None and st["pending"] is None)
            cl.post("/api/v31/engagement/hist-test/tracking")
            store.save_engagement(copy.deepcopy(live), slug="Hist Test", user="u1")
            st = cl.post("/api/v31/engagement/hist-test/status", json={"config": live}).json()
            ck("right after a save the live config has 0 unsaved changes (server stamps are not counted)", st["pending"]["n"] == 0)
            live2 = copy.deepcopy(live); del list(live2["assumptions"]["cac_feeds"].values())[0]["driver_specs"]["attrition_rate"]
            st = cl.post("/api/v31/engagement/hist-test/status", json={"config": live2}).json()
            ck("deleting a schedule shows as 1 unsaved change, kind removed", st["pending"]["n"] == 1 and st["pending"]["changes"][0]["kind"] == "removed")
        finally:
            A.app.dependency_overrides.clear()
    finally:
        shutil.rmtree(d, ignore_errors=True)
        if old_env is None: os.environ.pop("FOUNDRY_DATA_DIR", None)
        else: os.environ["FOUNDRY_DATA_DIR"] = old_env
    print(f"\n{p} passed, {f} failed")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
