import os
import json
from datetime import datetime, timedelta, timezone
import requests

try:
    from google import genai
    GEMINI_AKTIF = True
except Exception:
    GEMINI_AKTIF = False


class PusulaAnalizBeyni:
    def __init__(self, gemini_key="", groq_key=""):
        self.gemini_key = (gemini_key or os.environ.get("GEMINI_KEY", "")).strip()
        self.groq_key = (groq_key or os.environ.get("GROQ_KEY", "")).strip()
        self.arsiv_dosya = "haftalik_arsiv.json"
        self.evrim_dosya = "ai_evrim_hafizasi.json"
    def _ai_sor(self, prompt, max_tokens=450):
        g_key = str(self.gemini_key or "").strip()
        q_key = str(self.groq_key or "").strip()
        son_hata = "Bilinmiyor"
       if g_key:
            g_host = ".".join(["generativelanguage", "googleapis", "com"])
            for m in ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"):
                try:
                    u = f"https://{g_host}/v1beta/models/{m}:generateContent?key={g_key}"
                    r = requests.post(u, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15).json()
                    adaylar = r.get("candidates", list())
                    if adaylar:
                        parcalar = adaylar.pop(0).get("content", {}).get("parts", list())
                        if parcalar:
                            txt = parcalar.pop(0).get("text", "").strip()
                            if txt:
                                return txt
                    son_hata = str(r.get("error", {}).get("message", r))[:140]
                except Exception as e:
                    son_hata = str(e)[:140]
        if q_key:
            q_host = ".".join(["api", "groq", "com"])
            q_url = f"https://{q_host}/openai/v1/chat/completions"
            for m in ("llama-3.3-70b-versatile", "llama-3.1-8b-instant"):
                try:
                    r = requests.post(
                        q_url,
                        headers={"Authorization": f"Bearer {q_key}", "Content-Type": "application/json"},
                        json={"model": m, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3, "max_tokens": max_tokens},
                        timeout=15,
                    ).json()
                    secenekler = r.get("choices", list())
                    if secenekler:
                        txt = secenekler.pop(0).get("message", {}).get("content", "").strip()
                        if txt:
                            return txt
                    son_hata = str(r.get("error", {}).get("message", r))[:140]
                except Exception as e:
                    son_hata = str(e)[:140]
        return f"⚠️ AI Yanit Detayi: {son_hata}"

    def _evrim_hafizasi_oku(self):
        if os.path.exists(self.evrim_dosya):
            try:
                with open(self.evrim_dosya, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"versiyon": 1, "son_guncelleme": "", "ogrenilen_kurallar": [], "lig_ayarlari": {}}
    def gece_kendini_gelistir(self):
        if not os.path.exists(self.arsiv_dosya):
            return ""
        try:
            with open(self.arsiv_dosya, "r", encoding="utf-8") as f:
                arsiv = json.load(f)
        except Exception:
            return ""
        if len(arsiv) < 3:
            return ""

        hafiza = self._evrim_hafizasi_oku()
        bugun_str = datetime.now(timezone(timedelta(hours=3))).strftime("%d.%m.%Y")

        lig_istatistik = {}
        for k in arsiv[-50:]:
            l_ad = k.get("lig", "")
            if not l_ad:
                continue
            if l_ad not in lig_istatistik:
                lig_istatistik[l_ad] = {"top": 0, "hit": 0}
            lig_istatistik[l_ad]["top"] += 1
            if k.get("tuttu"):
                lig_istatistik[l_ad]["hit"] += 1

        yeni_lig_ayarlari = {}
        for l_ad, v in lig_istatistik.items():
            if v["top"] >= 3:
                oran = v["hit"] / v["top"]
                if oran < 0.45:
                    yeni_lig_ayarlari[l_ad] = -10
                elif oran < 0.55:
                    yeni_lig_ayarlari[l_ad] = -5
                elif oran >= 0.75:
                    yeni_lig_ayarlari[l_ad] = +6
                else:
                    yeni_lig_ayarlari[l_ad] = 0

        son_kayitlar = arsiv[-15:]
        ozet_metin = "\n".join(
            f"- [{x.get('lig')}] Sonuc: {'TUTTU' if x.get('tuttu') else 'YATTI'}"
            for x in son_kayitlar
        )
        mevcut_kurallar = "\n".join(hafiza.get("ogrenilen_kurallar", [])[-8:])

        prompt = (
            f"Sen kendi kendini gelistiren bir Spor Analiz Yapay Zekasisin.\n"
            f"Son 15 tahmin sonucun:\n{ozet_metin}\n\n"
            f"Mevcut Kurallarin:\n{mevcut_kurallar}\n\n"
            f"Gorevin: Yatan tahminlere bakarak kendine TEK CUMLELIK, somut ve yeni bir 'Kendi Kendini Duzeltme Kurali' yaz. Sadece yeni kurali yaz."
        )

        yeni_kural = self._ai_sor(prompt, max_tokens=120)
        kurallar = hafiza.get("ogrenilen_kurallar", [])
        if yeni_kural and len(yeni_kural) > 10:
            kurallar.append(f"[{bugun_str}] {yeni_kural}")

        yeni_versiyon = hafiza.get("versiyon", 1) + 1
        hafiza["versiyon"] = yeni_versiyon
        hafiza["son_guncelleme"] = bugun_str
        hafiza["ogrenilen_kurallar"] = kurallar[-25:]
        hafiza["lig_ayarlari"] = yeni_lig_ayarlari

        with open(self.evrim_dosya, "w", encoding="utf-8") as f:
            json.dump(hafiza, f, ensure_ascii=False, indent=2)

        return f"🧬 AI SISTEM KENDINI GUNCELLEDI (v{yeni_versiyon}.0)\n📌 Yeni Ogrenilen Kural: {yeni_kural}"

    def _oran_coz(self, rec_str):
        try:
            parcalar = [int(x) for x in str(rec_str).split("-") if x.strip().isdigit()]
            toplam = sum(parcalar)
            if len(parcalar) >= 2 and toplam > 0:
                return (parcalar[0] + 2) / (toplam + 4)
        except Exception:
            pass
        return 0.50
    def mac_deger_analizi(
        self,
        spor_turu,
        lig_adi,
        ev_ad,
        dep_ad,
        ev_rec="1-1",
        dep_rec="1-1",
        ev_eksik_puan=0,
        dep_eksik_puan=0,
        piyasa_barem=0.0,
        piyasa_handikap="",
        state="pre",
        ev_skor=0,
        dep_skor=0,
        detay_sure="",
        ev_yorgun=False,
        dep_yorgun=False,
        piyasa_tuzak_notu="",
        kotu_hava=False
    ):
        ev_guc = self._oran_coz(ev_rec)
        dep_guc = self._oran_coz(dep_rec)

        hafiza = self._evrim_hafizasi_oku()
        kalibrasyon_puani = hafiza.get("lig_ayarlari", {}).get(lig_adi, 0)
        versiyon = hafiza.get("versiyon", 1)

        ev_avantaj = 0.05 if spor_turu == "Futbol" else 0.04
        ev_yorgun_ceza = 0.09 if ev_yorgun else 0.0
        dep_yorgun_ceza = 0.11 if dep_yorgun else 0.0

        ev_net = max(0.08, min(0.92, ev_guc + ev_avantaj - (ev_eksik_puan * 0.025) - ev_yorgun_ceza))
        dep_net = max(0.08, min(0.92, dep_guc - (dep_eksik_puan * 0.025) - dep_yorgun_ceza))

        if state == "in":
            fark = ev_skor - dep_skor
            if spor_turu == "Futbol":
                ev_net = max(0.05, min(0.95, ev_net + (fark * 0.16)))
                dep_net = max(0.05, min(0.95, dep_net - (fark * 0.16)))
            else:
                ev_net = max(0.05, min(0.95, ev_net + (fark * 0.022)))
                dep_net = max(0.05, min(0.95, dep_net - (fark * 0.022)))

        guc_farki = ev_net - dep_net
        abs_fark = abs(guc_farki)

        tuzak_notu = ""
        if spor_turu == "Futbol":
            if guc_farki >= 0.16:
                ana_tercih = f"{ev_ad} Kazanir (MS 1)"
                ham_guven = int(56 + abs_fark * 48)
            elif guc_farki <= -0.16:
                ana_tercih = f"{dep_ad} Kazanir (MS 2)"
                ham_guven = int(55 + abs_fark * 48)
            else:
                ana_tercih = "Cifte Sans 1X / Dengeli Mac"
                ham_guven = int(62 + (0.16 - abs_fark) * 35)
                tuzak_notu = "Taraf bahsi riskli, iki takim birbirine cok yakin."
        else:
            if guc_farki >= 0.14:
                ana_tercih = f"{ev_ad} Kazanir (MS 1)"
                ham_guven = int(57 + abs_fark * 50)
            elif guc_farki <= -0.14:
                ana_tercih = f"{dep_ad} Kazanir (MS 2)"
                ham_guven = int(56 + abs_fark * 50)
            else:
                ana_tercih = "Taraf Riskli -> Toplam Sayi / Handikap Odakli"
                ham_guven = 64
                tuzak_notu = "Kafa kafaya mac; taraf yerine barem degerlendirilmeli."

        guven = max(48, min(90, ham_guven + kalibrasyon_puani))
        if kalibrasyon_puani <= -8 and not tuzak_notu:
            tuzak_notu = f"Oto-Evrim (v{versiyon}.0): Bu ligde son donemde dusuk isabet nedeniyle risk kirildi."
        if piyasa_tuzak_notu:
            tuzak_notu = f"🚨 PIYASA TUZAGI: {piyasa_tuzak_notu}"
        elif ev_yorgun and guc_farki > 0:
            tuzak_notu = f"⚠️ YORGUNLUK ALARMI: {ev_ad} dun mac yapti (Back-to-Back), surpriz riski yuksek!"
        elif dep_yorgun and guc_farki < 0:
            tuzak_notu = f"⚠️ YORGUNLUK ALARMI: {dep_ad} dun mac yapti (Deplasman Back-to-Back), riskli!"
        elif kotu_hava and spor_turu == "Futbol":
            tuzak_notu = "🌧️ HAVA & ZEMIN UYARISI: Kotu hava kosullari nedeniyle UST yerine ALT odaklanilmali."

        toplam_skor = ev_skor + dep_skor
        if spor_turu == "Futbol":
            if state == "in":
                barem_tercih = f"Canli {toplam_skor + 0.5} UST"
                barem_guven = min(82, int(60 + (ev_net + dep_net) * 14))
            elif ev_net >= 0.52 and dep_net >= 0.48:
                barem_tercih = "Toplam 2.5 UST"
                barem_guven = min(80, int(58 + (ev_net + dep_net) * 15))
            else:
                barem_tercih = "Toplam 1.5 UST / 3.5 ALT"
                barem_guven = 74
        else:
            ref_barem = float(piyasa_barem) if piyasa_barem and float(piyasa_barem) > 0 else (224.0 if "NBA" in lig_adi else 162.0)
            if state == "in" and any(k in detay_sure for k in ("Half", "HT", "IY")):
                projeksiyon = toplam_skor * 2
                if projeksiyon >= ref_barem + 10:
                    barem_tercih = f"Canli UST Firsati (Projeksiyon: {projeksiyon} / Barem: {ref_barem})"
                    barem_guven = 81
                elif projeksiyon <= ref_barem - 12:
                    barem_tercih = f"Canli ALT Firsati (Projeksiyon: {projeksiyon} / Barem: {ref_barem})"
                    barem_guven = 79
                else:
                    barem_tercih = f"Piyasa Dengede (Barem: {ref_barem})"
                    barem_guven = 65
            else:
                barem_tercih = f"Piyasa Baremi: {ref_barem}"
                barem_guven = 70

        deger_puani = round(min(9.8, max(4.2, (guven / 10.0) - (0.6 if tuzak_notu else 0.0))), 1)

        return {
            "ana_tercih": ana_tercih,
            "guven": guven,
            "barem_tercih": barem_tercih,
            "barem_guven": barem_guven,
            "deger_puani": deger_puani,
            "tuzak_notu": tuzak_notu,
            "ev_guc_yuzde": int(ev_net * 100),
            "dep_guc_yuzde": int(dep_net * 100),
        }

    def canli_web_istihbarati(self, ev_ad, dep_ad, spor_turu):
        bulgular = list()
        try:
            from duckduckgo_search import DDGS
            sorgular = [
                f"{ev_ad} {dep_ad} sakat cezali son dakika kadro",
                f"{ev_ad} vs {dep_ad} injury news lineup"
            ]
            with DDGS() as ddgs:
                for q in sorgular:
                    sonuclar = list(ddgs.text(q, max_results=3))
                    for s in sonuclar:
                        baslik = s.get("title", "")
                        ozet = s.get("body", "")
                        if baslik or ozet:
                            bulgular.append(f"- {baslik}: {ozet[:180]}")
        except Exception:
            pass
        return "\n".join(bulgular[:5]) if bulgular else "Canli web aramasinda ek son dakika haberi bulunamadi."

    def ai_karar_ve_onay(self, spor_turu, lig_adi, ev_ad, dep_ad, analiz_ozeti, saha_verisi=""):
        hafiza = self._evrim_hafizasi_oku()
        ogrenilenler = hafiza.get("ogrenilen_kurallar", list())[-5:]
        kural_metni = "\n".join(ogrenilenler) if ogrenilenler else "Henuz ek ozel kural yok."
        web_istihbarat = self.canli_web_istihbarati(ev_ad, dep_ad, spor_turu)

        prompt = (
            f"Sen kendi kendini gelistiren (v{hafiza.get('versiyon', 1)}.0) {spor_turu} Bas Analisti ve Istihbarat Sefisin.\n"
            f"Mac: [{lig_adi}] {ev_ad} vs {dep_ad}\n"
            f"Istatistik & Piyasa Ozeti: {analiz_ozeti}\n"
            f"Canli Saha Verisi: {saha_verisi}\n"
            f"Internetten Toplanan Son Dakika Haber & Sakatlik Istihbarati:\n{web_istihbarat}\n\n"
            f"Gecmis Hatalarindan Ogrenip Kendi Yazdigin Kurallar (BUNLARA KESIN UY):\n{kural_metni}\n\n"
            f"Gorevin: Ezbere konusma; yukaridaki istihbarati, kadro eksiklerini ve istatistikleri carpistirarak "
            f"kullaniciya gercek kanitlarla guven veren TAM OLARAK su 3 kisa maddede Turkce rapor ver:\n"
            f"🎯 ANA KARAR: (En degerli ve en ustun tek bahis secenegi)\n"
            f"🕵️ ISTIHBARAT & KANIT: (Web aramasindan buldugun kadro/sakatlik/form gercegiyle neden bu secenegin ustun oldugu - 1-2 net cumle)\n"
            f"⚠️ KRITIK RISK: (Bu tahmini bozabilecek tek somut tehlike)"
        )
        return self._ai_sor(prompt, max_tokens=450)
