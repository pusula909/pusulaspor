import json
import os
from ortak_beyin import lig_basari_bonusu_getir, sharp_piyasa_durumu_getir
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
import requests
from analiz_motoru import PusulaAnalizBeyni
try:
    from google import genai
    GEMINI_AKTIF = True
except Exception:
    GEMINI_AKTIF = False

TG_TOKEN = os.environ.get("TG_TOKEN", "").strip()
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "").strip()
GEMINI_KEY = os.environ.get("GEMINI_KEY", "").strip()
GROQ_KEY = os.environ.get("GROQ_KEY", "").strip()
beyin = PusulaAnalizBeyni(gemini_key=GEMINI_KEY, groq_key=GROQ_KEY)
suan_tr = datetime.now(timezone(timedelta(hours=3)))
tarih = suan_tr.strftime("%Y%m%d")
tarih_guzel = suan_tr.strftime("%d.%m.%Y")

alan = ".".join(("site", "api", "espn", "com"))
url_basi = "https://" + alan + "/apis/site/v2/sports/"
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
    },
    "Basketbol": {
        "NBA": "basketball/nba",
        "EuroLeague": "euroleague_resmi",
    },
}


def telegram_gonder(mesaj):
    if TG_TOKEN and TG_CHAT_ID:
        tg_adres = "https://" + "api." + "telegram.org" + "/bot" + TG_TOKEN + "/sendMessage"
        requests.post(tg_adres, data={"chat_id": TG_CHAT_ID, "text": mesaj}, timeout=10)


def _el_get(t):
    ev = list()
    try:
        h = {"User-Agent": "Mozilla/5.0", "Accept": "application/xml, text/xml"}
        yil = int(t[:4])
        ay = int(t[4:6])
        sezon_kodu = f"E{yil if ay >= 8 else yil - 1}"
        el_host = "https://api-live." + "euroleague.net/v1/"

        win_map, loss_map, res_map = {}, {}, {}
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
                    res_map[gc] = {"hs": str(hs), "ds": str(ds), "state": "post" if played else "pre"}
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
        for i in ET.fromstring(r_sch.content).findall(".//item"):
            d_raw = i.findtext("date", "").strip()
            if not d_raw:
                continue
            if datetime.strptime(d_raw, "%b %d, %Y").strftime("%Y%m%d") == t:
                h_ad = i.findtext("hometeam", "").strip()
                a_ad = i.findtext("awayteam", "").strip()
                s_time = i.findtext("startime", "20:00").strip()
                gc = i.findtext("gamecode", "").strip().replace(f"{sezon_kodu}_", "")
                info = res_map.get(gc, {"hs": "0", "ds": "0", "state": "pre"})
                ev_r = f"{win_map.get(h_ad, 0)}-{loss_map.get(h_ad, 0)}"
                dep_r = f"{win_map.get(a_ad, 0)}-{loss_map.get(a_ad, 0)}"
                ev.append({
                    "id": gc,
                    "status": {"type": {"state": info["state"], "shortDetail": s_time}},
                    "competitions": list(({
                        "competitors": list((
                            {"homeAway": "home", "team": {"displayName": h_ad}, "score": info["hs"], "records": list(({"summary": ev_r},))},
                            {"homeAway": "away", "team": {"displayName": a_ad}, "score": info["ds"], "records": list(({"summary": dep_r},))},
                        ))
                    },)),
                })
    except Exception:
        pass
    return {"events": ev}


def en_guclu_tahmini_bul(ev_ad, dep_ad, ev_rec, dep_rec, spor_turu, lig_adi):
    try:
        rapor = beyin.mac_deger_analizi(
            spor_turu=spor_turu,
            lig_adi=lig_adi,
            ev_ad=ev_ad,
            dep_ad=dep_ad,
            ev_rec=ev_rec,
            dep_rec=dep_rec,
            state="pre"
        )
        guven = rapor["guven"] if not rapor["tuzak_notu"] else 55
        etiket = f"💎 Deger: {rapor['deger_puani']}/10"
        return rapor["ana_tercih"], guven, etiket
    except Exception:
        return "Form Analizi", 55, ""

YILDIZLAR = (
    "Giannis", "Jokic", "Doncic", "Tatum", "Curry", "LeBron", "Durant", "Embiid", "Shai", "Edwards",
    "Brunson", "Mitchell", "Booker", "Davis", "Wembanyama", "Sengun", "Larkin", "Vezenkov", "Tavares",
    "Campazzo", "Hezonja", "Lessort", "Nunn", "Sloukas", "Icardi", "Osimhen", "Dzeko", "Tadic", "Immobile",
    "Rafa", "Haaland", "Salah", "Mbappe", "Vinicius", "Bellingham", "Kane", "Yamal", "Lewandowski", "Palmer", "Saka"
)


