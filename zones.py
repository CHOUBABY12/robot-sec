# -*- coding: utf-8 -*-
"""
ZONES D'INTÉRÊT (POI)
- Fair Value Gaps (FVG) + Inverse FVG
- Order Blocks : types (extrême, décisionnel, breaker, mitigation) et formations
  (1 bougie, multi-bougies, engulfing, avec FVG, avec prise de liquidité)
- Supply & Demand : RBR, DBR, DBD, RBD + flips SD / DS
"""
import numpy as np

import config as C


def _etat_zone(h, l, c, debut, haut, bas, sens):
    """Renvoie (nb de touches, invalidée?, indice d'invalidation)."""
    touches, dedans = 0, False
    for j in range(debut, len(c)):
        touche = l[j] <= haut if sens == 1 else h[j] >= bas
        if touche and not dedans:
            touches += 1
        dedans = touche
        casse = c[j] < bas if sens == 1 else c[j] > haut
        if casse:
            return touches, True, j
    return touches, False, None


# ---------------------------------------------------------------------------
# FVG
# ---------------------------------------------------------------------------
def detecter_fvg(df, a):
    o, h, l, c = (df[k].to_numpy() for k in ("Open", "High", "Low", "Close"))
    A = a.to_numpy()
    res = []
    for j in range(2, len(df)):
        for sens in (1, -1):
            if sens == 1 and l[j] > h[j - 2]:
                haut, bas = l[j], h[j - 2]
            elif sens == -1 and h[j] < l[j - 2]:
                haut, bas = l[j - 2], h[j]
            else:
                continue
            if haut - bas < C.FVG_MIN_ATR * A[j]:
                continue
            # remplissage
            etat, inv_i = "ouvert", None
            for k in range(j + 1, len(df)):
                if sens == 1:
                    if c[k] < bas:
                        etat, inv_i = "inversé (IFVG)", k
                        break
                    if l[k] <= bas:
                        etat = "comblé"
                    elif l[k] < haut and etat == "ouvert":
                        etat = "partiel"
                else:
                    if c[k] > haut:
                        etat, inv_i = "inversé (IFVG)", k
                        break
                    if h[k] >= haut:
                        etat = "comblé"
                    elif h[k] > bas and etat == "ouvert":
                        etat = "partiel"
            res.append({"genre": "FVG", "sens": sens if inv_i is None else -sens,
                        "sens_origine": sens, "i": j - 1, "haut": float(haut),
                        "bas": float(bas), "ce": float((haut + bas) / 2),
                        "etat": etat, "inv_i": inv_i})
    return res


# ---------------------------------------------------------------------------
# Order Blocks
# ---------------------------------------------------------------------------
def detecter_order_blocks(df, st, fvgs):
    o, h, l, c = (df[k].to_numpy() for k in ("Open", "High", "Low", "Close"))
    obs, vus = [], set()
    fvg_par_i = {}
    for f in fvgs:
        fvg_par_i.setdefault((f["i"], f["sens_origine"]), True)

    for e in st["evenements"]:
        sens, m = e["sens"], e["origine_i"]
        oppose = (lambda j: c[j] < o[j]) if sens == 1 else (lambda j: c[j] > o[j])
        j = m
        while j >= max(0, m - 6) and not oppose(j):
            j -= 1
        if j < max(0, m - 6):
            continue
        fin = j
        while j - 1 >= 0 and oppose(j - 1) and fin - j < 2:   # multi-bougies (max 3)
            j -= 1
        debut = j
        if (debut, sens) in vus:
            continue
        vus.add((debut, sens))

        if sens == 1:
            haut = float(max(h[debut:fin + 1]))
            bas = float(min(l[debut:m + 1].min(), l[debut:fin + 1].min()))
            corps_haut = float(max(o[debut:fin + 1]))
        else:
            bas = float(min(l[debut:fin + 1]))
            haut = float(max(h[debut:m + 1].max(), h[debut:fin + 1].max()))
            corps_haut = float(min(o[debut:fin + 1]))   # bord du corps côté prix

        avec_fvg = any((k, sens) in fvg_par_i for k in range(fin, e["i"] + 2))
        avant = l[max(0, debut - 15):debut] if sens == 1 else h[max(0, debut - 15):debut]
        prise_liq = len(avant) > 0 and (bas < avant.min() if sens == 1 else haut > avant.max())
        nxt = fin + 1
        engulfing = nxt < len(df) and (
            (sens == 1 and c[nxt] > o[fin] and c[nxt] > o[nxt]) or
            (sens == -1 and c[nxt] < o[fin] and c[nxt] < o[nxt]))

        formation = ["1 bougie" if debut == fin else f"{fin - debut + 1} bougies"]
        if engulfing:
            formation.append("engulfing")
        if avec_fvg:
            formation.append("avec FVG/imbalance")
        if prise_liq:
            formation.append("avec prise de liquidité")

        touches, invalide, inv_i = _etat_zone(h, l, c, e["i"] + 1, haut, bas, sens)
        if e["type"] == "CHoCH":
            type_ob = "Extrême (OB de CHoCH)"
        else:
            type_ob = "Décisionnel (OB de BOS)"
        sens_final = sens
        if invalide:
            # OB cassé → devient Breaker (s'il avait pris la liquidité) ou Mitigation block
            type_ob = "Breaker block" if prise_liq else "Mitigation block"
            sens_final = -sens
            touches = _etat_zone(h, l, c, inv_i + 1, haut, bas, sens_final)[0]
            invalide2 = _etat_zone(h, l, c, inv_i + 1, haut, bas, sens_final)[1]
            if invalide2:
                continue

        obs.append({
            "genre": "OB", "sens": sens_final, "type": type_ob, "i": debut,
            "evt_i": e["i"], "evt_type": e["type"], "haut": haut, "bas": bas,
            "mt": (haut + bas) / 2,                                   # mean threshold 50 %
            "raffine": (min(corps_haut, haut), bas) if sens == 1 else (haut, max(corps_haut, bas)),
            "formation": ", ".join(formation), "avec_fvg": avec_fvg,
            "prise_liq": bool(prise_liq), "touches": touches,
            "etat": "frais" if touches == 0 else f"testé {touches}x",
        })
    return obs


