import io
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
import pandas as pd
import requests
import streamlit as st

try:
    import winsound
    SES_AKTIF = True
except Exception:
    SES_AKTIF = False

try:
    from google import genai
    GEMINI_AKTIF = True
except Exception:
    GEMINI_AKTIF = False

st.set_page_config(page_title="AI Pro Spor Veri Merkezi", layout="wide")
st.markdown(
    '<style>.stApp{background-color:#F4F6F9!important}section[data-testid="stSidebar"]{background-color:#FFFFFF!important;border-right:2px solid #E2E8F0!important}h1{color:#0F172A!important;border-bottom:4px solid #DC2626;padding-bottom:8px;font-weight:900!important}h2,h3{color:#1E293B!important;background:#FFFFFF;border-left:5px solid #2563EB;padding:8px 14px;border-radius:6px;box-shadow:0 2px 6px rgba(0,0,0,0.05)}div[data-testid="stMetric"]{background:#FFFFFF!important;border:1px solid #E2E8F0!important;border-top:4px solid #16A34A!important;border-radius:12px!important;padding:15px!important;box-shadow:0 4px 12px rgba(0,0,0,0.06)!important}div[data-testid="stAlert"]{background:#EFF6FF!important;border:1px solid #BFDBFE!important;border-left:5px solid #2563EB!important;border-radius:10px!important}.stDownloadButton>button,.stButton>button{background:#DC2626!important;color:#FFFFFF!important;border-radius:8px!important;font-weight:700!important}</style>',
    unsafe_allow_html=True,
)
st.title("AI Pro Spor Veri Merkezi | Canli Analiz, Radar & Taktik Yorum")


@st.cache_data(ttl=30, show_spinner=False)
def _el_get(t):
    ev = list()
    try:
        h = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/xml, text/xml",
        }
        yil = int(t[:4])
        ay = int(t[4:6])
        sezon_kodu = f"E{yil if ay >= 8 else yil - 1}"
        el_host = "https://api-live." + "euroleague.net/v1/"

        win_map, loss_map, results_map = {}, {}, {}
        try:
            r_res = requests.get(
                f"{el_host}results?seasonCode={sezon_kodu}",
                headers=h,
                timeout=8,
            )
            for g in ET.fromstring(r_res.content).findall(".//game"):
                gc = g.findtext("gamecode", "").strip().replace(f"{sezon_kodu}_", "")
                t1 = g.findtext("hometeam", "").strip()
                t2 = g.findtext("awayteam", "").strip()
                hs = int(g.findtext("homescore", "0") or 0)
                ds = int(g.findtext("awayscore", "0") or 0)
                played = g.findtext("played", "false").lower() == "true"

                if gc:
                    results_map[gc] = {"hs": str(hs), "ds": str(ds), "played": played}

                if played and (hs > 0 or ds > 0):
                    if hs > ds:
                        win_map[t1] = win_map.get(t1, 0) + 1
                        loss_map[t2] = loss_map.get(t2, 0) + 1
                    else:
                        win_map[t2] = win_map.get(t2, 0) + 1
                        loss_map[t1] = loss_map.get(t1, 0) + 1
        except Exception:
            pass

        r_sch = requests.get(
            f"{el_host}schedules?seasonCode={sezon_kodu}",
            headers=h,
            timeout=8,
        )
        items = ET.fromstring(r_sch.content).findall(".//item")
        suan_tr = datetime.now(timezone(timedelta(hours=3))).replace(tzinfo=None)

        for i in items:
            d_raw = i.findtext("date", "").strip()
            if not d_raw:
                continue

            d_obj = datetime.strptime(d_raw, "%b %d, %Y")
            if d_obj.strftime("%Y%m%d") == t:
                h_ad = i.findtext("hometeam", "").strip()
                a_ad = i.findtext("awayteam", "").strip()
                s_time = i.findtext("startime", "20:00").strip()
                gc = i.findtext("gamecode", "").strip().replace(f"{sezon_kodu}_", "")

                hs, ds = "0", "0"
                st_code = "pre"
                detay = s_time
                ceyrekler_ev = list()
                ceyrekler_dep = list()

                if gc in results_map:
                    hs = results_map[gc]["hs"]
                    ds = results_map[gc]["ds"]
                    if results_map[gc]["played"]:
                        st_code = "post"
                        detay = "Tamamlandi"
                    elif int(hs) > 0 or int(ds) > 0:
                        st_code = "in"
                        detay = "Canli"

                if st_code == "pre":
                    try:
                        m_saat = datetime.strptime(f"{d_raw} {s_time}", "%b %d, %Y %H:%M") + timedelta(hours=2)
                        if m_saat <= suan_tr <= m_saat + timedelta(hours=3):
                            st_code = "in"
                            detay = "Canli Oynaniyor"
                    except Exception:
                        pass

                if st_code in ("in", "post") and gc:
                    try:
                        gr = requests.get(
                            f"{el_host}games?seasonCode={sezon_kodu}&gameCode={gc}",
                            headers=h,
                            timeout=5,
                        )
                        g_xml = ET.fromstring(gr.content)

                        sa1 = g_xml.findtext(".//TotalPointsA", g_xml.findtext(".//ScoreA", "")).strip()
                        sb1 = g_xml.findtext(".//TotalPointsB", g_xml.findtext(".//ScoreB", "")).strip()
                        if sa1 and sb1:
                            hs, ds = sa1, sb1

                        for q in range(1, 5):
                            qa = g_xml.findtext(f".//Quarter{q}A", "").strip()
                            qb = g_xml.findtext(f".//Quarter{q}B", "").strip()
                            if qa and qb:
                                ceyrekler_ev.append({"value": qa, "displayValue": qa})
                                ceyrekler_dep.append({"value": qb, "displayValue": qb})

                        if st_code == "in":
                            aktif_q = len(ceyrekler_ev) if ceyrekler_ev else 1
                            detay = f"Canli (Q{aktif_q})"
                    except Exception:
                        pass

                ev_r = f"{win_map.get(h_ad, 0)}-{loss_map.get(h_ad, 0)}"
                dep_r = f"{win_map.get(a_ad, 0)}-{loss_map.get(a_ad, 0)}"

                ev.append(
                    {
                        "id": gc,
                        "status": {"type": {"state": st_code, "shortDetail": detay}},
                        "competitions": list(
                            (
                                {
                                    "status": {"type": {"state": st_code, "shortDetail": detay}},
                                    "competitors": list(
                                        (
                                            {
                                                "homeAway": "home",
                                                "team": {"id": "1", "displayName": h_ad},
                                                "score": hs,
                                                "records": list(({"summary": ev_r},)),
                                                "linescores": ceyrekler_ev,
                                            },
                                            {
                                                "homeAway": "away",
                                                "team": {"id": "2", "displayName": a_ad},
                                                "score": ds,
                                                "records": list(({"summary": dep_r},)),
                                                "linescores": ceyrekler_dep,
                                            },
                                        )
                                    ),
                                },
                            )
                        ),
                    }
                )
    except Exception:
        pass
    return {"events": ev}

if "eski_skorlar" not in st.session_state:
    st.session_state.eski_skorlar = {}
if "radar_sonuclari" not in st.session_state:
    st.session_state.radar_sonuclari = list()
if "kupon_listesi" not in st.session_state:
    st.session_state.kupon_listesi = list()
if "kupon_bildirim_gonderildi" not in st.session_state:
    st.session_state.kupon_bildirim_gonderildi = False
