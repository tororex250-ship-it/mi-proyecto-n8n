#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
OMEGA-QUANT v32 ARGON-APEX | UNIFIED SPACETIME & BIOMETRIC TENNIS ORACLE
=============================================================================
Arquitectura Unificada (v30 Apex + v32 Argon):
  • Leyes del Tiempo (Triple Decaimiento): 50% (18d) + 30% (55d) + 20% (240d).
  • Vector de Aceleración Temporal: Momentum 65d vs Línea Base Histórica.
  • Telemetría Biométrica Completa: 1st In, 1st Won, 2nd Won, Ace%, DF%,
    Break Point Save% (Anti-Luck) y Break Point Conversion% al Resto.
  • Ley de Aclimatación en Altura (>1000m) vs Debut en Frío (0m/72h).
  • Escaneo Completo de Lateralidad Zurda ('L' ATP/WTA) en todos los CSVs.
  • Markov Intra-Set No-Estacionario: Ciclo de Pelotas (7/9j) + Tiebreak Exacto.
  • Trayectoria 4D (S1 -> S2 -> S3) con Fatiga 72h, Descanso y Deriva Térmica.
  • Protección Anti-Trampa en Altitud/Rally Corto + Candado Sharp de Pinnacle.
  • Salida Cero-Ruido (42 cols POCO X6 Pro) + Filtro Institucional Quarter-Kelly.
