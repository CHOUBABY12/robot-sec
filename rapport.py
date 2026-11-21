# -*- coding: utf-8 -*-
"""Rapport dans le terminal, graphiques PNG et alertes Telegram."""
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime

import config as C
import structure as S

L = 66


def _p(x):
    return f"{x:,.{C.DECIMALES}f}".replace(",", " ")


def _maintenant_paris():
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("Europe/Paris"))


def _dev():
    return "€" if C.DEVISE_COMPTE == "EUR" else "$"


def _titre(t):
    print("\n" + f"── {t} ".ljust(L, "─"))


def afficher(r, demo=False):
    icone = {1: "🟢 HAUSSIER", -1: "🔴 BAISSIER", 0: "⚪ NEUTRE"}
    print("\n" + "═" * L)
    print(f"  🤖 ROBOT SMC — {C.NOM_MARCHE}   {_maintenant_paris():%d/%m/%Y %H:%M}" + ("  [DÉMO]" if demo else ""))
    print("═" * L)
    print(f"  Source des prix : {C.SOURCE_PRIX}")
    if C.ECART_MT5 and C.SOURCE_PRIX.startswith("Yahoo"):
        print(f"  (prix corrigés pour MT5 : écart de {C.ECART_MT5:g} $ retiré)")
    print(f"  Prix : {_p(r['prix'])}    ATR {C.UT_MTF} : {_p(r['mtf']['atr_der'])}")
    print(f"  Biais : {icone[r['biais']]}    Note du setup : {r['note']}   (confluence {r['score']}/100)")
    print(f"  ➜ {r['statut']}")

    # Fractalisation
    _titre("1. MARKET STRUCTURE (fractalisation)")
    print(f"  {'UT':<6}{'Swing':<14}{'Sub':<14}{'Mineure':<14}Dernier évènement (sub)")
    for ut in ("htf", "mtf", "ltf"):
        a = r[ut]
        evts = a["st"]["sub"]["evenements"]
        der = evts[-1] if evts else None
        txt = (f"{der['type']} {'↑' if der['sens'] == 1 else '↓'} {_p(der['niveau'])} — {der['force']}"
               if der else "-")
        print(f"  {a['nom']:<6}{S.resume_tendance(a['st']['swing']):<14}"
              f"{S.resume_tendance(a['st']['sub']):<14}{S.resume_tendance(a['st']['mineure']):<14}{txt}")
    piv = [p for p in r["mtf"]["st"]["sub"]["pivots"]][-6:]
    if piv:
        print(f"  Séquence {C.UT_MTF} : " + " → ".join(f"{p['label']} {p['prix']:.0f}" for p in piv))

    # Premium / Discount
    j = r["jambe_ref"]
    _titre("2. PREMIUM / DISCOUNT (Fibonacci)")
    if j:
        dep, ext = ("bas (HL/L)", "haut (HH/H)") if j["sens"] == 1 else ("haut (LH/H)", "bas (LL/L)")
        print(f"  Jambe {'haussière' if j['sens'] == 1 else 'baissière'} : du {dep} {_p(j['bas'] if j['sens'] == 1 else j['haut'])}"
              f" au {ext} {_p(j['haut'] if j['sens'] == 1 else j['bas'])}")
        print("  " + "  ".join(f"{k:g}: {_p(v)}" for k, v in j["fib"].items()))
        print(f"  Prix en zone {j['zone']} (position {j['position']:.2f})"
              + ("  ✨ dans l'OTE" if j["dans_ote"] else ""))
        print(f"  Retracement : {'✅ valide' if j['retracement_valide'] else '❌ pas encore de pullback valide'}"
              f" (le plus profond : {j['retracement_max']:.2f})")
    else:
        print("  Pas de jambe exploitable.")

    # Liquidité
    _titre("3. LIQUIDITÉ")
    idm = r["idm"]
    print(f"  Inducement (IDM) : " + (f"{_p(idm['prix'])} — {'✅ balayé' if idm['balaye'] else '⏳ pas encore balayé'}"
                                     if idm else "pas encore formé"))
    if r["derniere_liq"]:
        print(f"  Dernière liquidité avant le POI : {_p(r['derniere_liq']['prix'])}")
    if r["cachee"]:
        print("  Liquidité cachée (interne) : " + ", ".join(_p(h["prix"]) for h in r["cachee"][-4:]))
    prix = r["prix"]
    bsl = sorted([l for l in r["liqs"] + r["eq"] if l["cote"] == "BSL" and l["prix"] > prix], key=lambda l: l["prix"])[:3]
    ssl = sorted([l for l in r["liqs"] + r["eq"] if l["cote"] == "SSL" and l["prix"] < prix], key=lambda l: -l["prix"])[:3]
    print("  Resting liquidity au-dessus (BSL) : " + (", ".join(f"{_p(l['prix'])} ({l['source']})" for l in bsl) or "-"))
    print("  Resting liquidity en-dessous (SSL) : " + (", ".join(f"{_p(l['prix'])} ({l['source']})" for l in ssl) or "-"))
    if r["trendline"]:
        print(f"  {r['trendline']['source']} : ≈ {_p(r['trendline']['prix'])}")
    for s in r["sweeps"][:3]:
        print(f"  ⚡ Liquidity sweep {s['cote']} à {_p(s['niveau'])} ({s['piege']}, structure {s['structure']})")

    # POI
    _titre(f"4. POINT OF INTEREST ({C.UT_MTF})")
    poi = r["poi"]
    if poi:
        print(f"  ⭐ {poi['nom']} : {_p(poi['bas'])} – {_p(poi['haut'])}   [{poi.get('etat', '')}]")
        if poi.get("formation"):
            print(f"     Formation : {poi['formation']}")
        print(f"     Qualité {poi['score']}/16 : " + ", ".join(poi["raisons"]))
        for z in r["autres_poi"]:
            print(f"  • Autre : {z['nom']} {_p(z['bas'])} – {_p(z['haut'])} (score {z['score']})")
        if r["raffinee"]:
            z = r["raffinee"]
            print(f"  🔍 Raffinement {C.UT_LTF} : {z['genre']} {_p(z['bas'])} – {_p(z['haut'])}")
        if r["confirmation"]:
            c = r["confirmation"]
            print(f"  ✅ Confirmation {C.UT_LTF} : {c['type']} à {_p(c['niveau'])} ({c['force']})")
    else:
        print("  Aucun POI valide.")

    # Outils
    _titre("5. KEY LEVELS & OUTILS")
    proches = sorted(r["key"], key=lambda k: abs(k[1] - prix))[:6]
    for nom, v in proches:
        print(f"  {'▲' if v > prix else '▼'} {nom:<28} {_p(v)}")
    for c in r["crt"]:
        print(f"  🕯  {c['texte']}")
    if r["smt"]:
        print(f"  🔀 {r['smt']['texte']}")
    print(f"  🕐 Session : {', '.join(r['sessions']) or 'hors session principale'}")

    # Checklist
    _titre("6. CHECKLIST DE CONFLUENCE")
    for ok, txt, pts in r["check"]:
        print(f"  {'✅' if ok else '❌'} {txt:<52} {pts:+d}")

    # Entrées
    _titre("7. ENTRÉES PROPOSÉES")
    if not r["entrees"]:
        print("  Aucune entrée : pas de POI dans le sens du biais.")
    for e in r["entrees"]:
        flag = "✅" if e["valide"] else "⚠️ ratio insuffisant"
        print(f"\n  ▸ {e['nom']}  {flag}")
        print(f"    {'ACHAT' if r['sens'] == 1 else 'VENTE'} à {_p(e['entree'])} | Stop {_p(e['stop'])}"
              f" (risque {_p(abs(e['entree'] - e['stop']))})")
        for k, ((p, n), rr) in enumerate(zip(e["tps"], e["rr"]), 1):
            print(f"    TP{k} {_p(p)}  (1:{rr:.1f})  ← {n}")
        if e["lots"] >= 0.01:
            print(f"    Taille : {e['lots']:.2f} lot pour risquer {e['risque_usd']:.0f} {_dev()} "
                  f"({C.RISQUE_PCT:g} % de {C.CAPITAL:.0f} {_dev()})")
        else:
            print(f"    Taille : stop trop large pour {C.RISQUE_PCT:g} % de {C.CAPITAL:.0f} {_dev()} (min 0,01 lot)")
        print(f"    {e['explication']}")

    print("\n" + "─" * L)
    print("  ⚠️  Outil d'aide à la décision, pas un conseil financier.")
    print("     Vérifie toujours sur ton graphique et teste d'abord en compte démo.")
    print("═" * L + "\n")


