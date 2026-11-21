import math
import requests

ALAN = ".".join(("site", "api", "espn", "com"))
PUAN_BASI = f"https://{ALAN}/apis/v2/sports/"
URL_BASI = f"https://{ALAN}/apis/site/v2/sports/"
BASLIKLAR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

_STANDINGS_CACHE = {}


def _poisson_olasilik(k, lamb):
    if lamb <= 0:
        return 1.0 if k == 0 else 0.0
    return (math.exp(-lamb) * (lamb ** k)) / math.factorial(k)


def lig_takim_ortalamalari_getir(lig_yolu):
    """ESPN standings uzerinden her takimin mac basi attigi/yedigi gol veya sayi ortalamasini ceker."""
    if lig_yolu in _STANDINGS_CACHE:
        return _STANDINGS_CACHE[lig_yolu]

    sonuc = {}
    if not lig_yolu or lig_yolu == "euroleague_resmi" or "/" not in lig_yolu:
        return sonuc

    try:
        r = requests.get(f"{PUAN_BASI}{lig_yolu}/standings", headers=BASLIKLAR, timeout=6).json()
        for g in r.get("children", []):
            for e in g.get("standings", {}).get("entries", []):
                t_ad = e.get("team", {}).get("displayName", "")
                st = {s["name"]: float(s.get("value", 0) or 0) for s in e.get("stats", [])}
                oynanan = st.get("gamesPlayed", 0)
                if t_ad and oynanan > 0:
                    atilan = st.get("pointsFor", 0)
                    yenilen = st.get("pointsAgainst", 0)
                    sonuc[t_ad] = {
                        "oynanan": oynanan,
                        "atilan_ort": atilan / oynanan,
                        "yenilen_ort": yenilen / oynanan,
                        "galibiyet_orani": st.get("winPercent", st.get("wins", 0) / oynanan),
                    }
    except Exception:
        pass

    _STANDINGS_CACHE[lig_yolu] = sonuc
    return sonuc


def piyasa_ve_oran_hareketi_cek(lig_yolu, mac_id):
    """Acilis baremi vs guncel barem kaymasini (Sharp Money) ve handikabi ceker."""
    veri = {"guncel_barem": None, "acilis_barem": None, "kayma": 0.0, "handikap": "", "sharp_uyari": ""}
    if not mac_id or lig_yolu == "euroleague_resmi" or "/" not in lig_yolu:
        return veri

    try:
        j = requests.get(f"{URL_BASI}{lig_yolu}/summary?event={mac_id}", headers=BASLIKLAR, timeout=5).json()
        pick = j.get("pickcenter", [])
        if pick:
            p0 = pick[0]
            if p0.get("overUnder"):
                veri["guncel_barem"] = float(p0["overUnder"])
            if p0.get("details"):
                veri["handikap"] = str(p0["details"])
            ou_open = p0.get("total", {}).get("over", {}).get("open", {}).get("line", "")
            if ou_open:
                temiz = "".join(c for c in str(ou_open) if c.isdigit() or c == ".")
                if temiz:
                    veri["acilis_barem"] = float(temiz)
            if veri["guncel_barem"] and veri["acilis_barem"]:
                fark = round(veri["guncel_barem"] - veri["acilis_barem"], 1)
                veri["kayma"] = fark
                if abs(fark) >= 2.5:
                    yon = "YUKARI (UST BASKISI)" if fark > 0 else "ASAGI (ALT BASKISI)"
                    veri["sharp_uyari"] = f"🚨 SHARP MONEY KAYMASI: Barem {veri['acilis_barem']} -> {veri['guncel_barem']} ({yon})"
    except Exception:
        pass
    return veri


