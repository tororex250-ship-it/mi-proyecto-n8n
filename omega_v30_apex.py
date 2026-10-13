#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=============================================================================
OMEGA-QUANT v30 APEX | TEMPORAL ORACLE ENGINE (ZERO-NOISE ARCHITECTURE)
=============================================================================
Todo el motor analítico y las Leyes del Tiempo trabajan bajo el capó:
  • Leyes del Tiempo: Doble decaimiento exponencial (65% 45d / 35% 240d).
  • Vector de Momentum Temporal: Compara rendimiento reciente (60d) vs base.
  • Descomposición Biométrica Completa: 1st In, 1st Won, 2nd Won, Ace%, DF%,
    Break Point Saved% y Break Point Conversion% (ya no quedan ignorados).
  • Matriz Knottenbelt (Oponentes Comunes) + H2H Directo Ponderado por Tiempo.
  • Termodinámica y Balística (Altitud, Densidad, Viento, Humedad OWM).
  • Calibración Bidireccional de Markov (Anclaje Moneyline + Línea Totales).
  • Salida Oráculo Cero-Ruido: Solo muestra LO QUE VA A PASAR y la jugada.
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
    if hasattr(os, 'sched_setaffinity'):
        try:
            available = os.cpu_count() or 8
            target_cores = {c for c in (4, 5, 6, 7) if c < available}
            if target_cores:
                os.sched_setaffinity(0, target_cores)
        except Exception:
            pass

bind_to_cortex_a715()

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

# ━━━━━━━━━━━━━━ 1. LEYES DEL TIEMPO (PESO TEMPORAL CONTINUO) ━━━━━━━━━━━━━━
def clean_str(s: str) -> str:
    s_norm = unicodedata.normalize('NFKD', str(s))
    return ''.join(c for c in s_norm if not unicodedata.combining(c)).lower().strip()

def parse_date_metrics(date_str: str) -> Tuple[float, float]:
    """Devuelve (peso_temporal, dias_transcurridos) bajo las Leyes del Tiempo."""
    if not date_str or len(str(date_str)) < 4:
        return 0.50, 180.0
    try:
        clean_d = str(date_str).replace("-", "").strip()
        if len(clean_d) >= 8:
            match_dt = datetime.strptime(clean_d[:8], "%Y%m%d").replace(tzinfo=timezone.utc)
        else:
            match_dt = datetime(int(clean_d[:4]), 6, 1, tzinfo=timezone.utc)
        now_dt = datetime.now(timezone.utc)
        days_diff = max(0.0, (now_dt - match_dt).total_seconds() / 86400.0)
        w_momentum = math.exp(-days_diff / 45.0)
        w_baseline = math.exp(-days_diff / 240.0)
        return float(0.65 * w_momentum + 0.35 * w_baseline), days_diff
    except Exception:
        return 0.50, 180.0

def parse_date_weight(date_str: str) -> float:
    w, _ = parse_date_metrics(date_str)
    return w

# ━━━━━━━━━━━━━━ 2. CACHÉ DE IDENTIDADES EN RAM (RAPIDFUZZ + SQLITE) ━━━━━━━━━━━━━━
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

# ━━━━━━━━━━━━━━ 3. INGESTA FORENSE ATÓMICA (ACE/DF/BP/MOMENTUM) ━━━━━━━━━━━━━━
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
        # Vectores de Momentum Temporal (últimos 60 días vs histórico)
        self.recent_sv_pts = 0.0
        self.recent_sv_won = 0.0
        self.recent_matches_w = 0.0
        self.recent_wins_w = 0.0
        self.opponents: Dict[str, List[float]] = {}
        self.h2h_matches = 0
        self.h2h_wins = 0
        self.h2h_weight_wins = 0.0
        self.h2h_weight_tot = 0.0
        # Tasas computadas
        self.ace_rate = 0.05
        self.df_rate = 0.04
        self.bp_save_rate = 0.60
        self.bp_conv_rate = 0.42
        self.temporal_momentum = 0.0

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
                    t_w, days_ago = parse_date_metrics(d_str)
                    r_surf = parts[s_idx].lower() if s_idx != -1 else ""
                    is_target_surf = (surf_filter in r_surf or not r_surf)
                    surf_w = 1.0 if is_target_surf else 0.22
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
                        if days_ago <= 75.0:
                            profile.recent_sv_pts += w_s * surf_w
                            profile.recent_sv_won += (w_1w + w_2w) * surf_w
                            profile.recent_matches_w += surf_w
                            profile.recent_wins_w += surf_w
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
                            profile.h2h_weight_wins += t_w
                            profile.h2h_weight_tot += t_w
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
                        if days_ago <= 75.0:
                            profile.recent_sv_pts += l_s * surf_w
                            profile.recent_sv_won += (l_1w + l_2w) * surf_w
                            profile.recent_matches_w += surf_w
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
                            profile.h2h_weight_tot += t_w
        except Exception:
            continue
    if profile.raw_pts >= 40 and profile.sv_pts > 0 and profile.rc_pts > 0:
        return profile
    return None

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

