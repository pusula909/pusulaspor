import json
import os
import re
import time
from datetime import datetime, timezone
import requests
import streamlit as st

TARAYICI_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
}

LIG_ESPN_YOLLARI = {
    "NBA": "basketball/nba",
    "EuroLeague": "basketball/euroleague",
    "Trendyol Super Lig": "soccer/tur.1",
    "Turkiye Super Lig": "soccer/tur.1",
    "Ingiltere Premier Lig": "soccer/eng.1",
    "Ispanya La Liga": "soccer/esp.1",
    "Italya Serie A": "soccer/ita.1",
    "Almanya Bundesliga": "soccer/ger.1",
    "Fransa Ligue 1": "soccer/fra.1",
    "Sampiyonlar Ligi": "soccer/uefa.champions",
    "Avrupa Ligi": "soccer/uefa.europa",
    "Isvec Allsvenskan": "soccer/swe.1",
    "Hollanda Eredivisie": "soccer/ned.1",
    "Portekiz Primeira Liga": "soccer/por.1",
}

LIG_ODDS_MAP = {
    "NBA": "basketball_nba",
    "EuroLeague": "basketball_euroleague",
    "Trendyol Super Lig": "soccer_turkey_super_league",
    "Turkiye Super Lig": "soccer_turkey_super_league",
    "Ingiltere Premier Lig": "soccer_epl",
    "Ispanya La Liga": "soccer_spain_la_liga",
    "Italya Serie A": "soccer_italy_serie_a",
    "Almanya Bundesliga": "soccer_germany_bundesliga",
    "Fransa Ligue 1": "soccer_france_ligue_one",
    "Sampiyonlar Ligi": "soccer_uefa_champs_league",
    "Avrupa Ligi": "soccer_uefa_europa_league",
}


def _us_to_decimal(us_oran):
    try:
        val = float(str(us_oran).replace("+", "").strip())
        if val == 0:
            return 0.0
        if val > 0:
            return round(1.0 + (val / 100.0), 2)
        return round(1.0 + (100.0 / abs(val)), 2)
    except Exception:
        return 0.0


def _isim_norm(ad):
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    s = str(ad).translate(tr_map).lower().strip()
    for sil in ("fc", "sk", "jk", "fk", "as", "ac", "cf", "sc", "if", "ff", "ik", "bk", "club", "united", "city", "istanbul", "calcio", "ud", "cd", "rcd"):
        s = s.replace(f" {sil}", "").replace(f"{sil} ", "")
    return "".join(c for c in s if c.isalnum())


def _yol_coz(lig_adi, lig_yolu=""):
    if lig_yolu and "/" in str(lig_yolu):
        return str(lig_yolu).strip()
    if lig_adi in LIG_ESPN_YOLLARI:
        return LIG_ESPN_YOLLARI[lig_adi]
    for k, v in LIG_ESPN_YOLLARI.items():
        if k.lower() in str(lig_adi).lower() or str(lig_adi).lower() in k.lower():
            return v
    return ""


def _odds_key_coz(lig_adi):
    if lig_adi in LIG_ODDS_MAP:
        return LIG_ODDS_MAP[lig_adi]
    for k, v in LIG_ODDS_MAP.items():
        if k.lower() in str(lig_adi).lower() or str(lig_adi).lower() in k.lower():
            return v
    return ""


def _odds_ayristir(od):
    if not isinstance(od, dict):
        return None
    ms1 = _us_to_decimal(od.get("homeTeamOdds", {}).get("moneyLine", 0))
    ms2 = _us_to_decimal(od.get("awayTeamOdds", {}).get("moneyLine", 0))
    msx = _us_to_decimal(od.get("drawOdds", {}).get("moneyLine", 0))
    barem = float(od.get("overUnder", 0) or 0)
    ust = _us_to_decimal(od.get("overOdds", 0))
    alt = _us_to_decimal(od.get("underOdds", 0))
    handikap = float(od.get("spread", 0) or 0)
    if ms1 > 0 or ms2 > 0 or barem > 0:
        tum_b = [{"barem": barem, "ust": ust or 1.85, "alt": alt or 1.85}] if barem > 0 else list()
        return {
            "ms1": ms1,
            "msx": msx,
            "ms2": ms2,
            "barem": barem,
            "ust": ust or (1.85 if barem > 0 else 0.0),
            "alt": alt or (1.85 if barem > 0 else 0.0),
            "handikap": handikap,
            "tum_baremler": tum_b,
        }
    return None