# ---------------------------------------------------------------------------
# Supply & Demand + flips
# ---------------------------------------------------------------------------
def detecter_supply_demand(df, a):
    o, h, l, c = (df[k].to_numpy() for k in ("Open", "High", "Low", "Close"))
    A = a.to_numpy()
    rng = h - l
    corps = np.abs(c - o)
    base = (corps <= 0.5 * np.maximum(rng, 1e-9)) | (rng <= 0.8 * A)
    impulsion = corps >= C.DISPLACEMENT_ATR * A
    zones = []
    j = 1
    while j < len(df) - 1:
        if not base[j]:
            j += 1
            continue
        k = j
        while k + 1 < len(df) and base[k + 1] and k - j < 2:
            k += 1
        sortie = k + 1
        entree = j - 1
        if sortie >= len(df) or not impulsion[sortie] or entree < 0:
            j = k + 1
            continue
        dir_out = 1 if c[sortie] > o[sortie] else -1
        dir_in = 1 if c[entree] > o[entree] else -1
        nom = {(1, 1): "RBR", (-1, 1): "DBR", (-1, -1): "DBD", (1, -1): "RBD"}[(dir_in, dir_out)]
        corps_h = np.maximum(o[j:k + 1], c[j:k + 1])
        corps_b = np.minimum(o[j:k + 1], c[j:k + 1])
        if dir_out == 1:     # demande : proximal = haut des corps, distal = plus bas
            haut, bas = float(corps_h.max()), float(l[j:k + 1].min())
        else:                # offre : proximal = bas des corps, distal = plus haut
            haut, bas = float(h[j:k + 1].max()), float(corps_b.min())
        touches, invalide, inv_i = _etat_zone(h, l, c, sortie + 1, haut, bas, dir_out)
        genre = "Demande" if dir_out == 1 else "Offre"
        sens_final, flip = dir_out, None
        if invalide:
            flip = "Flip DS (demande → offre)" if dir_out == 1 else "Flip SD (offre → demande)"
            sens_final = -dir_out
            t2, inv2, _ = _etat_zone(h, l, c, inv_i + 1, haut, bas, sens_final)
            if inv2:
                j = k + 1
                continue
            touches = t2
            genre = "Offre" if sens_final == -1 else "Demande"
        zones.append({"genre": "SD", "type": f"{genre} {nom}" + (f" — {flip}" if flip else ""),
                      "sens": sens_final, "i": j, "haut": haut, "bas": bas,
                      "mt": (haut + bas) / 2, "flip": flip, "touches": touches,
                      "etat": "frais" if touches == 0 else f"testé {touches}x"})
        j = k + 1
    return zones
