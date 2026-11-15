# -*- coding: utf-8 -*-
"""
LIQUIDITÉ
- resting liquidity (BSL au-dessus / SSL en-dessous) non balayée
- formations : equal highs/lows, double top/bottom, liquidité de trendline
- liquidity sweeps / liquidity traps (fausse cassure par mèche, BOS piège)
"""
import numpy as np

import config as C


def _intact(h, l, i, prix, cote):
    apres = h[i + 1:] if cote == "BSL" else l[i + 1:]
    if len(apres) == 0:
        return True
    return apres.max() < prix if cote == "BSL" else apres.min() > prix


def resting_liquidity(df, st_sub, st_swing):
    """Sommets / creux non balayés = liquidité au repos."""
    h, l = df["High"].to_numpy(), df["Low"].to_numpy()
    res = []
    for nom, st in (("swing", st_swing), ("sub", st_sub)):
        for p in st["pivots"]:
            cote = "BSL" if p["type"] == "H" else "SSL"
            if _intact(h, l, p["i"], p["prix"], cote):
                res.append({"cote": cote, "prix": p["prix"], "i": p["i"],
                            "source": f"{p['label']} {nom}"})
    # dédoublonnage (un pivot swing est souvent aussi un pivot sub)
    vus, uniq = set(), []
    for r in res:
        cle = (r["cote"], round(r["prix"], 2))
        if cle not in vus:
            vus.add(cle)
            uniq.append(r)
    return uniq


def equal_highs_lows(df, st, a_dernier):
    """Equal highs / equal lows (et double top / bottom) non balayés."""
    h, l = df["High"].to_numpy(), df["Low"].to_numpy()
    tol = C.TOLERANCE_EQ_ATR * a_dernier
    res = []
    for typ, cote in (("H", "BSL"), ("L", "SSL")):
        pts = [p for p in st["pivots"] if p["type"] == typ][-25:]
        for x in range(len(pts)):
            for y in range(x + 1, len(pts)):
                p1, p2 = pts[x], pts[y]
                if abs(p1["prix"] - p2["prix"]) > tol:
                    continue
                niveau = max(p1["prix"], p2["prix"]) if typ == "H" else min(p1["prix"], p2["prix"])
                if not _intact(h, l, p2["i"], niveau, cote):
                    continue
                entre = h[p1["i"]:p2["i"] + 1] if typ == "H" else l[p1["i"]:p2["i"] + 1]
                if typ == "H" and entre.max() > niveau + tol:
                    continue
                if typ == "L" and entre.min() < niveau - tol:
                    continue
                ecart = p2["i"] - p1["i"]
                forme = ("Double top" if typ == "H" else "Double bottom") if ecart >= 8 else \
                        ("Equal highs (EQH)" if typ == "H" else "Equal lows (EQL)")
                res.append({"cote": cote, "prix": float(niveau), "i": p2["i"],
                            "i1": p1["i"], "source": forme})
    return res


def liquidite_trendline(df, st_mineure, sens):
    """3 creux (haussier) / sommets (baissier) mineurs alignés = liquidité de trendline."""
    typ = "L" if sens == 1 else "H"
    pts = [p for p in st_mineure["pivots"] if p["type"] == typ][-4:]
    if len(pts) < 3:
        return None
    pts = pts[-3:]
    prix = [p["prix"] for p in pts]
    monotone = all(prix[k] < prix[k + 1] for k in range(2)) if sens == 1 else \
               all(prix[k] > prix[k + 1] for k in range(2))
    if not monotone:
        return None
    x = np.array([p["i"] for p in pts], float)
    y = np.array(prix)
    pente, ordo = np.polyfit(x, y, 1)
    pred = pente * x + ordo
    r2 = 1 - ((y - pred) ** 2).sum() / max(((y - y.mean()) ** 2).sum(), 1e-9)
    if r2 < 0.9:
        return None
    n = len(df) - 1
    valeur = pente * n + ordo
    prix = df["Close"].iloc[-1]
    if (sens == 1 and prix <= valeur) or (sens == -1 and prix >= valeur):
        return None                      # trendline déjà cassée → liquidité prise
    return {"cote": "SSL" if sens == 1 else "BSL", "prix": float(pente * n + ordo),
            "source": "Liquidité de trendline (3 touches)", "points": pts,
            "pente": pente, "ordo": ordo}


def sweeps_recents(df, sts, derniers=20):
    """Liquidity sweeps / pièges récents sur toutes les structures."""
    n = len(df)
    c = df["Close"].to_numpy()
    res = []
    for nom, st in sts.items():
        for s in st["sweeps"]:
            apres = c[s["i"] + 1:]
            casse_ensuite = len(apres) > 0 and (apres.max() > s["niveau"] if s["sens"] == 1
                                                else apres.min() < s["niveau"])
            if s["i"] >= n - derniers and not casse_ensuite:
                cote = "BSL" if s["sens"] == 1 else "SSL"
                res.append({"i": s["i"], "niveau": s["niveau"], "cote": cote,
                            "structure": nom,
                            "piege": "piège à acheteurs" if cote == "BSL" else "piège à vendeurs"})
        for e in st["evenements"]:
            if e["i"] >= n - derniers and e.get("force", "").startswith("piège"):
                cote = "BSL" if e["sens"] == 1 else "SSL"
                res.append({"i": e["i"], "niveau": e["niveau"], "cote": cote,
                            "structure": nom, "piege": f"BOS piège ({nom})"})
    vus, uniq = set(), []
    for r in sorted(res, key=lambda r: -r["i"]):
        cle = (r["cote"], round(r["niveau"], 1))
        if cle not in vus:
            vus.add(cle)
            uniq.append(r)
    return uniq
