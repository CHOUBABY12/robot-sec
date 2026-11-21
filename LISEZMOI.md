# 🤖 Robot d'analyse SMC / ICT : Or (XAU/USD)

Le robot analyse l'or sur 3 unités de temps (4h, 1h, 15m) avec les Smart Money Concepts.
Il te donne un biais, un POI, une note de setup (A+, A, B ou C) et des entrées avec stop et objectifs.
**Il ne passe aucun ordre** : tu restes maîtresse de tes décisions sur MetaTrader 5.

---

## 1. Installation (une seule fois, sur ton Mac)

1. **Installe Python** : va sur https://www.python.org/downloads/, télécharge la dernière version pour macOS et installe-la (suivant, suivant…).
2. **Place le dossier** `robot_smc` où tu veux, par exemple dans `Documents`.
3. **Ouvre le Terminal** (Cmd + Espace, tape « Terminal », Entrée).
4. Va dans le dossier du robot (adapte le chemin) :
   ```
   cd ~/Documents/robot_smc
   ```
5. Installe les bibliothèques :
   ```
   pip3 install -r requirements.txt
   ```

## 2. Lancer le robot

Dans le Terminal, depuis le dossier du robot :

| Commande | Effet |
|---|---|
| `python3 robot.py` | Une analyse complète + 3 graphiques |
| `python3 robot.py --boucle 15` | Relance l'analyse toutes les 15 min (Ctrl + C pour arrêter) |
| `python3 robot.py --capital 500 --risque 1` | Calcule la taille de lot pour ton compte |
| `python3 robot.py --bilan` | Statistiques du journal des trades (taux de réussite, R gagnés…) |
| `python3 backtest.py` | Rejoue le robot sur les ~2 derniers mois pour voir ce qu'il aurait gagné |
| `python3 robot.py --demo` | Test avec des données fictives (sans internet) |

**Plus simple** : double-clique sur `lancer_robot.command`.
La première fois, si le Mac bloque le fichier, fais clic droit → Ouvrir → Ouvrir.

Les graphiques et l'historique des analyses sont enregistrés dans le dossier `rapports/`.

## 3. Lire le rapport

1. **Market structure** : la tendance swing / sub / mineure sur chaque UT (fractalisation) et le dernier BOS/CHoCH avec son type (fort, faible, piège).
2. **Premium / Discount** : la jambe active avec son Fibonacci (1 = départ, 0,5 = équilibre, 0 = extrême, négatif = extensions), la zone actuelle et la condition de retracement.
3. **Liquidité** : inducement, dernière liquidité avant le POI, liquidité cachée, resting liquidity (BSL/SSL), equal highs/lows, trendline, sweeps et pièges.
4. **POI** : la meilleure zone (OB, FVG, Supply/Demand, breaker, flip) avec sa formation, sa qualité, son raffinement en 15m et la confirmation.
5. **Key levels et outils** : PDH/PDL, PWH/PWL, opens, session Asie, nombres ronds, CRT, SMT or/argent, killzone.
6. **Checklist** : le score de confluence sur 100.
7. **Entrées** : agressive, 50 % du POI, raffinée (sniper) et sur confirmation, avec TP1/TP2/TP3, le ratio et la taille de lot.

**Notes** : A+ (≥ 80), A (≥ 65), B (≥ 50), C (pas de trade).

## 4. Concepts intégrés

- **Structure** : pivots fractals à 3 niveaux (swing 10, sub 5, mineure 2 bougies), HH/HL/LH/LL, BOS (fort/displacement, faible, piège), CHoCH, condition de retracement (prise du bas ou du haut de la bougie précédente).
- **Premium/Discount** : Fibonacci du low au high (ou du HL au HH) en haussier, du high au low (ou du LH au LL) en baissier, OTE 0,618–0,79, extensions -0,27 / -0,618 / -1.
- **Zones** : Order Blocks (extrême, décisionnel, breaker, mitigation ; formations 1 bougie, multi-bougies, engulfing, avec FVG, avec prise de liquidité ; mean threshold ; version raffinée au corps), FVG / IFVG, Supply & Demand (RBR, DBR, DBD, RBD), flips SD/DS.
- **Liquidité** : inducement, liquidity trap, sweeps, liquidité cachée, dernière liquidité, resting liquidity, EQH/EQL, double top/bottom, trendline.
- **Outils** : key levels, sessions et killzones, CRT (D1 et 4h), SMT or/argent, gestion du risque.
- **Entrées** : risk entry, mean threshold, raffinée/sniper, confirmation (CHoCH/BOS en LTF).

## 5. Personnaliser

Ouvre `config.py` avec TextEdit ou VS Code pour changer : les unités de temps, la taille des pivots, ton capital, ton % de risque, le ratio minimum…

