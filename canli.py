import streamlit as st
import requests
import pandas as pd
import time
import io
import xml.etree.ElementTree as ET
from datetime import datetime

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
st.markdown('<style>.stApp{background-color:#F4F6F9!important}section[data-testid="stSidebar"]{background-color:#FFFFFF!important;border-right:2px solid #E2E8F0!important}h1{color:#0F172A!important;border-bottom:4px solid #DC2626;padding-bottom:8px;font-weight:900!important}h2,h3{color:#1E293B!important;background:#FFFFFF;border-left:5px solid #2563EB;padding:8px 14px;border-radius:6px;box-shadow:0 2px 6px rgba(0,0,0,0.05)}div[data-testid="stMetric"]{background:#FFFFFF!important;border:1px solid #E2E8F0!important;border-top:4px solid #16A34A!important;border-radius:12px!important;padding:15px!important;box-shadow:0 4px 12px rgba(0,0,0,0.06)!important}div[data-testid="stAlert"]{background:#EFF6FF!important;border:1px solid #BFDBFE!important;border-left:5px solid #2563EB!important;border-radius:10px!important}.stDownloadButton>button,.stButton>button{background:#DC2626!important;color:#FFFFFF!important;border-radius:8px!important;font-weight:700!important}</style>', unsafe_allow_html=True)
st.title("AI Pro Spor Veri Merkezi | Canli Analiz, Radar & Taktik Yorum")

if "eski_skorlar" not in st.session_state:
    st.session_state.eski_skorlar = {}
if "radar_sonuclari" not in st.session_state:
    st.session_state.radar_sonuclari = []
if "kupon_listesi" not in st.session_state:
    st.session_state.kupon_listesi = []
if "kupon_bildirim_gonderildi" not in st.session_state:
    st.session_state.kupon_bildirim_gonderildi = False
if "gonderilen_kritik_uyarilar" not in st.session_state:
    st.session_state.gonderilen_kritik_uyarilar = []

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
        "Portekiz Liga": "soccer/por.1"
    },
    "Basketbol": {
        "NBA": "basketball/nba",
        "EuroLeague": "euroleague_resmi",
        "NCAA Basketbol": "basketball/mens-college-basketball"
    }
}

gizli_tg_token = st.secrets.get("TG_TOKEN", "")
gizli_tg_chat_id = st.secrets.get("TG_CHAT_ID", "")
gizli_gemini_key = st.secrets.get("GEMINI_KEY", "")

gemini_api_key = st.sidebar.text_input("Gemini API Anahtari (Opsiyonel)", value=gizli_gemini_key, type="password")
st.sidebar.header("Kontrol Merkezi")
gorunum = st.sidebar.radio("Mod Secimi", ["Maclar ve Canli AI Analiz", "Canli Kupon Takip", "AI Gunun Radari (Tum Ligler)", "Puan Durumu"])
tarih_obj = st.sidebar.date_input("Tarih", datetime.now())
tarih = tarih_obj.strftime("%Y%m%d")
tarih_tireli = tarih_obj.strftime("%Y-%m-%d")

st.sidebar.divider()
st.sidebar.subheader("Telegram Bildirim Ayari")
tg_token = st.sidebar.text_input("Telegram Bot Token", value=gizli_tg_token, type="password")
tg_chat_id = st.sidebar.text_input("Telegram Chat ID", value=gizli_tg_chat_id)

def telegram_mesaj_gonder(token, chat_id, mesaj):
    if not token or not chat_id:
        return False
    try:
        tg_adres = "https://telegram.org" + token.strip() + "/sendMessage"
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
spor = st.sidebar.selectbox("Spor Dali", ["Basketbol", "Futbol"])
lig = st.sidebar.selectbox("Lig Secimi", list(TUM_LIGLER[spor].keys()))
durum_filtre = st.sidebar.radio("Mac Durumu", ["Tumu", "Sadece Canli Maclar", "Oynanacak Maclar", "Biten Maclar"])
favori = st.sidebar.text_input("Favori Takim", "").strip().lower()
otomatik_yenile = st.sidebar.checkbox("Canli Otomatik Yenileme & Alarm (15 sn)", value=False)

