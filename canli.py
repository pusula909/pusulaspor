import io
import json
import os
import time
from datetime import datetime, timedelta, timezone
import pandas as pd
import requests
import streamlit as st
from ortak_beyin import lig_basari_bonusu_getir, sharp_piyasa_durumu_getir

try:
    from google import genai
    GEMINI_AKTIF = True
except Exception:
    GEMINI_AKTIF = False

st.set_page_config(page_title="AI Pro Spor Veri Merkezi", layout="wide")
st.markdown(
    "<style>.stApp{background-color:#F4F6F9!important}section[data-testid='stSidebar']{background-color:#FFFFFF!important;border-right:1px solid #E2E8F0!important}h1,h2,h3,h4,p,span,label,div{color:#0F172A!important}.stButton>button{background-color:#DC2626!important;color:#FFFFFF!important;font-weight:700!important;border-radius:8px!important;border:none!important}.stButton>button *{color:#FFFFFF!important}</style>",
    unsafe_allow_html=True,
)
st.title("AI Pro Spor Veri Merkezi | Gercek Oran & Istatistik Motoru")

gemini_api_key = st.secrets.get("GEMINI_API_KEY", "")
groq_api_key = st.secrets.get("GROQ_KEY", "")
tg_token = st.secrets.get("TELEGRAM_TOKEN", "")
tg_chat = st.secrets.get("TELEGRAM_CHAT_ID", "")

TUM_LIGLER = {
    "Basketbol": {
        "NBA": "basketball/nba",
        "EuroLeague": "euroleague_resmi",
    },
    "Futbol": {
        "Trendyol Super Lig": "soccer/tur.1",
        "Premier Lig": "soccer/eng.1",
        "La Liga": "soccer/esp.1",
        "Serie A": "soccer/ita.1",
        "Bundesliga": "soccer/ger.1",
        "Fransa Ligue 1": "soccer/fra.1",
        "Sampiyonlar Ligi": "soccer/uefa.champions",
    },
}


def amerikan_to_ondalik(ml):
    try:
        v = float(ml)
        if v == 0:
            return None
        return round(1 + (v / 100.0), 2) if v > 0 else round(1 + (100.0 / abs(v)), 2)
    except Exception:
        return None


def gercek_oran_ve_istatistik_cek(yol, mac_id, ev_adi="", dep_adi=""):
    veri = {
        "ev_oran_yuzde": None,
        "dep_oran_yuzde": None,
        "ev_ondalik": None,
        "dep_ondalik": None,
        "piyasa_ev_ihtimal": None,
        "piyasa_dep_ihtimal": None,
        "barem": None,
        "handikap": None,
        "sakat_fark": 0,
        "sakat_metin": "Eksik Yok",
        "h2h_metin": "Kayit Yok",
        "sharp_not": "",
    }
    if not yol or not mac_id:
        return veri

    sharp_puan, sharp_not = sharp_piyasa_durumu_getir(mac_id)
    veri["sharp_not"] = sharp_not

    if yol == "euroleague_resmi":
        return veri

    try:
        url = f"https://espn.com{yol}/summary?event={mac_id}"
        sj = requests.get(url, timeout=6).json()
        comps = sj.get("header", {}).get("competitions", list(({},))).pop(0).get("competitors", list())
        ev_id = ""
        for c in comps:
            rec_str = next((r.get("summary", "") for r in c.get("record", list()) if r.get("type") == "total"), "")
            yuzde = None
            if "-" in rec_str:
                parca = rec_str.split("-")
                g_s, m_s = int(parca.pop(0)), int(parca.pop(0))
                if (g_s + m_s) > 0:
                    yuzde = round((g_s / (g_s + m_s)) * 100, 1)
            if c.get("homeAway") == "home":
                veri["ev_oran_yuzde"] = yuzde
                ev_id = c.get("team", {}).get("id", "")
            else:
                veri["dep_oran_yuzde"] = yuzde

        for pk in sj.get("pickcenter", list())[:1]:
            if pk.get("overUnder") is not None:
                veri["barem"] = float(pk.get("overUnder"))
            if pk.get("spread") is not None:
                veri["handikap"] = float(pk.get("spread"))
            ev_ml = pk.get("homeTeamOdds", {}).get("moneyLine")
            dep_ml = pk.get("awayTeamOdds", {}).get("moneyLine")
            ev_od = amerikan_to_ondalik(ev_ml)
            dep_od = amerikan_to_ondalik(dep_ml)
            veri["ev_ondalik"] = ev_od
            veri["dep_ondalik"] = dep_od
            if ev_od and dep_od and ev_od > 1 and dep_od > 1:
                ham_ev = 1.0 / ev_od
                ham_dep = 1.0 / dep_od
                toplam_marj = ham_ev + ham_dep
                veri["piyasa_ev_ihtimal"] = round((ham_ev / toplam_marj) * 100, 1)
                veri["piyasa_dep_ihtimal"] = round((ham_dep / toplam_marj) * 100, 1)

        sakatlar = list()
        for grp in sj.get("injuries", list()):
            t_isim = grp.get("team", {}).get("displayName", "")
            t_id = grp.get("team", {}).get("id", "")
            eksik_say = 0
            for inj in grp.get("injuries", list()):
                st_d = inj.get("status", "")
                oy_ad = inj.get("athlete", {}).get("displayName", "")
                if st_d in ("Out", "Doubtful"):
                    eksik_say += 1
                    sakatlar.append(f"{t_isim}: {oy_ad} ({st_d})")
            if ev_id and ev_id == t_id:
                veri["sakat_fark"] -= eksik_say * 3.5
            else:
                veri["sakat_fark"] += eksik_say * 3.5
        if sakatlar:
            veri["sakat_metin"] = ", ".join(sakatlar[:5])

        h2h_list = list()
        for h in sj.get("headToHeadGames", list())[:3]:
            if h.get("score"):
                h2h_list.append(f"{h.get('gameDate', '')[:10]} ({h.get('score')})")
        if h2h_list:
            veri["h2h_metin"] = " | ".join(h2h_list)
    except Exception:
        pass
    return veri