# ---------------------------------------------------------------------------
# Graphique
# ---------------------------------------------------------------------------
def graphique(r, ut="mtf", dossier="rapports", nb=160):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    os.makedirs(dossier, exist_ok=True)
    a = r[ut]
    df = a["df"]
    debut = max(0, len(df) - nb)
    d = df.iloc[debut:]
    x = range(len(d))
    fig, ax = plt.subplots(figsize=(15, 8))
    fin_x = len(d) + 8

    # bougies
    for k, (_, b) in enumerate(d.iterrows()):
        col = "#26a69a" if b["Close"] >= b["Open"] else "#ef5350"
        ax.vlines(k, b["Low"], b["High"], color=col, lw=0.8)
        ax.add_patch(Rectangle((k - 0.35, min(b["Open"], b["Close"])), 0.7,
                               max(abs(b["Close"] - b["Open"]), 1e-6), color=col))

    def zone(z, couleur, alpha, label=None, lw=0):
        x0 = max(z["i"] - debut, 0)
        if z["i"] - debut > len(d):
            return
        ax.add_patch(Rectangle((x0, z["bas"]), fin_x - x0, z["haut"] - z["bas"],
                               color=couleur, alpha=alpha, lw=lw))
        if label:
            ax.text(fin_x, (z["haut"] + z["bas"]) / 2, " " + label, fontsize=7, va="center", color=couleur)

    for ob in a["ob"][-8:]:
        zone(ob, "#1e88e5" if ob["sens"] == 1 else "#e53935", 0.12)
    for f in [f for f in a["fvg"] if f["etat"] in ("ouvert", "partiel")][-8:]:
        zone(f, "#9e9e9e", 0.18)
    for s in a["sd"][-5:]:
        zone(s, "#43a047" if s["sens"] == 1 else "#fb8c00", 0.10)
    if ut == "mtf" and r["poi"]:
        zone(r["poi"], "#fdd835", 0.45, "POI")
    if ut == "ltf" and r["raffinee"]:
        zone(r["raffinee"], "#fdd835", 0.45, "Zone raffinée")

    # évènements de structure
    for e in a["st"]["sub"]["evenements"]:
        if e["i"] < debut:
            continue
        x0 = max(e["pivot_i"] - debut, 0)
        col = "#1565c0" if e["sens"] == 1 else "#c62828"
        ax.hlines(e["niveau"], x0, e["i"] - debut, color=col, lw=1, ls="--" if e["type"] == "BOS" else "-")
        ax.text((x0 + e["i"] - debut) / 2, e["niveau"], e["type"], fontsize=7, color=col,
                ha="center", va="bottom" if e["sens"] == 1 else "top", weight="bold")
    for p in a["st"]["sub"]["pivots"]:
        if p["i"] >= debut:
            ax.text(p["i"] - debut, p["prix"], p["label"], fontsize=6, ha="center",
                    va="bottom" if p["type"] == "H" else "top", color="#555")

    # Fibonacci de la jambe
    j = a["jambe"] if ut != "mtf" else r["jambe_ref"]
    if j:
        x0 = max(j["debut_i"] - debut, 0) if j is a["jambe"] else 0
        for niv, v in j["fib"].items():
            col = "#8e24aa" if niv in (0.5,) else "#ab47bc"
            ax.hlines(v, x0, fin_x, color=col, lw=0.7, ls=":")
            ax.text(fin_x, v, f" {niv:g}", fontsize=6, color=col, va="center")
        ax.axhspan(j["fib"][C.OTE_BAS], j["fib"][C.OTE_HAUT], xmin=0, xmax=1, color="#ab47bc", alpha=0.05)

    # liquidité
    if ut == "mtf":
        for l in (r["eq"])[-6:]:
            ax.hlines(l["prix"], max(l.get("i1", l["i"]) - debut, 0), fin_x, color="#ff6f00", lw=1, ls="-.")
            ax.text(fin_x, l["prix"], " " + l["source"].split(" (")[0], fontsize=6, color="#ff6f00")
        if r["idm"] and r["idm"]["i"] >= debut:
            ax.scatter(r["idm"]["i"] - debut, r["idm"]["prix"], marker="x", color="#6d4c41", zorder=5)
            ax.text(r["idm"]["i"] - debut, r["idm"]["prix"], " IDM", fontsize=7, color="#6d4c41", va="top")

    # entrée principale
    if r["entrees"]:
        e = max(r["entrees"], key=lambda e: e["rr_final"])
        ax.hlines(e["entree"], len(d) - 3, fin_x, color="#000", lw=1.3)
        ax.hlines(e["stop"], len(d) - 3, fin_x, color="#d50000", lw=1.3)
        for (p, _), k in zip(e["tps"], range(1, 4)):
            ax.hlines(p, len(d) - 3, fin_x, color="#00c853", lw=1.1)
            ax.text(len(d) - 3, p, f"TP{k} ", fontsize=7, ha="right", color="#00a043")
        ax.text(len(d) - 3, e["entree"], "Entrée ", fontsize=7, ha="right")
        ax.text(len(d) - 3, e["stop"], "SL ", fontsize=7, ha="right", color="#d50000")

    for t in ax.texts:
        t.set_clip_on(True)
    lo, hi = d["Low"].min(), d["High"].max()
    pad = (hi - lo) * 0.15
    ax.set_ylim(lo - pad, hi + pad)
    ax.set_xlim(-1, fin_x + 12)
    pas = max(1, len(d) // 10)
    ax.set_xticks(list(x)[::pas])
    ax.set_xticklabels([t.strftime("%d/%m %Hh") for t in d.index[::pas]], fontsize=7, rotation=30)
    ax.grid(alpha=0.2)
    sens = "HAUSSIER" if r["sens"] == 1 else "BAISSIER"
    ax.set_title(f"{C.NOM_MARCHE} — {a['nom']} — biais {sens} — note {r['note']} ({r['score']}/100)",
                 fontsize=11, weight="bold")
    fichier = os.path.join(dossier, f"analyse_{C.MARCHE}_{a['nom']}.png")
    fig.tight_layout()
    fig.savefig(fichier, dpi=130)
    plt.close(fig)
    return fichier


# ---------------------------------------------------------------------------
# Telegram (facultatif)
# ---------------------------------------------------------------------------
def choisir_entree(r):
    """Entrée recommandée : confirmation > raffinée > 50 % > agressive (parmi les valides)."""
    ordre = ["confirmation", "raffinée", "50 %", "agressive"]
    valides = [e for e in r["entrees"] if e["valide"] and e["lots"] >= 0.01] or \
              [e for e in r["entrees"] if e["valide"]]
    for mot in ordre:
        for e in valides:
            if mot in e["nom"]:
                return e
    return None


def type_ordre(sens, entree, prix, atr):
    if abs(entree - prix) <= 0.15 * atr:
        return "AU MARCHÉ (Buy)" if sens == 1 else "AU MARCHÉ (Sell)"
    if sens == 1:
        return "BUY LIMIT" if entree < prix else "BUY STOP"
    return "SELL LIMIT" if entree > prix else "SELL STOP"


def message_alerte(r, e=None, ordre=None, annonces=None):
    from datetime import timedelta
    import nouvelles as N
    e = e or choisir_entree(r)
    if e is None:
        return None
    s = r["sens"]
    ordre = ordre or type_ordre(s, e["entree"], r["prix"], r["ltf"]["atr_der"])
    P = C.prix_txt
    risque_pts = abs(e["entree"] - e["stop"])
    from zoneinfo import ZoneInfo
    depart = r.get("maintenant")
    depart = depart.to_pydatetime() if hasattr(depart, "to_pydatetime") else (depart or datetime.now(ZoneInfo("UTC")))
    # heure de Paris (les serveurs GitHub sont à l'heure UTC)
    fin = (depart + timedelta(hours=C.VALIDITE_ORDRE_H)).astimezone(ZoneInfo("Europe/Paris")).strftime("%H:%M")
    poi = r["poi"]
    invalid = poi["haut"] if s == -1 else poi["bas"]
    lignes = [
        f"🤖 {C.NOM_MARCHE} — SETUP {r['note']} ({r['score']}/100)",
        f"{'🟢 ACHAT' if s == 1 else '🔴 VENTE'} — ordre {ordre}",
        f"Méthode : {e['nom']}",
        "",
        f"📍 Entrée : {P(e['entree'])}   (prix actuel {P(r['prix'])})",
        f"🛑 Stop loss : {P(e['stop'])}   (distance {P(risque_pts)})",
    ]
    for k, ((p, n), rr) in enumerate(zip(e["tps"], e["rr"]), 1):
        lignes.append(f"🎯 TP{k} : {P(p)}   (1:{rr:.1f}) — {n}")
    lignes += [
        "",
        f"📦 Lot : {e['lots']:.2f}  → risque ≈ {e['risque_usd']:.0f} {_dev()} ({C.RISQUE_PCT:g} %)"
        if e["lots"] >= 0.01 else "📦 Lot : stop trop large pour ton risque → passe ton tour",
        "",
        "📋 Gestion :",
        "• Au TP1 : ferme 50 % et remonte le stop à l'entrée (break-even)",
        "• Au TP2 : ferme 30 %, laisse courir le reste vers TP3",
        f"• Ordre valable jusqu'à {fin} : annule-le s'il n'est pas déclenché",
        f"• Setup invalidé si une bougie {C.UT_MTF} clôture {'sous' if s == 1 else 'au-dessus de'} {P(invalid)}",
        "",
        f"🔎 POI : {poi['nom']} {P(poi['bas'])}–{P(poi['haut'])}",
        "✅ " + " | ".join(t for ok, t, _ in r["check"] if ok)[:300],
        f"ℹ️ {r['statut']}",
    ]
    proch = N.prochaines(annonces, r.get("maintenant"), heures=C.VALIDITE_ORDRE_H + 2)
    if proch:
        lignes += ["", "📰 Annonce forte bientôt : " + ", ".join(
            f"{a['titre']} ({N.heure_paris(a['date'])})" for a in proch[:3])
            + " → prudence, réduis le risque ou attends après."]
    if C.SOURCE_PRIX.startswith("Twelve"):
        note_prix = " (prix spot en temps réel)."
    elif C.ECART_MT5:
        note_prix = " (prix Yahoo corrigés de l'écart MT5, ~15 min de retard)."
    else:
        note_prix = " (prix Yahoo : léger écart possible et ~15 min de retard)."
    lignes += ["", "⚠️ Compte DÉMO. Vérifie sur MT5 avant d'entrer" + note_prix]
    return "\n".join(lignes)


def message_test():
    if not C.TELEGRAM_TOKEN or not C.TELEGRAM_CHAT_ID:
        print("❌ Secrets Telegram manquants.")
        return False
    url = f"https://api.telegram.org/bot{C.TELEGRAM_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": C.TELEGRAM_CHAT_ID,
        "text": "✅ Robot SMC Or en ligne sur GitHub : analyse toutes les 15 min, "
                "même quand ton Mac est éteint."}).encode()
    try:
        urllib.request.urlopen(url, data=data, timeout=10)
        print("✅ Message de test Telegram envoyé.")
        return True
    except Exception as ex:
        print(f"❌ Telegram : {ex}")
        return False


