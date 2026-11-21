# -*- coding: utf-8 -*-
"""
KEY LEVELS & MARKET TOOLS
- PDH/PDL, PWH/PWL, PMH/PML, opens journaliers / hebdo / mensuels
- nombres ronds (niveaux psychologiques)
- sessions et killzones, range asiatique
- CRT (Candle Range Theory) en D1 et H4
- SMT divergence or / argent
- taille de position
"""
import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import config as C
from structure import pivots


def key_levels(d1: pd.DataFrame, ltf: pd.DataFrame, prix: float):
    niveaux = []
    if len(d1) >= 2:
        hier, auj = d1.iloc[-2], d1.iloc[-1]
        niveaux += [("PDH (haut d'hier)", hier["High"]), ("PDL (bas d'hier)", hier["Low"]),
                    ("Open du jour", auj["Open"])]
    sem = d1.resample("W").agg({"Open": "first", "High": "max", "Low": "min"})
    if len(sem) >= 2:
        niveaux += [("PWH (haut sem. dernière)", sem.iloc[-2]["High"]),
                    ("PWL (bas sem. dernière)", sem.iloc[-2]["Low"]),
                    ("Open de la semaine", sem.iloc[-1]["Open"])]
    mois = d1.resample("ME").agg({"Open": "first", "High": "max", "Low": "min"})
    if len(mois) >= 2:
        niveaux += [("PMH (haut mois dernier)", mois.iloc[-2]["High"]),
                    ("PML (bas mois dernier)", mois.iloc[-2]["Low"]),
                    ("Open du mois", mois.iloc[-1]["Open"])]

    # Range asiatique du jour (UTC 0h-6h)
    utc = ltf.tz_convert("UTC")
    jour = utc.index[-1].normalize()
    asie = utc[(utc.index >= jour) & (utc.index.hour < C.SESSIONS_UTC["Asie"][1])]
    if len(asie) > 0:
        niveaux += [("Haut session Asie", asie["High"].max()),
                    ("Bas session Asie", asie["Low"].min())]

    # Nombres ronds
    base50 = math.floor(prix / 50) * 50
    for r in (base50, base50 + 50):
        niveaux.append((f"Nombre rond {int(r)}", r))
    return [(nom, float(v)) for nom, v in niveaux]


def session_actuelle(maintenant=None):
    m = maintenant if maintenant is not None else datetime.now(timezone.utc)
    if hasattr(m, "to_pydatetime"):
        m = m.to_pydatetime()
    h = m.astimezone(timezone.utc).hour
    actives = [nom for nom, (a, b) in C.SESSIONS_UTC.items() if a <= h < b]
    return actives


def crt(df: pd.DataFrame, nom_ut: str, en_cours: bool = True):
    """Candle Range Theory sur les 2 dernières bougies clôturées."""
    if len(df) < 3:
        return None
    if en_cours:                               # la dernière (-1) est encore en cours
        b1, b2 = df.iloc[-3], df.iloc[-2]
    else:                                      # toutes les bougies sont fermées
        b1, b2 = df.iloc[-2], df.iloc[-1]
    if b2["High"] > b1["High"] and b1["Low"] < b2["Close"] < b1["High"]:
        return {"sens": -1, "ut": nom_ut, "cible": float(b1["Low"]),
                "texte": f"CRT baissier {nom_ut} : la bougie a balayé le haut "
                         f"{b1['High']:.2f} puis est revenue dans le range → cible {b1['Low']:.2f}"}
    if b2["Low"] < b1["Low"] and b1["Low"] < b2["Close"] < b1["High"]:
        return {"sens": 1, "ut": nom_ut, "cible": float(b1["High"]),
                "texte": f"CRT haussier {nom_ut} : la bougie a balayé le bas "
                         f"{b1['Low']:.2f} puis est revenue dans le range → cible {b1['High']:.2f}"}
    return None


def smt(or_df: pd.DataFrame, ag_df, n: int = C.PIVOT_SUB):
    """Divergence SMT : l'or fait un nouvel extrême mais pas l'argent (ou l'inverse)."""
    if ag_df is None or len(ag_df) < 50:
        return None
    commun = or_df.index.intersection(ag_df.index)
    if len(commun) < 50:
        return None
    a, b = or_df.loc[commun], ag_df.loc[commun]
    pa, pb = pivots(a, n), pivots(b, n)
    for typ in ("L", "H"):
        la = [p for p in pa if p["type"] == typ][-2:]
        if len(la) < 2:
            continue
        # pivots de l'argent les plus proches dans le temps
        lb = []
        for p in la:
            cands = [q for q in pb if q["type"] == typ and abs(q["i"] - p["i"]) <= n]
            if not cands:
                break
            lb.append(min(cands, key=lambda q: abs(q["i"] - p["i"])))
        if len(lb) < 2 or la[-1]["i"] < len(a) - 40:
            continue
        if typ == "L" and la[1]["prix"] < la[0]["prix"] and lb[1]["prix"] > lb[0]["prix"]:
            return {"sens": 1, "texte": "SMT haussière : l'or a fait un plus bas plus bas, "
                                         "l'argent non → faiblesse vendeuse"}
        if typ == "H" and la[1]["prix"] > la[0]["prix"] and lb[1]["prix"] < lb[0]["prix"]:
            return {"sens": -1, "texte": "SMT baissière : l'or a fait un plus haut plus haut, "
                                          "l'argent non → faiblesse acheteuse"}
    return None


def taille_position(entree, stop):
    """Lots pour risquer RISQUE_PCT du capital (capital dans la devise du compte)."""
    risque_compte = C.CAPITAL * C.RISQUE_PCT / 100
    taux = C.TAUX_EURUSD if C.DEVISE_COMPTE == "EUR" else 1.0
    risque_usd = risque_compte * taux
    distance = abs(entree - stop)
    if distance <= 0:
        return 0.0, risque_compte
    lots = math.floor(risque_usd / (distance * C.TAILLE_CONTRAT) * 100) / 100
    return lots, risque_compte
