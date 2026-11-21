# -*- coding: utf-8 -*-
"""
Téléchargement des prix (Yahoo Finance) et données de démonstration.

Améliorations :
- seules les bougies FERMÉES sont analysées (plus de faux BOS/CHoCH sur une bougie en cours)
- les bougies 4h et journalières sont découpées à l'heure serveur de ton MT5
- l'écart de prix Yahoo / MT5 (ECART_MT5) est retiré de tous les prix de l'or
"""
import sys

import numpy as np
import pandas as pd

import config as C

AGG = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}


def _regle(ut: str) -> str:
    """'15m' → '15min' (pandas), '4h' → '4h'."""
    return ut[:-1] + "min" if ut.endswith("m") else ut


def duree(ut: str) -> pd.Timedelta:
    return pd.Timedelta(_regle(ut))


def regrouper(df: pd.DataFrame, regle: str) -> pd.DataFrame:
    return df.resample(_regle(regle)).agg(AGG).dropna()


def regrouper_serveur(df: pd.DataFrame, regle: str) -> pd.DataFrame:
    """Regroupe en suivant l'heure serveur MT5 (bougies 4h / D1 identiques à MT5)."""
    tz = C.FUSEAU_SERVEUR_MT5
    local = df.tz_convert(tz).tz_localize(None)          # heure "murale" du serveur
    x = local.resample(_regle(regle)).agg(AGG).dropna()  # bougies à 0h, 4h, 8h… heure serveur
    x.index = x.index.tz_localize(tz, ambiguous=False, nonexistent="shift_forward")
    return x.tz_convert("Europe/Paris")


def fermees(df, d: pd.Timedelta, maintenant: pd.Timestamp):
    """Garde uniquement les bougies terminées à l'instant `maintenant`."""
    if df is None or df.empty:
        return df
    return df[df.index + d <= maintenant]


def _yahoo(symbole, intervalle, periode):
    try:
        import yfinance as yf
    except ImportError:
        sys.exit("❌ Il manque yfinance. Tape :  pip3 install -r requirements.txt")
    df = yf.download(symbole, period=periode, interval=intervalle,
                     progress=False, auto_adjust=False)
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open", "High", "Low", "Close"]].dropna()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df.index = df.index.tz_convert("Europe/Paris")
    return df


PERIODES = {"1m": "7d", "5m": "59d", "15m": "59d", "30m": "59d", "1h": "729d"}


# ---------------------------------------------------------------------------
# Construction des unités de temps à partir des données brutes
# ---------------------------------------------------------------------------
def _faire_ut(ut, h1, ltf_brut):
    if ut == C.UT_LTF:
        return ltf_brut
    if ut == "1h":
        return h1
    base = h1 if duree(ut) >= pd.Timedelta("1h") else ltf_brut
    return regrouper_serveur(base, ut)


def construire(h1, ltf_brut, ag_h1=None, maintenant=None):
    """
    Prépare les unités de temps pour l'analyse, telles qu'elles étaient à `maintenant`
    (sert aussi au backtest). h1 / ltf_brut / ag_h1 = données brutes 1h, LTF, argent 1h.
    """
    maintenant = maintenant or pd.Timestamp.now(tz="UTC")
    h1 = fermees(h1, pd.Timedelta("1h"), maintenant)
    ltf_brut = fermees(ltf_brut, duree(C.UT_LTF), maintenant)
    d = {}
    for cle, ut in (("htf", C.UT_HTF), ("mtf", C.UT_MTF), ("ltf", C.UT_LTF)):
        df = fermees(_faire_ut(ut, h1, ltf_brut), duree(ut), maintenant)
        d[cle] = df.iloc[-C.FENETRE[cle]:]
    # D1 à l'heure serveur ; la dernière bougie (en cours) est gardée volontairement
    # pour l'open du jour et le CRT (qui utilise les 2 bougies précédentes).
    d["d1"] = regrouper_serveur(h1, "1D").iloc[-450:]
    d["ltf_complet"] = ltf_brut              # pour le suivi des trades du journal
    d["smt"] = None
    if ag_h1 is not None and len(ag_h1):
        ag = fermees(ag_h1, pd.Timedelta("1h"), maintenant)
        ag = ag if C.UT_MTF == "1h" else fermees(regrouper_serveur(ag, C.UT_MTF),
                                                 duree(C.UT_MTF), maintenant)
        d["smt"] = ag.iloc[-C.FENETRE["mtf"]:]
    d["maintenant"] = maintenant
    return d


def _verifier(d):
    for k, mini in (("htf", 60), ("mtf", 60), ("ltf", 60), ("d1", 25)):
        v = d[k]
        if v is None or len(v) < mini:
            sys.exit(f"❌ Données insuffisantes ({k}). Vérifie ta connexion internet "
                     "ou réessaie dans quelques minutes.")
    return d


def _corriger_ecart(df):
    if df is None or not C.ECART_MT5:
        return df
    return df - C.ECART_MT5


