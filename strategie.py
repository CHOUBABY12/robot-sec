# -*- coding: utf-8 -*-
"""
STRATÉGIE TOP-DOWN (fractalisation HTF → MTF → LTF)
1. HTF : biais (structure swing) + premium / discount
2. MTF : jambe active, inducement, POI (OB / FVG / S&D / breaker / flip)
3. LTF : confirmation (CHoCH / BOS dans le POI) + raffinement
4. Liquidité, key levels, CRT, SMT, killzone → score de confluence
5. Types d'entrées avec stop, objectifs, ratio et taille de position
"""
import config as C
import liquidite as LQ
import outils as OT
import structure as S
import zones as Z


# ---------------------------------------------------------------------------
# Analyse complète d'une unité de temps (même logique sur chaque UT = fractal)
# ---------------------------------------------------------------------------
def analyser_ut(df, nom):
    a = S.atr(df)
    st = {
        "swing": S.analyser_structure(df, C.PIVOT_SWING, a),
        "sub": S.analyser_structure(df, C.PIVOT_SUB, a),
        "mineure": S.analyser_structure(df, C.PIVOT_MINEURE, a),
    }
    fvgs = Z.detecter_fvg(df, a)
    obs, vus = [], set()
    for niv in ("swing", "sub"):
        for ob in Z.detecter_order_blocks(df, st[niv], fvgs):
            if (ob["i"], ob["sens"]) not in vus:
                vus.add((ob["i"], ob["sens"]))
                ob["niveau"] = niv
                obs.append(ob)
    return {
        "nom": nom, "df": df, "atr": a, "atr_der": float(a.iloc[-1]), "st": st,
        "jambe": S.jambe_active(df, st["sub"]),
        "jambe_swing": S.jambe_active(df, st["swing"]),
        "fvg": fvgs, "ob": obs, "sd": Z.detecter_supply_demand(df, a),
    }


def _dernier_evt(st, sens):
    for e in reversed(st["evenements"]):
        if e["sens"] == sens:
            return e
    return None


def _chevauche(z1, z2):
    return z1["bas"] <= z2["haut"] and z2["bas"] <= z1["haut"]


