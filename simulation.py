# -*- coding: utf-8 -*-
"""
SIMULATION RAPIDE D'UN TRADE (numpy) — mêmes règles que journal.simuler, mais
avec des gestions différentes, pour tester des centaines de variantes.

Règles : l'ordre doit être déclenché avant la fin de validité ; si le prix touche la
première cible avant, l'ordre est annulé. Sur la bougie de déclenchement, seul le stop
compte. Si une bougie touche le stop ET une cible, on compte le stop (prudence).
"""
import numpy as np

GESTIONS = {
    # nom : (type de cibles, partiels, cible après laquelle le stop passe à l'entrée)
    "BE au TP1": ("liquidité", None, 1),
    "BE au TP2": ("liquidité", None, 2),
    "sans BE": ("liquidité", None, None),
    "objectif 2R": ("fixe", 2.0, None),
    "objectif 3R": ("fixe", 3.0, None),
}


def partiels(n, base=(0.5, 0.3, 0.2)):
    if n <= 1:
        return [1.0]
    if n == 2:
        return [base[0], 1 - base[0]]
    return list(base)


def _premier(cond):
    if cond.size == 0:
        return None
    k = int(np.argmax(cond))
    return k if cond[k] else None


def preparer(sens, entree, stop, tps, gestion):
    """Cibles, parts et règle de break-even pour une gestion donnée."""
    typ, val, be = GESTIONS[gestion]
    risque = abs(entree - stop)
    if typ == "fixe":
        return [entree + sens * val * risque], [1.0], None
    cibles = list(tps)
    parts = partiels(len(cibles))
    if be is not None and be >= len(cibles):     # pas de BE sur la dernière cible
        be = None
    return cibles, parts, be


def simuler(T, H, L, Cl, k0, t_alerte, sens, type_ordre, E, SL, cibles, parts, be_apres,
            validite_ns, duree_max_ns):
    """
    T, H, L, Cl : tableaux des bougies (T = début de bougie en ns UTC).
    k0 : première bougie à prendre en compte. Renvoie (statut, R, ns de fin ou None).
    """
    n = len(H)
    risque = abs(E - SL) or 1e-9
    if k0 >= n:
        return "en attente", 0.0, None
    fin_val = int(np.searchsorted(T, t_alerte + validite_ns))
    # 1. déclenchement
    if type_ordre == "marche":
        kf = k0
    else:
        h, lo = H[k0:fin_val], L[k0:fin_val]
        if type_ordre == "limit":
            dec = lo <= E if sens == 1 else h >= E
        else:
            dec = h >= E if sens == 1 else lo <= E
        c1 = cibles[0]
        ann = (h >= c1 if sens == 1 else lo <= c1) & ~dec
        a, b = _premier(dec), _premier(ann)
        if b is not None and (a is None or b < a):
            return "annulé", 0.0, int(T[k0 + b])
        if a is None:
            if fin_val >= n:
                return "en attente", 0.0, None
            return "annulé", 0.0, int(T[fin_val])
        kf = k0 + a
    # 2. trade en cours
    kmax = int(np.searchsorted(T, T[kf] + duree_max_ns))   # bougie où la durée max est atteinte
    fin = min(kmax + 1, n)
    stop, res, reste, j = SL, 0.0, 1.0, 0
    a_s, a_t = kf, kf + 1
    while True:
        seg = L[a_s:fin] <= stop if sens == 1 else H[a_s:fin] >= stop
        ks = _premier(seg)
        ks = None if ks is None else a_s + ks
        kt = None
        if j < len(cibles):
            seg = H[a_t:fin] >= cibles[j] if sens == 1 else L[a_t:fin] <= cibles[j]
            kt = _premier(seg)
            kt = None if kt is None else a_t + kt
        if ks is not None and (kt is None or ks <= kt):
            res += reste * (stop - E) * sens / risque
            return _statut(res), res, int(T[ks])
        if kt is None:
            if kmax < n:                                  # durée max atteinte
                res += reste * (Cl[kmax] - E) * sens / risque
                return _statut(res), res, int(T[kmax])
            return "en cours", res, None
        res += parts[j] * abs(cibles[j] - E) / risque
        reste -= parts[j]
        j += 1
        if j == len(cibles):
            return _statut(res), res, int(T[kt])
        if be_apres == j:
            stop = E
        a_s, a_t = kt + 1, kt


def _statut(r):
    return "gagné" if r > 0.05 else "perdu" if r < -0.05 else "break-even"
