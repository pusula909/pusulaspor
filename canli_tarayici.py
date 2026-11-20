import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
import requests

TG_TOKEN = os.environ.get("TG_TOKEN", "").strip()
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "").strip()

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
                    if res_map[gc]["played"]:
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


def telegram_komutlari_isle(hafiza, canli_ozet_listesi):
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
                telegram_gonder(f"📺 ANLIK CANLI MACLAR ({saat_str})\n\n" + "\n".join(canli_ozet_listesi[:15]))
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
            telegram_gonder("🤖 PusulaSpor Komutlari:\n/canli - O anki canli skorlar\n/bulten - Gunun AI bankolari\n/karne - Haftalik basari orani")
    except Exception:
        pass
    hafiza["son_update_id"] = son_update_id


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

                    uyari_tipi = ""
                    if s_adi == "Basketbol":
                        if ("Q2" in detay_sure or "Half" in detay_sure or "2C" in detay_sure) and top_s >= 92:
                            uyari_tipi = "🔥 YUKSEK TEMPO (UST FIRSATI)"
                        elif ("Q4" in detay_sure or "4C" in detay_sure or "OT" in detay_sure) and fark <= 5:
                            uyari_tipi = "⏳ CRUNCH TIME (SON CEYREK HEYECANI)"
                        elif ev_g >= 0.65 and (dep_s - ev_s) >= 6:
                            uyari_tipi = f"🔥 FAVORI GERIDE ({ev_ad} Geri Donus Firsati)"
                        elif dep_g >= 0.65 and (ev_s - dep_s) >= 6:
                            uyari_tipi = f"🔥 FAVORI GERIDE ({dep_ad} Geri Donus Firsati)"
                    else:
                        rakamlar = "".join(c for c in detay_sure if c.isdigit())
                        dk = int(rakamlar) if rakamlar else 0
                        if dk >= 75 and fark <= 1 and (ev_g >= 0.58 or dep_g >= 0.58):
                            baskili = ev_ad if ev_g >= dep_g else dep_ad
                            uyari_tipi = f"⏳ SON DAKIKA BASKI ({baskili} Yukleniyor)"
                        elif ("45" in detay_sure or "Half" in detay_sure or "HT" in detay_sure) and top_s >= 2:
                            uyari_tipi = "🔥 GOLLU TEMPO (2.5 / 3.5 UST)"
                        elif ("45" in detay_sure or "HT" in detay_sure) and top_s == 0 and (ev_g >= 0.60 or dep_g >= 0.60):
                            uyari_tipi = "🔥 IY 0-0 (2. YARI GOL FIRSATI)"

                    if uyari_tipi:
                        anahtar = f"{mac_id}_{uyari_tipi}"
                        if anahtar not in gonderilenler:
                            gonderilenler.add(anahtar)
                            yeni_mesajlar.append(f"• [{l_adi}] {ev_ad} {ev_s}-{dep_s} {dep_ad} ({detay_sure})\n  👉 {uyari_tipi}")
            except Exception:
                pass

    if yeni_mesajlar:
        baslik = f"🚨 CANLI RADAR UYARISI ({saat_str})\n\n"
        telegram_gonder(baslik + "\n\n".join(yeni_mesajlar))

    telegram_komutlari_isle(hafiza, canli_ozet_listesi)

    hafiza["uyarilar"] = list(gonderilenler)
    with open("canli_uyarilar.json", "w", encoding="utf-8") as f:
        json.dump(hafiza, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    canli_maclari_tara()
