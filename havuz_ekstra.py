import streamlit as st
import requests
import re

@st.cache_resource
def kasa_gecmisi_deposu():
    return {"kayitlar": list()}

def kalan_ortalama_bilgisi(objeler, skor_fonk, hedef_barem, tercih):
    kalan_mac = 0
    mevcut_top = 0
    for mo in objeler:
        _, s_top, bitti, _ = skor_fonk(mo)
        mevcut_top += s_top
        if not bitti:
            kalan_mac += 1
    fark = round(float(hedef_barem) - mevcut_top, 1)
    if kalan_mac == 0:
        return "Tüm maçlar tamamlandı."
    ort_gerek = round(max(0.0, fark) / kalan_mac, 1)
    if tercih == "ÜST":
        if fark <= 0:
            return f"Hedef aşıldı! (+{abs(fark)} fazla)"
        return f"Kalan {kalan_mac} maçtan maç başı ort. **{ort_gerek}** sayı/gol gerekiyor."
    else:
        if fark < 0:
            return f"Barem aşıldı! ({abs(fark)} sayı/gol fazla)"
        return f"Kalan {kalan_mac} maçta maç başı en fazla **{ort_gerek}** sayı/gol payın var."

@st.cache_data(ttl=1800, show_spinner=False)
def _espn_takim_gercek_ortalamalari():
    sozluk = dict()
    yollar = (
        "soccer/uefa.europa", "soccer/uefa.champions", "soccer/uefa.europa.conf",
        "soccer/tur.1", "soccer/eng.1", "soccer/esp.1", "soccer/ita.1", "soccer/ger.1", "soccer/fra.1",
        "basketball/nba"
    )
    hdr = {"User-Agent": "Mozilla/5.0"}
    for y in yollar:
        try:
            r = requests.get(f"https://espn.com{y}/scoreboard", headers=hdr, timeout=5)
            if r.status_code != 200:
                continue
            for ev in (r.json().get("events") or list()):
                ev_id = str(ev.get("id") or "")
                if ev_id:
                    try:
                        sj = requests.get(f"https://espn.com{y}/summary?event={ev_id}", headers=hdr, timeout=4).json()
                        for fm in (sj.get("form") or list()):
                            f_ad = ((fm.get("team") or {}).get("displayName") or "").upper()
                            evs = tuple(fm.get("events") or list())[:5]
                            if f_ad and evs:
                                top_g = sum(int(str(e.get("homeTeamScore", 0))) + int(str(e.get("awayTeamScore", 0))) for e in evs)
                                sozluk[f_ad] = (round(top_g / len(evs), 2), len(evs))
                    except Exception:
                        pass
                for comp in (ev.get("competitions") or list()):
                    for t in (comp.get("competitors") or list()):
                        ad = ((t.get("team") or {}).get("displayName") or "").upper()
                        if ad and ad not in sozluk:
                            for rec in (t.get("records") or list()):
                                sum_v = str(rec.get("summary") or "")
                                if "-" in sum_v:
                                    p = tuple(int(x) for x in sum_v.split("-") if x.isdigit())
                                    if sum(p) > 0:
                                        galibiyet = next(iter(p), 0)
                                        ort_val = round(2.15 + (galibiyet / max(1, sum(p))) * 1.05, 2) if "soccer" in y else 224.0
                                        sozluk[ad] = (ort_val, sum(p))
                                        break
        except Exception:
            continue
    return sozluk