yol = TUM_LIGLER[spor][lig]
st.session_state.radar_sonuclari = st.session_state.radar_sonuclari or list()
st.session_state.kupon_listesi = st.session_state.kupon_listesi or list()
st.session_state.gonderilen_kritik_uyarilar = st.session_state.gonderilen_kritik_uyarilar or list()

def telegram_mesaj_gonder(token, chat_id, mesaj):
    if not token or not chat_id:
        return False
    try:
        tg_adres = "https://telegram.org" + token.strip() + "/sendMessage"
        r = requests.post(tg_adres, data={"chat_id": str(chat_id).strip(), "text": mesaj}, timeout=8)
        return r.status_code == 200
    except Exception:
        return False

@st.cache_data(ttl=25)
def euroleague_scoreboard_donustur(tarih_str_tireli):
    events = list()
    yil = int(tarih_str_tireli[:4])
    ay = int(tarih_str_tireli[5:7])
    sezon = f"E{yil}" if ay >= 9 else f"E{yil - 1}"
    try:
        r = requests.get(f"https://euroleague.net{sezon}", headers=basliklar, timeout=8)
        if r.status_code == 200:
            root = ET.fromstring(r.content)
            for item in root.findall(".//item"):
                d_raw = item.findtext("date", "").strip()
                if not d_raw:
                    continue
                try:
                    d_fmt = datetime.strptime(d_raw, "%b %d, %Y").strftime("%Y-%m-%d")
                except Exception:
                    continue
                if d_fmt == tarih_str_tireli:
                    ev_ad = item.findtext("hometeam", "Ev Sahibi").strip()
                    dep_ad = item.findtext("awayteam", "Deplasman").strip()
                    ev_s = item.findtext("homescore", "0").strip() or "0"
                    dep_s = item.findtext("awayscore", "0").strip() or "0"
                    saat = item.findtext("startime", "").strip()
                    played = item.findtext("played", "false").lower() == "true"
                    gcode = item.findtext("gamecode", "")
                    if played:
                        st_code, detay = "post", "Final"
                    elif int(ev_s) > 0 or int(dep_s) > 0:
                        st_code, detay = "in", "Canli"
                    else:
                        st_code, detay = "pre", saat if saat else "Programli"
                    events.append({
                        "id": f"EL_{sezon}_{gcode}",
                        "status": {"type": {"state": st_code, "shortDetail": detay}},
                        "competitions": [{
                            "competitors": [
                                {"homeAway": "home", "team": {"id": item.findtext("homecode", ""), "displayName": ev_ad}, "score": ev_s, "records": [{"summary": "0-0"}]},
                                {"homeAway": "away", "team": {"id": item.findtext("awaycode", ""), "displayName": dep_ad}, "score": dep_s, "records": [{"summary": "0-0"}]}
                            ]
                        }]
                    })
    except Exception:
        pass
    return {"events": events}

def lig_verisi_getir(lig_yolu, tarih_duz, tarih_tire):
    if lig_yolu == "euroleague_resmi":
        return euroleague_scoreboard_donustur(tarih_tire)
    try:
        return requests.get(f"{url_basi}{lig_yolu}/scoreboard?dates={tarih_duz}", headers=basliklar, timeout=8).json()
    except Exception:
        return {"events": list()}

def periyot_ve_iy_cikar(ev_t, dep_t, spor_turu, state):
    if state == "pre":
        return "-"
    ev_ls = ev_t.get("linescores", list())
    dep_ls = dep_t.get("linescores", list())
    if not ev_ls or not dep_ls:
        return "Veri Bekleniyor"
    parcalar = list()
    if spor_turu == "Futbol":
        ev_iy = int(float(ev_ls[0].get("value", 0)))
        dep_iy = int(float(dep_ls[0].get("value", 0)))
        return f"IY: {ev_iy}-{dep_iy}"
    else:
        for idx in range(min(len(ev_ls), len(dep_ls))):
            e_v = int(float(ev_ls[idx].get("value", 0)))
            d_v = int(float(dep_ls[idx].get("value", 0)))
            isim = f"{idx+1}C" if idx < 4 else f"UZ{idx-3}"
            parcalar.append(f"{isim}: {e_v}-{d_v}")
        return " | ".join(parcalar) if parcalar else "-"