def gercek_mac_tahmini_hesapla(ev, dep, spor, lig, veri, state="pre", ev_skor=0, dep_skor=0, dakika=0, ev_sot=0, dep_sot=0):
    lig_bonus = lig_basari_bonusu_getir(lig)
    sharp_bonus = 5.0 if veri.get("sharp_not") else 0.0
    ev_sezon = veri.get("ev_oran_yuzde")
    dep_sezon = veri.get("dep_oran_yuzde")
    p_ev = veri.get("piyasa_ev_ihtimal")
    p_dep = veri.get("piyasa_dep_ihtimal")
    barem = veri.get("barem")
    sakat_etki = veri.get("sakat_fark", 0)

    if state == "in":
        toplam_s = ev_skor + dep_skor
        dk = max(1, int(dakika or 1))
        if spor == "Futbol":
            sut_t = int(ev_sot or 0) + int(dep_sot or 0)
            tempo = (toplam_s * 18 + sut_t * 6) / dk
            kalan_dk = max(1, 90 - dk)
            if dk >= 78 and tempo < 1.15:
                ihtimal = min(86.0, round(60.0 + (dk - 75) * 1.5, 1))
                return f"Canli Toplam {toplam_s + 0.5} ALT", ihtimal, f"Dakika {dk}' ve sut temposu dusuk ({round(tempo, 1)}); mac kilitli."
            ihtimal = max(48.0, min(84.0, round(46.0 + tempo * 13 + (kalan_dk / 5.5), 1)))
            return f"Canli Toplam {toplam_s + 0.5} UST", ihtimal, f"Dakika {dk}' canli sut/gol temposu ({round(tempo, 1)}) aktif."
        else:
            dakika_basi = toplam_s / dk
            tahmini_son = round(dakika_basi * 48, 1)
            if barem:
                yon = "UST" if tahmini_son > barem else "ALT"
                fark = abs(tahmini_son - barem)
                ihtimal = max(51.0, min(85.0, round(52.0 + fark * 1.4, 1)))
                return f"Canli Toplam {barem} {yon}", ihtimal, f"Canli tempo projeksiyonu {tahmini_son} sayi (Barem: {barem})."

    if p_ev is not None and p_dep is not None:
        if ev_sezon is not None and dep_sezon is not None and (ev_sezon + dep_sezon) > 0:
            form_ev = round((ev_sezon / (ev_sezon + dep_sezon)) * 100, 1)
            model_ev = round((p_ev * 0.60) + (form_ev * 0.40) + sakat_etki + (lig_bonus * 0.5) + sharp_bonus, 1)
        else:
            model_ev = round(p_ev + sakat_etki + (lig_bonus * 0.5) + sharp_bonus, 1)
        model_ev = max(12.0, min(89.0, model_ev))
        model_dep = round(100.0 - model_ev, 1)

        if model_ev >= model_dep:
            edge = round(model_ev - p_ev, 1)
            secim = f"{ev} Kazanir (MS 1)" if spor == "Futbol" else f"{ev} Kazanir"
            oran_txt = f" | Oran: {veri['ev_ondalik']}" if veri.get("ev_ondalik") else ""
            gerekce = f"Piyasa Ihtimali: %{p_ev} -> Model Ihtimali: %{model_ev} (Value Fark: {edge:+}%){oran_txt}"
            return secim, model_ev, gerekce
        else:
            edge = round(model_dep - p_dep, 1)
            secim = f"{dep} Kazanir (MS 2)" if spor == "Futbol" else f"{dep} Kazanir"
            oran_txt = f" | Oran: {veri['dep_ondalik']}" if veri.get("dep_ondalik") else ""
            gerekce = f"Piyasa Ihtimali: %{p_dep} -> Model Ihtimali: %{model_dep} (Value Fark: {edge:+}%){oran_txt}"
            return secim, model_dep, gerekce

    if ev_sezon is not None and dep_sezon is not None and (ev_sezon + dep_sezon) > 0:
        oran_ev = round((ev_sezon / (ev_sezon + dep_sezon)) * 100 + sakat_etki + lig_bonus, 1)
        oran_ev = max(18.0, min(85.0, oran_ev))
        if oran_ev >= 50:
            secim = f"{ev} Kazanir (MS 1)" if spor == "Futbol" else f"{ev} Kazanir"
            return secim, oran_ev, f"Gercek Sezon Galibiyet Orani: %{ev_sezon} vs %{dep_sezon} | Sakatlik Etkisi: {sakat_etki:+}%"
        secim = f"{dep} Kazanir (MS 2)" if spor == "Futbol" else f"{dep} Kazanir"
        return secim, round(100 - oran_ev, 1), f"Gercek Sezon Galibiyet Orani: %{dep_sezon} vs %{ev_sezon}"

    if barem is not None:
        return f"Mac Toplami {barem} UST", 54.0, f"Resmi Piyasa Baremi: {barem} (Detayli oran/form verisi bekleniyor)."

    return "Veri Yetersiz (Analiz Bekleniyor)", 0.0, "Bu mac icin resmi oran ve sezon istatistigi henuz acilmamis."