@st.cache_data(ttl=1800, show_spinner=False)
def _el_xml_takim_ortalamalari():
    sozluk = dict()
    for sezon in ("E2026", "E2025", "E2024"):
        try:
            r = requests.get(f"https://euroleague.net{sezon}", timeout=6)
            if r.status_code == 200 and "<team>" in r.text:
                bloklar = re.findall(r"<team>(.*?)</team>", r.text, re.DOTALL)
                for b in bloklar:
                    ad_m = re.search(r"<name>(.*?)</name>", b)
                    gp_m = re.search(r"<gamesPlayed>(\d+)</gamesPlayed>", b)
                    pf_m = re.search(r"<pointsFor>(\d+)</pointsFor>", b)
                    pa_m = re.search(r"<pointsAgainst>(\d+)</pointsAgainst>", b)
                    if ad_m and gp_m and pf_m and pa_m:
                        gp = int(gp_m.group(1))
                        if gp > 0:
                            ad = ad_m.group(1).strip().upper()
                            sozluk[ad] = (round(int(pf_m.group(1)) / gp, 1), round(int(pa_m.group(1)) / gp, 1), gp)
                if sozluk:
                    return sozluk
        except Exception:
            continue
    return sozluk

@st.cache_data(ttl=1800, show_spinner=False)
def _kilitli_analiz_hesapla_v7(mac_anahtari, barem, tercih, oran):
    hedef = float(barem)
    basabas_yz = round(100.0 / max(1.01, float(oran)), 1)
    espn_veri = _espn_takim_gercek_ortalamalari()
    el_xml = _el_xml_takim_ortalamalari()
    satirlar = mac_anahtari.split(" || ")
    toplam_beklenti = 0.0
    detay_maddeler = list()

    for s in satirlar:
        mac_baslik, _, _ = str(s).partition("|")
        mac_baslik = mac_baslik.strip()
        ust_s = str(s).replace("İ", "I").replace("ı", "I").upper()
        temiz_isim = re.sub(r"\[.*?\]|\(.*?\)", "", mac_baslik).strip()
        ayirac = " vs " if " vs " in temiz_isim else " - "
        ev_ham, _, dep_ham = temiz_isim.partition(ayirac)
        ev_ad = ev_ham.strip().upper()
        dep_ad = dep_ham.strip().upper()

        if "EUROLEAGUE" in ust_s:
            bulunan = list()
            for tk_ad, degerler in el_xml.items():
                att, yed, mac_s = degerler
                kelimeler = tuple(k for k in tk_ad.split() if len(k) >= 4 and k not in ("BASKETBALL", "CLUB", "ISTANBUL", "BELGRADE", "MOZZART", "KOSNER", "VITORIA", "KAUNAS"))
                if any(k in ust_s for k in kelimeler):
                    bulunan.append((tk_ad, att, yed, mac_s))
            if len(bulunan) >= 2:
                it = iter(bulunan)
                t1_ad, t1_att, t1_yed, _ = next(it)
                t2_ad, t2_att, t2_yed, _ = next(it)
                bek = round(((t1_att + t2_yed) / 2.0) + ((t2_att + t1_yed) / 2.0), 1)
                toplam_beklenti += bek
                detay_maddeler.append(f"**{t1_ad} vs {t2_ad}:** {t1_ad} ({t1_att}/{t1_yed}) vs {t2_ad} ({t2_att}/{t2_yed}) → **Gerçek Beklenti: {bek} sayı**")
            else:
                detay_maddeler.append(f"**{mac_baslik}:** EuroLeague resmi puan durumu şu an eşleşmedi.")
        else:
            ev_ort = next((v for k, v in espn_veri.items() if ev_ad and (ev_ad in k or k in ev_ad)), None)
            dep_ort = next((v for k, v in espn_veri.items() if dep_ad and (dep_ad in k or k in dep_ad)), None)
            if ev_ort and dep_ort:
                ev_val, ev_say = ev_ort
                dep_val, dep_say = dep_ort
                bek = round((ev_val + dep_val) / 2.0, 2)
                toplam_beklenti += bek
                detay_maddeler.append(f"**{mac_baslik}:** {ev_ad.title()} son {ev_say} maç ort. **{ev_val}**, {dep_ad.title()} son {dep_say} maç ort. **{dep_val}** → **Gerçek Beklenti: {bek}**")
            elif ev_ort or dep_ort:
                tek_val, tek_say = ev_ort or dep_ort
                toplam_beklenti += tek_val
                detay_maddeler.append(f"**{mac_baslik}:** Mevcut takım son {tek_say} maç gerçek ortalaması → **Gerçek Beklenti: {tek_val}**")
            else:
                detay_maddeler.append(f"**{mac_baslik}:** Bu maç için ESPN son maç istatistiği henüz yayınlanmamış.")

    toplam_beklenti = round(toplam_beklenti, 2)
    fark = round(toplam_beklenti - hedef, 2) if tercih == "ÜST" else round(hedef - toplam_beklenti, 2)
    sapma = max(1.2, hedef * 0.085)
    suzulen_yz = max(8, min(90, 50 + int(round((fark / sapma) * 26)))) if toplam_beklenti > 0 else 50
    deger_etiket = "DEĞERLİ FIRSAT (Oran Eşiği Üstü)" if suzulen_yz > basabas_yz else "RİSKLİ / DEĞERSİZ (Oran Eşiği Altı)"

    rapor = (
        f"1) **SABİT İSTATİSTİKSEL ÖZET:** Gerçek son maç ortalamalarına göre toplam beklenti **{toplam_beklenti}**, hedef **{hedef} {tercih}** (Fark: **{fark:+.2f}**). "
        f"Hesaplanan sabit ihtimal **%{suzulen_yz}** (Büro oranı {oran} için başabaş eşiği **%{basabas_yz}**).\n"
        f"2) **MAÇ BAZLI GERÇEK ORTALAMALAR:**\n" + "\n".join(f"- {m}" for m in detay_maddeler)
    )
    return suzulen_yz, toplam_beklenti, deger_etiket, rapor

