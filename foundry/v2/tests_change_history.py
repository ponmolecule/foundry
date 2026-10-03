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
    finally:
        shutil.rmtree(d, ignore_errors=True)
        if old_env is None: os.environ.pop("FOUNDRY_DATA_DIR", None)
        else: os.environ["FOUNDRY_DATA_DIR"] = old_env
    print(f"\n{p} passed, {f} failed")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
