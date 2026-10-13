# OMEGA-QUANT v30 APEX | Quantitative Tennis Engine & Scout

Motor analítico cuantitativo forense para tenis profesional (ATP, WTA, Challenger, ITF) optimizado para ejecución en **Termux (Android / Poco X6 Pro)** y calibrado con el **Scout & Oráculo de Gemini**.

---

## ⚡ Características Principales

1. **Inferencia Bayesiana Jerárquica:** Contracción empírica de saque y resto ($K=1200$) sobre datasets históricos de Jeff Sackmann (2022-2026).
2. **Descomposición Atómica de ADN:**
   - 1st In, 1st Won, 2nd Won, Ace rate, Double Faults.
   - Regresión a la media de puntos de quiebre (*Break Point Leverage / Anti-Luck*).
3. **Scouting Táctico Dinámico (`tactical_matchup`):**
   - Choque de estilos: *Sacador agresivo* vs. *Contragolpeador/Defensa*.
   - Penalización de volatilidad emocional y fragilidad de servicio en circuito femenino (WTA).
4. **Matriz Knottenbelt de Oponentes Comunes:** Comparación indirecta ponderada entre jugadores.
5. **Balística y Termodinámica (Gay-Lussac):**
   - Altura de pista, temperatura y arrastre (*drag*) con OpenWeatherMap y fallback barométrico offline.
6. **Resolución Analítica de Markov:**
   - Probabilidades exactas de Hold, Tiebreaks y matrices de sets (Bo3 y Bo5).
7. **Desviggeo de Mercado Shin (1992):**
   - Extracción de probabilidad justa (*Fair Odds*) a partir de Pinnacle calculando el factor de dinero informado ($z$).
8. **Detección Multi-Mercado y Gestión Quarter-Kelly:**
   - Detección de Valor (+EV > 3.0%) en Moneyline, Totales de juegos, Sets exactos y Combos bivariados.
   - Asignación de stakes enteros (*Integer Stakes*) con tope estricto de bankroll del 4.0%.

---

## 🚀 Guía de Ejecución en Termux

### 1. Clonar el repositorio
```bash
git clone https://github.com/tororex250-ship-it/mi-proyecto-n8n.git
cd mi-proyecto-n8n
```

### 2. Instalar dependencias
```bash
pkg install python -y
pip install numpy rapidfuzz requests
```

### 3. Extraer el dataset de tenis
Asegúrate de que la carpeta de datos `tennis_modern` esté en tu `$HOME` o en el directorio del proyecto:
```bash
unzip tennis_modern.zip -d $HOME/tennis_modern/
```

### 4. Ejecutar el análisis
Con archivo JSON:
```bash
python3 omega_v30_apex.py input_ejemplo.json
```

O directamente mediante stdin desde el bloque generado por la **Gem Scout & Oracle**:
```bash
cat > input.json << 'EOF'
{
  "event": { ... },
  "market_lines": { ... },
  "bankroll": 150.0
}
EOF
python3 omega_v30_apex.py input.json
```

---

## 📊 Formato Visual de Salida
Diseñado a **42 columnas de ancho** con códigos de color ANSI para ajuste a la pantalla de terminal móvil del Poco X6 Pro sin desbordamiento horizontal.
