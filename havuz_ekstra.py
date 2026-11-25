import streamlit as st
import requests

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
def _euroleague_gercek_istatistikler_v2():
    sozluk = dict()
    for sezon in ("E2026", "E2025", "E2024"):
        try:
            r = requests.get(f"https://euroleague.net{sezon}/seasons/{sezon}/standings", timeout=6)
            if r.status_code == 200:
                veri = r.json()
                gruplar = veri if isinstance(veri, list) else veri.get("standings", list())
                for grup in gruplar:
                    satirlar = grup.get("teams", grup) if isinstance(grup, dict) else list()
                    for t in (satirlar if isinstance(satirlar, list) else list()):
                        club = t.get("club") or t.get("team") or dict()
                        ad = (club.get("name") or club.get("editorialName") or "").upper()
                        gp = float(t.get("gamesPlayed") or t.get("played") or 0)
                        pf = float(t.get("pointsFor") or t.get("scored") or 0)
                        pa = float(t.get("pointsAgainst") or t.get("conceded") or 0)
                        if ad and gp > 0 and pf > 0:
                            sozluk[ad] = (round(pf / gp, 1), round(pa / gp, 1), int(gp))
                if sozluk:
                    return sozluk
        except Exception:
            continue
    return sozluk

@st.cache_data(ttl=1800, show_spinner=False)
def _kilitli_analiz_hesapla_v2(mac_anahtari, barem, tercih, oran):
    hedef = float(barem)
    basabas_yz = round(100.0 / max(1.01, float(oran)), 1)
    el_veri = _euroleague_gercek_istatistikler_v2()
    satirlar = mac_anahtari.split(" || ")
    toplam_beklenti = 0.0
    detay_maddeler = list()

    for s in satirlar:
        ust_s = s.upper()
        mac_baslik = s.split("|")[0].strip()
        if "EUROLEAGUE" in ust_s:
            bulunan = list()
            for tk_ad, (att, yed, mac_s) in el_veri.items():
                kelimeler = [k for k in tk_ad.split() if len(k) >= 4 and k not in ("BASKETBALL", "CLUB", "ISTANBUL", "BELGRADE", "MOZZART", "KOSNER", "VITORIA", "KAUNAS")]
                if any(k in ust_s for k in kelimeler):
                    bulunan.append((tk_ad, att, yed, mac_s))
            if len(bulunan) >= 2:
                ev_t = bulunan[0]
                dep_t = bulunan[1]
                bek = round(((ev_t[1] + dep_t[2]) / 2.0) + ((dep_t[1] + ev_t[2]) / 2.0), 1)
                toplam_beklenti += bek
                detay_maddeler.append(f"**{ev_t[0]} vs {dep_t[0]}:** {ev_t[0]} maç başı **{ev_t[1]}** atıp **{ev_t[2]}** yiyor ({ev_t[3]} maç); {dep_t[0]} maç başı **{dep_t[1]}** atıp **{dep_t[2]}** yiyor ({dep_t[3]} maç) → **Gerçek Beklenti: {bek} sayı**")
            elif len(bulunan) == 1:
                t_tek = bulunan[0]
                bek = round(t_tek[1] + t_tek[2], 1)
                toplam_beklenti += bek
                detay_maddeler.append(f"**{mac_baslik}:** {t_tek[0]} maç başı **{t_tek[1]}** atıp **{t_tek[2]}** yiyor ({t_tek[3]} maç) → **Gerçek Tempo Beklentisi: {bek} sayı**")
            else:
                detay_maddeler.append(f"**{mac_baslik}:** EuroLeague resmi API şu an yanıt vermedi (sabit sayı eklenmedi).")
        elif any(x in ust_s for x in ("SOCCER", "LİG", "PREMIER", "LIGA", "SERIE", "BUNDESLIGA", "ŞAMPİYONLAR")):
            toplam_beklenti += 2.65
            detay_maddeler.append(f"**{mac_baslik}:** Futbol lig ortalaması → **2.65 gol**")
        else:
            toplam_beklenti += 224.0
            detay_maddeler.append(f"**{mac_baslik}:** Basketbol ortalaması → **224.0 sayı**")

    toplam_beklenti = round(toplam_beklenti, 1)
    fark = round(toplam_beklenti - hedef, 1) if tercih == "ÜST" else round(hedef - toplam_beklenti, 1)
    sapma = max(2.0, hedef * 0.075)
    suzulen_yz = max(8, min(90, 50 + int(round((fark / sapma) * 26))))
    deger_etiket = "DEĞERLİ FIRSAT (Oran Eşiği Üstü)" if suzulen_yz > basabas_yz else "RİSKLİ / DEĞERSİZ (Oran Eşiği Altı)"

    rapor = (
        f"1) **SABİT İSTATİSTİKSEL ÖZET:** Gerçek sezon ortalamalarına göre toplam beklenti **{toplam_beklenti}**, hedef **{hedef} {tercih}** (Fark: **{fark:+.1f}**). "
        f"Hesaplanan sabit ihtimal **%{suzulen_yz}** (Büro oranı {oran} için başabaş eşiği **%{basabas_yz}**).\n"
        f"2) **MAÇ BAZLI GERÇEK ORTALAMALAR:**\n" + "\n".join(f"- {m}" for m in detay_maddeler)
    )
    return suzulen_yz, toplam_beklenti, deger_etiket, rapor

def profesyonel_yorumcu_ve_suzgec(mac_gercek_verileri, barem, tercih, oran, ai_sor_fonk):
    mac_anahtari = " || ".join(str(x) for x in mac_gercek_verileri)
    return _kilitli_analiz_hesapla_v2(mac_anahtari, float(barem), str(tercih), float(oran))

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
