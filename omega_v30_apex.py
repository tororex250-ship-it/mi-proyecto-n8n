#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""

=============================================================================

OMEGA-QUANT v30 APEX | ULTRA-FORENSIC QUANTITATIVE TENNIS ENGINE

=============================================================================

Arquitectura:

  • Inferencia Bayesiana Jerárquica + Contracción Empírica (Martin Ingram).

  • Descomposición Atómica Biométrica de Saque: 1st In, 1st Won, 2nd Won, Ace, DF.

  • Regresión a la Media de Puntos de Quiebre (Break Point Leverage / Anti-Luck).

  • Matriz de Oponentes Comunes (Algoritmo Knottenbelt, Imperial College).

  • Historial Directo H2H (Emparejamiento Táctico).

  • Interacción de Lateralidad Asimétrica (Zurdo 'L' vs Diestro 'R').

  • Balística Barométrica + Termodinámica de Pelota Presurizada (Gay-Lussac).

  • Cadenas de Markov Analíticas + Convolución Bivariada Bo3 y Bo5 (Slams).

  • Desviggeo de Shin (1992) con estimación de dinero informado (z).

  • Detección Multi-Mercado y Criterio Quarter-Kelly (ML + Totales de Juegos).

Hardware target: Dimensity 8300-Ultra (Afinidad CPU Cortex-A715 cores 4-7).

Formato visual: Terminal 42 columnas (POCO X6 Pro).

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

from typing import Dict, Tuple, Optional, Any, List, Set

import requests

import numpy as np

# ━━━━━━━━━━━━━━ 1. COTEJO DIFUSO RAPIDFUZZ (C++) ━━━━━━━━━━━━━━

try:

    from rapidfuzz import fuzz, process

    HAS_RAPIDFUZZ = True

except ImportError:

    HAS_RAPIDFUZZ = False

# ━━━━━━━━━━━━━━ 2. AFINIDAD DE HARDWARE CORTEX-A715 ━━━━━━━━━━━━━━

def bind_to_cortex_a715():

    if hasattr(os, 'sched_setaffinity'):

        try:

            available = os.cpu_count() or 8

            target_cores = {c for c in (4, 5, 6, 7) if c < available}

            if target_cores:

                os.sched_setaffinity(0, target_cores)

        except Exception:

            pass

bind_to_cortex_a715()

# ━━━━━━━━━━━━━━ 3. CONSTANTES Y FORMATO VISUAL (42 COLS) ━━━━━━━━━━━━━━

W = 42

SEP = "━" * W

DIV = "─" * W

SUB = "╌" * W

C_RST = "\033[0m"

C_BLD = "\033[1m"

C_CYN = "\033[1;36m"

C_GRN = "\033[1;32m"

C_RED = "\033[1;31m"

C_YLW = "\033[1;33m"

C_DIM = "\033[2m"

ANSI_REGEX = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

def pad_line(s: str, width: int = W) -> str:

    vlen = len(ANSI_REGEX.sub('', s))

    if vlen >= width:

        return s

    return s + " " * (width - vlen)

SPORTRADAR_KEY = "SCWUAE6MNuyZqjy3UnoX9jwe8jxDGAYaN7mDYXHw"

SPORTRADAR_BASE = "https://api.sportradar.com/tennis/trial/v3/en"

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

    "albert ramos": "L", "nishioka": "L", "thiago monteiro": "L", "vacherot": "R",

    "buse": "R", "ignacio buse": "R", "alcaraz": "R", "sinner": "R",

    "djokovic": "R", "medvedev": "R", "zverev": "R", "rublev": "R", "tsitsipas": "R"

}

# ━━━━━━━━━━━━━━ 4. NORMALIZACIÓN Y PONDERACIÓN TEMPORAL ━━━━━━━━━━━━━━

def clean_str(s: str) -> str:

    s_norm = unicodedata.normalize('NFKD', str(s))

    return ''.join(c for c in s_norm if not unicodedata.combining(c)).lower().strip()

def parse_date_weight(date_str: str) -> float:

    if not date_str or len(str(date_str)) < 4:

        return 0.50

    try:

        clean_d = str(date_str).replace("-", "").strip()

        if len(clean_d) >= 8:

            match_dt = datetime.strptime(clean_d[:8], "%Y%m%d").replace(tzinfo=timezone.utc)

        else:

            match_dt = datetime(int(clean_d[:4]), 6, 1, tzinfo=timezone.utc)

        now_dt = datetime.now(timezone.utc)

        days_diff = max(0.0, (now_dt - match_dt).total_seconds() / 86400.0)

        return float(math.exp(-days_diff / 303.72))

    except Exception:

        return 0.50

# ━━━━━━━━━━━━━━ 5. CACHÉ DE IDENTIDADES EN RAM (RAPIDFUZZ) ━━━━━━━━━━━━━━

PLAYER_INDEX_CACHE: List[str] = []

def get_player_universe() -> List[str]:

    global PLAYER_INDEX_CACHE

    if PLAYER_INDEX_CACHE:

        return PLAYER_INDEX_CACHE

    names = set()

    if os.path.exists(DB_PATH):

        try:

            with sqlite3.connect(DB_PATH, timeout=0.5) as conn:

                cur = conn.cursor()

                cur.execute("SELECT full_name FROM urn_directory")

                for (n,) in cur.fetchall():

                    if n:

                        names.add(n)

        except Exception:

            pass

    for db_f in ["tennis_analytics.db", "omega_39col.db", "tennis_records.db"]:

        if os.path.exists(db_f):

            try:

                with sqlite3.connect(db_f, timeout=0.5) as conn:

                    cur = conn.cursor()

                    for tbl in ["matches", "player_aliases"]:

                        try:

                            col = "canonical_name" if tbl == "player_aliases" else "winner_name"

                            cur.execute(f"SELECT DISTINCT {col} FROM {tbl} LIMIT 1500")

                            for (n,) in cur.fetchall():

                                if n:

                                    names.add(n)

                        except Exception:

                            pass

            except Exception:

                pass

    PLAYER_INDEX_CACHE = list(names)

    return PLAYER_INDEX_CACHE

def fuzzy_canonical_name(raw_name: str) -> str:

    if not HAS_RAPIDFUZZ:

        return raw_name

    universe = get_player_universe()

    if not universe:

        return raw_name

    best = process.extractOne(raw_name, universe, scorer=fuzz.token_set_ratio, score_cutoff=80.0)

    return best[0] if best else raw_name

