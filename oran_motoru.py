import os
from datetime import datetime, timedelta, timezone
import requests
import streamlit as st

LIG_SPORT_ID = {
    "NBA": 4,
    "EuroLeague": 10,
    "Ingiltere Premier Lig": 11,
    "Ispanya La Liga": 12,
    "Almanya Bundesliga": 13,
    "Italya Serie A": 14,
    "Fransa Ligue 1": 15,
    "Sampiyonlar Ligi": 16,
    "Avrupa Ligi": 17,
    "Trendyol Super Lig": 18,
    "Turkiye Super Lig": 18,
}


def _rapid_key_al():
    k = os.environ.get("RAPIDAPI_KEY", "").strip()
    if not k:
        try:
            k = str(st.secrets.get("RAPIDAPI_KEY", "")).strip()
        except Exception:
            pass
    return k or "3dcc052969msh6de1b2856f30599p144ecajsn0253f8249b50"


def _us_to_decimal(us_oran):
    try:
        val = float(str(us_oran).replace("+", "").strip())
        if val == 0 or abs(val) < 100 or abs(val) > 50000:
            return 0.0
        if val > 0:
            return round(1.0 + (val / 100.0), 2)
        return round(1.0 + (100.0 / abs(val)), 2)
    except Exception:
        return 0.0


def _isim_norm(ad):
    s = str(ad).translate(str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")).lower().strip()
    for sil in ("fc", "sk", "jk", "fk", "as", "ac", "cf", "sc", "club", "united", "city", "calcio", "ud", "cd", "rcd"):
        s = s.replace(f" {sil}", "").replace(f"{sil} ", "")
    return "".join(c for c in s if c.isalnum())


def _sport_id_bul(lig_adi):
    if lig_adi in LIG_SPORT_ID:
        return LIG_SPORT_ID[lig_adi]
    for k, v in LIG_SPORT_ID.items():
        if k.lower() in str(lig_adi).lower() or str(lig_adi).lower() in k.lower():
            return v
    return 18


@st.cache_data(ttl=120, show_spinner=False)
def gercek_oranlari_getir(lig_adi, lig_yolu=""):
    mac_sozluk = {}
    api_key = _rapid_key_al()
    sport_id = _sport_id_bul(lig_adi)
    simdi_utc = datetime.now(timezone.utc)
    tarihler = [
        (simdi_utc - timedelta(hours=6)).strftime("%Y-%m-%d"),
        simdi_utc.strftime("%Y-%m-%d"),
    ]
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "://rapidapi.com",
    }

    for tarih_str in dict.fromkeys(tarihler):
        try:
            u = f"https://rapidapi.com{sport_id}/events/{tarih_str}"
            r = requests.get(u, headers=headers, params={"include": "scores,all_periods"}, timeout=9)
            if r.status_code != 200:
                continue

            for ev in r.json().get("events", list()):
                ev_ad, dep_ad = "", ""
                for t in ev.get("teams_normalized", list()) or ev.get("teams", list()):
                    if t.get("is_home"):
                        ev_ad = t.get("name", "")
                    elif t.get("is_away"):
                        dep_ad = t.get("name", "")
                if not ev_ad or not dep_ad:
                    continue

                anahtar = f"{_isim_norm(ev_ad)}_{_isim_norm(dep_ad)}"
                lines = ev.get("lines", {}) or {}
                ms1, msx, ms2, barem, ust, alt, hdp = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
                tum_baremler = list()

                for _bk_id, ln in lines.items():
                    ml = ln.get("moneyline", {}) or {}
                    tot = ln.get("total", {}) or {}
                    spr = ln.get("spread", {}) or {}

                    if ms1 == 0.0:
                        ms1 = _us_to_decimal(ml.get("moneyline_home", 0))
                        ms2 = _us_to_decimal(ml.get("moneyline_away", 0))
                        msx = _us_to_decimal(ml.get("moneyline_draw", 0))

                    pt = float(tot.get("total_over", 0) or 0)
                    uo = _us_to_decimal(tot.get("total_over_money", 0))
                    ao = _us_to_decimal(tot.get("total_under_money", 0))
                    if pt > 0 and (uo > 0 or ao > 0):
                        if barem == 0.0:
                            barem, ust, alt = pt, (uo or 1.85), (ao or 1.85)
                        if not any(b["barem"] == pt for b in tum_baremler):
                            tum_baremler.append({"barem": pt, "ust": uo or 1.85, "alt": ao or 1.85})

                    if hdp == 0.0:
                        hdp = float(spr.get("point_spread_home", 0) or 0)

                tum_baremler.sort(key=lambda x: x["barem"])
                if ms1 > 0 or ms2 > 0 or barem > 0:
                    mac_sozluk[anahtar] = {
                        "ev": ev_ad,
                        "dep": dep_ad,
                        "ms1": ms1,
                        "msx": msx,
                        "ms2": ms2,
                        "barem": barem,
                        "ust": ust,
                        "alt": alt,
                        "handikap": hdp,
                        "tum_baremler": tum_baremler,
                    }
        except Exception:
            pass
    return mac_sozluk


def mac_oran_bul(lig_adi, ev_ad, dep_ad, lig_yolu="", ev_skor=0, dep_skor=0, state="pre", dakikastr=""):
    maclar = gercek_oranlari_getir(lig_adi, lig_yolu)
    if not maclar:
        return None
    k1 = _isim_norm(ev_ad)
    k2 = _isim_norm(dep_ad)
    tam = f"{k1}_{k2}"
    if tam in maclar:
        return maclar[tam]
    for anahtar, veri in maclar.items():
        if (k1[:4] and k1[:4] in anahtar) and (k2[:4] and k2[:4] in anahtar):
            return veri
    return None


def oran_durum_test():
    veriler = gercek_oranlari_getir("NBA")
    if veriler:
        ilk = next(iter(veriler.values()))
        return f"THERUNDOWN AKTIF ({len(veriler)} mac) | Ornek: {ilk['ev']} vs {ilk['dep']} -> MS1:{ilk['ms1']} MS2:{ilk['ms2']} Barem:{ilk['barem']}"
    return "TheRundown uzerinden su an acik mac orani bulunamadi."