def _envoyer(txt):
    url = f"https://api.telegram.org/bot{C.TELEGRAM_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": C.TELEGRAM_CHAT_ID, "text": txt}).encode()
    urllib.request.urlopen(url, data=data, timeout=10)


def _annonces_du_jour(annonces):
    import nouvelles as N
    a = N.prochaines(annonces, heures=16)
    if not a:
        return ""
    return ("📰 Annonces fortes aujourd'hui : "
            + ", ".join(f"{x['titre']} ({N.heure_paris(x['date'])[-5:]})" for x in a)
            + f" — pas d'alerte {C.NEWS_AVANT_MIN} min avant / {C.NEWS_APRES_MIN} min après.\n")


def resume_quotidien(resultats, annonces=None):
    """Point du matin (vers 8h, heure de Paris) pour tous les marchés : [(code, résultat)]."""
    if not C.TELEGRAM_TOKEN or not C.TELEGRAM_CHAT_ID:
        return False
    from zoneinfo import ZoneInfo
    maintenant = datetime.now(ZoneInfo("Europe/Paris"))
    if maintenant.weekday() >= 5 or not (7 <= maintenant.hour < 10):
        return False
    fichier = os.path.join("rapports", "dernier_resume.txt")
    jour = maintenant.strftime("%Y-%m-%d")
    try:
        if open(fichier, encoding="utf-8").read().strip() == jour:
            return False
    except OSError:
        pass
    blocs, devises = [], set()
    for code, r in resultats:
        C.activer(code)
        devises |= set(C.DEVISES_NEWS)
        poi = r["poi"]
        sens = {1: "🟢 haussier", -1: "🔴 baissier", 0: "⚪ neutre"}[r["biais"]]
        blocs.append(f"▪️ {C.NOM_MARCHE} : {C.prix_txt(r['prix'])} | {sens} | note {r['note']} ({r['score']}/100)\n"
                     + (f"   Zone : {poi['nom']} {C.prix_txt(poi['bas'])}–{C.prix_txt(poi['haut'])}\n" if poi else "")
                     + f"   {r['statut']}")
    C.DEVISES_NEWS = sorted(devises)
    txt = ("☀️ Point du matin\n\n" + "\n".join(blocs) + "\n\n" + _annonces_du_jour(annonces)
           + "Le robot tourne et t'alertera dès qu'un setup A ou A+ apparaît.")
    try:
        _envoyer(txt)
        os.makedirs("rapports", exist_ok=True)
        open(fichier, "w", encoding="utf-8").write(jour)
        return True
    except Exception as ex:
        print(f"  (résumé Telegram non envoyé : {ex})")
        return False