def telegram_gonder(mesaj):
    if not tg_token or not tg_chat:
        return False
    try:
        r = requests.post(
            f"https://telegram.org{tg_token}/sendMessage",
            json={"chat_id": tg_chat, "text": mesaj},
            timeout=8,
        )
        return r.status_code == 200
    except Exception:
        return False


def ai_yorum_uret(prompt):
    if GEMINI_AKTIF and gemini_api_key:
        try:
            cl = genai.Client(api_key=gemini_api_key.strip(), http_options={"api_version": "v1beta"})
            for mod in ("gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"):
                try:
                    res = cl.models.generate_content(model=mod, contents=prompt)
                    if res and res.text:
                        return res.text.strip(), f"Gemini ({mod})"
                except Exception:
                    continue
        except Exception:
            pass
    if groq_api_key:
        try:
            r = requests.post(
                "https://groq.com",
                headers={"Authorization": f"Bearer {groq_api_key.strip()}", "Content-Type": "application/json"},
                json={"model": "openai/gpt-oss-120b", "messages": [{"role": "user", "content": prompt}], "temperature": 0.2, "max_tokens": 900},
                timeout=15,
            ).json()
            if "choices" in r and r["choices"]:
                return r["choices"].pop(0).get("message", {}).get("content", "").strip(), "Groq (openai/gpt-oss-120b)"
        except Exception:
            pass
    return "AI yorum servisi su an yanit vermedi; asagidaki gercek oran ve istatistik tablosu aktif.", "Yerel Motor"


if "kupon_listesi" not in st.session_state:
    st.session_state.kupon_listesi = list()

