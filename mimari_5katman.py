import math
import requests
import streamlit as st
from datetime import datetime

_LIG_ESLESME = {
    "Trendyol Super Lig": "soccer/tur.1",
    "Ingiltere Premier Lig": "soccer/eng.1",
    "Ispanya La Liga": "soccer/esp.1",
    "Italya Serie A": "soccer/ita.1",
    "Almanya Bundesliga": "soccer/ger.1",
    "Fransa Ligue 1": "soccer/fra.1",
    "Hollanda Eredivisie": "soccer/ned.1",
    "Belcika Pro League": "soccer/bel.1",
    "Portekiz Primeira Liga": "soccer/por.1",
    "Avusturya Bundesliga": "soccer/aut.1",
    "UEFA Sampiyonlar Ligi": "soccer/uefa.champions",
    "UEFA Avrupa Ligi": "soccer/uefa.europa",
    "UEFA Konferans Ligi": "soccer/uefa.europa.conf",
    "NBA": "basketball/nba",
}

def _poisson_olasilik(lam, k):
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (math.exp(-lam) * (lam ** k)) / math.factorial(k)

def _normal_cdf(x, mu, sigma):
    if sigma <= 0:
        return 1.0 if x >= mu else 0.0
    return 0.5 * (1.0 + math.erf((x - mu) / (sigma * math.sqrt(2.0))))

@st.cache_data(ttl=1800, show_spinner=False)
def _canli_piyasa_oranlari_cek(odds_api_key):
    if not odds_api_key:
        return dict()
    sozluk = dict()
    spor_kodlari = ("soccer_turkey_super_league", "soccer_epl", "soccer_spain_la_liga", "soccer_spain_segunda_division", "soccer_italy_serie_a", "soccer_germany_bundesliga", "soccer_france_ligue_one", "soccer_netherlands_eredivisie", "soccer_belgium_first_div", "soccer_portugal_primeira_liga", "soccer_uefa_champs_league", "soccer_uefa_europa_league", "basketball_nba", "basketball_euroleague")
    for sk in spor_kodlari:
        try:
            _o_kok = "https:" + chr(47) + chr(47) + "api" + "." + "the-odds-api" + "." + "com" + chr(47) + "v4" + chr(47) + "sports" + chr(47)
            url = f"{_o_kok}{sk}/odds/?apiKey={odds_api_key}&regions=eu&markets=h2h,totals&oddsFormat=decimal"
            r = requests.get(url, timeout=4)
            if r.status_code != 200:
                continue
            for mac in r.json():
                ev = str(mac.get("home_team") or "").upper()
                dep = str(mac.get("away_team") or "").upper()
                bm = next(iter(mac.get("bookmakers") or list()), None)
                if not bm:
                    continue
                h2h_oran = dict()
                tot_hat, tot_ust, tot_alt = 0.0, 0.0, 0.0
                for mk in (bm.get("markets") or list()):
                    if mk.get("key") == "h2h":
                        for out in (mk.get("outcomes") or list()):
                            h2h_oran[str(out.get("name") or "").upper()] = float(out.get("price") or 0)
                    elif mk.get("key") == "totals":
                        for out in (mk.get("outcomes") or list()):
                            tot_hat = float(out.get("point") or 0)
                            if str(out.get("name") or "").lower() == "over":
                                tot_ust = float(out.get("price") or 0)
                            elif str(out.get("name") or "").lower() == "under":
                                tot_alt = float(out.get("price") or 0)
                if ev and dep:
                    sozluk[(ev, dep)] = {"ms1": h2h_oran.get(ev, 0.0), "msx": h2h_oran.get("DRAW", 0.0), "ms2": h2h_oran.get(dep, 0.0), "barem": tot_hat, "ust": tot_ust, "alt": tot_alt}
        except Exception:
            continue
    return sozluk

