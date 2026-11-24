import io
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
import pandas as pd
import requests
import streamlit as st
from analiz_motoru import PusulaAnalizBeyni

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
            r_res = requests.get(f"{el_host}results?seasonCode={sezon_kodu}", headers=h, timeout=8)
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

        r_sch = requests.get(f"{el_host}schedules?seasonCode={sezon_kodu}", headers=h, timeout=8)
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
                        live_json_url = "https://live." + f"euroleague.net/api/Boxscore?gamecode={gc}&seasoncode={sezon_kodu}"
                        lj = requests.get(live_json_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6).json()
                        by_q = lj.get("ByQuarter", list())
                        if len(by_q) >= 2:
                            ev_q_dict = by_q.pop(0)
                            dep_q_dict = by_q.pop(0)
                            tot_a, tot_b = 0, 0
                            for q_idx in range(1, 5):
                                qa = ev_q_dict.get(f"Quarter{q_idx}")
                                qb = dep_q_dict.get(f"Quarter{q_idx}")
                                if qa is not None and qb is not None and (int(qa) > 0 or int(qb) > 0 or q_idx == 1):
                                    ceyrekler_ev.append({"value": str(qa), "displayValue": str(qa)})
                                    ceyrekler_dep.append({"value": str(qb), "displayValue": str(qb)})
                                    tot_a += int(qa)
                                    tot_b += int(qb)
                            if tot_a > 0 or tot_b > 0:
                                hs, ds = str(tot_a), str(tot_b)
                            if st_code == "in":
                                aktif_q = len(ceyrekler_ev) if ceyrekler_ev else 1
                                detay = f"Canli (Q{aktif_q})"
                    except Exception:
                        pass

                    if hs == "0" and ds == "0":
                        try:
                            gr = requests.get(f"{el_host}games?seasonCode={sezon_kodu}&gameCode={gc}", headers=h, timeout=6)
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
        "Trendyol Super Lig": "soccer/tur.1",
        "Ingiltere Premier Lig": "soccer/eng.1",
        "Ispanya La Liga": "soccer/esp.1",
        "Italya Serie A": "soccer/ita.1",
        "Fransa Ligue 1": "soccer/fra.1",
        "Almanya Bundesliga": "soccer/ger.1",
        "Hollanda Eredivisie": "soccer/ned.1",
        "Belcika Pro League": "soccer/bel.1",
        "Portekiz Liga": "soccer/por.1",
        "Avusturya Bundesliga": "soccer/aut.1",
        "Isvicre Super League": "soccer/sui.1",
        "Isvec Allsvenskan": "soccer/swe.1",
        "Sampiyonlar Ligi": "soccer/uefa.champions",
        "Avrupa Ligi": "soccer/uefa.europa",
    },
    "Basketbol": {
        "NBA": "basketball/nba",
        "EuroLeague": "euroleague_resmi",
        
    },
}
gizli_tg_token = st.secrets.get("TG_TOKEN", "")
gizli_tg_chat_id = st.secrets.get("TG_CHAT_ID", "")
gizli_gemini_key = st.secrets.get("GEMINI_KEY", "") or st.secrets.get("GEMINI_API_KEY", "")
gemini_api_key = gizli_gemini_key
groq_api_key = st.secrets.get("GROQ_KEY", "") or st.secrets.get("GROQ_API_KEY", "")
beyin = PusulaAnalizBeyni(gemini_key=gemini_api_key, groq_key=groq_api_key)
st.sidebar.header("Kontrol Merkezi")
gorunum = st.sidebar.radio(
    "Mod Secimi",
    ["Maclar ve Canli AI Analiz", "Canli Kupon Takip", "AI Gunun Radari (Tum Ligler)", "Puan Durumu","AI Dogruluk Karnesi"],
)
gun_secimi = st.sidebar.radio(
    "Hizli Gun Secimi",
    ["Bugun", "Yarin", "2 Gun Sonra", "3 Gun Sonra", "Ozel Tarih Sec"],
    horizontal=True
)

bugun_tr = datetime.now(timezone(timedelta(hours=3)))
if gun_secimi == "Bugun":
    tarih_obj = bugun_tr
elif gun_secimi == "Yarin":
    tarih_obj = bugun_tr + timedelta(days=1)