with st.sidebar:
    st.header("Kontrol Paneli")
    sayfa = st.radio("Bolum Secin", ["Canli Analiz & Kupon", "Yildiz Oyuncu Analizi", "AI Dogruluk Karnesi"])
    tr_simdi = datetime.now(timezone(timedelta(hours=3)))
    secilen_tarih = st.date_input("Mac Tarihi", value=tr_simdi.date())
    tarih_str = secilen_tarih.strftime("%Y%m%d")

if sayfa == "AI Dogruluk Karnesi":
    st.subheader("AI Gecmis Basari & Performans Karnesi")
    if os.path.exists("haftalik_arsiv.json"):
        with open("haftalik_arsiv.json", "r", encoding="utf-8") as f:
            arsiv = json.load(f)
        if arsiv:
            df_a = pd.DataFrame(arsiv)
            toplam_m = len(df_a)
            tutan_m = int(df_a["tuttu"].sum()) if "tuttu" in df_a.columns else 0
            oran_k = round((tutan_m / toplam_m) * 100, 1) if toplam_m else 0
            c1, c2, c3 = st.columns(3)
            c1.metric("Toplam Mac", toplam_m)
            c2.metric("Tutan Tahmin", tutan_m)
            c3.metric("Genel Basari", f"%{oran_k}")
            st.dataframe(df_a, use_container_width=True)
        else:
            st.info("Arsivde henuz tamamlanmis mac kaydi bulunmuyor.")
    else:
        st.info("haftalik_arsiv.json henuz olusmamis; ilk maclar sonuclandikca otomatik dolacaktir.")

elif sayfa == "Yildiz Oyuncu Analizi":
    st.subheader("Yildiz Oyuncu Performans (Player Props) Radari")
    if st.button("Gunun NBA Maclarindan Gercek Kadro & Oyuncu Analizi Uret"):
        with st.spinner("NBA resmi kadro ve sakatlik verileri cekiliyor..."):
            try:
                rb = requests.get(f"https://espn.com{tarih_str}", timeout=8).json()
                ozetler = list()
                for ev_obj in rb.get("events", list())[:6]:
                    m_id = ev_obj.get("id", "")
                    m_ad = ev_obj.get("name", "")
                    v_detay = gercek_oran_ve_istatistik_cek("basketball/nba", m_id)
                    ozetler.append(f"- {m_ad} | Barem: {v_detay['barem']} | Eksikler: {v_detay['sakat_metin']}")
                if ozetler:
                    prompt_oy = "Asagidaki gercek NBA maclari ve sakatlik listelerine gore eksikler nedeniyle dakikası ve top kullanimi artacak 4 yildiz oyuncunun gercekci sayi/ribaund/asist onerisini yaz:\n" + "\n".join(ozetler)
                    yanit_oy, kaynak_oy = ai_yorum_uret(prompt_oy)
                    st.caption(f"Kaynak: {kaynak_oy}")
                    st.write(yanit_oy)
                else:
                    st.warning("Secili tarihte NBA maci bulunamadi.")
            except Exception as e:
                st.error(f"Veri cekme hatasi: {e}")

else:
    st.subheader("Gercek Oran & Istatistik Bazli Akilli Kombine")
    col_k1, col_k2 = st.columns(2)
    kombine_tetik = None
    if col_k1.button("En Yuksek Value Degerli 3'lu Kombine Olustur"):
        kombine_tetik = 3
    if col_k2.button("En Yuksek Value Degerli 4'lu Kombine Olustur"):
        kombine_tetik = 4

    if kombine_tetik:
        with st.spinner("Tum liglerin resmi oranlari, sezon formlari ve sakatliklari taraniyor..."):
            adaylar = list()
            for sp_ad, lig_dict in TUM_LIGLER.items():
                for lg_ad, lg_yol in lig_dict.items():
                    if lg_yol == "euroleague_resmi":
                        continue
                    try:
                        resp = requests.get(f"https://espn.com{lg_yol}/scoreboard?dates={tarih_str}", timeout=6).json()
                        for ev_item in resp.get("events", list()):
                            st_k = ev_item.get("status", {}).get("type", {}).get("state", "pre")
                            if st_k != "pre":
                                continue
                            comp = ev_item.get("competitions", list(({},))).pop(0)
                            taks = comp.get("competitors", list())
                            if len(taks) < 2:
                                continue
                            ev_n = next((t.get("team", {}).get("displayName", "") for t in taks if t.get("homeAway") == "home"), "")