def futbol_poisson_hesapla(lig_yolu, ev_ad, dep_ad, ev_eksik=0, dep_eksik=0, state="pre", ev_skor=0, dep_skor=0):
    """Gercek gol ortalamalarina gore Poisson skor ve market olasiliklarini hesaplar."""
    ortalamalar = lig_takim_ortalamalari_getir(lig_yolu)
    ev_st = ortalamalar.get(ev_ad)
    dep_st = ortalamalar.get(dep_ad)

    if ev_st and dep_st and ev_st["atilan_ort"] > 0 and dep_st["atilan_ort"] > 0:
        ev_gol_beklenti = ((ev_st["atilan_ort"] + dep_st["yenilen_ort"]) / 2.0) * 1.12
        dep_gol_beklenti = ((dep_st["atilan_ort"] + ev_st["yenilen_ort"]) / 2.0) * 0.92
    else:
        ev_gol_beklenti = 1.45
        dep_gol_beklenti = 1.15

    ev_gol_beklenti = max(0.35, ev_gol_beklenti * (1 - ev_eksik * 0.05))
    dep_gol_beklenti = max(0.30, dep_gol_beklenti * (1 - dep_eksik * 0.05))

    if state == "in":
        ev_gol_beklenti *= 0.45
        dep_gol_beklenti *= 0.45

    p_ms1, p_ms0, p_ms2 = 0.0, 0.0, 0.0
    p_ust25, p_kg_var = 0.0, 0.0
    skor_adaylari = []

    for i in range(6):
        for j in range(6):
            olas = _poisson_olasilik(i, ev_gol_beklenti) * _poisson_olasilik(j, dep_gol_beklenti)
            top_ev = ev_skor + i
            top_dep = dep_skor + j
            if top_ev > top_dep:
                p_ms1 += olas
            elif top_ev == top_dep:
                p_ms0 += olas
            else:
                p_ms2 += olas

            if (top_ev + top_dep) >= 3:
                p_ust25 += olas
            if top_ev > 0 and top_dep > 0:
                p_kg_var += olas

            skor_adaylari.append((f"{top_ev}-{top_dep}", olas))

    skor_adaylari.sort(key=lambda x: x[1], reverse=True)
    en_olasi_skorlar = [f"{s} (%{int(o * 100)})" for s, o in skor_adaylari[:3]]

    return {
        "ms1": int(round(p_ms1 * 100)),
        "ms0": int(round(p_ms0 * 100)),
        "ms2": int(round(p_ms2 * 100)),
        "ust25": int(round(p_ust25 * 100)),
        "alt25": int(round((1 - p_ust25) * 100)),
        "kg_var": int(round(p_kg_var * 100)),
        "beklenen_gol": round(ev_skor + dep_skor + ev_gol_beklenti + dep_gol_beklenti, 2),
        "olasi_skorlar": ", ".join(en_olasi_skorlar),
    }


def basketbol_tempo_hesapla(lig_yolu, lig_adi, ev_ad, dep_ad, ev_eksik=0, dep_eksik=0, piyasa_barem=None):
    """Takimlarin gercek sayi uretimi ve savunmasina gore beklenen toplam sayiyi ve Value farkini hesaplar."""
    ortalamalar = lig_takim_ortalamalari_getir(lig_yolu)
    ev_st = ortalamalar.get(ev_ad)
    dep_st = ortalamalar.get(dep_ad)

    if ev_st and dep_st and ev_st["atilan_ort"] > 40 and dep_st["atilan_ort"] > 40:
        ev_beklenen = ((ev_st["atilan_ort"] + dep_st["yenilen_ort"]) / 2.0) + 1.8
        dep_beklenen = ((dep_st["atilan_ort"] + ev_st["yenilen_ort"]) / 2.0) - 1.2
    else:
        taban = 81.0 if lig_adi == "EuroLeague" else 113.0
        ev_beklenen = taban + 1.5
        dep_beklenen = taban - 1.0

    ev_beklenen -= ev_eksik * 1.4
    dep_beklenen -= dep_eksik * 1.4
    toplam_beklenti = round(ev_beklenen + dep_beklenen, 1)

    value_fark = round(toplam_beklenti - piyasa_barem, 1) if piyasa_barem else 0.0
    value_etiket = ""
    if piyasa_barem:
        if value_fark >= 5.5:
            value_etiket = f"💎 VALUE UST (+{value_fark} Sayi Avantaji)"
        elif value_fark <= -5.5:
            value_etiket = f"💎 VALUE ALT ({value_fark} Sayi Avantaji)"

    return {
        "ev_beklenen": round(ev_beklenen, 1),
        "dep_beklenen": round(dep_beklenen, 1),
        "toplam_beklenti": toplam_beklenti,
        "piyasa_barem": piyasa_barem,
        "value_fark": value_fark,
        "value_etiket": value_etiket,
    }
