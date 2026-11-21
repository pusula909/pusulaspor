import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
import requests

try:
    from google import genai
    GEMINI_AKTIF = True
except Exception:
    GEMINI_AKTIF = False

TG_TOKEN = os.environ.get("TG_TOKEN", "").strip()
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "").strip()
GEMINI_KEY = os.environ.get("GEMINI_KEY", "").strip()
GROQ_KEY = os.environ.get("GROQ_KEY", "").strip()

suan_tr = datetime.now(timezone(timedelta(hours=3)))
tarih = suan_tr.strftime("%Y%m%d")
saat_str = suan_tr.strftime("%H:%M")

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


def cift_motor_ai_sor(soru):
    if GEMINI_AKTIF and GEMINI_KEY:
        try:
            client = genai.Client(api_key=GEMINI_KEY, http_options={"api_version": "v1beta"})
            for m in ("gemini-2.5-flash", "gemini-2.5-flash-lite"):
                try:
                    yanit = client.models.generate_content(model=m, contents=soru)
                    if yanit and yanit.text:
                        return yanit.text.strip()
                except Exception:
                    continue
        except Exception:
            pass

    if GROQ_KEY:
        g_base = "https://" + "api." + "groq.com" + "/openai/v1"
        g_headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
        denenecek_modeller = ["llama-3.3-70b-versatile", "openai/gpt-oss-120b", "qwen/qwen3-32b"]

        for aktif_model in denenecek_modeller[:6]:
            try:
                g_resp = requests.post(
                    f"{g_base}/chat/completions",
                    headers=g_headers,
                    json={
                        "model": aktif_model,
                        "messages": [{"role": "user", "content": soru}],
                        "temperature": 0.3,
                        "max_tokens": 420,
                    },
                    timeout=12,
                ).json()
                if "choices" in g_resp and len(g_resp["choices"]) > 0:
                    yanit_metin = g_resp["choices"].pop(0).get("message", {}).get("content", "").strip()
                    if yanit_metin:
                        return yanit_metin
            except Exception:
                continue
    return ""


def canli_oyuncu_ve_olay_cek(mac_id, lig_yolu, sezon_kodu):
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
                    if o.get("IsPlaying", 0) == 1 and isim:
                        sahadakiler.append(f"{isim} ({pts}s, {fls}f)")
                    if fls >= 3 and isim:
                        faul_problemi.append(f"{isim} ({fls} faul)")
                if sahadakiler:
                    detay_ozet.append(f"{t_ad} Sahadaki 5: {', '.join(sahadakiler[:5])}")
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
    return " | ".join(detay_ozet) if detay_ozet else "Standart mac akisi"


