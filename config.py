# -*- coding: utf-8 -*-
import os
"""
RÉGLAGES DU ROBOT : tu peux modifier toutes ces valeurs.
"""

# --- Marchés -----------------------------------------------------------------
# Marchés analysés en direct (alertes Telegram). Un marché n'est ajouté ici que
# s'il a été rentable sur 5 ans de backtest (voir rapports/optimisation_*.md).
MARCHES_ACTIFS = ["XAUUSD"]

# Fiche de chaque marché :
#  yahoo / twelvedata / dukascopy : symboles des sources de prix (None = indisponible)
#  smt : marché corrélé pour la divergence SMT
#  contrat : taille d'un lot (vérifie « Contract size » dans MT5 → clic droit sur le symbole → Specification)
#  decimales : précision d'affichage | spread : spread moyen (en prix) ajouté au stop
#  rond : écart entre deux « nombres ronds » | devises : annonces économiques surveillées
MARCHES = {
    "XAUUSD": dict(nom="OR (XAU/USD)", yahoo="GC=F", twelvedata="XAU/USD", dukascopy="xauusd",
                   smt="XAGUSD", contrat=100, decimales=2, spread=0.30, rond=50,
                   devises=["USD"]),
    "XAGUSD": dict(nom="ARGENT (XAG/USD)", yahoo="SI=F", twelvedata="XAG/USD", dukascopy="xagusd",
                   smt="XAUUSD", contrat=5000, decimales=3, spread=0.03, rond=1,
                   devises=["USD"]),
    "EURUSD": dict(nom="EUR/USD", yahoo="EURUSD=X", twelvedata="EUR/USD", dukascopy="eurusd",
                   smt="GBPUSD", contrat=100000, decimales=5, spread=0.00008, rond=0.01,
                   devises=["USD", "EUR"]),
    "GBPUSD": dict(nom="GBP/USD", yahoo="GBPUSD=X", twelvedata="GBP/USD", dukascopy="gbpusd",
                   smt="EURUSD", contrat=100000, decimales=5, spread=0.00012, rond=0.01,
                   devises=["USD", "GBP"]),
    "NAS100": dict(nom="NASDAQ 100 (NAS100)", yahoo="NQ=F", twelvedata=None, dukascopy="usatechidxusd",
                   smt="US500", contrat=1, decimales=1, spread=1.5, rond=500,
                   devises=["USD"]),
    "US500": dict(nom="S&P 500 (US500)", yahoo="ES=F", twelvedata=None, dukascopy="usa500idxusd",
                  smt="NAS100", contrat=1, decimales=1, spread=0.6, rond=100,
                  devises=["USD"]),
}

# Valeurs du marché en cours d'analyse (remplies par activer())
MARCHE = "XAUUSD"
SYMBOLE = "GC=F"
SYMBOLE_SMT = "SI=F"
NOM_MARCHE = "OR (XAU/USD)"
DECIMALES = 2
ROND = 50
DEVISES_NEWS = ["USD"]

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
TAILLE_CONTRAT = 100      # taille d'un lot (remplie par activer() selon le marché)
RR_MINIMUM = 2.0          # ratio gain/risque minimum pour valider un setup

# --- Devise du compte MT5 ---------------------------------------------------
DEVISE_COMPTE = "EUR"     # "EUR" ou "USD"
TAUX_EURUSD = 1.08        # mis à jour automatiquement à chaque analyse
VALIDITE_ORDRE_H = 8      # durée de validité d'un ordre limite (heures) — 8h retenu par l'optimisation

# --- Sessions / killzones (heures UTC) ---------------------------------------
SESSIONS_UTC = {
    "Asie": (0, 6),
    "Killzone Londres": (7, 10),
    "Killzone New York": (12, 15),
    "Clôture Londres": (15, 17),
}

# --- Alignement avec ton MetaTrader 5 ----------------------------------------
# Source des prix en direct : Twelve Data (spot, temps réel) si le secret GitHub
# TWELVEDATA_API_KEY existe, sinon Yahoo Finance (contrat à terme, ~15 min de retard).
SOURCE_PRIX = "?"
# Écart de prix : (prix affiché par le robot) - (prix XAU/USD sur ton MT5).
# ⚠️ Ne s'applique qu'à Yahoo (contrat à terme). Avec Twelve Data (spot), pas besoin.
# Exemple : le robot affiche 2 660 et MT5 2 645 → ECART_MT5 = 15.
# Tous les niveaux (entrée, stop, TP) sont alors donnés directement au prix MT5.
# Vérifie-le de temps en temps (il change surtout quand le contrat à terme change).
ECART_MT5 = 0.0
ECARTS_MT5 = {"XAUUSD": 0.0}   # écart par marché (seulement avec Yahoo)
# Fuseau de l'heure serveur de ton broker (pour que les bougies 4h et journalières
# soient découpées comme sur ton MT5). La plupart des brokers sont en GMT+2 l'hiver
# et GMT+3 l'été, ce qui correspond à "Europe/Athens".
FUSEAU_SERVEUR_MT5 = "Europe/Athens"
SPREAD = 0.30             # spread moyen (rempli par activer() selon le marché)

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
# Pas d'alerte pendant ces sessions (optimisation sur 2021-2026 : la session
# asiatique fait baisser les résultats). Mets [] pour tout recevoir.
SESSIONS_SANS_ALERTE = ["Asie"]


def activer(code):
    """Charge la fiche d'un marché dans les réglages globaux."""
    global MARCHE, SYMBOLE, SYMBOLE_SMT, NOM_MARCHE, DECIMALES, ROND, DEVISES_NEWS
    global TAILLE_CONTRAT, SPREAD, ECART_MT5
    m = MARCHES[code]
    MARCHE, NOM_MARCHE = code, m["nom"]
    SYMBOLE, SYMBOLE_SMT = m["yahoo"], MARCHES[m["smt"]]["yahoo"] if m.get("smt") else None
    DECIMALES, ROND, DEVISES_NEWS = m["decimales"], m["rond"], m["devises"]
    TAILLE_CONTRAT, SPREAD = m["contrat"], m["spread"]
    ECART_MT5 = ECARTS_MT5.get(code, 0.0)
    return m


def prix_txt(x):
    """Prix formaté selon le marché (2 décimales pour l'or, 5 pour l'EUR/USD…)."""
    return f"{x:.{DECIMALES}f}"
