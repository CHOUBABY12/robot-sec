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

# --- Notifications Telegram (optionnel, laisse vide pour désactiver) --------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")   # secret GitHub
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")  # secret GitHub
NOTE_MINI_ALERTE = "A"    # alerte seulement pour les setups A ou A+