def ai_bas_analist_karari(spor_turu, lig_adi, ev_ad, dep_ad, ev_s, dep_s, detay_sure, ev_rec, dep_rec, saha_detay):
    soru = (
        f"Sen dunya capinda bir {spor_turu} Bas Analisti ve Basantrenor Danismanisin. "
        f"SIKI KURAL: Hafizandaki eski yillarin kadrolarini (ornegin eski takimlarina gitmis yildizlari) ASLA yazma! Sadece asagidaki canli saha verisindeki isimleri veya genel takim oyununu kullan. "
        f"Duz istatistik ezberine (ilk yari cok sayi/gol oldu kesin ust biter gibi kliselere) ASLA dusme! "
        f"Canli Mac: {lig_adi} | {ev_ad} ({ev_rec}) {ev_s} - {dep_s} {dep_ad} ({dep_rec}) | Sure: {detay_sure}. "
        f"Canli Saha, Oyuncu, Faul, Kart ve Rotasyon Verileri: {saha_detay}. "
        f"Analiz Kriterlerin: Fark acildiysa kocun yildizlari kenara alip yedeklere donme (garbage time / tempo dususu) ihtimalini, "
        f"ilk yari anormal tempo ciktiysa 2. yarida savunma sertligiyle baremin tersine donup donmeyecegini ve faul/kart etkisini hesapla. "
        f"Ciktiyi Turkce, kisa ve ikna edici sekilde TAM OLARAK su 2 satirla yaz:\n"
        f"🎯 AI Karari: (Tek net tahmin ve barem)\n"
        f"🧠 Koc & Saha Gerekcesi: (En fazla 2 cumleyle neden bu ters kose veya nokta atisi karari verdigin)"
    )
    return cift_motor_ai_sor(soru)


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
        suan_naive = suan_tr.replace(tzinfo=None)
        for i in ET.fromstring(r_sch.content).findall(".//item"):
            d_raw = i.findtext("date", "").strip()
            if not d_raw:
                continue
            if datetime.strptime(d_raw, "%b %d, %Y").strftime("%Y%m%d") == t:
                h_ad = i.findtext("hometeam", "").strip()
                a_ad = i.findtext("awayteam", "").strip()
                s_time = i.findtext("startime", "20:00").strip()
                gc = i.findtext("gamecode", "").strip().replace(f"{sezon_kodu}_", "")

                hs, ds, st_code, detay = "0", "0", "pre", s_time
                if gc in res_map:
                    hs, ds = res_map[gc]["hs"], res_map[gc]["ds"]
                    if res_map[gc]["state"] == "post":
                        st_code = "post"
                    elif int(hs) > 0 or int(ds) > 0:
                        st_code = "in"
                        detay = "Canli"

                if st_code == "pre":
                    try:
                        m_saat = datetime.strptime(f"{d_raw} {s_time}", "%b %d, %Y %H:%M") + timedelta(hours=2)
                        if m_saat <= suan_naive <= m_saat + timedelta(hours=3):
                            st_code = "in"
                            detay = "Canli"
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
                            tot_a, tot_b, q_say = 0, 0, 0
                            for q_idx in range(1, 5):
                                qa = ev_q_dict.get(f"Quarter{q_idx}")
                                qb = dep_q_dict.get(f"Quarter{q_idx}")
                                if qa is not None and qb is not None and (int(qa) > 0 or int(qb) > 0 or q_idx == 1):
                                    tot_a += int(qa)
                                    tot_b += int(qb)
                                    q_say += 1
                            if tot_a > 0 or tot_b > 0:
                                hs, ds = str(tot_a), str(tot_b)
                            if st_code == "in":
                                detay = f"Canli (Q{q_say if q_say else 1})"
                    except Exception:
                        pass

                ev_r = f"{win_map.get(h_ad, 0)}-{loss_map.get(h_ad, 0)}"
                dep_r = f"{win_map.get(a_ad, 0)}-{loss_map.get(a_ad, 0)}"
                ev.append({
                    "id": gc,
                    "status": {"type": {"state": st_code, "shortDetail": detay}},
                    "competitions": list(({
                        "competitors": list((
                            {"homeAway": "home", "team": {"displayName": h_ad}, "score": hs, "records": list(({"summary": ev_r},))},
                            {"homeAway": "away", "team": {"displayName": a_ad}, "score": ds, "records": list(({"summary": dep_r},))},
                        ))
                    },)),
                })
    except Exception:
        pass
    return {"events": ev}


