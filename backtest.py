#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 BACKTEST — rejoue le robot sur le passé, comme s'il avait tourné en direct.

À chaque pas (par défaut toutes les heures), le robot ne voit QUE les bougies fermées
à ce moment-là. S'il aurait envoyé une alerte, le trade est ajouté puis suivi avec les
bougies suivantes (même gestion que le journal : 50 % au TP1 + stop à l'entrée, etc.).

Utilisation :
    python3 backtest.py                 ~2 mois d'or (limite Yahoo pour le 15 min)
    python3 backtest.py --note B        teste aussi les setups B
    python3 backtest.py --pas 2         une analyse toutes les 30 min (plus long)
    python3 backtest.py --demo          sur des données fictives (test du programme)
    python3 backtest.py --telegram      envoie le résumé sur Telegram

⚠️ Le filtre des annonces n'est pas appliqué (pas d'historique du calendrier),
   et les résultats passés ne garantissent pas les résultats futurs.
"""
import argparse
import csv
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd         # noqa: E402

import config as C          # noqa: E402
import donnees as D         # noqa: E402
import journal as J         # noqa: E402
import rapport as R         # noqa: E402
import strategie as ST      # noqa: E402


def main():
    p = argparse.ArgumentParser(description="Backtest du robot SMC")
    p.add_argument("--pas", type=int, default=4, help="nb de bougies LTF entre 2 analyses (4 = 1h)")
    p.add_argument("--note", choices=["A+", "A", "B"], help="note minimum (défaut : celle de config.py)")
    p.add_argument("--jours", type=int, help="ne tester que les X derniers jours")
    p.add_argument("--marche", default="XAUUSD", choices=sorted(C.MARCHES))
    p.add_argument("--demo", action="store_true", help="données fictives")
    p.add_argument("--telegram", action="store_true", help="envoyer le résumé sur Telegram")
    args = p.parse_args()
    if args.note:
        C.NOTE_MINI_ALERTE = args.note
    C.activer(args.marche)

    h1, ltf, ag = D.demo_brut(jours=90) if args.demo else D.charger_brut()
    dur = D.duree(C.UT_LTF)
    idx = ltf.index.tz_convert("UTC")
    t0 = max(idx[0], h1.index[0].tz_convert("UTC")) + pd.Timedelta(days=30)   # historique minimum
    if args.jours:
        t0 = max(t0, idx[-1] - pd.Timedelta(days=args.jours))
    instants = [t + dur for t in idx[idx >= t0][::args.pas]]
    if not instants:
        sys.exit("❌ Pas assez de données pour un backtest.")

    print(f"🧪 Backtest {C.NOM_MARCHE} du {instants[0]:%d/%m/%Y} au {instants[-1]:%d/%m/%Y} — "
          f"{len(instants)} analyses, alertes à partir de {C.NOTE_MINI_ALERTE}")
    journal, debut = [], time.time()
    for n, T in enumerate(instants, 1):
        data = D.construire(h1, ltf, ag, T)
        if min(len(data[k]) for k in ("htf", "mtf", "ltf")) < 60 or len(data["d1"]) < 25:
            continue
        J.mettre_a_jour(journal, data["ltf_complet"])
        res = ST.analyser(data, T)
        dec = J.setup_a_alerter(res, journal, T)
        if dec:
            e, ordre, cle = dec
            J.ajouter(journal, res, e, ordre, cle, T)
        if n % 50 == 0 or n == len(instants):
            reste = (time.time() - debut) / n * (len(instants) - n)
            print(f"  … {n}/{len(instants)} ({T:%d/%m %Hh}) — {len(journal)} alertes"
                  + (f", ~{reste / 60:.0f} min restantes" if reste > 60 else ""))

    J.mettre_a_jour(journal, D.fermees(ltf, dur, pd.Timestamp.now(tz="UTC")))

    os.makedirs("rapports", exist_ok=True)
    nom = "backtest_demo" if args.demo else f"backtest_{args.marche}"
    J.sauver(journal, os.path.join("rapports", f"{nom}.json"))
    with open(os.path.join("rapports", f"{nom}.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["n°", "date alerte (UTC)", "sens", "note", "score", "méthode", "ordre",
                    "session", "entrée", "stop", "TP", "statut", "résultat R"])
        for t in journal:
            w.writerow([t["id"], t["date_alerte"][:16], "achat" if t["sens"] == 1 else "vente",
                        t["note"], t["score"], t["methode"], t["ordre"], t["session"],
                        t["entree"], t["stop"], " / ".join(map(str, t["tps"])), t["statut"],
                        str(t["resultat_R"]).replace(".", ",")])

    print("\n" + "═" * 66)
    for t in journal:
        print(f"  n°{t['id']:<3} {t['date_alerte'][:16].replace('T', ' ')}  "
              f"{'ACHAT' if t['sens'] == 1 else 'VENTE'} {t['note']:<2}  {t['methode']:<26} "
              f"{t['statut']:<11} {t['resultat_R']:+.2f} R")
    txt = J.texte_stats(J.stats(journal), f"🧪 Backtest {C.NOM_MARCHE} "
                        f"({instants[0]:%d/%m} → {instants[-1]:%d/%m}, setups {C.NOTE_MINI_ALERTE} et +)")
    print("═" * 66 + "\n" + txt)
    print(f"\n  Détail trade par trade : rapports/{nom}.csv (s'ouvre avec Numbers ou Excel)")
    print("  ⚠️ Annonces économiques non filtrées dans le backtest.\n")
    if args.telegram and R.telegram_actif():
        R._envoyer(txt)
        print("  📲 Résumé envoyé sur Telegram.")


if __name__ == "__main__":
    main()
