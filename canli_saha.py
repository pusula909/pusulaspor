import requests
import streamlit.components.v1 as components


def _istatistik_oku(box_teams):
    veri = {
        "ev_sut": 0, "dep_sut": 0,
        "ev_isabet": 0, "dep_isabet": 0,
        "ev_korner": 0, "dep_korner": 0,
        "ev_top": 50, "dep_top": 50,
    }
    try:
        for t in box_teams:
            taraf = t.get("homeAway", "")
            prefix = "ev_" if taraf == "home" else ("dep_" if taraf == "away" else "")
            if not prefix:
                continue
            for st in t.get("statistics", list()):
                ad = str(st.get("name", "")).lower()
                val_str = str(st.get("displayValue", "0")).replace("%", "").strip()
                try:
                    val = int(float(val_str))
                except Exception:
                    val = 0
                if ad in ("totalshots", "shots", "fieldgoalsattempted"):
                    veri[prefix + "sut"] = val
                elif ad in ("shotsontarget", "shotsongoal", "fieldgoalsmade"):
                    veri[prefix + "isabet"] = val
                elif ad in ("woncorners", "cornerkicks", "rebounds", "totalrebounds"):
                    veri[prefix + "korner"] = val
                elif ad in ("possessionpct", "possession"):
                    veri[prefix + "top"] = val
    except Exception:
        pass
    return veri


