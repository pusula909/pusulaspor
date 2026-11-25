import requests

def mac_hakem_verisi_cek(url_basi, yol, event_id, basliklar, ev_takim="", dep_takim=""):
    isimler = list()
    if yol and yol != "euroleague_resmi" and event_id:
        try:
            veri = requests.get(f"{url_basi}{yol}/summary?event={event_id}", headers=basliklar, timeout=5).json()
            officials = ((veri.get("gameInfo") or {}).get("officials") or list())
            for off in officials[:3]:
                ad = (off.get("displayName") or off.get("fullName") or "").strip()
                pos = ((off.get("position") or {}).get("displayName") or "").strip()
                if ad:
                    isimler.append(f"{ad} ({pos})" if pos else ad)
        except Exception:
            pass

    if isimler:
        return f"Resmi Hakemler: {', '.join(isimler)}"

    if ev_takim and dep_takim:
        try:
            try:
                from ddgs import DDGS
            except Exception:
                from duckduckgo_search import DDGS
            notlar = list()
            with DDGS() as ddgs:
                for q in [f"{ev_takim} {dep_takim} referee", f"{ev_takim} {dep_takim} hakemi"]:
                    for s in list(ddgs.text(q, max_results=2)):
                        oz = (s.get("title", "") + " - " + s.get("body", ""))[:180]
                        if oz.strip():
                            notlar.append(oz)
            if notlar:
                return f"Resmi Atama Kaydı: {' // '.join(notlar[:2])}"
        except Exception:
            pass

    return "Henüz resmi hakem ataması yayınlanmadı"
