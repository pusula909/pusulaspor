import streamlit as st

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

def profesyonel_yorumcu_ve_suzgec(mac_gercek_verileri, barem, tercih, oran, ai_sor_fonk):
    basabas_yz = round(100.0 / max(1.01, float(oran)), 1)
    prompt = (
        f"Sen deneyimli bir spor yorumcusu ve veri analistisin. Hiçbir sabit varsayılan kullanma; SADECE aşağıdaki her takımın kendi gerçek sezon ortalamalarını, son 5 maç formunu, eksiklerini ve hakem verisini hesaplayarak sonuca git.\n"
        f"Kupon Havuzu ({len(mac_gercek_verileri)} Maç) | Hedef Barem: {barem} {tercih} | Büro Oranı: {oran} (Başabaş Eşiği: %{basabas_yz})\n\n"
        f"GERÇEK MAÇ VE TAKIM İSTATİSTİKLERİ:\n" + "\n".join(mac_gercek_verileri) + "\n\n"
        f"ÇIKTI FORMATI (İlk 2 satırı kesin bu formatta ver, ardından yorumu yaz):\n"
        f"SUZULEN_TOPLAM: [Takımların kendi gerçek ortalamaları ve eksikleri süzüldüğünde beklenen toplam sayı/gol, örn: 498.5]\n"
        f"SUZULEN_IHTIMAL: [10 ile 90 arası gerçekçi tam sayı yüzde, örn: 46]\n"
        f"YORUMCU_RAPORU:\n"
        f"1) GENEL DEĞERLENDİRME: Bu havuz neden gelir veya nerede takılır? ({oran} oran başabaş eşiği %{basabas_yz}'e göre DEĞERLİ mi RİSKLİ mi?)\n"
        f"2) MAÇ MAÇ ANALİZ: Her maçtaki iki takımın kendi gerçek sayı/gol ortalamalarını, temposunu ve varsa eksik/hakem etkisini tek tek yorumla.\n"
        f"3) KRİTİK KIRILMA NOKTASI: En çok dikkat edilmesi gereken maç hangisi?"
    )
    yanit = str(ai_sor_fonk(prompt, max_tokens=600))
    suzulen_top = float(barem)
    suzulen_yz = 50
    rapor_satir = list()
    rapor_basladi = False

    for satir in yanit.splitlines():
        s = satir.strip()
        if s.upper().startswith("SUZULEN_TOPLAM:"):
            rak = "".join(c for c in s.split(":", 1)[1] if c.isdigit() or c == ".")
            if rak:
                suzulen_top = round(float(rak), 1)
        elif s.upper().startswith("SUZULEN_IHTIMAL:"):
            rak = "".join(c for c in s.split(":", 1)[1] if c.isdigit())
            if rak:
                suzulen_yz = max(8, min(92, int(rak)))
        elif s.upper().startswith("YORUMCU_RAPORU:"):
            rapor_basladi = True
        elif rapor_basladi and s:
            rapor_satir.append(s)

    deger_etiket = "DEĞERLİ FIRSAT (Oran Eşiği Üstü)" if suzulen_yz > basabas_yz else "RİSKLİ / SINIRDA (Oran Eşiği Altı)"
    temiz_rapor = "\n".join(rapor_satir) if rapor_satir else yanit
    return suzulen_yz, suzulen_top, deger_etiket, temiz_rapor

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
