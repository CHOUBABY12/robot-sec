# -*- coding: utf-8 -*-
"""
MARKET STRUCTURE
- pivots (fractales) à 3 niveaux : swing, sub, mineure
- étiquettes HH / HL / LH / LL
- BOS (types : fort / faible / piège) et CHoCH (changement de structure)
- balayages de liquidité par mèche (liquidity sweep)
- jambe active, premium / discount avec Fibonacci, condition de retracement
- inducement, liquidité cachée, dernière liquidité
"""
import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

import config as C


def atr(df: pd.DataFrame, p: int = C.ATR_PERIODE) -> pd.Series:
    c = df["Close"]
    tr = pd.concat([df["High"] - df["Low"], (df["High"] - c.shift()).abs(),
                    (df["Low"] - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / p, adjust=False).mean()


# ---------------------------------------------------------------------------
# Pivots (fractales)
# ---------------------------------------------------------------------------
def pivots(df: pd.DataFrame, n: int):
    """Liste de pivots alternés {type:'H'/'L', i, prix, label}."""
    h, l = df["High"].to_numpy(), df["Low"].to_numpy()
    if len(df) < 2 * n + 1:
        return []
    wh = sliding_window_view(h, 2 * n + 1)
    wl = sliding_window_view(l, 2 * n + 1)
    ih = np.where(np.argmax(wh, axis=1) == n)[0] + n
    il = np.where(np.argmin(wl, axis=1) == n)[0] + n
    brut = [{"type": "H", "i": int(i), "prix": float(h[i])} for i in ih] + \
           [{"type": "L", "i": int(i), "prix": float(l[i])} for i in il]
    brut.sort(key=lambda p: (p["i"], p["type"] == "L"))

    alt = []
    for p in brut:                       # on force l'alternance H / L
        if alt and alt[-1]["type"] == p["type"]:
            plus_extreme = p["prix"] > alt[-1]["prix"] if p["type"] == "H" else p["prix"] < alt[-1]["prix"]
            if plus_extreme:
                alt[-1] = p
        else:
            alt.append(p)

    dernier = {"H": None, "L": None}
    for p in alt:                        # étiquettes HH / LH / HL / LL
        prec = dernier[p["type"]]
        if prec is None:
            p["label"] = p["type"]
        elif p["type"] == "H":
            p["label"] = "HH" if p["prix"] > prec["prix"] else "LH"
        else:
            p["label"] = "HL" if p["prix"] > prec["prix"] else "LL"
        dernier[p["type"]] = p
    return alt


def _fvg_a(df, j, sens):
    """Y a-t-il un FVG dans le sens donné sur la bougie j ?"""
    if j < 2 or j >= len(df):
        return False
    if sens == 1:
        return df["Low"].iat[j] > df["High"].iat[j - 2]
    return df["High"].iat[j] < df["Low"].iat[j - 2]


# ---------------------------------------------------------------------------
# Structure : BOS / CHoCH / sweeps
# ---------------------------------------------------------------------------
def analyser_structure(df: pd.DataFrame, n: int, a: pd.Series):
    o, h, l, c = (df[k].to_numpy() for k in ("Open", "High", "Low", "Close"))
    A = a.to_numpy()
    piv = pivots(df, n)
    confirmes = {}
    for p in piv:
        confirmes.setdefault(p["i"] + n, []).append(p)

    tendance, ph, pl = 0, None, None
    evenements, sweeps = [], []
    for b in range(len(df)):
        for p in confirmes.get(b, []):
            if p["type"] == "H":
                ph = dict(p, casse=False, balaye=False)
            else:
                pl = dict(p, casse=False, balaye=False)

        for sens, piv_actif in ((1, ph), (-1, pl)):
            if piv_actif is None or piv_actif["casse"]:
                continue
            niveau = piv_actif["prix"]
            franchi_corps = c[b] > niveau if sens == 1 else c[b] < niveau
            franchi_meche = h[b] > niveau if sens == 1 else l[b] < niveau

            if franchi_corps:
                type_ev = "CHoCH" if tendance == -sens else "BOS"
                debut = piv_actif["i"]
                seg = l[debut:b + 1] if sens == 1 else h[debut:b + 1]
                k = debut + (int(np.argmin(seg)) if sens == 1 else int(np.argmax(seg)))
                corps = abs(c[b] - o[b])
                displacement = corps >= C.DISPLACEMENT_ATR * A[b] or any(
                    _fvg_a(df, j, sens) for j in (b - 1, b, b + 1))
                evenements.append({
                    "sens": sens, "type": type_ev, "i": b, "niveau": niveau,
                    "pivot_i": piv_actif["i"], "origine_i": k,
                    "origine": float(l[k] if sens == 1 else h[k]),
                    "displacement": bool(displacement),
                })
                piv_actif["casse"] = True
                tendance = sens
            elif franchi_meche and not piv_actif["balaye"]:
                sweeps.append({"sens": sens, "i": b, "niveau": niveau,
                               "pivot_i": piv_actif["i"]})
                piv_actif["balaye"] = True

    # Type de BOS : fort / faible / piège (retour sous le niveau en <= 3 bougies)
    for e in evenements:
        suite = c[e["i"] + 1:e["i"] + 4]
        piege = len(suite) > 0 and (np.any(suite < e["niveau"]) if e["sens"] == 1
                                    else np.any(suite > e["niveau"]))
        if piege:
            e["force"] = "piège (fake-out)"
        elif e["displacement"]:
            e["force"] = "fort (displacement)"
        else:
            e["force"] = "faible"
    return {"pivots": piv, "evenements": evenements, "sweeps": sweeps,
            "tendance": tendance}


# ---------------------------------------------------------------------------
# Jambe active, premium / discount, retracement
# ---------------------------------------------------------------------------
def fib_prix(jambe, r):
    """Prix d'un niveau Fibonacci (1 = départ de la jambe, 0 = extrême)."""
    if jambe["sens"] == 1:
        return jambe["haut"] - r * (jambe["haut"] - jambe["bas"])
    return jambe["bas"] + r * (jambe["haut"] - jambe["bas"])


def jambe_active(df: pd.DataFrame, st: dict):
    if not st["evenements"]:
        return None
    e = st["evenements"][-1]
    h, l, c = df["High"].to_numpy(), df["Low"].to_numpy(), df["Close"].to_numpy()
    k = e["origine_i"]
    if e["sens"] == 1:
        ext_i = k + int(np.argmax(h[k:]))
        jambe = {"sens": 1, "bas": e["origine"], "haut": float(h[ext_i]),
                 "debut_i": k, "extreme_i": ext_i}
    else:
        ext_i = k + int(np.argmin(l[k:]))
        jambe = {"sens": -1, "haut": e["origine"], "bas": float(l[ext_i]),
                 "debut_i": k, "extreme_i": ext_i}
    amplitude = jambe["haut"] - jambe["bas"]
    if amplitude <= 0:
        return None
    prix = c[-1]

    # position actuelle : 0 = à l'extrême, 1 = au départ (convention de l'utilisatrice)
    if jambe["sens"] == 1:
        pos = (jambe["haut"] - prix) / amplitude
        plus_profond = (jambe["haut"] - l[ext_i:].min()) / amplitude
    else:
        pos = (prix - jambe["bas"]) / amplitude
        plus_profond = (h[ext_i:].max() - jambe["bas"]) / amplitude
    jambe["position"] = float(pos)
    jambe["retracement_max"] = float(plus_profond)

    if pos >= 0.5:
        zone = "DISCOUNT" if jambe["sens"] == 1 else "PREMIUM"
    else:
        zone = "PREMIUM" if jambe["sens"] == 1 else "DISCOUNT"
    jambe["zone"] = zone
    jambe["zone_favorable"] = pos >= 0.5
    jambe["dans_ote"] = C.OTE_HAUT <= pos <= C.OTE_BAS

    # Condition de retracement : une bougie prend le bas (haussier) / le haut (baissier)
    # de la bougie précédente après l'extrême → pullback valide
    valide = False
    for j in range(ext_i + 1, len(df)):
        if (jambe["sens"] == 1 and l[j] < l[j - 1]) or (jambe["sens"] == -1 and h[j] > h[j - 1]):
            valide = True
            break
    jambe["retracement_valide"] = valide
    jambe["fib"] = {r: fib_prix(jambe, r) for r in C.FIB_NIVEAUX}
    jambe["equilibre"] = fib_prix(jambe, 0.5)
    return jambe


# ---------------------------------------------------------------------------
# Inducement, liquidité cachée, dernière liquidité
# ---------------------------------------------------------------------------
def inducement(df, st_mineure, evt, sens):
    """Premier pullback mineur après le BOS = inducement (IDM)."""
    if evt is None:
        return None
    h, l = df["High"].to_numpy(), df["Low"].to_numpy()
    type_p = "L" if sens == 1 else "H"
    for p in st_mineure["pivots"]:
        if p["type"] == type_p and p["i"] > evt["i"]:
            apres = l[p["i"] + 1:] if sens == 1 else h[p["i"] + 1:]
            balaye = len(apres) > 0 and (apres.min() < p["prix"] if sens == 1 else apres.max() > p["prix"])
            return {"prix": p["prix"], "i": p["i"], "balaye": bool(balaye)}
    return None


def liquidite_cachee(df, st_mineure, st_sub, jambe):
    """Pivots mineurs internes à la jambe, non balayés, invisibles en sous-structure."""
    if jambe is None:
        return []
    h, l = df["High"].to_numpy(), df["Low"].to_numpy()
    sub_idx = {p["i"] for p in st_sub["pivots"]}
    type_p = "L" if jambe["sens"] == 1 else "H"
    res = []
    for p in st_mineure["pivots"]:
        if p["type"] != type_p or p["i"] < jambe["debut_i"] or p["i"] in sub_idx:
            continue
        apres = l[p["i"] + 1:] if jambe["sens"] == 1 else h[p["i"] + 1:]
        intact = len(apres) == 0 or (apres.min() > p["prix"] if jambe["sens"] == 1 else apres.max() < p["prix"])
        if intact:
            res.append({"prix": p["prix"], "i": p["i"]})
    return res


def resume_tendance(st):
    t = st["tendance"]
    return "HAUSSIÈRE" if t == 1 else "BAISSIÈRE" if t == -1 else "INDÉFINIE"
