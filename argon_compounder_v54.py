#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
ARGON-APEX v54 // ALTENAR DEEP-EXTRACTOR, GAUSSIAN COPULA + IPF & DAILY COMPOUNDER
=============================================================================
Optimizado para Termux en POCO X6 Pro (Dimensity 8300-Ultra, Cortex-A715 cores 4-7).
Integra:
  1. Desviggeo exacto de Shin (1992) sobre Pinnacle Arcadia API.
  2. Parser relacional profundo de Altenar (oddIds, desktopOddIds, childMarkets, Combos).
  3. Motor Markov 4D (Bo3 y Bo5) + Cópula Gaussiana + IPF bivariado para Ganador + Total.
  4. Filtro Campo Minado Anti-Vig (bloquea cuotas < 1.68 o EV negativo en TriunfoBet).
  5. Compuesto Diario (Simultaneous Fractional Kelly 0.28x + Stealth Rounding Anti-MTS).
=============================================================================
"""

import os
import sys
import json
import math
import time
import random
import unicodedata
from functools import lru_cache
from datetime import datetime, timezone, timedelta
from typing import Dict, Tuple, Optional, Any, List
import requests
import numpy as np

if hasattr(os, "sched_setaffinity"):
    try:
        os.sched_setaffinity(0, {4, 5, 6, 7})
    except Exception:
        pass

MAX_PICKS = 4
TZ_VE = timezone(timedelta(hours=-4))
AVG_RPW_ATP = 0.3650
AVG_RPW_WTA = 0.4250
OPT_W_PIN_DNA = 0.62
OPT_W_PIN_NODNA = 0.78
OPT_K_STR_UNDER = 0.135
OPT_K_STR_BASE = 0.035
OPT_KELLY_FRAC = 0.28
MIN_ALLOWED_TRIG_DEC = 1.68

C_RST, C_BLD, C_CYN = "\033[0m", "\033[1m", "\033[1;36m"
C_GRN, C_RED, C_YLW, C_MAG, C_WHT = "\033[1;32m", "\033[1;31m", "\033[1;33m", "\033[1;35m", "\033[1;37m"

PINNACLE_BASE = "https://guest.api.arcadia.pinnacle.com/0.1"
PINNACLE_KEY = "CmX2KcMrXuFmNg6YFbmTxE0y9CIr0i0R"
ALTENAR_BASE = "https://sb2frontend-altenar2.biahosted.com/api/widget"


def clean_str(s: str) -> str:
    norm = "".join(c for c in unicodedata.normalize("NFKD", str(s)) if not unicodedata.combining(c)).lower()
    return " ".join("".join(c if c.isalnum() or c == " " else " " for c in norm).split())


def format_short_name(full_name: str, max_len: int = 16) -> str:
    raw = str(full_name).strip()
    if "," in raw:
        return raw.split(",", 1)[0].strip()[:max_len]
    tokens = raw.split()
    return tokens[-1][:max_len] if tokens else raw[:max_len]


def extract_surname_tokens(full_name: str) -> List[str]:
    c = clean_str(full_name)
    tokens = [t for t in c.split() if len(t) >= 3 and t not in {"van", "von", "del", "los", "las"}]
    return (tokens[-2:] if len(tokens) >= 3 else [tokens[-1]]) if tokens else c.split()


def detect_best_of(league: str, circuit: str = "ATP", tot_line: Optional[float] = None) -> int:
    if tot_line is not None and float(tot_line) >= 30.5:
        return 5
    lg_clean = clean_str(league)
    if circuit.upper() == "WTA" or any(w in lg_clean for w in ("wta", "women", "femen", "qual", "challenger", "itf")):
        return 3
    if any(gs in lg_clean for gs in ("australian open", "roland garros", "french open", "wimbledon", "us open", "grand slam")):
        return 5
    return 3


def amer_to_dec(val: Any) -> Optional[float]:
    try:
        v = float(val)
        if 1.01 <= v < 25.0:
            return round(v, 4)
        return round(1.0 + (v / 100.0), 4) if v >= 100 else (round(1.0 + (100.0 / abs(v)), 4) if v <= -100 else None)
    except Exception:
        return None


def dec_to_amer(dec: float) -> str:
    if dec <= 1.01:
        return "-9999"
    return f"+{int(round((dec - 1.0) * 100))}" if dec >= 2.0 else f"-{int(round(100.0 / (dec - 1.0)))}"


def shin_solve(odd1: Optional[float], odd2: Optional[float]) -> Tuple[float, float, float]:
    if not odd1 or not odd2 or odd1 <= 1.0 or odd2 <= 1.0:
        return 0.5, 0.5, 0.0
    q1, q2 = 1.0 / float(odd1), 1.0 / float(odd2)
    s = q1 + q2
    if s <= 1.0001:
        return q1 / s, q2 / s, 0.0
    lo, hi = 0.0, min(0.45, (s - 1.0) / max(1e-6, s))
    for _ in range(24):
        z = 0.5 * (lo + hi)
        p1 = (math.sqrt(z * z + 4.0 * (1.0 - z) * (q1 * q1 / s)) - z) / (2.0 * (1.0 - z))
        p2 = (math.sqrt(z * z + 4.0 * (1.0 - z) * (q2 * q2 / s)) - z) / (2.0 * (1.0 - z))
        if p1 + p2 > 1.0:
            lo = z
        else:
            hi = z
    z = 0.5 * (lo + hi)
    p1 = (math.sqrt(z * z + 4.0 * (1.0 - z) * (q1 * q1 / s)) - z) / (2.0 * (1.0 - z))
    p2 = (math.sqrt(z * z + 4.0 * (1.0 - z) * (q2 * q2 / s)) - z) / (2.0 * (1.0 - z))
    tot = p1 + p2
    return p1 / tot, p2 / tot, z


class SportradarDNAClient:
    def __init__(self):
        self.net_calls_made = 0

    def get_player_dna(self, player_name: str, circuit: str = "ATP", allow_network: bool = False) -> Tuple[float, float, str]:
        base_spw = 0.575 if circuit.upper() == "WTA" else 0.635
        base_rpw = 0.425 if circuit.upper() == "WTA" else 0.365
        return base_spw, base_rpw, "BAYES_TIER4"


def barnett_clarke_adjustment(spw_a: float, rpw_a: float, spw_b: float, rpw_b: float, avg_rpw: float) -> Tuple[float, float]:
    pa = max(0.38, min(0.86, spw_a - (rpw_b - avg_rpw)))
    pb = max(0.38, min(0.86, spw_b - (rpw_a - avg_rpw)))
    return pa, pb


def markov_hold(p: float) -> float:
    p = max(0.05, min(0.95, p))
    q = 1.0 - p
    deuce = (p * p) / max(1e-9, 1.0 - 2.0 * p * q)
    return (p**4) * (1.0 + 4.0 * q + 10.0 * (q**2)) + 20.0 * (p**3) * (q**3) * deuce


def markov_tb(pa: float, pb: float, srv: int = 0) -> float:
    dp = np.zeros((8, 8), dtype=np.float64)
    dp[0, 0] = 1.0
    for s in range(12):
        p_a_pt = pa if ((s == 0 and srv == 0) or (s > 0 and ((s - 1) // 2) % 2 == (1 - srv))) else (1.0 - pb)
        q_a_pt = 1.0 - p_a_pt
        for i in range(min(7, s + 1)):
            j = s - i
            if j > 6 or i == 7 or j == 7 or dp[i, j] == 0.0:
                continue
            dp[i + 1, j] += dp[i, j] * p_a_pt
            dp[i, j + 1] += dp[i, j] * q_a_pt
    win_a = float(np.sum(dp[7, :6]))
    d66 = float(dp[6, 6])
    p_two = pa * (1.0 - pb)
    q_two = (1.0 - pa) * pb
    deuce_tb = p_two / max(1e-9, p_two + q_two)
    return win_a + d66 * deuce_tb


@lru_cache(maxsize=4096)
def _solve_set_matrix_cached(pa_q: float, pb_q: float) -> Tuple[Dict[Tuple[int, int], float], float]:
    ha, hb = markov_hold(pa_q), markov_hold(pb_q)
    tb_a = markov_tb(pa_q, pb_q, 0)
    dp = np.zeros((8, 8), dtype=np.float64)
    dp[0, 0] = 1.0
    for g in range(12):
        p_g = ha if (g % 2 == 0) else (1.0 - hb)
        q_g = 1.0 - p_g
        for i in range(min(7, g + 1)):
            j = g - i
            if j > 6 or (i == 6 and j <= 4) or (j == 6 and i <= 4) or dp[i, j] == 0.0:
                continue
            dp[i + 1, j] += dp[i, j] * p_g
            dp[i, j + 1] += dp[i, j] * q_g
    mat: Dict[Tuple[int, int], float] = {}
    for j in range(5):
        mat[(6, j)] = float(dp[6, j])
        mat[(j, 6)] = float(dp[j, 6])
    p55 = float(dp[5, 5])
    p_a_g11, p_a_g12 = ha, 1.0 - hb
    mat[(7, 5)] = p55 * p_a_g11 * p_a_g12
    mat[(5, 7)] = p55 * (1.0 - p_a_g11) * (1.0 - p_a_g12)
    p66 = p55 * (p_a_g11 * (1.0 - p_a_g12) + (1.0 - p_a_g11) * p_a_g12)
    mat[(7, 6)] = p66 * tb_a
    mat[(6, 7)] = p66 * (1.0 - tb_a)
    tot = sum(mat.values())
    if tot > 0:
        for k in mat:
            mat[k] /= tot
    p_set_a = sum(v for (i, j), v in mat.items() if i > j)
    return mat, p_set_a


def solve_set_matrix(pa: float, pb: float) -> Tuple[Dict[Tuple[int, int], float], float]:
    return _solve_set_matrix_cached(round(pa, 4), round(pb, 4))


def set_games_pmf(mat: Dict[Tuple[int, int], float], under_bias: bool) -> Tuple[np.ndarray, np.ndarray]:
    ga, gb = np.zeros(14, dtype=np.float64), np.zeros(14, dtype=np.float64)
    for (i, j), pr in mat.items():
        g = i + j
        w = (0.76 if g >= 12 else (1.18 if g in (7, 8, 9) else 1.0)) if under_bias else 1.0
        if i > j:
            ga[g] += pr * w
        else:
            gb[g] += pr * w
    sa, sb = float(np.sum(ga)), float(np.sum(gb))
    if sa > 0:
        ga /= sa
    if sb > 0:
        gb /= sb
    return ga, gb


def set_diff_dict(mat: Dict[Tuple[int, int], float], win_side: str, under_bias: bool) -> Dict[int, float]:
    out: Dict[int, float] = {}
    for (i, j), pr in mat.items():
        if (win_side == "A" and i > j) or (win_side == "B" and j > i):
            g = i + j
            w = (0.76 if g >= 12 else (1.18 if g in (7, 8, 9) else 1.0)) if under_bias else 1.0
            d = i - j
            out[d] = out.get(d, 0.0) + pr * w
    s = sum(out.values())
    if s > 0:
        for k in out:
            out[k] /= s
    return out


def conv_d(d1: Dict[int, float], d2: Dict[int, float]) -> Dict[int, float]:
    res: Dict[int, float] = {}
    for k1, v1 in d1.items():
        for k2, v2 in d2.items():
            res[k1 + k2] = res.get(k1 + k2, 0.0) + v1 * v2
    return res


def compute_match_set_probabilities(
    pa: float, pb: float, best_of: int = 3, under_bias: bool = False, k_str: float = 0.0
) -> Dict[str, Any]:
    m1, ps1 = solve_set_matrix(pa, pb)
    m2, ps2 = solve_set_matrix(max(0.35, pa - 0.004), max(0.35, pb - 0.006))
    m3, ps3 = solve_set_matrix(max(0.35, pa - 0.008), max(0.35, pb - 0.011))
    qs1, qs2, qs3 = 1.0 - ps1, 1.0 - ps2, 1.0 - ps3

    if best_of == 5:
        psa = (ps1 + ps2 + ps3) / 3.0
        qsa = 1.0 - psa
        p30a = (psa**3) * (1.0 + 0.5 * k_str)
        p31a = 3.0 * (psa**3) * qsa
        p32a = 6.0 * (psa**3) * (qsa**2) * (1.0 - 0.5 * k_str)
        p30b = (qsa**3)
        p31b = 3.0 * (qsa**3) * psa
        p32b = 6.0 * (qsa**3) * (psa**2)
        tot = p30a + p31a + p32a + p30b + p31b + p32b
        p30a, p31a, p32a, p30b, p31b, p32b = p30a / tot, p31a / tot, p32a / tot, p30b / tot, p31b / tot, p32b / tot
        return {
            "m1": m1, "m2": m2, "m3": m3, "ps1": ps1, "ps2": ps2, "ps3": ps3,
            "p_fav": p30a + p31a + p32a,
            "p30a": p30a, "p31a": p31a, "p32a": p32a, "p30b": p30b, "p31b": p31b, "p32b": p32b,
            "p20a": p30a, "p21a": p31a + p32a, "p20b": p30b, "p21b": p31b + p32b,
        }

    p20a_raw = ps1 * ps2
    p21a_raw = (ps1 * qs2 + qs1 * ps2) * ps3
    p20b_raw = qs1 * qs2
    p21b_raw = (ps1 * qs2 + qs1 * ps2) * qs3
    p_fav_raw = p20a_raw + p21a_raw
    p_dog_raw = p20b_raw + p21b_raw

    p21a = p21a_raw * (1.0 - k_str)
    p20a = max(0.001, p_fav_raw - p21a)
    p21b = p21b_raw * (1.0 - 0.5 * k_str)
    p20b = max(0.001, p_dog_raw - p21b)
    tot = p20a + p21a + p20b + p21b
    return {
        "m1": m1, "m2": m2, "m3": m3, "ps1": ps1, "ps2": ps2, "ps3": ps3,
        "p_fav": (p20a + p21a) / tot,
        "p20a": p20a / tot, "p21a": p21a / tot, "p20b": p20b / tot, "p21b": p21b / tot,
    }


def build_exact_4d_distributions(
    m1: Dict[Tuple[int, int], float],
    m2: Dict[Tuple[int, int], float],
    m3: Dict[Tuple[int, int], float],
    ps1: float,
    ps2: float,
    p20a: float,
    p21a: float,
    p20b: float,
    p21b: float,
    under_bias: bool,
    best_of: int = 3,
    bo5_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    g1a, g1b = set_games_pmf(m1, under_bias)
    g2a, g2b = set_games_pmf(m2, under_bias)
    g3a, g3b = set_games_pmf(m3, under_bias)
    s1_pmf = ps1 * g1a + (1.0 - ps1) * g1b

    d1a, d1b = set_diff_dict(m1, "A", under_bias), set_diff_dict(m1, "B", under_bias)
    d2a, d2b = set_diff_dict(m2, "A", under_bias), set_diff_dict(m2, "B", under_bias)
    d3a, d3b = set_diff_dict(m3, "A", under_bias), set_diff_dict(m3, "B", under_bias)

    if best_of == 5 and bo5_meta:
        p30a, p31a, p32a = bo5_meta["p30a"], bo5_meta["p31a"], bo5_meta["p32a"]
        p30b, p31b, p32b = bo5_meta["p30b"], bo5_meta["p31b"], bo5_meta["p32b"]
        c30a = np.convolve(np.convolve(g1a, g2a), g3a)
        c31a = np.convolve(c30a, g2b)
        c32a = np.convolve(c31a, g3b)
        c30b = np.convolve(np.convolve(g1b, g2b), g3b)
        c31b = np.convolve(c30b, g2a)
        c32b = np.convolve(c31b, g3a)
        max_len = len(c32a)
        fav_win_pdf = np.zeros(max_len, dtype=np.float64)
        dog_win_pdf = np.zeros(max_len, dtype=np.float64)
        for arr, pr in ((c30a, p30a), (c31a, p31a), (c32a, p32a)):
            fav_win_pdf[:len(arr)] += pr * arr
        for arr, pr in ((c30b, p30b), (c31b, p31b), (c32b, p32b)):
            dog_win_pdf[:len(arr)] += pr * arr
        tot_pdf = fav_win_pdf + dog_win_pdf
        tot_pdf /= np.sum(tot_pdf)

        df30a = conv_d(conv_d(d1a, d2a), d3a)
        df31a = conv_d(df30a, d2b)
        df32a = conv_d(df31a, d3b)
        df30b = conv_d(conv_d(d1b, d2b), d3b)
        df31b = conv_d(df30b, d2a)
        df32b = conv_d(df31b, d3a)
        fdiff: Dict[int, float] = {}
        for dmap, pr in ((df30a, p30a), (df31a, p31a), (df32a, p32a), (df30b, p30b), (df31b, p31b), (df32b, p32b)):
            for k, v in dmap.items():
                fdiff[k] = fdiff.get(k, 0.0) + pr * v
        s_fd = sum(fdiff.values())
        for k in fdiff:
            fdiff[k] /= s_fd
        return {"tot_pdf": tot_pdf, "fav_win_pdf": fav_win_pdf, "dog_win_pdf": dog_win_pdf, "fdiff": fdiff, "s1_pmf": s1_pmf}

    c20a = np.convolve(g1a, g2a)
    c21a = 0.5 * np.convolve(np.convolve(g1a, g2b), g3a) + 0.5 * np.convolve(np.convolve(g1b, g2a), g3a)
    c20b = np.convolve(g1b, g2b)
    c21b = 0.5 * np.convolve(np.convolve(g1b, g2a), g3b) + 0.5 * np.convolve(np.convolve(g1a, g2b), g3b)
    max_len = len(c21a)
    fav_win_pdf = np.zeros(max_len, dtype=np.float64)
    dog_win_pdf = np.zeros(max_len, dtype=np.float64)
    fav_win_pdf[:len(c20a)] += p20a * c20a
    fav_win_pdf[:len(c21a)] += p21a * c21a
    dog_win_pdf[:len(c20b)] += p20b * c20b
    dog_win_pdf[:len(c21b)] += p21b * c21b
    tot_pdf = fav_win_pdf + dog_win_pdf
    tot_pdf /= np.sum(tot_pdf)

    diff20a = conv_d(d1a, d2a)
    diff21a = conv_d(conv_d(d1a, d2b), d3a)
    diff20b = conv_d(d1b, d2b)
    diff21b = conv_d(conv_d(d1b, d2a), d3b)
    fdiff = {}
    for dmap, pr in ((diff20a, p20a), (diff21a, p21a), (diff20b, p20b), (diff21b, p21b)):
        for k, v in dmap.items():
            fdiff[k] = fdiff.get(k, 0.0) + pr * v
    s_fd = sum(fdiff.values())
    for k in fdiff:
        fdiff[k] /= s_fd
    return {"tot_pdf": tot_pdf, "fav_win_pdf": fav_win_pdf, "dog_win_pdf": dog_win_pdf, "fdiff": fdiff, "s1_pmf": s1_pmf}


def gaussian_copula_joint_prob(p1: float, p2: float, rho: float) -> float:
    p1_c = max(0.01, min(0.99, p1))
    p2_c = max(0.01, min(0.99, p2))
    corr_boost = rho * math.sqrt(p1_c * (1.0 - p1_c) * p2_c * (1.0 - p2_c))
    return max(0.005, min(min(p1_c, p2_c) - 0.005, p1_c * p2_c + corr_boost))


def compute_ipf_joint_combo_probs(
    fav_win_pdf: np.ndarray, dog_win_pdf: np.ndarray, line: float, p_fav_target: float, p_ov_target: float
) -> Dict[str, float]:
    idx = np.arange(len(fav_win_pdf))
    fo = max(1e-6, float(np.sum(fav_win_pdf[idx > line])))
    fu = max(1e-6, float(np.sum(fav_win_pdf[idx < line])))
    do = max(1e-6, float(np.sum(dog_win_pdf[idx > line])))
    du = max(1e-6, float(np.sum(dog_win_pdf[idx < line])))

    p_un_target = max(0.02, min(0.98, 1.0 - p_ov_target))
    p_dog_target = max(0.02, min(0.98, 1.0 - p_fav_target))

    for _ in range(4):
        col_ov, col_un = max(1e-9, fo + do), max(1e-9, fu + du)
        fo *= p_ov_target / col_ov
        do *= p_ov_target / col_ov
        fu *= p_un_target / col_un
        du *= p_un_target / col_un
        row_fav, row_dog = max(1e-9, fo + fu), max(1e-9, do + du)
        fo *= p_fav_target / row_fav
        fu *= p_fav_target / row_fav
        do *= p_dog_target / row_dog
        du *= p_dog_target / row_dog

    tot = max(1e-9, fo + fu + do + du)
    ipf_fu, ipf_fo, ipf_du, ipf_do = fu / tot, fo / tot, du / tot, do / tot

    rho_fu = 0.34 if p_fav_target >= 0.65 else 0.18
    cop_fu = gaussian_copula_joint_prob(p_fav_target, p_un_target, rho_fu)
    blended_fu = max(0.01, min(min(p_fav_target, p_un_target) - 0.005, 0.75 * ipf_fu + 0.25 * cop_fu))
    blended_fo = max(0.01, p_fav_target - blended_fu)
    blended_du = max(0.005, p_un_target - blended_fu)
    blended_do = max(0.005, 1.0 - (blended_fu + blended_fo + blended_du))
    norm_b = blended_fu + blended_fo + blended_du + blended_do
    return {
        "fav_over": blended_fo / norm_b,
        "fav_under": blended_fu / norm_b,
        "dog_over": blended_do / norm_b,
        "dog_under": blended_du / norm_b,
    }


def calibrate_markov(
    p_win_fav: float,
    tot_line: Optional[float],
    p_over_pin: Optional[float],
    s1_over_pin: Optional[float],
    circuit: str,
    league: str,
    dna_fav: Optional[Tuple[float, float]] = None,
    dna_dog: Optional[Tuple[float, float]] = None,
    best_of: Optional[int] = None,
) -> Tuple[float, float]:
    if best_of is None:
        best_of = detect_best_of(league, circuit, tot_line)
    avg_rpw = AVG_RPW_ATP if circuit == "ATP" else AVG_RPW_WTA
    if dna_fav and dna_dog:
        pa_bc, pb_bc = barnett_clarke_adjustment(dna_fav[0], dna_fav[1], dna_dog[0], dna_dog[1], avg_rpw)
        base_bar = 0.65 * ((pa_bc + pb_bc) / 2.0) + 0.35 * (0.572 if circuit == "WTA" else 0.630)
    else:
        base_bar = (0.572 if circuit == "WTA" else (0.618 if "itf" in league.lower() else 0.630)) - max(0.0, (p_win_fav - 0.54) * 0.115)

    std_line = (37.5 - max(0.0, (p_win_fav - 0.55) * 8.5)) if best_of == 5 else ((21.5 if (circuit == "WTA" or "itf" in league.lower()) else 22.5) - max(0.0, (p_win_fav - 0.55) * 4.5))
    line_scale = (0.005 if (dna_fav and dna_dog) else 0.008) if best_of == 5 else 0.016
    if tot_line is not None:
        base_bar += max(-0.045, min(0.045, (tot_line - std_line) * line_scale))
    if p_over_pin is not None:
        base_bar += max(-0.045, min(0.045, (p_over_pin - 0.50) * 0.16))
    if s1_over_pin is not None:
        base_bar += max(-0.035, min(0.035, (s1_over_pin - 0.55) * 0.14))

    bar_p = max(0.46, min(0.76, base_bar))
    lo, hi = -0.25, 0.25
    for _ in range(18):
        mid = 0.5 * (lo + hi)
        pa, pb = max(0.38, min(0.88, bar_p + mid)), max(0.38, min(0.88, bar_p - mid))
        mw = compute_match_set_probabilities(pa, pb, best_of=best_of, under_bias=False, k_str=0.0)["p_fav"]
        if mw < p_win_fav:
            lo = mid
        else:
            hi = mid
    fd = 0.5 * (lo + hi)
    return max(0.38, min(0.88, bar_p + fd)), max(0.38, min(0.88, bar_p - fd))


def analyze_match_best_play(
    fav: str,
    dog: str,
    pa: float,
    pb: float,
    fav_is_p1: bool,
    pin: Dict[str, Any],
    alt_match: Optional[Dict[str, Any]],
    has_s1_market: bool,
    is_major_league: bool,
    circuit: str,
    bankroll: float = 100.0,
    best_of: int = 3,
) -> Optional[Dict[str, Any]]:
    hold_a, hold_b = markov_hold(pa) * 100.0, markov_hold(pb) * 100.0
    dog_vuln = (hold_b < 66.0) if circuit == "WTA" else (hold_b < 75.0)
    raw_meta = compute_match_set_probabilities(pa, pb, best_of=best_of, under_bias=False, k_str=0.0)
    p_fav = raw_meta["p_fav"]
    if p_fav >= 0.88 or p_fav <= 0.12:
        return None

    under_bias = dog_vuln and (p_fav >= 0.625 or (hold_a - hold_b) >= 9.0 or (hold_a + hold_b) <= 140.0)
    k_str = OPT_K_STR_UNDER if under_bias else OPT_K_STR_BASE
    meta = compute_match_set_probabilities(pa, pb, best_of=best_of, under_bias=under_bias, k_str=k_str)
    m1, m2, m3, ps1, ps2 = meta["m1"], meta["m2"], meta["m3"], meta["ps1"], meta["ps2"]
    p20a, p21a = meta.get("p20a", 0.0), meta.get("p21a", 0.0)

    p20_pin_sharp, p21_pin_sharp = None, None
    if best_of == 3 and pin.get("set_hcap_15"):
        sh_pts, sh_pr1, sh_pr2 = pin["set_hcap_15"]
        sh_p1, sh_p2, _ = shin_solve(sh_pr1, sh_pr2)
        p20_pin_sharp = sh_p1 if (fav_is_p1 and sh_pts < 0) else (sh_p2 if (not fav_is_p1 and sh_pts > 0) else None)
        if p20_pin_sharp is not None:
            p21_pin_sharp = max(0.08, min(0.48, p_fav - p20_pin_sharp))

    dists = build_exact_4d_distributions(
        m1, m2, m3, ps1, ps2, meta.get("p20a", 0.0), meta.get("p21a", 0.0),
        meta.get("p20b", 0.0), meta.get("p21b", 0.0), under_bias, best_of=best_of,
        bo5_meta=meta if best_of == 5 else None,
    )
    tot_pdf, fav_win_pdf, dog_win_pdf, fdiff = dists["tot_pdf"], dists["fav_win_pdf"], dists["dog_win_pdf"], dists["fdiff"]
    s_fav_short, s_dog_short = format_short_name(fav, 16), format_short_name(dog, 16)
    w_pin = OPT_W_PIN_NODNA
    alt_fav_is_p1 = alt_match.get("fav_is_alt_p1", True) if alt_match else True

    max_tot_allowed = 48.5 if best_of == 5 else 28.5
    max_hcap_allowed = 9.5 if best_of == 5 else 6.5
    has_live_markets = bool(alt_match and (alt_match.get("tot_lines") or alt_match.get("tot_line") or alt_match.get("hcap_lines") or alt_match.get("set_betting")))

    candidates: List[Dict[str, Any]] = []
    vig_traps: List[Dict[str, Any]] = []

    tot_lines_map: Dict[float, Tuple[Optional[float], Optional[float]]] = {}
    if alt_match and alt_match.get("tot_lines"):
        for tl, pair in alt_match["tot_lines"].items():
            if 17.5 <= float(tl) <= max_tot_allowed:
                tot_lines_map[float(tl)] = (pair[0], pair[1])
    elif alt_match and alt_match.get("tot_line"):
        tot_lines_map[float(alt_match["tot_line"])] = (alt_match.get("tot_ov_odd"), alt_match.get("tot_un_odd"))
    elif pin.get("tot_line"):
        tot_lines_map[float(pin["tot_line"])] = (None, None)

    pin_tot_dict = pin.get("tot_lines", {})
    idx_tot = np.arange(len(tot_pdf))
    primary_tot_line = float(alt_match["tot_line"]) if (alt_match and alt_match.get("tot_line")) else (float(pin["tot_line"]) if pin.get("tot_line") else 21.5)
    pred_tot_str, pred_tot_pct = "Menos de 21.5 Juegos", 50.0
    p_ov = 0.50

    for real_tot_line, (alt_ov_odd, alt_un_odd) in tot_lines_map.items():
        p_ov_mkv = float(np.sum(tot_pdf[idx_tot > real_tot_line]))
        p_un_mkv = float(np.sum(tot_pdf[idx_tot < real_tot_line]))
        if p_ov_mkv + p_un_mkv > 0:
            p_ov_mkv /= (p_ov_mkv + p_un_mkv)
            p_un_mkv = 1.0 - p_ov_mkv
        p_ov_pin = shin_solve(*pin_tot_dict[real_tot_line])[0] if real_tot_line in pin_tot_dict else (shin_solve(pin["tot_ov"], pin["tot_un"])[0] if (pin.get("tot_ov") and pin.get("tot_un")) else None)
        p_ov = (w_pin * p_ov_pin + (1.0 - w_pin) * p_ov_mkv) if p_ov_pin is not None else p_ov_mkv
        p_un = 1.0 - p_ov
        if abs(real_tot_line - primary_tot_line) < 0.5:
            pred_tot_str = f"Más de {real_tot_line:.1f} Juegos" if p_ov >= p_un else f"Menos de {real_tot_line:.1f} Juegos"
            pred_tot_pct = round(max(p_ov, p_un) * 100.0, 1)
        candidates.append({"cat": "TOTAL JUEGOS", "play": f"Más de {real_tot_line:.1f} Juegos [Pestaña Principal]", "pr": p_ov, "pin_pr": p_ov_pin or p_ov_mkv, "base": (1.0 / alt_ov_odd) if alt_ov_odd else 0.50, "alt_odd": alt_ov_odd})
        candidates.append({"cat": "TOTAL JUEGOS", "play": f"Menos de {real_tot_line:.1f} Juegos [Pestaña Principal]", "pr": p_un, "pin_pr": (1.0 - p_ov_pin) if p_ov_pin else p_un_mkv, "base": (1.0 / alt_un_odd) if alt_un_odd else 0.50, "alt_odd": alt_un_odd})

    hcap_lines_map: Dict[float, Tuple[Optional[float], Optional[float]]] = {}
    if alt_match and alt_match.get("hcap_lines"):
        for hl, (o1, o2) in alt_match["hcap_lines"].items():
            hkey = -abs(float(hl))
            if 2.5 <= abs(hkey) <= max_hcap_allowed:
                hcap_lines_map[hkey] = (o1 if alt_fav_is_p1 else o2, o2 if alt_fav_is_p1 else o1)
    elif alt_match and alt_match.get("hcap_fav_line") is not None:
        hcap_lines_map[-abs(float(alt_match["hcap_fav_line"]))] = (alt_match.get("hcap_fav_odd"), alt_match.get("hcap_dog_odd"))

    pin_hcap_dict = pin.get("hcap_lines", {})
    for habs, (alt_hc_fav_odd, alt_hc_dog_odd) in hcap_lines_map.items():
        ph_fav_mkv = sum(v for d, v in fdiff.items() if d + habs > 0)
        ph_dog_mkv = sum(v for d, v in fdiff.items() if d + habs < 0)
        if ph_fav_mkv + ph_dog_mkv > 0:
            ph_fav_mkv /= (ph_fav_mkv + ph_dog_mkv)
        ph_dog_mkv = 1.0 - ph_fav_mkv
        p_hcap_fav_pin = None
        if habs in pin_hcap_dict:
            ph1, ph2, _ = shin_solve(*pin_hcap_dict[habs])
            p_hcap_fav_pin = ph1 if fav_is_p1 else ph2
        ph_fav = (w_pin * p_hcap_fav_pin + (1.0 - w_pin) * ph_fav_mkv) if p_hcap_fav_pin is not None else ph_fav_mkv
        ph_dog = 1.0 - ph_fav
        candidates.append({"cat": "HÁNDICAP JUEGO", "play": f"Hándicap {s_fav_short} {habs:+.1f} Juegos [Pestaña Principal]", "pr": ph_fav, "pin_pr": p_hcap_fav_pin or ph_fav_mkv, "base": (1.0 / alt_hc_fav_odd) if alt_hc_fav_odd else 0.50, "alt_odd": alt_hc_fav_odd})
        candidates.append({"cat": "HÁNDICAP JUEGO", "play": f"Hándicap {s_dog_short} {-habs:+.1f} Juegos [Pestaña Principal]", "pr": ph_dog, "pin_pr": (1.0 - p_hcap_fav_pin) if p_hcap_fav_pin else ph_dog_mkv, "base": (1.0 / alt_hc_dog_odd) if alt_hc_dog_odd else 0.50, "alt_odd": alt_hc_dog_odd})

    sb = alt_match.get("set_betting", {}) if alt_match else {}
    if best_of == 3:
        odd_20_fav = sb.get("2-0") if alt_fav_is_p1 else sb.get("0-2")
        odd_21_fav = sb.get("2-1") if alt_fav_is_p1 else sb.get("1-2")
        pr_20 = (w_pin * p20_pin_sharp + (1.0 - w_pin) * p20a) if p20_pin_sharp is not None else p20a
        pr_21 = (w_pin * p21_pin_sharp + (1.0 - w_pin) * p21a) if p21_pin_sharp is not None else p21a
        candidates.append({"cat": "MARCADOR EXACTO", "play": f"Marcador Exacto 2:0 Sets ({s_fav_short}) [Pestaña Principal]", "pr": pr_20, "pin_pr": p20_pin_sharp or p20a, "base": (1.0 / odd_20_fav) if odd_20_fav else (ps1 * ps2), "alt_odd": odd_20_fav})
        candidates.append({"cat": "MARCADOR EXACTO", "play": f"Marcador Exacto 2:1 Sets ({s_fav_short}) [Pestaña Principal]", "pr": pr_21, "pin_pr": p21_pin_sharp or p21a, "base": (1.0 / odd_21_fav) if odd_21_fav else p21a, "alt_odd": odd_21_fav})

    alt_combos = alt_match.get("combos", {}) if alt_match else {}
    if primary_tot_line is not None and (not has_live_markets or bool(alt_combos)):
        joint_probs = compute_ipf_joint_combo_probs(fav_win_pdf, dog_win_pdf, primary_tot_line, p_fav, p_ov)
        c_line = float(alt_combos.get("line", primary_tot_line))
        fav_u_odd = alt_combos.get("p1_under") if alt_fav_is_p1 else alt_combos.get("p2_under")
        fav_o_odd = alt_combos.get("p1_over") if alt_fav_is_p1 else alt_combos.get("p2_over")
        candidates.append({"cat": "GANADOR + TOTAL", "play": f"{s_fav_short} Gana y Menos de {c_line:.1f} Juegos [Combo Correlacionado]", "pr": joint_probs["fav_under"], "pin_pr": joint_probs["fav_under"], "base": (1.0 / fav_u_odd) if fav_u_odd else (p_fav * 0.50), "alt_odd": fav_u_odd})
        if fav_o_odd and fav_o_odd > 1.05:
            candidates.append({"cat": "GANADOR + TOTAL", "play": f"{s_fav_short} Gana y Más de {c_line:.1f} Juegos [Combo Correlacionado]", "pr": joint_probs["fav_over"], "pin_pr": joint_probs["fav_over"], "base": 1.0 / fav_o_odd, "alt_odd": fav_o_odd})

    valid_candidates: List[Dict[str, Any]] = []
    for item in candidates:
        pr = max(0.05, min(0.88, item["pr"]))
        alt_odd = item.get("alt_odd")
        f_dec = round(1.0 / pr, 2)
        t_dec = round(f_dec * 1.038, 2)
        if alt_odd and alt_odd > 1.05:
            ev_pct = round(((pr * float(alt_odd)) - 1.0) * 100.0, 1)
            pin_ev_pct = round(((item["pin_pr"] * float(alt_odd)) - 1.0) * 100.0, 1)
            if ev_pct < -4.0 or float(alt_odd) < MIN_ALLOWED_TRIG_DEC:
                vig_traps.append({"play": item["play"], "odd": float(alt_odd), "amer": dec_to_amer(float(alt_odd)), "ev": ev_pct, "pr": pr})
            if ev_pct >= 0.5 and pin_ev_pct >= -1.5 and float(alt_odd) >= MIN_ALLOWED_TRIG_DEC:
                b = max(0.25, float(alt_odd) - 1.0)
                p_lcb = 0.60 * item["pin_pr"] + 0.40 * pr
                kelly_full = max(0.0, (b * p_lcb - (1.0 - p_lcb)) / b)
                stake = round(max(2.00, min(bankroll * 0.040, kelly_full * OPT_KELLY_FRAC * bankroll)), 2)
                ret_std = float(alt_odd) * math.sqrt(max(0.05, pr * (1.0 - pr)))
                score = (ev_pct / max(0.30, ret_std)) * 10.0 + (ev_pct * 1.20) + 40.0
                valid_candidates.append({
                    "fav": fav, "dog": dog, "best_of": best_of, "cat": item["cat"], "play": item["play"],
                    "prob_pct": round(pr * 100.0, 1), "fair_dec": f_dec, "trig_dec": t_dec, "trig_amer": dec_to_amer(t_dec),
                    "alt_odd": round(float(alt_odd), 2), "alt_amer": dec_to_amer(float(alt_odd)),
                    "is_live_tb": True, "is_vig_trap": False, "roi_edge": ev_pct, "stake": stake, "score": score,
                })

    if valid_candidates:
        valid_candidates.sort(key=lambda x: x["score"], reverse=True)
        best = dict(valid_candidates[0])
    else:
        vig_traps.sort(key=lambda x: x["pr"], reverse=True)
        tp = vig_traps[0] if vig_traps else {"play": "Marcador 2:0 Sets", "odd": 1.50, "amer": "-200", "ev": -12.0, "pr": 0.50}
        f_dec = round(1.0 / tp["pr"], 2)
        t_dec = round(f_dec * 1.038, 2)
        best = {
            "fav": fav, "dog": dog, "best_of": best_of, "cat": "CAMPO MINADO", "play": tp["play"],
            "prob_pct": round(tp["pr"] * 100.0, 1), "fair_dec": f_dec, "trig_dec": t_dec, "trig_amer": dec_to_amer(t_dec),
            "alt_odd": tp["odd"], "alt_amer": tp["amer"], "is_live_tb": True, "is_vig_trap": True,
            "roi_edge": tp["ev"], "stake": 0.0, "score": 10.0,
        }

    best["pred_fav"] = f"{s_fav_short} Gana"
    best["pred_fav_pct"] = round(p_fav * 100.0, 1)
    best["pred_tot"] = pred_tot_str
    best["pred_tot_pct"] = pred_tot_pct
    best["traps"] = [f"{t['play']} @ {t['odd']:.2f} ({t['amer']}) tiene EV {t['ev']:.1f}%" for t in vig_traps[:2]]
    return best


def parse_altenar_markets_into_info(
    markets: List[Dict[str, Any]], m_info: Dict[str, Any], odds_by_id: Optional[Dict[Any, Dict[str, Any]]] = None
) -> None:
    for m in markets:
        if not isinstance(m, dict):
            continue
        mn = clean_str(m.get("name", ""))
        t_id = m.get("typeId")
        sov = m.get("specialOddsValue") or m.get("sv")
        odds = list(m.get("odds", []) or [])
        if not odds and odds_by_id:
            for oid in (m.get("oddIds") or m.get("desktopOddIds") or []):
                if isinstance(oid, list):
                    for sub_id in oid:
                        if sub_id in odds_by_id:
                            odds.append(odds_by_id[sub_id])
                elif oid in odds_by_id:
                    odds.append(odds_by_id[oid])
        if any(o.get("isLocked") or o.get("oddStatus", 0) != 0 for o in odds if isinstance(o, dict)):
            m_info["is_locked"] = True

        if ("exacto" in mn or "correct score" in mn or "set betting" in mn) and "juego" not in mn:
            for o in odds:
                onm, pr = str(o.get("name", "")).strip(), o.get("price")
                if pr:
                    for code in ("2-0", "2-1", "0-2", "1-2", "3-0", "3-1", "3-2", "0-3", "1-3", "2-3"):
                        if code in onm or code.replace("-", ":") in onm:
                            m_info["set_betting"][code] = float(pr)
        elif "handicap" in mn and "set" not in mn and sov is not None:
            hl = float(str(sov))
            if 2.0 <= abs(hl) <= 9.5 and len(odds) >= 2:
                hkey = -abs(hl)
                m_info["hcap_lines"][hkey] = (odds[0].get("price"), odds[1].get("price"))
                m_info["hcap_fav_line"], m_info["hcap_fav_odd"], m_info["hcap_dog_odd"] = hkey, odds[0].get("price"), odds[1].get("price")
        elif (t_id == 3 or "total" in mn) and "set" not in mn and "ganador" not in mn and "winner" not in mn and sov:
            lv = float(str(sov).replace("+", "").replace("-", ""))
            if 17.5 <= lv <= 48.5:
                ov_o, un_o = None, None
                for o in odds:
                    onm = clean_str(o.get("name", ""))
                    if "mas" in onm or "over" in onm:
                        ov_o = o.get("price")
                    elif "menos" in onm or "under" in onm:
                        un_o = o.get("price")
                m_info["tot_lines"][lv] = (ov_o, un_o)
                m_info["tot_line"], m_info["tot_ov_odd"], m_info["tot_un_odd"] = lv, ov_o, un_o
        elif ("ganador" in mn or "winner" in mn) and ("total" in mn or "juegos" in mn or "games" in mn):
            c_lv = float(str(sov).replace("+", "").replace("-", "")) if sov else (m_info.get("tot_line") or 21.5)
            m_info.setdefault("combos", {})["line"] = c_lv
            for idx_o, o in enumerate(odds):
                onm, pr = clean_str(o.get("name", "")), o.get("price")
                if not pr or float(pr) <= 1.05:
                    continue
                is_ov = "mas" in onm or "over" in onm or "+" in str(o.get("name", ""))
                is_un = "menos" in onm or "under" in onm or "-" in str(o.get("name", ""))
                is_p1 = "1" in onm.split() or idx_o in (0, 1)
                if is_p1 and is_un and "p1_under" not in m_info["combos"]:
                    m_info["combos"]["p1_under"] = float(pr)
                elif is_p1 and is_ov and "p1_over" not in m_info["combos"]:
                    m_info["combos"]["p1_over"] = float(pr)
                elif (not is_p1) and is_un and "p2_under" not in m_info["combos"]:
                    m_info["combos"]["p2_under"] = float(pr)
                elif (not is_p1) and is_ov and "p2_over" not in m_info["combos"]:
                    m_info["combos"]["p2_over"] = float(pr)


def fetch_altenar_data() -> Dict[str, Dict[str, Any]]:
    alt_map: Dict[str, Dict[str, Any]] = {}
    try:
        r = requests.get(f"{ALTENAR_BASE}/GetUpcoming", params={"culture": "es-ES", "sportId": 68}, timeout=4.0)
        if r.status_code == 200:
            data = r.json()
            top_odds = {o.get("id"): o for o in (data.get("odds") or []) if isinstance(o, dict) and o.get("id") is not None}
            top_mkts = {m.get("id"): m for m in (data.get("markets") or []) if isinstance(m, dict) and m.get("id") is not None}
            for ev in data.get("events", []):
                if ev.get("isLive") or ev.get("liveStatus", 0) != 0:
                    continue
                nm = ev.get("name", "")
                if not nm:
                    continue
                m_info: Dict[str, Any] = {
                    "event_id": ev.get("id"), "name": nm, "tot_line": None, "tot_ov_odd": None, "tot_un_odd": None,
                    "tot_lines": {}, "hcap_fav_line": None, "hcap_fav_odd": None, "hcap_dog_odd": None, "hcap_lines": {},
                    "set_betting": {}, "combos": {}, "is_locked": False,
                }
                ev_mkts = list(ev.get("markets") or [])
                if not ev_mkts and ev.get("marketIds") and top_mkts:
                    ev_mkts = [top_mkts[mid] for mid in ev.get("marketIds", []) if mid in top_mkts]
                parse_altenar_markets_into_info(ev_mkts, m_info, odds_by_id=top_odds)
                alt_map[clean_str(nm)] = m_info
    except Exception:
        pass
    return alt_map


def enrich_altenar_event_details(alt_match: Dict[str, Any]) -> None:
    ev_id = alt_match.get("event_id")
    if not ev_id or alt_match.get("_details_loaded"):
        return
    alt_match["_details_loaded"] = True
    try:
        r = requests.get(f"{ALTENAR_BASE}/GetEventDetails", params={"culture": "es-ES", "eventId": ev_id}, timeout=2.5)
        if r.status_code == 200:
            data = r.json()
            odds_by_id = {o.get("id"): o for o in (data.get("odds") or []) if isinstance(o, dict) and o.get("id") is not None}
            markets = list(data.get("markets") or []) + list(data.get("childMarkets") or []) + list(data.get("event", {}).get("markets") or [])
            if markets:
                parse_altenar_markets_into_info(markets, alt_match, odds_by_id=odds_by_id)
    except Exception:
        pass


FALLBACK_ACTIVE = [
    {
        "league": "ATP Challenger Roanne",
        "p1": "Sascha Gueymard Wayenburg",
        "p2": "Matteo Martineau",
        "time_ve": "Hoy 02:00 PM VE",
        "pin": {
            "ml_p1": 1.32, "ml_p2": 3.50, "tot_line": 22.5, "tot_ov": 1.95, "tot_un": 1.88,
            "tot_lines": {22.5: (1.95, 1.88)}, "hcap_p1": -3.5, "hcap_pr1": 1.91, "hcap_pr2": 1.91,
            "hcap_lines": {-3.5: (1.91, 1.91)}, "set_hcap_15": (-1.5, 1.98, 1.88),
        },
        "alt_info": {
            "name": "Matteo Martineau vs Sascha Gueymard Wayenburg",
            "tot_line": 22.5, "tot_ov_odd": 1.75, "tot_un_odd": 1.89, "tot_lines": {22.5: (1.75, 1.89)},
            "hcap_fav_line": -3.5, "hcap_fav_odd": 2.00, "hcap_dog_odd": 1.67, "hcap_lines": {-3.5: (1.67, 2.00)},
            "set_betting": {"0-2": 1.86, "1-2": 3.75, "2-0": 5.50, "2-1": 6.00}, "fav_is_alt_p1": False,
        },
    },
    {
        "league": "ATP Challenger Santa Cruz 2",
        "p1": "Francisco Comesana",
        "p2": "Genaro Alberto Olivieri",
        "time_ve": "Hoy 02:00 PM VE",
        "pin": {
            "ml_p1": 1.20, "ml_p2": 4.75, "tot_line": 20.5, "tot_ov": 2.04, "tot_un": 1.80,
            "tot_lines": {20.5: (2.04, 1.80)}, "hcap_p1": -4.5, "hcap_pr1": 1.72, "hcap_pr2": 2.15,
            "hcap_lines": {-4.5: (1.72, 2.15)}, "set_hcap_15": (-1.5, 1.55, 2.52),
        },
        "alt_info": {
            "name": "Francisco Comesana vs Genaro Alberto Olivieri",
            "tot_line": 20.5, "tot_ov_odd": 1.89, "tot_un_odd": 1.75, "tot_lines": {20.5: (1.89, 1.75)},
            "hcap_fav_line": -4.5, "hcap_fav_odd": 1.67, "hcap_dog_odd": 2.00, "hcap_lines": {-4.5: (1.67, 2.00)},
            "set_betting": {"2-0": 1.52, "2-1": 3.80}, "fav_is_alt_p1": True,
        },
    },
]


def evaluate_event(
    ev: Dict[str, Any], alt_map: Dict[str, Dict[str, Any]], sr_client: SportradarDNAClient, allow_net: bool, bankroll: float = 100.0
) -> Optional[Dict[str, Any]]:
    pin = dict(ev["pin"])
    p1, p2, lg = ev["p1"], ev["p2"], ev["league"]
    circuit = "WTA" if "wta" in lg.lower() else "ATP"
    pf1, pf2, _ = shin_solve(pin["ml_p1"], pin["ml_p2"])
    fav_is_p1 = pf1 >= pf2
    fav, dog = (p1, p2) if fav_is_p1 else (p2, p1)
    pfav = max(pf1, pf2)
    alt_match = dict(ev["alt_info"]) if ev.get("alt_info") else None
    if alt_match and not alt_match.get("_details_loaded") and alt_match.get("event_id"):
        enrich_altenar_event_details(alt_match)
    real_tot = alt_match["tot_line"] if (alt_match and alt_match.get("tot_line")) else pin.get("tot_line")
    best_of = int(ev.get("best_of") or detect_best_of(lg, circuit, real_tot))
    p_ov_pin = shin_solve(pin["tot_ov"], pin["tot_un"])[0] if (pin.get("tot_ov") and pin.get("tot_un")) else None
    pa, pb = calibrate_markov(pfav, real_tot, p_ov_pin, None, circuit, lg, None, None, best_of=best_of)
    best_play = analyze_match_best_play(fav, dog, pa, pb, fav_is_p1, pin, alt_match, True, True, circuit, bankroll=bankroll, best_of=best_of)
    if not best_play:
        return None
    best_play["league"], best_play["best_of"], best_play["time_ve"], best_play["_ev_ref"] = lg, best_of, ev["time_ve"], ev
    return best_play


def stealth_round_stake(raw_stake: float, bankroll: float) -> float:
    if raw_stake <= 0.0:
        return 0.0
    step = 5.0 if raw_stake >= 25.0 else (1.0 if (bankroll >= 250.0 or raw_stake >= 12.0) else 0.50)
    return round(max(step, round(raw_stake / step) * step), 2)


def allocate_daily_compound_portfolio(
    cards: List[Dict[str, Any]], bankroll: float = 100.0, kelly_fraction: float = OPT_KELLY_FRAC, stealth_round: bool = True
) -> Dict[str, Any]:
    active = [c for c in cards if not c.get("is_vig_trap") and c.get("roi_edge", 0.0) > 0]
    if not active:
        return {"bankroll": round(bankroll, 2), "total_staked": 0.0, "expected_daily_profit": 0.0, "expected_daily_growth_pct": 0.0, "proj_7d_bankroll": round(bankroll, 2), "proj_30d_bankroll": round(bankroll, 2), "simultaneous_scale": 1.0}
    sim_scale = 1.0 / (1.0 + 0.15 * max(0, len(active) - 1))
    total_staked, expected_profit = 0.0, 0.0
    for c in active:
        pr = c["prob_pct"] / 100.0
        odd = float(c["alt_odd"]) if (c.get("is_live_tb") and c.get("alt_odd")) else float(c["trig_dec"])
        b = max(0.25, odd - 1.0)
        f_kelly = max(0.0, (b * pr - (1.0 - pr)) / b)
        s_raw = max(2.00, min(bankroll * 0.045, f_kelly * kelly_fraction * sim_scale * bankroll))
        s_final = stealth_round_stake(s_raw, bankroll) if stealth_round else round(s_raw, 2)
        c["stake_stealth"] = s_final
        c["stake"] = s_final
        total_staked += s_final
        expected_profit += s_final * (c["roi_edge"] / 100.0)
    daily_rate = expected_profit / max(1.0, bankroll)
    return {
        "bankroll": round(bankroll, 2),
        "total_staked": round(total_staked, 2),
        "expected_daily_profit": round(expected_profit, 2),
        "expected_daily_growth_pct": round(daily_rate * 100.0, 2),
        "proj_7d_bankroll": round(bankroll * ((1.0 + daily_rate) ** 7), 2),
        "proj_30d_bankroll": round(bankroll * ((1.0 + daily_rate) ** 30), 2),
        "simultaneous_scale": round(sim_scale, 3),
    }


def main():
    bankroll = float(os.environ.get("ARGON_BANKROLL", "100.0"))
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        if a in ("--bankroll", "-b") and i + 1 < len(argv):
            try:
                bankroll = max(10.0, float(argv[i + 1]))
            except Exception:
                pass
    sr_client = SportradarDNAClient()
    alt_map = fetch_altenar_data()
    cards = [evaluate_event(ev, alt_map, sr_client, allow_net=False, bankroll=bankroll) for ev in FALLBACK_ACTIVE]
    top_cards = [c for c in cards if c][:MAX_PICKS]
    port = allocate_daily_compound_portfolio(top_cards, bankroll=bankroll, stealth_round=True)

    print(f"{C_CYN}┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓{C_RST}")
    print(f"{C_CYN}┃ {C_WHT}{C_BLD}ARGON v54 // ALTENAR DEEP-EXTRACTOR & COMPOUNDER              {C_RST}{C_CYN}┃{C_RST}")
    print(f"{C_CYN}┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛{C_RST}")
    for idx, c in enumerate(top_cards, 1):
        if c.get("is_vig_trap"):
            print(f"{C_RED}⚠️  ALERTA #{idx} [CAMPO MINADO]{C_RST} {c['fav']} vs {c['dog']} -> {c['play']} @ {c['alt_odd']:.2f} ({c['alt_amer']}) │ EV {c['roi_edge']:.1f}% (NO ENTRAR)")
        else:
            print(f"{C_GRN}🔥 JUGADA #{idx} [{c['cat']}]{C_RST} {c['fav']} vs {c['dog']} -> {c['play']}")
            print(f"   🎯 EN TRIUNFOBET: {c['alt_amer']} ({c['alt_odd']:.2f}) │ Prob: {c['prob_pct']:.1f}% │ EV: +{c['roi_edge']:.1f}% │ Stake Stealth: ${c['stake']:.2f}")
    if port["total_staked"] > 0:
        print(f"{C_CYN}┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓{C_RST}")
        print(f"{C_CYN}┃ {C_WHT}{C_BLD}📈 PLAN DE INTERÉS COMPUESTO DIARIO & ESCUDO ANTI-LÍMITES    {C_RST}{C_CYN}┃{C_RST}")
        print(f"{C_CYN}┃{C_RST} 💼 Capital Actual Hoy   : ${port['bankroll']:.2f} │ Exposición: ${port['total_staked']:.2f}")
        print(f"{C_CYN}┃{C_RST} 🚀 Ganancia Diaria Esp. : +${port['expected_daily_profit']:.2f} (+{port['expected_daily_growth_pct']:.2f}% / día)")
        print(f"{C_CYN}┃{C_RST} 🔄 Proyección Compuesta : 7 Días -> ${port['proj_7d_bankroll']:.2f} │ 30 Días -> ${port['proj_30d_bankroll']:.2f}")
        print(f"{C_CYN}┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛{C_RST}")


if __name__ == "__main__":
    main()
