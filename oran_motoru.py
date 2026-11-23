import json
import os
import time
import requests

CACHE_DOSYA = "gercek_oranlar_cache.json"
CACHE_SURE_SN = 300

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


def _odds_detay_cek(yol, event_id):
    try:
        u = f"https://espn.com{yol.split('/')[0]}/leagues/{yol.split('/')[1]}/events/{event_id}/competitions/{event_id}/odds"
        r = requests.get(u, timeout=6)
        if r.status_code != 200:
            return None
        items = r.json().get("items", [])
        if not items:
            return None
        od = items
        ms1 = _us_to_decimal(od.get("homeTeamOdds", {}).get("moneyLine", 0))
        ms2 = _us_to_decimal(od.get("awayTeamOdds", {}).get("moneyLine", 0))
        msx = _us_to_decimal(od.get("drawOdds", {}).get("moneyLine", 0))
        barem = float(od.get("overUnder", 0) or 0)
        ust = _us_to_decimal(od.get("overOdds", 0))
        alt = _us_to_decimal(od.get("underOdds", 0))
        handikap = float(od.get("spread", 0) or 0)
        tum_baremler = []
        if barem > 0:
            tum_baremler.append({"barem": barem, "ust": ust or 1.85, "alt": alt or 1.85})
        if ms1 > 0 or ms2 > 0 or barem > 0:
            return {
                "ms1": ms1,
                "msx": msx,
                "ms2": ms2,
                "barem": barem,
                "ust": ust or (1.85 if barem > 0 else 0.0),
                "alt": alt or (1.85 if barem > 0 else 0.0),
                "handikap": handikap,
                "tum_baremler": tum_baremler,
            }
    except Exception:
        pass
    return None


def gercek_oranlari_getir(lig_adi, lig_yolu=""):
    yol = _yol_coz(lig_adi, lig_yolu)
    if not yol:
        return {}

    cache = {}
    if os.path.exists(CACHE_DOSYA):
        try:
            with open(CACHE_DOSYA, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            cache = {}

    simdi = time.time()
    lig_kayit = cache.get(yol, {})
    if lig_kayit and lig_kayit.get("maclar") and (simdi - lig_kayit.get("zaman", 0)) < CACHE_SURE_SN:
        return lig_kayit.get("maclar", {})

    mac_sozluk = {}
    try:
        u = f"https://espn.com{yol}/scoreboard"
        r = requests.get(u, timeout=8)
        if r.status_code == 200:
            for ev in r.json().get("events", []):
                ev_id = str(ev.get("id", ""))
                comps = ev.get("competitions", [])
                if not comps:
                    continue
                comp = comps
                takimlar = comp.get("competitors", [])
                ev_ad, dep_ad = "", ""
                for t in takimlar:
                    if t.get("homeAway") == "home":
                        ev_ad = t.get("team", {}).get("displayName", "")
                    elif t.get("homeAway") == "away":
                        dep_ad = t.get("team", {}).get("displayName", "")

                anahtar = f"{_isim_norm(ev_ad)}_{_isim_norm(dep_ad)}"
                veri = None
                odds_list = comp.get("odds", [])
                if odds_list:
                    od = odds_list
                    ms1 = _us_to_decimal(od.get("homeTeamOdds", {}).get("moneyLine", 0))
                    ms2 = _us_to_decimal(od.get("awayTeamOdds", {}).get("moneyLine", 0))
                    msx = _us_to_decimal(od.get("drawOdds", {}).get("moneyLine", 0))
                    barem = float(od.get("overUnder", 0) or 0)
                    ust = _us_to_decimal(od.get("overOdds", 0))
                    alt = _us_to_decimal(od.get("underOdds", 0))
                    handikap = float(od.get("spread", 0) or 0)
                    if ms1 > 0 or ms2 > 0 or barem > 0:
                        tum_b = [{"barem": barem, "ust": ust or 1.85, "alt": alt or 1.85}] if barem > 0 else []
                        veri = {
                            "ms1": ms1,
                            "msx": msx,
                            "ms2": ms2,
                            "barem": barem,
                            "ust": ust or (1.85 if barem > 0 else 0.0),
                            "alt": alt or (1.85 if barem > 0 else 0.0),
                            "handikap": handikap,
                            "tum_baremler": tum_b,
                        }

                if not veri and ev_id:
                    veri = _odds_detay_cek(yol, ev_id)

                if veri:
                    veri["ev"] = ev_ad
                    veri["dep"] = dep_ad
                    mac_sozluk[anahtar] = veri

            if mac_sozluk:
                cache[yol] = {"zaman": simdi, "maclar": mac_sozluk}
                with open(CACHE_DOSYA, "w", encoding="utf-8") as f:
                    json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        return lig_kayit.get("maclar", {})

    return mac_sozluk


def mac_oran_bul(lig_adi, ev_ad, dep_ad, lig_yolu=""):
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
    veriler = gercek_oranlari_getir("NBA", "basketball/nba")
    if veriler:
        ilk = next(iter(veriler.values()))
        return f"AKTIF ({len(veriler)} mac cekildi) | Ornek: {ilk['ev']} vs {ilk['dep']} -> MS1:{ilk['ms1']} MS2:{ilk['ms2']} Barem:{ilk['barem']}"
    return "ESPN uzerinden su an acik oran bulunamadi."