if "gonderilen_kritik_uyarilar" not in st.session_state:
    st.session_state.gonderilen_kritik_uyarilar = list()

alan = ".".join(["site", "api", "espn", "com"])
url_basi = "https://" + alan + "/apis/site/v2/sports/"
puan_basi = "https://" + alan + "/apis/v2/sports/"
basliklar = {"User-Agent": "Mozilla/5.0"}

TUM_LIGLER = {
    "Futbol": {
        "Turkiye Super Lig": "soccer/tur.1",
        "Sampiyonlar Ligi": "soccer/uefa.champions",
        "Avrupa Ligi": "soccer/uefa.europa",
        "Ingiltere Premier League": "soccer/eng.1",
        "Ispanya La Liga": "soccer/esp.1",
        "Italya Serie A": "soccer/ita.1",
        "Almanya Bundesliga": "soccer/ger.1",
        "Fransa Ligue 1": "soccer/fra.1",
        "Hollanda Eredivisie": "soccer/ned.1",
        "Portekiz Liga": "soccer/por.1",
    },
    "Basketbol": {
        "NBA": "basketball/nba",
        "EuroLeague": "euroleague_resmi",
        "NCAA Basketbol": "basketball/mens-college-basketball",
    },
}

gizli_tg_token = st.secrets.get("TG_TOKEN", "")
gizli_tg_chat_id = st.secrets.get("TG_CHAT_ID", "")
gizli_gemini_key = st.secrets.get("GEMINI_KEY", "")

gemini_api_key = st.sidebar.text_input(
    "Gemini API Anahtari (Opsiyonel)",
    value=gizli_gemini_key,
    type="password",
    help="Google AI Studio'dan aldiginiz ucretsiz API anahtarini girerseniz maclara ozel gercek yapay zeka yorumu uretilir.",
)

st.sidebar.header("Kontrol Merkezi")
gorunum = st.sidebar.radio(
    "Mod Secimi",
    ["Maclar ve Canli AI Analiz", "Canli Kupon Takip", "AI Gunun Radari (Tum Ligler)", "Puan Durumu"],
)
tarih_obj = st.sidebar.date_input("Tarih", datetime.now())
tarih = tarih_obj.strftime("%Y%m%d")

st.sidebar.divider()
st.sidebar.subheader("Telegram Bildirim Ayari")
tg_token = st.sidebar.text_input("Telegram Bot Token", value=gizli_tg_token, type="password")
tg_chat_id = st.sidebar.text_input("Telegram Chat ID", value=gizli_tg_chat_id)


def telegram_mesaj_gonder(token, chat_id, mesaj):
    if not token or not chat_id:
        return False
    try:
        tg_adres = "https://" + "api." + "telegram.org" + "/bot" + token.strip() + "/sendMessage"
        r = requests.post(tg_adres, data={"chat_id": str(chat_id).strip(), "text": mesaj}, timeout=8)
        return r.status_code == 200
    except Exception:
        return False

if st.sidebar.button("Telegram Test Mesaji Gonder"):
    if telegram_mesaj_gonder(tg_token, tg_chat_id, "Pusulasporbot baglantisi basarili! Kupon bildirimleri aktif."):
        st.sidebar.success("Test mesaji telefonuna gonderildi!")
    else:
        st.sidebar.error("Gonderilemedi. Bota Telegram'dan BASLAT dediginden emin ol.")

st.sidebar.divider()
st.sidebar.subheader("Gercek Yapay Zeka (Gemini)")
st.sidebar.divider()
spor = st.sidebar.selectbox("Spor Dali", ["Basketbol", "Futbol"])
lig = st.sidebar.selectbox("Lig Secimi", list(TUM_LIGLER[spor].keys()))
durum_filtre = st.sidebar.radio("Mac Durumu", ["Tumu", "Sadece Canli Maclar", "Oynanacak Maclar", "Biten Maclar"])
favori = st.sidebar.text_input("Favori Takim", "").strip().lower()
otomatik_yenile = st.sidebar.checkbox("Canli Otomatik Yenileme & Alarm (30 sn)", value=False)

yol = TUM_LIGLER[spor][lig]
def canli_firsat_etiketi_uret(spor_turu, state, detay_sure, ev_s, dep_s, ev_rec, dep_rec):
    if state != "in":
        return "-"
    try:
        ev_p = list(int(x) for x in ev_rec.split("-"))
        dep_p = list(int(x) for x in dep_rec.split("-"))
        ev_g = ev_p.pop(0) / (sum(ev_p) if sum(ev_p) > 0 else 1)
        dep_g = dep_p.pop(0) / (sum(dep_p) if sum(dep_p) > 0 else 1)
        top_s = ev_s + dep_s

        if spor_turu == "Basketbol":
            if ("Q2" in detay_sure or "Half" in detay_sure or "2C" in detay_sure) and top_s >= 92:
                return "🔥 YUKSEK TEMPO (UST FIRSATI)"
            if ev_g >= 0.65 and (dep_s - ev_s) >= 6:
                return "🔥 FAVORI GERIDE (MS 1 FIRSATI)"
            if dep_g >= 0.65 and (ev_s - dep_s) >= 6:
                return "🔥 FAVORI GERIDE (MS 2 FIRSATI)"
        else:
            if ("45" in detay_sure or "Half" in detay_sure or "HT" in detay_sure) and top_s >= 2:
                return "🔥 GOLLU TEMPO (2.5/3.5 UST)"
            if ("45" in detay_sure or "HT" in detay_sure) and top_s == 0 and (ev_g >= 0.60 or dep_g >= 0.60):
                return "🔥 IY 0-0 (2. YARI GOL FIRSATI)"
    except Exception:
        pass
    return "Normal Akis"
def periyot_ve_iy_cikar(ev_t, dep_t, spor_turu, state):
    if state == "pre":
        return "-"
    ev_ls = list(ev_t.get("linescores", list()))
    dep_ls = list(dep_t.get("linescores", list()))
    if not ev_ls or not dep_ls:
        return "Veri Bekleniyor"
    parcalar = list()
    if spor_turu == "Futbol":
        ev_iy = int(float(ev_ls.pop(0).get("value", 0)))
        dep_iy = int(float(dep_ls.pop(0).get("value", 0)))
        return f"IY: {ev_iy}-{dep_iy}"
    else:
        for sayac, (e_item, d_item) in enumerate(zip(ev_ls, dep_ls), start=1):
            e_v = int(float(e_item.get("value", 0)))
            d_v = int(float(d_item.get("value", 0)))
            isim = f"{sayac}C" if sayac <= 4 else f"UZ{sayac - 4}"
            parcalar.append(f"{isim}: {e_v}-{d_v}")
        return " | ".join(parcalar) if parcalar else "-"


@st.cache_data(ttl=180)
def h2h_ve_form_getir(lig_yolu, mac_id, ev_ad, dep_ad):
    h2h_listesi = list()
    if lig_yolu == "euroleague_resmi":
        return h2h_listesi
    try:
        s_veri = requests.get(f"{url_basi}{lig_yolu}/summary?event={mac_id}", headers=basliklar, timeout=6).json()
        for oyun in s_veri.get("headToHeadGames", list()):
            skor_b = oyun.get("score", "")
            tarih_b = oyun.get("gameDate", "")[:10]
            if skor_b:
                h2h_listesi.append(f"{tarih_b}: {ev_ad} vs {dep_ad} ({skor_b})")
    except Exception:
        pass
    return h2h_listesi[:5]