elif gun_secimi == "2 Gun Sonra":
    tarih_obj = bugun_tr + timedelta(days=2)
elif gun_secimi == "3 Gun Sonra":
    tarih_obj = bugun_tr + timedelta(days=3)
else:
    tarih_obj = st.sidebar.date_input("Takvimden Sec", bugun_tr)

tarih = tarih_obj.strftime("%Y%m%d")
st.sidebar.caption(f"📅 Secili Bulten Tarihi: **{tarih_obj.strftime('%d.%m.%Y')}**")

st.sidebar.divider()
st.sidebar.subheader("Telegram Bildirim Ayari")
tg_token = gizli_tg_token
tg_chat_id = gizli_tg_chat_id


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
lig = st.sidebar.selectbox("Lig Secimi", ["Tumu (Butun Ligler)"] + list(TUM_LIGLER[spor].keys()))
yol = "" if lig == "Tumu (Butun Ligler)" else TUM_LIGLER[spor][lig]
yol = "" if lig == "Tumu (Butun Ligler)" else TUM_LIGLER[spor][lig]
durum_filtre = st.sidebar.radio("Mac Durumu", ["Tumu", "Sadece Canli Maclar", "Oynanacak Maclar", "Biten Maclar"])
favori = st.sidebar.text_input("Favori Takim", "").strip().lower()
otomatik_yenile = st.sidebar.checkbox("Canli Otomatik Yenileme & Alarm (30 sn)", value=False)

yol = "" if lig == "Tumu (Butun Ligler)" else TUM_LIGLER[spor][lig]
YILDIZ_LISTESI = (
    "Giannis", "Jokic", "Doncic", "Tatum", "Curry", "LeBron", "Durant", "Embiid", "Shai", "Edwards",
    "Brunson", "Mitchell", "Booker", "Davis", "Wembanyama", "Haliburton", "Maxey", "Banchero", "Morant",
    "Lillard", "Irving", "Young", "Ball", "Towns", "Sengun", "Larkin", "Vezenkov", "James", "Baldwin",
    "Tavares", "Campazzo", "Hezonja", "Lessort", "Nunn", "Sloukas", "Mirotic", "Clyburn", "Icardi", "Osimhen",
    "Dzeko", "Tadic", "Immobile", "Rafa", "Haaland", "Salah", "Mbappe", "Vinicius", "Bellingham", "Kane",
    "Yamal", "Lewandowski", "Palmer", "Saka", "Lautaro"
)

def sakatlik_etki_hesapla(sakat_listesi):
    etki = 0
    kritik_isimler = list()
    for s in sakat_listesi:
        if "(Out)" in s or "(Doubtful)" in s or "(Eksik)" in s:
            if any(y.lower() in s.lower() for y in YILDIZ_LISTESI):
                etki += 3
                kritik_isimler.append(s)
            else:
                etki += 1
    return etki, kritik_isimler

