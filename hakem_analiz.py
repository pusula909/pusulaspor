import requests
import re
import urllib.parse
from datetime import datetime

_TUM_ESPN_YOLLARI = (
    "basketball/nba",
    "soccer/tur.1",
    "soccer/eng.1",
    "soccer/esp.1",
    "soccer/ger.1",
    "soccer/ita.1",
    "soccer/fra.1",
    "soccer/ned.1",
    "soccer/bel.1",
    "soccer/por.1",
    "soccer/uefa.champions",
    "soccer/uefa.europa",
    "soccer/uefa.europa.conf",
)

def _takimdan_espn_id_bul(url_basi, ev_ad, dep_ad, basliklar):
    tarih = datetime.now().strftime("%Y%m%d")
    ev_u = ev_ad.upper()
    dep_u = dep_ad.upper()
    for y in _TUM_ESPN_YOLLARI:
        try:
            r = requests.get(f"{url_basi}{y}/scoreboard?dates={tarih}", headers=basliklar, timeout=4)
            if r.status_code != 200:
                continue
            for ev in (r.json().get("events") or list()):
                isim = (ev.get("name") or "").upper()
                if (ev_u and ev_u in isim) or (dep_u and dep_u in isim):
                    return y, str(ev.get("id") or "")
        except Exception:
            continue
    return "", ""

def mac_hakem_verisi_cek(url_basi, yol, event_id, basliklar, ev_takim="", dep_takim=""):
    eid = str(event_id or "").strip()
    aktif_yol = str(yol or "").strip()

    if (not eid or "/" not in aktif_yol) and (ev_takim or dep_takim):
        bul_yol, bul_id = _takimdan_espn_id_bul(url_basi, str(ev_takim), str(dep_takim), basliklar)
        if bul_id:
            aktif_yol, eid = bul_yol, bul_id

    if eid and "/" in aktif_yol:
        try:
            r = requests.get(f"{url_basi}{aktif_yol}/summary?event={eid}", headers=basliklar, timeout=4)
            if r.status_code == 200:
                officials = ((r.json().get("gameInfo") or {}).get("officials") or list())
                isimler = list()
                for off in officials[:4]:
                    ad = (off.get("displayName") or off.get("fullName") or "").strip()
                    pos = ((off.get("position") or {}).get("displayName") or "").strip()
                    if ad:
                        isimler.append(f"{ad} ({pos})" if pos else ad)
                if isimler:
                    return f"Resmi Hakemler: {', '.join(isimler)}"
        except Exception:
            pass

    if ev_takim and dep_takim:
        try:
            q = urllib.parse.quote(f'"{ev_takim}" "{dep_takim}" (referee OR Schiedsrichter OR arbitro OR arbitre OR scheidsrechter OR hakem)')
            rss_url = f"https://google.com{q}&hl=en-US&gl=US&ceid=US:en"
            rr = requests.get(rss_url, headers=basliklar, timeout=5)
            if rr.status_code == 200:
                basliklar_xml = re.findall(r"<title>(.*?)</title>", rr.text)[1:6]
                for b in basliklar_xml:
                    m = re.search(r"(?:referee|schiedsrichter|arbitro|arbitre|scheidsrechter|hakem)[:\s-]+([A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+){1,2})", b, re.IGNORECASE)
                    if m:
                        return f"Resmi Hakem (Haber Kaydı): {m.group(1).strip()}"
        except Exception:
            pass

    return "Henüz resmi hakem ataması açıklanmadı"