def telegram_actif():
    return bool(C.TELEGRAM_TOKEN and C.TELEGRAM_CHAT_ID)


def alerte_telegram(r, e, ordre, annonces=None):
    """Envoie l'alerte. Renvoie True si envoyée (ou si Telegram n'est pas configuré)."""
    txt = message_alerte(r, e, ordre, annonces)
    if not txt:
        return False
    if not telegram_actif():
        print("  (Telegram non configuré : alerte affichée ici seulement)\n" + txt)
        return True
    try:
        _envoyer(txt)
        return True
    except Exception as ex:
        print(f"  (Telegram non envoyé : {ex})")
        return False


def notifier_suivi(changes):
    """Prévient sur Telegram quand un trade du journal avance (entrée, TP, stop…)."""
    for t, evts in changes:
        sens = "ACHAT" if t["sens"] == 1 else "VENTE"
        nom = C.MARCHES.get(t.get("marche", "XAUUSD"), {}).get("nom", "")
        txt = (f"📒 Suivi du trade n°{t['id']} — {nom} ({sens} {t['note']}, alerte du "
               f"{t['date_alerte'][8:10]}/{t['date_alerte'][5:7]})\n" + "\n".join(evts))
        if t["statut"] in ("gagné", "perdu", "break-even"):
            icone = {"gagné": "✅", "perdu": "❌", "break-even": "↩️"}[t["statut"]]
            txt += f"\n{icone} Trade terminé : {t['statut']} ({t['resultat_R']:+.2f} R)"
        print("  " + txt.replace("\n", "\n  "))
        if telegram_actif():
            try:
                _envoyer(txt)
            except Exception as ex:
                print(f"  (Telegram non envoyé : {ex})")