@st.cache_data(ttl=15)
def koc_ve_rotasyon_etkisi_getir(lig_yolu, mac_id, ev_id, dep_id, spor_turu, ev_ad, dep_ad):
    ozetler = list()
    etki_puani = 0.0
    kritik_alarm = ""
    if lig_yolu == "euroleague_resmi":
        return "EuroLeague Canli Veri Akisi Aktif", 0.0, ""
    try:
        s_veri = requests.get(f"{url_basi}{lig_yolu}/summary?event={mac_id}", headers=basliklar, timeout=6).json()
        if spor_turu == "Basketbol":
            plays = s_veri.get("plays", list())
            if plays:
                son_olaylar = plays[-25:]
                ev_son_sayi = 0
                dep_son_sayi = 0
                son_hamle = ""
                for p in son_olaylar:
                    tip = p.get("type", {}).get("text", "")
                    metin = p.get("text", "")
                    skor_degeri = p.get("scoreValue", 0)
                    takim_id = str(p.get("team", {}).get("id", ""))
                    if "Timeout" in tip or "timeout" in metin.lower():
                        son_hamle = f"Mola ({metin})"
                        ev_son_sayi, dep_son_sayi = 0, 0
                    elif "Substitution" in tip or "enters the game" in metin.lower():
                        son_hamle = f"Oyuncu Degisikligi ({metin})"
                        ev_son_sayi, dep_son_sayi = 0, 0
                    if skor_degeri > 0:
                        if takim_id == str(ev_id):
                            ev_son_sayi += skor_degeri
                        elif takim_id == str(dep_id):
                            dep_son_sayi += skor_degeri
                seri_farki = ev_son_sayi - dep_son_sayi
                if son_hamle:
                    ozetler.append(f"Son Hamle: {son_hamle}")
                if abs(seri_farki) >= 6:
                    onde_olan = ev_ad if seri_farki > 0 else dep_ad
                    ozetler.append(f"Hamle Sonrasi Seri: {onde_olan} ({ev_son_sayi}-{dep_son_sayi})")
                    etki_puani = max(-0.08, min(0.08, seri_farki * 0.01))
                    kritik_alarm = f"BASKETBOL KRITIK SERI: {ev_ad} vs {dep_ad} macinda {son_hamle} sonrasi {onde_olan} {ev_son_sayi}-{dep_son_sayi} seri yakaladi!"
        elif spor_turu == "Futbol":
            olaylar = s_veri.get("keyEvents", list())
            if olaylar:
                son_olay = olaylar.pop()
                tip = son_olay.get("type", {}).get("text", "")
                dk = son_olay.get("clock", {}).get("displayValue", "")
                metin = son_olay.get("text", "")
                ozetler.append(f"Son Olay ({dk}): {tip} - {metin}")
                if any(k in tip for k in ("Goal", "Penalty", "Red Card", "Substitution")):
                    kritik_alarm = f"FUTBOL KRITIK AN ({dk}): {ev_ad} vs {dep_ad} -> {tip}: {metin}"
    except Exception:
        pass
    durum_metni = " | ".join(ozetler) if ozetler else "Kritik bir hamle veya seri yok"
    return durum_metni, etki_puani, kritik_alarm