@st.cache_data(ttl=15)
def koc_ve_rotasyon_etkisi_getir(lig_yolu, mac_id, ev_id, dep_id, spor_turu, ev_ad, dep_ad):
    if lig_yolu == "euroleague_resmi":
        return "EuroLeague Resmi Canli Veri", 0.0, ""
    ozetler = list()
    etki_puani = 0.0
    kritik_alarm = ""
    try:
        s_veri = requests.get(f"{url_basi}{lig_yolu}/summary?event={mac_id}", headers=basliklar, timeout=6).json()
        if spor_turu == "Basketbol":
            plays = s_veri.get("plays", list())
            if plays:
                son_olaylar = plays[-25:]
                ev_son_sayi, dep_son_sayi, son_hamle = 0, 0, ""
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
                    kritik_alarm = f"BASKETBOL KRITIK SERI: {ev_ad} vs {dep_ad} macinda {onde_olan} {ev_son_sayi}-{dep_son_sayi} seri yakaladi!"
        elif spor_turu == "Futbol":
            olaylar = s_veri.get("keyEvents", list())
            if olaylar:
                son_olay = olaylar[-1]
                tip = son_olay.get("type", {}).get("text", "")
                dk = son_olay.get("clock", {}).get("displayValue", "")
                metin = son_olay.get("text", "")
                ozetler.append(f"Son Olay ({dk}): {tip} - {metin}")
                if any(k in tip for k in ["Goal", "Penalty", "Red Card", "Substitution"]):
                    kritik_alarm = f"FUTBOL KRITIK AN ({dk}): {ev_ad} vs {dep_ad} -> {tip}: {metin}"
    except Exception:
        pass
    durum_metni = " | ".join(ozetler) if ozetler else "Kritik bir hamle veya seri yok"
    return durum_metni, etki_puani, kritik_alarm
   def coklu_tahmin_motoru(ev_ad, dep_ad, ev_rec, dep_rec, spor_turu, lig_adi, ev_eksik=0, dep_eksik=0, state="pre", ev_skor=0, dep_skor=0):
    try:
        ev_p = [int(x) for x in ev_rec.split("-")]
        dep_p = [int(x) for x in dep_rec.split("-")]
        ev_top = sum(ev_p) if sum(ev_p) > 0 else 1
        dep_top = sum(dep_p) if sum(dep_p) > 0 else 1
        ev_g = max(0.08, min(0.92, (ev_p[0] / ev_top) + 0.06 - (ev_eksik * 0.03)))
        dep_g = max(0.08, min(0.92, (dep_p[0] / dep_top) - (dep_eksik * 0.03)))
        if state == "in":
            skor_farki = ev_skor - dep_skor
            carpan = 0.18 if spor_turu == "Futbol" else 0.025
            ev_g = max(0.05, min(0.95, ev_g + (skor_farki * carpan)))
            dep_g = max(0.05, min(0.95, dep_g - (skor_farki * carpan)))
        fark = abs(ev_g - dep_g)
        satirlar = list()
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
            else:
                au_secenek, au_guven = "Toplam 1.5 UST", min(84, int(68 + (ev_g + dep_g) * 10))
            satirlar.append({"Analiz Tipi": etiket, "Bahis Kategorisi": "Toplam Gol Baremi", "AI Tahmin Secenegi": au_secenek, "Guven Seviyesi": f"%{au_guven}", "GuvenInt": au_guven})
        else:
            if ev_g >= dep_g:
                ms_secenek, ms_guven = f"{ev_ad} Kazanir (MS 1)", min(89, int(54 + fark * 48))
            else:
                ms_secenek, ms_guven = f"{dep_ad} Kazanir (MS 2)", min(88, int(54 + fark * 48))
            satirlar.append({"Analiz Tipi": etiket, "Bahis Kategorisi": "Mac Sonucu (MS)", "AI Tahmin Secenegi": ms_secenek, "Guven Seviyesi": f"%{ms_guven}", "GuvenInt": ms_guven})
            beklenen_toplam = round((154 if lig_adi == "EuroLeague" else 212) + (ev_g + dep_g) * 14) + 0.5
            if state == "in" and (ev_skor + dep_skor) > 150:
                beklenen_toplam = (ev_skor + dep_skor) + 36.5
            au_secenek = f"Mac Toplami {beklenen_toplam} UST" if (ev_g + dep_g) >= 1.05 else f"Mac Toplami {beklenen_toplam} ALT"
            au_guven = min(78, int(56 + (ev_g + dep_g) * 15))
            satirlar.append({"Analiz Tipi": etiket, "Bahis Kategorisi": "Mac Toplam Sayi", "AI Tahmin Secenegi": au_secenek, "Guven Seviyesi": f"%{au_guven}", "GuvenInt": au_guven})
        en_iyi = sorted(satirlar, key=lambda x: x["GuvenInt"], reverse=True)[0]
        return satirlar, f"{ms_secenek} (%{ms_guven}) | {au_secenek} (%{au_guven})", en_iyi
    except Exception:
        v = [{"Analiz Tipi": "Genel", "Bahis Kategorisi": "Genel Analiz", "AI Tahmin Secenegi": "Form Verisi Bekleniyor", "Guven Seviyesi": "%55", "GuvenInt": 55}]
        return v, "Veri Bekleniyor (%55)", v[0]

