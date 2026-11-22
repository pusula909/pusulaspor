import requests
import streamlit.components.v1 as components


def _espn_canli_aksiyon_cek(spor_turu, lig_yolu, mac_id):
    sonuc = {
        "aksiyon": "Canli saha akisi izleniyor...",
        "dakika": "",
        "taraf": "orta",
        "tip": "normal",
        "ev_baski": 50,
    }
    if not mac_id or not lig_yolu or lig_yolu == "euroleague_resmi":
        return sonuc
    try:
        kat = "basketball" if spor_turu == "Basketbol" else "soccer"
        host = ".".join(["site", "api", "espn", "com"])
        u = f"https://{host}/apis/site/v2/sports/{kat}/{lig_yolu}/summary?event={mac_id}"
        r = requests.get(u, headers={"User-Agent": "Mozilla/5.0"}, timeout=5).json()

        olaylar = r.get("keyEvents", list())
        if not olaylar:
            drives = r.get("plays", list())
            if isinstance(drives, list):
                olaylar = drives

        if olaylar:
            son = olaylar[-1]
            metin = son.get("text", "") or son.get("shortText", "")
            sure = son.get("clock", {}).get("displayValue", "")
            if metin:
                sonuc["aksiyon"] = metin[:95]
                sonuc["dakika"] = sure

            alt = metin.lower()
            if any(k in alt for k in ("goal", "gol", "3pt", "three point", "dunk", "layup")):
                sonuc["tip"] = "gol"
            elif any(k in alt for k in ("shot", "sut", "corner", "korner", "save", "kurtaris", "foul", "faul", "rebound")):
                sonuc["tip"] = "tehlike"

            takim_id = str(son.get("team", {}).get("id", ""))
            comp = r.get("header", {}).get("competitions", list())
            if comp:
                takimlar = comp.pop(0).get("competitors", list())
                ev_id = ""
                dep_id = ""
                for t in takimlar:
                    if t.get("homeAway") == "home":
                        ev_id = str(t.get("team", {}).get("id", ""))
                    elif t.get("homeAway") == "away":
                        dep_id = str(t.get("team", {}).get("id", ""))
                if takim_id and takim_id == ev_id:
                    sonuc["taraf"] = "ev"
                    sonuc["ev_baski"] = 68 if sonuc["tip"] != "normal" else 58
                elif takim_id and takim_id == dep_id:
                    sonuc["taraf"] = "dep"
                    sonuc["ev_baski"] = 32 if sonuc["tip"] != "normal" else 42
    except Exception:
        pass
    return sonuc


