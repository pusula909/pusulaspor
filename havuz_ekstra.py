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

def _mac_web_istihbarat_cek(mac_metni):
    parca_ilk = mac_metni.split("|")[0]
    for etiket in ("[EuroLeague]", "[Şampiyonlar Ligi]", "[Süper Lig]", "[Premier Lig]", "[La Liga]", "[Serie A]", "[Bundesliga]", "[NBA]"):
        parca_ilk = parca_ilk.replace(etiket, "")
    temiz_ad = parca_ilk.strip()
    parcalar = temiz_ad.split("vs") if "vs" in temiz_ad else temiz_ad.split("-")
    t1 = parcalar[0].strip() if len(parcalar) >= 1 else temiz_ad
    t2 = parcalar[1].strip() if len(parcalar) >= 2 else ""

    notlar = list()
    try:
        try:
            from ddgs import DDGS
        except Exception:
            from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            sorgular = [
                f"{t1} {t2} stats score average",
                f"{t1} {t2} injury news form"
            ]
            for q in sorgular:
                sonuclar = list(ddgs.text(q, max_results=3))
                for s in sonuclar:
                    baslik = str(s.get("title", "")).strip()
                    govde = str(s.get("body", "")).strip()
                    oz = f"{baslik}: {govde}"[:240].replace("\n", " ")
                    if oz.strip():
                        notlar.append(oz)
    except Exception as e:
        notlar.append(f"Arama notu: {e}")

    return " // ".join(notlar[:4]) if notlar else "Ek web haberi bulunamadı."

def profesyonel_yorumcu_ve_suzgec(mac_gercek_verileri, barem, tercih, oran, ai_sor_fonk):
    hedef = float(barem)
    basabas_yz = round(100.0 / max(1.01, float(oran)), 1)
    zengin_veriler = list()

    for satir in mac_gercek_verileri:
        s_str = str(satir)
        web_bilgi = _mac_web_istihbarat_cek(s_str)
        zengin_veriler.append(f"MAÇ VERİSİ: {s_str}\nCANLI WEB TARAMA SONUÇLARI: {web_bilgi}")

    prompt = (
        f"Sen profesyonel bir spor veri analisti ve bahis yorumcususun. Aşağıda her maç için sistem verisi ve canlı web tarama sonuçları verilmiştir.\n"
        f"Bu verileri kullanarak her takımın gücünü, güncel formunu, sakatlık/kadro durumunu ve skor/gol ortalamasını değerlendir ve mutlaka net sayısal tahmin üret.\n"
        f"Havuz: {len(mac_gercek_verileri)} Maç | Hedef Barem: {hedef} {tercih} | Büro Oranı: {oran} (Başabaş Eşiği: %{basabas_yz})\n\n"
        + "\n\n".join(zengin_veriler) + "\n\n"
        f"ZORUNLU ÇIKTI FORMATI (İlk 2 satırı mutlaka sadece rakamla doldur, asla parantez veya açıklama yazma):\n"
        f"BEKLENTI_TOPLAM: 498.5\n"
        f"GELME_IHTIMALI: 54\n"
        f"ANALIZ_METNI:\n"
        f"1) MAÇ MAÇ ANALİZ: Her maçtaki takımların güncel formunu, hücum/savunma temposunu ve web taramasından gelen haber/eksik bilgilerini tek tek yorumla.\n"
        f"2) HAVUZ HESABI & KARAR: {hedef} {tercih} baremine göre toplam beklenti kaç çıkıyor, {oran} oran (%{basabas_yz} eşiği) değerli mi riskli mi net karar ver."
    )

    yanit = str(ai_sor_fonk(prompt, max_tokens=850))
    toplam_beklenti = hedef
    suzulen_yz = 50
    rapor_satir = list()
    rapor_basladi = False

    for satir in yanit.splitlines():
        s = satir.strip()
        if s.upper().startswith("BEKLENTI_TOPLAM:"):
            rak = "".join(c for c in s.split(":", 1)[1] if c.isdigit() or c == ".")
            if rak:
                toplam_beklenti = round(float(rak), 1)
        elif s.upper().startswith("GELME_IHTIMALI:"):
            rak = "".join(c for c in s.split(":", 1)[1] if c.isdigit())
            if rak:
                suzulen_yz = max(8, min(92, int(rak)))
        elif s.upper().startswith("ANALIZ_METNI:"):
            rapor_basladi = True
        elif rapor_basladi and s:
            rapor_satir.append(s)

    deger_etiket = "DEĞERLİ FIRSAT (Oran Eşiği Üstü)" if suzulen_yz > basabas_yz else "RİSKLİ / DEĞERSİZ (Oran Eşiği Altı)"
    temiz_rapor = "\n".join(rapor_satir) if rapor_satir else yanit
    return suzulen_yz, toplam_beklenti, deger_etiket, temiz_rapor

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
