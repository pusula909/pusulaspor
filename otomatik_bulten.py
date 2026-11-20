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


def _el_get(t):
    ev = list()
    try:
        h = {"User-Agent": "Mozilla/5.0", "Accept": "application/xml, text/xml"}
        yil = int(t[:4])
        ay = int(t[4:6])
        sezon_kodu = f"E{yil if ay >= 8 else yil - 1}"
        el_host = "https://api-live." + "euroleague.net/v1/"

        win_map, loss_map = {}, {}
        try:
            r_res = requests.get(f"{el_host}results?seasonCode={sezon_kodu}", headers=h, timeout=8)
            for g in ET.fromstring(r_res.content).findall(".//game"):
                t1 = g.findtext("hometeam", "").strip()
                t2 = g.findtext("awayteam", "").strip()
                hs = int(g.findtext("homescore", "0") or 0)
                ds = int(g.findtext("awayscore", "0") or 0)
                if g.findtext("played", "false").lower() == "true" and (hs > 0 or ds > 0):
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
                ev_r = f"{win_map.get(h_ad, 0)}-{loss_map.get(h_ad, 0)}"
                dep_r = f"{win_map.get(a_ad, 0)}-{loss_map.get(a_ad, 0)}"
                ev.append({
                    "status": {"type": {"shortDetail": s_time}},
                    "competitions": list(({
                        "competitors": list((
                            {"homeAway": "home", "team": {"displayName": h_ad}, "records": list(({"summary": ev_r},))},
                            {"homeAway": "away", "team": {"displayName": a_ad}, "records": list(({"summary": dep_r},))},
                        ))
                    },)),
                })
    except Exception:
        pass
    return {"events": ev}


def tahmin_hesapla(ev_ad, dep_ad, ev_rec, dep_rec, spor_turu, lig_adi):
    try:
        ev_p = list(int(x) for x in ev_rec.split("-"))
        dep_p = list(int(x) for x in dep_rec.split("-"))
        ev_top = sum(ev_p) if sum(ev_p) > 0 else 1
        dep_top = sum(dep_p) if sum(dep_p) > 0 else 1
        ev_g = max(0.08, min(0.92, (ev_p.pop(0) / ev_top) + 0.06))
        dep_g = max(0.08, min(0.92, (dep_p.pop(0) / dep_top)))
        fark = abs(ev_g - dep_g)

        if spor_turu == "Futbol":
            if ev_g > dep_g + 0.14:
                return f"{ev_ad} Kazanir (MS 1)", min(89, int(56 + fark * 45))
            elif dep_g > ev_g + 0.14:
                return f"{dep_ad} Kazanir (MS 2)", min(88, int(55 + fark * 45))
            return "Toplam 1.5 UST", min(84, int(68 + (ev_g + dep_g) * 10))
        else:
            if ev_g >= dep_g:
                return f"{ev_ad} Kazanir (MS 1)", min(89, int(54 + fark * 48))
            return f"{dep_ad} Kazanir (MS 2)", min(88, int(54 + fark * 48))
    except Exception:
        return "Form Analizi", 55


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
                    tahmin, guven = tahmin_hesapla(ev_ad, dep_ad, ev_r, dep_r, s_adi, l_adi)
                    firsatlar.append({
                        "lig": l_adi,
                        "mac": f"{ev_ad} - {dep_ad}",
                        "saat": saat,
                        "tahmin": tahmin,
                        "guven": guven,
                    })
            except Exception:
                pass

    en_iyiler = sorted(firsatlar, key=lambda x: x["guven"], reverse=True)[:5]
    if not en_iyiler:
        mesaj = f"📅 {tarih_guzel} PusulaSpor AI Bulteni\nBugun icin bultende uygun mac bulunamadi."
    else:
        satirlar = list((f"🏆 {tarih_guzel} PUSULASPOR AI GUNUN BANKOLARI\n",))
        for idx, m in enumerate(en_iyiler, 1):
            satirlar.append(f"{idx}. [{m['lig']}] {m['mac']} ({m['saat']})\n   👉 Tahmin: {m['tahmin']} (Guven: %{m['guven']})")

        if GEMINI_AKTIF and GEMINI_KEY:
            try:
                client = genai.Client(api_key=GEMINI_KEY, http_options={"api_version": "v1beta"})
                ozet_istek = "Su maclar icin tek paragraflik kisa, motive edici bir gunun bulten yorumu yaz (maksimum 3 cumle): " + ", ".join(list(x["mac"] for x in en_iyiler))
                yanit = client.models.generate_content(model="gemini-2.5-flash", contents=ozet_istek)
                if yanit and yanit.text:
                    satirlar.append(f"\n🤖 AI Gunun Ozeti:\n{yanit.text.strip()}")
            except Exception:
                pass

        mesaj = "\n".join(satirlar)

    if TG_TOKEN and TG_CHAT_ID:
        tg_adres = "https://" + "api." + "telegram.org" + "/bot" + TG_TOKEN + "/sendMessage"
        requests.post(tg_adres, data={"chat_id": TG_CHAT_ID, "text": mesaj}, timeout=10)


if __name__ == "__main__":
    bulten_olustur_ve_gonder()