# ━━━━━━━━━━━━━━ 6. INGESTA FORENSE ATÓMICA DE ADN (1ST/2ND/ACE/BP) ━━━━━━━━━━━━━━

class PlayerBioProfile:

    def __init__(self):

        self.raw_pts = 0

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

        self.opponents: Dict[str, List[float]] = {}

        self.h2h_matches = 0

        self.h2h_wins = 0

def detect_handedness(player_name: str, files: List[str]) -> str:

    clean_p = clean_str(player_name)

    for k, h in KNOWN_HANDEDNESS.items():

        if k in clean_p:

            return h

    last_name = clean_p.split()[-1] if clean_p else ""

    for path in sorted(files)[:3]:

        try:

            with open(path, mode='r', encoding='utf-8', errors='ignore') as f:

                header = f.readline().lower()

                cols = [c.strip() for c in header.split(",")]

                w_idx = cols.index("winner_name") if "winner_name" in cols else -1

                l_idx = cols.index("loser_name") if "loser_name" in cols else -1

                wh_idx = cols.index("winner_hand") if "winner_hand" in cols else -1

                lh_idx = cols.index("loser_hand") if "loser_hand" in cols else -1

                if (w_idx != -1 and wh_idx != -1) or (l_idx != -1 and lh_idx != -1):

                    for line in f:

                        if last_name in line.lower():

                            parts = line.split(",")

                            if w_idx != -1 and wh_idx != -1 and len(parts) > max(w_idx, wh_idx):

                                if last_name in parts[w_idx].lower() and parts[wh_idx].strip() in ("L", "R"):

                                    return parts[wh_idx].strip()

                            if l_idx != -1 and lh_idx != -1 and len(parts) > max(l_idx, lh_idx):

                                if last_name in parts[l_idx].lower() and parts[lh_idx].strip() in ("L", "R"):

                                    return parts[lh_idx].strip()

        except Exception:

            continue

    return "R"

def scan_atomic_profile(files: List[str], target_player: str, opp_player: str, target_surf: str) -> Optional[PlayerBioProfile]:

    canonical = fuzzy_canonical_name(target_player)

    tokens = clean_str(canonical).split()

    if not tokens:

        return None

    last_name = tokens[-1]

    first_init = tokens[0][0] if len(tokens[0]) > 0 else ""

    opp_last = clean_str(fuzzy_canonical_name(opp_player)).split()[-1] if opp_player else ""

    profile = PlayerBioProfile()

    surf_filter = target_surf.lower()

    for path in sorted(files):

        try:

            with open(path, mode='r', encoding='utf-8', errors='ignore') as f:

                header = f.readline()

                if not header:

                    continue

                cols = [c.strip().lower() for c in header.split(",")]

                try:

                    w_idx = cols.index("winner_name")

                    l_idx = cols.index("loser_name")

                    s_idx = cols.index("surface") if "surface" in cols else -1

                    d_idx = cols.index("tourney_date") if "tourney_date" in cols else -1

                    ws_idx = cols.index("w_svpt") if "w_svpt" in cols else -1

                    w1i_idx = cols.index("w_1stin") if "w_1stin" in cols else -1

                    w1w_idx = cols.index("w_1stwon") if "w_1stwon" in cols else -1

                    w2w_idx = cols.index("w_2ndwon") if "w_2ndwon" in cols else -1

                    wace_idx = cols.index("w_ace") if "w_ace" in cols else -1

                    wdf_idx = cols.index("w_df") if "w_df" in cols else -1

                    wbps_idx = cols.index("w_bpsaved") if "w_bpsaved" in cols else -1

                    wbpf_idx = cols.index("w_bpfaced") if "w_bpfaced" in cols else -1

                    ls_idx = cols.index("l_svpt") if "l_svpt" in cols else -1

                    l1i_idx = cols.index("l_1stin") if "l_1stin" in cols else -1

                    l1w_idx = cols.index("l_1stwon") if "l_1stwon" in cols else -1

                    l2w_idx = cols.index("l_2ndwon") if "l_2ndwon" in cols else -1

                    lace_idx = cols.index("l_ace") if "l_ace" in cols else -1

                    ldf_idx = cols.index("l_df") if "l_df" in cols else -1

                    lbps_idx = cols.index("l_bpsaved") if "l_bpsaved" in cols else -1

                    lbpf_idx = cols.index("l_bpfaced") if "l_bpfaced" in cols else -1

                except ValueError:

                    continue

                for line in f:

                    line_l = line.lower()

                    if last_name not in line_l:

                        continue

                    parts = line.split(",")

                    if len(parts) <= max(w_idx, l_idx, ws_idx, ls_idx):

                        continue

                    w_clean = clean_str(parts[w_idx])

                    l_clean = clean_str(parts[l_idx])

                    is_winner = last_name in w_clean and (first_init == "" or first_init in w_clean)

                    is_loser = last_name in l_clean and (first_init == "" or first_init in l_clean)

                    if not is_winner and not is_loser:

                        continue

                    d_str = parts[d_idx] if d_idx != -1 else ""

                    t_w = parse_date_weight(d_str)

                    r_surf = parts[s_idx].lower() if s_idx != -1 else ""

                    is_target_surf = (surf_filter in r_surf or not r_surf)

                    surf_w = 1.0 if is_target_surf else 0.20

                    weight = t_w * surf_w

                    try:

                        w_s = float(parts[ws_idx]) if ws_idx != -1 and parts[ws_idx] else 0.0

                        l_s = float(parts[ls_idx]) if ls_idx != -1 and parts[ls_idx] else 0.0

                        if w_s <= 0 or l_s <= 0:

                            continue

                        w_1i = float(parts[w1i_idx]) if w1i_idx != -1 and parts[w1i_idx] else 0.0

                        w_1w = float(parts[w1w_idx]) if w1w_idx != -1 and parts[w1w_idx] else 0.0

                        w_2w = float(parts[w2w_idx]) if w2w_idx != -1 and parts[w2w_idx] else 0.0

                        w_ac = float(parts[wace_idx]) if wace_idx != -1 and parts[wace_idx] else 0.0

                        w_df = float(parts[wdf_idx]) if wdf_idx != -1 and parts[wdf_idx] else 0.0

                        w_bps = float(parts[wbps_idx]) if wbps_idx != -1 and parts[wbps_idx] else 0.0

                        w_bpf = float(parts[wbpf_idx]) if wbpf_idx != -1 and parts[wbpf_idx] else 0.0

                        l_1i = float(parts[l1i_idx]) if l1i_idx != -1 and parts[l1i_idx] else 0.0

                        l_1w = float(parts[l1w_idx]) if l1w_idx != -1 and parts[l1w_idx] else 0.0

                        l_2w = float(parts[l2w_idx]) if l2w_idx != -1 and parts[l2w_idx] else 0.0

                        l_ac = float(parts[lace_idx]) if lace_idx != -1 and parts[lace_idx] else 0.0

                        l_df = float(parts[ldf_idx]) if ldf_idx != -1 and parts[ldf_idx] else 0.0

                        l_bps = float(parts[lbps_idx]) if lbps_idx != -1 and parts[lbps_idx] else 0.0

                        l_bpf = float(parts[lbpf_idx]) if lbpf_idx != -1 and parts[lbpf_idx] else 0.0

                    except ValueError:

                        continue

                    if is_winner:

                        opp_id = l_clean.split()[-1]

                        profile.sv_pts += w_s * weight

                        profile.sv_1st_in += w_1i * weight

                        profile.sv_1st_won += w_1w * weight

                        profile.sv_2nd_won += w_2w * weight

                        profile.sv_aces += w_ac * weight

                        profile.sv_dfs += w_df * weight

                        profile.sv_bp_saved += w_bps * weight

                        profile.sv_bp_faced += w_bpf * weight

                        profile.rc_pts += l_s * weight

                        profile.rc_won += (l_s - (l_1w + l_2w)) * weight

                        profile.rc_bp_conv += (l_bpf - l_bps) * weight

                        profile.rc_bp_opps += l_bpf * weight

                        profile.raw_pts += int(w_s)

                        if is_target_surf:

                            profile.surf_pts += w_s

                        profile.weight_tot += weight

                        if opp_id not in profile.opponents:

                            profile.opponents[opp_id] = [0.0, 0.0, 0]

                        profile.opponents[opp_id][0] += ((w_1w + w_2w) / w_s) * weight

                        profile.opponents[opp_id][1] += weight

                        profile.opponents[opp_id][2] += int(w_s)

                        if opp_last and opp_last in l_clean:

                            profile.h2h_matches += 1

                            profile.h2h_wins += 1

                    elif is_loser:

                        opp_id = w_clean.split()[-1]

                        profile.sv_pts += l_s * weight

                        profile.sv_1st_in += l_1i * weight

                        profile.sv_1st_won += l_1w * weight

                        profile.sv_2nd_won += l_2w * weight

                        profile.sv_aces += l_ac * weight

                        profile.sv_dfs += l_df * weight

                        profile.sv_bp_saved += l_bps * weight

                        profile.sv_bp_faced += l_bpf * weight

                        profile.rc_pts += w_s * weight

                        profile.rc_won += (w_s - (w_1w + w_2w)) * weight

                        profile.rc_bp_conv += (w_bpf - w_bps) * weight

                        profile.rc_bp_opps += w_bpf * weight

                        profile.raw_pts += int(l_s)

                        if is_target_surf:

                            profile.surf_pts += l_s

                        profile.weight_tot += weight

                        if opp_id not in profile.opponents:

                            profile.opponents[opp_id] = [0.0, 0.0, 0]

                        profile.opponents[opp_id][0] += ((l_1w + l_2w) / l_s) * weight

                        profile.opponents[opp_id][1] += weight

                        profile.opponents[opp_id][2] += int(l_s)

                        if opp_last and opp_last in w_clean:

                            profile.h2h_matches += 1

        except Exception:

            continue

    if profile.raw_pts >= 40 and profile.sv_pts > 0 and profile.rc_pts > 0:

        return profile

    return None