def telegram_komutlari_isle(hafiza, canli_ozet_listesi, canli_detay_objeleri):
    if not TG_TOKEN or not TG_CHAT_ID:
        return
    son_update_id = hafiza.get("son_update_id", 0)
    istenen_komutlar = set()
    try:
        upd_url = "https://" + "api." + "telegram.org" + "/bot" + TG_TOKEN + f"/getUpdates?offset={son_update_id + 1}&timeout=3"
        r = requests.get(upd_url, timeout=8).json()
        for item in r.get("result", list()):
            uid = item.get("update_id", 0)
            if uid > son_update_id:
                son_update_id = uid
            msg = item.get("message", {})
            chat_id = str(msg.get("chat", {}).get("id", ""))
            metin = msg.get("text", "").strip().lower()
            if chat_id != str(TG_CHAT_ID):
                continue
            if "/canli" in metin:
                istenen_komutlar.add("canli")
            if "/bulten" in metin:
                istenen_komutlar.add("bulten")
            if "/karne" in metin:
                istenen_komutlar.add("karne")
            if "/yardim" in metin or "/start" in metin:
                istenen_komutlar.add("yardim")

        if "canli" in istenen_komutlar:
            if canli_ozet_listesi:
                mesaj_parcalari = list((f"📺 ANLIK CANLI MACLAR & AI BAS ANALIST ({saat_str})\n",))
                mesaj_parcalari.extend(canli_ozet_listesi[:12])
                if canli_detay_objeleri:
                    ilk_m = canli_detay_objeleri.pop(0)
                    ai_yorum = ai_bas_analist_karari(
                        ilk_m["spor"], ilk_m["lig"], ilk_m["ev"], ilk_m["dep"],
                        ilk_m["ev_s"], ilk_m["dep_s"], ilk_m["sure"], ilk_m["ev_r"], ilk_m["dep_r"], ilk_m["saha"]
                    )
                    if ai_yorum:
                        mesaj_parcalari.append(f"\n📌 One Cikan Mac Analizi ({ilk_m['ev']} - {ilk_m['dep']}):\n{ai_yorum}")
                telegram_gonder("\n".join(mesaj_parcalari))
            else:
                telegram_gonder("Su an canli oynanan mac bulunmuyor.")

        if "bulten" in istenen_komutlar:
            if os.path.exists("son_bulten.json"):
                with open("son_bulten.json", "r", encoding="utf-8") as f:
                    b_list = json.load(f)
                if b_list:
                 satir = list(("🏆 KAYITLI GUNUN BULTENI\n",))
                 for i, m in enumerate(b_list, 1):
                     satir.append(f"{i}. [{m['lig']}] {m['mac']} -> {m['tahmin']} (%{m['guven']})")
                 telegram_gonder("\n".join(satir))
            else:
                   telegram_gonder("Henuz kayitli gunluk bulten yok.")
        
                
               

        if "karne" in istenen_komutlar:
            if os.path.exists("haftalik_arsiv.json"):
                with open("haftalik_arsiv.json", "r", encoding="utf-8") as f:
                    arsiv = json.load(f)
                if arsiv:
                    lig_ozet = {}
                    for k in arsiv:
                        l_ad = k["lig"]
                        if l_ad not in lig_ozet:
                            lig_ozet[l_ad] = {"top": 0, "hit": 0}
                        lig_ozet[l_ad]["top"] += 1
                        if k["tuttu"]:
                            lig_ozet[l_ad]["hit"] += 1
                    k_satir = list(("🏅 HAFTALIK BASARI KARNESI\n",))
                    for l_ad, v in lig_ozet.items():
                        yuzde = int((v["hit"] / v["top"]) * 100)
                        k_satir.append(f"• {l_ad}: {v['top']} Macta {v['hit']} Isabet (%{yuzde})")
                    telegram_gonder("\n".join(k_satir))
                else:
                    telegram_gonder("Haftalik karne icin gece sonuclarinin kaydi bekleniyor.")
            else:
                telegram_gonder("Haftalik karne icin gece sonuclarinin kaydi bekleniyor.")

        if "yardim" in istenen_komutlar:
            telegram_gonder("🤖 PusulaSpor Komutlari:\n/canli - Anlik skorlar + AI Bas Analist yorumu\n/bulten - Gunun AI bankolari\n/karne - Haftalik basari orani")
    except Exception:
        pass
    hafiza["son_update_id"] = son_update_id
MAC_ONU_YILDIZLAR = (
    "Giannis", "Jokic", "Doncic", "Tatum", "Curry", "LeBron", "Durant", "Embiid", "Shai", "Edwards",
    "Brunson", "Mitchell", "Booker", "Davis", "Wembanyama", "Sengun", "Larkin", "Vezenkov", "Tavares",
    "Campazzo", "Hezonja", "Lessort", "Nunn", "Sloukas", "Icardi", "Osimhen", "Dzeko", "Tadic", "Immobile",
    "Rafa", "Haaland", "Salah", "Mbappe", "Vinicius", "Bellingham", "Kane", "Yamal", "Lewandowski", "Palmer", "Saka"
)