def resolve_hierarchical_dna(player_input: str, opp_input: str, target_surf: str = "Hard", circuit: Optional[str] = None) -> Tuple[float, float, int, str, str, PlayerBioProfile]:
    """Soporta tanto llamada de 4 argumentos (motor principal) como de 3 argumentos (scripts de backtest/optuna)."""
    if circuit is None:
        # Compatibilidad retroactiva: resolve_hierarchical_dna(player, surf, circuit)
        circuit_str = str(target_surf).upper()
        surf_str = str(opp_input)
        opp_str = ""
        res = _resolve_dna_core(player_input, opp_str, surf_str, circuit_str)
        return res[:5]  # type: ignore
    return _resolve_dna_core(player_input, opp_input, target_surf, circuit)

def _resolve_dna_core(player_input: str, opp_input: str, target_surf: str, circuit: str) -> Tuple[float, float, int, str, str, PlayerBioProfile]:
    mean_spw = 0.5750 if circuit == "WTA" else 0.6400
    mean_rpw = 0.4250 if circuit == "WTA" else 0.3600
    mean_ace = 0.042 if circuit == "WTA" else 0.082
    mean_df = 0.048 if circuit == "WTA" else 0.035
    mean_bp_conv = 0.445 if circuit == "WTA" else 0.400

    main_files, itf_files = get_dataset_files(circuit)
    hand = detect_handedness(player_input, main_files)
    prof = scan_atomic_profile(main_files, player_input, opp_input, target_surf)
    if prof:
        p_1in = prof.sv_1st_in / prof.sv_pts if prof.sv_pts > 0 else 0.62
        p_1w = prof.sv_1st_won / prof.sv_1st_in if prof.sv_1st_in > 0 else 0.70
        p_2nd_pts = prof.sv_pts - prof.sv_1st_in
        p_2w = prof.sv_2nd_won / p_2nd_pts if p_2nd_pts > 0 else 0.50
        spw_atomic = (p_1in * p_1w) + ((1.0 - p_1in) * p_2w)

        # Activar telemetría biométrica real: Aces, Dobles Faltas, Quiebres y Momentum Temporal
        prof.ace_rate = prof.sv_aces / prof.sv_pts if prof.sv_pts > 0 else mean_ace
        prof.df_rate = prof.sv_dfs / prof.sv_pts if prof.sv_pts > 0 else mean_df
        prof.bp_save_rate = prof.sv_bp_saved / prof.sv_bp_faced if prof.sv_bp_faced >= 15 else 0.60
        prof.bp_conv_rate = prof.rc_bp_conv / prof.rc_bp_opps if prof.rc_bp_opps >= 15 else mean_bp_conv

        # Penalización por fragilidad real de 2do saque / exceso de dobles faltas
        df_excess = max(0.0, prof.df_rate - mean_df)
        ace_bonus = max(-0.008, min(0.010, (prof.ace_rate - mean_ace) * 0.18))
        spw_atomic = spw_atomic + ace_bonus - (df_excess * 0.22)

        # Anti-Luck en Break Points salvados
        if prof.sv_bp_faced >= 20 and prof.bp_save_rate > 0.70:
            spw_atomic = 0.85 * spw_atomic + 0.15 * (spw_atomic - (prof.bp_save_rate - 0.70) * 0.08)

        # Vector de Momentum de las Leyes del Tiempo (últimos 75 días vs media histórica)
        if prof.recent_sv_pts >= 120:
            rec_spw = prof.recent_sv_won / prof.recent_sv_pts
            prof.temporal_momentum = max(-0.018, min(0.018, (rec_spw - spw_atomic) * 0.45))
            spw_atomic += prof.temporal_momentum

        rpw_raw = prof.rc_won / prof.rc_pts if prof.rc_pts > 0 else mean_rpw
        # Integración de eficacia en conversión de Break Points al resto
        bp_conv_delta = max(-0.010, min(0.010, (prof.bp_conv_rate - mean_bp_conv) * 0.12))
        rpw_raw += bp_conv_delta

        k_shrink = 1344.0
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
        net_delta = max(-0.025, min(0.025, delta_accum / weight_accum))
        return net_delta, valid_count
    return 0.0, 0

