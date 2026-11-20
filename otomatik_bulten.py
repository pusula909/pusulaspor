import json
import os
import sys
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
        ev_p = list(int(x) for x in ev_rec.split("-"))
        dep_p = list(int(x) for x in dep_rec.split("-"))
        ev_top = sum(ev_p) if sum(ev_p) > 0 else 1
        dep_top = sum(dep_p) if sum(dep_p) > 0 else 1
        ev_g = max(0.08, min(0.92, (ev_p.pop(0) / ev_top) + 0.06))
        dep_g = max(0.08, min(0.92, (dep_p.pop(0) / dep_top)))
        fark = abs(ev_g - dep_g)
        secenekler = list()
        deger_etiket = ""

        if spor_turu == "Futbol":
            if ev_g > dep_g + 0.14:
                secenekler.append({"tahmin": f"{ev_ad} Kazanir (MS 1)", "guven": min(89, int(56 + fark * 45))})
            elif dep_g > ev_g + 0.14:
                secenekler.append({"tahmin": f"{dep_ad} Kazanir (MS 2)", "guven": min(88, int(55 + fark * 45))})
                if dep_g >= 0.65:
                    deger_etiket = "💎 DEPLASMAN DEGER FIRSATI"
            else:
                secenekler.append({"tahmin": "Cifte Sans 1X (MS 0)", "guven": min(75, int(64 - fark * 20))})

            if ev_g >= 0.54 and dep_g >= 0.48:
                secenekler.append({"tahmin": "Toplam 2.5 UST", "guven": min(84, int(62 + (ev_g + dep_g) * 15))})
                if ev_g >= 0.62 and dep_g >= 0.58:
                    deger_etiket = "💎 YUKSEK HUCUM VALUE (2.5 UST)"
            elif ev_g <= 0.36 and dep_g <= 0.36:
                secenekler.append({"tahmin": "Toplam 2.5 ALT", "guven": min(81, int(63 + (1 - (ev_g + dep_g)) * 16))})
            else:
                secenekler.append({"tahmin": "Toplam 1.5 UST", "guven": min(85, int(68 + (ev_g + dep_g) * 10))})

            if ev_g >= 0.48 and dep_g >= 0.48:
                secenekler.append({"tahmin": "KG VAR (Karsilikli Gol)", "guven": min(82, int(60 + min(ev_g, dep_g) * 32))})

            if ev_g >= 0.62:
                secenekler.append({"tahmin": f"{ev_ad} 1.5 UST Gol", "guven": min(83, int(55 + ev_g * 34))})
            elif dep_g <= 0.32:
                secenekler.append({"tahmin": f"{dep_ad} 1.5 ALT Gol", "guven": min(81, int(80 - dep_g * 28))})
        else:
            if ev_g >= dep_g:
                secenekler.append({"tahmin": f"{ev_ad} Kazanir (MS 1)", "guven": min(89, int(54 + fark * 48))})
            else:
                secenekler.append({"tahmin": f"{dep_ad} Kazanir (MS 2)", "guven": min(88, int(54 + fark * 48))})
                if dep_g >= 0.68:
                    deger_etiket = "💎 DEPLASMAN FAVORISI VALUE"

            beklenen_toplam = round(154 + (ev_g + dep_g) * 14) + 0.5 if lig_adi == "EuroLeague" else round(212 + (ev_g + dep_g) * 14) + 0.5
            if (ev_g + dep_g) >= 1.12:
                secenekler.append({"tahmin": f"Mac Toplami {beklenen_toplam} UST", "guven": min(85, int(60 + (ev_g + dep_g) * 18))})
                if (ev_g + dep_g) >= 1.28:
                    deger_etiket = "💎 EKSTREM TEMPO FIRSATI"
            elif (ev_g + dep_g) <= 0.88:
                secenekler.append({"tahmin": f"Mac Toplami {beklenen_toplam} ALT", "guven": min(83, int(75 - (ev_g + dep_g) * 12))})

            taban_ev = 77 if lig_adi == "EuroLeague" else 105
            ev_barem = round(taban_ev + ev_g * 14) + 0.5
            if ev_g >= 0.58:
                secenekler.append({"tahmin": f"{ev_ad} {ev_barem} UST Sayi", "guven": min(84, int(55 + ev_g * 34))})

            taban_dep = 75 if lig_adi == "EuroLeague" else 103
            dep_barem = round(taban_dep + dep_g * 14) + 0.5
            if dep_g <= 0.38:
                secenekler.append({"tahmin": f"{dep_ad} {dep_barem} ALT Sayi", "guven": min(82, int(80 - dep_g * 28))})

        en_iyi = sorted(secenekler, key=lambda x: x["guven"], reverse=True).pop(0)
        return en_iyi["tahmin"], en_iyi["guven"], deger_etiket
    except Exception:
        return "Form Analizi", 55, ""


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
                    tahmin, guven, deger = en_guclu_tahmini_bul(ev_ad, dep_ad, ev_r, dep_r, s_adi, l_adi)
                    firsatlar.append({
                        "id": str(ev.get("id", "")),
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

    en_iyiler = sorted(firsatlar, key=lambda x: x["guven"], reverse=True)[:5]
    with open("son_bulten.json", "w", encoding="utf-8") as f:
        json.dump(en_iyiler, f, ensure_ascii=False, indent=2)

    if not en_iyiler:
        mesaj = f"📅 {tarih_guzel} PusulaSpor AI Bulteni\nBugun icin bultende uygun mac bulunamadi."
    else:
        satirlar = list((f"🏆 {tarih_guzel} PUSULASPOR AI GUNUN BANKOLARI\n",))
        for idx, m in enumerate(en_iyiler, 1):
            etiket_ek = f" | {m['deger']}" if m.get("deger") else ""
            satirlar.append(f"{idx}. [{m['lig']}] {m['mac']} ({m['saat']})\n   👉 Tahmin: {m['tahmin']} (Guven: %{m['guven']}){etiket_ek}")

        if GEMINI_AKTIF and GEMINI_KEY:
            try:
                client = genai.Client(api_key=GEMINI_KEY, http_options={"api_version": "v1beta"})
                ozet_istek = "Su maclar ve secilen tahminler icin 3 cumlelik kisa bir gunun bulten yorumu yaz: " + ", ".join(list(f"{x['mac']} ({x['tahmin']})" for x in en_iyiler))
                yanit = client.models.generate_content(model="gemini-2.5-flash", contents=ozet_istek)
                if yanit and yanit.text:
                    satirlar.append(f"\n🤖 AI Gunun Ozeti:\n{yanit.text.strip()}")
            except Exception:
                pass

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
