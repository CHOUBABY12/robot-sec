#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
⚖️ COMPARAISON DE VARIANTES + POIDS DE LA CHECKLIST

À partir des signaux historiques (signaux.py), teste des centaines de réglages :
note minimum, méthode d'entrée, sessions, gestion du trade, validité de l'ordre.

Pour éviter de se tromper (sur-optimisation) :
- les réglages sont classés sur la période d'APPRENTISSAGE (avant --coupure)
- puis vérifiés sur la période de VÉRIFICATION (après), que le classement n'a pas vue.

    python3 comparer.py                  (signaux/ + data/ Dukascopy)
    python3 comparer.py --demo           (signaux/demo.json.gz + données fictives)
"""
import argparse
import glob
import gzip
import itertools
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import config as C          # noqa: E402
import donnees as D         # noqa: E402
import historique as H      # noqa: E402
import simulation as SIM    # noqa: E402

NOTES = ["C", "B", "A", "A+"]
ENTREES = {"auto": None, "confirmation": "Entrée sur confirmation", "50 %": "Entrée au 50 %",
           "agressive": "Entrée agressive", "raffinée": "Entrée raffinée"}
PRIORITE = ["Entrée sur confirmation", "Entrée raffinée", "Entrée au 50 %", "Entrée agressive"]
SESSIONS = ["toutes", "killzones", "hors Asie"]
VALIDITES = [4, 8, 12]
# réglage actuel du robot en direct (après l'optimisation de novembre 2026)
REFERENCE = {"note": "A", "entree": "auto", "sessions": "hors Asie", "gestion": "BE au TP1", "validite": 8}
H_NS = 3600 * 10**9


# ---------------------------------------------------------------------------
# Chargement
# ---------------------------------------------------------------------------
def charger(demo):
    fichiers = ["signaux/demo.json.gz"] if demo else sorted(
        f for f in glob.glob("signaux/signaux_*.json.gz"))
    sig = []
    for f in fichiers:
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            sig += json.load(fh)
    if not sig:
        sys.exit("❌ Aucun signal : lance d'abord signaux.py.")
    sig.sort(key=lambda s: s["t"])
    m15 = D.demo_brut(jours=120)[1] if demo else H.lire("xauusd", "m15")
    T = m15.index.tz_convert("UTC").as_unit("ns").asi8
    for s in sig:
        s["_t"] = pd.Timestamp(s["t"]).as_unit("ns").value
    k0 = np.searchsorted(T, [s["_t"] for s in sig])
    for s, k in zip(sig, k0):
        s["_k0"] = int(k)
    return sig, (T, m15["High"].to_numpy(), m15["Low"].to_numpy(), m15["Close"].to_numpy())


def type_ordre(sens, entree, prix, atr):
    if abs(entree - prix) <= 0.15 * atr:
        return "marche"
    if sens == 1:
        return "limit" if entree < prix else "stop"
    return "limit" if entree > prix else "stop"


def choisir(s, mode):
    valides = [e for e in s["entrees"] if e["valide"]]
    if mode == "auto":
        for nom in PRIORITE:
            for e in valides:
                if e["nom"].startswith(nom):
                    return e
        return None
    nom = ENTREES[mode]
    return next((e for e in valides if e["nom"].startswith(nom)), None)


def session_ok(s, mode):
    if mode == "toutes":
        return True
    if mode == "killzones":
        return any(x.startswith("Killzone") for x in s["sessions"])
    return "Asie" not in s["sessions"]


# ---------------------------------------------------------------------------
# Simulation d'une variante
# ---------------------------------------------------------------------------
class Moteur:
    def __init__(self, sig, barres):
        self.sig, self.b = sig, barres
        self.cache = {}

    def issue(self, i, e, gestion, validite):
        cle = (i, e["nom"], gestion, validite)
        if cle not in self.cache:
            s = self.sig[i]
            cibles, parts, be = SIM.preparer(s["sens"], e["entree"], e["stop"], e["tps"], gestion)
            T, Hh, Ll, Cc = self.b
            self.cache[cle] = SIM.simuler(
                T, Hh, Ll, Cc, s["_k0"], s["_t"], s["sens"],
                type_ordre(s["sens"], e["entree"], s["prix"], s["atr_ltf"]),
                e["entree"], e["stop"], cibles, parts, be,
                validite * H_NS, C.DUREE_MAX_TRADE_H * H_NS)
        return self.cache[cle]

    def trades(self, v, filtre=None):
        """Liste des trades qu'aurait pris le robot avec la variante v."""
        res, derniers = [], {}
        mini = NOTES.index(v["note"]) if v.get("note") else 0
        for i, s in enumerate(self.sig):
            if filtre is not None:
                if not filtre(s):
                    continue
            elif NOTES.index(s["note"]) < mini:
                continue
            if not session_ok(s, v["sessions"]):
                continue
            e = choisir(s, v["entree"])
            if e is None:
                continue
            d = derniers.get(s["cle"])
            if d is not None:
                ta, te = d
                if te is None or te > s["_t"] or s["_t"] - ta < C.ANTI_DOUBLON_H * H_NS:
                    continue
            statut, r, fin = self.issue(i, e, v["gestion"], v["validite"])
            derniers[s["cle"]] = (s["_t"], fin)
            res.append({"t": s["_t"], "statut": statut, "R": r, "i": i, "nom": e["nom"]})
        return res


