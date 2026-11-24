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


@st.cache_data(ttl=120, show_spinner=False)
def _espn_yedek_oran(lig_adi, ev_ad, dep_ad):
    yol_map = {
        "NBA": "basketball/nba",
        "Ingiltere Premier Lig": "soccer/eng.1",
        "Ispanya La Liga": "soccer/esp.1",
        "Almanya Bundesliga": "soccer/ger.1",
        "Italya Serie A": "soccer/ita.1",
        "Fransa Ligue 1": "soccer/fra.1",
        "Sampiyonlar Ligi": "soccer/uefa.champions",
        "Avrupa Ligi": "soccer/uefa.europa",
        "Trendyol Super Lig": "soccer/tur.1",
        "Turkiye Super Lig": "soccer/tur.1",
    }
    yol = yol_map.get(lig_adi)
    if not yol:
        if "nba" in str(lig_adi).lower():
            yol = "basketball/nba"
        elif any(k in str(lig_adi).lower() for k in ("premier", "ingiltere")):
            yol = "soccer/eng.1"
        elif "la liga" in str(lig_adi).lower() or "ispanya" in str(lig_adi).lower():
            yol = "soccer/esp.1"
        elif "bundesliga" in str(lig_adi).lower() or "almanya" in str(lig_adi).lower():
            yol = "soccer/ger.1"
        elif "serie a" in str(lig_adi).lower() or "italya" in str(lig_adi).lower():
            yol = "soccer/ita.1"
        elif "ligue 1" in str(lig_adi).lower() or "fransa" in str(lig_adi).lower():
            yol = "soccer/fra.1"
        elif "sampiyonlar" in str(lig_adi).lower() or "champions" in str(lig_adi).lower():
            yol = "soccer/uefa.champions"
        elif "super lig" in str(lig_adi).lower() or "turkiye" in str(lig_adi).lower():
            yol = "soccer/tur.1"

    aranacak_yollar = [yol] if yol else [
        "basketball/nba",
        "soccer/eng.1",
        "soccer/esp.1",
        "soccer/ger.1",
        "soccer/ita.1",
        "soccer/fra.1",
        "soccer/uefa.champions",
        "soccer/tur.1",
    ]
    k1 = _isim_norm(ev_ad)
    k2 = _isim_norm(dep_ad)
    simdi = datetime.now(timezone.utc)
    for y in aranacak_yollar:
        for g in (0, 1, -1):
            t_str = (simdi + timedelta(days=g)).strftime("%Y%m%d")
            try:
                r = requests.get(f"https://espn.com{y}/scoreboard?dates={t_str}", timeout=7).json()
                for ev in r.get("events", list()):
                    comp = ev.get("competitions", list(({},))).pop(0)
                    taks = comp.get("competitors", list())
                    if len(taks) < 2:
                        continue
                    h_ad = next((t.get("team", {}).get("displayName", "") for t in taks if t.get("homeAway") == "home"), "")
                    a_ad = next((t.get("team", {}).get("displayName", "") for t in taks if t.get("homeAway") == "away"), "")
                    hn, an = _isim_norm(h_ad), _isim_norm(a_ad)
                    if (k1[:4] and k1[:4] in hn) and (k2[:4] and k2[:4] in an):
                        odds_list = comp.get("odds", list())
                        if not odds_list:
                            ev_id = ev.get("id", "")
                            if ev_id:
                                sum_r = requests.get(f"https://espn.com{y}/summary?event={ev_id}", timeout=6).json()
                                odds_list = sum_r.get("pickcenter", list())
                        if not odds_list:
                            continue
                        od = odds_list.pop(0)
                        barem = float(od.get("overUnder", 0) or 0)
                        hdp = float(od.get("spread", 0) or 0)
                        ms1 = _us_to_decimal(od.get("homeTeamOdds", {}).get("moneyLine", 0))
                        ms2 = _us_to_decimal(od.get("awayTeamOdds", {}).get("moneyLine", 0))
                        msx = _us_to_decimal(od.get("drawOdds", {}).get("moneyLine", 0))
                        if barem > 0 or ms1 > 0 or ms2 > 0:
                            return {
                                "ev": h_ad,
                                "dep": a_ad,
                                "ms1": ms1,
                                "msx": msx,
                                "ms2": ms2,
                                "barem": barem,
                                "ust": 1.88,
                                "alt": 1.88,
                                "handikap": hdp,
                                "tum_baremler": [{"barem": barem, "ust": 1.88, "alt": 1.88}] if barem > 0 else list(),
                            }
            except Exception:
                continue
    return None
    k1 = _isim_norm(ev_ad)
    k2 = _isim_norm(dep_ad)
    simdi = datetime.now(timezone.utc)
    for g in (0, 1, -1):
        t_str = (simdi + timedelta(days=g)).strftime("%Y%m%d")
        try:
            r = requests.get(f"https://espn.com{yol}/scoreboard?dates={t_str}", timeout=7).json()
            for ev in r.get("events", list()):
                comp = ev.get("competitions", list(({},))).pop(0)
                taks = comp.get("competitors", list())
                if len(taks) < 2:
                    continue
                h_ad = next((t.get("team", {}).get("displayName", "") for t in taks if t.get("homeAway") == "home"), "")
                a_ad = next((t.get("team", {}).get("displayName", "") for t in taks if t.get("homeAway") == "away"), "")
                hn, an = _isim_norm(h_ad), _isim_norm(a_ad)
                if (k1[:4] and k1[:4] in hn) and (k2[:4] and k2[:4] in an):
                    odds_list = comp.get("odds", list())
                    if not odds_list:
                        continue
                    od = odds_list.pop(0)
                    barem = float(od.get("overUnder", 0) or 0)
                    hdp = float(od.get("spread", 0) or 0)
                    ms1 = _us_to_decimal(od.get("homeTeamOdds", {}).get("moneyLine", 0))
                    ms2 = _us_to_decimal(od.get("awayTeamOdds", {}).get("moneyLine", 0))
                    msx = _us_to_decimal(od.get("drawOdds", {}).get("moneyLine", 0))
                    if barem > 0 or ms1 > 0 or ms2 > 0:
                        return {
                            "ev": h_ad,
                            "dep": a_ad,
                            "ms1": ms1,
                            "msx": msx,
                            "ms2": ms2,
                            "barem": barem,
                            "ust": 1.88,
                            "alt": 1.88,
                            "handikap": hdp,
                            "tum_baremler": [{"barem": barem, "ust": 1.88, "alt": 1.88}] if barem > 0 else list(),
                        }
        except Exception:
            continue
    return None

def mac_oran_bul(lig_adi, ev_ad, dep_ad, lig_yolu="", ev_skor=0, dep_skor=0, state="pre", dakikastr=""):
    maclar = gercek_oranlari_getir(lig_adi, lig_yolu)
    k1 = _isim_norm(ev_ad)
    k2 = _isim_norm(dep_ad)
    if maclar:
        tam = f"{k1}_{k2}"
        if tam in maclar:
            return maclar[tam]
        for anahtar, veri in maclar.items():
            if (k1[:4] and k1[:4] in anahtar) and (k2[:4] and k2[:4] in anahtar):
                return veri
    return _espn_yedek_oran(lig_adi, ev_ad, dep_ad)