def _espn_canli_aksiyon_cek(spor_turu, lig_yolu, mac_id):
    sonuc = {
        "aksiyon": "Canli mac verileri senkronize ediliyor...",
        "dakika": "",
        "taraf": "orta",
        "tip": "normal",
        "ev_baski": 50,
        "istatistik_ozet": "",
    }
    if not mac_id or not lig_yolu or lig_yolu == "euroleague_resmi":
        return sonuc
    try:
        kat = "basketball" if spor_turu == "Basketbol" else "soccer"
        host = ".".join(["site", "api", "espn", "com"])
        u = f"https://{host}/apis/site/v2/sports/{kat}/{lig_yolu}/summary?event={mac_id}"
        r = requests.get(u, headers={"User-Agent": "Mozilla/5.0"}, timeout=6).json()

        comp = r.get("header", {}).get("competitions", list())
        ev_id = ""
        dep_id = ""
        if comp:
            for t in comp.pop(0).get("competitors", list()):
                if t.get("homeAway") == "home":
                    ev_id = str(t.get("team", {}).get("id", ""))
                elif t.get("homeAway") == "away":
                    dep_id = str(t.get("team", {}).get("id", ""))

        box_teams = r.get("boxscore", {}).get("teams", list())
        ist = _istatistik_oku(box_teams)

        if spor_turu == "Basketbol":
            sonuc["istatistik_ozet"] = f"Sut: {ist['ev_sut']}-{ist['dep_sut']} | Isabet: {ist['ev_isabet']}-{ist['dep_isabet']} | Ribaund: {ist['ev_korner']}-{ist['dep_korner']}"
        else:
            sonuc["istatistik_ozet"] = f"Top: %{ist['ev_top']}-%{ist['dep_top']} | Sut: {ist['ev_sut']}-{ist['dep_sut']} (Isabet: {ist['ev_isabet']}-{ist['dep_isabet']}) | Korner: {ist['ev_korner']}-{ist['dep_korner']}"

        ev_guc = (ist["ev_sut"] * 3) + (ist["ev_isabet"] * 5) + (ist["ev_korner"] * 4) + ist["ev_top"]
        dep_guc = (ist["dep_sut"] * 3) + (ist["dep_isabet"] * 5) + (ist["dep_korner"] * 4) + ist["dep_top"]
        toplam_guc = ev_guc + dep_guc
        if toplam_guc > 0:
            oran = int((ev_guc / toplam_guc) * 100)
            sonuc["ev_baski"] = max(22, min(78, oran))
            if sonuc["ev_baski"] >= 55:
                sonuc["taraf"] = "ev"
                sonuc["tip"] = "tehlike" if sonuc["ev_baski"] >= 63 else "normal"
            elif sonuc["ev_baski"] <= 45:
                sonuc["taraf"] = "dep"
                sonuc["tip"] = "tehlike" if sonuc["ev_baski"] <= 37 else "normal"

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
                sonuc["aksiyon"] = metin[:90]
                sonuc["dakika"] = sure
            alt = metin.lower()
            if any(k in alt for k in ("goal", "gol", "3pt", "three point", "dunk", "layup")):
                sonuc["tip"] = "gol"
            takim_id = str(son.get("team", {}).get("id", ""))
            if takim_id and takim_id == ev_id:
                sonuc["taraf"] = "ev"
            elif takim_id and takim_id == dep_id:
                sonuc["taraf"] = "dep"
        else:
            if sonuc["taraf"] == "ev":
                sonuc["aksiyon"] = "Ev sahibi rakip yari sahada baski kuruyor"
            elif sonuc["taraf"] == "dep":
                sonuc["aksiyon"] = "Deplasman ekibi hucum ustunlugunu elinde tutuyor"
            else:
                sonuc["aksiyon"] = "Iki takim da dengeli oyun sergiliyor"
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
        ist_txt = veri["istatistik_ozet"]
        dk_txt = veri["dakika"] or sure or "CANLI"

        if taraf == "ev":
            x1, x2 = (380, 520) if tip in ("gol", "tehlike") else (330, 440)
            ok_txt = f"➡️ {ev_ad} Atakta"
        elif taraf == "dep":
            x1, x2 = (220, 80) if tip in ("gol", "tehlike") else (270, 160)
            ok_txt = f"⬅️ {dep_ad} Atakta"
        else:
            x1, x2 = (240, 360)
            ok_txt = "⚡ Dengeli Oyun Akisi"

        top_renk = "#ff2e4c" if tip == "gol" else ("#ffd60a" if tip == "tehlike" else "#ffffff")

        if spor_turu == "Basketbol":
            saha_svg = f"""
            <svg viewBox="0 0 600 250" width="100%" height="205" style="border-radius:12px;box-shadow:0 4px 14px rgba(0,0,0,0.3);">
              <defs>
                <linearGradient id="parke" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stop-color="#c98a4b"/>
                  <stop offset="50%" stop-color="#d99b5b"/>
                  <stop offset="100%" stop-color="#c98a4b"/>
                </linearGradient>
              </defs>
              <rect x="0" y="0" width="600" height="250" fill="url(#parke)"/>
              <rect x="14" y="14" width="572" height="222" fill="none" stroke="#ffffff" stroke-width="3"/>
              <line x1="300" y1="14" x2="300" y2="236" stroke="#ffffff" stroke-width="3"/>
              <circle cx="300" cy="125" r="35" fill="rgba(255,255,255,0.12)" stroke="#ffffff" stroke-width="3"/>
              <rect x="14" y="78" width="95" height="94" fill="rgba(180,50,30,0.25)" stroke="#ffffff" stroke-width="2.5"/>
              <rect x="491" y="78" width="95" height="94" fill="rgba(30,80,180,0.25)" stroke="#ffffff" stroke-width="2.5"/>
              <path d="M 14 32 Q 165 125 14 218" fill="none" stroke="#ffffff" stroke-width="2.5"/>
              <path d="M 586 32 Q 435 125 586 218" fill="none" stroke="#ffffff" stroke-width="2.5"/>
              <circle cx="32" cy="125" r="8" fill="none" stroke="#ff4500" stroke-width="3"/>
              <circle cx="568" cy="125" r="8" fill="none" stroke="#ff4500" stroke-width="3"/>
              <g>
                <animateTransform attributeName="transform" type="translate" values="{x1-300},0; {x2-300},-24; {x2-300},24; {x1-300},0" dur="3.6s" repeatCount="indefinite"/>
                <circle cx="300" cy="125" r="16" fill="{top_renk}" opacity="0.4"/>
                <circle cx="300" cy="125" r="8.5" fill="#ff6b00" stroke="#111" stroke-width="2"/>
              </g>
            </svg>
            """
        else:
            saha_svg = f"""
            <svg viewBox="0 0 600 250" width="100%" height="205" style="border-radius:12px;box-shadow:0 4px 14px rgba(0,0,0,0.3);">
              <rect x="0" y="0" width="600" height="250" fill="#1b7a37"/>
              <rect x="60" y="0" width="60" height="250" fill="#218c40"/>
              <rect x="180" y="0" width="60" height="250" fill="#218c40"/>
              <rect x="300" y="0" width="60" height="250" fill="#218c40"/>
              <rect x="420" y="0" width="60" height="250" fill="#218c40"/>
              <rect x="540" y="0" width="60" height="250" fill="#218c40"/>
              <rect x="16" y="14" width="568" height="222" fill="none" stroke="rgba(255,255,255,0.88)" stroke-width="2.5"/>
              <line x1="300" y1="14" x2="300" y2="236" stroke="rgba(255,255,255,0.88)" stroke-width="2.5"/>
              <circle cx="300" cy="125" r="36" fill="none" stroke="rgba(255,255,255,0.88)" stroke-width="2.5"/>
              <circle cx="300" cy="125" r="3.5" fill="#ffffff"/>
              <rect x="16" y="58" width="84" height="134" fill="none" stroke="rgba(255,255,255,0.88)" stroke-width="2.5"/>
              <rect x="16" y="92" width="32" height="66" fill="none" stroke="rgba(255,255,255,0.88)" stroke-width="2"/>
              <rect x="500" y="58" width="84" height="134" fill="none" stroke="rgba(255,255,255,0.88)" stroke-width="2.5"/>
              <rect x="552" y="92" width="32" height="66" fill="none" stroke="rgba(255,255,255,0.88)" stroke-width="2"/>
              <g>
                <animateTransform attributeName="transform" type="translate" values="{x1-300},0; {x2-300},-28; {x2-300},26; {x1-300},0" dur="3.8s" repeatCount="indefinite"/>
                <circle cx="300" cy="125" r="17" fill="{top_renk}" opacity="0.42"/>
                <circle cx="300" cy="125" r="8" fill="{top_renk}" stroke="#111111" stroke-width="2"/>
              </g>
            </svg>
            """

        html_kodu = f"""
        <div style="font-family:sans-serif;background:#111827;color:#f9fafb;padding:12px;border-radius:14px;border:1px solid #374151;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:13px;">
            <span style="font-weight:700;color:#60a5fa;">🏠 {ev_ad} ({ev_skor})</span>
            <span style="background:#dc2626;color:#fff;padding:2px 9px;border-radius:99px;font-weight:700;font-size:11px;">● {dk_txt}</span>
            <span style="font-weight:700;color:#f87171;">({dep_skor}) {dep_ad} ✈️</span>
          </div>
          {saha_svg}
          <div style="margin-top:8px;background:#1f2937;padding:8px 10px;border-radius:8px;display:flex;justify-content:space-between;align-items:center;font-size:12px;gap:8px;">
            <span style="color:#34d399;font-weight:700;white-space:nowrap;">{ok_txt}</span>
            <span style="color:#e5e7eb;text-align:right;">{aksiyon_txt}</span>
          </div>
          <div style="margin-top:6px;text-align:center;font-size:11px;color:#fbbf24;font-weight:600;">
            📊 {ist_txt}
          </div>
          <div style="margin-top:6px;">
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
        components.html(html_kodu, height=345)
    except Exception:
        pass