def mesures(trades, debut, fin):
    tr = [t for t in trades if debut <= t["t"] < fin]
    fermes = [t for t in tr if t["statut"] in ("gagné", "perdu", "break-even")]
    r = np.array([t["R"] for t in fermes]) if fermes else np.zeros(0)
    gains, pertes = r[r > 0].sum(), -r[r < 0].sum()
    courbe = np.cumsum(r) if len(r) else np.zeros(1)
    dd = float((np.maximum.accumulate(np.r_[0, courbe]) - np.r_[0, courbe]).max())
    mois = max((fin - debut) / (30.44 * 24 * H_NS), 1e-9)
    return {"n": len(fermes), "annules": sum(t["statut"] == "annulé" for t in tr),
            "taux": 100 * float((r > 0.05).mean()) if len(r) else 0.0,
            "R": float(r.sum()), "R_moy": float(r.mean()) if len(r) else 0.0,
            "pf": float(gains / pertes) if pertes > 0 else (99.0 if gains > 0 else 0.0),
            "dd": dd, "R_mois": float(r.sum() / mois), "trades_mois": len(fermes) / mois}


def nom_variante(v):
    return f"note ≥ {v['note']} | {v['entree']} | {v['sessions']} | {v['gestion']} | {v['validite']}h"


def ligne(m):
    pf = "∞" if m["pf"] >= 99 else f"{m['pf']:.2f}"
    return (f"{m['n']:>4} trades  {m['taux']:>3.0f} %  {m['R']:>+7.1f} R  "
            f"({m['R_moy']:+.2f}/trade, {m['R_mois']:+.1f} R/mois)  PF {pf:>4}  DD {m['dd']:.1f} R")