def coklu_tahmin_motoru(ev_ad, dep_ad, ev_rec, dep_rec, spor_turu, lig_adi, ev_eksik=0, dep_eksik=0, state="pre", ev_skor=0, dep_skor=0):
    try:
        ev_p = list(int(x) for x in ev_rec.split("-"))
        dep_p = list(int(x) for x in dep_rec.split("-"))
        ev_top = sum(ev_p) if sum(ev_p) > 0 else 1
        dep_top = sum(dep_p) if sum(dep_p) > 0 else 1
        ev_g = max(0.08, min(0.92, (ev_p.pop(0) / ev_top) + 0.06 - (ev_eksik * 0.03)))
        dep_g = max(0.08, min(0.92, (dep_p.pop(0) / dep_top) - (dep_eksik * 0.03)))

        if state == "in":
            skor_farki = ev_skor - dep_skor
            if spor_turu == "Futbol":
                ev_g = max(0.05, min(0.95, ev_g + (skor_farki * 0.18)))
                dep_g = max(0.05, min(0.95, dep_g - (skor_farki * 0.18)))
            else:
                ev_g = max(0.05, min(0.95, ev_g + (skor_farki * 0.025)))
                dep_g = max(0.05, min(0.95, dep_g - (skor_farki * 0.025)))

        fark = abs(ev_g - dep_g)
        satirlar = list()
        etiket = "CANLI AI" if state == "in" else "Mac Onu AI"

        if spor_turu == "Futbol":
            if ev_g > dep_g + 0.14:
                ms_secenek = f"{ev_ad} Kazanir (MS 1)"
                ms_guven = min(89, int(56 + fark * 45))
            elif dep_g > ev_g + 0.14:
                ms_secenek = f"{dep_ad} Kazanir (MS 2)"
                ms_guven = min(88, int(55 + fark * 45))
            else:
                ms_secenek = "Beraberlik / Cifte Sans 1X (MS 0)"
                ms_guven = min(75, int(64 - fark * 20))
            satirlar.append({"Analiz Tipi": etiket, "Bahis Kategorisi": "Mac Sonucu (MS)", "AI Tahmin Secenegi": ms_secenek, "Guven Seviyesi": f"%{ms_guven}", "GuvenInt": ms_guven})

            toplam_gol = ev_skor + dep_skor
            if state == "in":
                hedef_barem = toplam_gol + 0.5
                au_secenek = f"Canli Toplam {hedef_barem} UST"
                au_guven = min(82, int(62 + (ev_g + dep_g) * 12))
            elif ev_g >= 0.54 and dep_g >= 0.48:
                au_secenek = "Toplam 2.5 UST"
                au_guven = min(79, int(58 + (ev_g + dep_g) * 14))
            elif ev_g <= 0.36 and dep_g <= 0.36:
                au_secenek = "Toplam 2.5 ALT"
                au_guven = min(76, int(60 + (1 - (ev_g + dep_g)) * 16))
            else:
                au_secenek = "Toplam 1.5 UST"
                au_guven = min(84, int(68 + (ev_g + dep_g) * 10))
            satirlar.append({"Analiz Tipi": etiket, "Bahis Kategorisi": "Toplam Gol Baremi", "AI Tahmin Secenegi": au_secenek, "Guven Seviyesi": f"%{au_guven}", "GuvenInt": au_guven})

            if (state == "in" and ev_skor > 0 and dep_skor > 0) or (ev_g >= 0.45 and dep_g >= 0.45):
                kg_secenek = "KG VAR (Iki Takim da Gol Atar)"
                kg_guven = 99 if (state == "in" and ev_skor > 0 and dep_skor > 0) else min(75, int(55 + min(ev_g, dep_g) * 30))
            else:
                kg_secenek = "KG YOK"
                kg_guven = min(74, int(58 + fark * 25))
            satirlar.append({"Analiz Tipi": etiket, "Bahis Kategorisi": "Karsilikli Gol (KG)", "AI Tahmin Secenegi": kg_secenek, "Guven Seviyesi": f"%{kg_guven}", "GuvenInt": kg_guven})

            ev_gol_barem = (ev_skor + 0.5) if state == "in" else 1.5
            if ev_g >= 0.55:
                ev_gol_sec = f"{ev_ad} {ev_gol_barem} UST"
                ev_gol_guv = min(78, int(52 + ev_g * 32))
            else:
                ev_gol_sec = f"{ev_ad} {ev_gol_barem} ALT"
                ev_gol_guv = min(75, int(76 - ev_g * 28))
            satirlar.append({"Analiz Tipi": etiket, "Bahis Kategorisi": "Ev Sahibi Takim Golu", "AI Tahmin Secenegi": ev_gol_sec, "Guven Seviyesi": f"%{ev_gol_guv}", "GuvenInt": ev_gol_guv})

            dep_gol_barem = (dep_skor + 0.5) if state == "in" else 1.5
            if dep_g >= 0.55:
                dep_gol_sec = f"{dep_ad} {dep_gol_barem} UST"
                dep_gol_guv = min(76, int(50 + dep_g * 32))
            else:
                dep_gol_sec = f"{dep_ad} {dep_gol_barem} ALT"
                dep_gol_guv = min(77, int(78 - dep_g * 28))
            satirlar.append({"Analiz Tipi": etiket, "Bahis Kategorisi": "Deplasman Takim Golu", "AI Tahmin Secenegi": dep_gol_sec, "Guven Seviyesi": f"%{dep_gol_guv}", "GuvenInt": dep_gol_guv})

            en_iyi = sorted(satirlar, key=lambda x: x["GuvenInt"], reverse=True).pop(0)
            ozet_metin = f"{ms_secenek} (%{ms_guven}) | {au_secenek} (%{au_guven})"
            return satirlar, ozet_metin, en_iyi
        else:
            if ev_g >= dep_g:
                ms_secenek = f"{ev_ad} Kazanir (MS 1)"
                ms_guven = min(89, int(54 + fark * 48))
            else:
                ms_secenek = f"{dep_ad} Kazanir (MS 2)"
                ms_guven = min(88, int(54 + fark * 48))
            satirlar.append({"Analiz Tipi": etiket, "Bahis Kategorisi": "Mac Sonucu (MS)", "AI Tahmin Secenegi": ms_secenek, "Guven Seviyesi": f"%{ms_guven}", "GuvenInt": ms_guven})

            beklenen_toplam = round(212 + (ev_g + dep_g) * 14) + 0.5
            if lig_adi == "EuroLeague":
                beklenen_toplam = round(154 + (ev_g + dep_g) * 14) + 0.5
            if state == "in" and (ev_skor + dep_skor) > 150:
                beklenen_toplam = (ev_skor + dep_skor) + 36.5
            if (ev_g + dep_g) >= 1.05:
                au_secenek = f"Mac Toplami {beklenen_toplam} UST"
                au_guven = min(78, int(56 + (ev_g + dep_g) * 15))
            else:
                au_secenek = f"Mac Toplami {beklenen_toplam} ALT"
                au_guven = min(75, int(68 - (ev_g + dep_g) * 10))
            satirlar.append({"Analiz Tipi": etiket, "Bahis Kategorisi": "Mac Toplam Sayi", "AI Tahmin Secenegi": au_secenek, "Guven Seviyesi": f"%{au_guven}", "GuvenInt": au_guven})

            taban_ev = 77 if lig_adi == "EuroLeague" else 105
            ev_barem = round(taban_ev + ev_g * 14) + 0.5
            if ev_g >= 0.50:
                ev_sayi_sec = f"{ev_ad} {ev_barem} UST"
                ev_sayi_guv = min(77, int(52 + ev_g * 30))
            else:
                ev_sayi_sec = f"{ev_ad} {ev_barem} ALT"
                ev_sayi_guv = min(74, int(75 - ev_g * 25))
            satirlar.append({"Analiz Tipi": etiket, "Bahis Kategorisi": "Ev Sahibi Takim Sayisi", "AI Tahmin Secenegi": ev_sayi_sec, "Guven Seviyesi": f"%{ev_sayi_guv}", "GuvenInt": ev_sayi_guv})

            taban_dep = 75 if lig_adi == "EuroLeague" else 103
            dep_barem = round(taban_dep + dep_g * 14) + 0.5
            if dep_g >= 0.50:
                dep_sayi_sec = f"{dep_ad} {dep_barem} UST"
                dep_sayi_guv = min(76, int(51 + dep_g * 30))
            else:
                dep_sayi_sec = f"{dep_ad} {dep_barem} ALT"
                dep_sayi_guv = min(75, int(76 - dep_g * 25))
            satirlar.append({"Analiz Tipi": etiket, "Bahis Kategorisi": "Deplasman Takim Sayisi", "AI Tahmin Secenegi": dep_sayi_sec, "Guven Seviyesi": f"%{dep_sayi_guv}", "GuvenInt": dep_sayi_guv})

            en_iyi = sorted(satirlar, key=lambda x: x["GuvenInt"], reverse=True).pop(0)
            ozet_metin = f"{ms_secenek} (%{ms_guven}) | {au_secenek} (%{au_guven})"
            return satirlar, ozet_metin, en_iyi
    except Exception:
        varsayilan = list(({"Analiz Tipi": "Genel", "Bahis Kategorisi": "Genel Analiz", "AI Tahmin Secenegi": "Form Verisi Bekleniyor", "Guven Seviyesi": "%55", "GuvenInt": 55},))
        return varsayilan, "Veri Bekleniyor (%55)", varsayilan.pop(0)


