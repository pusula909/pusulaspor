import streamlit as st
import requests

def canli_saha_ve_anlatim_ciz(spor, lig_yolu, mac_id, ev_ad, dep_ad, ev_skor, dep_skor, state, durum_detay, url_basi, basliklar):
    st.subheader("Canli Mac Merkezi | 2D Saha Radari & Anlik Anlatim")
    if state == "pre": son_olay = "Mac Baslamasi Bekleniyor"
    elif state == "post": son_olay = "Mac Sona Erdi"
    else: son_olay = f"Canli Oyun Devam Ediyor ({durum_detay})"
    olaylar, istatistikler = list(), list()
    x_pos, y_pos = 50, 50
    if lig_yolu == "euroleague_resmi" and mac_id:
        try:
            h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            pb = requests.get("https://feeds.incrowdsports.com/provider/euroleague/v2/games/"+str(mac_id)+"/playbyplay", params={"seasonCode": "E2026"}, headers=h, timeout=5).json()
            for p in pb.get("data", {}).get("plays", list())[-8:]:
                txt = p.get("typeDescription", p.get("text", ""))
                pl = p.get("playerName", "")
                clk = p.get("clock", "")
                if txt: olaylar.append(f"{clk} - {pl} {txt}".strip())
            if olaylar:
                son_olay = olaylar[-1]
                x_pos = 78 if int(ev_skor) >= int(dep_skor) else 22
        except Exception:
            pass
    elif lig_yolu != "euroleague_resmi" and mac_id:
        try:
            s_veri = requests.get(f"{url_basi}{lig_yolu}/summary?event={mac_id}", headers=basliklar, timeout=6).json()
            for p in s_veri.get("plays", list())[-8:]:
                txt = p.get("text", "")
                clk = p.get("clock", {}).get("displayValue", "")
                per = p.get("period", {}).get("number", "")
                if txt: olaylar.append(f"P{per} ({clk}) - {txt}")
            if olaylar:
                son_olay = olaylar[-1]
                if ev_ad.lower() in son_olay.lower(): x_pos = 78
                elif dep_ad.lower() in son_olay.lower(): x_pos = 22
            box = s_veri.get("boxscore", {}).get("teams", list())
            if len(box) >= 2:
                s1 = {x.get("label", x.get("name", "")): x.get("displayValue", "0") for x in box[0].get("statistics", list())}
                s2 = {x.get("label", x.get("name", "")): x.get("displayValue", "0") for x in box[1].get("statistics", list())}
                for k in list(s1.keys())[:6]:
                    istatistikler.append({"Istatistik": k, ev_ad: s1.get(k, "-"), dep_ad: s2.get(k, "-")})
        except Exception:
            pass
    c1, c2 = st.columns([1.3, 1])
    with c1:
        if spor == "Futbol":
            svg = f'<svg viewBox="0 0 400 240" style="width:100%;border-radius:12px;background:#15803d;border:3px solid #fff"><rect x="10" y="10" width="380" height="220" fill="none" stroke="#fff" stroke-width="2"/><line x1="200" y1="10" x2="200" y2="230" stroke="#fff" stroke-width="2"/><circle cx="200" cy="120" r="32" fill="none" stroke="#fff" stroke-width="2"/><rect x="10" y="65" width="55" height="110" fill="none" stroke="#fff" stroke-width="2"/><rect x="335" y="65" width="55" height="110" fill="none" stroke="#fff" stroke-width="2"/><circle cx="{x_pos*3.6+20}" cy="{y_pos*2+20}" r="9" fill="#facc15" stroke="#000" stroke-width="2"/><text x="200" y="28" fill="#fff" font-size="13" font-weight="bold" text-anchor="middle">{ev_ad} {ev_skor} - {dep_skor} {dep_ad}</text></svg>'
        else:
            svg = f'<svg viewBox="0 0 400 240" style="width:100%;border-radius:12px;background:#d97706;border:3px solid #78350f"><rect x="10" y="10" width="380" height="220" fill="#f59e0b" stroke="#fff" stroke-width="2"/><line x1="200" y1="10" x2="200" y2="230" stroke="#fff" stroke-width="2"/><circle cx="200" cy="120" r="28" fill="none" stroke="#fff" stroke-width="2"/><path d="M 10 40 Q 110 120 10 200" fill="none" stroke="#fff" stroke-width="2"/><path d="M 390 40 Q 290 120 390 200" fill="none" stroke="#fff" stroke-width="2"/><circle cx="{x_pos*3.6+20}" cy="120" r="10" fill="#dc2626" stroke="#fff" stroke-width="2"/><text x="200" y="28" fill="#fff" font-size="13" font-weight="bold" text-anchor="middle">{ev_ad} {ev_skor} - {dep_skor} {dep_ad}</text></svg>'
        st.markdown(svg, unsafe_allow_html=True)
        st.info(f"Son Aksiyon: {son_olay}")
    with c2:
        st.markdown("**Canli Mac Anlatimi (Son Olaylar)**")
        if olaylar:
            for o in reversed(olaylar[-5:]):
                st.caption(o)        else:
            st.caption("Canli akis verisi bekleniyor veya mac henuz baslamadi.")
        if istatistikler:
            st.markdown("**Canli Mac Istatistikleri**")
            st.dataframe(istatistikler, use_container_width=True, hide_index=True)