def bilan_hebdo(journal, maintenant=None, forcer=False):
    """Bilan de la semaine, le vendredi soir (après 21h, heure de Paris), une seule fois."""
    import journal as J
    from zoneinfo import ZoneInfo
    m = (maintenant or datetime.now(ZoneInfo("Europe/Paris")))
    m = m.astimezone(ZoneInfo("Europe/Paris"))
    semaine = m.strftime("%G-S%V")
    fichier = os.path.join("rapports", "dernier_bilan.txt")
    if not forcer:
        if m.weekday() != 4 or m.hour < 21:
            return False
        try:
            if open(fichier, encoding="utf-8").read().strip() == semaine:
                return False
        except OSError:
            pass
    debut = (m - timedelta_jours(m.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    sem = [t for t in journal if J._ts(t["date_alerte"]) >= J._ts(debut)]
    txt = J.texte_stats(J.stats(sem), "📊 Bilan de la semaine")
    txt += "\n\n" + J.texte_stats(J.stats(journal), "📚 Depuis le début")
    print("\n" + txt + "\n")
    if not telegram_actif():
        return False
    try:
        _envoyer(txt)
        os.makedirs("rapports", exist_ok=True)
        open(fichier, "w", encoding="utf-8").write(semaine)
        return True
    except Exception as ex:
        print(f"  (bilan Telegram non envoyé : {ex})")
        return False


def timedelta_jours(n):
    from datetime import timedelta
    return timedelta(days=n)


def sauvegarder_json(r, dossier="rapports"):
    os.makedirs(dossier, exist_ok=True)
    resume = {
        "date": datetime.now().isoformat(timespec="minutes"), "prix": r["prix"],
        "biais": r["biais"], "note": r["note"], "score": r["score"], "statut": r["statut"],
        "poi": {k: r["poi"][k] for k in ("nom", "bas", "haut", "score")} if r["poi"] else None,
        "entrees": [{k: e[k] for k in ("nom", "entree", "stop", "rr_final", "lots")} |
                    {"tps": [p for p, _ in e["tps"]]} for e in r["entrees"]],
    }
    with open(os.path.join(dossier, "historique.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(resume, ensure_ascii=False) + "\n")