@st.cache_data(ttl=120)
def ai_kadro_ve_eksik_getir(lig_yolu, mac_id, ev_id, dep_id, spor_turu):
    kadro_limiti = 11 if spor_turu == "Futbol" else 5
    ev_sakatlar, dep_sakatlar = list(), list()
    ev_ilk_kadro, dep_ilk_kadro = list(), list()
    kaynak_durumu = "Resmi Kadro Havuzu (Sakatlar Cikarildi - Ilk 5 Mac Saati Aciklanir)"
    if lig_yolu == "euroleague_resmi":
        return ev_ilk_kadro, dep_ilk_kadro, ev_sakatlar, dep_sakatlar, "EuroLeague Resmi Veri Akisi"
    try:
        sum_url = f"{url_basi}{lig_yolu}/summary?event={mac_id}"
        s_veri = requests.get(sum_url, headers=basliklar, timeout=8).json()
        for grup in s_veri.get("injuries", list()):
            t_id = str(grup.get("team", {}).get("id", ""))
            for sakat in grup.get("injuries", list()):
                ad = sakat.get("athlete", {}).get("displayName", "")
                durum = sakat.get("status", "Eksik")
                if ad:
                    bilgi = f"{ad} ({durum})"
                    if t_id == str(ev_id):
                        ev_sakatlar.append(bilgi)
                    elif t_id == str(dep_id):
                        dep_sakatlar.append(bilgi)
        for r_grup in s_veri.get("rosters", list()):
            t_id = str(r_grup.get("team", {}).get("id", ""))
            baslayanlar = list()
            for oyuncu in r_grup.get("roster", list()):
                if oyuncu.get("starter"):
                    o_ad = oyuncu.get("athlete", {}).get("displayName", "")
                    poz = oyuncu.get("position", {}).get("abbreviation", "")
                    if o_ad:
                        baslayanlar.append(f"{o_ad} ({poz})" if poz else o_ad)
            if baslayanlar:
                kaynak_durumu = "Resmi Aciklanan Mac Kadrosu"
                if t_id == str(ev_id):
                    ev_ilk_kadro = baslayanlar[:kadro_limiti]
                elif t_id == str(dep_id):
                    dep_ilk_kadro = baslayanlar[:kadro_limiti]
        sakat_isimler_temiz = list(x.split(" (").pop(0) for x in (ev_sakatlar + dep_sakatlar))
        if not ev_ilk_kadro and ev_id:
            r_ev = requests.get(f"{url_basi}{lig_yolu}/teams/{ev_id}/roster", headers=basliklar, timeout=8).json()
            for item in r_ev.get("athletes", list()):
                if "items" in item:
                    for alt in item.get("items", list()):
                        ad = alt.get("displayName", "")
                        poz = alt.get("position", {}).get("abbreviation", "")
                        if ad and ad not in sakat_isimler_temiz and len(ev_ilk_kadro) < kadro_limiti:
                            ev_ilk_kadro.append(f"{ad} ({poz})" if poz else ad)
                else:
                    ad = item.get("displayName", "")
                    poz = item.get("position", {}).get("abbreviation", "")
                    if ad and ad not in sakat_isimler_temiz and len(ev_ilk_kadro) < kadro_limiti:
                        ev_ilk_kadro.append(f"{ad} ({poz})" if poz else ad)
        if not dep_ilk_kadro and dep_id:
            r_dep = requests.get(f"{url_basi}{lig_yolu}/teams/{dep_id}/roster", headers=basliklar, timeout=8).json()
            for item in r_dep.get("athletes", list()):
                if "items" in item:
                    for alt in item.get("items", list()):
                        ad = alt.get("displayName", "")
                        poz = alt.get("position", {}).get("abbreviation", "")
                        if ad and ad not in sakat_isimler_temiz and len(dep_ilk_kadro) < kadro_limiti:
                            dep_ilk_kadro.append(f"{ad} ({poz})" if poz else ad)
                else:
                    ad = item.get("displayName", "")
                    poz = item.get("position", {}).get("abbreviation", "")
                    if ad and ad not in sakat_isimler_temiz and len(dep_ilk_kadro) < kadro_limiti:
                        dep_ilk_kadro.append(f"{ad} ({poz})" if poz else ad)
    except Exception:
        pass
    return ev_ilk_kadro, dep_ilk_kadro, ev_sakatlar, dep_sakatlar, kaynak_durumu
@st.cache_data(ttl=600, show_spinner=False)
def gemini_taktik_yorumu_uret(api_key, spor_turu, lig_adi, ev_ad, dep_ad, ev_rec, dep_rec, ev_eksik, dep_eksik, durum_metni):
    if not GEMINI_AKTIF or not api_key:
        return None
    soru = (
        f"Sen profesyonel bir {spor_turu} veri analistisin. {lig_adi} ligindeki {ev_ad} (Form: {ev_rec}) vs {dep_ad} (Form: {dep_rec}) "
        f"macini incele. Mac durumu: {durum_metni}. "
        f"{ev_ad} eksikler: {ev_eksik}. {dep_ad} eksikler: {dep_eksik}. "
        f"Sadece su an aktif olan 2026-2027 sezonu guncel kadrolarini baz al (eski veya takas olmus oyunculari kesinlikle yazma). "
        f"Turkce olarak 3 kisa madde halinde: 1) Taktik ve tempo beklentisi, 2) Eksik oyuncularin oyuna etkisi, 3) Guncel kadro ve kilit oyuncu yorumu yap."
    )
    son_hata =""
    modeller = ("gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3-flash-preview")
     
    try:
        client = genai.Client(api_key=api_key.strip(), http_options={"api_version": "v1beta"})
        for m in modeller:
            try:
                yanit = client.models.generate_content(
                    model=m,
                    contents=soru,
                )
                if yanit and yanit.text:
                    return yanit.text
            except Exception as ic_hata:
                son_hata = str(ic_hata)
                continue
        return f"Gemini AI baglanti uyarisi: {son_hata}"
    except Exception as e:
        return f"Gemini AI baglanti uyarisi: {str(e)}"


def excel_dosyasi_olustur(df):
    tampon = io.BytesIO()
    with pd.ExcelWriter(tampon, engine="openpyxl") as yazici:
        df.to_excel(yazici, index=False, sheet_name="AI_Analiz")
    return tampon.getvalue()


