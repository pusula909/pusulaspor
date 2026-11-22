import json
import os
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
    deger_raporu = beyin.mac_deger_analizi(
        spor_turu=spor_turu,
        lig_adi=lig_adi,
        ev_ad=ev_ad,
        dep_ad=dep_ad,
        ev_rec=ev_rec,
        dep_rec=dep_rec,
        state="in",
        ev_skor=ev_s,
        dep_skor=dep_s,
        detay_sure=detay_sure
    )
    analiz_metni = (
        f"Ana Tercih: {deger_raporu['ana_tercih']} (Guven: %{deger_raporu['guven']}) | "
        f"Barem: {deger_raporu['barem_tercih']} | Deger Puani: {deger_raporu['deger_puani']}/10 | "
        f"Tuzak Notu: {deger_raporu['tuzak_notu'] or 'Temiz'}"
    )
    ai_onay = beyin.ai_karar_ve_onay(spor_turu, lig_adi, ev_ad, dep_ad, analiz_metni, saha_detay)
    ust_baslik = f"💎 Deger Puani: {deger_raporu['deger_puani']}/10 | {deger_raporu['ana_tercih']}"
    return f"{ust_baslik}\n{ai_onay}" if ai_onay else ust_baslik


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

def tek_takim_derin_analiz(aranan_takim):
    aranan = aranan_takim.strip().lower()
    if len(aranan) < 3:
        return "Lutfen en az 3 harfli bir takim adi yazin (Ornek: /analiz Lakers)"

    for s_adi, lig_sozluk in TUM_LIGLER.items():
        for l_adi, l_yolu in lig_sozluk.items():
            try:
                resp = (
                    _el_get(tarih)
                    if l_yolu == "euroleague_resmi"
                    else requests.get(f"{url_basi}{l_yolu}/scoreboard?dates={tarih}", headers=basliklar, timeout=7).json()
                )
                for ev in resp.get("events", list()):
                    comp = ev.get("competitions", list()).pop(0)
                    t_list = comp.get("competitors", list())
                    if len(t_list) < 2:
                        continue
                    t1, t2 = t_list.pop(0), t_list.pop(0)
                    ev_t = t1 if t1["homeAway"] == "home" else t2
                    dep_t = t2 if t1["homeAway"] == "home" else t1
                    ev_ad = ev_t["team"]["displayName"]
                    dep_ad = dep_t["team"]["displayName"]

                    if aranan in ev_ad.lower() or aranan in dep_ad.lower():
                        mac_id = str(ev.get("id", ""))
                        detay_sure = ev.get("status", {}).get("type", {}).get("shortDetail", "")
                        ev_s = int(float(ev_t.get("score", 0) or 0))
                        dep_s = int(float(dep_t.get("score", 0) or 0))
                        ev_r = ev_t.get("records", list()).pop(0).get("summary", "0-0") if ev_t.get("records") else "0-0"
                        dep_r = dep_t.get("records", list()).pop(0).get("summary", "0-0") if dep_t.get("records") else "0-0"

                        sakat_not = list()
                        piyasa_not = ""
                        if l_yolu != "euroleague_resmi" and "/" in l_yolu and mac_id:
                            try:
                                sj = requests.get(f"{url_basi}{l_yolu}/summary?event={mac_id}", headers=basliklar, timeout=5).json()
                                for grp in sj.get("injuries", list()):
                                    t_nm = grp.get("team", {}).get("displayName", "")
                                    for inj in grp.get("injuries", list()):
                                        if inj.get("status", "") in ("Out", "Doubtful"):
                                            sakat_not.append(f"{t_nm}: {inj.get('athlete', {}).get('displayName', '')}")
                                for pk in sj.get("pickcenter", list())[:1]:
                                    piyasa_not = f"Piyasa Barem: {pk.get('overUnder', '-')} | Handikap: {pk.get('details', '-')}"
                            except Exception:
                                pass

                        soru = (
                            f"Sen dunya capinda bir {s_adi} Bas Analistisin. Kullanici su mac icin ozel derin analiz istedi:\n"
                            f"Lig: {l_adi} | Mac: {ev_ad} ({ev_r}) vs {dep_ad} ({dep_r}) | Durum: {detay_sure} (Skor: {ev_s}-{dep_s})\n"
                            f"{piyasa_not} | Eksikler: {', '.join(sakat_not[:5]) or 'Eksik Yok'}\n"
                            f"Bu mac icin en mantikli, kazanma ihtimali en yuksek 1 ana tahmin ve 1 alternatif tahmin oner; "
                            f"gerekcesini 3 kisa madde halinde Turkce yaz."
                        )
                        rapor = beyin.mac_deger_analizi(
                    spor_turu=s_tur, lig_adi=l_adi, ev_ad=ev_ad, dep_ad=dep_ad,
                    ev_rec=ev_r, dep_rec=dep_r, state=state,
                    ev_skor=int(ev_s or 0), dep_skor=int(dep_s or 0), detay_sure=detay_sure
                )
                ai_yanit = beyin.ai_karar_ve_onay(
                    s_tur, l_adi, ev_ad, dep_ad,
                    f"{rapor['ana_tercih']} | Deger: {rapor['deger_puani']}/10 | Tuzak: {rapor['tuzak_notu'] or 'Temiz'}",
                    f"Formlar: {ev_r} vs {dep_r} | Eksikler: {sakat_not} | Piyasa: {piyasa_not}"
                )
                tuzak_satir = f"⚠️ {rapor['tuzak_notu']}\n" if rapor["tuzak_notu"] else ""
                return (
                    f"🔎 OZEL MAC ANALIZ RAPORU\n"
                    f"🏆 [{l_adi}] {ev_ad} - {dep_ad} ({detay_sure})\n"
                    f"📊 Formlar: {ev_r} vs {dep_r} | {piyasa_not}\n"
                    f"💎 Deger Puani: {rapor['deger_puani']}/10 | Guven: %{rapor['guven']}\n"
                    f"✅ Merkez Karar: {rapor['ana_tercih']}\n"
                    f"{tuzak_satir}"
                    f"🏥 Eksikler: {', '.join(sakat_not) or 'Yok'}\n\n"
                    f"{ai_yanit}"
                )
                        )
            except Exception:
                pass
    return f"Bugunun bulteninde '{aranan_takim}' adinda bir takimin maci bulunamadi."
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
            if metin.startswith("/analiz") or metin.startswith("/sor"):
              sorgu_takim = metin.replace("/analiz", "").replace("/sor", "").strip()
            if sorgu_takim:
                telegram_gonder(tek_takim_derin_analiz(sorgu_takim))
            else:
                    telegram_gonder("Kullanim ornegi: /analiz Real Madrid veya /analiz Lakers")    

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
def sharp_para_ve_oran_radari(gonderilenler):
    piyasa_dosya = "piyasa_hafiza.json"
    kayitli_piyasa = {"tarih": tarih, "maclar": {}}
    if os.path.exists(piyasa_dosya):
        try:
            with open(piyasa_dosya, "r", encoding="utf-8") as f:
                eski_p = json.load(f)
                if eski_p.get("tarih") == tarih:
                    kayitli_piyasa = eski_p
        except Exception:
            pass

    mac_sozluk = kayitli_piyasa.get("maclar", {})
    sharp_alarmlar = list()

    for s_adi, lig_sozluk in TUM_LIGLER.items():
        for l_adi, l_yolu in lig_sozluk.items():
            if l_yolu == "euroleague_resmi" or "/" not in l_yolu:
                continue
            try:
                resp = requests.get(f"{url_basi}{l_yolu}/scoreboard?dates={tarih}", headers=basliklar, timeout=6).json()
                for ev in resp.get("events", list()):
                    if ev.get("status", {}).get("type", {}).get("state", "pre") != "pre":
                        continue
                    mac_id = str(ev.get("id", ""))
                    comp = ev.get("competitions", list(({},))).pop(0)
                    t_list = comp.get("competitors", list())
                    if len(t_list) < 2:
                        continue
                    ev_ad = t_list.pop(0).get("team", {}).get("displayName", "Ev")
                    dep_ad = t_list.pop(0).get("team", {}).get("displayName", "Dep")

                    sj = requests.get(f"{url_basi}{l_yolu}/summary?event={mac_id}", headers=basliklar, timeout=5).json()
                    pk_l = sj.get("pickcenter", list())
                    if not pk_l:
                        continue
                    pk0 = pk_l.pop(0)
                    ou_yeni = float(pk0.get("overUnder", 0) or 0)
                    det_yeni = str(pk0.get("details", "")).strip()

                    if ou_yeni <= 0 and not det_yeni:
                        continue

                    if mac_id not in mac_sozluk:
                        mac_sozluk[mac_id] = {"ou": ou_yeni, "det": det_yeni, "ad": f"{ev_ad} - {dep_ad}", "lig": l_adi}
                    else:
                        eski_ou = float(mac_sozluk[mac_id].get("ou", 0) or 0)
                        eski_det = str(mac_sozluk[mac_id].get("det", "")).strip()
                        fark_ou = round(ou_yeni - eski_ou, 1) if (ou_yeni > 0 and eski_ou > 0) else 0.0
                        esik = 3.5 if s_adi == "Basketbol" else 0.5

                        sharp_anahtar = f"SHARP_{tarih}_{mac_id}"
                        if sharp_anahtar not in gonderilenler:
                            hareket_notu = ""
                            if abs(fark_ou) >= esik:
                                yon = "YUKARI FIRLADI (UST Parasi)" if fark_ou > 0 else "ASAGI DUSTU (ALT Parasi)"
                                hareket_notu = f"Barem Kaymasi: {eski_ou} -> {ou_yeni} ({fark_ou:+} | {yon})"
                            elif eski_det and det_yeni and eski_det != det_yeni:
                                hareket_notu = f"Handikap / Favori Kaymasi: {eski_det} -> {det_yeni}"

                            if hareket_notu:
                                gonderilenler.add(sharp_anahtar)
                                mac_sozluk[mac_id]["sharp_uyari"] = hareket_notu
                                sharp_alarmlar.append(
                                    f"🚨 [{l_adi}] {ev_ad} - {dep_ad}\n"
                                    f"   📊 {hareket_notu}\n"
                                    f"   💡 Piyasada sert para hareketi / gizli bilgi akisi tespit edildi!"
                                )
            except Exception:
                pass

    kayitli_piyasa["maclar"] = mac_sozluk
    with open(piyasa_dosya, "w", encoding="utf-8") as f:
        json.dump(kayitli_piyasa, f, ensure_ascii=False, indent=2)

    if sharp_alarmlar:
        telegram_gonder("🦈 SHARP PARA & ORAN DUSUSU RADARI\n\n" + "\n\n".join(sharp_alarmlar[:5]))            
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

    bulten_haritasi = {}
    if os.path.exists("son_bulten.json"):
        try:
            with open("son_bulten.json", "r", encoding="utf-8") as f:
                for b in json.load(f):
                    bulten_haritasi[str(b.get("id", ""))] = b
        except Exception:
            pass

    piyasa_haritasi = {}
    if os.path.exists("piyasa_takip.json"):
        try:
            with open("piyasa_takip.json", "r", encoding="utf-8") as f:
                piyasa_haritasi = json.load(f).get("maclar", {})
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
                    comp = ev.get("competitions", list(({},)))
                    t_list = comp.get("competitors", list())
                    if len(t_list) < 2:
                        continue

                    ev_t = next((t for t in t_list if t.get("homeAway") == "home"), t_list)
                    dep_t = next((t for t in t_list if t.get("homeAway") == "away"), t_list)

                    ev_ad = ev_t.get("team", {}).get("displayName", "Ev")
                    dep_ad = dep_t.get("team", {}).get("displayName", "Dep")
                    ev_s = int(float(ev_t.get("score", 0) or 0))
                    dep_s = int(float(dep_t.get("score", 0) or 0))
                    canli_ozet_listesi.append(f"• [{l_adi}] {ev_ad} {ev_s}-{dep_s} {dep_ad} ({detay_sure})")

                    ev_recs = ev_t.get("records", list())
                    dep_recs = dep_t.get("records", list())
                    ev_rec = ev_recs.get("summary", "1-1") if ev_recs else "1-1"
                    dep_rec = dep_recs.get("summary", "1-1") if dep_recs else "1-1"

                    ev_p = [int(x) for x in ev_rec.split("-") if x.isdigit()]
                    dep_p = [int(x) for x in dep_rec.split("-") if x.isdigit()]
                    ev_g = (ev_p / sum(ev_p)) if (len(ev_p) >= 2 and sum(ev_p) > 0) else 0.5
                    dep_g = (dep_p / sum(dep_p)) if (len(dep_p) >= 2 and sum(dep_p) > 0) else 0.5

                    top_s = ev_s + dep_s
                    fark = abs(ev_s - dep_s)

                    saha_bilgisi = canli_oyuncu_ve_olay_cek(mac_id, l_yolu, sezon_kodu)
                    canli_detay_objeleri.append({
                        "spor": s_adi, "lig": l_adi, "ev": ev_ad, "dep": dep_ad,
                        "ev_s": ev_s, "dep_s": dep_s, "sure": detay_sure,
                        "ev_r": ev_rec, "dep_r": dep_rec, "saha": saha_bilgisi
                    })

                    uyari_tipi = ""
                    uyari_kodu = ""

                    if s_adi == "Basketbol":
                        ikinci_ceyrek = any(k in detay_sure for k in ("2nd", "Q2", "2C"))
                        devre_arasi = any(k in detay_sure for k in ("Half", "HT", "IY"))
                        ucuncu_ceyrek = any(k in detay_sure for k in ("3rd", "Q3", "3C"))
                        dorduncu_ceyrek = any(k in detay_sure for k in ("4th", "Q4", "4C", "OT"))

                        acilis_baremi = float(piyasa_haritasi.get(mac_id, {}).get("ou", 0) or 0)
                        if acilis_baremi <= 0:
                            acilis_baremi = 224.0 if "NBA" in l_adi else 162.0

                        if devre_arasi and (top_s * 2) >= (acilis_baremi + 12):
                            uyari_tipi = f"🚀 YUKSEK TEMPO (Devre: {top_s} | Projeksiyon: {top_s*2} / Barem: {acilis_baremi})"
                            uyari_kodu = "TEMPO"

                        elif (ikinci_ceyrek or devre_arasi or ucuncu_ceyrek):
                            mac_bulten = bulten_haritasi.get(mac_id, {})
                            bulten_tahmin = mac_bulten.get("tahmin", "")

                            ev_gercek_fav = ("(MS 1)" in bulten_tahmin) or (ev_g >= 0.62 and (ev_g - dep_g) >= 0.20)
                            dep_gercek_fav = ("(MS 2)" in bulten_tahmin) or (dep_g >= 0.62 and (dep_g - ev_g) >= 0.20)

                            if ev_gercek_fav and not dep_gercek_fav and 8 <= (dep_s - ev_s) <= 15:
                                uyari_tipi = f"🔥 FAVORI GERIDE (MS 1 FIRSATI) | {ev_ad} -{dep_s - ev_s} Sayi Takipte"
                                uyari_kodu = "FAVORI"
                            elif dep_gercek_fav and not ev_gercek_fav and 8 <= (ev_s - dep_s) <= 15:
                                uyari_tipi = f"🔥 FAVORI GERIDE (MS 2 FIRSATI) | {dep_ad} -{ev_s - dep_s} Sayi Takipte"
                                uyari_kodu = "FAVORI"

                        elif dorduncu_ceyrek and fark <= 5 and top_s > 0:
                            uyari_tipi = "⏳ CRUNCH TIME (SON CEYREK HEYECANI)"
                            uyari_kodu = "CRUNCH"

                    else:
                        rakamlar = "".join(c for c in detay_sure if c.isdigit())
                        dk = int(rakamlar) if rakamlar else 0
                        if dk >= 75 and fark <= 1 and ((ev_g >= 0.60 and (ev_g - dep_g) >= 0.18) or (dep_g >= 0.60 and (dep_g - ev_g) >= 0.18)):
                            baskili = ev_ad if ev_g >= dep_g else dep_ad
                            uyari_tipi = f"⏳ SON DAKIKA BASKI ({baskili})"
                            uyari_kodu = "BASKI"
                        elif any(k in detay_sure for k in ("45", "Half", "HT")) and top_s >= 3:
                            uyari_tipi = "🚀 GOLLU TEMPO ANALIZI (IY 3+ Gol)"
                            uyari_kodu = "GOL_TEMPO"
                        elif any(k in detay_sure for k in ("45", "Half", "HT")) and top_s == 0 and abs(ev_g - dep_g) >= 0.25:
                            uyari_tipi = "🔥 IY 0-0 (FAVORI 2. YARI PLANI)"
                            uyari_kodu = "IY_00"

                    if uyari_tipi and uyari_kodu:
                        anahtar = f"{mac_id}_{uyari_kodu}"
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
    sharp_para_ve_oran_radari(gonderilenler)
    maca_1_saat_kala_kadro_kontrol(gonderilenler)
    bulten_anlik_sonuc_kontrol(gonderilenler)
    telegram_komutlari_isle(hafiza, canli_ozet_listesi, canli_detay_objeleri)

    hafiza["uyarilar"] = list(gonderilenler)
    with open("canli_uyarilar.json", "w", encoding="utf-8") as f:
        json.dump(hafiza, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    canli_maclari_tara()
