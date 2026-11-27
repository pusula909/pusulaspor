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
                            _q_ozet = ", ".join(f"{a.get('displayValue','0')}-{b.get('displayValue','0')}" for a, b in zip(ceyrekler_ev, ceyrekler_dep))
                        if st_code == "in":
                            aktif_q = len(ceyrekler_ev) if ceyrekler_ev else 1
                            _el_saat = str(lj.get("Clock") or lj.get("RemainingTime") or "").strip()
                            detay = f"Q{aktif_q}" + (f" ({_el_saat})" if _el_saat else "") + (f" | Çeyrekler: {_q_ozet}" if _q_ozet else "")
                        elif st_code == "post" and _q_ozet:
                            detay = f"Bitti | Çeyrekler: {_q_ozet}"
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
                        "date": (datetime.strptime(f"{d_raw} {s_time}", "%b %d, %Y %H:%M") - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
@st.cache_resource
def _kalici_kupon_havuzu():
    return {"liste": list(), "bildirim_atildi": False}

_k_havuz = _kalici_kupon_havuzu()
if "kupon_listesi" not in st.session_state:
    st.session_state.kupon_listesi = _k_havuz["liste"]
if "kupon_bildirim_gonderildi" not in st.session_state:
    st.session_state.kupon_bildirim_gonderildi = _k_havuz["bildirim_atildi"]
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
        "Sampiyonlar Ligi": "soccer/uefa.champions",
        "Avrupa Ligi": "soccer/uefa.europa",
        "Konferans Ligi": "soccer/uefa.europa.conf",
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
otomatik_yenile = st.sidebar.checkbox("Canli Otomatik Yenileme & Alarm (30 sn)", value=True)

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
        _toplam_m = len(kupon_tablosu)
        _gelen_m = sum(1 for r_k in kupon_tablosu if "TUTTU" in str(r_k.get("Durum", "")))
        _onde_m = sum(1 for r_k in kupon_tablosu if "Su An Tutuyor" in str(r_k.get("Durum", "")))
        _yatan_m = sum(1 for r_k in kupon_tablosu if "YATTI" in str(r_k.get("Durum", "")))
        _bekleyen_m = _toplam_m - (_gelen_m + _onde_m + _yatan_m)
        _ilerleme_yuzde = int(round(((_gelen_m * 1.0 + _onde_m * 0.65 + _bekleyen_m * 0.35) / max(1, _toplam_m)) * 100)) if _yatan_m == 0 else 0

        if _yatan_m > 0:
            st.error(f"❌ **KUPON KAYBETTİ!** ({_yatan_m} maç yattı | Gelen: {_gelen_m}/{_toplam_m} | İlerleme: %0)")
            st.progress(0)
        elif hepsi_bitti_ve_tuttu and _toplam_m > 0:
            st.success(f"🏆 **TEBRİKLER, KUPON KAZANDI!** ({_gelen_m}/{_toplam_m} Maç Tamamlandı | Başarı: %100)")
            st.progress(100)
        else:
            st.info(f"📊 **Kupon Canlı İlerlemesi: %{_ilerleme_yuzde}** — ✅ Gelen: **{_gelen_m}/{_toplam_m}** | 🟢 Şu An Tutan: **{_onde_m}** | ⏳ Bekleyen: **{_bekleyen_m}**")
            st.progress(max(0, min(100, _ilerleme_yuzde)))

        if not _k_havuz.get("bildirim_atildi", False) and not st.session_state.get("kupon_bildirim_gonderildi", False) and _toplam_m > 0:
            if _yatan_m > 0 or hepsi_bitti_ve_tuttu:
                _sonuc_baslik = "✅ KUPON KAZANDI!" if (hepsi_bitti_ve_tuttu and _yatan_m == 0) else "❌ KUPON KAYBETTİ!"
                _ozet_satirlar = list((f"{_sonuc_baslik} (Gelen: {_gelen_m}/{_toplam_m})", "-------------------------"))
                for _rm in kupon_tablosu:
                    _ozet_satirlar.append(f"• {_rm.get('Mac')} | {_rm.get('Oynanan')} -> {_rm.get('Skor')} ({_rm.get('Durum')})")
                telegram_mesaj_gonder(tg_token, tg_chat_id, "\n".join(_ozet_satirlar))
                st.session_state.kupon_bildirim_gonderildi = True
                _k_havuz["bildirim_atildi"] = True

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
            _k_havuz["bildirim_atildi"] = False
            st.session_state.kupon_bildirim_gonderildi = False
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
            _k_havuz["liste"].clear()
            _k_havuz["bildirim_atildi"] = False
            st.session_state.kupon_listesi = _k_havuz["liste"]
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
        st.divider()
    st.subheader("🎯 Kombine Toplam Gol / Sayı Havuzu (Manuel Barem & AI İhtimal Analizi)")
    st.caption("Seçtiğiniz maçların toplam gol veya toplam sayı havuzu için barem ve oranı manuel girin; AI istatistikleri araştırıp gelme ihtimalini hesaplasın ve canlı takip etsin.")

    @st.cache_resource
    def _kalici_havuz_deposu():
        return {"aktif": False, "maclar": list(), "barem": 0.0, "tercih": "ALT", "oran": 1.85, "ai_rapor": "", "bildirim_atildi": False}

    _hv_dep = _kalici_havuz_deposu()
    @st.cache_data(ttl=120, show_spinner=False)
    def _havuz_tum_bulten_cek(t_str):
        _tumu = {}
        try:
            _dt_ana = datetime.strptime(str(t_str), "%Y%m%d")
            _gunler = ((_dt_ana - timedelta(days=1)).strftime("%Y%m%d"), t_str, (_dt_ana + timedelta(days=1)).strftime("%Y%m%d"))
        except Exception:
            _gunler = (t_str,)

        for _g_str in _gunler:
            for _sp_k, _lig_dict in TUM_LIGLER.items():
                for _lg_k, _yl_k in _lig_dict.items():
                    if "sampiyonlar" in _lg_k.lower() or "avrupa ligi" in _lg_k.lower() or "konferans" in _lg_k.lower():
                        _kat = "Futbol - Avrupa Kupaları"
                    elif _sp_k == "Futbol":
                        _kat = "Futbol - Normal Sezon Ligleri"
                    elif "nba" in _lg_k.lower():
                        _kat = "Basketbol - NBA"
                    else:
                        _kat = "Basketbol - EuroLeague & Diğer"
                    try:
                        _rp = _el_get(_g_str) if _yl_k == "euroleague_resmi" else requests.get(f"{url_basi}{_yl_k}/scoreboard?dates={_g_str}", headers=basliklar, timeout=5).json()
                        for _ev_p in _rp.get("events", list()):
                            _cp = next(iter(_ev_p.get("competitions") or ()), {})
                            _tkp = _cp.get("competitors", list())
                            if len(_tkp) >= 2:
                                _eh = next((t.get("team", {}).get("displayName", "Ev") for t in _tkp if t.get("homeAway") == "home"), "Ev")
                                _da = next((t.get("team", {}).get("displayName", "Dep") for t in _tkp if t.get("homeAway") == "away"), "Dep")
                                _etk = f"[{_lg_k}] {_eh} vs {_da}"
                                if _etk not in _tumu:
                                    _tumu[_etk] = {"id": _ev_p.get("id"), "yol": _yl_k, "spor": _sp_k, "kat": _kat, "tarih_g": _g_str, "ev": _eh, "dep": _da, "etiket": _etk}
                    except Exception:
                        continue
        return _tumu

    _hv_map = _havuz_tum_bulten_cek(tarih)
    if not _hv_map:
        _hv_map = {m.get("etiket", ""): {**m, "kat": m.get("spor", "Tümü"), "tarih_g": tarih} for m in k_maclar_veri if m.get("etiket")}

    _hf1, _hf2 = st.columns([1.2, 1.8])
    _hv_kat_sec = _hf1.selectbox(
        "Kategori Filtresi",
        ["Tümü (Bütün Maçlar)", "Basketbol - NBA", "Basketbol - EuroLeague & Diğer", "Futbol - Avrupa Kupaları", "Futbol - Normal Sezon Ligleri"],
        key="hv_kat_filtre"
    )
    def _tr_norm(metin):
        s = str(metin or "").lower()
        for a, b in (("ó", "o"), ("ą", "a"), ("ć", "c"), ("ę", "e"), ("ł", "l"), ("ń", "n"), ("ś", "s"), ("ź", "z"), ("ż", "z"), ("ç", "c"), ("ğ", "g"), ("ı", "i"), ("ö", "o"), ("ş", "s"), ("ü", "u"), ("é", "e"), ("á", "a"), ("í", "i"), ("ú", "u"), ("ñ", "n")):
            s = s.replace(a, b)
        return s

    _hv_arama = _tr_norm(_hf2.text_input("🔎 Takım veya Maç Ara (Dünyadaki Tüm Ligler - Örn: Rakow, Galatasaray, Boca, Lakers...)", "").strip())
    if len(_hv_arama) >= 3:
        try:
            _g_hdr = {"User-Agent": "Mozilla/5.0"}
            _sdb = "https:" + chr(47) + chr(47) + "www" + "." + "thesportsdb" + "." + "com" + chr(47) + "api" + chr(47) + "v1" + chr(47) + "json" + chr(47) + "3" + chr(47)
            _sr = requests.get(f"{_sdb}searchteams.php", params={"t": _hv_arama}, headers=_g_hdr, timeout=5)
            if _sr.status_code == 200:
                for _stm in (_sr.json().get("teams") or list())[:5]:
                    _tid = str(_stm.get("idTeam") or "")
                    _tspor = "Basketbol" if "basketball" in str(_stm.get("strSport") or "").lower() else "Futbol"
                    _tlig = str(_stm.get("strLeague") or "Dunya Ligi")
                    if _tid:
                        _er = requests.get(f"{_sdb}eventsnext.php", params={"id": _tid}, headers=_g_hdr, timeout=5)
                        if _er.status_code == 200:
                            for _sev in (_er.json().get("events") or list())[:2]:
                                _sev_ad = str(_sev.get("strEvent") or "")
                                _sev_tar = str(_sev.get("dateEvent") or "")
                                _getk = f"[{_tlig} | {_sev_tar}] {_sev_ad}"
                                if _sev_ad and _getk not in _hv_map:
                                    _hv_map[_getk] = {"id": str(_sev.get("idEvent") or ""), "yol": "sdb", "spor": _tspor, "kat": "Dünya Geneli", "tarih_g": _sev_tar}
        except Exception:
            pass

    _tum_mac_secenekleri = list()
    for _etk_item, _obj_item in _hv_map.items():
        if _hv_kat_sec != "Tümü (Bütün Maçlar)" and _obj_item.get("kat") != _hv_kat_sec and len(_hv_arama) < 3:
            continue
        if _hv_arama and _hv_arama not in _tr_norm(_etk_item):
            continue
        _tum_mac_secenekleri.append(_etk_item)

    if "sepet" not in _hv_dep:
        _hv_dep["sepet"] = list(_hv_dep.get("maclar", list()))

    _hs1, _hs2 = st.columns([2.2, 1.0])
    _hv_aday_mac = _hs1.selectbox(
        f"Bulunan Maçlar ({len(_tum_mac_secenekleri)} maç)",
        options=_tum_mac_secenekleri if _tum_mac_secenekleri else ["Maç bulunamadı"],
        key="hv_aday_secim"
    )
    _hs2.write("")
    _hs2.write("")
    if _hs2.button("➕ Havuz Sepetine Ekle", use_container_width=True):
        if _hv_aday_mac in _hv_map and _hv_aday_mac not in _hv_dep["sepet"]:
            _hv_dep["sepet"].append(_hv_aday_mac)
            st.rerun()

    _hv_secilen_maclar = list(_hv_dep["sepet"])
    if _hv_secilen_maclar:
        st.markdown(f"**🛒 Havuz Sepetinizdeki Maçlar ({len(_hv_secilen_maclar)} maç eklendi):**")
        for _idx_sp, _m_sp in enumerate(_hv_secilen_maclar):
            _sc1, _sc2 = st.columns([4.5, 0.8])
            _sc1.write(f"{_idx_sp + 1}. {_m_sp}")
            if _sc2.button("❌ Çıkar", key=f"hv_sil_{_idx_sp}_{hash(_m_sp)}"):
                _hv_dep["sepet"].remove(_m_sp)
                st.rerun()
    else:
        st.caption("🛒 Havuz sepetiniz şu an boş. Yukarıdan takım arayıp '➕ Havuz Sepetine Ekle' butonuna basın.")
    _hc1, _hc2, _hc3 = st.columns(3)
    _hv_barem = _hc1.number_input("Toplam Havuz Baremi (Örn: 731.5 veya 12.5)", min_value=0.5, max_value=2500.0, value=float(_hv_dep.get("barem") or 731.5), step=0.5, key="hv_barem_in")
    _hv_tercih = _hc2.selectbox("Tercih", ["ALT", "ÜST"], index=0 if _hv_dep.get("tercih", "ALT") == "ALT" else 1, key="hv_tercih_in")
    _hv_oran = _hc3.number_input("Büro Oranı (Manuel)", min_value=1.01, max_value=100.0, value=float(_hv_dep.get("oran") or 1.85), step=0.05, key="hv_oran_in")

    def _havuz_canli_skor_cek(mac_obj):
        try:
            _y_h = mac_obj.get("yol", "")
            _id_h = str(mac_obj.get("id", ""))
            _dt_ref = datetime.strptime(str(tarih).replace("-", "")[:8], "%Y%m%d")
            _tar_liste = [(_dt_ref - timedelta(days=1)).strftime("%Y%m%d"), tarih, (_dt_ref + timedelta(days=1)).strftime("%Y%m%d")]
            _tum_evler = list()
            for _tg_x in _tar_liste:
                _r_x = _el_get(_tg_x) if _y_h == "euroleague_resmi" else requests.get(f"{url_basi}{_y_h}/scoreboard?dates={_tg_x}", headers=basliklar, timeout=6).json()
                _tum_evler.extend(_r_x.get("events", list()))
            for _ev_h in _tum_evler:
                if str(_ev_h.get("id", "")) == _id_h:
                    _c_h = next(iter(_ev_h.get("competitions") or ()), {})
                    _t_h = _c_h.get("competitors", list())
                    _s_top = sum(int(t.get("score", 0) or 0) for t in _t_h if str(t.get("score", "")).isdigit())
                    _sk_yazi = " - ".join(str(t.get("score", "0")) for t in _t_h[:2])
                    _st_h = ((_c_h.get("status") or {}).get("type") or {}).get("state", "pre")
                    _det_h = ((_c_h.get("status") or {}).get("type") or {}).get("shortDetail", "-")
                    _clk_h = str((_c_h.get("status") or {}).get("displayClock") or "").strip()
                    _per_h = (_c_h.get("status") or {}).get("period", 0)
                    _tr_saat = "-"
                    try:
                        _raw_dt = str(_ev_h.get("date") or _ev_h.get("startDate") or _c_h.get("date") or _c_h.get("startDate") or "")
                        if _raw_dt:
                            _utc_dt = datetime.fromisoformat(_raw_dt.replace("Z", "+00:00"))
                            _tr_saat = (_utc_dt + timedelta(hours=3)).strftime("%d.%m %H:%M")
                    except Exception:
                        pass
                    _lin_list = list()
                    if len(_t_h) >= 2:
                        _l1 = _t_h[0].get("linescores", list())
                        _l2 = _t_h[1].get("linescores", list())
                        _lin_list = [f"{int(float(a.get('value',0)))}-{int(float(b.get('value',0)))}" for a, b in zip(_l1, _l2)]
                    _lin_str = f" | Periyotlar: {', '.join(_lin_list)}" if _lin_list else ""
                    if _st_h == "pre":
                        _sure_bilgi = f"Başlangıç: {_tr_saat}"
                    elif _st_h == "post":
                        _sure_bilgi = f"Bitti ({_tr_saat}){_lin_str}"
                    else:
                        _sure_bilgi = f"{_det_h}" + (f" [{_clk_h}]" if (_clk_h and _clk_h not in _det_h) else "") + _lin_str
                    return _sk_yazi, _s_top, (_st_h == "post"), _sure_bilgi
        except Exception as _ex_hv:
            return "0 - 0", 0, False, f"Hata: {str(_ex_hv)[:45]}"
    _hb1, _hb2 = st.columns(2)
    if _hb1.button("🔍 AI İhtimal Analizi Yap & Canlı Takibi Başlat", use_container_width=True):
        if len(_hv_secilen_maclar) < 2:
            st.warning("Lütfen havuz analizi için en az 2 maç seçin.")
        else:
            _secili_objeler = [_hv_map[m] for m in _hv_secilen_maclar if m in _hv_map]
            if len(_secili_objeler) < 2:
                st.warning("Sepetteki maçların tarihi geçmiş olabilir. Lütfen '🗑️ Havuzu Temizle' butonuna basıp güncel bültenden en az 2 maç ekleyin.")
                st.stop()
            _mac_detay_list = list()
            for _mo in _secili_objeler:
                _sy, _st_top, _, _dt = _havuz_canli_skor_cek(_mo)
                _gercek_veri_not = ""
                try:
                    _y_oz = str(_mo.get("yol", ""))
                    _id_oz = str(_mo.get("id", ""))
                    if _y_oz == "euroleague_resmi":
                        _el_st = requests.get("https://euroleague.net", timeout=4).json()
                        _el_not = list()
                        for _grp in (_el_st.get("standings") or _el_st.get("teams") or list()):
                            _tm_el = ((_grp.get("club") or _grp.get("team") or {}).get("name") or "").lower()
                            if _tm_el and (_tm_el in _mo.get("ev", "").lower() or _tm_el in _mo.get("dep", "").lower()):
                                _gp = max(1, int(_grp.get("gamesPlayed") or _grp.get("played") or 1))
                                _pf = round(float(_grp.get("pointsFor") or 0) / _gp, 1)
                                _pa = round(float(_grp.get("pointsAgainst") or 0) / _gp, 1)
                                if _pf > 0:
                                    _el_not.append(f"{_tm_el.title()} Attığı:{_pf} Yediği:{_pa}")
                        if _el_not:
                            _gercek_veri_not = f" | EL Sezon Ort: {', '.join(_el_not)}"
                    elif _y_oz and _id_oz:
                        _sum_j = requests.get(f"{url_basi}{_y_oz}/summary?event={_id_oz}", headers=basliklar, timeout=5).json()
                        _st_oz = list()
                        for _bt in ((_sum_j.get("boxscore") or {}).get("teams") or list()):
                            _t_nm = (_bt.get("team") or {}).get("abbreviation", "")
                            _ppg = next((s.get("displayValue") for s in _bt.get("statistics", list()) if s.get("name") in ("avgPoints", "points", "goalsFor")), "")
                            if _t_nm and _ppg:
                                _st_oz.append(f"{_t_nm} Ort:{_ppg}")
                        for _fm in (_sum_j.get("form") or list()):
                            _f_tm = (_fm.get("team") or {}).get("abbreviation", "")
                            _evs = _fm.get("events", list())[:5]
                            if _f_tm and _evs:
                                _gol_top = sum(int(str(e.get("homeTeamScore", 0))) + int(str(e.get("awayTeamScore", 0))) for e in _evs if str(e.get("homeTeamScore", "")).isdigit())
                                _st_oz.append(f"{_f_tm} Son{len(_evs)}MacOrt:{round(_gol_top/len(_evs), 2)}")
                        _inj_list = list()
                        for _ij_grp in (_sum_j.get("injuries") or list()):
                            _ij_tm = (_ij_grp.get("team") or {}).get("abbreviation", "")
                            for _ij_p in _ij_grp.get("injuries", list())[:3]:
                                _ath = (_ij_p.get("athlete") or {}).get("shortName", "")
                                _ist = _ij_p.get("status", "")
                                if _ath:
                                    _inj_list.append(f"{_ij_tm}:{_ath}({_ist})")
                        if _st_oz or _inj_list:
                            _gercek_veri_not = f" | Gerçek Veri: {', '.join(_st_oz)} | Eksikler: {', '.join(_inj_list) if _inj_list else 'Tam kadro'}"
                except Exception:
                    pass
                import hakem_analiz as _hk_mod
                _gercek_veri_not += _hk_mod.mac_hakem_verisi_cek(url_basi, str(_mo.get("yol", "")), str(_mo.get("id", "")), basliklar)
                _mac_detay_list.append(f"{_mo.get('etiket')} (Skor: {_sy}, Durum: {_dt}{_gercek_veri_not})")
                _mac_basi_ort = round(_hv_barem / max(1, len(_secili_objeler)), 2)
            _anlik_top_b = 0
            _sure_top_b = 0.0
            _proj_top_b = 0.0
            for _mo_p in _secili_objeler:
                _sk_p, _top_p, _bit_p, _det_p = _havuz_canli_skor_cek(_mo_p)
                _anlik_top_b += _top_p
                _yol_p = str(_mo_p.get("yol", ""))
                _sp_p = str(_mo_p.get("spor", "Basketbol"))
                _lig_ort_p = 225.5 if "nba" in _yol_p else (164.5 if _sp_p == "Basketbol" else 2.75)
                if _bit_p:
                    _sure_top_b += 1.0
                    _proj_top_b += _top_p
                elif _top_p > 0:
                    _du_p = _det_p.upper()
                    _or_p = 0.88 if ("Q4" in _du_p or "OT" in _du_p or "UZ" in _du_p) else (0.65 if "Q3" in _du_p else (0.50 if ("DEVRE" in _du_p or "HT" in _du_p) else (0.35 if "Q2" in _du_p else (0.18 if "Q1" in _du_p else 0.50))))
                    _sure_top_b += _or_p
                    _proj_top_b += (_top_p * _or_p + _lig_ort_p * (1.0 - _or_p)) / max(0.25, _or_p) if _or_p >= 0.35 else (_top_p + _lig_ort_p * (1.0 - _or_p))
                else:
                    _proj_top_b += _lig_ort_p
            _proj_top_b = round(_proj_top_b, 1)
            _sure_yz_b = round((_sure_top_b / max(1, len(_secili_objeler))) * 100)
            _fark_b = (_hv_barem - _proj_top_b) if _hv_tercih == "ALT" else (_proj_top_b - _hv_barem)
            _olcek_b = max(4.0, _hv_barem * 0.055)
            _mat_yuzde = max(8, min(95, int(round(54 + (_fark_b / _olcek_b) * 24))))
            _ai_yorum_kisa = "Takımların sezonluk sayı/gol temposuna ve barem mesafesine göre istatistiksel takip aktif."
            if groq_api_key:
                try:
                    _p_hv = (
                        f"Secilen {len(_secili_objeler)} macin toplam skor/gol havuzu istatistik analizi:\n"
                        + "\n".join(_mac_detay_list)
                        + f"\nHedef Barem: {_hv_barem} {_hv_tercih} (Mac basi ort: {_mac_basi_ort}) | Su Anki Toplam: {_anlik_top_b} | Lig Ort Projeksiyonu: {_proj_top_b}.\n"
                        "Bu takimlarin gercek sezonluk hucum/savunma tempolarini, sakatlik/eksik durumlarini ve mevcut skorlari analiz ederek SADECE su 3 satiri yaz (baska hicbir sey yazma):\n"
                        "IHTIMAL: [25 ile 88 arasi gercekci tam sayi]\n"
                        "PROJEKSIYON: [Tahmini toplam sayi/gol ornegin 668.5]\n"
                        "YORUM: [Her macin adini tek tek yazarak kendi sakatlik ve tempo gerekcesini 1 kisa cumleyle ozetle; ornek: Orlando-Detroit: ... | Washington-Boston: ... | Denver-Dallas: ...]"
                    )
                    _q_hv = requests.post(
                        "https://" + "api" + ".groq.com" + "/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {groq_api_key}", "Content-Type": "application/json"},
                        json={"model": "openai/gpt-oss-120b", "messages": list(({"role": "user", "content": _p_hv},)), "temperature": 0.0, "seed": 42},
                        timeout=10,
                    ).json()
                    _c_hv = next(iter(_q_hv.get("choices") or ()), {})
                    _txt_hv = (_c_hv.get("message") or {}).get("content", "").strip()
                    if _txt_hv:
                        for _ln_h in _txt_hv.splitlines():
                            _ln_s = _ln_h.strip()
                            if _ln_s.upper().startswith("IHTIMAL:"):
                                _rakam_i = "".join(ch for ch in _ln_s.split(":", 1)[1] if ch.isdigit())
                                if _rakam_i:
                                    _mat_yuzde = max(15, min(92, int(_rakam_i)))
                            elif _ln_s.upper().startswith("PROJEKSIYON:"):
                                _rakam_p = "".join(ch for ch in _ln_s.split(":", 1)[1] if (ch.isdigit() or ch == "."))
                                if _rakam_p:
                                    _proj_top_b = round(float(_rakam_p), 1)
                            elif _ln_s.upper().startswith("YORUM:"):
                                _ai_yorum_kisa = _ln_s.split(":", 1)[1].strip()
                except Exception:
                    pass
            try:
                import importlib, havuz_ekstra as _hx_yor
                importlib.reload(_hx_yor)
                _mat_yuzde, _proj_top_b, _deg_etk, _yor_metin = _hx_yor.profesyonel_yorumcu_ve_suzgec(_mac_detay_list, _hv_barem, _hv_tercih, _hv_oran, beyin._ai_sor)
                _ai_yorum_kisa = f"[{_deg_etk}]\n{_yor_metin}"
            except Exception as _hx_hata:
                _ai_yorum_kisa = f"Modül Uyarı: {_hx_hata}"
            _hv_dep["baslangic_ihtimal"] = _mat_yuzde
            _hv_dep["baslangic_proj"] = _proj_top_b
            _ai_hv_sonuc = (
                f"• GELME İHTİMALİ: **%{_mat_yuzde}** (Süre İlerlemesi: %{_sure_yz_b})\n"
                f"• BEKLENEN TOPLAM PROJEKSİYON: **{_proj_top_b}** (Şu An: {_anlik_top_b} / Hedef: {_hv_barem} {_hv_tercih})\n"
                f"• AI DEĞERLENDİRME: {_ai_yorum_kisa}"
            )
            _hv_dep["aktif"] = True   
            
            _hv_dep["maclar"] = list(_hv_secilen_maclar)
            _hv_dep["objeler"] = _secili_objeler
            _hv_dep["barem"] = float(_hv_barem)
            _hv_dep["tercih"] = _hv_tercih
            _hv_dep["oran"] = float(_hv_oran)
            _hv_dep["ai_rapor"] = _ai_hv_sonuc
            _hv_dep["bildirim_atildi"] = False
            telegram_mesaj_gonder(
                tg_token,
                tg_chat_id,
                f"🎯 YENİ KOMBİNE HAVUZ TAKİBİ BAŞLADI\n• Barem: {_hv_barem} {_hv_tercih} | Oran: {_hv_oran}\n• Maç Sayısı: {len(_secili_objeler)}\n{_ai_hv_sonuc}"
            )
            st.rerun()

    if _hb2.button("🗑️ Havuzu Temizle", use_container_width=True):
        _hv_dep["aktif"] = False
        _hv_dep["maclar"] = list()
        _hv_dep["objeler"] = list()
        _hv_dep["ai_rapor"] = ""
        _hv_dep["bildirim_atildi"] = False
        st.rerun()

    if _hv_dep.get("aktif") and _hv_dep.get("objeler"):
        _anlik_toplam = 0
        _biten_havuz_mac = 0
        _hv_tablo_satir = list()
        for _mo_t in _hv_dep["objeler"]:
            _sk_str, _m_top, _bitti_mi, _dur_str = _havuz_canli_skor_cek(_mo_t)
            _anlik_toplam += _m_top
            if _bitti_mi:
                _biten_havuz_mac += 1
            _hv_tablo_satir.append({"Maç": _mo_t.get("etiket", "-"), "Saat / Süre": _dur_str, "Canlı Skor": _sk_str, "Maç Toplamı": _m_top})

        _sure_orani_top = 0.0
        _canli_proj_top = 0.0
        _bas_proj = float(_hv_dep.get("baslangic_proj") or _hv_dep["barem"])
        _mac_say_c = max(1, len(_hv_dep["objeler"]))
        _mac_basi_bas = _bas_proj / _mac_say_c
        for _mo_c in _hv_dep["objeler"]:
            _sk_c, _top_c, _bit_c, _det_c = _havuz_canli_skor_cek(_mo_c)
            if _bit_c:
                _sure_orani_top += 1.0
                _canli_proj_top += _top_c
            elif _top_c > 0:
                _d_up = _det_c.upper()
                _or_c = 0.88 if ("Q4" in _d_up or "OT" in _d_up or "UZ" in _d_up) else (0.65 if "Q3" in _d_up else (0.50 if ("DEVRE" in _d_up or "HT" in _d_up) else (0.35 if "Q2" in _d_up else (0.18 if "Q1" in _d_up else 0.50))))
                _sure_orani_top += _or_c
                _canli_proj_top += _top_c + (_mac_basi_bas * (1.0 - _or_c))
            else:
                _canli_proj_top += _mac_basi_bas
        _canli_proj_top = round(_canli_proj_top, 1)
        _genel_sure_yuzde = round((_sure_orani_top / _mac_say_c) * 100)
        _hedef_val = float(_hv_dep["barem"])
        _bas_ih = int(_hv_dep.get("baslangic_ihtimal") or 55)

        if _hv_dep["tercih"] == "ÜST":
            if _anlik_toplam > _hedef_val:
                _genel_kupon_yuzde = 100
            elif _genel_sure_yuzde == 0:
                _genel_kupon_yuzde = _bas_ih
            else:
                _fark_c = _canli_proj_top - _hedef_val
                _olcek_c = max(4.0, _hedef_val * 0.055)
                _tempo_ih = max(5, min(98, int(round(54 + (_fark_c / _olcek_c) * 24))))
                _agirlik_c = min(1.0, _genel_sure_yuzde / 75.0)
                _genel_kupon_yuzde = max(5, min(99, int(round(_bas_ih * (1.0 - _agirlik_c) + _tempo_ih * _agirlik_c))))
        else:
            if _anlik_toplam > _hedef_val:
                _genel_kupon_yuzde = 0
            elif _genel_sure_yuzde == 0:
                _genel_kupon_yuzde = _bas_ih
            else:
                _fark_c = _hedef_val - _canli_proj_top
                _olcek_c = max(4.0, _hedef_val * 0.055)
                _tempo_ih = max(5, min(98, int(round(54 + (_fark_c / _olcek_c) * 24))))
                _agirlik_c = min(1.0, _genel_sure_yuzde / 75.0)
                _genel_kupon_yuzde = max(5, min(99, int(round(_bas_ih * (1.0 - _agirlik_c) + _tempo_ih * _agirlik_c))))
        with st.container(border=True):
            _ai_kisa_not = _hv_dep.get("ai_rapor", "").split("DEĞERLENDİRME:").pop(-1).strip() if "DEĞERLENDİRME:" in _hv_dep.get("ai_rapor", "") else ""
            st.info(
                f"**🤖 Canlı Havuz Durumu ({_hv_dep['barem']} {_hv_dep['tercih']} | Oran: {_hv_dep['oran']}):**\n\n"
                f"• **GELME İHTİMALİ / İLERLEME:** **%{_genel_kupon_yuzde}** (Süre İlerlemesi: %{_genel_sure_yuzde})\n"
                f"• **BEKLENEN PROJEKSİYON:** **{_canli_proj_top}** (Şu An: {_anlik_toplam} / Hedef: {_hv_dep['barem']} {_hv_tercih})\n"
                + (f"• **AI DEĞERLENDİRME:** {_ai_kisa_not}" if _ai_kisa_not else "")
            )
            st.dataframe(pd.DataFrame(_hv_tablo_satir), use_container_width=True, hide_index=True)
            import havuz_ekstra as _hx
            st.caption(_hx.kalan_ortalama_bilgisi(_hv_dep["objeler"], _havuz_canli_skor_cek, _hv_dep["barem"], _hv_dep["tercih"]))
                
            
            _hedef_b = float(_hv_dep["barem"])
            _sec_t = _hv_dep["tercih"]
            _kalan_fark = round(_hedef_b - _anlik_toplam, 1)
            _tamam_mi = (_biten_havuz_mac == len(_hv_dep["objeler"]))

            if _sec_t == "ALT" and _anlik_toplam > _hedef_b:
                st.error(f"❌ **HAVUZ KAYBETTİ!** Toplam Skor ({_anlik_toplam}) sınırı ({_hedef_b} ALT) aştı!")
                st.progress(0)
                if not _hv_dep.get("bildirim_atildi"):
                    telegram_mesaj_gonder(tg_token, tg_chat_id, f"❌ HAVUZ KAYBETTİ! ({_hedef_b} ALT | Gerçekleşen Toplam: {_anlik_toplam})")
                    _hv_dep["bildirim_atildi"] = True
            elif _sec_t == "ÜST" and _anlik_toplam > _hedef_b:
                st.success(f"🏆 **HAVUZ ŞİMDİDEN KAZANDI!** Toplam Skor ({_anlik_toplam}) sınırı ({_hedef_b} ÜST) geçti!")
                st.progress(100)
                if not _hv_dep.get("bildirim_atildi"):
                    telegram_mesaj_gonder(tg_token, tg_chat_id, f"✅ HAVUZ KAZANDI! ({_hedef_b} ÜST | Gerçekleşen Toplam: {_anlik_toplam})")
                    _hv_dep["bildirim_atildi"] = True
            elif _tamam_mi:
                _kazandi_son = (_anlik_toplam < _hedef_b) if _sec_t == "ALT" else (_anlik_toplam > _hedef_b)
                if _kazandi_son:
                    st.success(f"🏆 **TEBRİKLER, HAVUZ KAZANDI!** ({_hedef_b} {_sec_t} | Final Toplam: {_anlik_toplam} | Oran: {_hv_dep['oran']})")
                    st.progress(100)
                else:
                    st.error(f"❌ **HAVUZ KAYBETTİ!** ({_hedef_b} {_sec_t} | Final Toplam: {_anlik_toplam})")
                    st.progress(0)
                if not _hv_dep.get("bildirim_atildi"):
                    _son_etiket = "✅ HAVUZ KAZANDI!" if _kazandi_son else "❌ HAVUZ KAYBETTİ!"
                    telegram_mesaj_gonder(tg_token, tg_chat_id, f"{_son_etiket} ({_hedef_b} {_sec_t} | Final Toplam: {_anlik_toplam} | Oran: {_hv_dep['oran']})")
                    _hv_dep["bildirim_atildi"] = True
            
            elif _sec_t == "ÜST" and _anlik_toplam > _hedef_b:
                st.success(f"🏆 **HAVUZ ŞİMDİDEN KAZANDI!** Toplam Skor ({_anlik_toplam}) sınırı ({_hedef_b} ÜST) geçti!")
                st.progress(100)
                if not _hv_dep.get("bildirim_atildi"):
                    telegram_mesaj_gonder(tg_token, tg_chat_id, f"✅ HAVUZ KAZANDI! ({_hedef_b} ÜST | Gerçekleşen Toplam: {_anlik_toplam})")
                    _hv_dep["bildirim_atildi"] = True
            elif _tamam_mi:
                _kazandi_son = (_anlik_toplam < _hedef_b) if _sec_t == "ALT" else (_anlik_toplam > _hedef_b)
                if _kazandi_son:
                    st.success(f"🏆 **TEBRİKLER, HAVUZ KAZANDI!** ({_hedef_b} {_sec_t} | Final Toplam: {_anlik_toplam} | Oran: {_hv_dep['oran']})")
                    st.progress(100)
                else:
                    st.error(f"❌ **HAVUZ KAYBETTİ!** ({_hedef_b} {_sec_t} | Final Toplam: {_anlik_toplam})")
                    st.progress(0)
                if not _hv_dep.get("bildirim_atildi"):
                    _son_etiket = "✅ HAVUZ KAZANDI!" if _kazandi_son else "❌ HAVUZ KAYBETTİ!"
                    telegram_mesaj_gonder(tg_token, tg_chat_id, f"{_son_etiket} ({_hedef_b} {_sec_t} | Final Toplam: {_anlik_toplam} | Oran: {_hv_dep['oran']})")
                    _hv_dep["bildirim_atildi"] = True
            else:
                _doluluk = int(min(100, round((_anlik_toplam / max(1.0, _hedef_b)) * 100)))
                st.info(f"📊 **Anlık Havuz Toplamı: {_anlik_toplam} / {_hedef_b} {_sec_t}** | Kalan Pay: **{_kalan_fark}** | Biten Maç: **{_biten_havuz_mac}/{len(_hv_dep['maclar'])}**")
                st.progress(_doluluk)
            import havuz_ekstra as _hx2
        _hx2.kasa_panosu_ciz(_anlik_toplam, _hedef_b, _sec_t, _hv_dep.get("oran", 1.5), _tamam_mi)    
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
                ozet_tahmin = ""  
                if state in ("pre", "in"):
                    deger_rapor = beyin.mac_deger_analizi(spor, aktif_lig_ad, ev_ad, dep_ad, ev_rec, dep_rec, state=state)
                    try:
                        import mimari_5katman as _m5
                        _m5_sonuc = _m5.bes_katman_analiz(spor, aktif_lig_ad, ev_ad, dep_ad, ev_rec, dep_rec, state, ev_s_int, dep_s_int, durum_detay, st.secrets.get("ODDS_API_KEY", ""))
                        deger_rapor.update(_m5_sonuc)
                        ozet_tahmin = _m5_sonuc["ozet_satir"]
                    except Exception as _m5_err:
                        ozet_tahmin = f"M5 Hata: {_m5_err}"
                 
                    if not deger_rapor["tuzak_notu"]:
                        banko_havuzu.append({"mac": f"{ev_ad} - {dep_ad}", "lig": aktif_lig_ad, "ev": ev_ad, "dep": dep_ad, "ozet": f"{deger_rapor['ana_tercih']} | {deger_rapor['barem_tercih']} | Deger: {deger_rapor['deger_puani']}/10", "guven": f"%{deger_rapor['guven']} | Deger: {deger_rapor['deger_puani']}/10", "guven_int": deger_rapor["deger_puani"]})
                    
                maclar.append({"ID": mac_id, "Lig": aktif_lig_ad, "LigYolu": aktif_yol, "EvID": ev_id, "DepID": dep_id, "State": state, "EvSkorInt": ev_s_int, "DepSkorInt": dep_s_int, "MacSecim": f"{ev_ad} vs {dep_ad}", "Fav": is_fav, "Dakika / Ceyrek": durum_gosterim, "Ev Sahibi": ev_ad, "Canli Skor": skor_gosterim, "Deplasman": dep_ad, "IY / Ceyrek Skorlari": iy_ceyrek_str, "Ev Form": ev_rec, "Dep Form": dep_rec, "Hizli AI Ozet": ozet_tahmin, "Canli Firsat": canli_firsat_etiketi_uret(spor, state, durum_detay, ev_s_int, dep_s_int, ev_rec, dep_rec)})
                if state in ("pre", "in") and isinstance(deger_rapor, dict):
                maclar[-1].update({"🎯 Karar": deger_rapor.get("karar_etiket", "—"), "📌 Tercih": deger_rapor.get("ana_tercih", "—"), "📊 İhtimal & Oran": deger_rapor.get("oran_sutun", "—"), "💎 Değer (EV)": deger_rapor.get("ev_sutun", "—"), "⚖️ Alt / Üst Barem": f"{deger_rapor.get('barem_tercih', '—')} (%{deger_rapor.get('barem_guven', 0)})"})
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
                 ai_rapor = beyin.ai_karar_ve_onay(spor, k["lig"], k["ev"], k["dep"], k["ozet"], k.get("saha", ""), yol=k.get("yol", yol), event_id=str(k.get("id", "")))
                 st.info(ai_rapor if ai_rapor else k["ozet"])

        st.subheader(f"{lig} | Canli Skor, IY / Ceyrek Detaylari ve AI Analiz")
        df_ham = pd.DataFrame(maclar)
        gizlenecek = ["ID", "LigYolu", "EvID", "DepID", "State", "EvSkorInt", "DepSkorInt", "MacSecim", "Hizli AI Ozet"]
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
        try:
            _ev_k = str(satir.get("Ev Sahibi", ""))
            _dep_k = str(satir.get("Deplasman", ""))
            _ozet_k = str(satir.get("Hizli AI Ozet", ""))
            _mb_tercih = "MS 1" if "MS 1" in _ozet_k else ("MS 2" if "MS 2" in _ozet_k else ("MS X" if "MS X" in _ozet_k else "1X / Dengeli"))
            _mb_guv = int(satir.get("En Guclu Guven", 65) or 65)

            @st.cache_data(ttl=300, show_spinner=False)
            def _konsey_oyu_al(motor_adi, ev_isim, dep_isim, lig_isim, ozet_veri, piyasa_veri):
                p_metin = (
                    f"Mac: {ev_isim} vs {dep_isim} ({lig_isim}). "
                    f"Istatistik Ozeti: {ozet_veri}. {piyasa_veri}. "
                    "Bu mac icin SADECE tek satir su formatta cevap ver: TERCIH: [MS 1 veya MS X veya MS 2] | GUVEN: [50-85 arasi tam sayi] | NEDEN: [en fazla 10 kelimelik kisa sebep]"
                )
                ham = ""
                if motor_adi == "Gemini" and gizli_gemini_key:
                    _g_host = "generativelanguage" + ".googleapis.com"
                    _g_path = "/v1beta/models/gemini-2.0-flash:generateContent?key=" + str(gizli_gemini_key)
                    rg = requests.post(
                        "https://" + _g_host + _g_path,
                        json={"contents": list(({"parts": list(({"text": p_metin},))},))},
                        timeout=7,
                    ).json()
                    _c_g = next(iter(rg.get("candidates") or ()), {})
                    _p_g = next(iter((_c_g.get("content") or {}).get("parts") or ()), {})
                    ham = _p_g.get("text", "")
                elif motor_adi == "Groq" and groq_api_key:
                    _q_host = "api" + ".groq.com"
                    _q_path = "/openai/v1/chat/completions"
                    rq = requests.post(
                        "https://" + _q_host + _q_path,
                        headers={"Authorization": f"Bearer {groq_api_key}", "Content-Type": "application/json"},
                        json={"model": "openai/gpt-oss-120b", "messages": list(({"role": "user", "content": p_metin},)), "temperature": 0.2},
                        timeout=7,
                    ).json()
                    _c_q = next(iter(rq.get("choices") or ()), {})
                    ham = (_c_q.get("message") or {}).get("content", "")
                if not ham:
                    return None
                sec = "MS 1" if "MS 1" in ham else ("MS 2" if "MS 2" in ham else ("MS X" if "MS X" in ham else _mb_tercih))
                import re as _re_k
                m_g = _re_k.search(r"GUVEN:\s*(\d{2})", ham)
                g_val = max(50, min(88, int(m_g.group(1)))) if m_g else _mb_guv
                n_val = ham.split("NEDEN:").pop(-1).strip() if "NEDEN:" in ham else ham.strip()[:80]
                return {"motor": motor_adi, "tercih": sec, "guven": g_val, "neden": n_val}

            _oylar = list(({"motor": "Merkez Beyin (Matematik)", "tercih": _mb_tercih, "guven": _mb_guv, "neden": _ozet_k[:75]},))
            for _m_ad in ("Gemini", "Groq"):
                _res_k = _konsey_oyu_al(_m_ad, _ev_k, _dep_k, str(satir.get("Lig", "")), _ozet_k, piyasa_notu)
                if _res_k:
                    _oylar.append(_res_k)

            from collections import Counter as _CntK
            _en_cok = next(iter(_CntK(x.get("tercih") for x in _oylar).most_common(1)), (_mb_tercih, 1))
            _ort_tercih, _oy_adedi = _en_cok
            _ort_guven = int(round(sum(x.get("guven", 65) for x in _oylar) / len(_oylar)))
            _etiket_map = {"MS 1": f"{_ev_k} Kazanir (MS 1)", "MS 2": f"{_dep_k} Kazanir (MS 2)", "MS X": "Beraberlik (MS X)", "1X / Dengeli": f"{_ev_k} Kaybetmez (1X)"}
            _mutabakat = f"{_oy_adedi}/{len(_oylar)} Tam Mutabakat" if _oy_adedi == len(_oylar) else f"{_oy_adedi}/{len(_oylar)} Cogunluk Karari"

            with st.container(border=True):
                st.markdown(f"### 🏛️ Yapay Zeka Ortak Karar Konseyi | {_ev_k} vs {_dep_k}")
                st.success(f"**🏆 ORTAK KARAR ({_mutabakat}):** **{_etiket_map.get(_ort_tercih, _ort_tercih)}** — **Ortalama Guven: %{_ort_guven}**")
                _k_cols = st.columns(len(_oylar))
                for _idx_k, _oy_item in enumerate(_oylar):
                    with _k_cols[_idx_k]:
                        st.metric(label=_oy_item.get("motor", "AI"), value=_oy_item.get("tercih", "-"), delta=f"%{ _oy_item.get('guven', 65)} Guven")
                        st.caption(_oy_item.get("neden", ""))
        except Exception as _konsey_err:
            st.warning(f"Konsey Uyarisi: {_konsey_err}")
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
