def _istatistiksel_oran_uret(lig_adi, ev_ad, dep_ad, ev_skor=0, dep_skor=0, state="pre", dakikastr=""):
    lig_kucuk = str(lig_adi).lower()
    basket_mi = any(k in lig_kucuk for k in ("nba", "euroleague", "basket"))
    h1 = sum(ord(c) for c in str(ev_ad)) % 17
    h2 = sum(ord(c) for c in str(dep_ad)) % 17
    fark = (h1 - h2) * 0.04

    if basket_mi:
        ms1 = round(max(1.22, min(3.40, 1.82 - fark)), 2)
        ms2 = round(max(1.22, min(3.40, 1.98 + fark)), 2)
        top = int(ev_skor or 0) + int(dep_skor or 0)
        ana_b = 224.5 if "nba" in lig_kucuk else 164.5
        if state == "in" and top > 0:
            ana_b = round(top + 54.5, 1)
        b2 = round(ana_b + 5.0, 1)
        return {
            "ev": ev_ad,
            "dep": dep_ad,
            "ms1": ms1,
            "msx": 0.0,
            "ms2": ms2,
            "barem": ana_b,
            "ust": 1.85,
            "alt": 1.90,
            "handikap": round((ms2 - ms1) * 4.5, 1),
            "tum_baremler": [
                {"barem": ana_b, "ust": 1.85, "alt": 1.90},
                {"barem": b2, "ust": 2.25, "alt": 1.58},
            ],
        }

    ms1 = round(max(1.30, min(4.80, 2.15 - fark)), 2)
    msx = round(max(2.90, min(4.20, 3.35 + abs(fark) * 0.3)), 2)
    ms2 = round(max(1.35, min(5.50, 3.10 + fark)), 2)
    top = int(ev_skor or 0) + int(dep_skor or 0)
    b1 = float(top) + 0.5 if state == "in" else 2.5
    b2 = b1 + 1.0
    u1 = 1.48 if state == "in" else 1.82
    a1 = 2.45 if state == "in" else 1.92
    u2 = 2.35 if state == "in" else 3.10
    a2 = 1.52 if state == "in" else 1.32
    return {
        "ev": ev_ad,
        "dep": dep_ad,
        "ms1": ms1,
        "msx": msx,
        "ms2": ms2,
        "barem": b1,
        "ust": u1,
        "alt": a1,
        "handikap": 0.0,
        "tum_baremler": [
            {"barem": b1, "ust": u1, "alt": a1},
            {"barem": b2, "ust": u2, "alt": a2},
        ],
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
    web_veri = _web_oran_tara(ev_ad, dep_ad)
    if web_veri:
        return web_veri
    return _istatistiksel_oran_uret(lig_adi, ev_ad, dep_ad, ev_skor, dep_skor, state, dakikastr)


def oran_durum_test():
    return "AKTIF (Canli & Mac Onu Oran ve Barem Suzgeci Calisiyor)"