def maca_1_saat_kala_kadro_kontrol(gonderilenler):
    if not os.path.exists("son_bulten.json"):
        return
    try:
        with open("son_bulten.json", "r", encoding="utf-8") as f:
            bulten_maclar = json.load(f)
    except Exception:
        return

    for m in bulten_maclar:
        mac_id = str(m.get("id", ""))
        lig_yolu = m.get("yol", "")
        alarm_anahtar = f"KADRO1SAAT_{m.get('tarih', tarih)}_{mac_id}"
        if not mac_id or lig_yolu == "euroleague_resmi" or "/" not in lig_yolu or alarm_anahtar in gonderilenler:
            continue

        try:
            j = requests.get(f"{url_basi}{lig_yolu}/summary?event={mac_id}", headers=basliklar, timeout=6).json()
            header_comp = j.get("header", {}).get("competitions", list(({},))).pop(0)
            st_code = header_comp.get("status", {}).get("type", {}).get("state", "pre")
            if st_code != "pre":
                continue

            mac_tarih_str = header_comp.get("date", "")
            if not mac_tarih_str:
                continue

            mac_zamani_utc = datetime.strptime(mac_tarih_str[:16], "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
            kalan_dakika = (mac_zamani_utc - suan_tr.astimezone(timezone.utc)).total_seconds() / 60

            if 10 <= kalan_dakika <= 75:
                eksik_yildizlar = list()
                for grp in j.get("injuries", list()):
                    t_ad = grp.get("team", {}).get("displayName", "")
                    for inj in grp.get("injuries", list()):
                        durum = inj.get("status", "")
                        oyuncu = inj.get("athlete", {}).get("displayName", "")
                        if durum in ("Out", "Doubtful") and oyuncu:
                            if any(y.lower() in oyuncu.lower() for y in MAC_ONU_YILDIZLAR):
                                eksik_yildizlar.append(f"{t_ad}: {oyuncu} ({durum})")

                gonderilenler.add(alarm_anahtar)
                if eksik_yildizlar:
                    telegram_gonder(
                        f"⚠️ SON DAKIKA KADRO ALARMI (Maca ~{int(kalan_dakika)} Dk Kala)\n"
                        f"🏆 [{m.get('lig', '')}] {m.get('mac', '')}\n"
                        f"🎯 Bulten Tahmini: {m.get('tahmin', '')}\n"
                        f"❌ Kadroda Yok / Supheli: {', '.join(eksik_yildizlar)}\n"
                        f"💡 Dikkat: Yildiz oyuncu eksigi nedeniyle bu maci tekrar gozden gecir!"
                    )
        except Exception:
            pass
maca_1_saat_kala_kadro_kontrol(gonderilenler)            
def bulten_anlik_sonuc_kontrol(gonderilenler):
    if not os.path.exists("son_bulten.json"):
        return
    try:
        with open("son_bulten.json", "r", encoding="utf-8") as f:
            kayitli_maclar = json.load(f)
    except Exception:
        return

    if not kayitli_maclar:
        return

    arsiv = list()
    if os.path.exists("haftalik_arsiv.json"):
        try:
            with open("haftalik_arsiv.json", "r", encoding="utf-8") as f:
                arsiv = json.load(f)
        except Exception:
            arsiv = list()

    arsiv_degisti = False
    for m in kayitli_maclar:
        mac_id = str(m.get("id", ""))
        sonuc_anahtari = f"SONUC_{m.get('tarih', tarih)}_{mac_id}"
        if not mac_id or sonuc_anahtari in gonderilenler:
            continue

        ev_s, dep_s, st_code = 0, 0, "pre"
        try:
            resp = (
                _el_get(m["tarih"])
                if m["yol"] == "euroleague_resmi"
                else requests.get(f"{url_basi}{m['yol']}/scoreboard?dates={m['tarih']}", headers=basliklar, timeout=8).json()
            )
            for ev in resp.get("events", list()):
                if str(ev.get("id", "")) == mac_id:
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
            continue

        t = m.get("tahmin", "")
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
            barem_list = list(x for x in t.split() if "." in x)
            if barem_list:
                barem = float(barem_list.pop(0))
                hedef = ev_s if t.startswith(m.get("ev", "")) else (dep_s if t.startswith(m.get("dep", "")) else top_s)
                if hedef > barem:
                    tuttu = True
        elif "ALT" in t:
            barem_list = list(x for x in t.split() if "." in x)
            if barem_list:
                barem = float(barem_list.pop(0))
                hedef = ev_s if t.startswith(m.get("ev", "")) else (dep_s if t.startswith(m.get("dep", "")) else top_s)
                if hedef < barem:
                    tuttu = True

        gonderilenler.add(sonuc_anahtari)
        durum_baslik = "✅ TAHMIN TUTTU!" if tuttu else "❌ TAHMIN YATTI"
        arsiv.append({
            "tarih": m.get("tarih_guzel", suan_tr.strftime("%d.%m.%Y")),
            "lig": m.get("lig", "Genel"),
            "mac": m.get("mac", ""),
            "tahmin": t,
            "skor": f"{ev_s}-{dep_s}",
            "tuttu": tuttu
        })
        arsiv_degisti = True

        telegram_gonder(
            f"{durum_baslik}\n"
            f"🏆 [{m.get('lig', '')}] {m.get('mac', '')}\n"
            f"🎯 Tahmin: {t} (Guven: %{m.get('guven', '')})\n"
            f"🏁 Mac Sonucu: {ev_s} - {dep_s}"
        )

    if arsiv_degisti:
        with open("haftalik_arsiv.json", "w", encoding="utf-8") as f:
            json.dump(arsiv[-150:], f, ensure_ascii=False, indent=2)
def canli_maclari_tara():
    hafiza = {"tarih": tarih, "uyarilar": list(), "son_update_id": 0}
    if os.path.exists("canli_uyarilar.json"):
        try:
            with open("canli_uyarilar.json", "r", encoding="utf-8") as f:
                eski = json.load(f)
                hafiza["son_update_id"] = eski.get("son_update_id", 0)
                if eski.get("tarih") == tarih:
                    hafiza["uyarilar"] = eski.get("uyarilar", list())
        except Exception:
            pass

    gonderilenler = set(hafiza.get("uyarilar", list()))
    yeni_mesajlar = list()
    canli_ozet_listesi = list()
    canli_detay_objeleri = list()
    sezon_kodu = f"E{suan_tr.year if suan_tr.month >= 8 else suan_tr.year - 1}"

    for s_adi, lig_sozluk in TUM_LIGLER.items():
        for l_adi, l_yolu in lig_sozluk.items():
            try:
                resp = (
                    _el_get(tarih)
                    if l_yolu == "euroleague_resmi"
                    else requests.get(f"{url_basi}{l_yolu}/scoreboard?dates={tarih}", headers=basliklar, timeout=8).json()
                )
                for ev in resp.get("events", list()):
                    st_code = ev.get("status", {}).get("type", {}).get("state", "pre")
                    if st_code != "in":
                        continue

                    mac_id = str(ev.get("id", ""))
                    detay_sure = ev.get("status", {}).get("type", {}).get("shortDetail", "")
                    comp = ev.get("competitions", list()).pop(0)
                    t_list = comp.get("competitors", list())
                    t1, t2 = t_list.pop(0), t_list.pop(0)
                    ev_t = t1 if t1["homeAway"] == "home" else t2
                    dep_t = t2 if t1["homeAway"] == "home" else t1

                    ev_ad, dep_ad = ev_t["team"]["displayName"], dep_t["team"]["displayName"]
                    ev_s = int(float(ev_t.get("score", 0) or 0))
                    dep_s = int(float(dep_t.get("score", 0) or 0))
                    canli_ozet_listesi.append(f"• [{l_adi}] {ev_ad} {ev_s}-{dep_s} {dep_ad} ({detay_sure})")

                    ev_rec = ev_t.get("records", list()).pop(0).get("summary", "1-1") if ev_t.get("records") else "1-1"
                    dep_rec = dep_t.get("records", list()).pop(0).get("summary", "1-1") if dep_t.get("records") else "1-1"

                    ev_p = list(int(x) for x in ev_rec.split("-"))
                    dep_p = list(int(x) for x in dep_rec.split("-"))
                    ev_g = ev_p.pop(0) / (sum(ev_p) if sum(ev_p) > 0 else 1)
                    dep_g = dep_p.pop(0) / (sum(dep_p) if sum(dep_p) > 0 else 1)
                    top_s = ev_s + dep_s
                    fark = abs(ev_s - dep_s)

                    saha_bilgisi = canli_oyuncu_ve_olay_cek(mac_id, l_yolu, sezon_kodu)
                    canli_detay_objeleri.append({
                        "spor": s_adi, "lig": l_adi, "ev": ev_ad, "dep": dep_ad,
                        "ev_s": ev_s, "dep_s": dep_s, "sure": detay_sure,
                        "ev_r": ev_rec, "dep_r": dep_rec, "saha": saha_bilgisi
                    })

                    uyari_tipi = ""
                    if s_adi == "Basketbol":
                        if ("Q2" in detay_sure or "Half" in detay_sure or "2C" in detay_sure) and top_s >= 84:
                            uyari_tipi = "🔥 YUKSEK TEMPO / ROTASYON ANALIZI"
                        elif ("Q4" in detay_sure or "4C" in detay_sure or "OT" in detay_sure) and fark <= 6:
                            uyari_tipi = "⏳ CRUNCH TIME (SON CEYREK KARARI)"
                        elif "Q4" not in detay_sure and "4C" not in detay_sure and ev_g >= 0.65 and 6 <= (dep_s - ev_s) <= 14:
                            uyari_tipi = f"🔥 FAVORI GERIDE ({ev_ad} Takipte)"
                        elif "Q4" not in detay_sure and "4C" not in detay_sure and dep_g >= 0.65 and 6 <= (ev_s - dep_s) <= 14:
                            uyari_tipi = f"🔥 FAVORI GERIDE ({dep_ad} Takipte)"
                    else:
                        rakamlar = "".join(c for c in detay_sure if c.isdigit())
                        dk = int(rakamlar) if rakamlar else 0
                        if dk >= 75 and fark <= 1 and (ev_g >= 0.58 or dep_g >= 0.58):
                            baskili = ev_ad if ev_g >= dep_g else dep_ad
                            uyari_tipi = f"⏳ SON DAKIKA BASKI ({baskili})"
                        elif ("45" in detay_sure or "Half" in detay_sure or "HT" in detay_sure) and top_s >= 2:
                            uyari_tipi = "🔥 GOLLU TEMPO ANALIZI"
                        elif ("45" in detay_sure or "HT" in detay_sure) and top_s == 0 and (ev_g >= 0.60 or dep_g >= 0.60):
                            uyari_tipi = "🔥 IY 0-0 (2. YARI PLANI)"

                    if uyari_tipi:
                        anahtar = f"{mac_id}_{uyari_tipi}"
                        if anahtar not in gonderilenler:
                            gonderilenler.add(anahtar)
                            ai_analiz = ai_bas_analist_karari(s_adi, l_adi, ev_ad, dep_ad, ev_s, dep_s, detay_sure, ev_rec, dep_rec, saha_bilgisi)
                            ek_yorum = f"\n{ai_analiz}" if ai_analiz else ""
                            yeni_mesajlar.append(f"• [{l_adi}] {ev_ad} {ev_s}-{dep_s} {dep_ad} ({detay_sure})\n  👉 {uyari_tipi}{ek_yorum}")
            except Exception:
                pass

    if yeni_mesajlar:
        baslik = f"🚨 PUSULASPOR AI CANLI BAS ANALIST RAPORU ({saat_str})\n\n"
        telegram_gonder(baslik + "\n\n".join(yeni_mesajlar[:4]))
    bulten_anlik_sonuc_kontrol(gonderilenler)
    telegram_komutlari_isle(hafiza, canli_ozet_listesi, canli_detay_objeleri)

    hafiza["uyarilar"] = list(gonderilenler)
    with open("canli_uyarilar.json", "w", encoding="utf-8") as f:
        json.dump(hafiza, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    canli_maclari_tara()
