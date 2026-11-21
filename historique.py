#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📚 HISTORIQUE DUKASCOPY (or spot XAU/USD, comme sur MT5)

Plusieurs années de bougies 15 min / 1h, gratuites, pour des backtests fiables.
Téléchargement (sur GitHub : Actions → « Données historiques » → Run workflow) :
    python3 historique.py telecharger --debut 2021-01-01
    python3 historique.py mettre-a-jour        (ajoute seulement les jours manquants)
    python3 historique.py info                 (ce qui est déjà téléchargé)
Nécessite Node.js (npx dukascopy-node).
"""
import argparse
import glob
import os
import subprocess
import sys
import tempfile

import pandas as pd

DOSSIER = "data"
# (instrument Dukascopy, unité de temps) → fichier
SERIES = {
    ("xauusd", "m15"): "xauusd_m15.csv.gz",
    ("xauusd", "h1"): "xauusd_h1.csv.gz",
    ("xagusd", "m15"): "xagusd_m15.csv.gz",
    ("xagusd", "h1"): "xagusd_h1.csv.gz",          # argent (et SMT de l'or)
    ("eurusd", "m15"): "eurusd_m15.csv.gz",
    ("eurusd", "h1"): "eurusd_h1.csv.gz",
    ("gbpusd", "m15"): "gbpusd_m15.csv.gz",
    ("gbpusd", "h1"): "gbpusd_h1.csv.gz",
    ("usatechidxusd", "m15"): "nas100_m15.csv.gz",  # Nasdaq 100
    ("usatechidxusd", "h1"): "nas100_h1.csv.gz",
    ("usa500idxusd", "h1"): "us500_h1.csv.gz",      # S&P 500 (SMT du Nasdaq)
}


def chemin(instrument, tf):
    return os.path.join(DOSSIER, SERIES[(instrument, tf)])


def _index(col):
    """Colonne timestamp (millisecondes ou texte) → DatetimeIndex en heure de Paris."""
    if pd.api.types.is_numeric_dtype(col):
        idx = pd.to_datetime(col.to_numpy(), unit="ms", utc=True)
    else:
        idx = pd.to_datetime(col.to_numpy(), utc=True)
    return pd.DatetimeIndex(idx).tz_convert("Europe/Paris")


def lire(instrument, tf):
    """DataFrame Open/High/Low/Close, index en heure de Paris (ou None)."""
    f = chemin(instrument, tf)
    if not os.path.exists(f):
        return None
    df = pd.read_csv(f)
    df.index = _index(df["timestamp"])
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"})
    df = df[["Open", "High", "Low", "Close"]].sort_index()
    # Dukascopy remplit les week-ends et la pause quotidienne avec des bougies « plates »
    # (ouverture = plus haut = plus bas = clôture) : on les retire, elles fausseraient l'ATR.
    return df[df["High"] > df["Low"]]


def _ecrire(instrument, tf, df):
    os.makedirs(DOSSIER, exist_ok=True)
    out = pd.DataFrame({"timestamp": df.index.tz_convert("UTC").as_unit("ms").asi8,
                        "open": df["Open"].round(3), "high": df["High"].round(3),
                        "low": df["Low"].round(3), "close": df["Close"].round(3)})
    out.to_csv(chemin(instrument, tf), index=False, compression="gzip")


def _npx(instrument, tf, debut, fin, dossier):
    cmd = ["npx", "--yes", "dukascopy-node", "-i", instrument, "-from", debut, "-to", fin,
           "-t", tf, "-f", "csv", "-dir", dossier, "-fn", f"{instrument}_{tf}_{debut}",
           "-r", "5", "-rp", "2000", "-bs", "8", "-bp", "800", "-s"]
    print("  $ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)
    fichiers = glob.glob(os.path.join(dossier, f"{instrument}_{tf}_{debut}*.csv"))
    if not fichiers:
        raise RuntimeError("aucun fichier produit")
    df = pd.read_csv(fichiers[0])
    os.remove(fichiers[0])
    return df


def telecharger(instrument, tf, debut, fin="now"):
    """Télécharge par tranches d'un an (plus fiable) et fusionne avec l'existant."""
    debut_ts = pd.Timestamp(debut)
    fin_ts = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize() + pd.Timedelta(days=1) \
        if fin == "now" else pd.Timestamp(fin)
    morceaux = []
    with tempfile.TemporaryDirectory() as tmp:
        a = debut_ts
        while a < fin_ts:
            b = min(a + pd.DateOffset(years=1), fin_ts)
            print(f"📥 {instrument} {tf} : {a:%Y-%m-%d} → {b:%Y-%m-%d}", flush=True)
            raw = _npx(instrument, tf, f"{a:%Y-%m-%d}", f"{b:%Y-%m-%d}", tmp)
            print(f"   {len(raw)} bougies", flush=True)
            morceaux.append(raw)
            a = b
    raw = pd.concat(morceaux)
    raw.index = _index(raw["timestamp"])
    raw = raw.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"})
    nouveau = raw[["Open", "High", "Low", "Close"]]
    ancien = lire(instrument, tf)
    tout = nouveau if ancien is None else pd.concat([ancien, nouveau])
    tout = tout[~tout.index.duplicated(keep="last")].sort_index().dropna()
    _ecrire(instrument, tf, tout)
    print(f"✅ {chemin(instrument, tf)} : {len(tout)} bougies "
          f"({tout.index[0]:%d/%m/%Y} → {tout.index[-1]:%d/%m/%Y})", flush=True)


def info():
    for (ins, tf), _ in SERIES.items():
        df = lire(ins, tf)
        if df is None:
            print(f"  {ins} {tf} : pas encore téléchargé")
        else:
            print(f"  {ins} {tf} : {len(df)} bougies, du {df.index[0]:%d/%m/%Y} au {df.index[-1]:%d/%m/%Y}")


def main():
    p = argparse.ArgumentParser(description="Historique Dukascopy")
    p.add_argument("action", choices=["telecharger", "mettre-a-jour", "info"])
    p.add_argument("--debut", default="2021-01-01")
    p.add_argument("--instruments", default="", help="ex. xagusd,eurusd (vide = tous)")
    a = p.parse_args()
    choix = [x.strip() for x in a.instruments.split(",") if x.strip()]
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    if a.action == "info":
        info()
        return
    for (ins, tf) in SERIES:
        if choix and ins not in choix:
            continue
        debut = a.debut
        if a.action == "mettre-a-jour":
            df = lire(ins, tf)
            if df is not None:
                debut = (df.index[-1].tz_convert("UTC") - pd.Timedelta(days=2)).strftime("%Y-%m-%d")
        try:
            telecharger(ins, tf, debut)
        except Exception as ex:
            sys.exit(f"❌ Échec du téléchargement {ins} {tf} : {ex}")


if __name__ == "__main__":
    main()
