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
        return "Lutfen en az 3 harfli bir takim adi yazin (Ornek: /sor Liverpool)"

    simdi = datetime.now(timezone(timedelta(hours=3)))
    tarihler = [simdi.strftime("%Y%m%d"), (simdi + timedelta(days=1)).strftime("%Y%m%d")]

    for tarih in tarihler:
        for s_tur, lig_sozluk in TUM_LIGLER.items():
            for l_adi, l_yolu in lig_sozluk.items():
                try:
                    resp = (
                        _el_get(tarih)
                        if l_yolu == "euroleague_resmi"
                        else requests.get(f"{url_basi}{l_yolu}/scoreboard?dates={tarih}&limit=100", headers=basliklar, timeout=7).json()
                    )
                    for ev in resp.get("events", list()):
                        comp_list = ev.get("competitions", list())
                        if not comp_list:
                            continue
                        comp = comp_list.pop(0)
                        t_list = comp.get("competitors", list())
                        if len(t_list) < 2:
                            continue
                        t1, t2 = t_list.pop(0), t_list.pop(0)
                        ev_t = t1 if t1.get("homeAway") == "home" else t2
                        dep_t = t2 if t1.get("homeAway") == "home" else t1
                        ev_ad = ev_t.get("team", {}).get("displayName", "")
                        dep_ad = dep_t.get("team", {}).get("displayName", "")

                        if aranan in ev_ad.lower() or aranan in dep_ad.lower():
                            detay_sure = ev.get("status", {}).get("type", {}).get("shortDetail", "")
                            state = ev.get("status", {}).get("type", {}).get("state", "pre")
                            ev_s = int(float(ev_t.get("score", 0) or 0))
                            dep_s = int(float(dep_t.get("score", 0) or 0))
                            ev_recs = ev_t.get("records", list())
                            dep_recs = dep_t.get("records", list())
                            ev_r = ev_recs.pop(0).get("summary", "1-1") if ev_recs else "1-1"
                            dep_r = dep_recs.pop(0).get("summary", "1-1") if dep_recs else "1-1"

                            rapor = beyin.mac_deger_analizi(
                                spor_turu=s_tur, lig_adi=l_adi, ev_ad=ev_ad, dep_ad=dep_ad,
                                ev_rec=ev_r, dep_rec=dep_r, state=state,
                                ev_skor=ev_s, dep_skor=dep_s, detay_sure=detay_sure
                            )
                            ai_yanit = beyin.ai_karar_ve_onay(
                                s_tur, l_adi, ev_ad, dep_ad,
                                f"{rapor['ana_tercih']} | Deger: {rapor['deger_puani']}/10 | Tuzak: {rapor['tuzak_notu'] or 'Temiz'}",
                                f"Durum: {detay_sure} | Skor: {ev_s}-{dep_s} | Form: {ev_r} vs {dep_r}"
                            )
                            tuzak_satir = f"⚠️ {rapor['tuzak_notu']}\n" if rapor["tuzak_notu"] else ""
                            return (
                                f"🔎 OZEL MAC ANALIZ RAPORU\n"
                                f"🏆 [{l_adi}] {ev_ad} - {dep_ad}\n"
                                f"⏱️ Durum: {detay_sure} ({ev_s}-{dep_s}) | Form: {ev_r} vs {dep_r}\n"
                                f"💎 Deger Puani: {rapor['deger_puani']}/10 | Guven: %{rapor['guven']}\n"
                                f"✅ Merkez Karar: {rapor['ana_tercih']}\n"
                                f"{tuzak_satir}\n"
                                f"{ai_yanit}"
                            )
                except Exception:
                    continue

    return f"Bugunun ve yarinin bulteninde '{aranan_takim}' adinda bir takimin maci bulunamadi."
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
            if "/kombin" in metin:
                istenen_komutlar.add("kombin")
            if "/yardim" in metin or "/start" in metin:
                istenen_komutlar.add("yardim")
            if metin.startswith("/analiz") or metin.startswith("/sor"):
                sorgu_takim = metin.replace("/analiz", "").replace("/sor", "").strip()
                if sorgu_takim:
                    telegram_gonder(tek_takim_derin_analiz(sorgu_takim))
                else:
                    telegram_gonder("Kullanim ornegi: /sor Real Madrid veya /sor Lakers")
    except Exception:
        pass

    if "canli" in istenen_komutlar:
        if canli_ozet_listesi:
            mesaj_parcalari = list(("🔴 ANLIK CANLI MAC DURUMU\n",))
            mesaj_parcalari.extend(canli_ozet_listesi[:15])
            if canli_detay_objeleri:
                ilk_m = canli_detay_objeleri.pop(0)
                ai_yorum = ai_bas_analist_karari(
                    ilk_m["spor"], ilk_m["lig"], ilk_m["ev"], ilk_m["dep"],
                    ilk_m["ev_s"], ilk_m["dep_s"], ilk_m["sure"], ilk_m["ev_r"], ilk_m["dep_r"], ilk_m["saha"]
                )
                if ai_yorum:
                    mesaj_parcalari.append(f"\n🔥 One Cikan Mac Analizi ({ilk_m['ev']} - {ilk_m['dep']}):\n{ai_yorum}")
            telegram_gonder("\n".join(mesaj_parcalari))
        else:
            telegram_gonder("Su an canli oynanan mac bulunmuyor.")

    if "bulten" in istenen_komutlar:
        if os.path.exists("son_bulten.json"):
            with open("son_bulten.json", "r", encoding="utf-8") as f:
                b_list = json.load(f)
            if b_list:
                satir = list(("📋 KAYITLI GUNUN BULTENI\n",))
                for i, m in enumerate(b_list, 1):
                    satir.append(f"{i}. [{m['lig']}] {m['mac']} -> {m['tahmin']} (%{m['guven']})")
                telegram_gonder("\n".join(satir))
        else:
            telegram_gonder("Henuz kayitli gunluk bulten yok.")

    if "kombin" in istenen_komutlar:
        if os.path.exists("son_bulten.json"):
            with open("son_bulten.json", "r", encoding="utf-8") as f:
                b_list = json.load(f)
            uygunlar = [m for m in b_list if not m.get("tuzak_notu")][:3]
            if uygunlar:
                mesaj = ["🏆 GUNUN CANLI ISTIHBARATLI 3'LU AI KOMBINESI\n"]
                for i, m in enumerate(uygunlar, 1):
                    takimlar = m.get("mac", "").split(" - ")
                    ev_a = takimlar.pop(0) if takimlar else m.get("mac", "")
                    dep_a = takimlar.pop(0) if takimlar else ""
                    rapor = beyin.ai_karar_ve_onay(m.get("spor", "Futbol"), m.get("lig", ""), ev_a, dep_a, f"{m.get('tahmin', '')} (Guven: %{m.get('guven', '')})")
                    mesaj.append(f"{i}️⃣ [{m.get('lig', '')}] {m.get('mac', '')}\n{rapor}\n")
                telegram_gonder("\n".join(mesaj))
            else:
                telegram_gonder("Su an tuzak filtresini gecen uygun kombine maci bulunamadi.")
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
                k_satir = list(("🏆 HAFTALIK BASARI KARNESI\n",))
                for l_ad, v in lig_ozet.items():
                    yuzde = int((v["hit"] / v["top"]) * 100)
                    k_satir.append(f"• {l_ad}: {v['top']} Macta {v['hit']} Isabet (%{yuzde})")
                telegram_gonder("\n".join(k_satir))
            else:
                telegram_gonder("Haftalik karne icin gece sonuclarinin kaydi bekleniyor.")
        else:
            telegram_gonder("Haftalik karne icin gece sonuclarinin kaydi bekleniyor.")

    if "yardim" in istenen_komutlar:
        yardim_metni = (
            "🤖 PUSULA AI KOMUT LISTESI\n\n"
            "/kombin - Canli web istihbaratli 3'lu gunun kombinesi\n"
            "/sor TakimAdi - Tek mac icin derin istihbarat & analiz\n"
            "/canli - O an oynanan canli maclar ve AI firsatlari\n"
            "/bulten - Gunun kayitli bulten listesi\n"
            "/karne - Haftalik AI basari karnesi"
        )
        telegram_gonder(yardim_metni)

    hafiza["son_update_id"] = son_update_id
    json.dump(hafiza, open("canli_hafiza.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def otomatik_radar_ve_karne():
    hafiza = json.load(open("canli_hafiza.json", "r", encoding="utf-8")) if os.path.exists("canli_hafiza.json") else {}
    if "alarmlar" not in hafiza:
        hafiza["alarmlar"] = {}
    if "gol_skorlari" not in hafiza:
        hafiza["gol_skorlari"] = {}

    simdi = datetime.now(timezone(timedelta(hours=3)))
    bugun_str = simdi.strftime("%Y%m%d")
    dun_str = (simdi - timedelta(days=1)).strftime("%Y%m%d")

    canli_ozet_listesi = list()
    canli_detay_objeleri = list()
    biten_skorlar = {}

    for s_tur, lig_sozluk in TUM_LIGLER.items():
        for l_adi, l_yolu in lig_sozluk.items():
            for t_str in (bugun_str, dun_str):
                try:
                    resp = (
                        _el_get(t_str)
                        if l_yolu == "euroleague_resmi"
                        else requests.get(f"{url_basi}{l_yolu}/scoreboard?dates={t_str}&limit=100", headers=basliklar, timeout=7).json()
                    )
                    for ev in resp.get("events", list()):
                        comp_list = ev.get("competitions", list())
                        if not comp_list:
                            continue
                        comp = comp_list.pop(0)
                        t_list = comp.get("competitors", list())
                        if len(t_list) < 2:
                            continue
                        t1, t2 = t_list.pop(0), t_list.pop(0)
                        ev_t = t1 if t1.get("homeAway") == "home" else t2
                        dep_t = t2 if t1.get("homeAway") == "home" else t1
                        ev_ad = ev_t.get("team", {}).get("displayName", "")
                        dep_ad = dep_t.get("team", {}).get("displayName", "")
                        ev_s = int(ev_t.get("score", 0) or 0)
                        dep_s = int(dep_t.get("score", 0) or 0)
                        state = ev.get("status", {}).get("type", {}).get("state", "")
                        detay_sure = ev.get("status", {}).get("type", {}).get("shortDetail", "")
                        mac_id = str(ev.get("id", f"{ev_ad}_{dep_ad}"))
                        mac_etiket = f"{ev_ad} - {dep_ad}"

                        if state == "post":
                            biten_skorlar[mac_etiket.lower()] = (ev_s, dep_s)

                        elif state == "pre" and t_str == bugun_str:
                            mac_tarih_str = ev.get("date", "")
                            if mac_tarih_str:
                                try:
                                    mac_dt = datetime.fromisoformat(mac_tarih_str.replace("Z", "+00:00"))
                                    kalan_dk = (mac_dt - datetime.now(timezone.utc)).total_seconds() / 60.0
                                    kadro_anahtar = f"ilk11_{mac_id}"
                                    if 10 <= kalan_dk <= 55 and kadro_anahtar not in hafiza["alarmlar"]:
                                        ev_recs = ev_t.get("records", list())
                                        dep_recs = dep_t.get("records", list())
                                        ev_r = ev_recs.pop(0).get("summary", "1-1") if ev_recs else "1-1"
                                        dep_r = dep_recs.pop(0).get("summary", "1-1") if dep_recs else "1-1"
                                        rapor = beyin.mac_deger_analizi(
                                            spor_turu=s_tur, lig_adi=l_adi, ev_ad=ev_ad, dep_ad=dep_ad,
                                            ev_rec=ev_r, dep_rec=dep_r, state="pre"
                                        )
                                        guven = int(rapor.get("guven", 0))
                                        deger_p = float(rapor.get("deger_puani", 0))
                                        tuzak_var = bool(rapor.get("tuzak_notu", ""))
                                        if guven >= 78 and deger_p >= 7.2 and not tuzak_var:
                                            ai_yorum = beyin.ai_karar_ve_onay(
                                                s_tur, l_adi, ev_ad, dep_ad,
                                                f"MACA {int(kalan_dk)} DK KALA RESMI ILK 11 & KADRO KONTROLU: {rapor.get('ana_tercih', '')} | Guven: %{guven}"
                                            )
                                            bildirim = (
                                                f"⏰ MACA {int(kalan_dk)} DK KALA RESMI ILK 11 & KADRO ALARMI\n\n"
                                                f"🏆 [{l_adi}] {ev_ad} - {dep_ad}\n"
                                                f"📊 Guven: %{guven} | Deger Puani: {deger_p}/10\n\n"
                                                f"{ai_yorum}"
                                            )
                                            telegram_gonder(bildirim)
                                            hafiza["alarmlar"][kadro_anahtar] = simdi.strftime("%Y-%m-%d %H:%M")
                                except Exception:
                                    pass

                        elif state == "in" and t_str == bugun_str:
                            canli_ozet_listesi.append(f"• [{l_adi}] {ev_ad} {ev_s}-{dep_s} {dep_ad} ({detay_sure})")
                            ev_recs = ev_t.get("records", list())
                            dep_recs = dep_t.get("records", list())
                            ev_r = ev_recs.pop(0).get("summary", "1-1") if ev_recs else "1-1"
                            dep_r = dep_recs.pop(0).get("summary", "1-1") if dep_recs else "1-1"

                            canli_detay_objeleri.append({
                                "spor": s_tur, "lig": l_adi, "ev": ev_ad, "dep": dep_ad,
                                "ev_s": ev_s, "dep_s": dep_s, "sure": detay_sure,
                                "ev_r": ev_r, "dep_r": dep_r, "saha": ""
                            })

                            rapor = beyin.mac_deger_analizi(
                                spor_turu=s_tur, lig_adi=l_adi, ev_ad=ev_ad, dep_ad=dep_ad,
                                ev_rec=ev_r, dep_rec=dep_r, state="in",
                                ev_skor=ev_s, dep_skor=dep_s, detay_sure=detay_sure
                            )
                            guven = int(rapor.get("guven", 0))
                            deger_p = float(rapor.get("deger_puani", 0))
                            tuzak_var = bool(rapor.get("tuzak_notu", ""))

                            onceki_skor = hafiza["gol_skorlari"].get(mac_id, "")
                            yeni_skor = f"{ev_s}-{dep_s}"
                            gol_oldu = bool(onceki_skor and onceki_skor != yeni_skor and (ev_s + dep_s) > 0)
                            hafiza["gol_skorlari"][mac_id] = yeni_skor

                            sure_alt = detay_sure.lower()
                            bask_4q_anahtar = f"4q_{mac_id}"
                            if s_tur == "Basketbol" and any(k in sure_alt for k in ("4th", "q4", "end of 3rd", "4p")) and bask_4q_anahtar not in hafiza["alarmlar"]:
                                toplam_sayi = ev_s + dep_s
                                fark_sayi = abs(ev_s - dep_s)
                                if toplam_sayi >= 135 and fark_sayi <= 16:
                                    yon = "CANLI TOPLAM SAYI UST (Yuksek Tempo & Yakin Skor)" if toplam_sayi >= 165 else "CANLI TOPLAM SAYI ALT (Dusuk Tempo & Savunma)"
                                    ai_bask = beyin.ai_karar_ve_onay(
                                        s_tur, l_adi, ev_ad, dep_ad,
                                        f"4. CEYREK BAREM AVCISI: Skor {ev_s}-{dep_s} (Toplam: {toplam_sayi}, Fark: {fark_sayi}) | Oneri: {yon}"
                                    )
                                    bildirim_bask = (
                                        f"🏀 4. CEYREK CANLI UST/ALT BAREM FIRSATI\n\n"
                                        f"🏆 [{l_adi}] {ev_ad} {ev_s}-{dep_s} {dep_ad} ({detay_sure})\n"
                                        f"⚡ Anlik Toplam: {toplam_sayi} Sayi | Skor Farki: {fark_sayi}\n\n"
                                        f"{ai_bask}"
                                    )
                                    telegram_gonder(bildirim_bask)
                                    hafiza["alarmlar"][bask_4q_anahtar] = simdi.strftime("%Y-%m-%d %H:%M")

                            alarm_anahtar = f"{mac_id}_{rapor.get('ana_tercih', '')}"
                            if guven >= 80 and deger_p >= 7.5 and not tuzak_var and alarm_anahtar not in hafiza["alarmlar"]:
                                ai_yorum = beyin.ai_karar_ve_onay(
                                    s_tur, l_adi, ev_ad, dep_ad,
                                    f"CANLI FIRSAT: {rapor.get('ana_tercih', '')} | Guven: %{guven} | Skor: {yeni_skor} ({detay_sure})"
                                )
                                gol_baslik = "⚽ GOL SONRASI %80+ CANLI FIRSAT ALARMI" if gol_oldu else "🔥 %80+ YUKSEK IHTIMALLI CANLI GOL / MAC FIRSATI"
                                bildirim = (
                                    f"{gol_baslik}\n\n"
                                    f"🏆 [{l_adi}] {ev_ad} {ev_s}-{dep_s} {dep_ad} ({detay_sure})\n"
                                    f"📊 Guven: %{guven} | Deger Puani: {deger_p}/10\n\n"
                                    f"{ai_yorum}"
                                )
                                telegram_gonder(bildirim)
                                hafiza["alarmlar"][alarm_anahtar] = simdi.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    continue
    if os.path.exists("son_bulten.json") and biten_skorlar:
        try:
            with open("son_bulten.json", "r", encoding="utf-8") as f:
                b_list = json.load(f)
            arsiv = json.load(open("haftalik_arsiv.json", "r", encoding="utf-8")) if os.path.exists("haftalik_arsiv.json") else list()
            kayitli_maclar = {k.get("mac", "") for k in arsiv}
            degisti = False
            for m in b_list:
                m_ad = m.get("mac", "")
                if m_ad in kayitli_maclar:
                    continue
                skor_tup = biten_skorlar.get(m_ad.lower())
                if not skor_tup:
                    continue
                es, ds = skor_tup
                tahmin_txt = str(m.get("tahmin", "")).upper()
                tuttu = False
                if "MS 1" in tahmin_txt or "KAZANIR (MS 1)" in tahmin_txt:
                    tuttu = es > ds
                elif "MS 2" in tahmin_txt or "KAZANIR (MS 2)" in tahmin_txt:
                    tuttu = ds > es
                elif "2.5 UST" in tahmin_txt or "UST" in tahmin_txt:
                    tuttu = (es + ds) >= 3
                elif "2.5 ALT" in tahmin_txt or "ALT" in tahmin_txt:
                    tuttu = (es + ds) <= 2
                elif "KG VAR" in tahmin_txt:
                    tuttu = (es > 0 and ds > 0)
                arsiv.append({
                    "tarih": simdi.strftime("%Y-%m-%d"),
                    "lig": m.get("lig", ""),
                    "mac": m_ad,
                    "tahmin": m.get("tahmin", ""),
                    "skor": f"{es}-{ds}",
                    "tuttu": tuttu
                })
                degisti = True
            if degisti:
                json.dump(arsiv[-150:], open("haftalik_arsiv.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        except Exception:
            pass

    telegram_komutlari_isle(hafiza, canli_ozet_listesi, canli_detay_objeleri)


if __name__ == "__main__":
    otomatik_radar_ve_karne()
