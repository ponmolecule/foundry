"""Presentation of weighted count breakdowns on Account streams (r421).

The engine resolves ``driver.params.count_multiplier_spec`` inside ``fee_stream_q``; this module re-resolves the
same spec with the same shared resolver after the run, over the full horizon, so the editor can show each band's
share, count per source unit and contribution by period, the share total in every period, and the resulting
count.  Nothing here feeds back into the engine.
"""
from .shared_assumptions import SharedAssumptions

_FAMILIES = (("lending", "lending_products"), ("deposit", "deposit_products"), ("obs", "obs_exposures"))


def count_breakdowns(cfg, res):
    a = (cfg or {}).get("assumptions") or {}
    ppy = int(a.get("periods_per_year") or 4)
    n = int(a.get("n_periods") or 12)
    try:
        from .growth import growth_context_from_cfg
        gctx = growth_context_from_cfg(cfg, ppy)
    except Exception:
        gctx = None
    qty = ((res or {}).get("fee_stream_quantities") or {}).get("series") or {}
    out = []
    for fam, key in _FAMILIES:
        for pi, p in enumerate(a.get(key) or []):
            for si, st in enumerate((p or {}).get("fee_streams") or []):
                drv = (st or {}).get("driver") or {}
                spec = (drv.get("params") or {}).get("count_multiplier_spec")
                if not spec:
                    continue
                sid = str(st.get("quantity_series_id") or "")
                rec = {"family": fam, "product_index": pi, "product": p.get("name"), "stream_index": si,
                       "stream": st.get("name"), "quantity_series_id": sid or None, "reference": drv.get("ref"),
                       "periods": n, "ppy": ppy}
                try:
                    mult, detail = SharedAssumptions({}, n, ppy, gctx).resolve(spec, "scalar")
                    bands = [{"id": d["component_id"], "name": d.get("name"), "weight_source": d.get("weight_source"),
                              "share": d["weight"], "count": d["amount"], "contribution": d["weighted_amount"]}
                             for d in detail if "component_id" in d]
                    rec["bands"] = bands
                    rec["multiplier"] = mult
                    rec["total_share"] = [sum(b["share"][t] for b in bands) for t in range(len(mult))]
                    q = qty.get(sid) if sid else None
                    if isinstance(q, list) and q:
                        q = [float(x or 0.0) for x in q[:n]]
                        rec["quantity"] = q
                        # Read the actual published upstream quantity. Dividing the result by the
                        # multiplier would misstate it when participation or launch timing also applies.
                        upstream_id = str(drv.get("ref") or "")
                        if drv.get("source") == "stream_ref":
                            hits = [x for x in p.get("fee_streams") or [] if x.get("name") == upstream_id]
                            upstream_id = str(hits[0].get("quantity_series_id") or "") if len(hits) == 1 else ""
                        upstream = qty.get(upstream_id)
                        rec["source"] = [float(x) if x is not None else None for x in upstream[:n]] if isinstance(upstream, list) else [None] * len(q)
                except ValueError as e:
                    rec["error"] = str(e)
                out.append(rec)
    return out