@st.cache_data(ttl=1800, show_spinner=False)
def _espn_takim_hucum_savunma(tarih_str):
    veri = dict()
    hdr = {"User-Agent": "Mozilla/5.0"}
    u_st = "https:" + chr(47) + chr(47) + "site" + "." + "api" + "." + "espn" + "." + "com" + chr(47) + "apis" + chr(47) + "v2" + chr(47) + "sports" + chr(47)
    for y in _LIG_ESLESME.values():
        r = requests.get(f"{u_st}{y}/standings", headers=hdr, timeout=4)
        if r.status_code != 200:
            continue
        gruplar = r.json().get("children") or [r.json()]
        for grp in gruplar:
            entries = ((grp.get("standings") or dict()).get("entries") or list())
            for ent in entries:
                tm = ent.get("team") or dict()
                t_ad = str(tm.get("displayName") or "").upper()
                st_map = {str(s.get("name") or ""): float(s.get("value") or 0) for s in (ent.get("stats") or list()) if s.get("value") is not None}
                gp = st_map.get("gamesPlayed", 0.0)
                att = st_map.get("pointsFor", st_map.get("goalsFor", 0.0))
                yed = st_map.get("pointsAgainst", st_map.get("goalsAgainst", 0.0))
                if t_ad and gp >= 2 and (att > 0 or yed > 0):
                    veri[t_ad] = (round(att / gp, 2), round(yed / gp, 2), int(gp))
    return veri
def _kayit_orani(kayit_str):
    parcalar = tuple(int(x) for x in str(kayit_str or "").split("-") if x.isdigit())
    if not parcalar or sum(parcalar) == 0:
        return 0.50
    gal = next(iter(parcalar), 0)
    return max(0.15, min(0.88, gal / sum(parcalar)))