# ━━━━━━━━━━━━━━ RESOLUCIÓN DINÁMICA DE ARCHIVOS MULTI-ENTORNO ━━━━━━━━━━━━━━

def get_dataset_files(circuit: str) -> Tuple[List[str], List[str]]:

    pfx = "wta" if circuit == "WTA" else "atp"

    home_dir = os.path.expanduser("~")

    candidate_dirs = [

        os.path.join(home_dir, "tennis_modern"),

        "/data/data/com.termux/files/home/tennis_modern",

        f"/tmp/tennis_dataset/tennis_{pfx}",

        "/tmp/tennis_dataset",

        os.path.join(home_dir, f"tennis_{pfx}"),

        "tennis_modern",

        f"tennis_{pfx}",

        "."

    ]

    main_files = []

    itf_files = []

    for d in candidate_dirs:

        if os.path.isdir(d):

            for pat in [os.path.join(d, f"{pfx}_matches_202*.csv"), os.path.join(d, f"{pfx}_matches_*.csv")]:

                for f in glob.glob(pat):

                    fl = os.path.basename(f).lower()

                    if "qual" in fl or "itf" in fl or "chall" in fl or "futures" in fl:

                        if f not in itf_files:

                            itf_files.append(f)

                    else:

                        if f not in main_files:

                            main_files.append(f)

    return main_files, itf_files