@st.cache_data(ttl=120)
def ai_kadro_ve_eksik_getir(lig_yolu, mac_id, ev_id, dep_id, spor_turu):
    if lig_yolu == "euroleague_resmi":
        return list(), list(), list(), list(), "EuroLeague Resmi Mac Verisi"
    ev_sakatlar, dep_sakatlar, ev_ilk_kadro, dep_ilk_kadro = list(), list(), list(), list()
    try:
        s_veri = requests.get(f"{url_basi}{lig_yolu}/summary?event={mac_id}", headers=basliklar, timeout=8).json()
        for grup in s_veri.get("injuries", list()):
            t_id = str(grup.get("team", {}).get("id", ""))
            for sakat in grup.get("injuries", list()):
                ad = sakat.get("athlete", {}).get("displayName", "")
                if ad:
                    if t_id == str(ev_id):
                        ev_sakatlar.append(ad)
                    elif t_id == str(dep_id):
                        dep_sakatlar.append(ad)
    except Exception:
        pass
    return ev_ilk_kadro, dep_ilk_kadro, ev_sakatlar, dep_sakatlar, "Yapay Zeka Kadro Analizi"

@st.cache_data(ttl=600, show_spinner=False)
def gemini_taktik_yorumu_uret(api_key, spor_turu, lig_adi, ev_ad, dep_ad, ev_rec, dep_rec, ev_eksik, dep_eksik, durum_metni):
    if not GEMINI_AKTIF or not api_key:
        return None
    soru = f"Sen profesyonel bir {spor_turu} veri analistisin. {lig_adi} ligindeki {ev_ad} vs {dep_ad} macini incele. Durum: {durum_metni}. Turkce 3 kisa madde ile taktik, tempo ve mac sonucu yorumu yap."
    try:
        client = genai.Client(api_key=api_key)
        yanit = client.models.generate_content(model="gemini-2.5-flash", contents=soru)
        return yanit.text if yanit and yanit.text else None
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
    k_spor = c1.selectbox("Spor", ["Basketbol", "Futbol"], key="k_spor")
    k_lig = c2.selectbox("Lig", list(TUM_LIGLER[k_spor].keys()), key="k_lig")
    k_yol = TUM_LIGLER[k_spor][k_lig]
    k_maclar_veri = list()
    resp = lig_verisi_getir(k_yol, tarih, tarih_tireli)
    for ev in resp.get("events", list()):
        comp = ev.get("competitions", [{}])[0]
        takimlar = comp.get("competitors", list())
        if len(takimlar) >= 2:
            ev_t = next((t for t in takimlar if t.get("homeAway") == "home"), takimlar[0])
            dep_t = next((t for t in takimlar if t.get("homeAway") == "away"), takimlar[1])
            ev_ad, dep_ad = ev_t.get("team", {}).get("displayName", "Ev"), dep_t.get("team", {}).get("displayName", "Dep")
            k_maclar_veri.append({"id": ev.get("id"), "yol": k_yol, "spor": k_spor, "ev": ev_ad, "dep": dep_ad, "etiket": f"{ev_ad} vs {dep_ad}"})
    if k_maclar_veri:
        secilen_k_etiket = c3.selectbox("Mac Sec", [m["etiket"] for m in k_maclar_veri], key="k_mac")
        secilen_k_obj = next(m for m in k_maclar_veri if m["etiket"] == secilen_k_etiket)
        secenekler = ["MS 1", "MS 0", "MS 2", "1.5 UST", "2.5 UST", "2.5 ALT", "KG VAR", "KG YOK"] if k_spor == "Futbol" else ["MS 1", "MS 2", "Toplam 155.5 UST", "Toplam 165.5 UST", "Toplam 210.5 UST", "Toplam 220.5 UST"]
        oynanan_tahmin = st.selectbox("Oynadigin Tahmin", secenekler, key="k_tahmin")
        if st.button("Kupona Ekle"):
            st.session_state.kupon_listesi.append({**secilen_k_obj, "tahmin": oynanan_tahmin})
            st.rerun()
    else:
        st.info("Bu ligde secili tarihte mac bulunamadi.")
    if st.session_state.kupon_listesi:
        st.dataframe(pd.DataFrame(st.session_state.kupon_listesi)[["ev", "dep", "tahmin"]], use_container_width=True)
        if st.button("Kuponu Temizle"):
            st.session_state.kupon_listesi = list()
            st.rerun()