def son_dakika_baski_kontrol(spor_turu, state, detay_sure, ev_ad, dep_ad, ev_s, dep_s, ev_rec, dep_rec):
    if state != "in":
        return ""
    try:
        ev_p = [int(x) for x in ev_rec.split("-") if x.isdigit()]
        dep_p = [int(x) for x in dep_rec.split("-") if x.isdigit()]
        ev_ham_oran = ((ev_p[0] + 2) / (ev_top + 4)) if len(ev_p) >= 2 else 0.50
        dep_ham_oran = ((dep_p[0] + 2) / (dep_top + 4)) if len(dep_p) >= 2 else 0.50
        fark = abs(ev_s - dep_s)

        if spor_turu == "Futbol":
            rakamlar = "".join(c for c in detay_sure if c.isdigit())
            dk = int(rakamlar) if rakamlar else 0
            if dk >= 75 and fark <= 1 and (ev_g >= 0.58 or dep_g >= 0.58):
                baskili_takim = ev_ad if ev_g >= dep_g else dep_ad
                return f"⏳ SON DAKIKA BASKI UYARISI ({dk}. Dk): {ev_ad} {ev_s}-{dep_s} {dep_ad} | {baskili_takim} gol icin yukleniyor!"
        else:
            if ("Q4" in detay_sure or "4C" in detay_sure or "OT" in detay_sure) and fark <= 5:
                return f"⏳ CRUNCH TIME (SON CEYREK HEYECANI): {ev_ad} {ev_s}-{dep_s} {dep_ad} ({detay_sure}) | Fark sadece {fark} sayi!"
    except Exception:
        pass
    return ""
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
            if ("Q2" in detay_sure or "Half" in detay_sure or "2C" in detay_sure) and top_s >= 86:
                return "🔥 YUKSEK TEMPO (UST FIRSATI)"
            if "Q4" not in detay_sure and "4C" not in detay_sure and ev_g >= 0.65 and 6 <= (dep_s - ev_s) <= 14:
                return "🔥 FAVORI GERIDE (MS 1 FIRSATI)"
            if "Q4" not in detay_sure and "4C" not in detay_sure and dep_g >= 0.65 and 6 <= (ev_s - dep_s) <= 14:
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
        rapor = beyin.mac_deger_analizi(
            spor_turu=spor_turu,
            lig_adi=lig_adi,
            ev_ad=ev_ad,
            dep_ad=dep_ad,
            ev_rec=ev_rec,
            dep_rec=dep_rec,
            ev_eksik_puan=ev_eksik,
            dep_eksik_puan=dep_eksik,
            state=state,
            ev_skor=ev_skor,
            dep_skor=dep_skor
        )
        ev_g = rapor["ev_guc_yuzde"] / 100.0
        dep_g = rapor["dep_guc_yuzde"] / 100.0
        fark = abs(ev_g - dep_g)
        satirlar = list()
        tuzak_etiket = f"⚠️ {rapor['tuzak_notu']}" if rapor["tuzak_notu"] else f"💎 Deger Puani: {rapor['deger_puani']}/10 (Temiz)"
        satirlar.append({
        "Analiz Tipi": "MERKEZ BEYIN",
        "Bahis Kategorisi": "Deger & Tuzak Denetimi",
        "AI Tahmin Secenegi": f"{rapor['ana_tercih']} | {tuzak_etiket}",
        "Guven Seviyesi": f"%{rapor['guven']}",
        "GuvenInt": rapor["guven"]
     })
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
def canli_oyuncu_ve_olay_cek(mac_id, lig_yolu, spor_turu, sezon_kodu="E2026"):
    detay_ozet = list()
    try:
        if lig_yolu == "euroleague_resmi" and mac_id:
            u = "https://live." + f"euroleague.net/api/Boxscore?gamecode={mac_id}&seasoncode={sezon_kodu}"
            j = requests.get(u, headers={"User-Agent": "Mozilla/5.0"}, timeout=5).json()
            for idx, st_blok in enumerate(j.get("Stats", list())[:2]):
                t_ad = st_blok.get("Team", f"Takim {idx+1}")
                oyuncular = st_blok.get("PlayersStats", list())
                sahadakiler = list()
                faul_problemi = list()
                for o in oyuncular:
                    isim = o.get("Player", "").strip()
                    pts = int(o.get("Points", 0) or 0)
                    fls = int(o.get("FoulsCommited", 0) or 0)
                    is_playing = o.get("IsPlaying", 0)
                    if is_playing == 1 and isim:
                        sahadakiler.append(f"{isim} ({pts}s, {fls}f)")
                    if fls >= 3 and isim:
                        faul_problemi.append(f"{isim} ({fls} faul)")
                if sahadakiler:
                    detay_ozet.append(f"{t_ad} Sahadaki Bes: {', '.join(sahadakiler[:5])}")
                if faul_problemi:
                    detay_ozet.append(f"{t_ad} Faul Siniri: {', '.join(faul_problemi[:4])}")
        elif mac_id and "/" in lig_yolu:
            u = f"{url_basi}{lig_yolu}/summary?event={mac_id}"
            j = requests.get(u, headers=basliklar, timeout=5).json()
            for item in j.get("keyEvents", list())[-6:]:
                tip = item.get("type", {}).get("text", "")
                dk = item.get("clock", {}).get("displayValue", "")
                txt = item.get("text", "")
                if txt:
                    detay_ozet.append(f"[{dk}] {tip}: {txt}")
            for box_t in j.get("boxscore", {}).get("players", list())[:2]:
                t_ad = box_t.get("team", {}).get("displayName", "")
                stats_grp = box_t.get("statistics", list())
                if stats_grp:
                    ath_list = stats_grp.pop(0).get("athletes", list())
                    aktifler = list()
                    for a in ath_list[:6]:
                        a_ad = a.get("athlete", {}).get("displayName", "")
                        st_vals = a.get("stats", list())
                        if a_ad and st_vals:
                            aktifler.append(f"{a_ad} ({'/'.join(st_vals[:3])})")
                    if aktifler:
                        detay_ozet.append(f"{t_ad} Rotasyon: {', '.join(aktifler)}")
    except Exception:
        pass
    return " | ".join(detay_ozet) if detay_ozet else "Canli oyuncu/olay verisi henuz olusmadi."


