import json
import os


def lig_basari_bonusu_getir(lig_adi):
    if not os.path.exists("haftalik_arsiv.json"):
        return 0
    try:
        with open("haftalik_arsiv.json", "r", encoding="utf-8") as f:
            veriler = json.load(f)
        lig_maclar = list(x for x in veriler if x.get("lig") == lig_adi)
        if len(lig_maclar) < 3:
            return 0
        oran = sum(int(x.get("tuttu", 0)) for x in lig_maclar) / len(lig_maclar)
        if oran >= 0.70:
            return 6
        if oran < 0.45:
            return -8
    except Exception:
        pass
    return 0


def sharp_piyasa_durumu_getir(mac_id):
    if not os.path.exists("piyasa_hafiza.json") or not mac_id:
        return 0, ""
    try:
        with open("piyasa_hafiza.json", "r", encoding="utf-8") as f:
            p_veri = json.load(f)
        kayit = p_veri.get("maclar", {}).get(str(mac_id), {})
        if kayit.get("sharp_uyari"):
            return 8, kayit.get("sharp_uyari", "")
    except Exception:
        pass
    return 0, ""