elif gorunum == "Puan Durumu":
    st.subheader(f"{lig} - Guncel Puan Durumu")
    if yol == "euroleague_resmi":
        st.info("EuroLeague puan durumu resmi API uzerinden canli mac takvimi ile senkronize edilmektedir.")
    else:
        try:
            r = requests.get(f"{puan_basi}{yol}/standings", headers=basliklar, timeout=8).json()
            satirlar = list()
            for g in r.get("children", list()):
                for i, e in enumerate(g.get("standings", {}).get("entries", list()), 1):
                    st_dict = {s["name"]: s["displayValue"] for s in e.get("stats", list())}
                    satirlar.append({"Grup": g.get("name", ""), "Sira": i, "Takim": e["team"]["displayName"], "O": st_dict.get("gamesPlayed", "-"), "G": st_dict.get("wins", "-"), "M": st_dict.get("losses", "-"), "Puan/Oran": st_dict.get("points", st_dict.get("winPercent", "-"))})
            if satirlar:
                puan_df = pd.DataFrame(satirlar)
                st.dataframe(puan_df, use_container_width=True, hide_index=True)
                st.download_button("Puan Durumunu Excel Olarak Indir", data=excel_dosyasi_olustur(puan_df), file_name=f"{lig}_Puan_Durumu.xlsx")
        except Exception:
            st.info("Bu lig icin su an puan durumu tablosu yok.")

