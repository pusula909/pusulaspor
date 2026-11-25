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
            for m in ("gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-2.5-flash"):
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
            for m in ("openai/gpt-oss-120b", "openai/gpt-oss-20b"):
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
            if state == "in" and toplam_skor > 0:
                top_dk = 48.0 if "NBA" in lig_adi else 40.0
                per_dk = 12.0 if "NBA" in lig_adi else 10.0
                s_alt = str(detay_sure).lower()
                oynanan_dk = top_dk * 0.5
                try:
                    kalan_p_dk = 0.0
                    if ":" in s_alt:
                        parca = s_alt.split("-")[0].strip() if "-" in s_alt else s_alt.split(" ")[0].strip()
                        if ":" in parca:
                            dak, san = parca.split(":")[:2]
                            kalan_p_dk = float(dak) + (float(san) / 60.0)
                    if any(k in s_alt for k in ("half", "ht", "iy")):
                        oynanan_dk = per_dk * 2
                    elif any(k in s_alt for k in ("end of 1st", "1. ceyrek sonu")):
                        oynanan_dk = per_dk
                    elif any(k in s_alt for k in ("end of 3rd", "3. ceyrek sonu")):
                        oynanan_dk = per_dk * 3
                    elif any(k in s_alt for k in ("1st", "1p", "q1")):
                        oynanan_dk = max(2.0, per_dk - kalan_p_dk)
                    elif any(k in s_alt for k in ("2nd", "2p", "q2")):
                        oynanan_dk = (per_dk * 2) - kalan_p_dk
                    elif any(k in s_alt for k in ("3rd", "3p", "q3")):
                        oynanan_dk = (per_dk * 3) - kalan_p_dk
                    elif any(k in s_alt for k in ("4th", "4p", "q4", "ot")):
                        oynanan_dk = max(per_dk * 3.1, (per_dk * 4) - kalan_p_dk)
                except Exception:
                    oynanan_dk = top_dk * 0.5

                projeksiyon = round((toplam_skor / max(4.0, oynanan_dk)) * top_dk, 1)
                canli_hat = round(projeksiyon) - 0.5
                if projeksiyon >= ref_barem + 8:
                    barem_tercih = f"Canli {canli_hat} UST (Tempo Projeksiyonu: {projeksiyon})"
                    barem_guven = min(86, int(72 + (projeksiyon - ref_barem) * 0.6))
                elif projeksiyon <= ref_barem - 8:
                    barem_tercih = f"Canli {canli_hat} ALT (Tempo Projeksiyonu: {projeksiyon})"
                    barem_guven = min(85, int(72 + (ref_barem - projeksiyon) * 0.6))
                else:
                    yon_txt = "UST" if projeksiyon >= canli_hat else "ALT"
                    barem_tercih = f"Canli {canli_hat} {yon_txt} (Projeksiyon: {projeksiyon})"
                    barem_guven = 68
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

    def _karne_oz_ogrenme_ozeti(self, lig_adi):
    web_istihbarat = self._canli_web_istihbarati(ev_ad, dep_ad)
        try:
            if not os.path.exists("haftalik_arsiv.json"):
                return "Henuz yeterli gecmis karne verisi yok."
            with open("haftalik_arsiv.json", "r", encoding="utf-8") as f:
                arsiv = json.load(f)
            if not arsiv:
                return "Henuz yeterli gecmis karne verisi yok."
            genel_top = len(arsiv)
            genel_hit = sum(1 for k in arsiv if k.get("tuttu"))
            lig_maclar = [k for k in arsiv if k.get("lig", "").lower() == str(lig_adi).lower()]
            yatan_ornekler = [
                f"{k.get('mac')} ({k.get('tahmin')} -> Skor {k.get('skor')})"
                for k in arsiv[-25:] if not k.get("tuttu")
            ][-3:]
            ozet = f"Genel AI Karnesi: {genel_top} macta {genel_hit} isabet (%{int((genel_hit/genel_top)*100)}). "
            if lig_maclar:
                l_hit = sum(1 for k in lig_maclar if k.get("tuttu"))
                ozet += f"{lig_adi} ligi ozelinde {len(lig_maclar)} macta {l_hit} isabet (%{int((l_hit/len(lig_maclar))*100)}). "
            if yatan_ornekler:
                ozet += f"Son yatan tuzak ornekleri: {', '.join(yatan_ornekler)}."
            return ozet
        except Exception:
            return "Karne verisi okunamadi."
        return "Karne verisi okunamadi."

    def canli_web_istihbarati(self, ev_ad, dep_ad, spor_turu):
        bulgular = list()
        try:
            from duckduckgo_search import DDGS
            if spor_turu == "Basketbol":
                sorgular = [
                    f"{ev_ad} {dep_ad} starting lineup injury report ruled out",
                    f"{ev_ad} vs {dep_ad} ilk 5 sakatlik son dakika kadro",
                    f"{ev_ad} {dep_ad} back to back fatigue pace report",
                ]
            else:
                sorgular = [
                    f"{ev_ad} {dep_ad} resmi ilk 11 yedek sakat cezali kadro",
                    f"{ev_ad} vs {dep_ad} confirmed starting XI bench injury lineup",
                    f"{ev_ad} {dep_ad} maci hakemi hava durumu fikstur yogunlugu",
                ]
            with DDGS() as ddgs:
                for q in sorgular:
                    sonuclar = list(ddgs.text(q, max_results=2))
                    for s in sonuclar:
                        baslik = s.get("title", "")
                        ozet = s.get("body", "")
                        if baslik or ozet:
                            bulgular.append(f"- {baslik}: {ozet[:175]}")
        except Exception:
            pass
            return "\n".join(bulgular[:7]) if bulgular else "Canli web aramasinda ek son dakika kadro/ilk 11 haberi bulunamadi."

    def ai_karar_ve_onay(self, spor_turu, lig_adi, ev_ad, dep_ad, analiz_ozeti, saha_verisi="", yol="", event_id=""):
        hakem_bilgi = ""
        try:
            import hakem_analiz as _hk_ana
            hakem_bilgi = _hk_ana.mac_hakem_verisi_cek("https://espn.com", yol, event_id, {"User-Agent": "Mozilla/5.0"})
        except Exception:
            pass
       
        hafiza = self._evrim_hafizasi_oku()
        ogrenilenler = hafiza.get("ogrenilen_kurallar", list())[-5:]
        kural_metni = "\n".join(ogrenilenler) if ogrenilenler else "Henuz ek ozel kural yok."
        karne_dersi = self._karne_oz_ogrenme_ozeti(lig_adi)
       

        oran_metni = "Bu mac icin canli piyasa orani cekilemedi."
        try:
            from oran_motoru import mac_oran_bul
            o_veri = mac_oran_bul(lig_adi, ev_ad, dep_ad)
            if o_veri:
                msx_yazi = f" | MS X: {o_veri['msx']}" if o_veri.get("msx", 0) > 0 else ""
                barem_yazi = f" | Acilan Barem: {o_veri['barem']} (Ust: {o_veri['ust']} / Alt: {o_veri['alt']})" if o_veri.get("barem", 0) > 0 else ""
                hdp_yazi = f" | Handikap: {o_veri['handikap']}" if o_veri.get("handikap", 0) != 0 else ""
                oran_metni = f"GERCEK BAHIS SIRKETI ORANLARI -> MS 1: {o_veri['ms1']}{msx_yazi} | MS 2: {o_veri['ms2']}{barem_yazi}{hdp_yazi}"
        except Exception:
            pass

        prompt = (
            f"Sen v{hafiza.get('versiyon', 1)}.0 {spor_turu} Bas Analistisin.\n"
            f"Mac: [{lig_adi}] {ev_ad} vs {dep_ad}\n"
            f"{oran_metni}\n"
            f"Mac Durumu & Ozet: {analiz_ozeti}\n"
            f"Saha & Skor Verisi: {saha_verisi}\n"
            f"Karne Dersi: {karne_dersi}\n"
            f"Resmi Hakem & Istihbarat Verisi:\n{hakem_bilgi}\n{web_istihbarat}\n"
            f"HAKEM KURALI: Yukarida resmi hakem ismi varsa o hakemin duduk sikligi, faul/serbest atis veya kart/tempo karakterini mutlaka analiz et; hakem ismi yoksa ASLA hakem ismi uydurma.\n"
            f"Kurallar:\n{kural_metni}\n"
            "Piyasa verilerinin hem mac oncesi hem canli olarak gosterdigi yukaridaki GERCEK SECENEKLERI VE DEGERLERI (MS 1/X/2, acilan barem, ust/alt ve handikap) "
            "macin mevcut skoru, dakikasi, resmi ilk 11/ilk 5, sakatlik ve karne dersleriyle tek tek suzerek "
            "gerceklesme ihtimali en yuksek ve en mantikli TEK ISTATISTIKSEL TERCIHI belirle. TAM OLARAK su 3 kisa maddede Turkce rapor ver:\n"
            "• ANA KARAR: (Secenekler icinden suzulen en guclu tek istatistiksel sonuc tercihi ve piyasa degeri)\n"
            "🕵️ İSTİHBARAT & ORAN SÜZME ANALİZİ: (Acilan oranlar/baremler neden bu secenege elendi + ilk 11/sakatlik/skor kaniti - 1-2 cumle)\n"
            "⚠️ KRİTİK RİSK: (En somut tehlike)"
        )
        return self._ai_sor(prompt, max_tokens=450)
