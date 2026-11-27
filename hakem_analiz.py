import requests

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

def mac_hakem_verisi_cek(url_basi, yol, event_id, basliklar, ev_takim="", dep_takim=""):
    eid = str(event_id or "").strip()
    if not eid or str(yol) == "euroleague_resmi":
        return "Henüz resmi hakem bilgisi düşmedi"

    aday_yollar = [yol] if (yol and "/" in str(yol)) else list(_TUM_ESPN_YOLLARI)
    for y in aday_yollar:
        try:
            r = requests.get(f"{url_basi}{y}/summary?event={eid}", headers=basliklar, timeout=4)
            if r.status_code != 200:
                continue
            veri = r.json()
            header_comps = ((veri.get("header") or {}).get("competitions") or list())
            if not header_comps:
                continue
            officials = ((veri.get("gameInfo") or {}).get("officials") or list())
            isimler = list()
            for off in officials[:4]:
                ad = (off.get("displayName") or off.get("fullName") or "").strip()
                pos = ((off.get("position") or {}).get("displayName") or "").strip()
                if ad:
                    isimler.append(f"{ad} ({pos})" if pos else ad)
            if isimler:
                return f"Resmi Hakemler: {', '.join(isimler)}"
            return "Henüz resmi hakem ataması açıklanmadı (ESPN resmi maç özeti)"
        except Exception:
            continue

    return "Henüz resmi hakem ataması açıklanmadı"
