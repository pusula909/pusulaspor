import io
import json
import os
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

alan = ".".join(["site", "api", "espn", "com"])
url_basi = "https://" + alan + "/apis/site/v2/sports/"
puan_basi = "https://" + alan + "/apis/v2/sports/"
basliklar = {"User-Agent": "Mozilla/5.0"}


@st.cache_data(ttl=30, show_spinner=False)
def _el_get(t):
    ev = list()
    try:
        h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "application/xml, text/xml"}
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

                ev_r = f"{win_map.get(h_ad, 0)}-{loss_map.get(h_ad, 0)}"
                dep_r = f"{win_map.get(a_ad, 0)}-{loss_map.get(a_ad, 0)}"

                ev.append({
                    "id": gc,
                    "status": {"type": {"state": st_code, "shortDetail": detay}},
                    "competitions": [{
                        "status": {"type": {"state": st_code, "shortDetail": detay}},
                        "competitors": [
                            {"homeAway": "home", "team": {"id": "1", "displayName": h_ad}, "score": hs, "records": [{"summary": ev_r}], "linescores": ceyrekler_ev},
                            {"homeAway": "away", "team": {"id": "2", "displayName": a_ad}, "score": ds, "records": [{"summary": dep_r}], "linescores": ceyrekler_dep},
                        ],
                    }],
                })
    except Exception:
        pass
    return {"events": ev}


@st.cache_data(ttl=120, show_spinner=False)
def piyasa_baremi_getir(lig_yolu, mac_id):
    sonuc = {"barem": None, "spread": ""}
    if not mac_id or lig_yolu == "euroleague_resmi" or "/" not in lig_yolu:
        return sonuc
    try:
        u = f"{url_basi}{lig_yolu}/summary?event={mac_id}"
        j = requests.get(u, headers=basliklar, timeout=5).json()
        pick = j.get("pickcenter", [])
        if pick:
            p0 = pick[0]
            if p0.get("overUnder"):
                sonuc["barem"] = float(p0["overUnder"])
            if p0.get("details"):
                sonuc["spread"] = str(p0["details"])
    except Exception:
        pass
    return sonuc


@st.cache_data(ttl=45, show_spinner=False)
def derin_saha_ve_istatistik_cek(mac_id, lig_yolu, tarih_str):
    detay_ozet = []
    yil, ay = int(tarih_str[:4]), int(tarih_str[4:6])
    sezon_kodu = f"E{yil if ay >= 8 else yil - 1}"
    try:
        if lig_yolu == "euroleague_resmi" and mac_id:
            u = f"https://euroleague.net{mac_id}&seasoncode={sezon_kodu}"
            j = requests.get(u, headers=basliklar, timeout=5).json()
            for idx, st_blok in enumerate(j.get("Stats", [])[:2]):
                t_ad = st_blok.get("Team", f"Takim {idx+1}")
                sahadakiler, faul_siniri = [], []
                for o in st_blok.get("PlayersStats", []):
                    isim = o.get("Player", "").strip()
                    pts = int(o.get("Points", 0) or 0)
                    fls = int(o.get("FoulsCommited", 0) or 0)
                    if o.get("IsPlaying", 0) == 1 and isim:
                        sahadakiler.append(f"{isim}({pts}s,{fls}f)")
                    if fls >= 3 and isim:
                        faul_siniri.append(f"{isim}({fls}f)")
                if sahadakiler:
                    detay_ozet.append(f"{t_ad} Sahadaki 5: {', '.join(sahadakiler[:5])}")
                if faul_siniri:
                    detay_ozet.append(f"{t_ad} Faul Riski: {', '.join(faul_siniri[:4])}")
        elif mac_id and "/" in lig_yolu:
            u = f"{url_basi}{lig_yolu}/summary?event={mac_id}"
            j = requests.get(u, headers=basliklar, timeout=5).json()
            for t_stat in j.get("boxscore", {}).get("teams", [])[:2]:
                t_ad = t_stat.get("team", {}).get("displayName", "")
                secilen = []
                for s in t_stat.get("statistics", []):
                    etk = s.get("label", s.get("name", ""))
                    deg = s.get("displayValue", "")
                    if any(k in etk.lower() for k in ("fg%", "3p%", "rebounds", "turnovers", "shots", "possession", "corners")):
                        secilen.append(f"{etk}: {deg}")
                if secilen:
                    detay_ozet.append(f"{t_ad} Istatistikleri [{', '.join(secilen[:5])}]")
            for item in j.get("keyEvents", [])[-5:]:
                dk = item.get("clock", {}).get("displayValue", "")
                txt = item.get("text", "")
                if txt:
                    detay_ozet.append(f"[{dk}] {txt}")
            for box_t in j.get("boxscore", {}).get("players", [])[:2]:
                t_ad = box_t.get("team", {}).get("displayName", "")
                stats_grp = box_t.get("statistics", [])
                if stats_grp:
                    aktifler = []
                    for a in stats_grp[0].get("athletes", [])[:5]:
                        a_ad = a.get("athlete", {}).get("displayName", "")
                        st_vals = a.get("stats", [])
                        if a_ad and st_vals:
                            aktifler.append(f"{a_ad}({'/'.join(st_vals[:3])})")
                    if aktifler:
                        detay_ozet.append(f"{t_ad} Rotasyon: {', '.join(aktifler)}")
    except Exception:
        pass
    return " | ".join(detay_ozet) if detay_ozet else "Canli saha istatistigi bekleniyor."
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
)

