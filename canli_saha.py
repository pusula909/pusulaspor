import requests
import streamlit.components.v1 as components


def _gercek_mac_verisi_cek(spor_turu, lig_yolu, mac_id):
    veri = {
        "olaylar": list(),
        "istatistikler": list(),
        "durum_notu": "",
    }
    if not mac_id or not lig_yolu or lig_yolu == "euroleague_resmi":
        return veri
    try:
        kat = "basketball" if spor_turu == "Basketbol" else "soccer"
        host = ".".join(["site", "api", "espn", "com"])
        u = f"https://{host}/apis/site/v2/sports/{kat}/{lig_yolu}/summary?event={mac_id}"
        r = requests.get(u, headers={"User-Agent": "Mozilla/5.0"}, timeout=6).json()

        comp = r.get("header", {}).get("competitions", list())
        takim_map = {}
        if comp:
            ilk = comp.pop(0)
            for t in ilk.get("competitors", list()):
                tid = str(t.get("team", {}).get("id", ""))
                tad = t.get("team", {}).get("shortDisplayName", "") or t.get("team", {}).get("displayName", "")
                if tid:
                    takim_map[tid] = tad

            for d in ilk.get("details", list()):
                dk = d.get("clock", {}).get("displayValue", "")
                tid = str(d.get("team", {}).get("id", ""))
                tad = takim_map.get(tid, "")
                oyuncu = ""
                sporcular = d.get("athletesInvolved", list())
                if sporcular:
                    oyuncu = sporcular.pop(0).get("displayName", "")
                tip_yazi = d.get("type", {}).get("text", "")
                if d.get("scoringPlay"):
                    ikon = "⚽ GOL"
                elif d.get("redCard"):
                    ikon = "🟥 KIRMIZI KART"
                elif d.get("yellowCard"):
                    ikon = "🟨 SARI KART"
                else:
                    ikon = "📌 OLAY"
                satir = f"{ikon} | {dk}' {oyuncu} ({tad}) {tip_yazi}".strip()
                veri["olaylar"].append(satir)

        if not veri["olaylar"]:
            key_ev = r.get("keyEvents", list())
            for k in key_ev[-8:]:
                dk = k.get("clock", {}).get("displayValue", "")
                txt = k.get("text", "") or k.get("shortText", "")
                if txt:
                    veri["olaylar"].append(f"📌 {dk} {txt}".strip())

        if not veri["olaylar"] and spor_turu == "Basketbol":
            plays = r.get("plays", list())
            if isinstance(plays, list):
                for p in plays[-6:]:
                    dk = p.get("clock", {}).get("displayValue", "")
                    txt = p.get("text", "")
                    if txt:
                        veri["olaylar"].append(f"🏀 {dk} {txt}".strip())

        box_teams = r.get("boxscore", {}).get("teams", list())
        if len(box_teams) == 2:
            ev_stats = {}
            dep_stats = {}
            for t in box_teams:
                hedef = ev_stats if t.get("homeAway") == "home" else dep_stats
                for st in t.get("statistics", list()):
                    ad = str(st.get("name", "")).lower()
                    val = str(st.get("displayValue", "")).strip()
                    hedef[ad] = val

            eslesmeler = [
                ("possessionpct", "Topa Sahip Olma"),
                ("totalshots", "Toplam Sut"),
                ("shotsontarget", "Isabetli Sut"),
                ("woncorners", "Korner"),
                ("foulscommitted", "Faul"),
                ("yellowcards", "Sari Kart"),
                ("fieldgoalsmade", "Isabetli Atis"),
                ("threepointfieldgoalsmade", "3 Sayi Isabet"),
                ("totalrebounds", "Toplam Ribaund"),
                ("assists", "Asist"),
                ("turnovers", "Top Kaybi"),
            ]
            for kod, etiket in eslesmeler:
                v1 = ev_stats.get(kod, "")
                v2 = dep_stats.get(kod, "")
                if v1 and v2 and not (v1 == "0" and v2 == "0"):
                    veri["istatistikler"].append((etiket, v1, v2))
    except Exception:
        pass
    return veri
def canli_saha_goster(spor_turu, lig_yolu, mac_id, ev_ad, dep_ad, ev_skor="0", dep_skor="0", sure=""):
    try:
        veri = _gercek_mac_verisi_cek(spor_turu, lig_yolu, mac_id)
        olaylar = veri["olaylar"]
        istatistikler = veri["istatistikler"]
        dk_txt = sure or "CANLI"

        if olaylar:
            olay_html = "".join(
                f'<div style="padding:6px 10px;background:#1f2937;border-left:3px solid #10b981;border-radius:6px;margin-bottom:5px;font-size:12px;color:#f3f4f6;">{o}</div>'
                for o in olaylar[-8:]
            )
        else:
            olay_html = '<div style="padding:8px 10px;background:#1f2937;border-radius:6px;font-size:12px;color:#9ca3af;">Bu karsilasmada henuz kayitli resmi gol veya kart olayi bulunmuyor.</div>'

        ist_html = ""
        if istatistikler:
            satirlar = ""
            for etiket, v1, v2 in istatistikler[:6]:
                satirlar += f"""
                <div style="display:flex;justify-content:space-between;align-items:center;padding:5px 8px;border-bottom:1px solid #374151;font-size:12px;">
                  <span style="font-weight:700;color:#60a5fa;width:25%;text-align:left;">{v1}</span>
                  <span style="color:#d1d5db;width:50%;text-align:center;">{etiket}</span>
                  <span style="font-weight:700;color:#f87171;width:25%;text-align:right;">{v2}</span>
                </div>
                """
            ist_html = f'<div style="margin-top:10px;background:#1f2937;border-radius:8px;padding:6px;">{satirlar}</div>'

        yukseklik = 175 + (min(len(olaylar), 8) * 32) + (min(len(istatistikler), 6) * 28)

        html_kodu = f"""
        <div style="font-family:sans-serif;background:#111827;color:#f9fafb;padding:14px;border-radius:14px;border:1px solid #374151;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid #374151;font-size:14px;">
            <span style="font-weight:700;color:#60a5fa;">🏠 {ev_ad} ({ev_skor})</span>
            <span style="background:#dc2626;color:#fff;padding:3px 10px;border-radius:99px;font-weight:700;font-size:11px;">● {dk_txt}</span>
            <span style="font-weight:700;color:#f87171;">({dep_skor}) {dep_ad} ✈️</span>
          </div>
          <div style="font-size:11px;font-weight:700;color:#9ca3af;margin-bottom:6px;letter-spacing:0.5px;">📋 RESMI MAC OLAYLARI & ZAMAN TUNELI</div>
          {olay_html}
          {ist_html}
        </div>
        """
        components.html(html_kodu, height=min(480, max(190, yukseklik)))
    except Exception:
        pass
