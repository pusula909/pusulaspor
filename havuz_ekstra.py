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

def _el_takim_ortalamalari():
    try:
        for sezon in ("E2026", "E2025", "E2024"):
            r = requests.get(f"https://euroleague.net{sezon}/seasons/{sezon}/standings", timeout=5)
            if r.status_code == 200:
                veri = r.json()
                sozluk = dict()
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
                            sozluk[ad] = (round(pf / gp, 1), round(pa / gp, 1))
                if sozluk:
                    return sozluk
        return dict()
    except Exception:
        return dict()

def profesyonel_yorumcu_ve_suzgec(mac_gercek_verileri, barem, tercih, oran, ai_sor_fonk):
    el_ort = _el_takim_ortalamalari()
    analiz_satirlari = list()
    toplam_beklenti = 0.0

    for satir in mac_gercek_verileri:
        s_str = str(satir)
        if "EUROLEAGUE" in s_str.upper():
            eslesen = list()
            for tk_ad, degerler in el_ort.items():
                kelimeler = [k for k in tk_ad.split() if len(k) >= 4]
                if any(k in s_str.upper() for k in kelimeler):
                    eslesen.append((tk_ad, degerler, degerler))
            if len(eslesen) >= 2:
                t1 = eslesen
                t2 = eslesen
                m_bek = round(((t1 + t2) / 2.0) + ((t1 + t2) / 2.0), 1)
                toplam_beklenti += m_bek
                analiz_satirlari.append(f"{s_str} | Gerçek Sezon Ort: {t1} ({t1} atıyor/{t1} yiyor) vs {t2} ({t2} atıyor/{t2} yiyor) -> Maç Beklentisi: {m_bek}")
            else:
                toplam_beklenti += 165.0
                analiz_satirlari.append(f"{s_str} | EuroLeague Lig Ortalaması: 165.0")
        elif any(x in s_str.upper() for x in ("SOCCER", "LİG", "PREMIER", "LIGA", "SERIE", "BUNDESLIGA")):
            toplam_beklenti += 2.65
            analiz_satirlari.append(s_str)
        else:
            toplam_beklenti += 224.0
            analiz_satirlari.append(s_str)

    toplam_beklenti = round(toplam_beklenti, 1)
    hedef = float(barem)
    fark = round(toplam_beklenti - hedef, 1) if tercih == "ÜST" else round(hedef - toplam_beklenti, 1)
    standart_sapma = max(2.0, hedef * 0.085)
    ham_yz = 50 + int(round((fark / standart_sapma) * 28))
    suzulen_yz = max(8, min(90, ham_yz))
    basabas_yz = round(100.0 / max(1.01, float(oran)), 1)
    deger_etiket = "DEĞERLİ FIRSAT (Oran Eşiği Üstü)" if suzulen_yz > basabas_yz else "RİSKLİ / DEĞERSİZ (Oran Eşiği Altı)"

    prompt = (
        f"SEN BİR VERİ ANALİSTİSİN. KESİN KURAL: Aşağıda verilmeyen hiçbir bilgiyi (sakatlık, kadro, hakem vb.) ASLA UYDURMA. Sadece verilen sayıları özetle.\n"
        f"Havuz: {len(mac_gercek_verileri)} Maç | Barem: {hedef} {tercih} | Büro Oranı: {oran} (Başabaş Eşiği: %{basabas_yz})\n"
        f"Sabit Matematiksel Beklenti: {toplam_beklenti} | Sabit İhtimal: %{suzulen_yz} ({deger_etiket})\n"
        f"Veriler:\n" + "\n".join(analiz_satirlari) + "\n\n"
        f"3 kısa madde yaz (uydurma bilgi kesinlikle yasak, tüm maçları eksiksiz yaz):\n"
        f"1) MATEMATİKSEL ÖZET: {toplam_beklenti} beklenti ile {hedef} {tercih} baremi arasındaki {fark:+.1f} farkı ve %{suzulen_yz} ihtimali yorumla.\n"
        f"2) MAÇ BAZLI VERİLER: Listedeki {len(mac_gercek_verileri)} maçın tamamının gerçek sayı ortalamalarını kısa ve net özetle.\n"
        f"3) RİSK KARARI: {oran} oran için başabaş eşiği %{basabas_yz} iken %{suzulen_yz} ihtimalle bu bahis mantıklı mı?"
    )
    yorum = str(ai_sor_fonk(prompt, max_tokens=750))
    return suzulen_yz, toplam_beklenti, deger_etiket, yorum

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
