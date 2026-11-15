#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🤖 ROBOT D'ANALYSE SMC / ICT — OR (XAU/USD)

Utilisation (dans le Terminal, depuis le dossier du robot) :
    python3 robot.py                    analyse unique + graphiques
    python3 robot.py --boucle 15        analyse toutes les 15 minutes
    python3 robot.py --capital 2000 --risque 0.5
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

import config as C          # noqa: E402
import donnees as D         # noqa: E402
import rapport as R         # noqa: E402
import strategie as ST      # noqa: E402


def une_analyse(args):
    data = D.charger_demo() if args.demo else D.charger_tout()
    res = ST.analyser(data)
    R.afficher(res, demo=args.demo)
    if not args.sans_graphique:
        f1 = R.graphique(res, "mtf")
        f2 = R.graphique(res, "ltf", nb=200)
        f3 = R.graphique(res, "htf", nb=150)
        print(f"  📈 Graphiques : {f3}, {f1}, {f2}\n")
    R.sauvegarder_json(res)
    if R.alerte_telegram(res):
        print("  📲 Alerte Telegram envoyée.\n")
    return res


def main():
    p = argparse.ArgumentParser(description="Robot d'analyse SMC pour l'or")
    p.add_argument("--boucle", type=int, metavar="MIN", help="relancer toutes les X minutes")
    p.add_argument("--capital", type=float, help=f"capital du compte (défaut {C.CAPITAL:g} $)")
    p.add_argument("--risque", type=float, help=f"%% risqué par trade (défaut {C.RISQUE_PCT:g})")
    p.add_argument("--sans-graphique", action="store_true", help="ne pas créer les images")
    p.add_argument("--test-telegram", action="store_true", help="envoyer un message de test")
    p.add_argument("--demo", action="store_true", help="données fictives, sans internet")
    args = p.parse_args()
    if args.capital:
        C.CAPITAL = args.capital
    if args.risque:
        C.RISQUE_PCT = args.risque

    if args.test_telegram:
        sys.exit(0 if R.message_test() else 1)
    if not args.boucle:
        une_analyse(args)
        return
    print(f"🔁 Analyse toutes les {args.boucle} min — Ctrl+C pour arrêter.")
    try:
        while True:
            une_analyse(args)
            time.sleep(args.boucle * 60)
    except KeyboardInterrupt:
        print("\n👋 Robot arrêté.")


if __name__ == "__main__":
    main()