@st.cache_data(ttl=90, show_spinner=False)
def gemini_taktik_yorumu_uret(api_key, spor_turu, lig_adi, ev_ad, dep_ad, ev_rec, dep_rec, ev_eksik, dep_eksik, durum_metni):
    soru = (
        f"Sen dunya capinda bir {spor_turu} Bas Analisti ve Basantrenor Danismanisin. "
        f"Duz istatistik ezberine (ilk yari cok sayi/gol oldu kesin ust biter gibi kliselere) ASLA dusme! "
        f"Mac: {lig_adi} | {ev_ad} (Form: {ev_rec}) vs {dep_ad} (Form: {dep_rec}). "
        f"Anlik Durum, Skor, Ceyrek/Yari Akisi ve Canli Saha/Oyuncu/Rotasyon Verileri: {durum_metni}. "
        f"{ev_ad} Eksikler: {ev_eksik}. {dep_ad} Eksikler: {dep_eksik}. "
        f"Analiz Kriterlerin:\n"
        f"1) Skor farki acildiysa kocun yildizlari kenara alip yedeklere donme (garbage time / rotasyon) ihtimalini hesapla.\n"
        f"2) Ilk yari anormal yuksek/dusuk tempo ciktiysa, ikinci yarida kocun savunma sertligi veya tempo kirma hamlesiyle baremin tersine donup donmeyecegini tart.\n"
        f"3) Sahadaki mevcut 5'leri, faul problemindeki kilit oyunculari, kartlari ve sakatliklari hesaba kat.\n"
        f"4) SIKI KURAL: Hafizandaki eski sezon oyuncularini (ornegin Trae Young, John Collins, Dejounte Murray gibi eski takimlarina gitmis isimleri) ASLA yazma! Yalnızca verilen Kadro Havuzu ve Canli Saha listesindeki oyunculari kullan.\n\n"
        f"Ciktiyi Turkce olarak TAM OLARAK su 3 baslikta, net ve ikna edici yaz:\n"
        f"🎯 NOKTA ATISI ANA KARAR: (Tek bir net secenek ve kendi belirledigin mantikli barem)\n"
        f"🧠 KOC, ROTASYON VE OYUN OKUMASI: (Neden bu karari verdigini sahadaki oyuncular, koc hamlesi ve tempo kirilmasiyla acikla)\n"
        f"⚠️ EN BUYUK RISK / DIKKAT NOKTASI: (Bu tahmini bozabilecek tek kritik senaryo)"
    )

    son_hata = ""
    if GEMINI_AKTIF and api_key:
        modeller = ("gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3-flash-preview")
        try:
            client = genai.Client(api_key=api_key.strip(), http_options={"api_version": "v1beta"})
            for m in modeller:
                try:
                    yanit = client.models.generate_content(model=m, contents=soru)
                    if yanit and yanit.text:
                        return yanit.text
                except Exception as ic_hata:
                    son_hata = str(ic_hata)
                    continue
        except Exception as e:
            son_hata = str(e)

    groq_anahtar = ""
    try:
        groq_anahtar = str(st.secrets["GROQ_KEY"]).strip()
    except Exception:
        pass

    if groq_anahtar:
        g_base = "https://" + "api." + "groq.com" + "/openai/v1"
        g_headers = {"Authorization": f"Bearer {groq_anahtar}", "Content-Type": "application/json"}
        denenecek_modeller = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]
        for aktif_model in denenecek_modeller[:6]:
            try:
                g_resp = requests.post(
                    f"{g_base}/chat/completions",
                    headers=g_headers,
                    json={
                        "model": aktif_model,
                        "messages": [{"role": "user", "content": soru}],
                        "temperature": 0.4,
                        "max_tokens": 450,
                    },
                    timeout=12,
                ).json()
                if "choices" in g_resp and len(g_resp["choices"]) > 0:
                    yanit_metin = g_resp["choices"].pop(0).get("message", {}).get("content", "").strip()
                    if yanit_metin:
                        return yanit_metin
                elif "error" in g_resp:
                    son_hata = f"Groq ({aktif_model}): {g_resp['error'].get('message', '')}"
            except Exception as ge:
                son_hata = f"Groq Baglanti: {ge}"

    return f"AI baglanti uyarisi: {son_hata}"
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

        st.divider()
        kupon_turu = st.radio(
            "Kupon Tipi Secimi",
            ["Kombine Kupon", "Tekli (Ayri Ayri) Kupon"],
            horizontal=True,
            key="kupon_turu_secim"
        )

        k1, k2, k3 = st.columns([2, 2, 1])

        if kupon_turu == "Kombine Kupon":
            k1.metric("Kombine Canli Tutma Ihtimali", f"%{int(genel_ihtimal * 100)}")
        else:
            ort_ihtimal = int((sum(float(x["Canli Ihtimal"].replace("%", "")) for x in kupon_tablosu) / len(kupon_tablosu))) if kupon_tablosu else 0
            k1.metric("Tekli Maclar Ortalama Ihtimal", f"%{ort_ihtimal}")

        if k2.button("📲 Kuponu Kaydet & Telegram'a Gonder", use_container_width=True):
            tarih_etiket = datetime.now(timezone(timedelta(hours=3))).strftime("%d.%m.%Y %H:%M")
            baslik_ikon = "🔗" if kupon_turu == "Kombine Kupon" else "🎯"

            mesaj_satirlari = [
                f"{baslik_ikon} YENI {kupon_turu.upper()} KAYDEDILDI ({tarih_etiket})",
                f"📋 Toplam Mac Sayisi: {len(kupon_tablosu)}",
                "--------------------------------"
            ]

            for idx_m, satir_m in enumerate(kupon_tablosu, 1):
                mesaj_satirlari.append(
                    f"{idx_m}. {satir_m['Mac']}\n"
                    f"   👉 Tahmin: {satir_m['Oynanan']} | Skor: {satir_m['Skor']} ({satir_m['Durum']})"
                )

            mesaj_satirlari.append("--------------------------------")
            if kupon_turu == "Kombine Kupon":
                mesaj_satirlari.append(f"📊 Kombine Tutma Ihtimali: %{int(genel_ihtimal * 100)}")
            else:
                mesaj_satirlari.append("💡 Tekli kupon olarak kaydedildi. Her mac bagimsiz takip edilir.")

            if telegram_mesaj_gonder(tg_token, tg_chat_id, "\n".join(mesaj_satirlari)):
                st.success("✅ Kupon kaydedildi ve detaylari Telegram ekranina gonderildi!")
            else:
                st.error("❌ Telegram gonderilemedi! Sol menuden TG_TOKEN ve TG_CHAT_ID ayarlarini kontrol et.")

        if k3.button("🗑️ Temizle", use_container_width=True):
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
elif gorunum == "AI Dogruluk Karnesi":
    st.subheader("📊 AI Dogruluk Karnesi & Lig Bazli Basari Analizi")
    import json, os
    if os.path.exists("haftalik_arsiv.json"):
        with open("haftalik_arsiv.json", "r", encoding="utf-8") as f:
            arsiv_veri = json.load(f)
        if arsiv_veri:
            df_arsiv = pd.DataFrame(arsiv_veri)
            toplam_mac = len(df_arsiv)
            toplam_isabet = int(df_arsiv["tuttu"].sum())
            genel_oran = int((toplam_isabet / toplam_mac) * 100)

            m1, m2, m3 = st.columns(3)
            m1.metric("Toplam Analiz Edilen Mac", f"{toplam_mac} Mac")
            m2.metric("Basarili AI Tahmini", f"{toplam_isabet} Isabet")
            m3.metric("Genel AI Isabet Orani", f"%{genel_oran}")

            st.divider()
            st.subheader("🏆 Lig Bazinda AI Basari Yuzdesi (%)")
            lig_grup = df_arsiv.groupby("lig").agg(
                Toplam_Mac=("tuttu", "count"),
                Tutan_Tahmin=("tuttu", "sum")
            ).reset_index()
            lig_grup["Basari_Orani (%)"] = ((lig_grup["Tutan_Tahmin"] / lig_grup["Toplam_Mac"]) * 100).round(1)
            lig_grup = lig_grup.sort_values(by="Basari_Orani (%)", ascending=False)

            st.bar_chart(lig_grup.set_index("lig")["Basari_Orani (%)"], color="#16A34A")
            st.dataframe(lig_grup, use_container_width=True, hide_index=True)
        else:
            st.info("Henuz tamamlanmis bulten kaydi bulunmuyor. Maclar bittikce grafik otomatik dolacaktir.")
    else:
        st.info("Henuz arsiv dosyasi olusmadi. Gunun bultenindeki maclar tamamlandikca veriler burada birikecektir.")
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
    secili_ligler = list(TUM_LIGLER[spor].items()) if lig == "Tumu (Butun Ligler)" else [(lig, yol)]
    maclar = list()
    banko_havuzu = list()
    for aktif_lig_ad, aktif_yol in secili_ligler:
        try:
            r = _el_get(tarih) if aktif_yol == "euroleague_resmi" else requests.get(f"{url_basi}{aktif_yol}/scoreboard?dates={tarih}&limit=100", headers=basliklar, timeout=8).json()
        except Exception:
            r = {}
        for ev in r.get("events", list()):
            try:
                mac_id = ev.get("id", "")
                comp = ev.get("competitions", list()).pop(0)
                t_list = comp.get("competitors", list())
                t1, t2 = t_list.pop(0), t_list.pop(0)
                ev_t = t1 if t1.get("homeAway") == "home" else t2
                dep_t = t2 if t1.get("homeAway") == "home" else t1
                ev_ad_ham = ev_t.get("team", {}).get("displayName", "")
                dep_ad = dep_t.get("team", {}).get("displayName", "")
                ev_ad = ev_ad_ham
                ev_id, dep_id = ev_t.get("team", {}).get("id", ""), dep_t.get("team", {}).get("id", "")
                ev_r_l, dep_r_l = ev_t.get("records", list()), dep_t.get("records", list())
                ev_rec = ev_r_l.pop(0).get("summary", "0-0") if ev_r_l else "0-0"
                dep_rec = dep_r_l.pop(0).get("summary", "0-0") if dep_r_l else "0-0"
                state = ev.get("status", {}).get("type", {}).get("state", "pre")
                durum_detay = ev.get("status", {}).get("type", {}).get("shortDetail", "")
                ev_s_int = int(float(ev_t.get("score", 0) or 0))
                dep_s_int = int(float(dep_t.get("score", 0) or 0))
                if (durum_filtre == "Sadece Canli Maclar" and state != "in") or (durum_filtre == "Oynanacak Maclar" and state != "pre") or (durum_filtre == "Biten Maclar" and state != "post"):
                    continue
                is_fav = bool(favori and (favori in ev_ad.lower() or favori in dep_ad.lower()))
                if favori and not is_fav:
                    continue
                mac_saat_tr = (datetime.fromisoformat(ev.get("date", "").replace("Z", "+00:00")) + timedelta(hours=3)).strftime("%H:%M") if ev.get("date") else durum_detay
                temiz_sure = durum_detay.replace("Half", "IY").replace("End of", "Sonu").replace("1st", "1P").replace("2nd", "2P").replace("3rd", "3P").replace("4th", "4P")
                durum_gosterim = f"🔴 {temiz_sure} CANLI" if state == "in" else (f"🏁 MS ({temiz_sure})" if state == "post" else f"⏰ {mac_saat_tr}")
                skor_gosterim = f"{ev_s_int} - {dep_s_int}" if state in ("in", "post") else "vs"
                if state == "in":
                    if mac_id in st.session_state.eski_skorlar and st.session_state.eski_skorlar.get(mac_id) != skor_gosterim:
                        st.toast(f"SKOR DEGISTI! {ev_ad} {skor_gosterim} {dep_ad}")
                    st.session_state.eski_skorlar[mac_id] = skor_gosterim
                iy_ceyrek_str = periyot_ve_iy_cikar(ev_t, dep_t, spor, state)
                _, ozet_tahmin, en_guclu = coklu_tahmin_motoru(ev_ad, dep_ad, ev_rec, dep_rec, spor, aktif_lig_ad, 0, 0, state, ev_s_int, dep_s_int)
                if state == "pre":
                 deger_rapor = beyin.mac_deger_analizi(spor, aktif_lig_ad, ev_ad, dep_ad, ev_rec, dep_rec, state=state)
                 if not deger_rapor["tuzak_notu"]:
                     banko_havuzu.append({"mac": f"{ev_ad} - {dep_ad}", "lig": aktif_lig_ad, "ev": ev_ad, "dep": dep_ad, "ozet": f"{deger_rapor['ana_tercih']} | {deger_rapor['barem_tercih']} | Deger: {deger_rapor['deger_puani']}/10", "guven": f"%{deger_rapor['guven']} | Deger: {deger_rapor['deger_puani']}/10", "guven_int": deger_rapor["deger_puani"]})
                    
                maclar.append({"ID": mac_id, "Lig": aktif_lig_ad, "LigYolu": aktif_yol, "EvID": ev_id, "DepID": dep_id, "State": state, "EvSkorInt": ev_s_int, "DepSkorInt": dep_s_int, "MacSecim": f"{ev_ad} vs {dep_ad}", "Fav": is_fav, "Dakika / Ceyrek": durum_gosterim, "Ev Sahibi": ev_ad, "Canli Skor": skor_gosterim, "Deplasman": dep_ad, "IY / Ceyrek Skorlari": iy_ceyrek_str, "Ev Form": ev_rec, "Dep Form": dep_rec, "Hizli AI Ozet": ozet_tahmin, "Canli Firsat": canli_firsat_etiketi_uret(spor, state, durum_detay, ev_s_int, dep_s_int, ev_rec, dep_rec)})
            except Exception:
                continue

    if maclar:
        en_iyi_kartlar = sorted(banko_havuzu, key=lambda x: x["guven_int"], reverse=True)[:3]
        if en_iyi_kartlar:
         st.subheader(f"{lig} | AI Bas Analist & Canli Istihbarat Onerileri")
         cols = st.columns(len(en_iyi_kartlar))
         for i, k in enumerate(en_iyi_kartlar):
             with cols[i].container(border=True):
                 st.markdown(f"**🏆 {k['mac']}**")
                 st.caption(f"Lig: {k['lig']} | {k['guven']}")
                 ai_rapor = beyin.ai_karar_ve_onay(spor, k["lig"], k["ev"], k["dep"], k["ozet"])
                 st.info(ai_rapor if ai_rapor else k["ozet"])

        st.subheader(f"{lig} | Canli Skor, IY / Ceyrek Detaylari ve AI Analiz")
        df_ham = pd.DataFrame(maclar)
        gizlenecek = ["ID", "LigYolu", "EvID", "DepID", "State", "EvSkorInt", "DepSkorInt", "MacSecim", "Fav"]
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
        piyasa_notu = ""
        try:
            if yol != "euroleague_resmi" and "/" in yol:
                p_json = requests.get(f"{url_basi}{yol}/summary?event={satir['ID']}", headers=basliklar, timeout=5).json()
                pick = p_json.get("pickcenter", [])
                for p in pick[:1]:
                    ou_val = p.get("overUnder", "")
                    det_val = p.get("details", "")
                    
                    if ou_val or det_val:
                        piyasa_notu = f"Piyasa Baremi: {ou_val} | Handikap: {det_val}"
                        st.info(f"💰 Gercek Bahis Piyasasi Cizgisi -> Alt/Ust Baremi: **{ou_val}** | Favori/Handikap: **{det_val}**")
        except Exception:
            pass
        ev_kadro, dep_kadro, ev_eksikler, dep_eksikler, kaynak = ai_kadro_ve_eksik_getir(
            yol, satir["ID"], satir["EvID"], satir["DepID"], spor
        )
        koc_etkisi_metni, momentum_etkisi, _ = koc_ve_rotasyon_etkisi_getir(
            yol, satir["ID"], satir["EvID"], satir["DepID"], spor, satir["Ev Sahibi"], satir["Deplasman"]
        )
        ev_sakat_puan, ev_yildiz_eksikler = sakatlik_etki_hesapla(ev_eksikler)
        dep_sakat_puan, dep_yildiz_eksikler = sakatlik_etki_hesapla(dep_eksikler)
        if ev_yildiz_eksikler:
            st.error(f"⚠️ KRITIK YILDIZ EKSIK ALARMI ({satir['Ev Sahibi']}): {', '.join(ev_yildiz_eksikler)} — Guven orani dusuruldu!")
        if dep_yildiz_eksikler:
            st.error(f"⚠️ KRITIK YILDIZ EKSIK ALARMI ({satir['Deplasman']}): {', '.join(dep_yildiz_eksikler)} — Guven orani dusuruldu!")
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
                saha_bilgi = canli_oyuncu_ve_olay_cek(satir.get("MacID", satir.get("ID", "")), satir.get("LigYolu", ""), spor)
            zengin_durum = f"{satir.get('Dakika / Ceyrek', '')} | Skor: {satir.get('Canli Skor', '')} | Periyotlar: {satir.get('IY / Ceyrek Skorlari', '')} | Taktik: {koc_etkisi_metni} | Canli Saha: {saha_bilgi}"
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
                tablo_en_iyi = next(iter(detayli_tahmin_satirlari)).get("AI Tahmin Secenegi", "")
                st.warning(f"⚡ *NET ÖZET KARAR:* Matematiksel Tablon *{tablo_en_iyi}* diyor — Yapay Zeka ise yukarıdaki *NOKTA ATIŞI ANA KARAR* satırını öneriyor. İkisi aynı yönüyse *GÜÇLÜ SİNYAL, zıtsa **PAS GEÇ!*") 
        if h2h_verisi:
            st.info("*Son Kafa Kafaya (H2H) Maclar:* " + "  |  ".join(h2h_verisi))
        st.info(f"*Kadro Kaynagi:* {kaynak}")
        st.write(f"*{satir['Ev Sahibi']} Eksikler:*", ", ".join(ev_eksikler) if ev_eksikler else "Bildirilen eksik yok")
        st.write(f"*{satir['Ev Sahibi']} Muhtemel Kadro:*", ", ".join(ev_kadro) if ev_kadro else "Lig verisi bekleniyor")
        st.write(f"*{satir['Deplasman']} Eksikler:*", ", ".join(dep_eksikler) if dep_eksikler else "Bildirilen eksik yok")
        st.write(f"*{satir['Deplasman']} Muhtemel Kadro:*", ", ".join(dep_kadro) if dep_kadro else "Lig verisi bekleniyor")
        st.divider()
        st.subheader(f"📊 {satir['Ev Sahibi']} vs {satir['Deplasman']} | Guc & Tempo Karsilastirma Grafigi")
        try:
            ev_p_g = list(int(x) for x in satir["Ev Form"].split("-"))
            dep_p_g = list(int(x) for x in satir["Dep Form"].split("-"))
            ev_oran = round((ev_p_g.pop(0) / (sum(ev_p_g) if sum(ev_p_g) > 0 else 1)) * 100, 1)
            dep_oran = round((dep_p_g.pop(0) / (sum(dep_p_g) if sum(dep_p_g) > 0 else 1)) * 100, 1)
            taban_skor = 80.0 if spor == "Basketbol" else 1.4
            ev_beklenen = round(taban_skor * (0.85 + (ev_oran / 200)), 1)
            dep_beklenen = round(taban_skor * (0.85 + (dep_oran / 200)), 1)

            grafik_df = pd.DataFrame(
                {
                    satir["Ev Sahibi"]: (ev_oran, ev_beklenen),
                    satir["Deplasman"]: (dep_oran, dep_beklenen),
                },
                index=("Galibiyet Yuzdesi (%)", "Beklenen Skor / Tempo"),
            )
            st.bar_chart(grafik_df, use_container_width=True)
        except Exception:
            pass
    else:
        st.warning("Bu tarihte mac bulunamadi. Sol menuden tarihi degistirin.")

    

if otomatik_yenile:
    time.sleep(30)
    st.rerun()
