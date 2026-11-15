# -*- coding: utf-8 -*-
"""Téléchargement des prix (Yahoo Finance) et données de démonstration."""
import sys

import numpy as np
import pandas as pd

import config as C

AGG = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}


def regrouper(df: pd.DataFrame, regle: str) -> pd.DataFrame:
    return df.resample(regle).agg(AGG).dropna()


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


def _charger_ut(symbole, ut):
    """Récupère une unité de temps ; 4h est reconstruit à partir du 1h."""
    if ut == "4h":
        h1 = _yahoo(symbole, "1h", "729d")
        return None if h1 is None else regrouper(h1, "4h")
    periodes = {"1m": "7d", "5m": "59d", "15m": "59d", "30m": "59d",
                "1h": "729d", "1d": "5y"}
    return _yahoo(symbole, ut, periodes.get(ut, "60d"))


def charger_tout():
    print("⏳ Téléchargement des données…")
    d = {
        "htf": _charger_ut(C.SYMBOLE, C.UT_HTF),
        "mtf": _charger_ut(C.SYMBOLE, C.UT_MTF),
        "ltf": _charger_ut(C.SYMBOLE, C.UT_LTF),
        "d1": _charger_ut(C.SYMBOLE, "1d"),
    }
    for k, v in d.items():
        if v is None or len(v) < 60:
            sys.exit(f"❌ Données insuffisantes ({k}). Vérifie ta connexion internet "
                     "ou réessaie dans quelques minutes.")
    d["smt"] = _charger_ut(C.SYMBOLE_SMT, C.UT_MTF)   # facultatif
    try:
        fx = _yahoo("EURUSD=X", "1d", "5d")
        if fx is not None and len(fx):
            C.TAUX_EURUSD = float(fx["Close"].iloc[-1])
    except Exception:
        pass
    return d


# ---------------------------------------------------------------------------
# Données de démonstration (pour tester sans internet)
# ---------------------------------------------------------------------------
def charger_demo(graine: int = 20):
    rng = np.random.default_rng(graine)
    n = 60 * 96                                   # 60 jours de bougies 15 min
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

    # Argent corrélé (pour la SMT)
    ag = m15.copy() * (31 / 2650)
    ag = ag * (1 + np.cumsum(rng.normal(0, 0.0004, n)))[:, None]

    return {
        "htf": regrouper(m15, "4h"),
        "mtf": regrouper(m15, "1h"),
        "ltf": m15,
        "d1": regrouper(m15, "1D"),
        "smt": regrouper(ag, "1h"),
    }
