# -*- coding: utf-8 -*-
"""
JOURNAL DES TRADES
- chaque alerte envoyée est enregistrée (rapports/journal.json)
- à chaque analyse, le robot regarde ce que le prix a fait depuis :
  ordre déclenché ? TP1 / TP2 / TP3 ? stop ? → résultat en R
- statistiques (taux de réussite, R gagnés, par note, par session, par méthode)

Gestion simulée (la même que dans l'alerte) : au TP1 on ferme 50 % et le stop passe
à l'entrée, au TP2 on ferme 30 %, le reste au TP3. Si une bougie touche le stop ET un
TP, on compte le stop (hypothèse prudente).
"""
import json
import os
from datetime import timedelta

import pandas as pd

import config as C
import donnees as D
import rapport as R

FICHIER = os.path.join("rapports", "journal.json")
FINIS = ("gagné", "perdu", "break-even", "annulé")


# ---------------------------------------------------------------------------
# Lecture / écriture
# ---------------------------------------------------------------------------
def charger(fichier=FICHIER):
    try:
        with open(fichier, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def sauver(journal, fichier=FICHIER):
    os.makedirs(os.path.dirname(fichier), exist_ok=True)
    with open(fichier, "w", encoding="utf-8") as f:
        json.dump(journal, f, ensure_ascii=False, indent=1)


def _ts(x):
    t = pd.Timestamp(x)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def _paris(t):
    return _ts(t).tz_convert("Europe/Paris").strftime("%d/%m %H:%M")


# ---------------------------------------------------------------------------
# Décider s'il faut alerter (et éviter les doublons)
# ---------------------------------------------------------------------------
def cle_setup(r):
    """Un setup = un sens + un POI (même si la note passe de A à A+)."""
    p = r["poi"]
    return f"{r['sens']}|{round(p['bas'])}|{round(p['haut'])}"


def setup_a_alerter(r, journal, maintenant):
    """Renvoie (entrée, type d'ordre, clé) si une alerte doit partir, sinon None."""
    ordre_notes = ["C", "B", "A", "A+"]
    if not r["poi"] or ordre_notes.index(r["note"]) < ordre_notes.index(C.NOTE_MINI_ALERTE):
        return None
    if any(s in C.SESSIONS_SANS_ALERTE for s in r["sessions"]):
        return None
    e = R.choisir_entree(r)
    if e is None:
        return None
    cle = cle_setup(r)
    m = _ts(maintenant)
    for t in journal:
        if t["cle"] != cle:
            continue
        if t["statut"] in ("en attente", "en cours"):
            return None
        if m - _ts(t["date_alerte"]) < timedelta(hours=C.ANTI_DOUBLON_H):
            return None
    ordre = R.type_ordre(r["sens"], e["entree"], r["prix"], r["ltf"]["atr_der"])
    return e, ordre, cle


def ajouter(journal, r, e, ordre, cle, maintenant):
    t = {
        "id": (max((x["id"] for x in journal), default=0) + 1),
        "date_alerte": _ts(maintenant).isoformat(),
        "sens": r["sens"], "note": r["note"], "score": r["score"],
        "methode": e["nom"].split(" (")[0], "ordre": ordre,
        "session": next((s for s in r["sessions"] if s.startswith("Killzone")),
                        r["sessions"][0] if r["sessions"] else "hors session"),
        "poi": r["poi"]["nom"], "cle": cle,
        "prix_alerte": round(r["prix"], 2), "entree": round(e["entree"], 2),
        "stop": round(e["stop"], 2), "tps": [round(p, 2) for p, _ in e["tps"]],
        "rr": [round(x, 2) for x in e["rr"]],
        "statut": "en attente", "resultat_R": 0.0, "tp_touches": 0,
        "date_entree": None, "date_sortie": None, "evenements": [],
    }
    journal.append(t)
    return t


# ---------------------------------------------------------------------------
# Suivi d'un trade sur les bougies LTF
# ---------------------------------------------------------------------------
def _partiels(n):
    if n <= 1:
        return [1.0]
    if n == 2:
        return [C.PARTIELS[0], 1 - C.PARTIELS[0]]
    return list(C.PARTIELS)


def simuler(t, df):
    """Rejoue le trade depuis l'alerte. Met `t` à jour, renvoie les nouveaux évènements."""
    if t["statut"] in FINIS or df is None or df.empty:
        return []
    dur = D.duree(C.UT_LTF)
    ta = _ts(t["date_alerte"])
    idx = df.index.tz_convert("UTC")
    garde = (idx + dur) > ta
    idx = idx[garde]
    hi, lo, cl = (df[k].to_numpy()[garde] for k in ("High", "Low", "Close"))

    s, E, sl0, tps = t["sens"], t["entree"], t["stop"], t["tps"]
    risque = abs(E - sl0) or 1e-9
    parts = _partiels(len(tps))
    marche = t["ordre"].startswith("AU MARCHÉ")
    limite = "LIMIT" in t["ordre"]
    fin_validite = ta + timedelta(hours=C.VALIDITE_ORDRE_H)

    statut, res, restant, stop, touches = "en attente", 0.0, 1.0, sl0, 0
    d_in = d_out = None
    evts = []

    def stop_touche(k):
        return lo[k] <= stop if s == 1 else hi[k] >= stop

    def fermer_au_stop(k):
        nonlocal res, restant, d_out
        res += restant * (stop - E) * s / risque
        restant, d_out = 0.0, idx[k]
        if touches == 0:
            evts.append(f"🛑 {_paris(idx[k])} stop touché à {stop:.2f}")
        else:
            evts.append(f"↩️ {_paris(idx[k])} reste fermé à l'entrée (break-even)")

    for k in range(len(idx)):
        if statut == "en attente":
            if idx[k] >= fin_validite:
                statut = "annulé"
                evts.append(f"⌛ ordre non déclenché avant {_paris(fin_validite)} → annulé")
                break
            if marche:
                declenche = True
            elif limite:
                declenche = lo[k] <= E if s == 1 else hi[k] >= E
            else:                                   # ordre stop
                declenche = hi[k] >= E if s == 1 else lo[k] <= E
            if not declenche:
                if tps and (hi[k] >= tps[0] if s == 1 else lo[k] <= tps[0]):
                    statut = "annulé"
                    evts.append(f"🏃 {_paris(idx[k])} le prix est parti au TP1 sans déclencher l'ordre → annulé")
                    break
                continue
            statut, d_in = "en cours", idx[k]
            evts.append(f"▶️ {_paris(idx[k])} ordre déclenché à {E:.2f}")
            if stop_touche(k):                      # même bougie : prudence
                fermer_au_stop(k)
                break
            continue

        # trade en cours
        if stop_touche(k):
            fermer_au_stop(k)
            break
        while touches < len(tps) and (hi[k] >= tps[touches] if s == 1 else lo[k] <= tps[touches]):
            gain = abs(tps[touches] - E) / risque
            res += parts[touches] * gain
            restant -= parts[touches]
            touches += 1
            txt = f"🎯 {_paris(idx[k])} TP{touches} touché ({tps[touches - 1]:.2f})"
            if touches == 1 and touches < len(tps):
                stop = E
                txt += " → stop remonté à l'entrée"
            evts.append(txt)
        if touches == len(tps):
            restant, d_out = 0.0, idx[k]
            break
        if idx[k] - d_in >= timedelta(hours=C.DUREE_MAX_TRADE_H):
            res += restant * (cl[k] - E) * s / risque
            restant, d_out = 0.0, idx[k]
            evts.append(f"⏱ {_paris(idx[k])} durée max atteinte → fermé à {cl[k]:.2f}")
            break

    if statut == "en cours" and restant <= 1e-9:
        statut = "gagné" if res > 0.05 else "perdu" if res < -0.05 else "break-even"

    nouveaux = evts[len(t["evenements"]):]
    t.update(statut=statut, resultat_R=round(res, 2), tp_touches=touches,
             date_entree=d_in.isoformat() if d_in is not None else None,
             date_sortie=d_out.isoformat() if d_out is not None else None,
             evenements=evts)
    return nouveaux


def mettre_a_jour(journal, df):
    """Met à jour tous les trades ouverts. Renvoie [(trade, nouveaux évènements)]."""
    changes = []
    for t in journal:
        nv = simuler(t, df)
        if nv:
            changes.append((t, nv))
    return changes


# ---------------------------------------------------------------------------
# Statistiques
# ---------------------------------------------------------------------------
def risque_compte():
    return C.CAPITAL * C.RISQUE_PCT / 100


def stats(trades):
    fermes = [t for t in trades if t["statut"] in ("gagné", "perdu", "break-even")]
    g = [t for t in fermes if t["statut"] == "gagné"]
    p = [t for t in fermes if t["statut"] == "perdu"]
    total = sum(t["resultat_R"] for t in fermes)
    gains = sum(t["resultat_R"] for t in g)
    pertes = -sum(t["resultat_R"] for t in p)

    def par(cle):
        res = {}
        for t in fermes:
            d = res.setdefault(t[cle], {"n": 0, "g": 0, "R": 0.0})
            d["n"] += 1
            d["g"] += t["statut"] == "gagné"
            d["R"] += t["resultat_R"]
        return res

    return {
        "alertes": len(trades), "fermes": len(fermes), "gagnes": len(g), "perdus": len(p),
        "be": len(fermes) - len(g) - len(p),
        "annules": sum(t["statut"] == "annulé" for t in trades),
        "ouverts": sum(t["statut"] in ("en attente", "en cours") for t in trades),
        "taux": 100 * len(g) / len(fermes) if fermes else 0.0,
        "R": total, "R_moyen": total / len(fermes) if fermes else 0.0,
        "profit_factor": gains / pertes if pertes else (float("inf") if gains else 0.0),
        "argent": total * risque_compte(),
        "par_note": par("note"), "par_session": par("session"), "par_methode": par("methode"),
        "meilleur": max(fermes, key=lambda t: t["resultat_R"], default=None),
        "pire": min(fermes, key=lambda t: t["resultat_R"], default=None),
    }


def texte_stats(st, titre):
    dev = "€" if C.DEVISE_COMPTE == "EUR" else "$"
    pf = "∞" if st["profit_factor"] == float("inf") else f"{st['profit_factor']:.2f}"
    l = [titre,
         f"Alertes : {st['alertes']}  |  déclenchées et clôturées : {st['fermes']}",
         f"✅ {st['gagnes']} gagnés   ❌ {st['perdus']} perdus   ↩️ {st['be']} break-even",
         f"⌛ {st['annules']} annulés   ⏳ {st['ouverts']} encore ouverts"]
    if st["fermes"]:
        l += [f"Taux de réussite : {st['taux']:.0f} %",
              f"Résultat : {st['R']:+.2f} R  (≈ {st['argent']:+.0f} {dev} avec "
              f"{C.RISQUE_PCT:g} % de risque)",
              f"Moyenne par trade : {st['R_moyen']:+.2f} R  |  profit factor : {pf}"]
        for nom, cle in (("Par note", "par_note"), ("Par session", "par_session"),
                         ("Par méthode", "par_methode")):
            if st[cle]:
                l.append(f"{nom} : " + " | ".join(
                    f"{k} {v['g']}/{v['n']} ({v['R']:+.1f} R)" for k, v in sorted(st[cle].items())))
    else:
        l.append("Pas encore assez de trades clôturés pour des statistiques.")
    return "\n".join(l)
