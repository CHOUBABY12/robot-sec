# -*- coding: utf-8 -*-
import os
"""
RÉGLAGES DU ROBOT : tu peux modifier toutes ces valeurs.
"""

# --- Marché -----------------------------------------------------------------
SYMBOLE = "GC=F"        # Or (COMEX), très proche du XAU/USD de MetaTrader 5
SYMBOLE_SMT = "SI=F"    # Argent : sert à détecter la divergence SMT or/argent
NOM_MARCHE = "OR (XAU/USD)"

# --- Fractalisation : 3 unités de temps (top-down) --------------------------
# HTF = biais | MTF = zones / POI | LTF = confirmation et entrée
UT_HTF = "4h"
UT_MTF = "1h"
UT_LTF = "15m"

# --- Niveaux de structure (nombre de bougies de chaque côté d'un pivot) -----
PIVOT_SWING = 10      # structure swing (majeure)
PIVOT_SUB = 5         # sous-structure
PIVOT_MINEURE = 2     # structure mineure (interne)

# --- Paramètres techniques ---------------------------------------------------
ATR_PERIODE = 14
DISPLACEMENT_ATR = 1.2    # corps de bougie >= 1,2 x ATR = displacement (mouvement institutionnel)
TOLERANCE_EQ_ATR = 0.15   # deux sommets à moins de 0,15 ATR = equal highs (liquidité)
MARGE_SL_ATR = 0.15       # marge ajoutée au stop au-delà de la zone
FVG_MIN_ATR = 0.10        # taille minimale d'un FVG (filtre les micro-gaps)

# --- Fibonacci (convention : 1 = départ de la jambe, 0 = extrême, négatif = extension)
FIB_NIVEAUX = [1.0, 0.79, 0.705, 0.618, 0.5, 0.0, -0.27, -0.618, -1.0]
OTE_HAUT, OTE_BAS = 0.618, 0.79   # Optimal Trade Entry

# --- Gestion du risque -------------------------------------------------------
CAPITAL = 5000.0          # capital du compte démo (5 000 €)
RISQUE_PCT = 1.0          # % du capital risqué par trade
TAILLE_CONTRAT = 100      # 1 lot d'or = 100 onces (1 $ de mouvement = 100 $ par lot)
RR_MINIMUM = 2.0          # ratio gain/risque minimum pour valider un setup

# --- Devise du compte MT5 ---------------------------------------------------
DEVISE_COMPTE = "EUR"     # "EUR" ou "USD"
TAUX_EURUSD = 1.08        # mis à jour automatiquement à chaque analyse
VALIDITE_ORDRE_H = 4      # durée de validité conseillée d'un ordre limite (heures)

# --- Sessions / killzones (heures UTC) ---------------------------------------
SESSIONS_UTC = {
    "Asie": (0, 6),
    "Killzone Londres": (7, 10),
    "Killzone New York": (12, 15),
    "Clôture Londres": (15, 17),
}

# --- Alignement avec ton MetaTrader 5 ----------------------------------------
# Écart de prix : (prix affiché par le robot) - (prix XAU/USD sur ton MT5).
# Exemple : le robot affiche 2 660 et MT5 2 645 → ECART_MT5 = 15.
# Tous les niveaux (entrée, stop, TP) sont alors donnés directement au prix MT5.
# Vérifie-le de temps en temps (il change surtout quand le contrat à terme change).
ECART_MT5 = 0.0
# Fuseau de l'heure serveur de ton broker (pour que les bougies 4h et journalières
# soient découpées comme sur ton MT5). La plupart des brokers sont en GMT+2 l'hiver
# et GMT+3 l'été, ce qui correspond à "Europe/Athens".
FUSEAU_SERVEUR_MT5 = "Europe/Athens"
SPREAD = 0.30             # spread moyen de l'or chez ton broker ($), ajouté au stop

# --- Fenêtre d'analyse (nombre de bougies gardées par UT) ---------------------
FENETRE = {"htf": 700, "mtf": 1500, "ltf": 1200}

# --- Filtre des annonces économiques (NFP, CPI, FOMC…) -----------------------
FILTRE_NEWS = True
NEWS_AVANT_MIN = 30       # pas d'alerte 30 min avant une annonce forte USD
NEWS_APRES_MIN = 30       # … ni 30 min après

# --- Suivi des trades (journal) ----------------------------------------------
PARTIELS = (0.5, 0.3, 0.2)   # part fermée à TP1 / TP2 / TP3 (stop à l'entrée après TP1)
DUREE_MAX_TRADE_H = 72       # au-delà, le trade est considéré clôturé au prix du moment
ANTI_DOUBLON_H = 12          # pas de 2e alerte sur le même POI pendant 12 h

# --- Notifications Telegram (optionnel, laisse vide pour désactiver) --------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")   # secret GitHub
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")  # secret GitHub
NOTE_MINI_ALERTE = "A"    # alerte seulement pour les setups A ou A+