if gorunum == "Canli Kupon Takip":
    st.subheader("Canli Kombine Kupon Olusturucu & Anlik Takip")
    c1, c2, c3 = st.columns(3)
    k_spor = c1.selectbox("Spor", ("Basketbol", "Futbol"), key="k_spor")
    k_lig = c2.selectbox("Lig", list(TUM_LIGLER[k_spor].keys()), key="k_lig")
    k_yol = TUM_LIGLER[k_spor][k_lig]

    k_maclar_veri = list()
    try:
        resp = (
            _el_get(tarih)
            if k_yol == "euroleague_resmi"
            else requests.get(f"{url_basi}{k_yol}/scoreboard?dates={tarih}", headers=basliklar, timeout=6).json()
        )
        for ev in resp.get("events", list()):
            comp = ev.get("competitions", list(({},))).pop(0)
            takimlar = comp.get("competitors", list())
            if len(takimlar) >= 2:
                ev_t = next((t for t in takimlar if t.get("homeAway") == "home"), takimlar.pop(0))
                dep_t = next((t for t in takimlar if t.get("homeAway") == "away"), takimlar.pop(0))
                ev_ad = ev_t.get("team", {}).get("displayName", "Ev")
                dep_ad = dep_t.get("team", {}).get("displayName", "Dep")
                k_maclar_veri.append(
                    {
                        "id": ev.get("id"),
                        "yol": k_yol,
                        "spor": k_spor,
                        "ev": ev_ad,
                        "dep": dep_ad,
                        "etiket": f"{ev_ad} vs {dep_ad}",
                    }
                )
    except Exception:
        pass

    if k_maclar_veri:
        secilen_k_etiket = c3.selectbox("Mac Sec", list(m["etiket"] for m in k_maclar_veri), key="k_mac")
        secilen_k_obj = next(m for m in k_maclar_veri if m["etiket"] == secilen_k_etiket)
        t_col1, t_col2 = st.columns(2)

        if k_spor == "Futbol":
            secenekler = (
                "MS 1",
                "MS 0",
                "MS 2",
                "1.5 UST",
                "2.5 UST",
                "2.5 ALT",
                "KG VAR",
                "KG YOK",
                "Toplam Barem UST",
                "Toplam Barem ALT",
                "Ev Sahibi Barem UST",
                "Ev Sahibi Barem ALT",
                "Deplasman Barem UST",
                "Deplasman Barem ALT",
            )
            secilen_tip = t_col1.selectbox("Tahmin Tipi", secenekler, key="k_tahmin")

            if "Barem" in secilen_tip:
                taraf = (
                    "Ev Sahibi"
                    if "Ev Sahibi" in secilen_tip
                    else ("Deplasman" if "Deplasman" in secilen_tip else "Toplam")
                )
                ornek_val = 1.5 if taraf in ("Ev Sahibi", "Deplasman") else 3.5
                ozel_b = t_col2.number_input(
                    f"{taraf} Barem Gir (Ornek: {ornek_val})",
                    min_value=0.5,
                    max_value=15.5,
                    value=ornek_val,
                    step=1.0,
                    key="k_barem_f",
                )
                yon = "UST" if "UST" in secilen_tip else "ALT"
                oynanan_tahmin = f"{taraf} {ozel_b} {yon}"
            else:
                oynanan_tahmin = secilen_tip
        else:
            secenekler = (
                "MS 1",
                "MS 2",
                "Toplam UST (El Ile Barem)",
                "Toplam ALT (El Ile Barem)",
                "Ev Sahibi UST (El Ile Barem)",
                "Ev Sahibi ALT (El Ile Barem)",
                "Deplasman UST (El Ile Barem)",
                "Deplasman ALT (El Ile Barem)",
            )
            secilen_tip = t_col1.selectbox("Tahmin Tipi", secenekler, key="k_tahmin_b")

            if "El Ile Barem" in secilen_tip:
                if "Ev Sahibi" in secilen_tip:
                    taraf, varsayilan, min_v, max_v = "Ev Sahibi", 82.5, 40.5, 160.5
                elif "Deplasman" in secilen_tip:
                    taraf, varsayilan, min_v, max_v = "Deplasman", 82.5, 40.5, 160.5
                else:
                    taraf, varsayilan, min_v, max_v = "Toplam", 165.5, 100.5, 280.5

                ozel_b = t_col2.number_input(
                    f"{taraf} Barem Sayisi Gir (Ornek: {varsayilan})",
                    min_value=min_v,
                    max_value=max_v,
                    value=varsayilan,
                    step=1.0,
                    key=f"k_barem_b_{taraf}",
                )
                yon = "UST" if "UST" in secilen_tip else "ALT"
                oynanan_tahmin = f"{taraf} {ozel_b} {yon}"
            else:
                oynanan_tahmin = secilen_tip

        if st.button("Kupona Ekle"):
            st.session_state.kupon_listesi.append(
                {
                    "id": secilen_k_obj["id"],
                    "yol": secilen_k_obj["yol"],
                    "spor": secilen_k_obj["spor"],
                    "ev": secilen_k_obj["ev"],
                    "dep": secilen_k_obj["dep"],
                    "tahmin": oynanan_tahmin,
                }
            )
            st.session_state.kupon_bildirim_gonderildi = False
            st.rerun()
    else:
        st.info("Bu ligde secili tarihte mac bulunamadi.")

    st.divider()
    if st.session_state.kupon_listesi:
        st.subheader("Aktif Kuponum & Canli Tutma Ihtimali")
        kupon_tablosu = list()
        genel_ihtimal = 1.0
        hepsi_bitti_ve_tuttu = True

        for idx, item in enumerate(st.session_state.kupon_listesi):
            ev_s, dep_s, state_k, detay_k = 0, 0, "pre", "Baslamadi"
            try:
                if item["yol"] == "euroleague_resmi":
                    bulunan_ev = next(
                        (x for x in _el_get(tarih).get("events", list()) if str(x.get("id")) == str(item["id"])),
                        {},
                    )
                    header_comp = bulunan_ev.get("competitions", list(({},))).pop(0)
                    state_k = bulunan_ev.get("status", {}).get("type", {}).get("state", "pre")
                    detay_k = bulunan_ev.get("status", {}).get("type", {}).get("shortDetail", "")
                else:
                    s_res = requests.get(
                        f"{url_basi}{item['yol']}/summary?event={item['id']}", headers=basliklar, timeout=5
                    ).json()
                    header_comp = s_res.get("header", {}).get("competitions", list(({},))).pop(0)
                    state_k = header_comp.get("status", {}).get("type", {}).get("state", "pre")
                    detay_k = header_comp.get("status", {}).get("type", {}).get("shortDetail", "")

                for t_obj in header_comp.get("competitors", list()):
                    if t_obj.get("homeAway") == "home":
                        ev_s = int(float(t_obj.get("score", 0) or 0))
                    else:
                        dep_s = int(float(t_obj.get("score", 0) or 0))
            except Exception:
                pass

            t = item["tahmin"]
            toplam_s = ev_s + dep_s
            durum_ikon = "⏳ Beklemede"
            tekil_olasilik = 0.58

            if state_k in ("in", "post"):
                tuttu_mu = False
                if t == "MS 1" and ev_s > dep_s:
                    tuttu_mu = True
                elif t == "MS 2" and dep_s > ev_s:
                    tuttu_mu = True
                elif t == "MS 0" and ev_s == dep_s:
                    tuttu_mu = True
                elif t == "KG VAR" and ev_s > 0 and dep_s > 0:
                    tuttu_mu = True
                elif t == "KG YOK" and (ev_s == 0 or dep_s == 0):
                    tuttu_mu = True
                elif "UST" in t:
                    barem = float(list(x for x in t.split() if "." in x).pop(0))
                    hedef_skor = ev_s if "Ev Sahibi" in t else (dep_s if "Deplasman" in t else toplam_s)
                    if hedef_skor > barem:
                        tuttu_mu = True
                elif "ALT" in t:
                    barem = float(list(x for x in t.split() if "." in x).pop(0))
                    hedef_skor = ev_s if "Ev Sahibi" in t else (dep_s if "Deplasman" in t else toplam_s)
                    if hedef_skor < barem:
                        tuttu_mu = True

                if state_k == "post":
                    if tuttu_mu:
                        durum_ikon = "✅ TUTTU"
                        tekil_olasilik = 1.0
                    else:
                        durum_ikon = "❌ YATTI"
                        tekil_olasilik = 0.0
                        hepsi_bitti_ve_tuttu = False
                else:
                    hepsi_bitti_ve_tuttu = False
                    if tuttu_mu:
                        durum_ikon = "🟢 Su An Tutuyor"
                        tekil_olasilik = 0.78
                    else:
                        durum_ikon = "🟡 Geride / Bekliyor"
                        tekil_olasilik = 0.35
            else:
                hepsi_bitti_ve_tuttu = False

            if state_k == "in":
                _, _, k_alarm = koc_ve_rotasyon_etkisi_getir(
                    item["yol"], item["id"], "", "", item["spor"], item["ev"], item["dep"]
                )
                skor_anahtari = f"{item['id']}_{ev_s}_{dep_s}"
                if (ev_s + dep_s) > 0 and skor_anahtari not in st.session_state.gonderilen_kritik_uyarilar:
                    st.session_state.gonderilen_kritik_uyarilar.append(skor_anahtari)
                    if item["spor"] == "Futbol":
                        telegram_mesaj_gonder(
                            tg_token,
                            tg_chat_id,
                            f"GOL! {item['ev']} {ev_s} - {dep_s} {item['dep']} ({detay_k}) | Oynanan: {t}",
                        )
                if k_alarm and k_alarm not in st.session_state.gonderilen_kritik_uyarilar:
                    st.session_state.gonderilen_kritik_uyarilar.append(k_alarm)
                    telegram_mesaj_gonder(tg_token, tg_chat_id, f"KRITIK AN: {k_alarm} | Oynanan: {t}")

            genel_ihtimal *= tekil_olasilik
            kupon_tablosu.append(
                {
                    "Mac": f"{item['ev']} vs {item['dep']}",
                    "Oynanan": t,
                    "Skor": f"{ev_s} - {dep_s}",
                    "Sure": detay_k,
                    "Durum": durum_ikon,
                    "Canli Ihtimal": f"%{int(tekil_olasilik * 100)}",
                }
            )

        st.dataframe(pd.DataFrame(kupon_tablosu), use_container_width=True, hide_index=True)

        k1, k2 = st.columns(2)
        k1.metric("Kuponun Canli Tutma Ihtimali", f"%{int(genel_ihtimal * 100)}")
        if k2.button("Kuponu Temizle"):
            st.session_state.kupon_listesi = list()
            st.session_state.kupon_bildirim_gonderildi = False
            st.rerun()

        if hepsi_bitti_ve_tuttu and len(st.session_state.kupon_listesi) > 0:
            st.success("🎉 TEBRIKLER! KUPONUNUZDAKI TUM MACLAR KAZANDI!")
            st.balloons()
            if not st.session_state.kupon_bildirim_gonderildi:
                if SES_AKTIF:
                    winsound.Beep(1000, 700)
                ozet_msj = "TEBRIKLER! KUPONUNUZ KAZANDI! - " + " | ".join(
                    list(f"{x['Mac']} -> {x['Oynanan']} ({x['Skor']})" for x in kupon_tablosu)
                )
                telegram_mesaj_gonder(tg_token, tg_chat_id, ozet_msj)
                st.session_state.kupon_bildirim_gonderildi = True