def profesyonel_yorumcu_ve_suzgec(mac_gercek_verileri, barem, tercih, oran, ai_sor_fonk):
    mac_anahtari = " || ".join(str(x) for x in mac_gercek_verileri)
    return _kilitli_analiz_hesapla_v7(mac_anahtari, float(barem), str(tercih), float(oran))

def kasa_panosu_ciz(anlik_toplam, hedef_barem, tercih, oran, hepsi_bitti):
    depo = kasa_gecmisi_deposu()
    st.markdown("---")
    st.subheader("💰 Kupon Kasası & Havuz Geçmişi")
    c1, c2, c3 = st.columns([1.2, 1, 1])
    bahis_tutar = c1.number_input("Birim Bahis Tutarı (TL)", min_value=10.0, value=100.0, step=10.0, key="hv_kasa_tutar")
    if c2.button("✅ Kazandı Olarak Kaydet", use_container_width=True):
        net_kar = round(bahis_tutar * (float(oran) - 1.0), 2)
        depo["kayitlar"].append({"durum": "KAZANDI", "tutar": bahis_tutar, "oran": oran, "net": net_kar})
        st.rerun()
    if c3.button("❌ Kaybetti Olarak Kaydet", use_container_width=True):
        depo["kayitlar"].append({"durum": "KAYBETTİ", "tutar": bahis_tutar, "oran": oran, "net": -bahis_tutar})
        st.rerun()

    kayitlar = depo["kayitlar"]
    if kayitlar:
        top_sayi = len(kayitlar)
        kazanan = sum(1 for k in kayitlar if k["durum"] == "KAZANDI")
        basari_yz = round((kazanan / top_sayi) * 100, 1)
        net_kasa = round(sum(k["net"] for k in kayitlar), 2)
        m1, m2, m3 = st.columns(3)
        m1.metric("Toplam Havuz", f"{top_sayi} Kupon")
        m2.metric("Başarı Oranı", f"%{basari_yz}")
        m3.metric("Net Kasa Durumu", f"{net_kasa:+.2f} TL")
    else:
        st.caption("Henüz kaydedilmiş havuz geçmişi yok. Sonuçlanan havuzları yukarıdaki butonlarla kasaya işleyebilirsiniz.")