def bes_katman_analiz(spor, lig_adi, ev_ad, dep_ad, ev_rec, dep_rec, state="pre", ev_skor=0, dep_skor=0, detay_sure="", odds_api_key=""):
    tarih_str = datetime.now().strftime("%Y%m%d")
    takim_stats = _espn_takim_hucum_savunma(tarih_str)
    piyasa_map = _canli_piyasa_oranlari_cek(odds_api_key)

    ev_u = str(ev_ad).upper()
    dep_u = str(dep_ad).upper()
    ev_st = next((v for k, v in takim_stats.items() if ev_u and (ev_u in k or k in ev_u)), None)
    dep_st = next((v for k, v in takim_stats.items() if dep_u and (dep_u in k or k in dep_u)), None)
    piyasa = next((v for (pe, pd), v in piyasa_map.items() if (ev_u in pe or pe in ev_u) and (dep_u in pd or pd in dep_u)), dict())

    ev_guc = _kayit_orani(ev_rec)
    dep_guc = _kayit_orani(dep_rec)

    if spor == "Futbol":
        lig_ort_gol = 1.35
        if ev_st and dep_st:
            ev_att, ev_yed, _ = ev_st
            dep_att, dep_yed, _ = dep_st
            lam_ev = max(0.35, min(3.4, ((ev_att / lig_ort_gol) * (dep_yed / lig_ort_gol) * lig_ort_gol) * 1.06))
            lam_dep = max(0.30, min(3.1, ((dep_att / lig_ort_gol) * (ev_yed / lig_ort_gol) * lig_ort_gol) * 0.94))
            veri_kaynagi = "Poisson + Son 6 Mac Gol"
        else:
            lam_ev = max(0.45, min(2.6, 1.05 + (ev_guc - dep_guc) * 1.15 + 0.15))
            lam_dep = max(0.40, min(2.4, 1.00 + (dep_guc - ev_guc) * 1.10))
            veri_kaynagi = "Poisson + Form Modeli"

        import re as _re
        _dk_m = _re.search(r"(\d+)", str(durum_detay or ""))
        _dk = int(_dk_m.group(1)) if _dk_m else (45 if "HT" in str(durum_detay or "").upper() else 30)
        _kalan = max(0.08, min(0.95, (90.0 - min(88, _dk)) / 90.0)) if state == "in" else 1.0
        _c_ev = ev_skor if state == "in" else 0
        _c_dep = dep_skor if state == "in" else 0

        p1, px, p2, p_ust25 = 0.0, 0.0, 0.0, 0.0
        for g_ev in range(6):
            pe = _poisson_olasilik(lam_ev * _kalan, g_ev)
            for g_dep in range(6):
                pd_ = _poisson_olasilik(lam_dep * _kalan, g_dep)
                olas = pe * pd_
                if (_c_ev + g_ev) > (_c_dep + g_dep):
                    p1 += olas
                elif (_c_ev + g_ev) == (_c_dep + g_dep):
                    px += olas
                else:
                    p2 += olas
                if (_c_ev + _c_dep + g_ev + g_dep) >= 3:
                    p_ust25 += olas

        yz1 = int(round(p1 * 100))
        yzx = int(round(px * 100))
        yz2 = int(round(p2 * 100))
        yz_ust = int(round(p_ust25 * 100))
        yz_alt = max(5, 100 - yz_ust)
        bek_gol = round(lam_ev + lam_dep, 2)

        if yz1 >= 56:
            ana_tercih, guven, b_oran = f"{ev_ad} Kazanir (MS 1)", yz1, piyasa.get("ms1", 0.0)
        elif yz2 >= 55:
            ana_tercih, guven, b_oran = f"{dep_ad} Kazanir (MS 2)", yz2, piyasa.get("ms2", 0.0)
        elif (yz1 + yzx) >= 74 and yz1 >= 40:
            ana_tercih, guven, b_oran = f"{ev_ad} Yenilmez (1X)", min(82, yz1 + yzx), 0.0
        elif (yz1 + yzx) >= 74 and yz1 >= 40:
            _cs1x = round(1.0 / ((1.0 / piyasa["ms1"]) + (1.0 / piyasa["msx"])), 2) if piyasa.get("ms1", 0) > 1 and piyasa.get("msx", 0) > 1 else 0.0
            ana_tercih, guven, b_oran = f"{ev_ad} Yenilmez (1X)", min(82, yz1 + yzx), _cs1x
        elif (yz2 + yzx) >= 74 and yz2 >= 40:
            _csx2 = round(1.0 / ((1.0 / piyasa["ms2"]) + (1.0 / piyasa["msx"])), 2) if piyasa.get("ms2", 0) > 1 and piyasa.get("msx", 0) > 1 else 0.0
            ana_tercih, guven, b_oran = f"{dep_ad} Yenilmez (X2)", min(82, yz2 + yzx), _csx2
        else:
            ana_tercih, guven, b_oran = f"PAS GEC (MS1:%{yz1} X:%{yzx} MS2:%{yz2})", max(yz1, yzx, yz2), 0.0

        if state == "in":
            canli_hat = (ev_skor + dep_skor) + 0.5
            barem_tercih = f"Canli {canli_hat} UST (Beklenti: {bek_gol})"
            barem_guven = min(84, max(54, yz_ust))
        elif yz_ust >= 58:
            barem_tercih = f"2.5 UST (Beklenti: {bek_gol} gol)"
            barem_guven = yz_ust
        elif yz_alt >= 58:
            barem_tercih = f"2.5 ALT (Beklenti: {bek_gol} gol)"
            barem_guven = yz_alt
        else:
            barem_tercih = f"Barem Pas Gec (Beklenti: {bek_gol} gol)"
            barem_guven = max(yz_ust, yz_alt)

    else:
        is_nba = "NBA" in str(lig_adi).upper()
        lig_ort = 113.5 if is_nba else 82.5
        sigma_fark = 11.5 if is_nba else 9.5
        sigma_top = 14.5 if is_nba else 11.5

        if ev_st and dep_st:
            ev_att, ev_yed, _ = ev_st
            dep_att, dep_yed, _ = dep_st
            bek_ev = ((ev_att + dep_yed) / 2.0) + (2.5 if is_nba else 2.0)
            bek_dep = ((dep_att + ev_yed) / 2.0) - (1.5 if is_nba else 1.0)
            veri_kaynagi = "Normal Dagilim + Son 6 Mac"
        else:
            fark_puan = (ev_guc - dep_guc) * (18.0 if is_nba else 14.0) + (2.8 if is_nba else 2.2)
            bek_ev = lig_ort + (fark_puan / 2.0)
            bek_dep = lig_ort - (fark_puan / 2.0)
            veri_kaynagi = "Normal Dagilim + Form Modeli"

        bek_fark = bek_ev - bek_dep
        bek_top = round(bek_ev + bek_dep, 1)
        p1 = 1.0 - _normal_cdf(0.0, bek_fark, sigma_fark)
        yz1 = int(round(p1 * 100))
        yz2 = max(5, 100 - yz1)

        if yz1 >= 60:
            ana_tercih, guven, b_oran = f"{ev_ad} Kazanir (MS 1)", yz1, piyasa.get("ms1", 0.0)
        elif yz2 >= 60:
            ana_tercih, guven, b_oran = f"{dep_ad} Kazanir (MS 2)", yz2, piyasa.get("ms2", 0.0)
        else:
            ana_tercih, guven, b_oran = f"PAS GEC (MS1:%{yz1} MS2:%{yz2})", max(yz1, yz2), 0.0

        piyasa_hat = float(piyasa.get("barem") or 0.0)
        aktif_hat = piyasa_hat if piyasa_hat > 0 else (round(bek_top - 3.5) + 0.5 if bek_top >= (231.0 if is_nba else 168.0) else (round(bek_top + 3.5) + 0.5 if bek_top <= (221.0 if is_nba else 158.0) else 0.0))
        if state == "in" and (ev_skor + dep_skor) > 0:
            canli_hat = round(bek_top) - 0.5
            barem_tercih = f"Canli {canli_hat} (Projeksiyon: {bek_top})"
            barem_guven = 66
        elif aktif_hat > 0:
            p_ust = 1.0 - _normal_cdf(aktif_hat, bek_top, sigma_top)
            yz_u = int(round(p_ust * 100))
            if yz_u >= 56:
                barem_tercih, barem_guven = f"{aktif_hat} UST (Proj: {bek_top})", yz_u
            elif (100 - yz_u) >= 56:
                barem_tercih, barem_guven = f"{aktif_hat} ALT (Proj: {bek_top})", (100 - yz_u)
            else:
                barem_tercih, barem_guven = f"Barem Pas Gec ({aktif_hat} | Proj: {bek_top})", max(yz_u, 100 - yz_u)
        else:
            barem_tercih = f"Barem Pas Gec (Projeksiyon: {bek_top} sayi)"
            barem_guven = 50

    adil_oran = round(100.0 / max(10, guven), 2)
    pas_mi = "PAS GEC" in ana_tercih
    ev_yuzde = round(((guven / 100.0) * b_oran - 1.0) * 100, 1) if (b_oran and b_oran > 1.01) else 0.0

    if pas_mi:
        karar_etiket = "⚪ PAS GEÇ (Dengeli)"
    elif b_oran and b_oran > 1.01 and ev_yuzde >= 2.0:
        karar_etiket = "🟢 DEĞERLİ FIRSAT"
    elif b_oran and b_oran > 1.01 and ev_yuzde < 0:
        karar_etiket = "🟡 FAVORİ (Oran Düşük)"
    else:
        karar_etiket = "🔵 İSTATİSTİK ÜSTÜN"

    oran_sutun = f"%{guven} | Büro: {b_oran}" if (b_oran and b_oran > 1.01) else f"%{guven} | Adil: {adil_oran}"
    ev_sutun = f"🔥 {ev_yuzde:+.1f}%" if ev_yuzde >= 2.0 else (f"⚠️ {ev_yuzde:+.1f}%" if (b_oran and b_oran > 1.01) else "—")
    deger_puani = round(min(9.6, max(3.5, (guven / 10.0) - (1.8 if pas_mi else 0.0))), 1)
    ozet_satir = f"{karar_etiket} | {ana_tercih} ({oran_sutun})"

    return {
        "ana_tercih": ana_tercih,
        "guven": guven,
        "barem_tercih": barem_tercih,
        "barem_guven": barem_guven,
        "deger_puani": deger_puani,
        "ozet_satir": ozet_satir,
        "karar_etiket": karar_etiket,
        "oran_sutun": oran_sutun,
        "ev_sutun": ev_sutun,
    }