elif gorunum == "Puan Durumu":
    st.subheader(f"{lig} - Guncel Puan Durumu")
    try:
        r = requests.get(f"{puan_basi}{yol}/standings", headers=basliklar, timeout=8).json()
        satirlar = list()
        for g in r.get("children", list()):
            for i, e in enumerate(g.get("standings", {}).get("entries", list()), 1):
                st_dict = {s["name"]: s["displayValue"] for s in e.get("stats", list())}
                satirlar.append(
                    {
                        "Grup": g.get("name", ""),
                        "Sira": i,
                        "Takim": e["team"]["displayName"],
                        "O": st_dict.get("gamesPlayed", "-"),
                        "G": st_dict.get("wins", "-"),
                        "M": st_dict.get("losses", "-"),
                        "Puan/Oran": st_dict.get("points", st_dict.get("winPercent", "-")),
                    }
                )
        if satirlar:
            puan_df = pd.DataFrame(satirlar)
            st.dataframe(puan_df, use_container_width=True, hide_index=True)
            st.download_button(
                "Puan Durumunu Excel Olarak Indir",
                data=excel_dosyasi_olustur(puan_df),
                file_name=f"{lig}_Puan_Durumu.xlsx",
            )
        else:
            st.info("Bu lig icin su an puan durumu tablosu yok.")
    except Exception:
        st.info("Bu lig icin su an puan durumu tablosu mevcut degil.")

elif gorunum == "AI Gunun Radari (Tum Ligler)":
    st.subheader(f"AI Gunun Radari | {tarih_obj.strftime('%d.%m.%Y')} Tum Ligler Taramasi")
    st.write("Tek tikla dunya genelindeki tum aktif ligleri tarayarak en yuksek guven oranina sahip banko tahminleri listeler.")
    if st.button("Tum Ligleri Simdi Tara ve En Guclu Tahminleri Bul", type="primary"):
        tum_radar = list()
        ilerleme = st.progress(0)
        toplam_islem = sum(len(v) for v in TUM_LIGLER.values())
        sayac = 0
        for s_adi, lig_sozluk in TUM_LIGLER.items():
            for l_adi, l_yolu in lig_sozluk.items():
                sayac += 1
                ilerleme.progress(min(1.0, sayac / toplam_islem))
                try:
                    resp = (
                        _el_get(tarih)
                        if l_yolu == "euroleague_resmi"
                        else requests.get(
                            f"{url_basi}{l_yolu}/scoreboard?dates={tarih}", headers=basliklar, timeout=5
                        ).json()
                    )
                    for ev in resp.get("events", list()):
                        comp = ev.get("competitions", list()).pop(0)
                        t_list = comp.get("competitors", list())
                        t1, t2 = t_list.pop(0), t_list.pop(0)
                        ev_t = t1 if t1["homeAway"] == "home" else t2
                        dep_t = t2 if t1["homeAway"] == "home" else t1
                        ev_ad, dep_ad = ev_t["team"]["displayName"], dep_t["team"]["displayName"]
                        ev_r = ev_t.get("records", list()).pop(0).get("summary", "0-0") if ev_t.get("records") else "0-0"
                        dep_r = dep_t.get("records", list()).pop(0).get("summary", "0-0") if dep_t.get("records") else "0-0"
                        st_code = ev["status"]["type"]["state"]
                        _, _, en_iyi = coklu_tahmin_motoru(
                            ev_ad,
                            dep_ad,
                            ev_r,
                            dep_r,
                            s_adi,
                            l_adi,
                            0,
                            0,
                            st_code,
                            int(ev_t.get("score", 0)),
                            int(dep_t.get("score", 0)),
                        )
                        tum_radar.append(
                            {
                                "Spor": s_adi,
                                "Lig": l_adi,
                                "Mac": f"{ev_ad} vs {dep_ad}",
                                "Durum": ev["status"]["type"]["shortDetail"],
                                "AI En Guclu Tahmin": en_iyi["AI Tahmin Secenegi"],
                                "Guven": f"%{en_iyi['GuvenInt']}",
                                "GuvenInt": en_iyi["GuvenInt"],
                            }
                        )
                except Exception:
                    pass
        st.session_state.radar_sonuclari = sorted(tum_radar, key=lambda x: x["GuvenInt"], reverse=True)
    if st.session_state.radar_sonuclari:
        radar_df = pd.DataFrame(st.session_state.radar_sonuclari).drop(columns=("GuvenInt",), errors="ignore")
        st.success(f"Toplam {len(radar_df)} mac tarandi ve guven sirasina gore listelendi!")
        st.dataframe(radar_df, use_container_width=True, hide_index=True)
        st.download_button(
            "Gunun Radar Raporunu Excel Indir",
            data=excel_dosyasi_olustur(radar_df),
            file_name=f"AI_Radar_{tarih}.xlsx",
        )