@st.cache_data(ttl=180, show_spinner=False)
def gercek_oranlari_getir(lig_adi, lig_yolu=""):
    mac_sozluk = {}
    yol = _yol_coz(lig_adi, lig_yolu)
    if yol:
        try:
            tarih_str = datetime.now(timezone.utc).strftime("%Y%m%d")
            u = f"https://espn.com{yol}/scoreboard?dates={tarih_str}"
            r = requests.get(u, headers=TARAYICI_HEADERS, timeout=8)
            if r.status_code == 200 and r.text.strip().startswith("{"):
                for ev in r.json().get("events", list()):
                    comp = next(iter(ev.get("competitions", list())), None)
                    if not comp:
                        continue
                    ev_ad, dep_ad = "", ""
                    for t in comp.get("competitors", list()):
                        if t.get("homeAway") == "home":
                            ev_ad = t.get("team", {}).get("displayName", "")
                        elif t.get("homeAway") == "away":
                            dep_ad = t.get("team", {}).get("displayName", "")
                    anahtar = f"{_isim_norm(ev_ad)}_{_isim_norm(dep_ad)}"
                    od = next(iter(comp.get("odds", list())), None)
                    veri = _odds_ayristir(od)
                    if veri:
                        veri["ev"] = ev_ad
                        veri["dep"] = dep_ad
                        mac_sozluk[anahtar] = veri
        except Exception:
            pass

    if not mac_sozluk:
        okey = _odds_key_coz(lig_adi)
        api_key = os.environ.get("ODDS_API_KEY", "").strip() or "f8be96b3315d2461837ca413e1ae4593"
        if okey:
            try:
                u2 = f"https://the-odds-api.com{okey}/odds/?apiKey={api_key}&regions=eu,us&markets=h2h,totals&oddsFormat=decimal"
                r2 = requests.get(u2, headers=TARAYICI_HEADERS, timeout=8)
                if r2.status_code == 200 and r2.text.strip().startswith("["):
                    for ev in r2.json():
                        ev_ad = ev.get("home_team", "")
                        dep_ad = ev.get("away_team", "")
                        anahtar = f"{_isim_norm(ev_ad)}_{_isim_norm(dep_ad)}"
                        ms1, msx, ms2 = 0.0, 0.0, 0.0
                        baremler = {}
                        for bk in ev.get("bookmakers", list()):
                            for m in bk.get("markets", list()):
                                if m.get("key") == "h2h" and ms1 == 0.0:
                                    for out in m.get("outcomes", list()):
                                        nm = out.get("name", "")
                                        pr = float(out.get("price", 0) or 0)
                                        if nm == ev_ad:
                                            ms1 = pr
                                        elif nm == dep_ad:
                                            ms2 = pr
                                        elif nm.lower() == "draw":
                                            msx = pr
                                elif m.get("key") == "totals":
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
                        sirali_b = [{"barem": k, "ust": v["ust"], "alt": v["alt"]} for k, v in sorted(baremler.items())]
                        ana_b = next(iter(sirali_b), {"barem": 0.0, "ust": 0.0, "alt": 0.0})
                        if ms1 > 0 or ms2 > 0 or sirali_b:
                            mac_sozluk[anahtar] = {
                                "ev": ev_ad,
                                "dep": dep_ad,
                                "ms1": ms1,
                                "msx": msx,
                                "ms2": ms2,
                                "barem": ana_b["barem"],
                                "ust": ana_b["ust"],
                                "alt": ana_b["alt"],
                                "handikap": 0.0,
                                "tum_baremler": sirali_b,
                            }
            except Exception:
                pass

    return mac_sozluk


@st.cache_data(ttl=240, show_spinner=False)
def _web_oran_tara(ev_ad, dep_ad):
    try:
        q = requests.utils.quote(f"{ev_ad} vs {dep_ad} odds over under")
        u = f"https://duckduckgo.com{q}"
        r = requests.get(u, headers=TARAYICI_HEADERS, timeout=7)
        if r.status_code == 200:
            metin = re.sub(r"<[^>]+>", " ", r.text)
            oranlar = re.findall(r"\b([1-9]\.\d{2})\b", metin)
            baremler = re.findall(r"\b(1\.5|2\.5|3\.5|4\.5|5\.5|1[5-9]\d\.5|2[0-5]\d\.5)\b", metin)
            temiz_o = [float(x) for x in oranlar if 1.15 <= float(x) <= 6.50]
            if len(temiz_o) >= 2:
                b_val = float(next(iter(baremler), 0) or 0)
                return {
                    "ev": ev_ad,
                    "dep": dep_ad,
                    "ms1": temiz_o,
                    "msx": temiz_o if len(temiz_o) >= 3 else 0.0,
                    "ms2": temiz_o if len(temiz_o) >= 3 else temiz_o,
                    "barem": b_val,
                    "ust": 1.85 if b_val > 0 else 0.0,
                    "alt": 1.85 if b_val > 0 else 0.0,
                    "handikap": 0.0,
                    "tum_baremler": [{"barem": b_val, "ust": 1.85, "alt": 1.85}] if b_val > 0 else list(),
                }
    except Exception:
        pass
    return None


def mac_oran_bul(lig_adi, ev_ad, dep_ad, lig_yolu=""):