# ---------------------------------------------------------------------------
# Sélection du meilleur POI
# ---------------------------------------------------------------------------
def choisir_poi(mtf, sens, jambe_ref, idm):
    df = mtf["df"]
    prix = float(df["Close"].iloc[-1])
    A = mtf["atr_der"]
    cands = []
    for ob in mtf["ob"]:
        if ob["sens"] == sens:
            nom = ob["type"] if ob["type"].endswith("block") else f"Order Block {ob['type']}"
            cands.append(dict(ob, nom=nom.replace("Breaker block", "Breaker Block (OB cassé → flip)")
                              .replace("Mitigation block", "Mitigation Block (OB cassé → flip)")))
    for f in mtf["fvg"]:
        if f["sens"] == sens and f["etat"] in ("ouvert", "partiel", "inversé (IFVG)"):
            nom = "Inverse FVG" if f["etat"].startswith("inversé") else "FVG"
            cands.append(dict(f, nom=nom, type=nom, etat=f["etat"]))
    for z in mtf["sd"]:
        if z["sens"] == sens:
            cands.append(dict(z, nom=f"Zone {z['type']}"))

    bon = []
    for z in cands:
        if sens == 1 and not (z["bas"] < prix and (jambe_ref is None or z["haut"] > jambe_ref["bas"] - A)):
            continue
        if sens == -1 and not (z["haut"] > prix and (jambe_ref is None or z["bas"] < jambe_ref["haut"] + A)):
            continue
        centre = z.get("mt", z.get("ce", (z["haut"] + z["bas"]) / 2))
        if abs(centre - prix) > 12 * A:
            continue
        bon.append(z)

    for z in bon:
        pts, why = 0, []
        g = z["genre"]
        pts += {"OB": 3, "SD": 2, "FVG": 1}[g]
        if "Breaker" in z.get("type", "") or z.get("flip"):
            pts += 1; why.append("zone flippée (breaker / flip)")
        if z.get("avec_fvg"):
            pts += 2; why.append("crée un FVG (displacement)")
        if z.get("prise_liq"):
            pts += 2; why.append("a pris de la liquidité")
        if z.get("etat") in ("frais", "ouvert"):
            pts += 2; why.append("zone fraîche (jamais touchée)")
        if jambe_ref:
            milieu = (z["haut"] + z["bas"]) / 2
            pos = (jambe_ref["haut"] - milieu) / max(jambe_ref["haut"] - jambe_ref["bas"], 1e-9) \
                if sens == 1 else (milieu - jambe_ref["bas"]) / max(jambe_ref["haut"] - jambe_ref["bas"], 1e-9)
            z["pos_fib"] = pos
            if pos >= 0.5:
                pts += 2; why.append("en " + ("discount" if sens == 1 else "premium"))
            if C.OTE_HAUT <= pos <= C.OTE_BAS + 0.1:
                pts += 1; why.append("dans l'OTE (0.618–0.79)")
        if idm and ((sens == 1 and z["haut"] <= idm["prix"]) or (sens == -1 and z["bas"] >= idm["prix"])):
            pts += 2; why.append("derrière l'inducement")
        autres = [o for o in bon if o is not z and _chevauche(o, z)]
        if autres:
            pts += 1; why.append("confluence avec " + ", ".join(sorted({o["genre"] for o in autres})))
        z["score"], z["raisons"] = pts, why

    if not bon:
        return None, []
    bon.sort(key=lambda z: (-z["score"], abs((z["haut"] + z["bas"]) / 2 - prix)))
    return bon[0], bon[1:4]


# ---------------------------------------------------------------------------
# Objectifs (liquidité opposée)
# ---------------------------------------------------------------------------
def cibles(sens, entree, A, liqs, key, jambe_ref, crt_list):
    pts = []
    cote = "BSL" if sens == 1 else "SSL"
    for l in liqs:
        if l["cote"] == cote:
            pts.append((l["prix"], f"liquidité {l['source']}"))
    for nom, v in key:
        pts.append((v, nom))
    if jambe_ref:
        ext = jambe_ref["haut"] if sens == 1 else jambe_ref["bas"]
        pts.append((ext, "extrême de la jambe (liquidité externe)"))
        for r in (-0.27, -0.618, -1.0):
            pts.append((S.fib_prix(jambe_ref, r), f"extension Fibonacci {r}"))
    for c in crt_list:
        if c and c["sens"] == sens:
            pts.append((c["cible"], f"cible CRT {c['ut']}"))
    pts = [(p, n) for p, n in pts if (p - entree) * sens > 0.5 * A]
    pts.sort(key=lambda x: (x[0] - entree) * sens)
    uniq = []
    for p, n in pts:
        if not uniq or abs(p - uniq[-1][0]) > 0.3 * A:
            uniq.append((p, n))
    return uniq


def construire_entree(nom, sens, entree, stop, liste_cibles, explication):
    stop = stop - sens * C.SPREAD          # le spread peut déclencher le stop plus tôt
    risque = abs(entree - stop)
    if risque <= 0:
        return None
    rr = lambda p: abs(p - entree) / risque
    tp1 = next(((p, n) for p, n in liste_cibles if rr(p) >= 1), None)
    tp2 = next(((p, n) for p, n in liste_cibles if rr(p) >= C.RR_MINIMUM), None)
    tp3 = next(((p, n) for p, n in liste_cibles if rr(p) >= 3.5), None)
    tps = []
    for t in (tp1, tp2, tp3):
        if t and t not in tps:
            tps.append(t)
    lots, risque_usd = OT.taille_position(entree, stop)
    rr_final = rr(tps[-1][0]) if tps else 0
    return {"nom": nom, "entree": entree, "stop": stop, "tps": tps,
            "rr": [rr(p) for p, _ in tps], "rr_final": rr_final,
            "valide": rr_final >= C.RR_MINIMUM, "lots": lots,
            "risque_usd": risque_usd, "explication": explication}