else:
    r = (
        _el_get(tarih)
        if yol == "euroleague_resmi"
        else requests.get(f"{url_basi}{yol}/scoreboard?dates={tarih}", headers=basliklar, timeout=8).json()
    )
    maclar = list()
    banko_havuzu = list()
    for ev in r.get("events", list()):
        mac_id = ev.get("id", "")
        comp = ev.get("competitions", list()).pop(0)
        takim_listesi = comp.get("competitors", list())
        t1 = takim_listesi.pop(0)
        t2 = takim_listesi.pop(0)
        ev_t = t1 if t1["homeAway"] == "home" else t2
        dep_t = t2 if t1["homeAway"] == "home" else t1
        ev_ad, dep_ad = ev_t["team"]["displayName"], dep_t["team"]["displayName"]
        ev_id, dep_id = ev_t["team"].get("id", ""), dep_t["team"].get("id", "")
        ev_rec_list = ev_t.get("records", list())
        dep_rec_list = dep_t.get("records", list())
        ev_rec = ev_rec_list.pop(0).get("summary", "0-0") if ev_rec_list else "0-0"
        dep_rec = dep_rec_list.pop(0).get("summary", "0-0") if dep_rec_list else "0-0"
        state = ev["status"]["type"]["state"]
        durum_detay = ev["status"]["type"]["shortDetail"]
        ev_s_int = int(ev_t.get("score", 0))
        dep_s_int = int(dep_t.get("score", 0))

        if durum_filtre == "Sadece Canli Maclar" and state != "in":
            continue
        if durum_filtre == "Oynanacak Maclar" and state != "pre":
            continue
        if durum_filtre == "Biten Maclar" and state != "post":
            continue

        is_fav = bool(favori and (favori in ev_ad.lower() or favori in dep_ad.lower()))
        if favori and not is_fav:
            continue

        if state == "in":
            durum_gosterim = f"CANLI ({durum_detay})"
            skor_gosterim = f"{ev_s_int} - {dep_s_int}"
            if mac_id in st.session_state.eski_skorlar and st.session_state.eski_skorlar[mac_id] != skor_gosterim:
                st.toast(f"SKOR DEGISTI! {ev_ad} {skor_gosterim} {dep_ad}")
                if SES_AKTIF and otomatik_yenile:
                    winsound.Beep(1000, 350)
            st.session_state.eski_skorlar[mac_id] = skor_gosterim
        elif state == "post":
            durum_gosterim = f"BITTI ({durum_detay})"
            skor_gosterim = f"{ev_s_int} - {dep_s_int}"
        else:
            durum_gosterim = durum_detay
            skor_gosterim = "vs"

        iy_ceyrek_str = periyot_ve_iy_cikar(ev_t, dep_t, spor, state)
        _, ozet_tahmin, en_guclu = coklu_tahmin_motoru(
            ev_ad, dep_ad, ev_rec, dep_rec, spor, lig, 0, 0, state, ev_s_int, dep_s_int
        )

        banko_havuzu.append(
            {
                "mac": f"{ev_ad} - {dep_ad}",
                "tahmin": en_guclu["AI Tahmin Secenegi"],
                "guven": en_guclu["Guven Seviyesi"],
                "guven_int": en_guclu["GuvenInt"],
            }
        )

        maclar.append(
            {
                "ID": mac_id,
                "EvID": ev_id,
                "DepID": dep_id,
                "State": state,
                "EvSkorInt": ev_s_int,
                "DepSkorInt": dep_s_int,
                "MacSecim": f"{ev_ad} vs {dep_ad}",
                "Fav": is_fav,
                "Dakika / Ceyrek": durum_gosterim,
                "Ev Sahibi": ev_ad,
                "Canli Skor": skor_gosterim,
                "Deplasman": dep_ad,
                "IY / Ceyrek Skorlari": iy_ceyrek_str,
                "Ev Form": ev_rec,
                "Dep Form": dep_rec,
                "Hizli AI Ozet": ozet_tahmin,
                "Canli Firsat": canli_firsat_etiketi_uret(spor, state, durum_detay, ev_s_int, dep_s_int, ev_rec, dep_rec),

            }
        )
    if maclar:
        en_iyi_kartlar = sorted(banko_havuzu, key=lambda x: x["guven_int"], reverse=True)[:3]
        if en_iyi_kartlar:
            st.subheader(f"{lig} | Gunun En Yuksek Guvenli AI Tahminleri")
            cols = st.columns(len(en_iyi_kartlar))
            for i, k in enumerate(en_iyi_kartlar):
                cols[i].metric(label=k["mac"], value=k["tahmin"], delta=f"Guven: {k['guven']}")

        st.subheader(f"{lig} | Canli Skor, IY / Ceyrek Detaylari ve AI Analiz")
        df_ham = pd.DataFrame(maclar)
        gizlenecek = ("ID", "EvID", "DepID", "State", "EvSkorInt", "DepSkorInt", "MacSecim", "Fav")
        gosterilecek_tablo = df_ham.drop(columns=list(gizlenecek))
        st.dataframe(gosterilecek_tablo, use_container_width=True, hide_index=True)
        st.download_button(
            "Bu Ligin Analiz Tablosunu Excel Indir",
            data=excel_dosyasi_olustur(gosterilecek_tablo),
            file_name=f"{lig}_{tarih}.xlsx",
        )
        st.divider()
        st.subheader("Secilen Mac Icin Detayli AI Tahmin, H2H Form ve Kadro Analizi")
        secilen_mac = st.selectbox("Incelenecek maci secin:", df_ham["MacSecim"].tolist())
        satir = df_ham[df_ham["MacSecim"] == secilen_mac].head(1).to_dict(orient="records").pop(0)
        h2h_verisi = h2h_ve_form_getir(yol, satir["ID"], satir["Ev Sahibi"], satir["Deplasman"])
        ev_kadro, dep_kadro, ev_eksikler, dep_eksikler, kaynak = ai_kadro_ve_eksik_getir(
            yol, satir["ID"], satir["EvID"], satir["DepID"], spor
        )
        koc_etkisi_metni, momentum_etkisi, _ = koc_ve_rotasyon_etkisi_getir(
            yol, satir["ID"], satir["EvID"], satir["DepID"], spor, satir["Ev Sahibi"], satir["Deplasman"]
        )
        detayli_tahmin_satirlari, _, _ = coklu_tahmin_motoru(
            satir["Ev Sahibi"],
            satir["Deplasman"],
            satir["Ev Form"],
            satir["Dep Form"],
            spor,
            lig,
            len(ev_eksikler),
            len(dep_eksikler),
            satir["State"],
            satir["EvSkorInt"],
            satir["DepSkorInt"],
        )
        st.markdown(f"*Durum:* {satir['Dakika / Ceyrek']}  |  *Periyot / IY Detayi:* {satir['IY / Ceyrek Skorlari']}")
        if satir["State"] == "in":
            st.warning(f"⚡ Canli Koc Hamlesi & Rotasyon Etkisi: {koc_etkisi_metni}")
        df_goster = pd.DataFrame(detayli_tahmin_satirlari).drop(columns=("GuvenInt",), errors="ignore")
        st.dataframe(df_goster, use_container_width=True, hide_index=True)
        if gemini_api_key:
            with st.spinner("Gercek Yapay Zeka (Gemini) maci ve kadrolari yorumluyor..."):
                zengin_durum = f"{satir['Dakika / Ceyrek']} | Taktik: {koc_etkisi_metni} | Aktif Kadro Ornekleri: Ev({', '.join(ev_kadro)}), Dep({', '.join(dep_kadro)})"
                ai_yorum = gemini_taktik_yorumu_uret(
                    gemini_api_key,
                    spor,
                    lig,
                    satir["Ev Sahibi"],
                    satir["Deplasman"],
                    satir["Ev Form"],
                    satir["Dep Form"],
                    ", ".join(ev_eksikler),
                    ", ".join(dep_eksikler),
                    zengin_durum,
                )
                if ai_yorum:
                    st.success(f"Gemini AI Taktik ve Kadro Yorumu: {ai_yorum}")
        if h2h_verisi:
            st.info("*Son Kafa Kafaya (H2H) Maclar:* " + "  |  ".join(h2h_verisi))
        st.info(f"*Kadro Kaynagi:* {kaynak}")
        st.write(f"*{satir['Ev Sahibi']} Eksikler:*", ", ".join(ev_eksikler) if ev_eksikler else "Bildirilen eksik yok")
        st.write(f"*{satir['Ev Sahibi']} Muhtemel Kadro:*", ", ".join(ev_kadro) if ev_kadro else "Lig verisi bekleniyor")
        st.write(f"*{satir['Deplasman']} Eksikler:*", ", ".join(dep_eksikler) if dep_eksikler else "Bildirilen eksik yok")
        st.write(f"*{satir['Deplasman']} Muhtemel Kadro:*", ", ".join(dep_kadro) if dep_kadro else "Lig verisi bekleniyor")
    else:
        st.warning("Bu tarihte mac bulunamadi. Sol menuden tarihi degistirin.")

if otomatik_yenile:
    time.sleep(30)
    st.rerun()