def piyasa_ve_sakatlik_kontrol(lig_yolu, mac_id):
    sakat_ceza = 0
    sakat_notlar = list()
    piyasa_ozet = ""
    hava_uyari = ""
    if lig_yolu == "euroleague_resmi" or "/" not in lig_yolu or not mac_id:
        return sakat_ceza, sakat_notlar, piyasa_ozet, hava_uyari
    try:
        j = requests.get(f"{url_basi}{lig_yolu}/summary?event={mac_id}", headers=basliklar, timeout=6).json()
        for grp in j.get("injuries", list()):
            t_ad = grp.get("team", {}).get("displayName", "")
            for inj in grp.get("injuries", list()):
                durum = inj.get("status", "")
                oyuncu = inj.get("athlete", {}).get("displayName", "")
                if durum in ("Out", "Doubtful") and oyuncu:
                    if any(y.lower() in oyuncu.lower() for y in YILDIZLAR):
                        sakat_ceza += 8
                        sakat_notlar.append(f"{t_ad}: {oyuncu} ({durum})")
                    else:
                        sakat_ceza += 2
        for p in j.get("pickcenter", list())[:1]:
            ou = p.get("overUnder", "")
            det = p.get("details", "")
            if ou or det:
                piyasa_ozet = f"Piyasa: {det} | Barem: {ou}"

        w_obj = j.get("gameInfo", {}).get("weather", {})
        w_durum = str(w_obj.get("displayValue", "")).lower()
        if any(k in w_durum for k in ("rain", "storm", "snow", "heavy", "wind")):
            hava_uyari = f"Agir Hava/Zemin ({w_obj.get('displayValue', '')})"
    except Exception:
        pass
    return sakat_ceza, sakat_notlar[:3], piyasa_ozet, hava_uyari


def hakem_ai_tuzak_ele(aday_listesi):
    if not aday_listesi:
        return aday_listesi
    aday_metin = "\n".join(
        list(f"- ID:{m['id']} | [{m['lig']}] {m['mac']} -> {m['tahmin']} (Guven:%{m['guven']}) | {m.get('piyasa', '')} | Eksikler: {', '.join(m.get('eksikler', [])) or 'Yok'}" for m in aday_listesi)
    )
    soru = (
        "Sen profesyonel bir spor risk analistisin. Asagidaki mac adaylarini incele. "
        "Yildiz eksigi olan, tuzak olabilecek veya piyasa cizgisiyle celisen maclari ELE. "
        "Sadece en saglam, en dusuk riskli EN FAZLA 4 macin ID numarasini ve her biri icin 1 cumlelik secim gerekcesini yaz.\n"
        "Format TAM OLARAK soyle olsun:\n"
        "ID:12345 | Gerekce: ...\n\n"
        f"Adaylar:\n{aday_metin}"
    )
    yanit_metin = ""
    if GEMINI_AKTIF and GEMINI_KEY:
        try:
            client = genai.Client(api_key=GEMINI_KEY, http_options={"api_version": "v1beta"})
            for m_ad in ("gemini-2.5-flash", "gemini-2.5-flash-lite"):
                try:
                    y = client.models.generate_content(model=m_ad, contents=soru)
                    if y and y.text:
                        yanit_metin = y.text.strip()
                        break
                except Exception:
                    continue
        except Exception:
            pass

    if not yanit_metin:
        return aday_listesi[:4]

    secilenler = list()
    for satir in yanit_metin.splitlines():
        if "ID:" in satir:
            for aday in aday_listesi:
                if f"ID:{aday['id']}" in satir and aday not in secilenler:
                    gerekce = satir.split("Gerekce:")[-1].strip() if "Gerekce:" in satir else ""
                    aday["ai_gerekce"] = gerekce
                    secilenler.append(aday)
    return secilenler[:4] if secilenler else aday_listesi[:4]


