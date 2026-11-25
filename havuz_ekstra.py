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

def profesyonel_yorumcu_ve_suzgec(objeler, barem, tercih, oran, ai_sor_fonk):
    url_basi = "https://espn.com"
    hdr = {"User-Agent": "Mozilla/5.0"}
    mac_veri_satirlari = list()
    suzulen_toplam = 0.0
    eksik_sayisi = 0

    for mo in objeler:
        yol = str(mo.get("yol", ""))
        eid = str(mo.get("id", ""))
        ev = mo.get("ev", "")
        dep = mo.get("dep", "")
        beklenen = 2.6 if "soccer" in yol else 218.0
        sakat_not = "Kadro tam"
        hakem_not = "Hakem henüz açıklanmadı"

        if yol and yol != "euroleague_resmi" and eid:
            try:
                veri = requests.get(f"{url_basi}{yol}/summary?event={eid}", headers=hdr, timeout=5).json()
                # Sezonluk ortalama skoru çek
                comps = (((veri.get("header") or {}).get("competitions") or list()))
                if comps:
                    tlist = (comps[0].get("competitors") or list())
                    ort_top = 0.0
                    sayac = 0
                    for t in tlist:
                        for st_item in (t.get("statistics") or list()):
                            if st_item.get("name") in ("avgPoints", "avgGoals", "pointsFor"):
                                ort_top += float(st_item.get("displayValue", 0))
                                sayac += 1
                    if sayac >= 2 and ort_top > 0:
                        beklenen = round(ort_top, 1)
                # Sakatlıkları çek
                inj_list = list()
                for grp in (veri.get("injuries") or list()):
                    for item in (grp.get("injuries") or list()):
                        if str(item.get("status", "")).lower() in ("out", "doubtful"):
                            oyuncu = ((item.get("athlete") or {}).get("displayName") or "")
                            if oyuncu:
                                inj_list.append(oyuncu)
                if inj_list:
                    eksik_sayisi += len(inj_list)
                    sakat_not = f"Eksikler: {', '.join(inj_list[:4])}"
                    beklenen = round(beklenen * (0.96 if "basketball" in yol else 0.94), 1)
                # Hakem çek
                offs = ((veri.get("gameInfo") or {}).get("officials") or list())
                if offs:
                    hakem_not = "Hakem: " + ", ".join([(o.get("displayName") or "") for o in offs[:2] if o.get("displayName")])
            except Exception:
                pass

        suzulen_toplam += beklenen
        mac_veri_satirlari.append(f"- {ev} vs {dep} | Süzülen Beklenti: {beklenen} | {sakat_not} | {hakem_not}")

    suzulen_toplam = round(suzulen_toplam, 1)
    fark = round(suzulen_toplam - float(barem), 1) if tercih == "ÜST" else round(float(barem) - suzulen_toplam, 1)
    oran_pay = max(1.0, float(barem) * 0.12)
    ham_yz = 52 + int((fark / oran_pay) * 35)
    suzulen_yz = max(8, min(92, ham_yz))
    basabas_yz = round(100.0 / max(1.01, float(oran)), 1)
    deger_etiket = "DEĞERLİ FIRSAT (Büro Oranının Üstünde)" if suzulen_yz > basabas_yz else "RİSKLİ / SINIRDA (Büro Oranının Altında)"

    prompt = (
        f"Sen deneyimli, net konuşan bir spor yorumcusu ve istatistik analistisin. Asla uydurma bilgi verme, sadece aşağıdaki gerçek süzgeç verilerini yorumla.\n"
        f"Kupon Havuzu: {len(objeler)} Maç | Barem: {barem} {tercih} | Büro Oranı: {oran}\n"
        f"Süzülmüş Gerçekçi Beklenti Toplamı: {suzulen_toplam} | Süzülmüş Gelme İhtimali: %{suzulen_yz} (Başabaş Eşiği: %{basabas_yz})\n"
        f"Maç Verileri:\n" + "\n".join(mac_veri_satirlari) + "\n\n"
        f"GÖREV: Tıpkı canlı yayındaki bir baş yorumcu gibi 3 kısa paragrafta yaz:\n"
        f"1) GENEL YORUMCU KARARI: Bu havuz neden gelir veya nerede takılır? (Süzülen %{suzulen_yz} ihtimali ve {suzulen_toplam} beklentisi üzerinden net konuş)\n"
        f"2) MAÇ MAÇ KIRILMA NOKTALARI: Her maçın temposunu, eksik oyuncularını ve varsa hakem etkisini tek tek değerlendir.\n"
        f"3) RİSK SÜZGECİ & TAVSİYE: En kritik risk hangi maçta ve {oran} oran bu riske değer mi?"
    )
    yorum = str(ai_sor_fonk(prompt, max_tokens=550))
    return suzulen_yz, suzulen_toplam, deger_etiket, yorum

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