# ---------------------------------------------------------------------------
# Analyse globale
# ---------------------------------------------------------------------------
def analyser(donnees, maintenant=None):
    maintenant = maintenant or donnees.get("maintenant")
    htf = analyser_ut(donnees["htf"], C.UT_HTF)
    mtf = analyser_ut(donnees["mtf"], C.UT_MTF)
    ltf = analyser_ut(donnees["ltf"], C.UT_LTF)
    d1 = donnees["d1"]
    df = mtf["df"]
    prix = float(donnees["ltf"]["Close"].iloc[-1])
    A = mtf["atr_der"]

    # 1. Biais HTF
    biais = htf["st"]["swing"]["tendance"] or htf["st"]["sub"]["tendance"]
    if biais == 0:
        biais = mtf["st"]["sub"]["tendance"]
    sens = biais if biais != 0 else 1

    # 2. Jambe de référence et inducement MTF
    jambe_mtf = mtf["jambe"]
    aligne = jambe_mtf is not None and jambe_mtf["sens"] == sens
    jambe_ref = jambe_mtf if aligne else htf["jambe_swing"] or htf["jambe"]
    evt_mtf = _dernier_evt(mtf["st"]["sub"], sens)
    idm = S.inducement(df, mtf["st"]["mineure"], evt_mtf, sens)

    # 3. Liquidité
    liqs = LQ.resting_liquidity(df, mtf["st"]["sub"], mtf["st"]["swing"])
    eq = LQ.equal_highs_lows(df, mtf["st"]["sub"], A) + LQ.equal_highs_lows(df, mtf["st"]["mineure"], A)
    tl = LQ.liquidite_trendline(df, mtf["st"]["mineure"], sens)
    sweeps = LQ.sweeps_recents(df, mtf["st"], derniers=24)
    cachee = S.liquidite_cachee(df, mtf["st"]["mineure"], mtf["st"]["sub"],
                                jambe_mtf if aligne else None)
    key = OT.key_levels(d1, donnees["ltf"], prix)

    # 4. POI + dernière liquidité avant le POI
    poi, autres_poi = choisir_poi(mtf, sens, jambe_ref, idm)
    derniere_liq = None
    if poi:
        cands = [h for h in cachee if (h["prix"] > poi["haut"] if sens == 1 else h["prix"] < poi["bas"])]
        if cands:
            derniere_liq = min(cands, key=lambda h: abs(h["prix"] - (poi["haut"] if sens == 1 else poi["bas"])))

    # 5. Outils de marché
    # D1 : la dernière bougie est en cours ; 4h : uniquement des bougies fermées
    crt_list = [OT.crt(d1, "D1"), OT.crt(htf["df"], C.UT_HTF, en_cours=False)]
    smt = OT.smt(df, donnees.get("smt"))
    sessions = OT.session_actuelle(maintenant)

    # 6. Confirmation LTF + raffinement
    confirmation, raffinee = None, None
    if poi:
        marge = 0.5 * A
        lo, hi = poi["bas"] - marge, poi["haut"] + marge
        for e in reversed(ltf["st"]["sub"]["evenements"][-6:]):
            if e["sens"] == sens and lo <= e["origine"] <= hi and e["i"] >= len(ltf["df"]) - 64:
                confirmation = e
                break
        zones_ltf = [z for z in ltf["ob"] + [f for f in ltf["fvg"] if f["etat"] in ("ouvert", "partiel")]
                     if z["sens"] == sens and z["bas"] >= poi["bas"] - 0.1 * A
                     and z["haut"] <= poi["haut"] + 0.1 * A]
        if confirmation:
            liees = [z for z in ltf["ob"] if z.get("evt_i") == confirmation["i"] and z["sens"] == sens]
            if liees:
                zones_ltf = liees + zones_ltf
        if zones_ltf:
            raffinee = min(zones_ltf[:3] if confirmation else zones_ltf, key=lambda z: z["haut"] - z["bas"])

    # 7. Entrées
    liste_c = cibles(sens, prix, A, liqs + eq, key, jambe_ref, crt_list)
    entrees = []
    if poi:
        marge_sl = C.MARGE_SL_ATR * A
        dans_poi = poi["bas"] <= prix <= poi["haut"]
        prox = poi["haut"] if sens == 1 else poi["bas"]
        dist = poi["bas"] - marge_sl if sens == 1 else poi["haut"] + marge_sl
        e_aggr = prix if dans_poi else prox
        lc = cibles(sens, e_aggr, A, liqs + eq, key, jambe_ref, crt_list)
        entrees.append(construire_entree(
            "Entrée agressive (risk entry)", sens, e_aggr, dist, lc,
            "Ordre limite au bord du POI (proximal), stop derrière la zone (distal). "
            "Plus de gain potentiel, mais sans confirmation."))
        mt = (poi["haut"] + poi["bas"]) / 2
        entrees.append(construire_entree(
            "Entrée au 50 % du POI (mean threshold)", sens, mt, dist,
            cibles(sens, mt, A, liqs + eq, key, jambe_ref, crt_list),
            "Ordre limite au milieu de la zone : meilleur ratio, risque de ne pas être servi."))
        if raffinee:
            ml = C.MARGE_SL_ATR * ltf["atr_der"]
            e_r = raffinee["haut"] if sens == 1 else raffinee["bas"]
            s_r = raffinee["bas"] - ml if sens == 1 else raffinee["haut"] + ml
            mini = 0.5 * ltf["atr_der"]              # stop minimum (spread + bruit)
            if abs(e_r - s_r) < mini:
                s_r = e_r - mini * sens
            entrees.append(construire_entree(
                f"Entrée raffinée / sniper ({C.UT_LTF})", sens, e_r, s_r,
                cibles(sens, e_r, A, liqs + eq, key, jambe_ref, crt_list),
                f"Zone {raffinee['genre']} {C.UT_LTF} à l'intérieur du POI {C.UT_MTF} : "
                "stop plus serré, ratio bien meilleur."))
        if confirmation:
            ml = C.MARGE_SL_ATR * ltf["atr_der"]
            s_c = confirmation["origine"] - ml if sens == 1 else confirmation["origine"] + ml
            liees = [z for z in ltf["ob"] + ltf["fvg"] if z["sens"] == sens
                     and z["i"] >= confirmation["origine_i"] and z["i"] <= confirmation["i"] + 2
                     and z.get("etat") not in ("comblé", "inversé (IFVG)")]
            if liees:   # retour sur l'OB / FVG créé par la confirmation
                z = max(liees, key=lambda z: z["haut"] if sens == 1 else -z["bas"])
                e_c = min(prix, z["haut"]) if sens == 1 else max(prix, z["bas"])
            else:
                e_c = prix
            entrees.append(construire_entree(
                f"Entrée sur confirmation ({confirmation['type']} {C.UT_LTF})", sens, e_c, s_c,
                cibles(sens, e_c, A, liqs + eq, key, jambe_ref, crt_list),
                f"Le prix a réagi dans le POI et a fait un {confirmation['type']} en {C.UT_LTF} : "
                "entrée au retour sur l'OB/FVG créé (ou au marché si le prix y est), "
                "stop derrière l'origine du mouvement."))
    entrees = [e for e in entrees if e]

    # 8. Score de confluence
    check = []

    def add(ok, pts, txt, malus=0):
        check.append((ok, txt, pts if ok else -malus))

    add(biais != 0, 15, f"Biais {C.UT_HTF} défini ({S.resume_tendance(htf['st']['swing'])})")
    add(aligne, 10, f"Structure {C.UT_MTF} alignée avec le biais")
    hj = htf["jambe_swing"] or htf["jambe"]
    htf_ok = hj is not None and hj["sens"] == sens and hj["zone_favorable"]
    add(htf_ok, 10, f"Prix en {'discount' if sens == 1 else 'premium'} sur la jambe {C.UT_HTF}",
        malus=5)
    qp = poi["score"] if poi else 0
    add(qp >= 7, 15, f"POI de haute qualité (score {qp}/16)")
    if 4 <= qp < 7:
        check[-1] = (True, f"POI de qualité moyenne (score {qp}/16)", 8)
    add(bool(idm and idm["balaye"]), 10, "Inducement balayé")
    opp = "SSL" if sens == 1 else "BSL"
    add(any(s["cote"] == opp for s in sweeps), 10,
        f"Liquidité {'vendeuse (SSL)' if sens == 1 else 'acheteuse (BSL)'} prise récemment")
    add(confirmation is not None and confirmation["type"] == "CHoCH", 15,
        f"CHoCH de confirmation en {C.UT_LTF} dans le POI")
    if confirmation is not None and confirmation["type"] == "BOS":
        check[-1] = (True, f"BOS de confirmation en {C.UT_LTF} dans le POI", 8)
    crt_ok = [c for c in crt_list if c and c["sens"] == sens]
    crt_ko = [c for c in crt_list if c and c["sens"] == -sens]
    add(bool(crt_ok), 5, "CRT aligné", malus=5 if crt_ko else 0)
    add(bool(smt and smt["sens"] == sens), 5, "Divergence SMT alignée",
        malus=5 if smt and smt["sens"] == -sens else 0)
    add(any(s.startswith("Killzone") for s in sessions), 5, "Dans une killzone (Londres / New York)")
    score = max(0, min(100, sum(p for _, _, p in check)))
    rr_ok = any(e["valide"] for e in entrees)
    if not poi or not rr_ok:
        note = "C"
    else:
        note = "A+" if score >= 80 else "A" if score >= 65 else "B" if score >= 50 else "C"

    # 9. Statut
    if biais == 0:
        statut = "Structure indéfinie : pas de biais clair → rester à l'écart."
    elif not poi:
        statut = "Aucun POI valide dans le bon sens pour l'instant → attendre."
    elif confirmation and note == "C":
        statut = (f"Confirmation {C.UT_LTF} dans le POI, mais trop peu de confluences "
                  "→ setup faible, prudence.")
    elif confirmation and jambe_ref and not jambe_ref["zone_favorable"]:
        statut = (f"Confirmation {C.UT_LTF} obtenue, mais le prix est déjà reparti "
                  f"→ attendre un retour sur l'OB/FVG {C.UT_LTF} (ne pas courir après le prix).")
    elif confirmation:
        statut = f"Confirmation {C.UT_LTF} obtenue dans le POI → setup exploitable."
    elif poi["bas"] <= prix <= poi["haut"]:
        statut = f"Prix DANS le POI → attendre un CHoCH en {C.UT_LTF} pour confirmer."
    else:
        statut = "En attente du retour du prix dans le POI."

    return {
        "prix": prix, "sens": sens, "biais": biais, "htf": htf, "mtf": mtf, "ltf": ltf,
        "jambe_ref": jambe_ref, "aligne": aligne, "idm": idm, "poi": poi,
        "autres_poi": autres_poi, "derniere_liq": derniere_liq, "cachee": cachee,
        "liqs": liqs, "eq": eq, "trendline": tl, "sweeps": sweeps, "key": key,
        "crt": [c for c in crt_list if c], "smt": smt, "sessions": sessions,
        "confirmation": confirmation, "raffinee": raffinee, "entrees": entrees,
        "check": check, "score": score, "note": note, "statut": statut,
        "maintenant": maintenant,
    }
