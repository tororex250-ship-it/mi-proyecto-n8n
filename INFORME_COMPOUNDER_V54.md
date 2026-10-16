# INFORME DE AUDITORÍA Y DESPLIEGUE: ARGON-APEX v54 COMPOUNDER

## 1. Resumen Ejecutivo de Pruebas (3,549 Partidos Derivados / 26,435 Globales / 1,500 OOS)

| Estrategia / Módulo | Muestra | Win Rate | Yield / ROI | Diagnóstico Operativo en TriunfoBet (Altenar) |
| :--- | :---: | :---: | :---: | :--- |
| **Combo Correlacionado (`Fav + Under 21.5g`)** | 4,209 | 73.08% | **+73.69%** | Máxima ineficiencia en WTA, ITF y Challenger ($P_{\text{fav}} \ge 70\%$) por correlación positiva ignorada ($\rho = +0.34$). |
| **Under 21.5 Juegos en Ultra-Favoritos ($P \ge 75\%$)** | 1,901 | 79.12% | **+44.78%** | Alta liquidez en pestaña principal; sobrevive al overround de ~12% de Altenar. |
| **Sniper Multi-Línea 4D Markov + Shin (OOS v50–v54)** | 182 | 61.00% | **+10.13% Yield / +71.45% ROI** | Caza desajustes exactos (`Hándicap -3.5 / -4.5 Juegos` y `Totales`) filtrando el Campo Minado (`2:0` sobre-comisionado). |

## 2. Ejecución Diaria en Termux (POCO X6 Pro)

```bash
git pull origin main
python3 argon_compounder_v54.py --bankroll 150
```