def resolve_physics(tourn: str, city_field: Optional[str], court_env: str) -> Dict[str, Any]:
    if court_env.lower() == "indoor":
        t, p = 21.0, 1013.25
        rho = (p * 100.0) / (287.058 * (t + 273.15))
        return {"mode": "INDOOR", "temp": t, "pressure": p, "density": round(rho, 3), "delta_env": 0.0, "elev": 0, "humidity": 50.0}
    target_city = city_field.strip() if city_field else "New York,US"
    elev = 0
    t_name = clean_str(str(tourn or "") + " " + str(target_city)).upper()
    for c_key, c_alt in CITY_ELEVATION_METERS.items():
        if c_key in t_name or clean_str(c_key) in clean_str(t_name):
            elev = c_alt
            break
    t, w, p_sea, p_real, hum = 24.0, 0.0, 1013.25, 1013.25, 50.0
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
                hum = float(d["main"].get("humidity", 50.0))
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
    d_humidity = -((hum - 50.0) / 100.0) * 0.0040
    d_env_total = round(d_drag + d_wind + d_ball_temp + d_humidity, 4)
    mode_str = f"OWM({clean_str(target_city.split(',')[0])[:6]})" if found_live else (
        f"CACHE({clean_str(target_city.split(',')[0])[:6]})" if elev > 0 else "BARO"
    )
    return {
        "mode": mode_str, "temp": round(t, 1), "pressure": round(p_real, 1),
        "density": round(rho, 3), "delta_env": d_env_total, "elev": elev, "humidity": hum
    }

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

