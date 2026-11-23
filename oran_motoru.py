import os
import json
import time
import requests

CACHE_DOSYA = "gercek_oranlar_cache.json"
CACHE_SURE_SN = 3600

LIG_ODDS_MAP = {
    "NBA": "basketball_nba",
    "EuroLeague": "basketball_euroleague",
    "Turkiye Super Lig": "soccer_turkey_super_league",
    "Ingiltere Premier Lig": "soccer_epl",
    "Ispanya La Liga": "soccer_spain_la_liga",
    "Italya Serie A": "soccer_italy_serie_a",
    "Almanya Bundesliga": "soccer_germany_bundesliga",
    "Fransa Ligue 1": "soccer_france_ligue_one",
    "Sampiyonlar Ligi": "soccer_uefa_champs_league",
    "Avrupa Ligi": "soccer_uefa_europa_league",
}


def _api_anahtari_al():
    anahtar = os.environ.get("ODDS_API_KEY", "").strip()
    if not anahtar:
        try:
            import streamlit as st
            anahtar = str(st.secrets.get("ODDS_API_KEY", "")).strip()
        except Exception:
            pass
    return anahtar or "f8be96b3315d2461837ca413e1ae4593"


def _isim_norm(ad):
    s = str(ad).lower().strip()
    for sil in ("fc", "sk", "jk", "fk", "as", "ac", "cf", "sc", "club", "united", "city"):
        s = s.replace(f" {sil}", "").replace(f"{sil} ", "")
    return "".join(c for c in s if c.isalnum())


def gercek_oranlari_getir(lig_adi):
    sport_key = LIG_ODDS_MAP.get(lig_adi, "")
    if not sport_key:
        return {}

    cache = {}
    if os.path.exists(CACHE_DOSYA):
        try:
            with open(CACHE_DOSYA, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            cache = {}

    simdi = time.time()
    lig_kayit = cache.get(sport_key, {})
    if lig_kayit and (simdi - lig_kayit.get("zaman", 0)) < CACHE_SURE_SN:
        return lig_kayit.get("maclar", {})

    api_key = _api_anahtari_al()
    mac_sozluk = {}
    try:
        u = f"https://the-odds-api.com{sport_key}/odds"
        params = {
            "apiKey": api_key,
            "regions": "eu,us",
            "markets": "h2h,totals,alternate_totals",
            "oddsFormat": "decimal",
        }
        r = requests.get(u, params=params, timeout=10)
        if r.status_code != 200:
            params["markets"] = "h2h,totals"
            r = requests.get(u, params=params, timeout=10)

        if r.status_code == 200:
            for ev in r.json():
                ev_ad = ev.get("home_team", "")
                dep_ad = ev.get("away_team", "")
                anahtar = f"{_isim_norm(ev_ad)}_{_isim_norm(dep_ad)}"
                ms1, msx, ms2 = 0.0, 0.0, 0.0
                baremler = {}

                for bk in ev.get("bookmakers", list()):
                    for m in bk.get("markets", list()):
                        mkey = m.get("key", "")
                        if mkey == "h2h" and ms1 == 0.0:
                            for out in m.get("outcomes", list()):
                                nm = out.get("name", "")
                                pr = float(out.get("price", 0) or 0)
                                if nm == ev_ad:
                                    ms1 = pr
                                elif nm == dep_ad:
                                    ms2 = pr
                                elif nm.lower() == "draw":
                                    msx = pr
                        elif mkey in ("totals", "alternate_totals"):
                            for out in m.get("outcomes", list()):
                                nm = out.get("name", "").lower()
                                pr = float(out.get("price", 0) or 0)
                                pt = float(out.get("point", 0) or 0)
                                if pt > 0 and pr > 0:
                                    if pt not in baremler:
                                        baremler[pt] = {"ust": 0.0, "alt": 0.0}
                                    if nm == "over" and baremler[pt]["ust"] == 0.0:
                                        baremler[pt]["ust"] = pr
                                    elif nm == "under" and baremler[pt]["alt"] == 0.0:
                                        baremler[pt]["alt"] = pr

                sirali_baremler = [
                    {"barem": k, "ust": v["ust"], "alt": v["alt"]}
                    for k, v in sorted(baremler.items())
                    if v["ust"] > 0 or v["alt"] > 0
                ]
                ana_b = sirali_baremler[0] if sirali_baremler else {"barem": 0.0, "ust": 0.0, "alt": 0.0}

                if ms1 > 0 or ms2 > 0 or sirali_baremler:
                    mac_sozluk[anahtar] = {
                        "ev": ev_ad,
                        "dep": dep_ad,
                        "ms1": ms1,
                        "msx": msx,
                        "ms2": ms2,
                        "barem": ana_b["barem"],
                        "ust": ana_b["ust"],
                        "alt": ana_b["alt"],
                        "tum_baremler": sirali_baremler,
                    }
            cache[sport_key] = {"zaman": simdi, "maclar": mac_sozluk}
            with open(CACHE_DOSYA, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        return lig_kayit.get("maclar", {})

    return mac_sozluk


def mac_oran_bul(lig_adi, ev_ad, dep_ad):
    maclar = gercek_oranlari_getir(lig_adi)
    if not maclar:
        return None
    k1 = _isim_norm(ev_ad)
    k2 = _isim_norm(dep_ad)
    tam = f"{k1}_{k2}"
    if tam in maclar:
        return maclar[tam]
    for anahtar, veri in maclar.items():
        if (k1[:5] and k1[:5] in anahtar) and (k2[:5] and k2[:5] in anahtar):
            return veri
    return None
