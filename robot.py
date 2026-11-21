#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🤖 ROBOT D'ANALYSE SMC / ICT — OR (XAU/USD)

Utilisation (dans le Terminal, depuis le dossier du robot) :
    python3 robot.py                    analyse unique + graphiques
    python3 robot.py --boucle 15        analyse toutes les 15 minutes
    python3 robot.py --capital 2000 --risque 0.5
    python3 robot.py --bilan            statistiques du journal des trades
    python3 robot.py --demo             test avec des données fictives (sans internet)

⚠️ Le robot ANALYSE seulement, il ne passe aucun ordre.
"""
import argparse
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
import nouvelles as N       # noqa: E402
import rapport as R         # noqa: E402
import strategie as ST      # noqa: E402


def une_analyse(args):
    maintenant = pd.Timestamp.now(tz="UTC")
    data = D.charger_demo(maintenant=maintenant) if args.demo else D.charger_tout(maintenant)
    res = ST.analyser(data, maintenant)
    R.afficher(res, demo=args.demo)
    if not args.sans_graphique:
        f1 = R.graphique(res, "mtf")
        f2 = R.graphique(res, "ltf", nb=200)
        f3 = R.graphique(res, "htf", nb=150)
        print(f"  📈 Graphiques : {f3}, {f1}, {f2}\n")
    R.sauvegarder_json(res)

    # 1. Suivi des trades déjà alertés (en démo, on ne touche pas au vrai journal)
    fichier = os.path.join("rapports", "journal_demo.json") if args.demo else J.FICHIER
    journal = J.charger(fichier)
    R.notifier_suivi(J.mettre_a_jour(journal, data["ltf_complet"]))

    # 2. Annonces économiques
    annonces = [] if args.demo else N.charger()
    if R.resume_quotidien(res, annonces):
        print("  📲 Point du matin envoyé.\n")

    # 3. Nouvelle alerte ?
    decision = J.setup_a_alerter(res, journal, maintenant)
    if decision:
        e, ordre, cle = decision
        news = N.annonce_proche(annonces, maintenant)
        if news:
            print(f"  📰 Setup {res['note']} ignoré : {news['titre']} à "
                  f"{N.heure_paris(news['date'])} (trop proche d'une annonce forte).\n")
        elif R.alerte_telegram(res, e, ordre, annonces):
            t = J.ajouter(journal, res, e, ordre, cle, maintenant)
            J.simuler(t, data["ltf_complet"])
            print(f"  📲 Alerte envoyée et ajoutée au journal (trade n°{t['id']}).\n")
    J.sauver(journal, fichier)

    # 4. Bilan de la semaine (vendredi soir)
    if not args.demo and R.bilan_hebdo(journal):
        print("  📲 Bilan de la semaine envoyé.\n")
    return res


def main():
    p = argparse.ArgumentParser(description="Robot d'analyse SMC pour l'or")
    p.add_argument("--boucle", type=int, metavar="MIN", help="relancer toutes les X minutes")
    p.add_argument("--capital", type=float, help=f"capital du compte (défaut {C.CAPITAL:g})")
    p.add_argument("--risque", type=float, help=f"%% risqué par trade (défaut {C.RISQUE_PCT:g})")
    p.add_argument("--sans-graphique", action="store_true", help="ne pas créer les images")
    p.add_argument("--test-telegram", action="store_true", help="envoyer un message de test")
    p.add_argument("--bilan", action="store_true", help="afficher (et envoyer) les statistiques")
    p.add_argument("--demo", action="store_true", help="données fictives, sans internet")
    args = p.parse_args()
    if args.capital:
        C.CAPITAL = args.capital
    if args.risque:
        C.RISQUE_PCT = args.risque

    if args.test_telegram:
        sys.exit(0 if R.message_test() else 1)
    if args.bilan:
        R.bilan_hebdo(J.charger(), forcer=True)
        return
    if not args.boucle:
        une_analyse(args)
        return
    print(f"🔁 Analyse toutes les {args.boucle} min — Ctrl+C pour arrêter.")
    try:
        while True:
            try:
                une_analyse(args)
            except SystemExit as ex:          # ex. Yahoo indisponible : on réessaie plus tard
                print(f"  ⚠️ Analyse impossible ({ex}). Nouvel essai dans {args.boucle} min.")
            time.sleep(args.boucle * 60)
    except KeyboardInterrupt:
        print("\n👋 Robot arrêté.")


if __name__ == "__main__":
    main()
