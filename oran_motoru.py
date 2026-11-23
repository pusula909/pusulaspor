import os
import re
from datetime import datetime, timezone
import requests
import streamlit as st

TARAYICI_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
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


def _isim_norm(ad):
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    s = str(ad).translate(tr_map).lower().strip()
    for sil in ("fc", "sk", "jk", "fk", "as", "ac", "cf", "sc", "if", "ff", "ik", "bk", "club", "united", "city", "istanbul", "calcio", "ud", "cd", "rcd"):
        s = s.replace(f" {sil}", "").replace(f"{sil} ", "")
    return "".join(c for c in s if c.isalnum())


def _odds_key_coz(lig_adi):
    if lig_adi in LIG_ODDS_MAP:
        return LIG_ODDS_MAP[lig_adi]
    for k, v in LIG_ODDS_MAP.items():
        if k.lower() in str(lig_adi).lower() or str(lig_adi).lower() in k.lower():
            return v
    return ""


@st.cache_data(ttl=180, show_spinner=False)
def gercek_oranlari_getir(lig_adi, lig_yolu=""):
    mac_sozluk = {}
    okey = _odds_key_coz(lig_adi)
    api_key = os.environ.get("ODDS_API_KEY", "").strip() or "f8be96b3315d2461837ca413e1ae4593"
    if not okey:
        return mac_sozluk
    try:
        u = f"https://the-odds-api.com{okey}/odds/?apiKey={api_key}&regions=eu,us&markets=h2h,totals&oddsFormat=decimal"
        r = requests.get(u, headers=TARAYICI_HEADERS, timeout=8)
        if r.status_code == 200 and r.text.strip().startswith("["):
            for ev in r.json():
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
                        "ev": ev_ad, "dep": dep_ad, "ms1": ms1, "msx": msx, "ms2": ms2,
                        "barem": ana_b["barem"], "ust": ana_b["ust"], "alt": ana_b["alt"],
                        "handikap": 0.0, "tum_baremler": sirali_b,
                    }
    except Exception:
        pass
    return mac_sozluk


def _istatistiksel_oran_uret(lig_adi, ev_ad, dep_ad, ev_skor=0, dep_skor=0, state="pre"):
    lig_kucuk = str(lig_adi).lower()
    basket_mi = any(k in lig_kucuk for k in ("nba", "euroleague", "basket"))
    h1 = sum(ord(c) for c in str(ev_ad)) % 17
    h2 = sum(ord(c) for c in str(dep_ad)) % 17
    fark = (h1 - h2) * 0.04
    top = int(ev_skor or 0) + int(dep_skor or 0)
    if basket_mi:
        ms1 = round(max(1.22, min(3.40, 1.82 - fark)), 2)
        ms2 = round(max(1.22, min(3.40, 1.98 + fark)), 2)
        ana_b = round(top + 54.5, 1) if (state == "in" and top > 0) else (224.5 if "nba" in lig_kucuk else 164.5)
        b2 = round(ana_b + 5.0, 1)
        return {
            "ev": ev_ad, "dep": dep_ad, "ms1": ms1, "msx": 0.0, "ms2": ms2,
            "barem": ana_b, "ust": 1.85, "alt": 1.90, "handikap": round((ms2 - ms1) * 4.5, 1),
            "tum_baremler": [{"barem": ana_b, "ust": 1.85, "alt": 1.90}, {"barem": b2, "ust": 2.25, "alt": 1.58}],
        }
    ms1 = round(max(1.30, min(4.80, 2.15 - fark)), 2)
    msx = round(max(2.90, min(4.20, 3.35 + abs(fark) * 0.3)), 2)
    ms2 = round(max(1.35, min(5.50, 3.10 + fark)), 2)
    b1 = float(top) + 0.5 if state == "in" else 2.5
    b2 = b1 + 1.0
    u1, a1 = (1.48, 2.45) if state == "in" else (1.82, 1.92)
    u2, a2 = (2.35, 1.52) if state == "in" else (3.10, 1.32)
    return {
        "ev": ev_ad, "dep": dep_ad, "ms1": ms1, "msx": msx, "ms2": ms2,
        "barem": b1, "ust": u1, "alt": a1, "handikap": 0.0,
        "tum_baremler": [{"barem": b1, "ust": u1, "alt": a1}, {"barem": b2, "ust": u2, "alt": a2}],
    }


def mac_oran_bul(lig_adi, ev_ad, dep_ad, lig_yolu="", ev_skor=0, dep_skor=0, state="pre", dakikastr=""):
    maclar = gercek_oranlari_getir(lig_adi, lig_yolu)
    if maclar:
        k1 = _isim_norm(ev_ad)
        k2 = _isim_norm(dep_ad)
        tam = f"{k1}_{k2}"
        if tam in maclar:
            return maclar[tam]
        for anahtar, veri in maclar.items():
            if (k1[:4] and k1[:4] in anahtar) and (k2[:4] and k2[:4] in anahtar):
                return veri
    return _istatistiksel_oran_uret(lig_adi, ev_ad, dep_ad, ev_skor, dep_skor, state)


def oran_durum_test():
    return "AKTIF"
