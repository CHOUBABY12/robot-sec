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
    return f"{x:,.2f}".replace(",", " ")


def _dev():
    return "€" if C.DEVISE_COMPTE == "EUR" else "$"


def _titre(t):
    print("\n" + f"── {t} ".ljust(L, "─"))


def afficher(r, demo=False):
    icone = {1: "🟢 HAUSSIER", -1: "🔴 BAISSIER", 0: "⚪ NEUTRE"}
    print("\n" + "═" * L)
    print(f"  🤖 ROBOT SMC — {C.NOM_MARCHE}   {datetime.now():%d/%m/%Y %H:%M}" + ("  [DÉMO]" if demo else ""))
    print("═" * L)
    print(f"  Prix : {_p(r['prix'])} $    ATR {C.UT_MTF} : {r['mtf']['atr_der']:.2f} $")
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
              f" (risque {abs(e['entree'] - e['stop']):.2f} $)")
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
    fichier = os.path.join(dossier, f"analyse_{a['nom']}.png")
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


def message_alerte(r):
    from datetime import timedelta
    e = choisir_entree(r)
    if e is None:
        return None, None
    s = r["sens"]
    ordre = type_ordre(s, e["entree"], r["prix"], r["ltf"]["atr_der"])
    risque_pts = abs(e["entree"] - e["stop"])
    fin = (datetime.now() + timedelta(hours=C.VALIDITE_ORDRE_H)).strftime("%H:%M")
    poi = r["poi"]
    invalid = poi["haut"] if s == -1 else poi["bas"]
    lignes = [
        f"🤖 {C.NOM_MARCHE} — SETUP {r['note']} ({r['score']}/100)",
        f"{'🟢 ACHAT' if s == 1 else '🔴 VENTE'} — ordre {ordre}",
        f"Méthode : {e['nom']}",
        "",
        f"📍 Entrée : {e['entree']:.2f}   (prix actuel {r['prix']:.2f})",
        f"🛑 Stop loss : {e['stop']:.2f}   (risque {risque_pts:.2f} $/once)",
    ]
    for k, ((p, n), rr) in enumerate(zip(e["tps"], e["rr"]), 1):
        lignes.append(f"🎯 TP{k} : {p:.2f}   (1:{rr:.1f}) — {n}")
    lignes += [
        "",
        f"📦 Lot : {e['lots']:.2f}  → risque ≈ {e['risque_usd']:.0f} {_dev()} ({C.RISQUE_PCT:g} %)"
        if e["lots"] >= 0.01 else "📦 Lot : stop trop large pour ton risque → passe ton tour",
        "",
        "📋 Gestion :",
        "• Au TP1 : ferme 50 % et remonte le stop à l'entrée (break-even)",
        "• Au TP2 : ferme 30 %, laisse courir le reste vers TP3",
        f"• Ordre valable jusqu'à {fin} : annule-le s'il n'est pas déclenché",
        f"• Setup invalidé si une bougie {C.UT_MTF} clôture {'sous' if s == 1 else 'au-dessus de'} {invalid:.2f}",
        "",
        f"🔎 POI : {poi['nom']} {poi['bas']:.2f}–{poi['haut']:.2f}",
        "✅ " + " | ".join(t for ok, t, _ in r["check"] if ok)[:300],
        f"ℹ️ {r['statut']}",
        "",
        "⚠️ Compte DÉMO. Vérifie sur MT5 (léger écart de prix possible) avant d'entrer.",
    ]
    cle = f"{r['note']}|{s}|{round(e['entree'], 0)}"
    return "\n".join(lignes), cle


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


def alerte_telegram(r):
    if not C.TELEGRAM_TOKEN or not C.TELEGRAM_CHAT_ID:
        return False
    ordre = ["C", "B", "A", "A+"]
    if ordre.index(r["note"]) < ordre.index(C.NOTE_MINI_ALERTE):
        return False
    txt, cle = message_alerte(r)
    if not txt:
        return False
    fichier_cle = os.path.join("rapports", "derniere_alerte.txt")
    try:
        if open(fichier_cle, encoding="utf-8").read().strip() == cle:
            return False
    except OSError:
        pass
    url = f"https://api.telegram.org/bot{C.TELEGRAM_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": C.TELEGRAM_CHAT_ID, "text": txt}).encode()
    try:
        urllib.request.urlopen(url, data=data, timeout=10)
        os.makedirs("rapports", exist_ok=True)
        with open(fichier_cle, "w", encoding="utf-8") as f:
            f.write(cle)
        return True
    except Exception as ex:
        print(f"  (Telegram non envoyé : {ex})")
        return False


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