# ---------------------------------------------------------------------------
# Programme principal
# ---------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--demo", action="store_true")
    p.add_argument("--coupure", default="2025-01-01", help="début de la période de vérification")
    p.add_argument("--min-trades", type=int, default=60, help="minimum de trades en apprentissage")
    p.add_argument("--telegram", action="store_true", help="envoyer le résumé sur Telegram")
    p.add_argument("--candidat", action="append", default=[],
                   help='variante à détailler, ex. "A|auto|hors Asie|BE au TP1|8"')
    a = p.parse_args()
    t0 = time.time()
    sig, barres = charger(a.demo)
    m = Moteur(sig, barres)
    debut, fin = sig[0]["_t"], sig[-1]["_t"] + 1
    coupure = pd.Timestamp(a.coupure, tz="UTC").value
    if a.demo:                                   # 2/3 – 1/3 sur les données fictives
        coupure = debut + (fin - debut) * 2 // 3
        a.min_trades = 5
    fmt = lambda ns: pd.Timestamp(ns, tz="UTC").strftime("%d/%m/%Y")   # noqa: E731
    out = []

    def dire(x=""):
        print(x, flush=True)
        out.append(x)

    dire(f"# ⚖️ Optimisation du robot SMC — {C.NOM_MARCHE}")
    dire(f"{len(sig)} signaux. Apprentissage : {fmt(debut)} → {fmt(coupure)} | "
         f"Vérification : {fmt(coupure)} → {fmt(fin)}")

    # 1. toutes les variantes
    grille = [dict(zip(("note", "entree", "sessions", "gestion", "validite"), x))
              for x in itertools.product(["A+", "A", "B"], ENTREES, SESSIONS,
                                         SIM.GESTIONS, VALIDITES)]
    resultats = []
    for v in grille:
        tr = m.trades(v)
        resultats.append((v, mesures(tr, debut, coupure), mesures(tr, coupure, fin)))
    ref = next(r for r in resultats if r[0] == REFERENCE)
    dire(f"\n{len(grille)} variantes testées en {time.time() - t0:.0f} s.")
    dire("\n## Réglage actuel du robot")
    dire(f"`{nom_variante(REFERENCE)}`")
    dire(f"- Apprentissage : {ligne(ref[1])}")
    dire(f"- Vérification  : {ligne(ref[2])}")

    eligibles = [r for r in resultats if r[1]["n"] >= a.min_trades]
    eligibles.sort(key=lambda r: (-r[1]["R"]))
    dire(f"\n## Top 15 sur l'apprentissage (≥ {a.min_trades} trades), et leur vérification")
    for k, (v, ap, ve) in enumerate(eligibles[:15], 1):
        dire(f"{k:>2}. `{nom_variante(v)}`")
        dire(f"    apprentissage : {ligne(ap)}")
        dire(f"    vérification  : {ligne(ve)}")
    positifs = [r for r in eligibles if r[1]["R"] > 0]
    deux = [r for r in positifs if r[2]["R"] > 0]
    dire(f"\nVariantes gagnantes en apprentissage : {len(positifs)}/{len(eligibles)} ; "
         f"gagnantes aussi en vérification : {len(deux)}")

    # 2. effet moyen de chaque réglage (plus fiable qu'un seul « meilleur » réglage)
    dire("\n## Effet de chaque réglage (moyenne sur toutes les variantes)")
    for dim, valeurs in (("note", ["A+", "A", "B"]), ("entree", list(ENTREES)),
                         ("sessions", SESSIONS), ("gestion", list(SIM.GESTIONS)),
                         ("validite", VALIDITES)):
        dire(f"\n**{dim}**")
        for val in valeurs:
            grp = [r for r in resultats if r[0][dim] == val]
            ra = np.mean([r[1]["R_moy"] for r in grp if r[1]["n"]] or [0])
            rv = np.mean([r[2]["R_moy"] for r in grp if r[2]["n"]] or [0])
            na = np.mean([r[1]["trades_mois"] for r in grp])
            dire(f"- {val!s:<13} R moyen/trade : apprentissage {ra:+.3f} | vérification {rv:+.3f}"
                 f"  ({na:.1f} trades/mois)")

    # 2 bis. détail par année et par sens (achats / ventes) pour quelques variantes
    def lire_candidat(txt):
        n, e, se, g, va = [x.strip() for x in txt.split("|")]
        return {"note": n, "entree": e, "sessions": se, "gestion": g, "validite": int(va)}

    a_detailler = [REFERENCE] + [r[0] for r in eligibles[:2]] + [lire_candidat(c) for c in a.candidat]
    dire("\n## Détail par année et par sens (achats / ventes)")
    for v in a_detailler:
        tr = [t for t in m.trades(v) if t["statut"] in ("gagné", "perdu", "break-even")]
        if not tr:
            continue
        df = pd.DataFrame([{"an": pd.Timestamp(t["t"], tz="UTC").year, "sens": sig[t["i"]]["sens"],
                            "R": t["R"]} for t in tr])
        dire(f"\n`{nom_variante(v)}`")
        dire("- par année : " + " | ".join(f"{k} {g.R.sum():+.0f} R ({len(g)})" for k, g in df.groupby("an")))
        for sens, nom in ((1, "achats"), (-1, "ventes")):
            g = df[df.sens == sens]
            if len(g):
                dire(f"- {nom} : {g.R.sum():+.1f} R sur {len(g)} trades "
                     f"({100 * (g.R > 0.05).mean():.0f} % gagnants, {g.R.mean():+.2f} R/trade)")

    # 3. poids de la checklist mesurés sur les données
    dire("\n## Poids de la checklist mesurés sur les données (apprentissage)")
    base = {"entree": "auto", "sessions": "toutes", "gestion": "BE au TP1", "validite": 4}
    tous = m.trades(base, filtre=lambda s: True)
    ap = [t for t in tous if t["t"] < coupure and t["statut"] in ("gagné", "perdu", "break-even")]
    cles = [c[0] for c in sig[0]["check"]]
    poids = {}
    dire("| Confluence | R moyen si oui | si non | écart | poids actuel → mesuré |")
    dire("|---|---|---|---|---|")
    ecarts = {}
    for k, cle in enumerate(cles):
        oui = [t["R"] for t in ap if sig[t["i"]]["check"][k][1]]
        non = [t["R"] for t in ap if not sig[t["i"]]["check"][k][1]]
        mo, mn = (np.mean(oui) if len(oui) >= 10 else np.nan), (np.mean(non) if len(non) >= 10 else np.nan)
        ecarts[cle] = (mo, mn, len(oui), len(non))
    actuels = {c: max([abs(p) for s in sig for (cc, ok, p) in s["check"] if cc == c] or [0])
               for c in cles}
    # confluences mesurables : leur part des 100 points est redistribuée selon l'écart mesuré ;
    # les autres (toujours vraies, ou trop rares) gardent leur poids actuel
    mesurables = [c for c, v in ecarts.items() if not np.isnan(v[0] - v[1])]
    part = sum(actuels[c] for c in mesurables)
    pos = {c: max(0.0, ecarts[c][0] - ecarts[c][1]) for c in mesurables}
    total = sum(pos.values())
    for c in cles:
        if c in mesurables:
            poids[c] = round(part * pos[c] / total) if total > 0 else actuels[c]
        else:
            poids[c] = actuels[c]
        mo, mn, no, nn = ecarts[c]
        f = lambda x: "n/a" if np.isnan(x) else f"{x:+.2f}"   # noqa: E731
        dire(f"| {c} | {f(mo)} ({no}) | {f(mn)} ({nn}) | {f(mo - mn) if not np.isnan(mo - mn) else 'n/a'}"
             f" | {actuels[c]} → {poids[c]} |")

    def score_mesure(s):
        return sum(poids[c] for (c, ok, _) in s["check"] if ok)

    meilleurs = []
    for seuil in range(30, 95, 5):
        v = dict(base, note=None)
        tr = m.trades(v, filtre=lambda s, sl=seuil: score_mesure(s) >= sl)
        ma = mesures(tr, debut, coupure)
        if ma["n"] >= a.min_trades:
            meilleurs.append((seuil, ma, mesures(tr, coupure, fin)))
    if meilleurs:
        seuil, ma, mv = max(meilleurs, key=lambda x: x[1]["R"])
        dire(f"\nAvec les poids mesurés, meilleur seuil en apprentissage : score ≥ {seuil}")
        dire(f"- Apprentissage : {ligne(ma)}")
        dire(f"- Vérification  : {ligne(mv)}")
        dire(f"- Réglage actuel (vérification) : {ligne(ref[2])}")
    else:
        dire("\nPas assez de trades pour tester les poids mesurés.")

    os.makedirs("rapports", exist_ok=True)
    nom = "optimisation_demo" if a.demo else "optimisation"
    with open(os.path.join("rapports", f"{nom}.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    with open(os.path.join("rapports", f"{nom}.json"), "w", encoding="utf-8") as f:
        json.dump({"reference": [REFERENCE, ref[1], ref[2]],
                   "variantes": [[v, ap_, ve] for v, ap_, ve in resultats],
                   "poids_mesures": poids}, f, ensure_ascii=False)
    dire(f"\n(terminé en {time.time() - t0:.0f} s)")

    if a.telegram:
        import rapport as R
        court = [f"⚖️ Optimisation {C.NOM_MARCHE} — {len(grille)} réglages testés",
                 f"Apprentissage {fmt(debut)}→{fmt(coupure)}, vérification {fmt(coupure)}→{fmt(fin)}",
                 "", "Réglage actuel :", f"• appr. {ligne(ref[1])}", f"• vérif. {ligne(ref[2])}"]
        for k, (v, ap_, ve) in enumerate(eligibles[:3], 1):
            court += ["", f"{k}. {nom_variante(v)}", f"• appr. {ligne(ap_)}", f"• vérif. {ligne(ve)}"]
        court += ["", f"Gagnantes en apprentissage ET en vérification : {len(deux)}/{len(eligibles)}",
                  "Rapport complet : rapports/optimisation.md sur GitHub."]
        if R.telegram_actif():
            R._envoyer("\n".join(court)[:4000])


if __name__ == "__main__":
    main()