# ---------------------------------------------------------------------------
# Twelve Data : prix spot en temps réel (clé gratuite sur twelvedata.com)
# ---------------------------------------------------------------------------
TD_INTERVALLES = {"15m": "15min", "1h": "1h", "5m": "5min", "30m": "30min"}


def _twelvedata(symbole, ut, cle, nb=5000):
    import json
    import urllib.parse
    import urllib.request
    q = urllib.parse.urlencode({"symbol": symbole, "interval": TD_INTERVALLES[ut], "outputsize": nb,
                                "timezone": "UTC", "order": "ASC", "apikey": cle})
    rep = json.loads(urllib.request.urlopen(f"https://api.twelvedata.com/time_series?{q}",
                                            timeout=20).read().decode("utf-8"))
    return _td_vers_df(rep)


def _td_vers_df(rep):
    if rep.get("status") != "ok" or not rep.get("values"):
        raise RuntimeError(rep.get("message", "réponse vide"))
    df = pd.DataFrame(rep["values"])
    df.index = pd.DatetimeIndex(pd.to_datetime(df["datetime"], utc=True)).tz_convert("Europe/Paris")
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"})
    return df[["Open", "High", "Low", "Close"]].astype(float).sort_index()


def charger_twelvedata(cle):
    h1 = _twelvedata("XAU/USD", "1h", cle)
    ltf = _twelvedata("XAU/USD", C.UT_LTF, cle)
    try:
        ag = _twelvedata("XAG/USD", "1h", cle)
    except Exception:
        ag = None
    return h1, ltf, ag


def charger_brut():
    """Télécharge les données brutes : or 1h, or LTF, argent 1h."""
    import os
    cle = os.environ.get("TWELVEDATA_API_KEY", "")
    if cle:
        print("⏳ Téléchargement des données (Twelve Data, temps réel)…")
        try:
            h1, ltf, ag = charger_twelvedata(cle)
            C.SOURCE_PRIX = "Twelve Data (spot, temps réel)"
            _taux_eurusd()
            return h1, ltf, ag
        except Exception as ex:
            print(f"  ⚠️ Twelve Data indisponible ({ex}) → Yahoo Finance en secours.")
    print("⏳ Téléchargement des données (Yahoo Finance, ~15 min de retard)…")
    C.SOURCE_PRIX = "Yahoo Finance (contrat à terme, ~15 min de retard)"
    h1 = _corriger_ecart(_yahoo(C.SYMBOLE, "1h", PERIODES["1h"]))
    ltf = _corriger_ecart(_yahoo(C.SYMBOLE, C.UT_LTF, PERIODES.get(C.UT_LTF, "59d")))
    if h1 is None or ltf is None:
        sys.exit("❌ Impossible de télécharger les prix. Vérifie ta connexion internet "
                 "ou réessaie dans quelques minutes.")
    try:
        ag = _yahoo(C.SYMBOLE_SMT, "1h", PERIODES["1h"])   # facultatif
    except Exception:
        ag = None
    _taux_eurusd()
    return h1, ltf, ag


def _taux_eurusd():
    try:
        fx = _yahoo("EURUSD=X", "1d", "5d")
        if fx is not None and len(fx):
            C.TAUX_EURUSD = float(fx["Close"].iloc[-1])
    except Exception:
        pass


def charger_tout(maintenant=None):
    h1, ltf, ag = charger_brut()
    return _verifier(construire(h1, ltf, ag, maintenant))


# ---------------------------------------------------------------------------
# Données de démonstration (pour tester sans internet)
# ---------------------------------------------------------------------------
def demo_brut(graine: int = 20, jours: int = 60):
    rng = np.random.default_rng(graine)
    n = jours * 96                                # bougies 15 min
    regimes = np.repeat(rng.choice([-1, 1], size=n // 300 + 1) *
                        rng.uniform(0.00005, 0.00018, size=n // 300 + 1), 300)[:n]
    bruit = rng.normal(0, 0.0012, n)
    chocs = rng.choice([0, 1], n, p=[0.985, 0.015]) * rng.normal(0, 0.006, n)
    rend = regimes + bruit + chocs
    close = 2650 * np.exp(np.cumsum(rend))
    open_ = np.r_[close[0], close[:-1]] * (1 + rng.normal(0, 0.0002, n))
    mech = np.abs(rng.normal(0, 1.2, (2, n)))
    high = np.maximum(open_, close) + mech[0]
    low = np.minimum(open_, close) - mech[1]
    fin = pd.Timestamp.now(tz="Europe/Paris").floor("15min")
    idx = pd.date_range(end=fin, periods=n, freq="15min")
    m15 = pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close}, index=idx)
    ag = m15.copy() * (31 / 2650)                 # argent corrélé (pour la SMT)
    ag = ag * (1 + np.cumsum(rng.normal(0, 0.0004, n)))[:, None]
    return regrouper(m15, "1h"), m15, regrouper(ag, "1h")


def charger_demo(graine: int = 20, maintenant=None):
    C.SOURCE_PRIX = "données fictives (démo)"
    h1, m15, ag = demo_brut(graine)
    return construire(h1, m15, ag, maintenant)