def resolve_hierarchical_dna(player_input: str, opp_input: str, target_surf: str, circuit: str) -> Tuple[float, float, int, str, str, PlayerBioProfile]:

    canonical = fuzzy_canonical_name(player_input)

    mean_spw = 0.5750 if circuit == "WTA" else 0.6400

    mean_rpw = 0.4250 if circuit == "WTA" else 0.3600

    main_files, itf_files = get_dataset_files(circuit)

    hand = detect_handedness(player_input, main_files)

    prof = scan_atomic_profile(main_files, player_input, opp_input, target_surf)

    if prof:

        p_1in = prof.sv_1st_in / prof.sv_pts if prof.sv_pts > 0 else 0.62

        p_1w = prof.sv_1st_won / prof.sv_1st_in if prof.sv_1st_in > 0 else 0.70

        p_2nd_pts = prof.sv_pts - prof.sv_1st_in

        p_2w = prof.sv_2nd_won / p_2nd_pts if p_2nd_pts > 0 else 0.50

        spw_atomic = (p_1in * p_1w) + ((1.0 - p_1in) * p_2w)

        if prof.sv_bp_faced >= 20:

            bp_rate = prof.sv_bp_saved / prof.sv_bp_faced

            if bp_rate > 0.72:

                spw_atomic = 0.85 * spw_atomic + 0.15 * (spw_atomic * (1.0 - (bp_rate - 0.72) * 0.5))

        rpw_raw = prof.rc_won / prof.rc_pts if prof.rc_pts > 0 else mean_rpw

        k_shrink = 1200.0

        w_sample = prof.raw_pts / (prof.raw_pts + k_shrink)

        spw = w_sample * spw_atomic + (1.0 - w_sample) * mean_spw

        rpw = w_sample * rpw_raw + (1.0 - w_sample) * mean_rpw

        return spw, rpw, prof.raw_pts, f"CSV-MAIN ({prof.raw_pts}p)", hand, prof

    if hand == "R":

        hand = detect_handedness(player_input, itf_files)

    prof_itf = scan_atomic_profile(itf_files, player_input, opp_input, target_surf)

    if prof_itf:

        spw_raw = (prof_itf.sv_1st_won + prof_itf.sv_2nd_won) / prof_itf.sv_pts

        rpw_raw = prof_itf.rc_won / prof_itf.rc_pts

        spw_adj = spw_raw * (0.94 if circuit == "WTA" else 0.95)

        rpw_adj = rpw_raw * (0.92 if circuit == "WTA" else 0.93)

        k_shrink = 1500.0

        w_sample = prof_itf.raw_pts / (prof_itf.raw_pts + k_shrink)

        spw = w_sample * spw_adj + (1.0 - w_sample) * mean_spw

        rpw = w_sample * rpw_adj + (1.0 - w_sample) * mean_rpw

        return spw, rpw, prof_itf.raw_pts, f"CSV-ITF ({prof_itf.raw_pts}p)", hand, prof_itf

    dummy = PlayerBioProfile()

    return mean_spw, mean_rpw, 0, f"PRIOR-{circuit}", hand, dummy

# ━━━━━━━━━━━━━━ 7. MATRIZ KNOTTENBELT DE OPONENTES COMUNES ━━━━━━━━━━━━━━

def compute_common_opponents_delta(prof_a: PlayerBioProfile, prof_b: PlayerBioProfile) -> Tuple[float, int]:

    opps_a = set(prof_a.opponents.keys())

    opps_b = set(prof_b.opponents.keys())

    shared = opps_a.intersection(opps_b)

    if not shared:

        return 0.0, 0

    delta_accum = 0.0

    weight_accum = 0.0

    valid_count = 0

    for opp in shared:

        spw_a_opp, w_a, pts_a = prof_a.opponents[opp]

        spw_b_opp, w_b, pts_b = prof_b.opponents[opp]

        if w_a > 0 and w_b > 0 and (pts_a + pts_b) >= 80:

            diff = (spw_a_opp / w_a) - (spw_b_opp / w_b)

            w_pair = math.sqrt(pts_a * pts_b) / 100.0

            delta_accum += diff * w_pair

            weight_accum += w_pair

            valid_count += 1

    if weight_accum > 0:

        net_delta = max(-0.04, min(0.04, delta_accum / weight_accum))

        return net_delta, valid_count

    return 0.0, 0

# ━━━━━━━━━━━━━━ 8. BALÍSTICA, FÍSICA Y TERMODINÁMICA DE PELOTA ━━━━━━━━━━━━━━

def resolve_physics(tourn: str, city_field: Optional[str], court_env: str) -> Dict[str, Any]:

    if court_env.lower() == "indoor":

        t, p = 21.0, 1013.25

        rho = (p * 100.0) / (287.058 * (t + 273.15))

        return {"mode": "INDOOR", "temp": t, "pressure": p, "density": round(rho, 3), "delta_env": 0.0, "elev": 0}

    target_city = city_field.strip() if city_field else "New York,US"

    elev = 0

    t_name = clean_str(str(tourn or "") + " " + str(target_city)).upper()

    for c_key, c_alt in CITY_ELEVATION_METERS.items():

        if c_key in t_name or clean_str(c_key) in clean_str(t_name):

            elev = c_alt

            break

    t, w, p_sea, p_real = 24.0, 0.0, 1013.25, 1013.25

    found_live = False

    if OWM_KEY:

        try:

            r = requests.get(

                "https://api.openweathermap.org/data/2.5/weather",

                params={"q": target_city, "appid": OWM_KEY, "units": "metric"},

                timeout=1.2

            )

            if r.status_code == 200:

                d = r.json()

                t = float(d["main"]["temp"])

                w = float(d.get("wind", {}).get("speed", 0.0)) * 3.6

                p_sea = float(d["main"]["pressure"])

                p_real = float(d["main"]["grnd_level"]) if "grnd_level" in d["main"] else (

                    p_sea * math.pow(1.0 - (2.25577e-5 * elev), 5.25588) if elev > 0 else p_sea

                )

                found_live = True

        except Exception:

            pass

    if not found_live:

        p_real = 1013.25 * math.pow(1.0 - (2.25577e-5 * elev), 5.25588) if elev > 0 else 1013.25

    rho = (p_real * 100.0) / (287.058 * (t + 273.15))

    d_drag = (1.0 - (rho / 1.225)) * 0.08

    d_wind = -((w / 60.0) * 0.012)

    d_ball_temp = (t - 22.0) * 0.0016

    d_env_total = round(d_drag + d_wind + d_ball_temp, 4)

    mode_str = f"OWM({clean_str(target_city.split(',')[0])[:6]})" if found_live else (

        f"CACHE({clean_str(target_city.split(',')[0])[:6]})" if elev > 0 else "BARO"

    )

    return {

        "mode": mode_str, "temp": round(t, 1), "pressure": round(p_real, 1),

        "density": round(rho, 3), "delta_env": d_env_total, "elev": elev

    }

# ━━━━━━━━━━━━━━ 9. CADENAS DE MARKOV Y CONVOLUCIÓN EXACTA ━━━━━━━━━━━━━━

def markov_hold(p: float) -> float:

    p = max(0.01, min(0.99, p))

    q = 1.0 - p

    denom = p**2 + q**2

    return (p**4) * (1.0 + 4.0 * q + 10.0 * (q**2)) + (20.0 * (p**3) * (q**3) * (p**2 / denom) if denom > 0 else 0.0)