# ━━━━━━━━━━━━━━ 4. MOTOR SILENCIOSO + DICTAMEN DE LO QUE VA A PASAR ━━━━━━━━━━━━━━
def run_prediction_pipeline(payload: Dict[str, Any]):
    t0 = time.perf_counter_ns()
    ev = payload.get("event", {})
    market = payload.get("market_lines", {})
    pinn = market.get("pinnacle", {})
    soft = market.get("soft", {})
    bankroll = float(payload.get("bankroll", 150.0))

    p1_name = ev.get("player_1", "Jugador 1")
    p2_name = ev.get("player_2", "Jugador 2")
    tour = ev.get("tour", "ATP").upper()
    circuit = "WTA" if "WTA" in tour else "ATP"
    tourn = ev.get("tournament", "Torneo")
    city_f = ev.get("city")
    env = str(ev.get("court_env", "outdoor")).lower()
    surf = ev.get("surface", "Hard")
    best_of = int(ev.get("best_of", 3))

    s1 = p1_name.strip().split()[-1][:10]
    s2 = p2_name.strip().split()[-1][:10]

    # Procesamiento interno de Balística, ADN, Biometría, Knottenbelt y Leyes del Tiempo
    physics = resolve_physics(tourn, city_f, env)
    d_env_base = physics["delta_env"]

    spw_a, rpw_a, pts_a, src_a, hand_a, prof_a = _resolve_dna_core(p1_name, p2_name, surf, circuit)
    spw_b, rpw_b, pts_b, src_b, hand_b, prof_b = _resolve_dna_core(p2_name, p1_name, surf, circuit)
    knotten_delta, _ = compute_common_opponents_delta(prof_a, prof_b)

    mean_spw = 0.5750 if circuit == "WTA" else 0.6400
    mean_rpw = 0.4250 if circuit == "WTA" else 0.3600

    # El boost balístico beneficia más a quien tiene mayor tasa de Aces
    ace_factor_a = max(0.85, min(1.30, prof_a.ace_rate / (0.042 if circuit == "WTA" else 0.082)))
    ace_factor_b = max(0.85, min(1.30, prof_b.ace_rate / (0.042 if circuit == "WTA" else 0.082)))
    boost_a = d_env_base * math.pow(spw_a / mean_spw, 1.1) * ace_factor_a
    boost_b = d_env_base * math.pow(spw_b / mean_spw, 1.1) * ace_factor_b

    tactical_a, tactical_b = 0.0, 0.0
    if hand_a == "L" and hand_b == "R":
        tactical_a = 0.008 if "hard" in surf.lower() else 0.012
        tactical_b = -0.005
    elif hand_b == "L" and hand_a == "R":
        tactical_b = 0.008 if "hard" in surf.lower() else 0.012
        tactical_a = -0.005

    tactical_scout = ev.get("tactical_matchup", {})
    p1_style = str(tactical_scout.get("p1_style", "")).lower()
    p2_style = str(tactical_scout.get("p2_style", "")).lower()
    exp_shape = str(tactical_scout.get("expected_shape", "symmetric")).lower()
    tac_bias = str(tactical_scout.get("bias", "neutral")).lower()

    if ("counterpuncher" in p1_style or "defense" in p1_style) and "aggressive" in p2_style:
        tactical_a += 0.005
        tactical_b -= 0.004
    elif ("counterpuncher" in p2_style or "defense" in p2_style) and "aggressive" in p1_style:
        tactical_b += 0.005
        tactical_a -= 0.004

    if any(k in p1_style for k in ["erratic", "volatile", "double_fault", "fragile"]):
        tactical_a -= 0.012
    if any(k in p2_style for k in ["erratic", "volatile", "double_fault", "fragile"]):
        tactical_b -= 0.012

    # H2H ponderado por las Leyes del Tiempo (partidos recientes pesan más que H2H viejos)
    h2h_boost_a = 0.0
    if prof_a.h2h_weight_tot > 0:
        h2h_win_rate = prof_a.h2h_weight_wins / prof_a.h2h_weight_tot
        h2h_boost_a = (h2h_win_rate - 0.50) * min(0.022, 0.007 * prof_a.h2h_matches)

    pa_base = spw_a - (rpw_b - mean_rpw) + boost_a + tactical_a + knotten_delta + h2h_boost_a
    pb_base = spw_b - (rpw_a - mean_rpw) + boost_b + tactical_b - knotten_delta - h2h_boost_a

    if circuit == "WTA":
        pa_base = min(0.680, max(0.420, pa_base))
        pb_base = min(0.680, max(0.420, pb_base))
    else:
        pa_base = min(0.760, max(0.460, pa_base))
        pb_base = min(0.760, max(0.460, pb_base))

    pin_p1 = parse_odds(pinn.get("moneyline", {}).get("p1"))
    pin_p2 = parse_odds(pinn.get("moneyline", {}).get("p2"))
    tot_pin = pinn.get("games_total", {})
    tot_line = parse_spread(tot_pin.get("line")) or parse_spread(soft.get("games_total", {}).get("line")) or (38.5 if best_of == 5 else 22.5)

    # Calibración del baricentro de saque según la línea del mercado y sesgo táctico
    bar_p = (pa_base + pb_base) / 2.0
    ref_line = 38.5 if best_of == 5 else (21.0 if circuit == "WTA" else 22.5)
    line_shift = (tot_line - ref_line) * 0.008
    bar_p = max(0.46, min(0.74, bar_p + line_shift))

    if "under" in tac_bias or "asymmetric" in exp_shape:
        bar_p = max(0.46, bar_p - (0.016 if circuit == "WTA" else 0.020))
    elif "over" in tac_bias or "tiebreak" in exp_shape:
        bar_p = min(0.74, bar_p + 0.014)

    # Bisección Exacta de Markov (28 iteraciones)
    if pin_p1 and pin_p2:
        p_shin_a, _, _ = shin_solve_2way(pin_p1, pin_p2)
        _, p_set_a_raw = analytical_set_matrix(pa_base, pb_base)
        p_match_a_raw = (
            10.0 * (p_set_a_raw**3) - 15.0 * (p_set_a_raw**4) + 6.0 * (p_set_a_raw**5)
            if best_of == 5 else
            3.0 * (p_set_a_raw**2) - 2.0 * (p_set_a_raw**3)
        )
        min_pts = min(pts_a, pts_b)
        w_micro = min(0.35, 0.08 + 0.27 * (min_pts / 6000.0)) if min_pts > 0 else 0.08
        p_target_a = (1.0 - w_micro) * p_shin_a + w_micro * p_match_a_raw

        low_s, high_s = 0.001, 0.999
        for _ in range(28):
            mid_s = (low_s + high_s) / 2.0
            m_eval = (
                10.0 * (mid_s**3) - 15.0 * (mid_s**4) + 6.0 * (mid_s**5)
                if best_of == 5 else
                3.0 * (mid_s**2) - 2.0 * (mid_s**3)
            )
            if m_eval < p_target_a:
                low_s = mid_s
            else:
                high_s = mid_s
        s_target = (low_s + high_s) / 2.0

        low_d, high_d = -0.25, 0.25
        for _ in range(28):
            mid_d = (low_d + high_d) / 2.0
            pa_t = max(0.35, min(0.82, bar_p + mid_d))
            pb_t = max(0.35, min(0.82, bar_p - mid_d))
            _, p_eval = analytical_set_matrix(pa_t, pb_t)
            if p_eval < s_target:
                low_d = mid_d
            else:
                high_d = mid_d
        mid_d_final = (low_d + high_d) / 2.0
        pa_final = max(0.35, min(0.82, bar_p + mid_d_final))
        pb_final = max(0.35, min(0.82, bar_p - mid_d_final))
        match_win_a = p_target_a
    else:
        pa_final = pa_base
        pb_final = pb_base
        _, p_set_a_raw = analytical_set_matrix(pa_final, pb_final)
        match_win_a = (
            10.0 * (p_set_a_raw**3) - 15.0 * (p_set_a_raw**4) + 6.0 * (p_set_a_raw**5)
            if best_of == 5 else
            3.0 * (p_set_a_raw**2) - 2.0 * (p_set_a_raw**3)
        )

    match_win_b = 1.0 - match_win_a
    set_dist_matrix, p_set_a = analytical_set_matrix(pa_final, pb_final)
    p_set_b = 1.0 - p_set_a
    hold_a = markov_hold(pa_final) * 100.0
    hold_b = markov_hold(pb_final) * 100.0

    fav_prob = max(match_win_a, match_win_b)
    is_under_bias = ("under" in tac_bias or "asymmetric" in exp_shape or fav_prob >= 0.66)

    set_games_a = np.zeros(14, dtype=np.float64)
    set_games_b = np.zeros(14, dtype=np.float64)

    for (ga, gb), pr in set_dist_matrix.items():
        g = ga + gb
        if g < 14:
            w_adj = (0.68 if g >= 12 else (1.28 if g in (7, 8, 9) else 1.0)) if is_under_bias else 1.0
            if ga > gb:
                set_games_a[g] += pr * w_adj
            else:
                set_games_b[g] += pr * w_adj

    sum_ga = np.sum(set_games_a)
    if sum_ga > 0:
        set_games_a /= sum_ga
    sum_gb = np.sum(set_games_b)
    if sum_gb > 0:
        set_games_b /= sum_gb

    top_s1_label = "6-4"
    top_s1_prob = 0.0
    for (i, j), prob in set_dist_matrix.items():
        g = i + j
        w_adj = (0.68 if g >= 12 else (1.28 if g in (7, 8, 9) else 1.0)) if is_under_bias else 1.0
        p_eff = prob * w_adj
        if p_eff > top_s1_prob:
            top_s1_prob = p_eff
            w_tag = s1 if i > j else s2
            mx, mn = max(i, j), min(i, j)
            top_s1_label = f"{mx}-{mn} {w_tag}"
    norm_s1 = sum(
        prob * ((0.68 if (i + j) >= 12 else (1.28 if (i + j) in (7, 8, 9) else 1.0)) if is_under_bias else 1.0)
        for (i, j), prob in set_dist_matrix.items()
    )
    if norm_s1 > 0:
        top_s1_prob /= norm_s1

    if best_of == 5:
        p_3_0_a = p_set_a ** 3
        p_3_1_a = 3.0 * (p_set_a ** 3) * p_set_b
        p_3_2_a = 6.0 * (p_set_a ** 3) * (p_set_b ** 2)
        p_3_0_b = p_set_b ** 3
        p_3_1_b = 3.0 * (p_set_b ** 3) * p_set_a
        p_3_2_b = 6.0 * (p_set_b ** 3) * (p_set_a ** 2)
        tot_b5 = p_3_0_a + p_3_1_a + p_3_2_a + p_3_0_b + p_3_1_b + p_3_2_b
        p_3_0_a, p_3_1_a, p_3_2_a = p_3_0_a / tot_b5, p_3_1_a / tot_b5, p_3_2_a / tot_b5
        p_3_0_b, p_3_1_b, p_3_2_b = p_3_0_b / tot_b5, p_3_1_b / tot_b5, p_3_2_b / tot_b5
        score_sets = [
            (f"{s1} 3-0", p_3_0_a), (f"{s1} 3-1", p_3_1_a), (f"{s1} 3-2", p_3_2_a),
            (f"{s2} 3-0", p_3_0_b), (f"{s2} 3-1", p_3_1_b), (f"{s2} 3-2", p_3_2_b)
        ]
        c_30_a = np.convolve(np.convolve(set_games_a, set_games_a), set_games_a)
        c_31_a = np.convolve(c_30_a, set_games_b)
        c_32_a = np.convolve(c_31_a, set_games_b)
        c_30_b = np.convolve(np.convolve(set_games_b, set_games_b), set_games_b)
        c_31_b = np.convolve(c_30_b, set_games_a)
        c_32_b = np.convolve(c_31_b, set_games_a)
        tot_max = len(c_32_a)
        tot_pdf = np.zeros(tot_max, dtype=np.float64)
        tot_pdf[:len(c_30_a)] += p_3_0_a * c_30_a
        tot_pdf[:len(c_31_a)] += p_3_1_a * c_31_a
        tot_pdf[:len(c_32_a)] += p_3_2_a * c_32_a
        tot_pdf[:len(c_30_b)] += p_3_0_b * c_30_b
        tot_pdf[:len(c_31_b)] += p_3_1_b * c_31_b
        tot_pdf[:len(c_32_b)] += p_3_2_b * c_32_b
        p_3rd = p_3_2_a + p_3_2_b
    else:
        p_2_1_a_iid = 2.0 * (p_set_a ** 2) * p_set_b
        p_2_1_b_iid = 2.0 * (p_set_b ** 2) * p_set_a

        k_straight = 0.24 if is_under_bias else 0.06
        p_2_1_a = p_2_1_a_iid * (1.0 - k_straight)
        p_2_0_a = max(0.0, match_win_a - p_2_1_a)
        p_2_1_b = p_2_1_b_iid * (1.0 - k_straight)
        p_2_0_b = max(0.0, match_win_b - p_2_1_b)

        score_sets = [
            (f"{s1} 2-0", p_2_0_a), (f"{s1} 2-1", p_2_1_a),
            (f"{s2} 2-0", p_2_0_b), (f"{s2} 2-1", p_2_1_b)
        ]
        c_20_a = np.convolve(set_games_a, set_games_a)
        c_21_a = np.convolve(c_20_a, set_games_b)
        c_20_b = np.convolve(set_games_b, set_games_b)
        c_21_b = np.convolve(c_20_b, set_games_a)
        tot_max = len(c_21_a)
        tot_pdf = np.zeros(tot_max, dtype=np.float64)
        tot_pdf[:len(c_20_a)] += p_2_0_a * c_20_a
        tot_pdf[:len(c_21_a)] += p_2_1_a * c_21_a
        tot_pdf[:len(c_20_b)] += p_2_0_b * c_20_b
        tot_pdf[:len(c_21_b)] += p_2_1_b * c_21_b
        p_3rd = p_2_1_a + p_2_1_b

    score_sets.sort(key=lambda x: x[1], reverse=True)
    if np.sum(tot_pdf) > 0:
        tot_pdf /= np.sum(tot_pdf)

    exp_total_games = float(np.sum(np.arange(len(tot_pdf)) * tot_pdf))
    mean_ga_set = sum(ga * prob for (ga, gb), prob in set_dist_matrix.items())
    mean_gb_set = sum(gb * prob for (ga, gb), prob in set_dist_matrix.items())
    exp_sets = (2.0 + p_3rd) if best_of == 3 else 3.5
    exp_margin = abs(mean_ga_set - mean_gb_set) * exp_sets

    fav_is_a = match_win_a >= match_win_b
    fav_name = s1 if fav_is_a else s2
    dog_name = s2 if fav_is_a else s1

    po_main = sum_above(tot_pdf, tot_line)
    pu_main = sum_below(tot_pdf, tot_line)
    st_main = po_main + pu_main
    if st_main > 0:
        po_main /= st_main
        pu_main /= st_main

    tot_dir_lbl = f"UNDER {tot_line:.1f}g" if pu_main >= po_main else f"OVER {tot_line:.1f}g"
    tot_dir_prob = max(pu_main, po_main)

    if best_of == 3:
        p_over_given_a = p_2_0_a * sum_above(c_20_a, tot_line) + p_2_1_a * sum_above(c_21_a, tot_line)
        p_under_given_a = p_2_0_a * sum_below(c_20_a, tot_line) + p_2_1_a * sum_below(c_21_a, tot_line)
        p_over_given_b = p_2_0_b * sum_above(c_20_b, tot_line) + p_2_1_b * sum_above(c_21_b, tot_line)
        p_under_given_b = p_2_0_b * sum_below(c_20_b, tot_line) + p_2_1_b * sum_below(c_21_b, tot_line)
    else:
        p_over_given_a = p_3_0_a * sum_above(c_30_a, tot_line) + p_3_1_a * sum_above(c_31_a, tot_line) + p_3_2_a * sum_above(c_32_a, tot_line)
        p_under_given_a = p_3_0_a * sum_below(c_30_a, tot_line) + p_3_1_a * sum_below(c_31_a, tot_line) + p_3_2_a * sum_below(c_32_a, tot_line)
        p_over_given_b = p_3_0_b * sum_above(c_30_b, tot_line) + p_3_1_b * sum_above(c_31_b, tot_line) + p_3_2_b * sum_above(c_32_b, tot_line)
        p_under_given_b = p_3_0_b * sum_below(c_30_b, tot_line) + p_3_1_b * sum_below(c_31_b, tot_line) + p_3_2_b * sum_below(c_32_b, tot_line)

    combos = [
        (f"{s1} + Over", p_over_given_a),
        (f"{s1} + Under", p_under_given_a),
        (f"{s2} + Over", p_over_given_b),
        (f"{s2} + Under", p_under_given_b)
    ]
    combos.sort(key=lambda x: x[1], reverse=True)

    fav_scores = [(lbl, pr) for lbl, pr in score_sets if fav_name in lbl]
    top_set_lbl, top_set_prob = fav_scores[0] if fav_scores else score_sets[0]

    # ━━━━━━━━━━━━━━ SALIDA ORÁCULO TEMPORAL (CERO RUIDO) ━━━━━━━━━━━━━━
    print(f"\n{C_CYN}{SEP}{C_RST}")
    print(pad_line(f" {C_CYN}{C_BLD}OMEGA v30 APEX{C_RST} | {C_YLW}ORÁCULO TEMPORAL{C_RST}"))
    print(f"{C_CYN}{DIV}{C_RST}")
    print(pad_line(f" {C_BLD}{p1_name}{C_RST} vs {C_BLD}{p2_name}{C_RST}"))
    print(pad_line(f" {circuit} {tourn[:16]} | {surf} | {physics['elev']}m"))
    print(f"{DIV}")

    print(pad_line(f"{C_YLW}[1] PULSO TEMPORAL & DOMINIO DE SAQUE{C_RST}"))
    print(pad_line(f" • {s1:<10}: Hold {hold_a:4.1f}% | Win {match_win_a*100:4.1f}%"))
    print(pad_line(f" • {s2:<10}: Hold {hold_b:4.1f}% | Win {match_win_b*100:4.1f}%"))
    print(f"{DIV}")

    print(pad_line(f"{C_GRN}[2] LO QUE VA A PASAR (DICTAMEN){C_RST}"))
    print(pad_line(f" ▶ GANADOR    : {C_BLD}{fav_name} GANA{C_RST} ({fav_prob*100:4.1f}%)"))
    print(pad_line(f" ▶ MARCADOR   : {C_BLD}{top_set_lbl}{C_RST} ({top_set_prob*100:4.1f}%) | S1: {top_s1_label}"))
    print(pad_line(f" ▶ TOTAL PROY : {C_BLD}{exp_total_games:4.1f} juegos{C_RST} (Margen +{exp_margin:.1f}g)"))
    print(pad_line(f" ▶ TENDENCIA  : {C_BLD}{tot_dir_lbl}{C_RST} ({tot_dir_prob*100:4.1f}%)"))
    print(f"{DIV}")

    master_candidates = [
        (f"{fav_name} ML", fav_prob),
        (tot_dir_lbl, tot_dir_prob),
        (top_set_lbl, top_set_prob)
    ]
    master_candidates.sort(key=lambda x: x[1], reverse=True)
    master_lbl, master_prob = master_candidates[0]

    print(pad_line(f"{C_CYN}[3] ORDEN DE EJECUCIÓN (SIN RUIDO){C_RST}"))
    print(pad_line(f" 🎯 JUGADA REINA: {C_GRN}{C_BLD}{master_lbl}{C_RST} ({master_prob*100:4.1f}%)"))
    print(pad_line(f"    Cuota Justa : {prob_to_decimal(master_prob)} | Combo: {combos[0][0]}"))

    soft_p1 = parse_odds(soft.get("moneyline", {}).get("p1"))
    soft_p2 = parse_odds(soft.get("moneyline", {}).get("p2"))
    soft_tot_ov = parse_odds(soft.get("games_total", {}).get("over"))
    soft_tot_un = parse_odds(soft.get("games_total", {}).get("under"))
    soft_sb = soft.get("set_betting", {})
    soft_cb = soft.get("combos", {})

    prob_map = {lbl.strip(): p for lbl, p in score_sets}
    combo_map = {lbl.strip(): p for lbl, p in combos}

    eval_markets = [
        (f"{s1} ML", match_win_a, soft_p1),
        (f"{s2} ML", match_win_b, soft_p2),
        (f"OVER {tot_line:.1f}g", po_main, soft_tot_ov),
        (f"UNDER {tot_line:.1f}g", pu_main, soft_tot_un),
        (f"{s1} 2-0", prob_map.get(f"{s1} 2-0", 0.0), parse_odds(soft_sb.get("2_0"))),
        (f"{s1} 2-1", prob_map.get(f"{s1} 2-1", 0.0), parse_odds(soft_sb.get("2_1"))),
        (f"{s2} 2-0", prob_map.get(f"{s2} 2-0", 0.0), parse_odds(soft_sb.get("0_2"))),
        (f"{s2} 2-1", prob_map.get(f"{s2} 2-1", 0.0), parse_odds(soft_sb.get("1_2"))),
        (f"{s1} + Over", combo_map.get(f"{s1} + Over", 0.0), parse_odds(soft_cb.get("p1_over"))),
        (f"{s1} + Under", combo_map.get(f"{s1} + Under", 0.0), parse_odds(soft_cb.get("p1_under"))),
        (f"{s2} + Over", combo_map.get(f"{s2} + Over", 0.0), parse_odds(soft_cb.get("p2_over"))),
        (f"{s2} + Under", combo_map.get(f"{s2} + Under", 0.0), parse_odds(soft_cb.get("p2_under"))),
    ]

    valid_kelly = []
    for m_tag, m_prob, s_odd in eval_markets:
        if not s_odd or s_odd <= 1.05 or s_odd > 4.50:
            continue
        if dog_name in m_tag and fav_prob >= 0.58:
            continue
        if m_prob < 0.35:
            continue
        edge = (m_prob * s_odd) - 1.0
        if edge > 0.03:
            b = s_odd - 1.0
            k_fraction = max(0.0, (b * m_prob - (1.0 - m_prob)) / b)
            stake_pct = min(0.04, 0.25 * k_fraction)
            stake_val = stake_pct * bankroll
            if stake_val >= 1.50:
                valid_kelly.append((m_tag, m_prob, s_odd, edge, stake_val, stake_pct))

    valid_kelly.sort(key=lambda x: x[1] * (1.0 + x[3]), reverse=True)

    if valid_kelly:
        print(f"{SUB}")
        for m_tag, m_prob, s_odd, edge, stake_val, stake_pct in valid_kelly[:2]:
            print(pad_line(f" {C_GRN}▶ DISPARO KELLY: {m_tag:<13} @ {s_odd:.2f}{C_RST}"))
            print(pad_line(f"   Edge: +{edge*100:.1f}% | Stake: ${stake_val:.2f} ({stake_pct*100:.1f}%)"))

    t1 = time.perf_counter_ns()
    calc_ms = (t1 - t0) / 1_000_000.0
    print(f"{DIV}")
    print(pad_line(f"{C_DIM}Leyes del Tiempo OK | {calc_ms:5.1f} ms | A715{C_RST}"))
    print(f"{C_CYN}{SEP}{C_RST}\n")
    sys.stdout.flush()

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