def bulten_olustur_ve_gonder():
    firsatlar = list()
    for s_adi, lig_sozluk in TUM_LIGLER.items():
        for l_adi, l_yolu in lig_sozluk.items():
            try:
                resp = (
                    _el_get(tarih)
                    if l_yolu == "euroleague_resmi"
                    else requests.get(f"{url_basi}{l_yolu}/scoreboard?dates={tarih}", headers=basliklar, timeout=8).json()
                )
                for ev in resp.get("events", list()):
                    comp = ev.get("competitions", list()).pop(0)
                    t_list = comp.get("competitors", list())
                    t1, t2 = t_list.pop(0), t_list.pop(0)
                    ev_t = t1 if t1["homeAway"] == "home" else t2
                    dep_t = t2 if t1["homeAway"] == "home" else t1
                    ev_ad, dep_ad = ev_t["team"]["displayName"], dep_t["team"]["displayName"]
                    ev_r = ev_t.get("records", list()).pop(0).get("summary", "1-1") if ev_t.get("records") else "1-1"
                    dep_r = dep_t.get("records", list()).pop(0).get("summary", "1-1") if dep_t.get("records") else "1-1"
                    saat = ev.get("status", {}).get("type", {}).get("shortDetail", "")
                    mac_id = str(ev.get("id", ""))
                    tahmin, guven, deger = en_guclu_tahmini_bul(ev_ad, dep_ad, ev_r, dep_r, s_adi, l_adi)
                    firsatlar.append({
                        "id": mac_id,
                        "yol": l_yolu,
                        "tarih": tarih,
                        "tarih_guzel": tarih_guzel,
                        "lig": l_adi,
                        "ev": ev_ad,
                        "dep": dep_ad,
                        "mac": f"{ev_ad} - {dep_ad}",
                        "saat": saat,
                        "tahmin": tahmin,
                        "guven": guven,
                        "deger": deger,
                    })
            except Exception:
                pass

    en_guclu_adaylar = sorted(firsatlar, key=lambda x: x["guven"], reverse=True)[:10]
    filtrelenmis_adaylar = list()
    for aday in en_guclu_adaylar:
        ceza, eksikler, piyasa, hava = piyasa_ve_sakatlik_kontrol(aday["yol"], aday["id"])
        if hava and "UST" in aday["tahmin"]:
            aday["tahmin"] = "Toplam 2.5 ALT"
            piyasa = f"{piyasa} | 🌧️ {hava}" if piyasa else f"🌧️ {hava}"
        lig_bonus = lig_basari_bonusu_getir(aday["lig"])
        sharp_bonus, sharp_not = sharp_piyasa_durumu_getir(aday["id"])
        aday["guven"] = max(50, min(96, aday["guven"] - ceza + lig_bonus + sharp_bonus))
     if sharp_not:
         piyasa = f"{piyasa} | 🦈 {sharp_not}" if piyasa else f"🦈 {sharp_not}"
        aday["eksikler"] = eksikler
        aday["piyasa"] = piyasa
        if aday["guven"] >= 62:
            filtrelenmis_adaylar.append(aday)

    en_iyiler = hakem_ai_tuzak_ele(sorted(filtrelenmis_adaylar, key=lambda x: x["guven"], reverse=True)[:8])
    with open("son_bulten.json", "w", encoding="utf-8") as f:
        json.dump(en_iyiler, f, ensure_ascii=False, indent=2)

    if not en_iyiler:
        mesaj = f"📅 {tarih_guzel} PusulaSpor Akilli Filtre Bulteni\nBugun tuzak filtresini gecen yuksek guvenli mac bulunamadi."
    else:
        satirlar = list((f"🏆 {tarih_guzel} PUSULASPOR AKILLI FILTRE BANKOLARI\n",))
        for idx, m in enumerate(en_iyiler, 1):
            etiket_ek = f" | {m['deger']}" if m.get("deger") else ""
            gerekce_ek = f"\n   🧠 Hakem AI: {m['ai_gerekce']}" if m.get("ai_gerekce") else ""
            piyasa_ek = f"\n   💰 {m['piyasa']}" if m.get("piyasa") else ""
            satirlar.append(
                f"{idx}. [{m['lig']}] {m['mac']} ({m['saat']})\n"
                f"   👉 Tahmin: {m['tahmin']} (Net Guven: %{m['guven']}){etiket_ek}{piyasa_ek}{gerekce_ek}"
            )
        mesaj = "\n".join(satirlar)

    telegram_gonder(mesaj)

