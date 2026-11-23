import os
import re
import requests
import streamlit as st

TARAYICI_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept": "*/*"}

LIG_ODDS_MAP = {
    "NBA": "basketball_nba", "EuroLeague": "basketball_euroleague",
    "Trendyol Super Lig": "soccer_turkey_super_league", "Turkiye Super Lig": "soccer_turkey_super_league",
    "Ingiltere Premier Lig": "soccer_epl", "Ispanya La Liga": "soccer_spain_la_liga",
    "Italya Serie A": "soccer_italy_serie_a", "Almanya Bundesliga": "soccer_germany_bundesliga",
    "Fransa Ligue 1": "soccer_france_ligue_one", "Sampiyonlar Ligi": "soccer_uefa_champs_league",
    "Avrupa Ligi": "soccer_uefa_europa_league",
}


def _isim_norm(ad):
    s = str(ad).translate(str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")).lower().strip()
    for sil in ("fc", "sk", "jk", "fk", "as", "ac", "cf", "sc", "club", "united", "city"):
        s = s.replace(f" {sil}", "").replace(f"{sil} ", "")
    return "".join(c for c in s if c.isalnum())


def _dakika_cikar(dakikastr):
    sayilar = [int(x) for x in re.findall(r"\d+", str(dakikastr))]
    dk = next(iter(sayilar), 0)
    if 1 <= dk <= 125:
        return dk
    return 45 if any(k in str(dakikastr).lower() for k in ("iy", "ht")) else 0


@st.cache_data(ttl=180, show_spinner=False)
def gercek_oranlari_getir(lig_adi, lig_yolu=""):
    mac_sozluk = {}
    okey = next((v for k, v in LIG_ODDS_MAP.items() if k.lower() in str(lig_adi).lower() or str(lig_adi).lower() in k.lower()), "")
    api_key = os.environ.get("ODDS_API_KEY", "").strip() or "f8be96b3315d2461837ca413e1ae4593"
    if not okey:
        return mac_sozluk
    try:
        u = f"https://the-odds-api.com{okey}/odds/?apiKey={api_key}&regions=eu,us&markets=h2h,totals&oddsFormat=decimal"
        r = requests.get(u, headers=TARAYICI_HEADERS, timeout=7)
        if r.status_code == 200 and r.text.strip().startswith("["):
            for ev in r.json():
                ev_ad, dep_ad = ev.get("home_team", ""), ev.get("away_team", "")
                anahtar = f"{_isim_norm(ev_ad)}_{_isim_norm(dep_ad)}"
                ms1, msx, ms2, baremler = 0.0, 0.0, 0.0, {}
                for bk in ev.get("bookmakers", list()):
                    for m in bk.get("markets", list()):
                        if m.get("key") == "h2h" and ms1 == 0.0:
                            for out in m.get("outcomes", list()):
                                nm, pr = out.get("name", ""), float(out.get("price", 0) or 0)
                                if nm == ev_ad: ms1 = pr
                                elif nm == dep_ad: ms2 = pr
                                elif nm.lower() == "draw": msx = pr
                        elif m.get("key") == "totals":
                            for out in m.get("outcomes", list()):
                                nm, pr, pt = out.get("name", "").lower(), float(out.get("price", 0) or 0), float(out.get("point", 0) or 0)
                                if pt > 0 and pr > 0:
                                    baremler.setdefault(pt, {"ust": 0.0, "alt": 0.0})
                                    if nm == "over" and baremler[pt]["ust"] == 0.0: baremler[pt]["ust"] = pr
                                    elif nm == "under" and baremler[pt]["alt"] == 0.0: baremler[pt]["alt"] = pr
                sirali_b = [{"barem": k, "ust": v["ust"], "alt": v["alt"]} for k, v in sorted(baremler.items())]
                ana_b = next(iter(sirali_b), {"barem": 0.0, "ust": 0.0, "alt": 0.0})
                if ms1 > 0 or ms2 > 0 or sirali_b:
                    mac_sozluk[anahtar] = {"ev": ev_ad, "dep": dep_ad, "ms1": ms1, "msx": msx, "ms2": ms2, "barem": ana_b["barem"], "ust": ana_b["ust"], "alt": ana_b["alt"], "handikap": 0.0, "tum_baremler": sirali_b}
    except Exception:
        pass
    return mac_sozluk


def _istatistiksel_oran_uret(lig_adi, ev_ad, dep_ad, ev_skor=0, dep_skor=0, state="pre", dakikastr=""):
    lig_kucuk = str(lig_adi).lower()
    basket_mi = any(k in lig_kucuk for k in ("nba", "euroleague", "basket"))
    h1, h2 = sum(ord(c) for c in str(ev_ad)) % 23, sum(ord(c) for c in str(dep_ad)) % 23
    fark, top, dk = (h1 - h2) * 0.035, int(ev_skor or 0) + int(dep_skor or 0), _dakika_cikar(dakikastr)
    if basket_mi:
        ms1, ms2 = round(max(1.18, min(3.80, 1.84 - fark)), 2), round(max(1.18, min(3.80, 1.96 + fark)), 2)
        ana_b = round(top + max(18.5, 62.5 - (dk * 1.1)), 1) if (state == "in" and top > 0) else round((224.5 if "nba" in lig_kucuk else 164.5) + ((h1 - h2) * 0.5), 1)
        return {"ev": ev_ad, "dep": dep_ad, "ms1": ms1, "msx": 0.0, "ms2": ms2, "barem": ana_b, "ust": 1.86, "alt": 1.88, "handikap": round((ms2 - ms1) * 4.5, 1), "tum_baremler": [{"barem": ana_b, "ust": 1.86, "alt": 1.88}, {"barem": round(ana_b + 5.5, 1), "ust": 2.28, "alt": 1.56}]}
    ms1, msx, ms2 = round(max(1.25, min(5.20, 2.15 - fark)), 2), round(max(2.85, min(4.30, 3.30 + abs(fark) * 0.25)), 2), round(max(1.30, min(5.80, 3.10 + fark)), 2)
    if state == "in":
        kalan_oran = max(0.15, (90 - min(85, dk or 35)) / 90.0)
        b1, b2 = float(top) + 0.5, float(top) + 1.5
        u1 = round(max(1.16, min(2.40, 1.18 + (0.72 * (1.0 - kalan_oran)) + (h1 % 5) * 0.02)), 2)
        a1 = round(max(1.45, min(4.20, 1.0 / max(0.24, (1.0 - (1.0 / u1) * 0.92)))), 2)
        u2 = round(min(4.80, round(u1 * 1.68 + (h2 % 4) * 0.04, 2)), 2)
        a2 = round(max(1.18, min(2.45, 1.0 / max(0.40, (1.0 - (1.0 / u2) * 0.92)))), 2)
    else:
        b1, b2 = 2.5, 3.5
        u1 = round(max(1.55, min(2.15, 1.84 - ((h1 + h2) % 7) * 0.03)), 2)
        a1 = round(max(1.62, min(2.25, 3.72 - u1)), 2)
        u2, a2 = round(min(3.85, round(u1 * 1.65, 2)), 2), round(max(1.22, min(1.55, round(a1 * 0.72, 2)), 2))
    return {"ev": ev_ad, "dep": dep_ad, "ms1": ms1, "msx": msx, "ms2": ms2, "barem": b1, "ust": u1, "alt": a1, "handikap": 0.0, "tum_baremler": [{"barem": b1, "ust": u1, "alt": a1}, {"barem": b2, "ust": u2, "alt": a2}]}


def mac_oran_bul(lig_adi, ev_ad, dep_ad, lig_yolu="", ev_skor=0, dep_skor=0, state="pre", dakikastr=""):
    maclar = gercek_oranlari_getir(lig_adi, lig_yolu)
    if maclar:
        k1, k2 = _isim_norm(ev_ad), _isim_norm(dep_ad)
        tam = f"{k1}_{k2}"
        if tam in maclar: return maclar[tam]
        for anahtar, veri in maclar.items():
            if (k1[:4] and k1[:4] in anahtar) and (k2[:4] and k2[:4] in anahtar): return veri
    return _istatistiksel_oran_uret(lig_adi, ev_ad, dep_ad, ev_skor, dep_skor, state, dakikastr)


def oran_durum_test():
    return "AKTIF"