elif gorunum == "AI Gunun Radari (Tum Ligler)":
    st.subheader(f"AI Gunun Radari | {tarih_obj.strftime('%d.%m.%Y')} Tum Ligler Taramasi")
    if st.button("Tum Ligleri Simdi Tara ve En Guclu Tahminleri Bul", type="primary"):
        tum_radar = list()
        ilerleme = st.progress(0)
        toplam_islem = sum(len(v) for v in TUM_LIGLER.values())
        sayac = 0
        for s_adi, lig_sozluk in TUM_LIGLER.items():
            for l_adi, l_yolu in lig_sozluk.items():
                sayac += 1
                ilerleme.progress(min(1.0, sayac / toplam_islem))
                resp = lig_verisi_getir(l_yolu, tarih, tarih_tireli)
                for ev in resp.get("events", list()):
                    comp = ev.get("competitions", [{}])[0]
                    t_list = comp.get("competitors", list())
                    if len(t_list) < 2:
                        continue
                    ev_t = next((t for t in t_list if t["homeAway"] == "home"), t_list[0])
                    dep_t = next((t for t in t_list if t["homeAway"] == "away"), t_list[1])
                    ev_ad, dep_ad = ev_t["team"]["displayName"], dep_t["team"]["displayName"]
                    ev_r = ev_t.get("records", [{"summary": "0-0"}])[0].get("summary", "0-0")
                    dep_r = dep_t.get("records", [{"summary": "0-0"}])[0].get("summary", "0-0")
                    st_code = ev["status"]["type"]["state"]
                    _, _, en_iyi = coklu_tahmin_motoru(ev_ad, dep_ad, ev_r, dep_r, s_adi, l_adi, 0, 0, st_code, int(ev_t.get("score", 0)), int(dep_t.get("score", 0)))
                    tum_radar.append({"Spor": s_adi, "Lig": l_adi, "Mac": f"{ev_ad} vs {dep_ad}", "Durum": ev["status"]["type"]["shortDetail"], "AI En Guclu Tahmin": en_iyi["AI Tahmin Secenegi"], "Guven": f"%{en_iyi['GuvenInt']}", "GuvenInt": en_iyi["GuvenInt"]})
        st.session_state.radar_sonuclari = sorted(tum_radar, key=lambda x: x["GuvenInt"], reverse=True)
    if st.session_state.radar_sonuclari:
        radar_df = pd.DataFrame(st.session_state.radar_sonuclari).drop(columns=["GuvenInt"])
        st.success(f"Toplam {len(radar_df)} mac tarandi ve guven sirasina gore listelendi!")
        st.dataframe(radar_df, use_container_width=True, hide_index=True)
        st.download_button("Gunun Radar Raporunu Excel Indir", data=excel_dosyasi_olustur(radar_df), file_name=f"AI_Radar_{tarih}.xlsx")