st.sidebar.header("Kontrol Merkezi")
gorunum = st.sidebar.radio(
    "Mod Secimi",
    ["Maclar ve Canli AI Analiz", "VIP Bulten & AI Karne", "Canli Kupon Takip", "AI Gunun Radari (Tum Ligler)", "Puan Durumu"],
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
    if telegram_mesaj_gonder(tg_token, tg_chat_id, "Pusulasporbot baglantisi basarili!"):
        st.sidebar.success("Test mesaji telefonuna gonderildi!")
    else:
        st.sidebar.error("Gonderilemedi. Bota Telegram'dan BASLAT dediginden emin ol.")

st.sidebar.divider()
spor = st.sidebar.selectbox("Spor Dali", ["Basketbol", "Futbol"])
lig = st.sidebar.selectbox("Lig Secimi", list(TUM_LIGLER[spor].keys()))
durum_filtre = st.sidebar.radio("Mac Durumu", ["Tumu", "Sadece Canli Maclar", "Oynanacak Maclar", "Biten Maclar"])
favori = st.sidebar.text_input("Favori Takim", "").strip().lower()
otomatik_yenile = st.sidebar.checkbox("Canli Otomatik Yenileme & Alarm (30 sn)", value=False)

yol = TUM_LIGLER[spor][lig]
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
        ev_p = list(int(x) for x in ev_rec.split("-"))
        dep_p = list(int(x) for x in dep_rec.split("-"))
        ev_g = ev_p.pop(0) / (sum(ev_p) if sum(ev_p) > 0 else 1)
        dep_g = dep_p.pop(0) / (sum(dep_p) if sum(dep_p) > 0 else 1)
        fark = abs(ev_s - dep_s)
        if spor_turu == "Futbol":
            rakamlar = "".join(c for c in detay_sure if c.isdigit())
            dk = int(rakamlar) if rakamlar else 0
            if dk >= 75 and fark <= 1 and (ev_g >= 0.58 or dep_g >= 0.58):
                baskili = ev_ad if ev_g >= dep_g else dep_ad
                return f"SON DAKIKA GOL BASKISI: {baskili} yukleniyor! ({ev_ad} {ev_s}-{dep_s} {dep_ad}, {detay_sure})"
        else:
            if ("Q4" in detay_sure or "4C" in detay_sure) and fark <= 5:
                return f"CRUNCH TIME: {ev_ad} {ev_s}-{dep_s} {dep_ad} ({detay_sure})"
    except Exception:
        pass
    return ""


def canli_firsat_etiketi_uret(spor_turu, state, detay_sure, ev_s, dep_s, ev_rec, dep_rec):
    if state != "in":
        return "Normal Akis"
    try:
        ev_p = list(int(x) for x in ev_rec.split("-"))
        dep_p = list(int(x) for x in dep_rec.split("-"))
        ev_g = ev_p.pop(0) / (sum(ev_p) if sum(ev_p) > 0 else 1)
        dep_g = dep_p.pop(0) / (sum(dep_p) if sum(dep_p) > 0 else 1)
        if spor_turu == "Basketbol":
            if ev_g >= 0.65 and (dep_s - ev_s) >= 7:
                return f"🔥 {ev_ad} Geri Donus Firsati"
            if dep_g >= 0.65 and (ev_s - dep_s) >= 7:
                return f"🔥 {dep_ad} Geri Donus Firsati"
            if ("Q2" in detay_sure or "Half" in detay_sure) and (ev_s + dep_s) >= 122:
                return "🔥 Yuksek Tempo (UST Sinyali)"
        else:
            if ev_g >= 0.62 and dep_s > ev_s:
                return f"🔥 {ev_ad} Evinde Geride (Baski)"
    except Exception:
        pass
    return "Normal Akis"


def periyot_ve_iy_cikar(ev_t, dep_t, spor_turu, state):
    if state == "pre":
        return "-"
    ev_ls = ev_t.get("linescores", [])
    dep_ls = dep_t.get("linescores", [])
    if not ev_ls or not dep_ls:
        return "-"
    parcalar = []
    for idx in range(min(len(ev_ls), len(dep_ls))):
        v1 = ev_ls[idx].get("displayValue", ev_ls[idx].get("value", "0"))
        v2 = dep_ls[idx].get("displayValue", dep_ls[idx].get("value", "0"))
        etiket = f"{idx+1}Y" if spor_turu == "Futbol" else f"{idx+1}C"
        parcalar.append(f"{etiket}: {v1}-{v2}")
    return " | ".join(parcalar)


def coklu_tahmin_motoru(ev_ad, dep_ad, ev_rec, dep_rec, spor_turu, lig_adi, ev_eksik, dep_eksik, state, ev_skor, dep_skor, piyasa_barem=None):
    try:
        ev_p = list(int(x) for x in ev_rec.split("-"))
        dep_p = list(int(x) for x in dep_rec.split("-"))
        ev_top = sum(ev_p) if sum(ev_p) > 0 else 1
        dep_top = sum(dep_p) if sum(dep_p) > 0 else 1
        ev_g = max(0.08, min(0.92, (ev_p.pop(0) / ev_top) + 0.06 - (ev_eksik * 0.03)))
        dep_g = max(0.08, min(0.92, (dep_p.pop(0) / dep_top) - (dep_eksik * 0.03)))

        if state == "in":
            skor_farki = ev_skor - dep_skor
            katsayi = 0.18 if spor_turu == "Futbol" else 0.025
            ev_g = max(0.05, min(0.95, ev_g + (skor_farki * katsayi)))
            dep_g = max(0.05, min(0.95, dep_g - (skor_farki * katsayi)))

        fark = abs(ev_g - dep_g)
        satirlar = []
        etiket = "CANLI AI" if state == "in" else "Mac Onu AI"

        if spor_turu == "Futbol":
            if ev_g > dep_g + 0.14:
                ms_secenek, ms_guven = f"{ev_ad} Kazanir (MS 1)", min(89, int(56 + fark * 45))
            elif dep_g > ev_g + 0.14:
                ms_secenek, ms_guven = f"{dep_ad} Kazanir (MS 2)", min(88, int(55 + fark * 45))
            else:
                ms_secenek, ms_guven = "Beraberlik / Cifte Sans 1X (MS 0)", min(75, int(64 - fark * 20))
            satirlar.append({"Analiz Tipi": etiket, "Bahis Kategorisi": "Mac Sonucu (MS)", "AI Tahmin Secenegi": ms_secenek, "Guven Seviyesi": f"%{ms_guven}", "GuvenInt": ms_guven})

            toplam_gol = ev_skor + dep_skor
            if state == "in":
                au_secenek, au_guven = f"Canli Toplam {toplam_gol + 0.5} UST", min(82, int(62 + (ev_g + dep_g) * 12))
            elif ev_g >= 0.54 and dep_g >= 0.48:
                au_secenek, au_guven = "Toplam 2.5 UST", min(79, int(58 + (ev_g + dep_g) * 14))
            elif ev_g <= 0.36 and dep_g <= 0.36:
                au_secenek, au_guven = "Toplam 2.5 ALT", min(76, int(60 + (1 - (ev_g + dep_g)) * 16))
            else:
                au_secenek, au_guven = "Toplam 1.5 UST", min(84, int(68 + (ev_g + dep_g) * 10))
            satirlar.append({"Analiz Tipi": etiket, "Bahis Kategorisi": "Toplam Gol Baremi", "AI Tahmin Secenegi": au_secenek, "Guven Seviyesi": f"%{au_guven}", "GuvenInt": au_guven})

            if (state == "in" and ev_skor > 0 and dep_skor > 0) or (ev_g >= 0.45 and dep_g >= 0.45):
                kg_secenek = "KG VAR (Iki Takim da Gol Atar)"
                kg_guven = 99 if (state == "in" and ev_skor > 0 and dep_skor > 0) else min(75, int(55 + min(ev_g, dep_g) * 30))
            else:
                kg_secenek, kg_guven = "KG YOK", min(74, int(58 + fark * 25))
            satirlar.append({"Analiz Tipi": etiket, "Bahis Kategorisi": "Karsilikli Gol (KG)", "AI Tahmin Secenegi": kg_secenek, "Guven Seviyesi": f"%{kg_guven}", "GuvenInt": kg_guven})
        else:
            if ev_g >= dep_g:
                ms_secenek, ms_guven = f"{ev_ad} Kazanir (MS 1)", min(89, int(54 + fark * 48))
            else:
                ms_secenek, ms_guven = f"{dep_ad} Kazanir (MS 2)", min(88, int(54 + fark * 48))
            satirlar.append({"Analiz Tipi": etiket, "Bahis Kategorisi": "Mac Sonucu (MS)", "AI Tahmin Secenegi": ms_secenek, "Guven Seviyesi": f"%{ms_guven}", "GuvenInt": ms_guven})

            model_beklenti = round(154 + (ev_g + dep_g) * 14) + 0.5 if lig_adi == "EuroLeague" else round(212 + (ev_g + dep_g) * 14) + 0.5
            aktif_barem = piyasa_barem if (piyasa_barem and state == "pre") else model_beklenti
            if state == "in" and (ev_skor + dep_skor) > 150:
                aktif_barem = (ev_skor + dep_skor) + 36.5

            if (piyasa_barem and model_beklenti - piyasa_barem >= 5) or (not piyasa_barem and (ev_g + dep_g) >= 1.05):
                au_secenek = f"Mac Toplami {aktif_barem} UST" + (" 💎 VALUE" if (piyasa_barem and model_beklenti - piyasa_barem >= 6) else "")
                au_guven = min(84, int(60 + (ev_g + dep_g) * 15))
            else:
                au_secenek = f"Mac Toplami {aktif_barem} ALT" + (" 💎 VALUE" if (piyasa_barem and piyasa_barem - model_beklenti >= 6) else "")
                au_guven = min(80, int(70 - (ev_g + dep_g) * 10))
            satirlar.append({"Analiz Tipi": etiket, "Bahis Kategorisi": "Mac Toplam Sayi", "AI Tahmin Secenegi": au_secenek, "Guven Seviyesi": f"%{au_guven}", "GuvenInt": au_guven})

        en_iyi = sorted(satirlar, key=lambda x: x["GuvenInt"], reverse=True).pop(0)
        ozet_metin = f"{ms_secenek} (%{ms_guven}) | {au_secenek} (%{au_guven})"
        return satirlar, ozet_metin, en_iyi
    except Exception:
        varsayilan = [{"Analiz Tipi": "Genel", "Bahis Kategorisi": "Genel Analiz", "AI Tahmin Secenegi": "Form Verisi Bekleniyor", "Guven Seviyesi": "%55", "GuvenInt": 55}]
        return varsayilan, "Veri Bekleniyor (%55)", varsayilan.pop(0)


@st.cache_data(ttl=120)
def ai_kadro_ve_eksik_getir(lig_yolu, mac_id, ev_id, dep_id, spor_turu):
    ev_sakatlar, dep_sakatlar, ev_ilk_kadro, dep_ilk_kadro = [], [], [], []
    if lig_yolu == "euroleague_resmi":
        return ev_ilk_kadro, dep_ilk_kadro, ev_sakatlar, dep_sakatlar, "EuroLeague Resmi Veri Akisi"
    try:
        sum_url = f"{url_basi}{lig_yolu}/summary?event={mac_id}"
        s_veri = requests.get(sum_url, headers=basliklar, timeout=8).json()
        for grup in s_veri.get("injuries", []):
            t_id = str(grup.get("team", {}).get("id", ""))
            for sakat in grup.get("injuries", []):
                ad = sakat.get("athlete", {}).get("displayName", "")
                durum = sakat.get("status", "Eksik")
                if ad:
                    if t_id == str(ev_id):
                        ev_sakatlar.append(f"{ad} ({durum})")
                    else:
                        dep_sakatlar.append(f"{ad} ({durum})")
        for roster in s_veri.get("rosters", []):
            t_id = str(roster.get("team", {}).get("id", ""))
            isimler = [r.get("athlete", {}).get("displayName", "") for r in roster.get("roster", [])[:11] if r.get("athlete", {}).get("displayName")]
            if t_id == str(ev_id):
                ev_ilk_kadro = isimler
            else:
                dep_ilk_kadro = isimler
    except Exception:
        pass
    return ev_ilk_kadro, dep_ilk_kadro, ev_sakatlar, dep_sakatlar, "ESPN Resmi Kadro & Sakatlik Havuzu"


@st.cache_data(ttl=180)
def h2h_ve_form_getir(lig_yolu, mac_id, ev_ad, dep_ad):
    if lig_yolu == "euroleague_resmi":
        return []
    try:
        s_veri = requests.get(f"{url_basi}{lig_yolu}/summary?event={mac_id}", headers=basliklar, timeout=6).json()
        sonuclar = []
        for g in s_veri.get("againstTheSpread", [])[:2]:
            for m in g.get("games", [])[:3]:
                sonuclar.append(f"{m.get('awayTeam', {}).get('abbreviation', '')} {m.get('awayScore', '')}-{m.get('homeScore', '')} {m.get('homeTeam', {}).get('abbreviation', '')}")
        return sonuclar[:5]
    except Exception:
        return []


@st.cache_data(ttl=90, show_spinner=False)
def gemini_taktik_yorumu_uret(api_key, spor_turu, lig_adi, ev_ad, dep_ad, ev_rec, dep_rec, ev_eksik, dep_eksik, durum_metni):
    soru = (
        f"Sen dunya capinda bir {spor_turu} Bas Analisti ve Basantrenor Danismanisin. "
        f"Duz istatistik ezberine ASLA dusme! "
        f"Mac: {lig_adi} | {ev_ad} (Form: {ev_rec}) vs {dep_ad} (Form: {dep_rec}). "
        f"Anlik Durum, Piyasa Baremi, Boxscore Istatistikleri ve Sahadaki Oyuncular: {durum_metni}. "
        f"{ev_ad} Eksikler: {ev_eksik}. {dep_ad} Eksikler: {dep_eksik}. "
        f"SIKI KURAL: Hafizandaki eski yillarin kadrolarini ASLA yazma! Yalnizca verilen Kadro Havuzu ve Canli Saha listesindeki oyunculari kullan.\n\n"
        f"Ciktiyi Turkce olarak TAM OLARAK su 3 baslikta yaz:\n"
        f"🎯 NOKTA ATISI ANA KARAR: (Tek bir net secenek ve piyasa baremine gore mantikli karar)\n"
        f"🧠 KOC, ROTASYON VE OYUN OKUMASI: (Sahadaki istatistikler, piyasa baremi ve koc hamlesiyle acikla)\n"
        f"⚠️ EN BUYUK RISK / DIKKAT NOKTASI: (Bu tahmini bozabilecek tek kritik senaryo)"
    )
    if GEMINI_AKTIF and api_key:
        try:
            client = genai.Client(api_key=api_key.strip(), http_options={"api_version": "v1beta"})
            for m in ("gemini-2.5-flash", "gemini-2.5-flash-lite"):
                try:
                    yanit = client.models.generate_content(model=m, contents=soru)
                    if yanit and yanit.text:
                        return yanit.text
                except Exception:
                    continue
        except Exception:
            pass
    groq_anahtar = st.secrets.get("GROQ_KEY", "").strip()
    if groq_anahtar:
        try:
            g_resp = requests.post(
                "https://groq.com",
                headers={"Authorization": f"Bearer {groq_anahtar}", "Content-Type": "application/json"},
                json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": soru}], "temperature": 0.4, "max_tokens": 450},
                timeout=12,
            ).json()
            if "choices" in g_resp and g_resp["choices"]:
                return g_resp["choices"].get("message", {}).get("content", "").strip()
        except Exception:
            pass
    return "AI yorumu icin API anahtari bekleniyor."


def excel_dosyasi_olustur(df):
    tampon = io.BytesIO()
    with pd.ExcelWriter(tampon, engine="openpyxl") as yazici:
        df.to_excel(yazici, index=False, sheet_name="AI_Analiz")
    return tampon.getvalue()if gorunum == "VIP Bulten & AI Karne":
    st.subheader("🌅 Gunun VIP AI Bulteni & Haftalik Performans Karnesi")
    col_b, col_k = st.columns(2)

    with col_b:
        st.markdown("### 📋 Son Otomatik Bulten (son_bulten.json)")
        if os.path.exists("son_bulten.json"):
            try:
                with open("son_bulten.json", "r", encoding="utf-8") as f:
                    b_veri = json.load(f)
                if b_veri:
                    df_b = pd.DataFrame(b_veri)[["tarih_guzel", "lig", "mac", "saat", "tahmin", "guven"]]
                    df_b.columns = ["Tarih", "Lig", "Mac", "Saat", "AI Tahmin", "Guven %"]
                    st.dataframe(df_b, use_container_width=True, hide_index=True)
                else:
                    st.info("Bulten dosyasi su an bos.")
            except Exception as e:
                st.warning(f"Bulten okunamadi: {e}")
        else:
            st.info("Henuz otomatik bulten dosyasi olusmamis.")

    with col_k:
        st.markdown("### 🏅 AI Basari & Isabet Karnesi (haftalik_arsiv.json)")
        if os.path.exists("haftalik_arsiv.json"):
            try:
                with open("haftalik_arsiv.json", "r", encoding="utf-8") as f:
                    k_veri = json.load(f)
                if k_veri:
                    df_k = pd.DataFrame(k_veri)
                    toplam_m = len(df_k)
                    tutan_m = int(df_k["tuttu"].sum())
                    oran = int((tutan_m / toplam_m) * 100) if toplam_m > 0 else 0
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Toplam Analiz", f"{toplam_m} Mac")
                    m2.metric("Isabetli Tahmin", f"{tutan_m} Mac")
                    m3.metric("Genel Basari", f"%{oran}")
                    st.dataframe(df_k.tail(15), use_container_width=True, hide_index=True)
                else:
                    st.info("Karne icin gece mac sonuclari bekleniyor.")
            except Exception as e:
                st.warning(f"Karne okunamadi: {e}")
        else:
            st.info("Henuz haftalik arsiv dosyasi olusmamis.")

elif gorunum == "Canli Kupon Takip":
    st.subheader("Canli Kombine Kupon Olusturucu & Anlik Takip")
    c1, c2, c3 = st.columns(3)
    k_spor = c1.selectbox("Spor", ("Basketbol", "Futbol"), key="k_spor")
    k_lig = c2.selectbox("Lig", list(TUM_LIGLER[k_spor].keys()), key="k_lig")
    k_yol = TUM_LIGLER[k_spor][k_lig]

    k_maclar_veri = []
    try:
        resp = _el_get(tarih) if k_yol == "euroleague_resmi" else requests.get(f"{url_basi}{k_yol}/scoreboard?dates={tarih}", headers=basliklar, timeout=6).json()
        for ev in resp.get("events", []):
            comp = ev.get("competitions", [{}]).pop(0)
            takimlar = comp.get("competitors", [])
            if len(takimlar) >= 2:
                ev_t = next((t for t in takimlar if t.get("homeAway") == "home"), takimlar.pop(0))
                dep_t = next((t for t in takimlar if t.get("homeAway") == "away"), takimlar.pop(0))
                ev_ad = ev_t.get("team", {}).get("displayName", "Ev")
                dep_ad = dep_t.get("team", {}).get("displayName", "Dep")
                k_maclar_veri.append({"id": ev.get("id"), "yol": k_yol, "spor": k_spor, "ev": ev_ad, "dep": dep_ad, "etiket": f"{ev_ad} vs {dep_ad}"})
    except Exception:
        pass

    if k_maclar_veri:
        secilen_k_etiket = c3.selectbox("Mac Sec", [m["etiket"] for m in k_maclar_veri], key="k_mac")
        secilen_k_obj = next(m for m in k_maclar_veri if m["etiket"] == secilen_k_etiket)
        t_col1, t_col2 = st.columns(2)
        secenekler = ("MS 1", "MS 0", "MS 2", "1.5 UST", "2.5 UST", "2.5 ALT", "KG VAR", "KG YOK") if k_spor == "Futbol" else ("MS 1", "MS 2", "Mac Toplami UST", "Mac Toplami ALT")
        secilen_tip = t_col1.selectbox("Tahmin Tipi", secenekler, key="k_tahmin")
        if "Mac Toplami" in secilen_tip:
            b_val = t_col2.number_input("Barem Girin", value=220.5, step=1.0)
            son_tahmin = f"Mac Toplami {b_val} {'UST' if 'UST' in secilen_tip else 'ALT'}"
        else:
            son_tahmin = secilen_tip
        if st.button("Kupona Ekle"):
            st.session_state.kupon_listesi.append({**secilen_k_obj, "tahmin": son_tahmin})
            st.success(f"Eklendi: {secilen_k_obj['etiket']} -> {son_tahmin}")

    if st.session_state.kupon_listesi:
        kupon_tablosu = []
        genel_ihtimal = 1.0
        hepsi_bitti_ve_tuttu = True
        for item in st.session_state.kupon_listesi:
            ev_s, dep_s, state_k, detay_k = 0, 0, "pre", "Baslamadi"
            try:
                if item["yol"] == "euroleague_resmi":
                    bulunan = next((x for x in _el_get(tarih).get("events", []) if str(x.get("id")) == str(item["id"])), {})
                    header_comp = bulunan.get("competitions", [{}]).pop(0)
                    state_k = bulunan.get("status", {}).get("type", {}).get("state", "pre")
                    detay_k = bulunan.get("status", {}).get("type", {}).get("shortDetail", "")
                else:
                    s_res = requests.get(f"{url_basi}{item['yol']}/summary?event={item['id']}", headers=basliklar, timeout=5).json()
                    header_comp = s_res.get("header", {}).get("competitions", [{}]).pop(0)
                    state_k = header_comp.get("status", {}).get("type", {}).get("state", "pre")
                    detay_k = header_comp.get("status", {}).get("type", {}).get("shortDetail", "")
                for t_obj in header_comp.get("competitors", []):
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
                    barem = float([x for x in t.split() if "." in x].pop(0))
                    if toplam_s > barem:
                        tuttu_mu = True
                elif "ALT" in t:
                    barem = float([x for x in t.split() if "." in x].pop(0))
                    if toplam_s < barem:
                        tuttu_mu = True

                if state_k == "post":
                    durum_ikon = "✅ TUTTU" if tuttu_mu else "❌ YATTI"
                    tekil_olasilik = 1.0 if tuttu_mu else 0.0
                    if not tuttu_mu:
                        hepsi_bitti_ve_tuttu = False
                else:
                    hepsi_bitti_ve_tuttu = False
                    durum_ikon = "🟢 Su An Tutuyor" if tuttu_mu else "🟡 Geride / Bekliyor"
                    tekil_olasilik = 0.78 if tuttu_mu else 0.35
            else:
                hepsi_bitti_ve_tuttu = False

            genel_ihtimal *= tekil_olasilik
            kupon_tablosu.append({"Mac": f"{item['ev']} vs {item['dep']}", "Oynanan": t, "Skor": f"{ev_s} - {dep_s}", "Sure": detay_k, "Durum": durum_ikon, "Canli Ihtimal": f"%{int(tekil_olasilik * 100)}"})

        st.dataframe(pd.DataFrame(kupon_tablosu), use_container_width=True, hide_index=True)
        k1, k2 = st.columns(2)
        k1.metric("Kuponun Canli Tutma Ihtimali", f"%{int(genel_ihtimal * 100)}")
        if k2.button("Kuponu Temizle"):
            st.session_state.kupon_listesi = []
            st.session_state.kupon_bildirim_gonderildi = False
            st.rerun()

elif gorunum == "Puan Durumu":
    st.subheader(f"{lig} - Guncel Puan Durumu")
    try:
        r = requests.get(f"{puan_basi}{yol}/standings", headers=basliklar, timeout=8).json()
        satirlar = []
        for g in r.get("children", []):
            for i, e in enumerate(g.get("standings", {}).get("entries", []), 1):
                st_dict = {s["name"]: s["displayValue"] for s in e.get("stats", [])}
                satirlar.append({"Grup": g.get("name", ""), "Sira": i, "Takim": e["team"]["displayName"], "O": st_dict.get("gamesPlayed", "-"), "G": st_dict.get("wins", "-"), "M": st_dict.get("losses", "-"), "Puan/Oran": st_dict.get("points", st_dict.get("winPercent", "-"))})
        if satirlar:
            puan_df = pd.DataFrame(satirlar)
            st.dataframe(puan_df, use_container_width=True, hide_index=True)
            st.download_button("Puan Durumunu Excel Olarak Indir", data=excel_dosyasi_olustur(puan_df), file_name=f"{lig}_Puan_Durumu.xlsx")
        else:
            st.info("Bu lig icin su an puan durumu tablosu yok.")
    except Exception:
        st.info("Bu lig icin su an puan durumu tablosu mevcut degil.")

elif gorunum == "AI Gunun Radari (Tum Ligler)":
    st.subheader(f"AI Gunun Radari | {tarih_obj.strftime('%d.%m.%Y')} Tum Ligler Taramasi")
    if st.button("Tum Ligleri Simdi Tara ve En Guclu Tahminleri Bul", type="primary"):
        tum_radar = []
        ilerleme = st.progress(0)
        toplam_islem = sum(len(v) for v in TUM_LIGLER.values())
        sayac = 0
        for s_adi, lig_sozluk in TUM_LIGLER.items():
            for l_adi, l_yolu in lig_sozluk.items():
                sayac += 1
                ilerleme.progress(min(1.0, sayac / toplam_islem))
                try:
                    r_veri = _el_get(tarih) if l_yolu == "euroleague_resmi" else requests.get(f"{url_basi}{l_yolu}/scoreboard?dates={tarih}", headers=basliklar, timeout=6).json()
