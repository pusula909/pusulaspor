import requests

def mac_hakem_verisi_cek(url_basi, yol, event_id, basliklar):
    isimler = list()
    ev_ad = ""
    dep_ad = ""
    if yol and yol != "euroleague_resmi" and event_id:
        try:
            veri = requests.get(f"{url_basi}{yol}/summary?event={event_id}", headers=basliklar, timeout=5).json()
            officials = ((veri.get("gameInfo") or {}).get("officials") or list())
            for off in officials[:3]:
                ad = (off.get("displayName") or off.get("fullName") or "").strip()
                pos = ((off.get("position") or {}).get("displayName") or "").strip()
                if ad:
                    isimler.append(f"{ad} ({pos})" if pos else ad)
            comps = ((veri.get("header") or {}).get("competitions") or list())
            if comps:
                tlist = (comps[0].get("competitors") or list())
                if len(tlist) >= 2:
                    ev_ad = ((tlist[0].get("team") or {}).get("displayName") or "")
                    dep_ad = ((tlist[1].get("team") or {}).get("displayName") or "")
        except Exception:
            pass

    if isimler:
        return f" | Resmi Hakemler: {', '.join(isimler)}"

    if ev_ad and dep_ad:
        try:
            from duckduckgo_search import DDGS
            notlar = list()
            with DDGS() as ddgs:
                for q in [f"{ev_ad} {dep_ad} referee", f"{ev_ad} {dep_ad} hakem"]:
                    for s in list(ddgs.text(q, max_results=2)):
                        oz = (s.get("title", "") + " - " + s.get("body", ""))[:180]
                        if oz.strip():
                            notlar.append(oz)
            if notlar:
                return f" | Web Resmi Hakem İstihbaratı: {' // '.join(notlar[:2])}"
        except Exception:
            pass

    return " | Resmi Hakemler: Henüz resmi atama açıklanmadı (isim uydurma)"
