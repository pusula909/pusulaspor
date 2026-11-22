import os
import json
import requests

try:
    from google import genai
    GEMINI_AKTIF = True
except Exception:
    GEMINI_AKTIF = False


class PusulaAnalizBeyni:
    """
    Web arayuzu, Telegram canli radari ve Gunluk Bulten icin
    tek merkezli, cok katmanli profesyonel spor analiz motoru.
    """

    def __init__(self, gemini_key="", groq_key=""):
        self.gemini_key = (gemini_key or os.environ.get("GEMINI_KEY", "")).strip()
        self.groq_key = (groq_key or os.environ.get("GROQ_KEY", "")).strip()

    def _oran_coz(self, rec_str):
        """'15-5' veya '10-4-6' gibi derece metnini güvenli galibiyet oranina cevirir."""
        try:
            parcalar = [int(x) for x in str(rec_str).split("-") if x.strip().isdigit()]
            toplam = sum(parcalar)
            if len(parcalar) >= 2 and toplam > 0:
                # Sezon basi sapmalarini dengeleyen Laplace yumusatmasi
                return (parcalar + 2) / (toplam + 4)
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
        detay_sure=""
    ):
        """
        Ezber oranlara dusmeden; saha gucu, sakatlik maliyeti, piyasa baremi
        ve canli skoru birlestirip tek bir tutarli karar ve deger puani uretir.
        """
        ev_guc = self._oran_coz(ev_rec)
        dep_guc = self._oran_coz(dep_rec)

        # Ic saha avantaji ve sakatlik etkisi
        ev_avantaj = 0.05 if spor_turu == "Futbol" else 0.04
        ev_net = max(0.08, min(0.92, ev_guc + ev_avantaj - (ev_eksik_puan * 0.025)))
        dep_net = max(0.08, min(0.92, dep_guc - (dep_eksik_puan * 0.025)))

        # Canli mac ise skor ve sure etkisini dahil et
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

        # 1. Ana Taraf Karari ve Tuzak Kontrolu
        tuzak_notu = ""
        if spor_turu == "Futbol":
            if guc_farki >= 0.16:
                ana_tercih = f"{ev_ad} Kazanir (MS 1)"
                guven = min(88, int(56 + abs_fark * 48))
            elif guc_farki <= -0.16:
                ana_tercih = f"{dep_ad} Kazanir (MS 2)"
                guven = min(87, int(55 + abs_fark * 48))
            else:
                ana_tercih = "Cifte Sans 1X / Dengeli Mac"
                guven = min(76, int(62 + (0.16 - abs_fark) * 35))
                tuzak_notu = "Taraf bahsi riskli, iki takim birbirine cok yakin."
        else:
            if guc_farki >= 0.14:
                ana_tercih = f"{ev_ad} Kazanir (MS 1)"
                guven = min(89, int(57 + abs_fark * 50))
            elif guc_farki <= -0.14:
                ana_tercih = f"{dep_ad} Kazanir (MS 2)"
                guven = min(88, int(56 + abs_fark * 50))
            else:
                ana_tercih = "Taraf Riskli -> Toplam Sayi / Handikap Odakli"
                guven = 64
                tuzak_notu = "Kafa kafaya mac; taraf yerine barem degerlendirilmeli."

        # 2. Piyasa Baremi (Alt/Ust) Degerlendirmesi
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

        # 3. 10 Uzerinden Genel Deger Puani (Value Rating)
        deger_puani = round(min(9.8, max(4.5, (guven / 10.0) - (0.6 if tuzak_notu else 0.0))), 1)

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

    def ai_karar_ve_onay(self, spor_turu, lig_adi, ev_ad, dep_ad, analiz_ozeti, saha_verisi=""):
        """
        Yapay zekaya sadece yorum yazdirmaz; hesaplanan matematiksel analizi
        saha ve kadro verisiyle denetletip 'ONAY' veya 'DIKKAT / TUZAK' karari aldirir.
        """
        prompt = (
            f"Sen dunya capinda bir {spor_turu} Bas Analisti ve Risk Yoneticisisin.\n"
            f"Mac: {lig_adi} | {ev_ad} vs {dep_ad}\n"
            f"Matematik Motoru Ciktisi: {analiz_ozeti}\n"
            f"Canli Saha / Kadro / Eksik Verisi: {saha_verisi}\n\n"
            f"Gorevin: Bu tahmini saha gercekleri, rotasyon, sakatlik ve piyasa tuzaklari acisindan denetlemek.\n"
            f"Ciktiyi Turkce olarak TAM OLARAK su 3 kisa maddede ver:\n"
            f"🎯 ANA KARAR: (En mantikli tek secenek ve neden degerli oldugu)\n"
            f"🧠 SAHA & TAKTIK OKUMASI: (Kadro, tempo veya koc hamlesi acisindan 1-2 net cumle)\n"
            f"⚠️ TUZAK / RISK UYARISI: (Bu tahmini bozabilecek tek kritik nokta)"
        )

        if GEMINI_AKTIF and self.gemini_key:
            try:
                client = genai.Client(api_key=self.gemini_key, http_options={"api_version": "v1beta"})
                for m in ("gemini-2.5-flash", "gemini-2.5-flash-lite"):
                    try:
                        yanit = client.models.generate_content(model=m, contents=prompt)
                        if yanit and yanit.text:
                            return yanit.text.strip()
                    except Exception:
                        continue
            except Exception:
                pass

        if self.groq_key:
            g_base = "https://groq.com"
            g_headers = {"Authorization": f"Bearer {self.groq_key}", "Content-Type": "application/json"}
            for m in ("openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"):
                try:
                    r = requests.post(
                        f"{g_base}/chat/completions",
                        headers=g_headers,
                        json={
                            "model": m,
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.3,
                            "max_tokens": 400,
                        },
                        timeout=12,
                    ).json()
                    if "choices" in r and r["choices"]:
                        txt = r["choices"].get("message", {}).get("content", "").strip()
                        if txt:
                            return txt
                except Exception:
                    continue

        return ""