def canli_saha_goster(spor_turu, lig_yolu, mac_id, ev_ad, dep_ad, ev_skor="0", dep_skor="0", sure=""):
    try:
        veri = _espn_canli_aksiyon_cek(spor_turu, lig_yolu, mac_id)
        taraf = veri["taraf"]
        tip = veri["tip"]
        ev_baski = veri["ev_baski"]
        dep_baski = 100 - ev_baski
        aksiyon_txt = veri["aksiyon"].replace('"', "'").replace("<", "").replace(">", "")
        dk_txt = veri["dakika"] or sure or "CANLI"

        if taraf == "ev":
            top_x = 82 if tip in ("gol", "tehlike") else 66
            ok_txt = f"➡️ {ev_ad} Hucumda"
        elif taraf == "dep":
            top_x = 18 if tip in ("gol", "tehlike") else 34
            ok_txt = f"⬅️ {dep_ad} Hucumda"
        else:
            top_x = 50
            ok_txt = "⚡ Orta Saha Mucadelesi"

        top_renk = "#ff2e4c" if tip == "gol" else ("#ffd60a" if tip == "tehlike" else "#ffffff")

        if spor_turu == "Basketbol":
            saha_svg = f"""
            <svg viewBox="0 0 600 260" width="100%" height="210" style="border-radius:12px;box-shadow:0 4px 14px rgba(0,0,0,0.25);">
              <defs>
                <linearGradient id="parke" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stop-color="#c98a4b"/>
                  <stop offset="50%" stop-color="#d99b5b"/>
                  <stop offset="100%" stop-color="#c98a4b"/>
                </linearGradient>
              </defs>
              <rect x="0" y="0" width="600" height="260" fill="url(#parke)"/>
              <rect x="14" y="14" width="572" height="232" fill="none" stroke="#ffffff" stroke-width="3"/>
              <line x1="300" y1="14" x2="300" y2="246" stroke="#ffffff" stroke-width="3"/>
              <circle cx="300" cy="130" r="36" fill="rgba(255,255,255,0.12)" stroke="#ffffff" stroke-width="3"/>
              <rect x="14" y="82" width="95" height="96" fill="rgba(180,50,30,0.25)" stroke="#ffffff" stroke-width="2.5"/>
              <rect x="491" y="82" width="95" height="96" fill="rgba(30,80,180,0.25)" stroke="#ffffff" stroke-width="2.5"/>
              <path d="M 14 35 Q 165 130 14 225" fill="none" stroke="#ffffff" stroke-width="2.5"/>
              <path d="M 586 35 Q 435 130 586 225" fill="none" stroke="#ffffff" stroke-width="2.5"/>
              <circle cx="32" cy="130" r="8" fill="none" stroke="#ff4500" stroke-width="3"/>
              <circle cx="568" cy="130" r="8" fill="none" stroke="#ff4500" stroke-width="3"/>
              <circle cx="{top_x * 6}" cy="130" r="14" fill="{top_renk}" opacity="0.35">
                <animate attributeName="r" values="10;20;10" dur="1.4s" repeatCount="indefinite"/>
              </circle>
              <circle cx="{top_x * 6}" cy="130" r="8" fill="#ff6b00" stroke="#111" stroke-width="2"/>
            </svg>
            """
        else:
            saha_svg = f"""
            <svg viewBox="0 0 600 260" width="100%" height="210" style="border-radius:12px;box-shadow:0 4px 14px rgba(0,0,0,0.25);">
              <rect x="0" y="0" width="600" height="260" fill="#1b7a37"/>
              <rect x="60" y="0" width="60" height="260" fill="#218c40"/>
              <rect x="180" y="0" width="60" height="260" fill="#218c40"/>
              <rect x="300" y="0" width="60" height="260" fill="#218c40"/>
              <rect x="420" y="0" width="60" height="260" fill="#218c40"/>
              <rect x="540" y="0" width="60" height="260" fill="#218c40"/>
              <rect x="16" y="14" width="568" height="232" fill="none" stroke="rgba(255,255,255,0.88)" stroke-width="2.5"/>
              <line x1="300" y1="14" x2="300" y2="246" stroke="rgba(255,255,255,0.88)" stroke-width="2.5"/>
              <circle cx="300" cy="130" r="38" fill="none" stroke="rgba(255,255,255,0.88)" stroke-width="2.5"/>
              <circle cx="300" cy="130" r="3.5" fill="#ffffff"/>
              <rect x="16" y="62" width="84" height="136" fill="none" stroke="rgba(255,255,255,0.88)" stroke-width="2.5"/>
              <rect x="16" y="96" width="32" height="68" fill="none" stroke="rgba(255,255,255,0.88)" stroke-width="2"/>
              <rect x="500" y="62" width="84" height="136" fill="none" stroke="rgba(255,255,255,0.88)" stroke-width="2.5"/>
              <rect x="552" y="96" width="32" height="68" fill="none" stroke="rgba(255,255,255,0.88)" stroke-width="2"/>
              <circle cx="{top_x * 6}" cy="130" r="16" fill="{top_renk}" opacity="0.4">
                <animate attributeName="r" values="10;22;10" dur="1.3s" repeatCount="indefinite"/>
              </circle>
              <circle cx="{top_x * 6}" cy="130" r="7.5" fill="{top_renk}" stroke="#111111" stroke-width="2"/>
            </svg>
            """

        html_kodu = f"""
        <div style="font-family:sans-serif;background:#111827;color:#f9fafb;padding:12px;border-radius:14px;border:1px solid #374151;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:13px;">
            <span style="font-weight:700;color:#60a5fa;">🏠 {ev_ad} ({ev_skor})</span>
            <span style="background:#dc2626;color:#fff;padding:2px 8px;border-radius:99px;font-weight:700;font-size:11px;">● {dk_txt}</span>
            <span style="font-weight:700;color:#f87171;">({dep_skor}) {dep_ad} ✈️</span>
          </div>
          {saha_svg}
          <div style="margin-top:8px;background:#1f2937;padding:8px 10px;border-radius:8px;display:flex;justify-content:space-between;align-items:center;font-size:12px;">
            <span style="color:#34d399;font-weight:700;">{ok_txt}</span>
            <span style="color:#e5e7eb;">{aksiyon_txt}</span>
          </div>
          <div style="margin-top:8px;">
            <div style="display:flex;justify-content:space-between;font-size:11px;color:#9ca3af;margin-bottom:3px;">
              <span>Atak Baskisi %{ev_baski}</span>
              <span>%{dep_baski} Atak Baskisi</span>
            </div>
            <div style="width:100%;height:7px;background:#ef4444;border-radius:99px;overflow:hidden;">
              <div style="width:{ev_baski}%;height:100%;background:#3b82f6;"></div>
            </div>
          </div>
        </div>
        """
        components.html(html_kodu, height=325)
    except Exception:
        pass
