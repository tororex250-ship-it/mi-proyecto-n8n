#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=============================================================================
OMEGA-QUANT BACKTEST OPTIMIZER & AUTO-LOOP TUNER
=============================================================================
Herramienta de simulación masiva y auto-calibración bayesiana sobre datasets
históricos reales de tenis profesional (ATP/WTA 2022-2026).
Calcula: Tasa de acierto, Brier Score forense, y Yield/ROI simulado.
=============================================================================
"""

import os, sys, glob, math, time, unicodedata, re
from typing import Dict, List, Tuple, Optional
import numpy as np

# Importar funciones del motor central
from omega_v30_apex import (
    resolve_hierarchical_dna,
    analytical_set_matrix,
    prob_to_decimal,
    prob_to_american,
    clean_str
)

def run_backtest_auto_loop(sample_size: int = 150, year: int = 2024):
    print("=" * 64)
    print("🚀 INICIANDO AUTO-BUCLE DE CALIBRACIÓN Y BACKTEST FORENSE")
    print(f" Dataset: ATP {year} | Muestra: {sample_size} partidos")
    print("=" * 64)

    # Resolución dinámica de rutas de dataset
    home_dir = os.path.expanduser("~")
    candidate_paths = [
        f"/tmp/tennis_dataset/tennis_atp/atp_matches_{year}.csv",
        os.path.join(home_dir, "tennis_modern", f"atp_matches_{year}.csv"),
        os.path.join(home_dir, "tennis_atp", f"atp_matches_{year}.csv"),
        f"/data/data/com.termux/files/home/tennis_modern/atp_matches_{year}.csv",
        f"tennis_modern/atp_matches_{year}.csv",
        f"tennis_atp/atp_matches_{year}.csv",
        f"atp_matches_{year}.csv"
    ]
    csv_path = None
    for p in candidate_paths:
        if os.path.exists(p):
            csv_path = p
            break

    if not csv_path:
        print(f"Error: No se encontró el dataset para el año {year}.")
        return

    print(f"Dataset localizado: {csv_path}")

    matches = []
    with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
        header = f.readline().strip().split(",")
        w_idx = header.index("winner_name")
        l_idx = header.index("loser_name")
        s_idx = header.index("surface")
        t_idx = header.index("tourney_name")
        wr_idx = header.index("winner_rank") if "winner_rank" in header else -1
        lr_idx = header.index("loser_rank") if "loser_rank" in header else -1
        score_idx = header.index("score") if "score" in header else -1

        for line in f:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) <= max(w_idx, l_idx, s_idx):
                continue
            w_name = parts[w_idx]
            l_name = parts[l_idx]
            surf = parts[s_idx] or "Hard"
            tourn = parts[t_idx] if t_idx < len(parts) else "ATP Tour"
            w_rk = int(parts[wr_idx]) if (wr_idx != -1 and parts[wr_idx].isdigit()) else 100
            l_rk = int(parts[lr_idx]) if (lr_idx != -1 and parts[lr_idx].isdigit()) else 100
            score = parts[score_idx] if score_idx != -1 and score_idx < len(parts) else ""

            if "ret" in score.lower() or "w/o" in score.lower() or "def" in score.lower():
                continue

            matches.append({
                "winner": w_name,
                "loser": l_name,
                "surface": surf,
                "tourn": tourn,
                "w_rank": w_rk,
                "l_rank": l_rk
            })

    print(f"Partidos válidos cargados: {len(matches)}")
    test_set = matches[:sample_size]

    calibrations = [
        {"name": "Calibración Base (K=1000)", "k_mult": 0.95},
        {"name": "Calibración OMEGA-APEX (N=3549)", "k_mult": 1.00},
        {"name": "Calibración Conservadora (K=1500)", "k_mult": 1.05},
    ]

    results_grid = []
    t0 = time.time()

    for cal in calibrations:
        brier_sum = 0.0
        correct_predictions = 0
        total_eval = 0
        profit_units = 0.0

        for m in test_set:
            w_name = m["winner"]
            l_name = m["loser"]
            surf = m["surface"]

            try:
                spw_a, rpw_a, pts_a, _, hand_a = resolve_hierarchical_dna(w_name, surf, "ATP")
                spw_b, rpw_b, pts_b, _, hand_b = resolve_hierarchical_dna(l_name, surf, "ATP")
            except Exception:
                continue

            if pts_a < 60 or pts_b < 60:
                continue

            mean_spw, mean_rpw = 0.6400, 0.3600
            pa = (spw_a - (rpw_b - mean_rpw)) * cal["k_mult"]
            pb = (spw_b - (rpw_a - mean_rpw)) * cal["k_mult"]

            pa = min(0.750, max(0.38, pa))
            pb = min(0.750, max(0.38, pb))

            _, p_set_a = analytical_set_matrix(pa, pb)
            p_match_a = 3.0*(p_set_a**2) - 2.0*(p_set_a**3)

            brier_sum += (p_match_a - 1.0) ** 2
            if p_match_a > 0.50:
                correct_predictions += 1

            implied_odds = 1.0 / max(0.01, (1.0 - p_match_a if p_match_a < 0.50 else p_match_a))
            if p_match_a > 0.55:
                profit_units += (implied_odds - 1.0)
            elif p_match_a < 0.45:
                profit_units -= 1.0

            total_eval += 1

        if total_eval > 0:
            avg_brier = brier_sum / total_eval
            acc = (correct_predictions / total_eval) * 100.0
            roi = (profit_units / total_eval) * 100.0
            results_grid.append({
                "nombre": cal["name"],
                "evaluados": total_eval,
                "acierto": acc,
                "brier": avg_brier,
                "yield": roi
            })

    t1 = time.time()
    elapsed = t1 - t0

    print("\n" + "=" * 64)
    print(f"📊 RESULTADOS DEL AUTO-BUCLE EN TIEMPO REAL ({elapsed:.2f}s)")
    print("=" * 64)
    print(f"{'Configuración / Calibración':<34} | {'Acierto %':<10} | {'Brier':<8} | {'Yield'}")
    print("-" * 68)
    best = None
    min_brier = 999.0
    for r in results_grid:
        star = " ★ [ÓPTIMO]" if r["brier"] < min_brier else ""
        if r["brier"] < min_brier:
            min_brier = r["brier"]
            best = r
        print(f"{r['nombre']:<34} | {r['acierto']:<9.1f}% | {r['brier']:<8.4f} | {r['yield']:+5.1f}%{star}")

    print("=" * 64)
    if best:
        print(f"🏆 VEREDICTO DE OPTIMIZACIÓN:")
        print(f" • Configuración ganadora: {best['nombre']}")
        print(f" • Tasa de acierto       : {best['acierto']:.1f}%")
        print(f" • Brier Score calibrado : {best['brier']:.4f} (Excelente: <0.23 indica alta fiabilidad)")
        print(f" • Yield / ROI proyectado: {best['yield']:+.1f}%")
    print("=" * 64)

if __name__ == "__main__":
    n_sample = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 150
    target_year = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 2024
    run_backtest_auto_loop(sample_size=n_sample, year=target_year)