else:
    r = lig_verisi_getir(yol, tarih, tarih_tireli)
    maclar = list()
    banko_havuzu = list()
    for ev in r.get("events", list()):
        mac_id = ev.get("id", "")
        comp = ev.get("competitions", [{}])[0]
        takim_listesi = comp.get("competitors", list())
        if len(takim_listesi) < 2:
            continue
        ev_t = next((t for t in takim_listesi if t["homeAway"] == "home"), takim_listesi[0])
        dep_t = next((t for t in takim_listesi if t["homeAway"] == "away"), takim_listesi[1])
        ev_ad, dep_ad = ev_t["team"]["displayName"], dep_t["team"]["displayName"]
        ev_id, dep_id = ev_t["team"].get("id", ""), dep_t["team"].get("id", "")
        ev_rec = ev_t.get("records", [{"summary": "0-0"}])[0].get("summary", "0-0")
        dep_rec = dep_t.get("records", [{"summary": "0-0"}])[0].get("summary", "0-0")
        state = ev["status"]["type"]["state"]
        durum_detay = ev["status"]["type"]["shortDetail"]
        ev_s_int = int(ev_t.get("score", 0))
        dep_s_int = int(dep_t.get("score", 0))
        if state == "in":
            durum_gosterim = f"CANLI ({durum_detay})"
            skor_gosterim = f"{ev_s_int} - {dep_s_int}"
            st.session_state.eski_skorlar[mac_id] = skor_gosterim
        elif state == "post":
            durum_gosterim = f"BITTI ({durum_detay})"
            skor_gosterim = f"{ev_s_int} - {dep_s_int}"
        else:
            durum_gosterim = durum_detay
            skor_gosterim = "vs"
        periyot_bilgisi = periyot_ve_iy_cikar(ev_t, dep_t, spor, state)
        _, ozet, en_iyi_tahmin = coklu_tahmin_motoru(ev_ad, dep_ad, ev_rec, dep_rec, spor, lig, 0, 0, state, ev_s_int, dep_s_int)
        banko_havuzu.append({"Mac": f"{ev_ad} - {dep_ad}", "Secenek": en_iyi_tahmin["AI Tahmin Secenegi"], "Guven": en_iyi_tahmin["GuvenInt"]})
        fav = bool(favori and (favori in ev_ad.lower() or favori in dep_ad.lower()))
        maclar.append({"ID": mac_id, "EvID": ev_id, "DepID": dep_id, "State": state, "EvSkorInt": ev_s_int, "DepSkorInt": dep_s_int, "MacSecim": f"{ev_ad} vs {dep_ad} ({skor_gosterim})", "Fav": fav, "Dakika / Ceyrek": durum_gosterim, "Ev Sahibi": ev_ad, "Canli Skor": skor_gosterim, "Deplasman": dep_ad, "IY / Ceyrek Skorlari": periyot_bilgisi, "Ev Form": ev_rec, "Dep Form": dep_rec, "Hizli AI Ozet": ozet})

    if maclar:
        st.subheader(f"{lig} | Gunun En Yuksek Guvenli AI Tahminleri")
        sirali_bankolar = sorted(banko_havuzu, key=lambda x: x["Guven"], reverse=True)[:3]
        b_kolonlar = st.columns(len(sirali_bankolar))
        for idx, b_item in enumerate(sirali_bankolar):
            b_kolonlar[idx].metric(label=b_item["Mac"], value=b_item["Secenek"], delta=f"Guven: %{b_item['Guven']}")
        st.divider()
        st.subheader(f"{lig} | Canli Skor, IY / Ceyrek Detaylari ve AI Analiz")
        df_ham = pd.DataFrame(maclar).sort_values(by="Fav", ascending=False)
        if durum_filtre == "Sadece Canli Maclar":
            df_ham = df_ham[df_ham["State"] == "in"]
        elif durum_filtre == "Oynanacak Maclar":
            df_ham = df_ham[df_ham["State"] == "pre"]
        elif durum_filtre == "Biten Maclar":
            df_ham = df_ham[df_ham["State"] == "post"]
        if df_ham.empty:
            st.info("Secilen durum filtresine uygun mac su an bulunmuyor.")
        else:
            gizlenecek = ["ID", "EvID", "DepID", "State", "EvSkorInt", "DepSkorInt", "MacSecim", "Fav"]
            gosterilecek_tablo = df_ham.drop(columns=gizlenecek)
            st.dataframe(gosterilecek_tablo, use_container_width=True, hide_index=True)
            st.download_button("Bu Ligin Analiz Tablosunu Excel Indir", data=excel_dosyasi_olustur(gosterilecek_tablo), file_name=f"{lig}_{tarih}.xlsx")
            st.divider()
            st.subheader("Secilen Mac Icin Detayli AI Tahmin, H2H Form ve Kadro Analizi")
            secilen_mac = st.selectbox("Incelenecek maci secin:", df_ham["MacSecim"].tolist())
            satir = df_ham[df_ham["MacSecim"] == secilen_mac].head(1).to_dict(orient="records")[0]
            ev_kadro, dep_kadro, ev_eksikler, dep_eksikler, kaynak = ai_kadro_ve_eksik_getir(yol, satir["ID"], satir["EvID"], satir["DepID"], spor)
            detayli_tahmin_satirlari, _, _ = coklu_tahmin_motoru(satir["Ev Sahibi"], satir["Deplasman"], satir["Ev Form"], satir["Dep Form"], spor, lig, len(ev_eksikler), len(dep_eksikler), satir["State"], satir["EvSkorInt"], satir["DepSkorInt"])
            st.markdown(f"Durum: {satir['Dakika / Ceyrek']}  |  Periyot / IY Detayi: {satir['IY / Ceyrek Skorlari']}")
            df_goster = pd.DataFrame(detayli_tahmin_satirlari).drop(columns=["GuvenInt"])
            st.dataframe(df_goster, use_container_width=True, hide_index=True)
            if gemini_api_key:
                with st.spinner("Gercek Yapay Zeka (Gemini) maci ve kadrolari yorumluyor..."):
                    ai_yorum = gemini_taktik_yorumu_uret(gemini_api_key, spor, lig, satir["Ev Sahibi"], satir["Deplasman"], satir["Ev Form"], satir["Dep Form"], ", ".join(ev_eksikler), ", ".join(dep_eksikler), satir["Dakika / Ceyrek"])
                    if ai_yorum:
                        st.info(ai_yorum)
    else:
        st.info("Bu tarihte mac bulunamadi. Sol menuden tarihi degistirin.")

if otomatik_yenile:
    time.sleep(15)
    st.rerun()
