#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📡 SIGNAUX HISTORIQUES — fait tourner l'analyse du robot sur le passé (une fois)
et enregistre, à chaque pas, tout ce qu'il voyait : note, checklist, POI, entrées.
Les variantes de réglages sont ensuite testées très vite par comparer.py.

    python3 signaux.py --marche EURUSD --annee 2023      (données Dukascopy de data/)
    python3 signaux.py --demo                              (données fictives)
"""
import argparse
import gzip
import json
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd         # noqa: E402

import config as C          # noqa: E402
import donnees as D         # noqa: E402
import historique as H      # noqa: E402
import journal as J         # noqa: E402
import strategie as ST      # noqa: E402

# Ordre fixe des lignes de la checklist (voir strategie.analyser, étape 8)
CLES_CHECK = ["biais", "mtf_aligne", "zone_htf", "poi", "idm", "liq_prise",
              "confirmation", "crt", "smt", "killzone"]


def sources(demo=False):
    """Historique Dukascopy du marché actif (C.activer) : 1h, 15m et 1h du marché SMT."""
    if demo:
        return D.demo_brut(jours=120)
    m = C.MARCHES[C.MARCHE]
    ins = m["dukascopy"]
    smt = C.MARCHES.get(m.get("smt") or "", {}).get("dukascopy")
    h1, m15 = H.lire(ins, "h1"), H.lire(ins, "m15")
    ag = H.lire(smt, "h1") if smt else None
    if h1 is None or m15 is None:
        sys.exit(f"❌ Historique {C.MARCHE} absent : lance d'abord « python3 historique.py telecharger ».")
    return h1, m15, ag


def _tranche(df, debut, fin):
    if df is None:
        return None
    i, j = df.index.searchsorted(debut), df.index.searchsorted(fin, side="right")
    return df.iloc[i:j]


def signal(res, T):
    if not res["poi"] or not res["entrees"]:
        return None
    return {
        "t": T.isoformat(), "sens": res["sens"], "note": res["note"], "score": res["score"],
        "check": [[k, bool(ok), int(pts)] for k, (ok, _, pts) in zip(CLES_CHECK, res["check"])],
        "sessions": res["sessions"], "prix": round(res["prix"], 6),
        "atr_ltf": round(res["ltf"]["atr_der"], 6),
        "cle": J.cle_setup(res),          # même clé anti-doublon que le robot en direct
        "poi": res["poi"]["genre"], "poi_score": res["poi"]["score"],
        "confirmation": res["confirmation"]["type"] if res["confirmation"] else None,
        "entrees": [{"nom": e["nom"].split(" (")[0], "entree": round(e["entree"], 6),
                     "stop": round(e["stop"], 6), "tps": [round(p, 6) for p, _ in e["tps"]],
                     "rr": [round(x, 3) for x in e["rr"]], "valide": e["valide"]}
                    for e in res["entrees"]],
    }


def generer(h1, m15, ag, de, a, pas=4):
    dur = D.duree(C.UT_LTF)
    idx = m15.index.tz_convert("UTC")
    de = max(pd.Timestamp(de, tz="UTC"), idx[0] + pd.Timedelta(days=40))
    a = min(pd.Timestamp(a, tz="UTC"), idx[-1] + dur)
    instants = [t + dur for t in idx[(idx >= de) & (idx < a)][::pas]]
    print(f"📡 Signaux du {de:%d/%m/%Y} au {a:%d/%m/%Y} : {len(instants)} analyses", flush=True)
    res_list, t0 = [], time.time()
    for n, T in enumerate(instants, 1):
        debut = T - pd.Timedelta(days=520)
        data = D.construire(_tranche(h1, debut, T), _tranche(m15, T - pd.Timedelta(days=30), T),
                            _tranche(ag, debut, T), T)
        if min(len(data[k]) for k in ("htf", "mtf", "ltf")) < 60 or len(data["d1"]) < 25:
            continue
        try:
            s = signal(ST.analyser(data, T), T)
        except Exception as ex:                 # une bougie bizarre ne doit pas tout arrêter
            print(f"  ⚠️ {T}: {ex}")
            continue
        if s:
            res_list.append(s)
        if n % 500 == 0:
            v = (time.time() - t0) / n
            print(f"  … {n}/{len(instants)} ({T:%d/%m/%Y}) {len(res_list)} signaux, "
                  f"~{v * (len(instants) - n) / 60:.0f} min restantes", flush=True)
    return res_list


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--de", default="2021-01-01")
    p.add_argument("--a", default="2100-01-01")
    p.add_argument("--pas", type=int, default=4)
    p.add_argument("--annee", type=int, help="raccourci : toute une année")
    p.add_argument("--marche", default="XAUUSD", choices=sorted(C.MARCHES))
    p.add_argument("--demo", action="store_true")
    p.add_argument("--sortie")
    a = p.parse_args()
    if a.annee:
        a.de, a.a = f"{a.annee}-01-01", f"{a.annee + 1}-01-01"
    C.activer(a.marche)
    h1, m15, ag = sources(a.demo)
    sig = generer(h1, m15, ag, a.de, a.a, a.pas)
    os.makedirs("signaux", exist_ok=True)
    out = a.sortie or os.path.join("signaux", ("demo" if a.demo else f"signaux_{a.marche}_{a.de[:4]}") + ".json.gz")
    with gzip.open(out, "wt", encoding="utf-8") as f:
        json.dump(sig, f)
    print(f"✅ {len(sig)} signaux → {out}")


if __name__ == "__main__":
    main()