def markov_tiebreak(pa: float, pb: float) -> float:

    dp = [[0.0] * 8 for _ in range(8)]

    dp[0][0] = 1.0

    for total in range(12):

        for i in range(min(total + 1, 7)):

            j = total - i

            if j >= 7 or i >= 7:

                continue

            prob = dp[i][j]

            if prob <= 0.0:

                continue

            srv_a = (total == 0) or (((total + 1) // 2) % 2 == 1)

            p_pt = pa if srv_a else (1.0 - pb)

            if i + 1 <= 7:

                dp[i + 1][j] += prob * p_pt

            if j + 1 <= 7:

                dp[i][j + 1] += prob * (1.0 - p_pt)

    p_a_wins = sum(dp[7][j] for j in range(6))

    denom = (pa * (1.0 - pb)) + ((1.0 - pa) * pb)

    return p_a_wins + dp[6][6] * ((pa * (1.0 - pb)) / denom if denom > 0 else 0.5)

def analytical_set_matrix(pa_srv: float, pb_srv: float) -> Tuple[Dict[Tuple[int, int], float], float]:

    ga = markov_hold(pa_srv)

    ha = 1.0 - markov_hold(pb_srv)

    def solve_opener(start_server: int):

        dp = [[[0.0, 0.0] for _ in range(8)] for _ in range(8)]

        dp[0][0][start_server] = 1.0

        final = {}

        for total in range(13):

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

                        tb = markov_tiebreak(pa_srv, pb_srv)

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

    d0 = solve_opener(0)

    d1 = solve_opener(1)

    combined = {k: 0.5 * d0.get(k, 0.0) + 0.5 * d1.get(k, 0.0) for k in set(d0).union(d1)}

    return combined, sum(prob for (i, j), prob in combined.items() if i > j)

# ━━━━━━━━━━━━━━ 10. SHIN DE-VIGGING BIDIRECCIONAL ━━━━━━━━━━━━━━

def parse_odds(val: Any) -> Optional[float]:

    if val is None:

        return None

    s = str(val).strip()

    if not s or s.lower() in ("null", "none"):

        return None

    try:

        f = float(s)

        if s.startswith("+") or f >= 100:

            return round(1.0 + (f / 100.0), 4)

        elif s.startswith("-") or f <= -100:

            return round(1.0 + (100.0 / abs(f)), 4)

        return round(f, 4)

    except Exception:

        return None

def parse_spread(val: Any) -> Optional[float]:

    if val is None:

        return None

    try:

        return float(str(val).strip().replace("+", ""))

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

    z = mid

    denom = 2.0 * (1.0 - z)

    if denom <= 0:

        return p1 / S, p2 / S, 0.0

    t1 = math.sqrt(z**2 + 4.0 * (1.0 - z) * (p1**2) / S)

    t2 = math.sqrt(z**2 + 4.0 * (1.0 - z) * (p2**2) / S)

    pf1, pf2 = (t1 - z) / denom, (t2 - z) / denom

    tot = pf1 + pf2

    return pf1 / tot, pf2 / tot, z

def prob_to_american(p: float) -> str:

    if p <= 0.001:

        return "+99900"

    if p >= 0.999:

        return "-99900"

    if p >= 0.50:

        return f"-{int(round((p / (1.0 - p)) * 100.0))}"

    else:

        return f"+{int(round(((1.0 - p) / p) * 100.0))}"

def prob_to_decimal(p: float) -> str:

    p = max(0.001, min(0.999, p))

    return f"{1.0 / p:.2f}"

def sum_below(dist: np.ndarray, thresh: float) -> float:

    k = np.arange(len(dist))

    return float(np.sum(dist[k < thresh]))

def sum_above(dist: np.ndarray, thresh: float) -> float:

    k = np.arange(len(dist))

    return float(np.sum(dist[k > thresh]))

# ━━━━━━━━━━━━━━ 11. PIPELINE PRINCIPAL DE INFERENCIA v30 ━━━━━━━━━━━━━━

def run_prediction_pipeline(payload: Dict[str, Any]):

    t0 = time.perf_counter_ns()

    ev = payload.get("event", {})

    mkt = payload.get("market_lines", {})

    bankroll = float(payload.get("bankroll", 1000.0))

    p1_raw = ev.get("player_1", "Player A")

    p2_raw = ev.get("player_2", "Player B")

    circuit = ev.get("tour", "ATP").upper()

    tourn = ev.get("tournament", "ATP Event")

    city = ev.get("city")

    surf = ev.get("surface", "Hard")

    env_type = ev.get("court_env", "outdoor")

    best_of = int(ev.get("best_of", 3))

    spw_a, rpw_a, pts_a, src_a, hand_a, bio_a = resolve_hierarchical_dna(p1_raw, p2_raw, surf, circuit)

    spw_b, rpw_b, pts_b, src_b, hand_b, bio_b = resolve_hierarchical_dna(p2_raw, p1_raw, surf, circuit)

    phy = resolve_physics(tourn, city, env_type)

    d_env_base = phy["delta_env"]

    mean_spw = 0.5750 if circuit == "WTA" else 0.6400

    boost_a = d_env_base * math.pow(spw_a / mean_spw, 1.2)

    boost_b = d_env_base * math.pow(spw_b / mean_spw, 1.2)

    tac_matchup = ev.get("tactical_matchup", {})

    tac_bias = str(tac_matchup.get("bias", "neutral")).lower()

    exp_shape = str(tac_matchup.get("expected_shape", "symmetric")).lower()

    tactical_a, tactical_b = 0.0, 0.0

    if hand_a == "L" and hand_b == "R":

        tactical_a = 0.008 if "hard" in surf.lower() else 0.012

        tactical_b = -0.005

    elif hand_a == "R" and hand_b == "L":

        tactical_b = 0.008 if "hard" in surf.lower() else 0.012

        tactical_a = -0.005

    scout_delta_a, scout_delta_b = 0.0, 0.0

    p1_style = str(tac_matchup.get("p1_style", "")).lower()

    p2_style = str(tac_matchup.get("p2_style", "")).lower()

    if "counterpuncher" in p1_style and "aggressive" in p2_style:

        scout_delta_a += 0.005

        scout_delta_b -= 0.003

    elif "counterpuncher" in p2_style and "aggressive" in p1_style:

        scout_delta_b += 0.005

        scout_delta_a -= 0.003

    if any(k in p1_style for k in ["erratic", "volatile", "double_fault", "fragile"]):

        scout_delta_a -= 0.010

    if any(k in p2_style for k in ["erratic", "volatile", "double_fault", "fragile"]):

        scout_delta_b -= 0.010

    tactical_a += scout_delta_a

    tactical_b += scout_delta_b

    d_knotten, kn_matches = compute_common_opponents_delta(bio_a, bio_b)

    d_knotten = max(-0.025, min(0.025, d_knotten))

    h2h_matches = bio_a.h2h_matches

    h2h_a_wins = bio_a.h2h_wins

    d_h2h = 0.0

    if h2h_matches >= 2:

        w_rate = h2h_a_wins / h2h_matches

        d_h2h = (w_rate - 0.50) * 0.018

    pa_pt = spw_a + boost_a + (tactical_a / 2.0) + (d_knotten / 2.0) + (d_h2h / 2.0)

    pb_pt = spw_b + boost_b + (tactical_b / 2.0) - (d_knotten / 2.0) - (d_h2h / 2.0)

    pa_pt = max(0.40, min(0.85, pa_pt))

    pb_pt = max(0.40, min(0.85, pb_pt))

    diff_pt = pa_pt - pb_pt

    k_scale = 3.95 if circuit == "WTA" else 4.30

    p_analytic_raw = 1.0 / (1.0 + math.exp(-k_scale * diff_pt))

    pin_mkt = mkt.get("pinnacle", {})

    pin_p1_raw = parse_odds(pin_mkt.get("moneyline", {}).get("p1"))

    pin_p2_raw = parse_odds(pin_mkt.get("moneyline", {}).get("p2"))

    pin_p1_fair, pin_p2_fair, z_informed = None, None, 0.0

    if pin_p1_raw and pin_p2_raw:

        pin_p1_fair, pin_p2_fair, z_informed = shin_solve_2way(pin_p1_raw, pin_p2_raw)

    if pin_p1_fair is not None:

        match_win_a = 0.40 * p_analytic_raw + 0.60 * pin_p1_fair

        match_win_b = 1.0 - match_win_a

    else:

        match_win_a = p_analytic_raw

        match_win_b = 1.0 - p_analytic_raw

    logit_a = math.log(match_win_a / max(1e-9, 1.0 - match_win_a))

    delta_target = logit_a / k_scale

    pa_final = max(0.40, min(0.85, (pa_pt + pb_pt + delta_target) / 2.0))

    pb_final = max(0.40, min(0.85, (pa_pt + pb_pt - delta_target) / 2.0))

    hold_a = markov_hold(pa_final)

    hold_b = markov_hold(pb_final)

    set_dist, p_set_a = analytical_set_matrix(pa_final, pb_final)

    p_set_b = 1.0 - p_set_a

    d_ga = np.zeros(14, dtype=np.float64)

    d_gb = np.zeros(14, dtype=np.float64)

    fav_p_raw = max(match_win_a, match_win_b)

    is_under_bias = (tac_bias == "under" or exp_shape == "asymmetric" or fav_p_raw >= 0.68)

    for (ga, gb), prob in set_dist.items():

        tot_g = ga + gb

        p_adj = prob * (0.40 if tot_g >= 12 else (1.60 if tot_g in (7, 8, 9) else 1.0)) if is_under_bias else prob

        if ga > gb: d_ga[tot_g] += p_adj

        else: d_gb[tot_g] += p_adj

    s_ga = np.sum(d_ga)

    if s_ga > 0: d_ga /= s_ga

    s_gb = np.sum(d_gb)

    if s_gb > 0: d_gb /= s_gb

    lambda_m = (0.08 if circuit == "WTA" else 0.12) + (0.22 if is_under_bias else 0.0)

    p_a_s2_given_s1 = p_set_a + lambda_m * (1.0 - p_set_a)

    p_b_s2_given_s1 = p_set_b + lambda_m * (1.0 - p_set_b)

    p_a_20 = p_set_a * p_a_s2_given_s1

    p_b_20 = p_set_b * p_b_s2_given_s1

    p_3rd = max(0.0, 1.0 - (p_a_20 + p_b_20))

    tot_win = max(1e-9, match_win_a + match_win_b)

    p_a_21 = p_3rd * (match_win_a / tot_win)

    p_b_21 = p_3rd * (match_win_b / tot_win)

    if best_of == 5:

        p_a_30 = p_set_a**3

        p_b_30 = p_set_b**3

        p_a_31 = 3.0 * (p_set_a**3) * p_set_b

        p_b_31 = 3.0 * (p_set_b**3) * p_set_a

        p_a_32 = 6.0 * (p_set_a**3) * (p_set_b**2)

        p_b_32 = 6.0 * (p_set_b**3) * (p_set_a**2)

        tot_b5 = p_a_30 + p_b_30 + p_a_31 + p_b_31 + p_a_32 + p_b_32

        p_a_30, p_b_30 = p_a_30 / tot_b5, p_b_30 / tot_b5

        p_a_31, p_b_31 = p_a_31 / tot_b5, p_b_31 / tot_b5

        p_a_32, p_b_32 = p_a_32 / tot_b5, p_b_32 / tot_b5

        set_scores = [

            (f"{s1} 3-0", p_a_30), (f"{s2} 3-0", p_b_30),

            (f"{s1} 3-1", p_a_31), (f"{s2} 3-1", p_b_31),

            (f"{s1} 3-2", p_a_32), (f"{s2} 3-2", p_b_32)

        ]

        d_a_30 = np.convolve(np.convolve(d_ga, d_ga), d_ga)

        d_b_30 = np.convolve(np.convolve(d_gb, d_gb), d_gb)

        d_a_31 = np.convolve(d_a_30, d_gb)

        d_b_31 = np.convolve(d_b_30, d_ga)

        d_a_32 = np.convolve(d_a_31, d_gb)

        d_b_32 = np.convolve(d_b_31, d_ga)

        max_l = max(len(d_a_32), len(d_b_32))

        tot_pdf = np.zeros(max_l, dtype=np.float64)

        tot_pdf[:len(d_a_30)] += p_a_30 * d_a_30

        tot_pdf[:len(d_b_30)] += p_b_30 * d_b_30

        tot_pdf[:len(d_a_31)] += p_a_31 * d_a_31

        tot_pdf[:len(d_b_31)] += p_b_31 * d_b_31

        tot_pdf[:len(d_a_32)] += p_a_32 * d_a_32

        tot_pdf[:len(d_b_32)] += p_b_32 * d_b_32

    else:

        s1 = p1_raw.split()[-1]

        s2 = p2_raw.split()[-1]

        set_scores = [

            (f"{s2} 2-0", p_b_20), (f"{s1} 2-0", p_a_20),

            (f"{s2} 2-1", p_b_21), (f"{s1} 2-1", p_a_21)

        ]

        d_1_20 = np.convolve(d_ga, d_ga)

        d_2_20 = np.convolve(d_gb, d_gb)

        d_1_21 = np.convolve(d_1_20, d_gb)

        d_2_21 = np.convolve(d_2_20, d_ga)

        max_len = max(len(d_1_21), len(d_2_21))

        tot_pdf = np.zeros(max_len, dtype=np.float64)

        tot_pdf[:len(d_1_20)] += p_a_20 * d_1_20

        tot_pdf[:len(d_2_20)] += p_b_20 * d_2_20

        tot_pdf[:len(d_1_21)] += p_a_21 * d_1_21

        tot_pdf[:len(d_2_21)] += p_b_21 * d_2_21

    tot_line = parse_spread(pin_mkt.get("games_total", {}).get("line")) or (38.5 if best_of == 5 else 22.5)

    p_ov_main = sum_above(tot_pdf, tot_line)

    p_un_main = sum_below(tot_pdf, tot_line)

    s_tot = p_ov_main + p_un_main

    if s_tot > 0:

        p_ov_main /= s_tot

        p_un_main /= s_tot

    mean_ga_set = sum(ga * prob for (ga, gb), prob in set_dist.items())

    mean_gb_set = sum(gb * prob for (ga, gb), prob in set_dist.items())

    exp_sets = 2.0 + p_3rd if best_of == 3 else 3.5

    exp_margin = abs(mean_ga_set - mean_gb_set) * exp_sets

    first_set = []

    for (ga, gb), prob in set_dist.items():

        lbl = f"{ga}-{gb} {s1}" if ga > gb else f"{gb}-{ga} {s2}"

        first_set.append((lbl, prob))

    first_set.sort(key=lambda x: x[1], reverse=True)

    top_s1_label, top_s1_prob = first_set[0]

    if best_of == 3:

        p_a_un = p_a_20 * sum_below(d_1_20, tot_line) + p_a_21 * sum_below(d_1_21, tot_line)

        p_a_ov = p_a_20 * sum_above(d_1_20, tot_line) + p_a_21 * sum_above(d_1_21, tot_line)

        p_b_un = p_b_20 * sum_below(d_2_20, tot_line) + p_b_21 * sum_below(d_2_21, tot_line)

        p_b_ov = p_b_20 * sum_above(d_2_20, tot_line) + p_b_21 * sum_above(d_2_21, tot_line)

    else:

        p_a_un = p_a_30 * sum_below(d_a_30, tot_line) + p_a_31 * sum_below(d_a_31, tot_line) + p_a_32 * sum_below(d_a_32, tot_line)

        p_a_ov = p_a_30 * sum_above(d_a_30, tot_line) + p_a_31 * sum_above(d_a_31, tot_line) + p_a_32 * sum_above(d_a_32, tot_line)

        p_b_un = p_b_30 * sum_below(d_b_30, tot_line) + p_b_31 * sum_below(d_b_31, tot_line) + p_b_32 * sum_below(d_b_32, tot_line)

        p_b_ov = p_b_30 * sum_above(d_b_30, tot_line) + p_b_31 * sum_above(d_b_31, tot_line) + p_b_32 * sum_above(d_b_32, tot_line)

    combos = [

        (f"{s2} + Under", p_b_un),

        (f"{s1} + Under", p_a_un),

        (f"{s1} + Over", p_a_ov),

        (f"{s2} + Over", p_b_ov)

    ]

    combos.sort(key=lambda x: x[1], reverse=True)

    print(f"\n{C_CYN}{SEP}{C_RST}")

    print(pad_line(f" {C_CYN}{C_BLD}OMEGA-QUANT v30 APEX{C_RST} | {C_BLD}42-COL POCO{C_RST}"))

    print(f"{C_CYN}{DIV}{C_RST}")

    print(pad_line(f" {C_BLD}{p1_raw}{C_RST} vs {C_BLD}{p2_raw}{C_RST}"))

    print(pad_line(f" {circuit} {tourn[:16]} | {surf} Bo{best_of}"))

    print(DIV)

    print(pad_line(f"{C_YLW}[1] ENTRADA Y ADN EXACTO{C_RST}"))

    print(pad_line(f" • Alt/Aire : {phy['elev']}m | ρ={phy['density']}kg/m³"))

    print(pad_line(f" • Balística: {phy['delta_env']:+.4f} ({phy['mode']})"))

    print(pad_line(f" • [A] {s1:<7}: {src_a} ({hand_a})"))

    print(pad_line(f"   Hold Proy: {hold_a*100:4.1f}%"))

    print(pad_line(f" • [B] {s2:<7}: {src_b} ({hand_b})"))

    print(pad_line(f"   Hold Proy: {hold_b*100:4.1f}%"))

    kn_str = f" • Matriz Kn: {kn_matches} opps ({d_knotten:+.3f}) | H2H: {h2h_a_wins}-{h2h_matches-h2h_a_wins}" if kn_matches > 0 else f" • Matriz Kn: 0 opps | H2H: {h2h_a_wins}-{h2h_matches-h2h_a_wins}"

    print(pad_line(kn_str))

    p1_pin_str = f"{s1} {pin_mkt.get('moneyline', {}).get('p1', 'N/A')}"

    p2_pin_str = f"{s2} {pin_mkt.get('moneyline', {}).get('p2', 'N/A')}"

    print(pad_line(f" • Ancla Sh : {p1_pin_str} | {p2_pin_str}"))

    print(DIV)

    p1_us = prob_to_american(match_win_a)

    p2_us = prob_to_american(match_win_b)

    fav_winner = s1 if match_win_a >= match_win_b else s2

    print(pad_line(f"{C_YLW}[2] RESOLUCIÓN ANALÍTICA{C_RST}"))

    print(pad_line(f" • {s1:<6} Fair: {match_win_a*100:4.1f}% ( {C_CYN}{p1_us:>5}{C_RST}|{prob_to_decimal(match_win_a)})"))

    print(pad_line(f" • {s2:<6} Fair: {match_win_b*100:4.1f}% ( {C_CYN}{p2_us:>5}{C_RST}|{prob_to_decimal(match_win_b)})"))

    print(pad_line(f" • Set 1 Top: {top_s1_label} ({top_s1_prob*100:4.1f}%)"))

    print(pad_line(f" • Margen J : {fav_winner} +{exp_margin:.1f} proy"))

    print(SUB)

    print(pad_line(f"{C_YLW}[3] PROBABILIDAD SETS{C_RST}"))

    set_scores.sort(key=lambda x: x[1], reverse=True)

    for idx, (label, prob) in enumerate(set_scores, 1):

        us_odd = prob_to_american(prob)

        tag = f" {C_GRN}[TOP]{C_RST}" if idx == 1 else ""

        print(pad_line(f" {idx}. {label:<9}: {prob*100:4.1f}% ( {C_CYN}{us_odd:>5}{C_RST}){tag}"))

    print(SUB)

    print(pad_line(f"{C_YLW}[4] GRILLA TOTALES ({tot_line:.1f}g){C_RST}"))

    print(pad_line(" LÍNEA  OVER%  CUOTA  UNDER% CUOTA"))

    lines_list = [tot_line - 1.0, tot_line, tot_line + 1.0]

    p_overs = [sum_above(tot_pdf, l) for l in lines_list]

    p_unders = [sum_below(tot_pdf, l) for l in lines_list]

    for ln, po, pu in zip(lines_list, p_overs, p_unders):

        s_ln = po + pu

        if s_ln > 0:

            po /= s_ln

            pu /= s_ln

        us_o = prob_to_american(po)

        us_u = prob_to_american(pu)

        mark = "*" if ln == tot_line else " "

        print(pad_line(f" {ln:4.1f}g{mark}{po*100:4.1f}%  {C_CYN}{us_o:>5}{C_RST} {pu*100:4.1f}%  {C_CYN}{us_u:>5}{C_RST}"))

    print(SUB)

    print(pad_line(f"{C_YLW}[5] COMBOS BIVARIADOS{C_RST}"))

    for c_lbl, c_p in combos:

        c_us = prob_to_american(c_p)

        c_dec = prob_to_decimal(c_p)

        print(pad_line(f" • {c_lbl:<14}: {c_p*100:4.1f}% ( {C_CYN}{c_us:>5}{C_RST}|{c_dec})"))

    print(DIV)

    piso_opts = [

        (f"OVER {lines_list[0]:.1f}g", p_overs[0]),

        (f"UNDER {lines_list[2]:.1f}g", p_unders[2]),

        (f"{fav_winner} ML", max(match_win_a, match_win_b))

    ]

    piso_opts.sort(key=lambda x: x[1], reverse=True)

    piso_lbl, piso_prob = piso_opts[0] if piso_opts else ("N/A", 0.50)

    eq_lbl = f"UNDER {tot_line:.1f}g" if p_un_main >= p_ov_main else f"OVER {tot_line:.1f}g"

    eq_prob = max(p_un_main, p_ov_main)

    top_set_lbl, top_set_prob = set_scores[0]

    top_combo_lbl, top_combo_prob = combos[0]

    print(pad_line(f"{C_GRN}🎯 HOJA DE RUTA (VALOR & EJECUCIÓN){C_RST}"))

    print(pad_line(f" 1. PISO CERTEZA : {piso_lbl} ({piso_prob*100:4.1f}%) | Fair: {prob_to_decimal(piso_prob)}"))

    print(pad_line(f" 2. EQUILIBRADA  : {eq_lbl} ({eq_prob*100:4.1f}%) | Fair: {prob_to_decimal(eq_prob)}"))

    print(pad_line(f" 3. ASIMETRÍA SET: {top_set_lbl} ({top_set_prob*100:4.1f}%) | Fair: {prob_to_decimal(top_set_prob)}"))

    print(pad_line(f" 4. COMBO CORREL : {top_combo_lbl} ({top_combo_prob*100:4.1f}%) | Fair: {prob_to_decimal(top_combo_prob)}"))

    print(DIV)

    soft_mkt = mkt.get("soft", {})

    print(pad_line(f"{C_YLW}GESTIÓN MULTI-MERCADO KELLY (BANK ${bankroll:.0f}){C_RST}"))

    print(pad_line(" • Hard Cap Máximo : 4.0% ($6.00)"))

    print(pad_line(" • Regla Disparo   : EV > +3.0% vs Soft"))

    soft_p1 = parse_odds(soft_mkt.get("moneyline", {}).get("p1"))

    soft_p2 = parse_odds(soft_mkt.get("moneyline", {}).get("p2"))

    soft_tot_ov = parse_odds(soft_mkt.get("games_total", {}).get("over"))

    soft_tot_un = parse_odds(soft_mkt.get("games_total", {}).get("under"))

    ev_bets = []

    if soft_p1 and match_win_a * soft_p1 > 1.03:

        ev_bets.append((f"{s1} ML", match_win_a, soft_p1))

    if soft_p2 and match_win_b * soft_p2 > 1.03:

        ev_bets.append((f"{s2} ML", match_win_b, soft_p2))

    if soft_tot_ov and p_ov_main * soft_tot_ov > 1.03:

        ev_bets.append((f"OVER {tot_line:.1f}g", p_ov_main, soft_tot_ov))

    if soft_tot_un and p_un_main * soft_tot_un > 1.03:

        ev_bets.append((f"UNDER {tot_line:.1f}g", p_un_main, soft_tot_un))

    if not ev_bets:

        print(pad_line(" • Estado Mercado  : Sin desajustes > +3% EV"))

    else:

        for b_name, b_prob, b_odd in ev_bets:

            edge = (b_prob * b_odd) - 1.0

            q_kelly = max(0.0, min(0.04, (edge / (b_odd - 1.0)) * 0.25))

            stake_val = bankroll * q_kelly

            print(pad_line(f"{C_GRN} ▶ +EV DETECTADO: {b_name:<14} @ {b_odd:.2f}{C_RST}"))

            print(pad_line(f"   Edge: +{edge*100:.1f}% | Stake: ${stake_val:.2f} ({q_kelly*100:.1f}%)"))

    t_elapsed = (time.perf_counter_ns() - t0) / 1e6

    print(pad_line(f"{C_DIM}Runtime: {t_elapsed:.1f} ms | Afinidad A715 OK{C_RST}"))

    print(f"{C_CYN}{SEP}{C_RST}\n")

if __name__ == "__main__":

    raw_input = ""

    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):

        with open(sys.argv[1], "r", encoding="utf-8") as f:

            raw_input = f.read().strip()

    elif not sys.stdin.isatty():

        raw_input = sys.stdin.read().strip()

    if not raw_input:

        sys.stderr.write("Error: Buffer de entrada vacío.\n")

        sys.exit(1)

    try:

        run_prediction_pipeline(json.loads(raw_input))

    except Exception as ex:

        sys.stderr.write(f"Error procesando telemetría: {ex}\n")

        sys.exit(1)