def sonuc_raporu_kontrol_et():
    if not os.path.exists("son_bulten.json"):
        return
    with open("son_bulten.json", "r", encoding="utf-8") as f:
        kayitli_maclar = json.load(f)

    if not kayitli_maclar:
        return

    arsiv = list()
    if os.path.exists("haftalik_arsiv.json"):
        try:
            with open("haftalik_arsiv.json", "r", encoding="utf-8") as f:
                arsiv = json.load(f)
        except Exception:
            arsiv = list()

    rapor_tarih = kayitli_maclar.get("tarih_guzel", tarih_guzel)
    satirlar = list((f"📊 {rapor_tarih} PUSULASPOR AI GECE SONUC KARNESI\n",))
    tuttu_sayisi = 0
    biten_sayisi = 0

    for idx, m in enumerate(kayitli_maclar, 1):
        ev_s, dep_s, st_code = 0, 0, "pre"
        try:
            resp = (
                _el_get(m["tarih"])
                if m["yol"] == "euroleague_resmi"
                else requests.get(f"{url_basi}{m['yol']}/scoreboard?dates={m['tarih']}", headers=basliklar, timeout=8).json()
            )
            for ev in resp.get("events", list()):
                if str(ev.get("id", "")) == str(m["id"]):
                    st_code = ev.get("status", {}).get("type", {}).get("state", "pre")
                    comp = ev.get("competitions", list()).pop(0)
                    for t_obj in comp.get("competitors", list()):
                        if t_obj.get("homeAway") == "home":
                            ev_s = int(float(t_obj.get("score", 0) or 0))
                        else:
                            dep_s = int(float(t_obj.get("score", 0) or 0))
                    break
        except Exception:
            pass

        if st_code != "post":
            satirlar.append(f"{idx}. [{m['lig']}] {m['mac']}\n   ⏳ Mac Henuz Tamamlanmadi ({ev_s}-{dep_s})")
            continue

        biten_sayisi += 1
        t = m["tahmin"]
        top_s = ev_s + dep_s
        tuttu = False

        if "(MS 1)" in t and ev_s > dep_s:
            tuttu = True
        elif "(MS 2)" in t and dep_s > ev_s:
            tuttu = True
        elif "(MS 0)" in t and ev_s >= dep_s:
            tuttu = True
        elif "KG VAR" in t and ev_s > 0 and dep_s > 0:
            tuttu = True
        elif "UST" in t:
            barem = float(list(x for x in t.split() if "." in x).pop(0))
            hedef = ev_s if t.startswith(m["ev"]) else (dep_s if t.startswith(m["dep"]) else top_s)
            if hedef > barem:
                tuttu = True
        elif "ALT" in t:
            barem = float(list(x for x in t.split() if "." in x).pop(0))
            hedef = ev_s if t.startswith(m["ev"]) else (dep_s if t.startswith(m["dep"]) else top_s)
            if hedef < barem:
                tuttu = True

        if tuttu:
            tuttu_sayisi += 1
            ikon = "✅ TUTTU"
        else:
            ikon = "❌ YATTI"

        arsiv.append({"tarih": rapor_tarih, "lig": m["lig"], "tuttu": tuttu})
        satirlar.append(f"{idx}. [{m['lig']}] {m['mac']} -> Skor: {ev_s}-{dep_s}\n   🎯 {t} | {ikon}")

    with open("haftalik_arsiv.json", "w", encoding="utf-8") as f:
        json.dump(arsiv[-70:], f, ensure_ascii=False, indent=2)

    if biten_sayisi > 0:
        oran = int((tuttu_sayisi / biten_sayisi) * 100)
        satirlar.append(f"\n📈 GENEL BASARI: {biten_sayisi} Macta {tuttu_sayisi} Isabet (%{oran})")
    telegram_gonder("\n".join(satirlar))

    if suan_tr.weekday() == 0 and len(arsiv) >= 5:
        lig_ozet = {}
        for kayit in arsiv[-35:]:
            l_ad = kayit["lig"]
            if l_ad not in lig_ozet:
                lig_ozet[l_ad] = {"top": 0, "hit": 0}
            lig_ozet[l_ad]["top"] += 1
            if kayit["tuttu"]:
                lig_ozet[l_ad]["hit"] += 1
        h_satir = list(("🏅 HAFTALIK LIG BAZLI BASARI KARNESI\n",))
        for l_ad, v in lig_ozet.items():
            yuzde = int((v["hit"] / v["top"]) * 100)
            h_satir.append(f"• {l_ad}: {v['top']} Macta {v['hit']} Isabet (%{yuzde})")
        telegram_gonder("\n".join(h_satir))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv.pop(1) == "rapor":
        sonuc_raporu_kontrol_et()
    else:
        bulten_olustur_ve_gonder()
