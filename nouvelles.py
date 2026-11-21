# -*- coding: utf-8 -*-
"""
ANNONCES ÉCONOMIQUES (NFP, CPI, FOMC…)
Calendrier de la semaine (Forex Factory), annonces USD à fort impact uniquement.
Si le calendrier n'est pas joignable, le robot continue normalement (sans filtre).
"""
import json
import time
import urllib.request
from datetime import datetime, timedelta, timezone

import config as C

URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
_cache = {"t": 0.0, "annonces": None}


def charger(forcer=False):
    """Annonces fortes de la semaine : [{'titre', 'devise', 'date' (UTC)}] (toutes devises)."""
    if not C.FILTRE_NEWS:
        return []
    if not forcer and _cache["annonces"] is not None and time.time() - _cache["t"] < 3 * 3600:
        return _cache["annonces"]
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "robot-smc/1.0"})
        brut = json.loads(urllib.request.urlopen(req, timeout=10).read().decode("utf-8"))
        res = []
        for ev in brut:
            if ev.get("impact") != "High":
                continue
            try:
                d = datetime.fromisoformat(ev["date"]).astimezone(timezone.utc)
            except (KeyError, ValueError):
                continue
            res.append({"titre": f"{ev.get('country', '')} {ev.get('title', 'Annonce')}".strip(),
                        "devise": ev.get("country", ""), "date": d})
        res.sort(key=lambda a: a["date"])
        _cache.update(t=time.time(), annonces=res)
    except Exception as ex:
        print(f"  (calendrier économique indisponible : {ex})")
        if _cache["annonces"] is None:
            _cache.update(t=time.time() - 2.5 * 3600, annonces=[])   # réessai dans 30 min
    return _cache["annonces"]


def _utc(m):
    if m is None:
        return datetime.now(timezone.utc)
    if hasattr(m, "to_pydatetime"):
        m = m.to_pydatetime()
    return m.astimezone(timezone.utc)


def _du_marche(annonces):
    """Annonces qui concernent le marché en cours (USD pour l'or, USD + EUR pour l'EUR/USD…)."""
    return [a for a in annonces or [] if a.get("devise", "USD") in C.DEVISES_NEWS]


def annonce_proche(annonces, maintenant=None):
    """Annonce forte dans la fenêtre interdite (avant / après), sinon None."""
    m = _utc(maintenant)
    for a in _du_marche(annonces):
        if a["date"] - timedelta(minutes=C.NEWS_AVANT_MIN) <= m <= a["date"] + timedelta(minutes=C.NEWS_APRES_MIN):
            return a
    return None


def prochaines(annonces, maintenant=None, heures=24):
    m = _utc(maintenant)
    return [a for a in _du_marche(annonces) if m <= a["date"] <= m + timedelta(hours=heures)]


def heure_paris(d):
    from zoneinfo import ZoneInfo
    return d.astimezone(ZoneInfo("Europe/Paris")).strftime("%a %d/%m %H:%M") \
        .replace("Mon", "lun").replace("Tue", "mar").replace("Wed", "mer") \
        .replace("Thu", "jeu").replace("Fri", "ven").replace("Sat", "sam").replace("Sun", "dim")