=============================================================================
"""

import sys
import os
import json
import math
import time
import sqlite3
import unicodedata
import glob
import re
from datetime import datetime, timezone
from typing import Dict, Tuple, Optional, Any, List
import requests
import numpy as np

try:
    from rapidfuzz import fuzz, process
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

def bind_to_cortex_a715():
    if hasattr(os, "sched_setaffinity"):
        try:
            avail = os.cpu_count() or 8
            cores = {c for c in (4, 5, 6, 7) if c < avail}
            if cores:
                os.sched_setaffinity(0, cores)
        except Exception:
            pass

bind_to_cortex_a715()

W = 42
SEP, DIV, SUB = "━" * W, "─" * W, "╌" * W
C_RST, C_BLD, C_CYN = "\033[0m", "\033[1m", "\033[1;36m"
C_GRN, C_RED, C_YLW, C_DIM = "\033[1;32m", "\033[1;31m", "\033[1;33m", "\033[2m"
ANSI_REGEX = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

def pad_line(s: str, width: int = W) -> str:
    vlen = len(ANSI_REGEX.sub("", s))
    return s if vlen >= width else s + " " * (width - vlen)

OWM_KEY = "e9217773c7bb714d19cf13dff0e35e72"
DB_PATH = "sportradar_cache.db"

CITY_ELEVATION_METERS = {
    "GUADALAJARA": 1566, "MADRID": 667, "BOGOTA": 2600, "GSTAAD": 1050,
    "KITZBUHEL": 760, "MEXICO": 2240, "QUITO": 2850, "MUNICH": 520,
    "SAO PAULO": 760, "JOHANNESBURG": 1753, "ALMATY": 700, "CHENGDU": 500,
    "WINSTON": 296, "WINSTONSALEM": 296, "CINCINNATI": 200, "BASEL": 260,
    "VIENNA": 171, "SANTIAGO": 570, "CORDOBA": 400, "GENEVA": 375,
    "ATLANTA": 320, "STUTTGART": 245, "NEW YORK": 10, "MELBOURNE": 15,
    "PARIS": 35, "LONDON": 15, "ROME": 20, "MIAMI": 2, "INDIAN WELLS": 39,
    "MONTE CARLO": 50, "BEIJING": 44, "WUHAN": 23, "SHANGHAI": 4,
    "TORONTO": 76, "MONTREAL": 23, "TOKYO": 40, "DUBAI": 5, "DOHA": 10
}

KNOWN_HANDEDNESS = {
    "nadal": "L", "shapovalov": "L", "norrie": "L", "mannarino": "L",
    "umbert": "L", "shelton": "L", "cerundolo": "L", "juan manuel cerundolo": "L",
    "albert ramos": "L", "nishioka": "L", "thiago monteiro": "L", "draper": "L",
    "tien": "L", "tabilo": "L", "bellucci": "L", "kayla day": "L", "day": "L",
    "fernandez": "L", "leylah fernandez": "L", "haddad maia": "L", "trevisan": "L",
    "danilovic": "L", "shnaider": "L", "vondrousova": "L", "kvitova": "L",
    "kerber": "L", "rus": "L", "arango": "R", "samsonova": "R", "jacquemot": "R",
    "alcaraz": "R", "sinner": "R", "djokovic": "R", "medvedev": "R",
    "zverev": "R", "rublev": "R", "de minaur": "R", "minaur": "R", "khachanov": "R"
}

# ━━━━━━━━━━━━━━ 1. LEYES DEL TIEMPO (TRIPLE DECAIMIENTO EXPONENCIAL) ━━━━━━━━━━━━━━
def clean_str(s: str) -> str:
    s_norm = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s_norm if not unicodedata.combining(c)).lower().strip()

def parse_date_metrics(date_str: str) -> Tuple[float, float]:
    """Triple decaimiento temporal: 50% (18d) + 30% (55d) + 20% (240d)."""
    if not date_str or len(str(date_str)) < 4:
        return 0.45, 180.0
    try:
        clean_d = str(date_str).replace("-", "").strip()
        match_dt = (
            datetime.strptime(clean_d[:8], "%Y%m%d").replace(tzinfo=timezone.utc)
            if len(clean_d) >= 8 else datetime(int(clean_d[:4]), 6, 1, tzinfo=timezone.utc)
        )
        days = max(0.0, (datetime.now(timezone.utc) - match_dt).total_seconds() / 86400.0)
        w = 0.50 * math.exp(-days / 18.0) + 0.30 * math.exp(-days / 55.0) + 0.20 * math.exp(-days / 240.0)
        return float(w), days
    except Exception:
        return 0.45, 180.0

def parse_date_weight(date_str: str) -> float:
    w, _ = parse_date_metrics(date_str)
    return w

# ━━━━━━━━━━━━━━ 2. CACHÉ DE IDENTIDADES (RAPIDFUZZ + SQLITE) ━━━━━━━━━━━━━━
PLAYER_INDEX_CACHE: List[str] = []

def fuzzy_canonical_name(raw_name: str) -> str:
    global PLAYER_INDEX_CACHE
    if not HAS_RAPIDFUZZ:
        return raw_name
    if not PLAYER_INDEX_CACHE:
        names = set()
        for db_f in [DB_PATH, "tennis_analytics.db", "omega_39col.db", "tennis_records.db"]:
            if os.path.exists(db_f):
                try:
                    with sqlite3.connect(db_f, timeout=0.5) as conn:
                        cur = conn.cursor()
                        for q in [
                            "SELECT full_name FROM urn_directory",
                            "SELECT DISTINCT canonical_name FROM player_aliases LIMIT 1500",
                            "SELECT DISTINCT winner_name FROM matches LIMIT 1500"
                        ]:
                            try:
                                cur.execute(q)
                                names.update(n for (n,) in cur.fetchall() if n)
                            except Exception:
                                pass
                except Exception:
                    pass
        PLAYER_INDEX_CACHE = list(names)
    if not PLAYER_INDEX_CACHE:
        return raw_name
    best = process.extractOne(raw_name, PLAYER_INDEX_CACHE, scorer=fuzz.token_set_ratio, score_cutoff=80.0)
    return best[0] if best else raw_name

# ━━━━━━━━━━━━━━ 3. PERFIL BIOMÉTRICO ATÓMICO Y MOMENTUM TEMPORAL ━━━━━━━━━━━━━━
class PlayerBioProfile:
    def __init__(self):
        self.raw_pts = 0
        self.raw_bp_faced = 0
        self.surf_pts = 0.0
        self.weight_tot = 0.0
        self.sv_pts = 0.0
        self.sv_1st_in = 0.0
        self.sv_1st_won = 0.0
        self.sv_2nd_won = 0.0
        self.sv_aces = 0.0
        self.sv_dfs = 0.0
        self.sv_bp_saved = 0.0
        self.sv_bp_faced = 0.0
        self.rc_pts = 0.0
        self.rc_won = 0.0
        self.rc_bp_conv = 0.0
        self.rc_bp_opps = 0.0
        self.recent_sv_pts = 0.0
        self.recent_sv_won = 0.0
        self.opponents: Dict[str, List[float]] = {}
        self.h2h_matches = 0
        self.h2h_wins = 0
        self.h2h_weight_wins = 0.0
        self.h2h_weight_tot = 0.0
        self.ace_rate = 0.06
        self.df_rate = 0.04
        self.bp_save_rate = 0.62
        self.bp_conv_rate = 0.41
        self.temporal_momentum = 0.0

def detect_handedness(player_name: str, files: List[str]) -> str:
    clean_p = clean_str(player_name)
    for k, h in KNOWN_HANDEDNESS.items():
        if k in clean_p:
            return h
    tokens = clean_p.split()
    last_name = tokens[-1] if tokens else ""
    first_init = tokens[0][0] if tokens and tokens[0] else ""
    for path in sorted(files, reverse=True):
        try:
            with open(path, mode="r", encoding="utf-8", errors="ignore") as f:
                cols = [c.strip() for c in f.readline().lower().split(",")]
                w_i = cols.index("winner_name") if "winner_name" in cols else -1
                l_i = cols.index("loser_name") if "loser_name" in cols else -1
                wh_i = cols.index("winner_hand") if "winner_hand" in cols else -1
                lh_i = cols.index("loser_hand") if "loser_hand" in cols else -1
                for line in f:
                    if last_name in line.lower():
                        p = line.split(",")
                        if w_i != -1 and wh_i != -1 and len(p) > max(w_i, wh_i):
                            wc = clean_str(p[w_i])
                            if last_name in wc and (not first_init or first_init in wc) and p[wh_i].strip() in ("L", "R"):
                                return p[wh_i].strip()
                        if l_i != -1 and lh_i != -1 and len(p) > max(l_i, lh_i):
                            lc = clean_str(p[l_i])
                            if last_name in lc and (not first_init or first_init in lc) and p[lh_i].strip() in ("L", "R"):
                                return p[lh_i].strip()
        except Exception:
            continue
    return "R"

def scan_atomic_profile(files: List[str], target_player: str, opp_player: str, target_surf: str) -> Optional[PlayerBioProfile]:
    tokens = clean_str(fuzzy_canonical_name(target_player)).split()
    if not tokens:
        return None
    last_name, first_init = tokens[-1], (tokens[0][0] if tokens[0] else "")
    opp_last = clean_str(fuzzy_canonical_name(opp_player)).split()[-1] if opp_player else ""
    prof = PlayerBioProfile()
    surf_filter = target_surf.lower()

    for path in sorted(files):
        try:
            with open(path, mode="r", encoding="utf-8", errors="ignore") as f:
                header = f.readline()
                if not header:
                    continue
                cols = [c.strip().lower() for c in header.split(",")]
                idx = {k: (cols.index(k) if k in cols else -1) for k in [
                    "winner_name", "loser_name", "surface", "tourney_date",
                    "w_svpt", "w_1stin", "w_1stwon", "w_2ndwon", "w_ace", "w_df", "w_bpsaved", "w_bpfaced",
                    "l_svpt", "l_1stin", "l_1stwon", "l_2ndwon", "l_ace", "l_df", "l_bpsaved", "l_bpfaced"
                ]}
                if idx["winner_name"] == -1 or idx["loser_name"] == -1 or idx["w_svpt"] == -1 or idx["l_svpt"] == -1:
                    continue
                for line in f:
                    if last_name not in line.lower():
                        continue
                    p = line.split(",")
                    if len(p) <= max(idx["w_svpt"], idx["l_svpt"]):
                        continue
                    w_c, l_c = clean_str(p[idx["winner_name"]]), clean_str(p[idx["loser_name"]])
                    is_w = last_name in w_c and (not first_init or first_init in w_c)
                    is_l = last_name in l_c and (not first_init or first_init in l_c)
                    if not is_w and not is_l:
                        continue
                    try:
                        ws, ls = float(p[idx["w_svpt"]] or 0), float(p[idx["l_svpt"]] or 0)
                        if ws <= 0 or ls <= 0:
                            continue
                        w1i, w1w, w2w = float(p[idx["w_1stin"]] or 0), float(p[idx["w_1stwon"]] or 0), float(p[idx["w_2ndwon"]] or 0)
                        wac = float(p[idx["w_ace"]] or 0) if idx["w_ace"] != -1 else 0.0
                        wdf = float(p[idx["w_df"]] or 0) if idx["w_df"] != -1 else 0.0
                        wbps, wbpf = float(p[idx["w_bpsaved"]] or 0), float(p[idx["w_bpfaced"]] or 0)
                        l1i, l1w, l2w = float(p[idx["l_1stin"]] or 0), float(p[idx["l_1stwon"]] or 0), float(p[idx["l_2ndwon"]] or 0)
                        lac = float(p[idx["l_ace"]] or 0) if idx["l_ace"] != -1 else 0.0
                        ldf = float(p[idx["l_df"]] or 0) if idx["l_df"] != -1 else 0.0
                        lbps, lbpf = float(p[idx["l_bpsaved"]] or 0), float(p[idx["l_bpfaced"]] or 0)
                    except ValueError:
                        continue

                    t_w, days_ago = parse_date_metrics(p[idx["tourney_date"]] if idx["tourney_date"] != -1 else "")
                    r_surf = p[idx["surface"]].lower() if idx["surface"] != -1 else ""
                    is_surf = (surf_filter in r_surf or not r_surf)
                    surf_w = 1.0 if is_surf else 0.22
                    weight = t_w * surf_w

                    my_s, my_1i, my_1w, my_2w, my_ac, my_df, my_bps, my_bpf = (
                        (ws, w1i, w1w, w2w, wac, wdf, wbps, wbpf) if is_w else (ls, l1i, l1w, l2w, lac, ldf, lbps, lbpf)
                    )
                    op_s, op_1w, op_2w, op_bps, op_bpf, op_c = (
                        (ls, l1w, l2w, lbps, lbpf, l_c) if is_w else (ws, w1w, w2w, wbps, wbpf, w_c)
                    )

                    prof.sv_pts += my_s * weight
                    prof.sv_1st_in += my_1i * weight
                    prof.sv_1st_won += my_1w * weight
                    prof.sv_2nd_won += my_2w * weight
                    prof.sv_aces += my_ac * weight
                    prof.sv_dfs += my_df * weight
                    prof.sv_bp_saved += my_bps * weight
                    prof.sv_bp_faced += my_bpf * weight
                    prof.raw_bp_faced += int(my_bpf)
                    prof.rc_pts += op_s * weight
                    prof.rc_won += (op_s - (op_1w + op_2w)) * weight
                    prof.rc_bp_conv += max(0.0, op_bpf - op_bps) * weight
                    prof.rc_bp_opps += op_bpf * weight
                    prof.raw_pts += int(my_s)

                    if days_ago <= 65.0:
                        prof.recent_sv_pts += my_s * surf_w
                        prof.recent_sv_won += (my_1w + my_2w) * surf_w

                    if is_surf:
                        prof.surf_pts += my_s
                    prof.weight_tot += weight

                    opp_id = op_c.split()[-1] if op_c else "unk"
                    if opp_id not in prof.opponents:
                        prof.opponents[opp_id] = [0.0, 0.0, 0]
                    prof.opponents[opp_id][0] += ((my_1w + my_2w) / my_s) * weight
                    prof.opponents[opp_id][1] += weight
                    prof.opponents[opp_id][2] += int(my_s)
                    if opp_last and opp_last in op_c:
                        prof.h2h_matches += 1
                        prof.h2h_weight_tot += t_w
                        if is_w:
                            prof.h2h_wins += 1
                            prof.h2h_weight_wins += t_w
        except Exception:
            continue
    return prof if (prof.raw_pts >= 40 and prof.sv_pts > 0 and prof.rc_pts > 0) else None

def get_dataset_files(circuit: str) -> Tuple[List[str], List[str]]:
    pfx = "wta" if circuit == "WTA" else "atp"
    home = os.path.expanduser("~")
    dirs = [
        os.path.join(home, "tennis_modern"), "/data/data/com.termux/files/home/tennis_modern",
        f"/tmp/tennis_dataset/tennis_{pfx}", "/tmp/tennis_dataset",
        os.path.join(home, f"tennis_{pfx}"), "tennis_modern", f"tennis_{pfx}", "."
    ]
    main_f, itf_f = [], []
    for d in dirs:
        if os.path.isdir(d):
            for pat in [os.path.join(d, f"{pfx}_matches_202*.csv"), os.path.join(d, f"{pfx}_matches_*.csv")]:
                for f in glob.glob(pat):
                    fl = os.path.basename(f).lower()
                    target = itf_f if any(k in fl for k in ("qual", "itf", "chall", "futures")) else main_f
                    if f not in target:
                        target.append(f)
    return main_f, itf_f

def _resolve_dna_core(player_in: str, opp_in: str, surf: str, circuit: str) -> Tuple[float, float, int, str, str, PlayerBioProfile]:
    mean_spw = 0.5750 if circuit == "WTA" else 0.6400
    mean_rpw = 0.4250 if circuit == "WTA" else 0.3600
    mean_ace = 0.042 if circuit == "WTA" else 0.082
    mean_df = 0.048 if circuit == "WTA" else 0.035
    mean_bp_conv = 0.445 if circuit == "WTA" else 0.400

    main_f, itf_f = get_dataset_files(circuit)
    hand = detect_handedness(player_in, main_f)
    prof = scan_atomic_profile(main_f, player_in, opp_in, surf)
    if prof:
        p_1in = prof.sv_1st_in / prof.sv_pts if prof.sv_pts > 0 else 0.62
        p_1w = prof.sv_1st_won / prof.sv_1st_in if prof.sv_1st_in > 0 else 0.70
        p_2nd = max(1e-6, prof.sv_pts - prof.sv_1st_in)
        p_2w = prof.sv_2nd_won / p_2nd
        spw_at = (p_1in * p_1w) + ((1.0 - p_1in) * p_2w)

        prof.ace_rate = prof.sv_aces / prof.sv_pts if prof.sv_pts > 0 else mean_ace
        prof.df_rate = prof.sv_dfs / prof.sv_pts if prof.sv_pts > 0 else mean_df
        prof.bp_save_rate = prof.sv_bp_saved / prof.sv_bp_faced if prof.sv_bp_faced >= 15 else 0.62
        prof.bp_conv_rate = prof.rc_bp_conv / prof.rc_bp_opps if prof.rc_bp_opps >= 15 else mean_bp_conv

        df_excess = max(0.0, prof.df_rate - mean_df)
        ace_bonus = max(-0.008, min(0.010, (prof.ace_rate - mean_ace) * 0.16))
        spw_at = spw_at + ace_bonus - (df_excess * 0.22)

        if prof.raw_bp_faced >= 20 and prof.bp_save_rate > 0.72:
            spw_at = 0.85 * spw_at + 0.15 * (spw_at * (1.0 - (prof.bp_save_rate - 0.72) * 0.5))

        if prof.recent_sv_pts >= 100:
            rec_spw = prof.recent_sv_won / prof.recent_sv_pts
            prof.temporal_momentum = max(-0.016, min(0.016, (rec_spw - spw_at) * 0.40))
            spw_at += prof.temporal_momentum

        rpw_raw = prof.rc_won / prof.rc_pts if prof.rc_pts > 0 else mean_rpw
        bp_conv_delta = max(-0.010, min(0.010, (prof.bp_conv_rate - mean_bp_conv) * 0.12))
        rpw_raw += bp_conv_delta

        w_s = prof.raw_pts / (prof.raw_pts + 1344.0)
        return (w_s * spw_at + (1.0 - w_s) * mean_spw), (w_s * rpw_raw + (1.0 - w_s) * mean_rpw), prof.raw_pts, f"CSV-MAIN ({prof.raw_pts}p)", hand, prof
    if hand == "R":
        hand = detect_handedness(player_in, itf_f)
    prof_itf = scan_atomic_profile(itf_f, player_in, opp_in, surf)
    if prof_itf:
        spw_adj = ((prof_itf.sv_1st_won + prof_itf.sv_2nd_won) / prof_itf.sv_pts) * (0.94 if circuit == "WTA" else 0.95)
        rpw_adj = (prof_itf.rc_won / prof_itf.rc_pts) * (0.92 if circuit == "WTA" else 0.93)
        w_s = prof_itf.raw_pts / (prof_itf.raw_pts + 1500.0)
        return (w_s * spw_adj + (1.0 - w_s) * mean_spw), (w_s * rpw_adj + (1.0 - w_s) * mean_rpw), prof_itf.raw_pts, f"CSV-ITF ({prof_itf.raw_pts}p)", hand, prof_itf
    return mean_spw, mean_rpw, 0, f"PRIOR-{circuit}", hand, PlayerBioProfile()

def resolve_hierarchical_dna(player_in: str, opp_in: str, surf: str = "Hard", circuit: Optional[str] = None):
    if circuit is None:
        res = _resolve_dna_core(player_in, "", str(opp_in), str(surf).upper())
        return res[:5]
    return _resolve_dna_core(player_in, opp_in, surf, circuit)

def compute_common_opponents_delta(prof_a: PlayerBioProfile, prof_b: PlayerBioProfile) -> float:
    shared = set(prof_a.opponents.keys()).intersection(prof_b.opponents.keys())
    if not shared:
        return 0.0
    d_acc, w_acc = 0.0, 0.0
    for opp in shared:
        sa, wa, pa = prof_a.opponents[opp]
        sb, wb, pb = prof_b.opponents[opp]
        if wa > 0 and wb > 0 and (pa + pb) >= 80:
            w_p = math.sqrt(pa * pb) / 100.0
            d_acc += ((sa / wa) - (sb / wb)) * w_p
            w_acc += w_p
    return max(-0.025, min(0.025, d_acc / w_acc)) if w_acc > 0 else 0.0

def resolve_physics(tourn: str, city_field: Optional[str], court_env: str, session_time: str = "day_heat") -> Dict[str, Any]:
    if court_env.lower() == "indoor" or session_time.lower() == "indoor":
        return {"delta_env": 0.0, "thermal_drift": 0.0, "elev": 0}
    target_city = city_field.strip() if city_field else "New York,US"
    elev = 0
    t_name = clean_str(f"{tourn} {target_city}").upper()
    for c_key, c_alt in CITY_ELEVATION_METERS.items():
        if c_key in t_name or clean_str(c_key) in clean_str(t_name):
            elev = c_alt
            break
    t, w, p_real, hum = 24.0, 0.0, 1013.25 * math.pow(1.0 - (2.25577e-5 * elev), 5.25588), 50.0
    if OWM_KEY:
        try:
            r = requests.get("https://api.openweathermap.org/data/2.5/weather", params={"q": target_city, "appid": OWM_KEY, "units": "metric"}, timeout=1.0)
            if r.status_code == 200:
                d = r.json()
                t, w, hum = float(d["main"]["temp"]), float(d.get("wind", {}).get("speed", 0.0)) * 3.6, float(d["main"].get("humidity", 50.0))
                p_sea = float(d["main"]["pressure"])
                p_real = float(d["main"].get("grnd_level", p_sea * math.pow(1.0 - (2.25577e-5 * elev), 5.25588)))
        except Exception:
            pass
    st = session_time.lower()
    thermal_drift = -0.002
    if "day" in st or "heat" in st:
        t, hum, thermal_drift = max(t, 26.0), min(hum, 48.0), -0.002
    elif "twilight" in st:
        thermal_drift = -0.008
    elif "night" in st or "slow" in st:
        t, hum, thermal_drift = min(t, 19.0), max(hum, 68.0), -0.005
    rho = (p_real * 100.0) / (287.058 * (t + 273.15))
    d_env = round((1.0 - (rho / 1.225)) * 0.08 - ((w / 60.0) * 0.012) + (t - 22.0) * 0.0016 - ((hum - 50.0) / 100.0) * 0.0040, 4)
    return {"delta_env": d_env, "thermal_drift": thermal_drift, "elev": elev}

# ━━━━━━━━━━━━━━ 4. MARKOV INTRA-SET (CICLO DE PELOTAS 7/9) Y TRAYECTORIA 4D ━━━━━━━━━━━━━━
def markov_hold(p: float) -> float:
    p = max(0.01, min(0.99, p))
    q = 1.0 - p
    denom = p**2 + q**2
    return (p**4) * (1.0 + 4.0 * q + 10.0 * (q**2)) + (20.0 * (p**3) * (q**3) * (p**2 / denom) if denom > 0 else 0.0)

def markov_tiebreak(pa: float, pb: float, first_server: int = 0) -> float:
    dp = [[0.0] * 8 for _ in range(8)]
    dp[0][0] = 1.0
    for total in range(12):
        for i in range(min(total + 1, 7)):
            j = total - i
            if j >= 7 or i >= 7 or dp[i][j] <= 0.0:
                continue
            is_first_srv = (total == 0) or (((total + 1) // 2) % 2 == 1)
            srv_a = is_first_srv if first_server == 0 else (not is_first_srv)
            p_pt = pa if srv_a else (1.0 - pb)
            dp[i + 1][j] += dp[i][j] * p_pt
            dp[i][j + 1] += dp[i][j] * (1.0 - p_pt)
    p_a_wins = sum(dp[7][j] for j in range(6))
    denom = (pa * (1.0 - pb)) + ((1.0 - pa) * pb)
    return p_a_wins + dp[6][6] * ((pa * (1.0 - pb)) / denom if denom > 0 else 0.5)

def analytical_set_matrix(pa_srv: float, pb_srv: float, set_num: int = 1) -> Tuple[Dict[Tuple[int, int], float], float]:
    def solve_opener(start_server: int):
        dp = [[[0.0, 0.0] for _ in range(8)] for _ in range(8)]
        dp[0][0][start_server] = 1.0
        final = {}
        for total in range(13):
            ball_mod = 0.008 if total in (0, 1, 7, 8) else (-0.010 if total in (5, 6, 10, 11) else 0.0)
            ga = markov_hold(pa_srv + ball_mod)
            ha = 1.0 - markov_hold(pb_srv + ball_mod)
            for i in range(min(total + 1, 8)):
                j = total - i
                if j >= 8:
                    continue
                for s in (0, 1):
                    prob = dp[i][j][s]
                    if prob <= 0.0:
                        continue
                    if (i == 6 and j <= 4) or (i == 7 and j == 5) or (j == 6 and i <= 4) or (j == 7 and i == 5):
                        final[(i, j)] = final.get((i, j), 0.0) + prob
                        continue
                    if i == 6 and j == 6:
                        tb = markov_tiebreak(pa_srv, pb_srv, first_server=start_server)
                        final[(7, 6)] = final.get((7, 6), 0.0) + prob * tb
                        final[(6, 7)] = final.get((6, 7), 0.0) + prob * (1.0 - tb)
                        continue
                    pw = ga if s == 0 else ha
                    ns = 1 - s
                    if i + 1 <= 7:
                        dp[i + 1][j][ns] += prob * pw
                    if j + 1 <= 7:
                        dp[i][j + 1][ns] += prob * (1.0 - pw)
        return final
    d0, d1 = solve_opener(0), solve_opener(1)
    comb = {k: 0.5 * d0.get(k, 0.0) + 0.5 * d1.get(k, 0.0) for k in set(d0).union(d1)}
    return comb, sum(prob for (i, j), prob in comb.items() if i > j)

def split_set_games_pmf(set_matrix: Dict[Tuple[int, int], float], is_under_bias: bool, is_high_alt_short: bool = False) -> Tuple[np.ndarray, np.ndarray]:
    ga_pmf, gb_pmf = np.zeros(14, dtype=np.float64), np.zeros(14, dtype=np.float64)
    for (ga, gb), pr in set_matrix.items():
        g = ga + gb
        if g < 14:
            if is_high_alt_short:
                w = 1.24 if g >= 12 else (0.85 if g <= 8 else 1.0)
            elif is_under_bias:
                w = 0.58 if g >= 12 else (1.36 if g in (7, 8, 9, 10) else 1.0)
            else:
                w = 1.0
            if ga > gb:
                ga_pmf[g] += pr * w
            else:
                gb_pmf[g] += pr * w
    if np.sum(ga_pmf) > 0:
        ga_pmf /= np.sum(ga_pmf)
    if np.sum(gb_pmf) > 0:
        gb_pmf /= np.sum(gb_pmf)
    return ga_pmf, gb_pmf

def parse_odds(val: Any) -> Optional[float]:
    if val is None or str(val).strip().lower() in ("", "null", "none"):
        return None
    try:
        s = str(val).strip()
        f = float(s)
        if s.startswith("+") or f >= 100:
            return round(1.0 + (f / 100.0), 4)
        if s.startswith("-") or f <= -100:
            return round(1.0 + (100.0 / abs(f)), 4)
        return round(f, 4)
    except Exception:
        return None

def parse_spread(val: Any) -> Optional[float]:
    try:
        return float(str(val).strip().replace("+", "")) if val is not None else None
    except Exception:
        return None

def shin_solve_2way(odd1: float, odd2: float) -> Tuple[float, float, float]:
    if not odd1 or not odd2 or odd1 <= 1.0 or odd2 <= 1.0:
        return 0.5, 0.5, 0.0
    p1, p2 = 1.0 / odd1, 1.0 / odd2
    S = p1 + p2
    if abs(S - 1.0) < 1e-9:
        return p1 / S, p2 / S, 0.0
    low, high = 0.0, max(0.0, S - 1.0)
    for _ in range(35):
        mid = (low + high) / 2.0
        t1 = math.sqrt(mid**2 + 4.0 * (1.0 - mid) * (p1**2) / S)
        t2 = math.sqrt(mid**2 + 4.0 * (1.0 - mid) * (p2**2) / S)
        if (t1 + t2) - 2.0 > 0:
            low = mid
        else:
            high = mid
    z = (low + high) / 2.0
    denom = 2.0 * (1.0 - z)
    pf1 = (math.sqrt(z**2 + 4.0 * (1.0 - z) * (p1**2) / S) - z) / denom
    pf2 = (math.sqrt(z**2 + 4.0 * (1.0 - z) * (p2**2) / S) - z) / denom
    tot = pf1 + pf2
    return pf1 / tot, pf2 / tot, z

def prob_to_american(p: float) -> str:
    if p <= 0.001:
        return "+99900"
    if p >= 0.999:
        return "-99900"
    return f"-{int(round((p / (1.0 - p)) * 100.0))}" if p >= 0.50 else f"+{int(round(((1.0 - p) / p) * 100.0))}"

def prob_to_decimal(p: float) -> str:
    return f"{1.0 / max(0.001, min(0.999, p)):.2f}"

def sum_below(dist: np.ndarray, thresh: float) -> float:
    return float(np.sum(dist[np.arange(len(dist)) < thresh]))

def sum_above(dist: np.ndarray, thresh: float) -> float:
    return float(np.sum(dist[np.arange(len(dist)) > thresh]))

def eval_4d_trajectory(bar_p: float, delta_d: float, decay_a: float, decay_b: float, drift: float, best_of: int):
    pa1 = max(0.35, min(0.82, bar_p + delta_d - 0.25 * decay_a))
    pb1 = max(0.35, min(0.82, bar_p - delta_d - 0.25 * decay_b))
    pa2 = max(0.35, min(0.82, pa1 - decay_a + 0.5 * drift))
    pb2 = max(0.35, min(0.82, pb1 - decay_b + 0.5 * drift))
    pa3 = max(0.35, min(0.82, pa2 - 1.35 * decay_a + 0.5 * drift))
    pb3 = max(0.35, min(0.82, pb2 - 1.35 * decay_b + 0.5 * drift))

    m1, ps1 = analytical_set_matrix(pa1, pb1, 1)
    m2, ps2 = analytical_set_matrix(pa2, pb2, 2)
    m3, ps3 = analytical_set_matrix(pa3, pb3, 3)

    if best_of == 3:
        p20a = ps1 * ps2
        p21a = ps1 * (1.0 - ps2) * ps3 + (1.0 - ps1) * ps2 * ps3
        p20b = (1.0 - ps1) * (1.0 - ps2)
        p21b = (1.0 - ps1) * ps2 * (1.0 - ps3) + ps1 * (1.0 - ps2) * (1.0 - ps3)
        m_win_a = p20a + p21a
    else:
        pm = (ps1 + ps2 + ps3) / 3.0
        m_win_a = 10.0 * (pm**3) - 15.0 * (pm**4) + 6.0 * (pm**5)
        p20a = p21a = p20b = p21b = 0.0
    return m_win_a, (pa1, pb1, pa2, pb2, pa3, pb3), (m1, m2, m3), (ps1, ps2, ps3), (p20a, p21a, p20b, p21b)

# ━━━━━━━━━━━━━━ 5. PIPELINE MAESTRO (ACLIMATACIÓN + ALTITUD + ORÁCULO 4D) ━━━━━━━━━━━━━━
def run_prediction_pipeline(payload: Dict[str, Any]):
    t0 = time.perf_counter_ns()
    ev = payload.get("event", {})
    market = payload.get("market_lines", {})
    pinn, soft = market.get("pinnacle", {}), market.get("soft", {})
    bankroll = float(payload.get("bankroll", 150.0))

    p1_name, p2_name = ev.get("player_1", "Jugador 1"), ev.get("player_2", "Jugador 2")
    circuit = "WTA" if "WTA" in str(ev.get("tour", "ATP")).upper() else "ATP"
    tourn, city_f = ev.get("tournament", "Torneo"), ev.get("city")
    env, session_time = str(ev.get("court_env", "outdoor")).lower(), str(ev.get("session_time", "day_heat")).lower()
    surf, best_of = ev.get("surface", "Hard"), int(ev.get("best_of", 3))
    s1, s2 = p1_name.strip().split()[-1][:10], p2_name.strip().split()[-1][:10]

    physics = resolve_physics(tourn, city_f, env, session_time)
    d_env, drift, elev = physics["delta_env"], physics["thermal_drift"], physics["elev"]

    spw_a, rpw_a, pts_a, _, hand_a, prof_a = _resolve_dna_core(p1_name, p2_name, surf, circuit)
    spw_b, rpw_b, pts_b, _, hand_b, prof_b = _resolve_dna_core(p2_name, p1_name, surf, circuit)
    knotten = compute_common_opponents_delta(prof_a, prof_b)

    mean_spw = 0.5750 if circuit == "WTA" else 0.6400
    mean_rpw = 0.4250 if circuit == "WTA" else 0.3600
    ace_ref = 0.042 if circuit == "WTA" else 0.082
    ace_f_a = max(0.85, min(1.30, prof_a.ace_rate / ace_ref))
    ace_f_b = max(0.85, min(1.30, prof_b.ace_rate / ace_ref))
    boost_a = d_env * math.pow(spw_a / mean_spw, 1.1) * ace_f_a
    boost_b = d_env * math.pow(spw_b / mean_spw, 1.1) * ace_f_b

    # Ventaja de zurdo ('L') amplificada en altitud elevada (>1000m)
    lefty_bonus = (0.011 if elev >= 1000 else 0.008) if "hard" in surf.lower() else 0.012
    tac_a = lefty_bonus if (hand_a == "L" and hand_b == "R") else (-0.005 if (hand_b == "L" and hand_a == "R") else 0.0)
    tac_b = lefty_bonus if (hand_b == "L" and hand_a == "R") else (-0.005 if (hand_a == "L" and hand_b == "R") else 0.0)

    t_scout = ev.get("tactical_matchup", {})
    p1_st, p2_st = str(t_scout.get("p1_style", "")).lower(), str(t_scout.get("p2_style", "")).lower()
    exp_shape, tac_bias = str(t_scout.get("expected_shape", "symmetric")).lower(), str(t_scout.get("bias", "neutral")).lower()

    is_style_clash_a = ("counterpuncher" in p1_st or "defense" in p1_st) and ("aggressive" in p2_st or "server" in p2_st)
    is_style_clash_b = ("counterpuncher" in p2_st or "defense" in p2_st) and ("aggressive" in p1_st or "server" in p1_st)

    if is_style_clash_a:
        tac_a += 0.006; tac_b -= 0.005
    elif is_style_clash_b:
        tac_b += 0.006; tac_a -= 0.005

    if any(k in p1_st for k in ("erratic", "volatile", "double_fault", "fragile")):
        tac_a -= 0.012
    if any(k in p2_st for k in ("erratic", "volatile", "double_fault", "fragile")):
        tac_b -= 0.012

    tc = ev.get("temporal_coordinates", {})
    p1_m72, p2_m72 = float(tc.get("p1_mins_72h", 0.0)), float(tc.get("p2_mins_72h", 0.0))
    p1_rest, p2_rest = float(tc.get("p1_rest_hours", 36.0)), float(tc.get("p2_rest_hours", 36.0))
    p1_f14 = max(-1.0, min(1.0, float(tc.get("p1_form_14d", 0.0))))
    p2_f14 = max(-1.0, min(1.0, float(tc.get("p2_form_14d", 0.0))))
    r_prof = str(tc.get("avg_rally_profile", "medium")).lower()
    r_mult = 1.35 if "long" in r_prof else (0.75 if "short" in r_prof else 1.0)

    # Ley de Fatiga vs Recuperación Completa (>=36h de descanso absorbe carga normal <=135m)
    def calc_decay(m72: float, rest: float, st: str) -> float:
        eff_mins = max(0.0, m72 - (135.0 if rest >= 36.0 else 80.0))
        load = (eff_mins / 150.0) * 0.014
        r_pen = max(0.0, (26.0 - rest) / 10.0) * 0.009 if rest < 26.0 else 0.0
        s_burn = 0.0045 if any(k in st for k in ("server", "aggressive", "erratic", "fragile")) else 0.0015
        if rest >= 40.0 and m72 <= 135.0:
            s_burn *= 0.50
        return (load + r_pen + s_burn) * r_mult

    decay_a, decay_b = calc_decay(p1_m72, p1_rest, p1_st), calc_decay(p2_m72, p2_rest, p2_st)

    # Ley de Aclimatación en Altura (>1000m): Ritmo de cancha (45-150m con buen descanso) vs Debut en Frío (0m)
    acclim_a, acclim_b = 0.0, 0.0
    cold_alt_debut = False
    if elev >= 1000:
        if 45.0 <= p1_m72 <= 155.0 and p1_rest >= 30.0 and p2_m72 == 0.0:
            acclim_a += 0.012
            acclim_b -= 0.010
            cold_alt_debut = True
        elif 45.0 <= p2_m72 <= 155.0 and p2_rest >= 30.0 and p1_m72 == 0.0:
            acclim_b += 0.012
            acclim_a -= 0.010
            cold_alt_debut = True

    fatigue_edge_a = (decay_b - decay_a) * 1.40
    form_edge_a = (p1_f14 - p2_f14) * 0.035

    h2h_a = 0.0
    if prof_a.h2h_weight_tot > 0:
        h2h_a = ((prof_a.h2h_weight_wins / prof_a.h2h_weight_tot) - 0.50) * min(0.022, 0.007 * prof_a.h2h_matches)

    pa_base = spw_a - (rpw_b - mean_rpw) + boost_a + tac_a + knotten + h2h_a + acclim_a + (form_edge_a / 2.0) + (fatigue_edge_a / 2.0)
    pb_base = spw_b - (rpw_a - mean_rpw) + boost_b + tac_b - knotten - h2h_a + acclim_b - (form_edge_a / 2.0) - (fatigue_edge_a / 2.0)
    lo_b, hi_b = (0.420, 0.680) if circuit == "WTA" else (0.460, 0.760)
    pa_base, pb_base = min(hi_b, max(lo_b, pa_base)), min(hi_b, max(lo_b, pb_base))

    # ━━━━━━━━━━━━━━ AUDITORÍA FORENSE DE SEÑALES DE MERCADO Y ALTITUD ━━━━━━━━━━━━━━
    pin_p1 = parse_odds(pinn.get("moneyline", {}).get("p1"))
    pin_p2 = parse_odds(pinn.get("moneyline", {}).get("p2"))
    tot_line = parse_spread(pinn.get("games_total", {}).get("line")) or parse_spread(soft.get("games_total", {}).get("line")) or (38.5 if best_of == 5 else 22.5)

    soft_p1 = parse_odds(soft.get("moneyline", {}).get("p1"))
    soft_p2 = parse_odds(soft.get("moneyline", {}).get("p2"))
    soft_ov = parse_odds(soft.get("games_total", {}).get("over"))
    soft_un = parse_odds(soft.get("games_total", {}).get("under"))
    soft_sb = soft.get("set_betting", {})
    soft_cb = soft.get("combos", {})

    odd_20 = parse_odds(soft_sb.get("2_0"))
    odd_21 = parse_odds(soft_sb.get("2_1"))
    odd_02 = parse_odds(soft_sb.get("0_2"))
    odd_12 = parse_odds(soft_sb.get("1_2"))
    odd_p1_ov = parse_odds(soft_cb.get("p1_over"))
    odd_p1_un = parse_odds(soft_cb.get("p1_under"))
    odd_p2_ov = parse_odds(soft_cb.get("p2_over"))
    odd_p2_un = parse_odds(soft_cb.get("p2_under"))

    # En Altitud (>=1000m) con Rally Corto ("short") o Debut en Frío de la favorita, el saque domina y hay alto riesgo de Tiebreak/3er Set
    is_high_alt_short = (elev >= 1000 and ("short" in r_prof or cold_alt_debut))

    mkt_under_signals = 0
    if not is_high_alt_short:
        if soft_un and soft_ov and soft_un < soft_ov:
            mkt_under_signals += 1
        if odd_p1_un and odd_p1_ov and odd_p1_un < odd_p1_ov:
            mkt_under_signals += 1
        if odd_20 and odd_21 and (odd_21 - odd_20) >= 0.85:
            mkt_under_signals += 1
        if (is_style_clash_a or is_style_clash_b) and "long" in r_prof and abs(p1_m72 - p2_m72) >= 20 and min(p1_rest, p2_rest) < 30.0:
            mkt_under_signals += 2

    auto_under_override = (mkt_under_signals >= 2 and not is_high_alt_short)
    is_under_bias = (("under" in tac_bias or "asymmetric" in exp_shape or auto_under_override) and not is_high_alt_short)

    bar_p = (pa_base + pb_base) / 2.0
    if is_high_alt_short:
        bar_p = min(0.73, bar_p + (0.016 if circuit == "WTA" else 0.014))
    elif is_under_bias:
        bar_p = max(0.48, bar_p - (0.018 if circuit == "WTA" else 0.024))
    elif "over" in tac_bias and not auto_under_override:
        bar_p = min(0.71, bar_p + 0.010)

    raw_delta = (pa_base - pb_base) / 2.0
    p_match_raw, _, _, _, _ = eval_4d_trajectory(bar_p, raw_delta, decay_a, decay_b, drift, best_of)

    if pin_p1 and pin_p2:
        p_shin_a, _, _ = shin_solve_2way(pin_p1, pin_p2)
        min_pts = min(pts_a, pts_b)
        w_micro = min(0.45, 0.16 + 0.29 * (min_pts / 6000.0)) if min_pts > 0 else 0.20
        if abs(decay_a - decay_b) >= 0.004 or abs(p1_f14 - p2_f14) >= 0.08 or is_style_clash_a or is_style_clash_b or cold_alt_debut:
            w_micro = max(w_micro, 0.48)

        p_target_a = (1.0 - w_micro) * p_shin_a + w_micro * p_match_raw
        low_d, high_d = -0.25, 0.25
        for _ in range(28):
            mid_d = (low_d + high_d) / 2.0
            m_ev, _, _, _, _ = eval_4d_trajectory(bar_p, mid_d, decay_a, decay_b, drift, best_of)
            if m_ev < p_target_a:
                low_d = mid_d
            else:
                high_d = mid_d
        final_delta = (low_d + high_d) / 2.0
    else:
        final_delta = raw_delta

    match_win_a, srv_tuple, mats, p_sets, raw_2x = eval_4d_trajectory(bar_p, final_delta, decay_a, decay_b, drift, best_of)
    match_win_b = 1.0 - match_win_a
    pa_s1, pb_s1, pa_s2, pb_s2, pa_s3, pb_s3 = srv_tuple
    mat_s1, mat_s2, mat_s3 = mats
    p_set1_a, p_set2_a, p_set3_a = p_sets
    p_set1_b, p_set2_b, p_set3_b = 1.0 - p_set1_a, 1.0 - p_set2_a, 1.0 - p_set3_a
    p_2_0_a_raw, p_2_1_a_raw, p_2_0_b_raw, p_2_1_b_raw = raw_2x

    hold_a = markov_hold((pa_s1 + pa_s2) / 2.0) * 100.0
    hold_b = markov_hold((pb_s1 + pb_s2) / 2.0) * 100.0
    fav_prob = max(match_win_a, match_win_b)
    if fav_prob >= 0.72 and not is_high_alt_short:
        is_under_bias = True

    s1_ga, s1_gb = split_set_games_pmf(mat_s1, is_under_bias, is_high_alt_short)
    s2_ga, s2_gb = split_set_games_pmf(mat_s2, is_under_bias, is_high_alt_short)
    s3_ga, s3_gb = split_set_games_pmf(mat_s3, is_under_bias, is_high_alt_short)

    top_s1_label, top_s1_prob = "6-4", 0.0
    for (i, j), prob in mat_s1.items():
        g = i + j
        if is_high_alt_short:
            w_s1 = 1.25 if g >= 12 else (0.85 if g <= 8 else 1.0)
        elif is_under_bias:
            w_s1 = 0.58 if g >= 12 else (1.36 if g in (7, 8, 9, 10) else 1.0)
        else:
            w_s1 = 1.0
        p_eff = prob * w_s1
        if p_eff > top_s1_prob:
            top_s1_prob = p_eff
            top_s1_label = f"{max(i, j)}-{min(i, j)} {s1 if i > j else s2}"

    if best_of == 5:
        psa = (p_set1_a + p_set2_a + p_set3_a) / 3.0
        psb = 1.0 - psa
        p30a, p31a, p32a = psa**3, 3.0 * (psa**3) * psb, 6.0 * (psa**3) * (psb**2)
        p30b, p31b, p32b = psb**3, 3.0 * (psb**3) * psa, 6.0 * (psb**3) * (psa**2)
        tb5 = p30a + p31a + p32a + p30b + p31b + p32b
        p30a, p31a, p32a, p30b, p31b, p32b = p30a/tb5, p31a/tb5, p32a/tb5, p30b/tb5, p31b/tb5, p32b/tb5
        score_sets = [(f"{s1} 3-0", p30a), (f"{s1} 3-1", p31a), (f"{s1} 3-2", p32a), (f"{s2} 3-0", p30b), (f"{s2} 3-1", p31b), (f"{s2} 3-2", p32b)]
        c30a = np.convolve(np.convolve(s1_ga, s2_ga), s3_ga)
        c31a, c32a = np.convolve(c30a, s2_gb), np.convolve(np.convolve(c30a, s2_gb), s3_gb)
        c30b = np.convolve(np.convolve(s1_gb, s2_gb), s3_gb)
        c31b, c32b = np.convolve(c30b, s2_ga), np.convolve(np.convolve(c30b, s2_ga), s3_ga)
        tot_pdf = np.zeros(len(c32a), dtype=np.float64)
        for c_arr, pr in [(c30a, p30a), (c31a, p31a), (c32a, p32a), (c30b, p30b), (c31b, p31b), (c32b, p32b)]:
            tot_pdf[:len(c_arr)] += pr * c_arr
        p_3rd = p32a + p32b
        p_ov_a = p30a * sum_above(c30a, tot_line) + p31a * sum_above(c31a, tot_line) + p32a * sum_above(c32a, tot_line)
        p_un_a = p30a * sum_below(c30a, tot_line) + p31a * sum_below(c31a, tot_line) + p32a * sum_below(c32a, tot_line)
        p_ov_b = p30b * sum_above(c30b, tot_line) + p31b * sum_above(c31b, tot_line) + p32b * sum_above(c32b, tot_line)
        p_un_b = p30b * sum_below(c30b, tot_line) + p31b * sum_below(c31b, tot_line) + p32b * sum_below(c32b, tot_line)
    else:
        # En Altitud + Debut en Frío / Rally Corto, aumenta la volatilidad de 3er set (k_str negativo)
        k_str = -0.15 if is_high_alt_short else (0.28 if is_under_bias else 0.06)
        p_2_1_a = min(match_win_a * 0.65, p_2_1_a_raw * (1.0 - k_str))
        p_2_0_a = max(0.0, match_win_a - p_2_1_a)
        p_2_1_b = min(match_win_b * 0.65, p_2_1_b_raw * (1.0 - k_str))
        p_2_0_b = max(0.0, match_win_b - p_2_1_b)
        score_sets = [(f"{s1} 2-0", p_2_0_a), (f"{s1} 2-1", p_2_1_a), (f"{s2} 2-0", p_2_0_b), (f"{s2} 2-1", p_2_1_b)]
        c_20_a = np.convolve(s1_ga, s2_ga)
        c_21_a = 0.5 * np.convolve(np.convolve(s1_ga, s2_gb), s3_ga) + 0.5 * np.convolve(np.convolve(s1_gb, s2_ga), s3_ga)
        c_20_b = np.convolve(s1_gb, s2_gb)
        c_21_b = 0.5 * np.convolve(np.convolve(s1_gb, s2_ga), s3_gb) + 0.5 * np.convolve(np.convolve(s1_ga, s2_gb), s3_gb)
        tot_pdf = np.zeros(len(c_21_a), dtype=np.float64)
        for c_arr, pr in [(c_20_a, p_2_0_a), (c_21_a, p_2_1_a), (c_20_b, p_2_0_b), (c_21_b, p_2_1_b)]:
            tot_pdf[:len(c_arr)] += pr * c_arr
        p_3rd = p_2_1_a + p_2_1_b
        p_ov_a = p_2_0_a * sum_above(c_20_a, tot_line) + p_2_1_a * sum_above(c_21_a, tot_line)
        p_un_a = p_2_0_a * sum_below(c_20_a, tot_line) + p_2_1_a * sum_below(c_21_a, tot_line)
        p_ov_b = p_2_0_b * sum_above(c_20_b, tot_line) + p_2_1_b * sum_above(c_21_b, tot_line)
        p_un_b = p_2_0_b * sum_below(c_20_b, tot_line) + p_2_1_b * sum_below(c_21_b, tot_line)

    score_sets.sort(key=lambda x: x[1], reverse=True)
    if np.sum(tot_pdf) > 0:
        tot_pdf /= np.sum(tot_pdf)

    exp_total_games = float(np.sum(np.arange(len(tot_pdf)) * tot_pdf))
    fav_is_a = match_win_a >= match_win_b
    fav_name, dog_name = (s1, s2) if fav_is_a else (s2, s1)
    fav_s1_prob = p_set1_a if fav_is_a else p_set1_b
    drop_a, drop_b = (p_set3_a - p_set1_a) * 100.0, (p_set3_b - p_set1_b) * 100.0

    po_main, pu_main = sum_above(tot_pdf, tot_line), sum_below(tot_pdf, tot_line)
    st_m = po_main + pu_main
    if st_m > 0:
        po_main /= st_m; pu_main /= st_m
    tot_dir_lbl = f"UNDER {tot_line:.1f}g" if pu_main >= po_main else f"OVER {tot_line:.1f}g"
    tot_dir_prob = max(pu_main, po_main)

    combos = [(f"{s1} + Over", p_ov_a), (f"{s1} + Under", p_un_a), (f"{s2} + Over", p_ov_b), (f"{s2} + Under", p_un_b)]
    combos.sort(key=lambda x: x[1], reverse=True)
    fav_scores = [(lbl, pr) for lbl, pr in score_sets if fav_name in lbl]
    top_set_lbl, top_set_prob = fav_scores[0] if fav_scores else score_sets[0]

    # ━━━━━━━━━━━━━━ SALIDA UNIFICADA ORÁCULO 4D (CERO RUIDO) ━━━━━━━━━━━━━━
    print(f"\n{C_CYN}{SEP}{C_RST}")
    print(pad_line(f" {C_CYN}{C_BLD}OMEGA v32 ARGON-APEX{C_RST} | {C_YLW}ORÁCULO 4D{C_RST}"))
    print(f"{C_CYN}{DIV}{C_RST}")
    print(pad_line(f" {C_BLD}{p1_name}{C_RST} vs {C_BLD}{p2_name}{C_RST}"))
    print(pad_line(f" {circuit} {tourn[:14]} | {surf} | {elev}m"))
    print(f"{DIV}")
    print(pad_line(f"{C_YLW}[1] CURVATURA TEMPORAL (SET 1 -> SET 3){C_RST}"))
    print(pad_line(f" • {s1:<10}: S1 {p_set1_a*100:4.1f}% -> S3 {p_set3_a*100:4.1f}% | Hold {hold_a:4.1f}%"))
    print(pad_line(f" • {s2:<10}: S1 {p_set1_b*100:4.1f}% -> S3 {p_set3_b*100:4.1f}% | Hold {hold_b:4.1f}%"))
    print(f"{DIV}")
    print(pad_line(f"{C_GRN}[2] LO QUE VA A PASAR (DICTAMEN 4D){C_RST}"))
    print(pad_line(f" ▶ GANADOR    : {C_BLD}{fav_name} GANA{C_RST} ({fav_prob*100:4.1f}%)"))
    print(pad_line(f" ▶ MARCADOR   : {C_BLD}{top_set_lbl}{C_RST} ({top_set_prob*100:4.1f}%) | S1: {top_s1_label}"))
    print(pad_line(f" ▶ TOTAL PROY : {C_BLD}{exp_total_games:4.1f} juegos{C_RST} (3er Set: {p_3rd*100:4.1f}%)"))
    print(pad_line(f" ▶ TENDENCIA  : {C_BLD}{tot_dir_lbl}{C_RST} ({tot_dir_prob*100:4.1f}%)"))
    if cold_alt_debut:
        cold_p = s2 if p2_m72 == 0 else s1
        acc_p = s1 if p2_m72 == 0 else s2
        print(pad_line(f" {C_YLW}⚠ ALERTA {elev}m: {acc_p} aclimatado vs {cold_p} debut (Riesgo TB/Over){C_RST}"))
    elif min(drop_a, drop_b) <= -2.5:
        tired_p = s1 if drop_a < drop_b else s2
        print(pad_line(f" {C_RED}⚠ FATIGA 72H : {tired_p} cae {min(drop_a, drop_b):.1f}% hacia el Set 3{C_RST}"))
    print(f"{DIV}")

    master_candidates = [(f"{fav_name} ML", fav_prob), (tot_dir_lbl, tot_dir_prob), (top_set_lbl, top_set_prob)]
    if (drop_a if fav_is_a else drop_b) <= -3.5 and fav_s1_prob > fav_prob:
        master_candidates.append((f"{fav_name} GANA SET 1", fav_s1_prob))
    master_candidates.sort(key=lambda x: x[1], reverse=True)
    master_lbl, master_prob = master_candidates[0]

    fav_combos = [(lbl, pr) for lbl, pr in combos if fav_name in lbl]
    best_fav_combo = fav_combos[0][0] if fav_combos else combos[0][0]

    print(pad_line(f"{C_CYN}[3] ORDEN DE EJECUCIÓN (SIN RUIDO){C_RST}"))
    print(pad_line(f" 🎯 JUGADA REINA: {C_GRN}{C_BLD}{master_lbl}{C_RST} ({master_prob*100:4.1f}%)"))
    print(pad_line(f"    Cuota Justa : {prob_to_decimal(master_prob)} | Combo: {best_fav_combo}"))

    prob_map = {lbl.strip(): p for lbl, p in score_sets}
    combo_map = {lbl.strip(): p for lbl, p in combos}
    eval_markets = [
        (f"{s1} ML", match_win_a, soft_p1, pin_p1),
        (f"{s2} ML", match_win_b, soft_p2, pin_p2),
        (f"OVER {tot_line:.1f}g", po_main, soft_ov, None),
        (f"UNDER {tot_line:.1f}g", pu_main, soft_un, None),
        (f"{s1} 2-0", prob_map.get(f"{s1} 2-0", 0.0), odd_20, None),
        (f"{s1} 2-1", prob_map.get(f"{s1} 2-1", 0.0), odd_21, None),
        (f"{s2} 2-0", prob_map.get(f"{s2} 2-0", 0.0), odd_02, None),
        (f"{s2} 2-1", prob_map.get(f"{s2} 2-1", 0.0), odd_12, None),
        (f"{s1} + Over", combo_map.get(f"{s1} + Over", 0.0), odd_p1_ov, None),
        (f"{s1} + Under", combo_map.get(f"{s1} + Under", 0.0), odd_p1_un, None),
        (f"{s2} + Over", combo_map.get(f"{s2} + Over", 0.0), odd_p2_ov, None),
        (f"{s2} + Under", combo_map.get(f"{s2} + Under", 0.0), odd_p2_un, None),
    ]

    valid_kelly = []
    for m_tag, m_prob, s_odd, p_sharp_odd in eval_markets:
        if not s_odd or s_odd <= 1.05 or s_odd > 4.50 or m_prob < 0.36:
            continue
        # Candado Sharp Institucional: Nunca apostar Moneyline en casa Soft si paga peor que Pinnacle
        if p_sharp_odd and s_odd < (p_sharp_odd - 0.02):
            continue
        if dog_name in m_tag and fav_prob >= 0.54:
            continue
        if "OVER" in m_tag.upper() and pu_main > po_main:
            continue
        if "UNDER" in m_tag.upper() and po_main > pu_main:
            continue
        edge = (m_prob * s_odd) - 1.0
        if edge > 0.03:
            b = s_odd - 1.0
            stake_pct = min(0.04, 0.25 * max(0.0, (b * m_prob - (1.0 - m_prob)) / b))
            stake_val = stake_pct * bankroll
            if stake_val >= 1.50:
                valid_kelly.append((m_tag, m_prob, s_odd, edge, stake_val, stake_pct))

    valid_kelly.sort(key=lambda x: x[1] * (1.0 + x[3]), reverse=True)
    if valid_kelly:
        print(f"{SUB}")
        for m_tag, m_prob, s_odd, edge, stake_val, stake_pct in valid_kelly[:2]:
            print(pad_line(f" {C_GRN}▶ DISPARO KELLY: {m_tag:<13} @ {s_odd:.2f}{C_RST}"))
            print(pad_line(f"   Edge: +{edge*100:.1f}% | Stake: ${stake_val:.2f} ({stake_pct*100:.1f}%)"))

    calc_ms = (time.perf_counter_ns() - t0) / 1_000_000.0
    print(f"{DIV}")
    print(pad_line(f"{C_DIM}Argon-Apex 4D | Ciclo Bolas | {calc_ms:4.1f} ms{C_RST}"))
    print(f"{C_CYN}{SEP}{C_RST}\n")
    sys.stdout.flush()

if __name__ == "__main__":
    raw_in = ""
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            raw_in = f.read().strip()
    elif not sys.stdin.isatty():
        raw_in = sys.stdin.read().strip()
    if not raw_in:
        sys.stderr.write("Error: Buffer de entrada vacío.\n")
        sys.exit(1)
    try:
        run_prediction_pipeline(json.loads(raw_in))
    except Exception as ex:
        sys.stderr.write(f"Error procesando telemetría: {ex}\n")
        sys.exit(1)