### Alertes sur ton iPhone (Telegram, facultatif)
1. Dans Telegram, écris à **@BotFather** → `/newbot` → il te donne un **token**.
2. Écris un message à ton nouveau bot, puis ouvre dans un navigateur :
   `https://api.telegram.org/bot<TON_TOKEN>/getUpdates` et note le nombre après `"chat":{"id":`.
3. Colle le token et l'id dans `config.py` (`TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`).
4. Lance `python3 robot.py --boucle 15` : tu reçois une alerte à chaque setup A ou A+.

## 6. Journal des trades, bilan et backtest

- **Journal** : chaque alerte envoyée est enregistrée dans `rapports/journal.json`. À chaque analyse,
  le robot regarde ce que le prix a fait : ordre déclenché, TP1/TP2/TP3 touchés, stop… et t'envoie
  un message de suivi sur Telegram. Gestion simulée : 50 % fermés au TP1 + stop à l'entrée,
  30 % au TP2, le reste au TP3. Un ordre non déclenché en 4 h, ou si le prix part au TP1 sans
  lui, est compté « annulé ».
- **Bilan** : chaque vendredi soir (après 21h), un bilan de la semaine et depuis le début arrive
  sur Telegram (taux de réussite, résultat en R et en €, par note, par session, par méthode).
- **Backtest** : sur GitHub, onglet **Actions** → **Backtest** → **Run workflow**. Choisis la note
  minimum (A, A+ ou B). Le résumé arrive sur Telegram et le détail se télécharge en bas de la page
  (`resultats-backtest`). Limite : Yahoo ne donne que ~2 mois de bougies 15 min.

## 7. Optimisation sur plusieurs années

1. **Données** : Actions → **Données historiques (Dukascopy)** → Run workflow (`mettre-a-jour`
   ajoute les jours manquants). 5 ans d'or spot en 15 min sont dans le dossier `data/`.
2. **Optimisation** : Actions → **Optimisation** → Run workflow. Le robot analyse chaque année en
   parallèle (~15 min), puis 675 réglages sont comparés. Ils sont classés sur 2021-2024
   (apprentissage) puis vérifiés sur 2025-2026 (vérification, jamais vue par le classement).
   Le rapport est dans `rapports/optimisation.md` et un résumé arrive sur Telegram.
3. **Comparer à nouveau** : pour tester d'autres réglages sans recalculer les signaux.

⚠️ Le backtest ne compte ni le glissement (slippage) ni les commissions (seul le spread est
ajouté au stop) : les vrais résultats seront un peu moins bons.

## 8. Prix en temps réel (Twelve Data, gratuit)

1. Crée un compte gratuit sur https://twelvedata.com (plan Basic, sans carte bancaire).
2. Copie ta clé API (Dashboard → API Keys).
3. Sur GitHub : ton dépôt → **Settings** → **Secrets and variables** → **Actions** →
   **New repository secret**. Nom : `TWELVEDATA_API_KEY`, valeur : ta clé.
4. C'est tout : le robot utilise alors le prix spot sans retard (Yahoo reste en secours).
   Avec Twelve Data, laisse `ECART_MT5 = 0`.

## 9. Réglages à faire une fois

- **`ECART_MT5`** (seulement sans Twelve Data) : compare le prix d'une alerte avec le prix XAU/USD de ton MT5 au même moment.
  Si le robot dit 2 660 et MT5 2 645, mets `ECART_MT5 = 15`. Tous les niveaux seront alors au prix MT5.
- **`FUSEAU_SERVEUR_MT5`** : heure serveur de ton broker (par défaut GMT+2/+3 = `"Europe/Athens"`),
  pour que les bougies 4h et journalières soient les mêmes que sur ton MT5.
- **`SPREAD`** : spread moyen de l'or chez ton broker, ajouté au stop.
- **Annonces** : pas d'alerte 30 min avant / après une annonce forte USD (NFP, CPI, FOMC…).
  Les annonces du jour sont listées dans le point du matin.

## 10. Bon à savoir

- Le robot n'analyse que les bougies **fermées** : un BOS/CHoCH n'est validé qu'à la clôture.

- Les prix viennent de Yahoo Finance (contrat à terme or `GC=F`). Ils peuvent différer de quelques dollars du XAU/USD de ton broker MT5 et ont environ 10 à 15 minutes de retard. Vérifie toujours les niveaux sur ton graphique MT5 avant d'entrer.
- Avec 1 000 $ et 1 % de risque, tu ne risques que 10 $ par trade : les stops larges donnent souvent « moins de 0,01 lot ». Dans ce cas, privilégie l'entrée raffinée ou passe ton tour.
- C'est un outil d'aide à la décision, **pas un conseil financier**. Teste-le plusieurs semaines en **compte démo** et note les résultats avant d'engager de l'argent réel.
