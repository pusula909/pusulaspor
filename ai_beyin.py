import json
import os
import requests

try:
    from google import genai
    GEMINI_AKTIF = True
except Exception:
    GEMINI_AKTIF = False

ALAN = ".".join(("site", "api", "espn", "com"))
URL_BASI = f"https://{ALAN}/apis/site/v2/sports/"
BASLIKLAR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def canli_baski_ve_istatistik_hesapla(lig_yolu, mac_id, spor_turu, state="pre"):
    """Mac ici istatistikleri (sut %, korner, isabetli sut, top kaybi) ceker ve 0-100 Canli Baski Puani uretir."""
    sonuc = {
        "baski_puani": 0,
        "baski_etiketi": "Mac Baslamadi",
        "istatistik_ozeti": "Henuz mac ici istatistik yok.",
        "son_olaylar": "",
    }
    if state != "in" or not mac_id or lig_yolu == "euroleague_resmi" or "/" not in lig_yolu:
        return sonuc

    try:
        j = requests.get(f"{URL_BASI}{lig_yolu}/summary?event={mac_id}", headers=BASLIKLAR, timeout=5).json()
        takim_notlari = []
        baski_skoru = 50

        for t_stat in j.get("boxscore", {}).get("teams", [])[:2]:
            t_ad = t_stat.get("team", {}).get("displayName", "")
            stat_map = {}
            for s in t_stat.get("statistics", []):
                ad = s.get("label", s.get("name", "")).lower()
                val = s.get("displayValue", "")
                stat_map[ad] = val

            if spor_turu == "Futbol":
                sot = stat_map.get("shots on target", stat_map.get("shotsontarget", "0"))
                cor = stat_map.get("corners", stat_map.get("cornerkicks", "0"))
                pos = stat_map.get("possession", stat_map.get("possessionpct", "50"))
                takim_notlari.append(f"{t_ad}: Isabetli Sut {sot}, Korner {cor}, Topla Oynama {pos}")
                try:
                    baski_skoru += int(float(str(sot).replace("%", ""))) * 3 + int(float(str(cor).replace("%", ""))) * 2
                except Exception:
                    pass
            else:
                fg = stat_map.get("fg%", stat_map.get("fieldgoalpct", "-"))
                tp = stat_map.get("3p%", stat_map.get("threepointfieldgoalpct", "-"))
                reb = stat_map.get("rebounds", stat_map.get("totalrebounds", "-"))
                to = stat_map.get("turnovers", "-")
                takim_notlari.append(f"{t_ad}: Sut {fg}, 3P {tp}, Ribaund {reb}, Top Kaybi {to}")
                try:
                    fg_num = float(str(fg).replace("%", ""))
                    if fg_num >= 52:
                        baski_skoru += 12
                except Exception:
                    pass

        olaylar = []
        for item in j.get("keyEvents", [])[-4:]:
            dk = item.get("clock", {}).get("displayValue", "")
            txt = item.get("text", "")
            if txt:
                olaylar.append(f"[{dk}] {txt}")

        baski_skoru = max(15, min(98, baski_skoru))
        if baski_skoru >= 80:
            etiket = f"🔥 COK YUKSEK BASKI / TEMPO ({baski_skoru}/100)"
        elif baski_skoru >= 62:
            etiket = f"⚡ AKTIF HUCUM IVMESI ({baski_skoru}/100)"
        else:
            etiket = f"🛡️ KONTROLLU / DUSUK TEMPO ({baski_skoru}/100)"

        sonuc["baski_puani"] = baski_skoru
        sonuc["baski_etiketi"] = etiket
        if takim_notlari:
            sonuc["istatistik_ozeti"] = " | ".join(takim_notlari)
        if olaylar:
            sonuc["son_olaylar"] = " | ".join(olaylar)
    except Exception:
        pass
    return sonuc


def yapilandirilmis_ai_karari_uret(gemini_key, groq_key, analiz_paketi):
    """Gemini veya Groq'tan daginik paragraf yerine doğrudan OYNA/PAS GEC ve guven skoru dondurur."""
    g_key = (gemini_key or os.environ.get("GEMINI_KEY", "")).strip()
    q_key = (groq_key or os.environ.get("GROQ_KEY", "")).strip()

    prompt = (
        "Sen dunya capinda bir Nicel Spor Analisti ve Basantrenor Danismanisin. "
        "Asagidaki matematiksel olasiliklari, gercek piyasa baremini, sakatliklari ve canli saha istatistiklerini analiz et.\n"
        f"VERILER:\n{json.dumps(analiz_paketi, ensure_ascii=False)}\n\n"
        "SIKI KURALLAR:\n"
        "1) Eski sezon kadrolarini ASLA yazma, sadece verilen verileri kullan.\n"
        "2) Eger model tahmini ile piyasa baremi celisiyorsa veya kritik yildiz eksikligi belirsizlik yaratiyorsa 'PAS GEC' de.\n"
        "3) Cevabi SADECE gecerli bir JSON formatinda ver, baska hicbir aciklama yazma:\n"
        '{"durum": "OYNA veya CANLI BEKLE veya PAS GEC", "secim": "Tek net bahis secimi ve barem", "guven": 82, "sebep": "En fazla 2 cumlelik net taktik ve matematiksel gerekce", "risk": "Tek cumlelik en buyuk risk"}'
    )

    ham_yanit = ""
    if g_key:
        for m in ("gemini-2.5-flash", "gemini-2.5-flash-lite"):
            try:
                g_url = f"https://googleapis.com{m}:generateContent?key={g_key}"
                res = requests.post(g_url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=12).json()
                cands = res.get("candidates", [])
                if cands:
                    parts = cands.pop(0).get("content", {}).get("parts", [])
                    if parts:
                        ham_yanit = parts.pop(0).get("text", "").strip()
                        if ham_yanit:
                            break
            except Exception:
                continue
   if not ham_yanit and q_key:
        try:
            g_resp = requests.post(
                "https://groq.com",
                headers={"Authorization": f"Bearer {q_key}", "Content-Type": "application/json"},
                json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "temperature": 0.25, "max_tokens": 350},
                timeout=12,
            ).json()
            if "choices" in g_resp and g_resp["choices"]:
                ham_yanit = g_resp["choices"].pop(0).get("message", {}).get("content", "").strip()
        except Exception:
            pass

    try:
        bas = ham_yanit.find("{")
        son = ham_yanit.rfind("}")
        if bas != -1 and son != -1:
            veri = json.loads(ham_yanit[bas : son + 1])
            return {
                "durum": str(veri.get("durum", "CANLI BEKLE")).upper(),
                "secim": str(veri.get("secim", "Piyasa Takibi")),
                "guven": int(veri.get("guven", 65)),
                "sebep": str(veri.get("sebep", "")),
                "risk": str(veri.get("risk", "")),
            }
    except Exception:
        pass

    return {
        "durum": "CANLI BEKLE",
        "secim": "Veri Analizi",
        "guven": 60,
        "sebep": ham_yanit if ham_yanit else "AI baglantisi icin API anahtari bekleniyor.",
        "risk": "Mac ici kadro ve tempo degisimi.",
    }
