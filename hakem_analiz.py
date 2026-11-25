import requests

def mac_hakem_verisi_cek(url_basi, yol, event_id, basliklar):
    if not yol or yol == "euroleague_resmi" or not event_id:
        return ""
    try:
        veri = requests.get(f"{url_basi}{yol}/summary?event={event_id}", headers=basliklar, timeout=5).json()
        officials = ((veri.get("gameInfo") or {}).get("officials") or list())
        isimler = list()
        for off in officials[:3]:
            ad = (off.get("displayName") or off.get("fullName") or "").strip()
            pos = ((off.get("position") or {}).get("displayName") or "").strip()
            if ad:
                isimler.append(f"{ad} ({pos})" if pos else ad)
        if isimler:
            return f" | Resmi Hakemler: {', '.join(isimler)}"
        return " | Resmi Hakemler: Henüz açıklanmadı (isim uydurma)"
    except Exception:
        return ""
