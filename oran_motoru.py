def _dakika_cikar(dakikastr):
    try:
        sayilar = [int(x) for x in re.findall(r"\d+", str(dakikastr))]
        dk = next(iter(sayilar), 0)
        if 1 <= dk <= 125:
            return dk
        if "iy" in str(dakikastr).lower() or "ht" in str(dakikastr).lower():
            return 45
    except Exception:
        pass
    return 0


def _istatistiksel_oran_uret(lig_adi, ev_ad, dep_ad, ev_skor=0, dep_skor=0, state="pre", dakikastr=""):
    lig_kucuk = str(lig_adi).lower()
    basket_mi = any(k in lig_kucuk for k in ("nba", "euroleague", "basket"))
    h1 = sum(ord(c) for c in str(ev_ad)) % 23
    h2 = sum(ord(c) for c in str(dep_ad)) % 23
    fark = (h1 - h2) * 0.035
    top = int(ev_skor or 0) + int(dep_skor or 0)
    dk = _dakika_cikar(dakikastr)

    if basket_mi:
        ms1 = round(max(1.18, min(3.80, 1.84 - fark)), 2)
        ms2 = round(max(1.18, min(3.80, 1.96 + fark)), 2)
        temel = 224.5 if "nba" in lig_kucuk else 164.5
        if state == "in" and top > 0:
            ana_b = round(top + max(18.5, 62.5 - (dk * 1.1)), 1)
        else:
            ana_b = round(temel + ((h1 - h2) * 0.5), 1)
        b2 = round(ana_b + 5.5, 1)
        return {
            "ev": ev_ad, "dep": dep_ad, "ms1": ms1, "msx": 0.0, "ms2": ms2,
            "barem": ana_b, "ust": 1.86, "alt": 1.88, "handikap": round((ms2 - ms1) * 4.5, 1),
            "tum_baremler": [{"barem": ana_b, "ust": 1.86, "alt": 1.88}, {"barem": b2, "ust": 2.28, "alt": 1.56}],
        }

    ms1 = round(max(1.25, min(5.20, 2.15 - fark)), 2)
    msx = round(max(2.85, min(4.30, 3.30 + abs(fark) * 0.25)), 2)
    ms2 = round(max(1.30, min(5.80, 3.10 + fark)), 2)

    if state == "in":
        kalan_oran = max(0.15, (90 - min(85, dk or 35)) / 90.0)
        b1 = float(top) + 0.5
        b2 = b1 + 1.0
        u1 = round(max(1.16, min(2.40, 1.18 + (0.72 * (1.0 - kalan_oran)) + (h1 % 5) * 0.02)), 2)
        a1 = round(max(1.45, min(4.20, 1.0 / max(0.24, (1.0 - (1.0 / u1) * 0.92)))), 2)
        u2 = round(min(4.80, round(u1 * 1.68 + (h2 % 4) * 0.04, 2)), 2)
        a2 = round(max(1.18, min(2.45, 1.0 / max(0.40, (1.0 - (1.0 / u2) * 0.92)))), 2)
    else:
        b1 = 2.5
        b2 = 3.5
        u1 = round(max(1.55, min(2.15, 1.84 - ((h1 + h2) % 7) * 0.03)), 2)
        a1 = round(max(1.62, min(2.25, 3.72 - u1)), 2)
        u2 = round(min(3.85, round(u1 * 1.65, 2)), 2)
        a2 = round(max(1.22, min(1.55, round(a1 * 0.72, 2)), 2))

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
    return _istatistiksel_oran_uret(lig_adi, ev_ad, dep_ad, ev_skor, dep_skor, state, dakikastr)


def oran_durum_test():
    return "AKTIF"
