# PHASE 13 — HISTORICAL PERFORMANCE AND MODEL ANALYTICS

## 1. Overview & Data Grounding

This document outlines the evaluation methodology, empirical formulas, and measured performance metrics comparing the **Deterministic Baseline ETA** model against the **XGBoost Dynamic Railway ETA Predictor**.

### Fundamental Directives
1. **ZERO FABRICATION**: All performance statistics are parsed directly from serialized model validation logs (`models/model_metadata.json`), section profiles (`models/section_profiles.json`), and authentic historical train observations (`data/historical_train_runs.csv`).
2. **OUT-OF-TIME CHRONOLOGICAL SPLIT**: To guard against data leakage and simulate real deployment conditions, models were validated on chronologically held-out train runs ($80\%$ train, $20\%$ test).
3. **NO VISUAL OVERLOAD**: Restrained, clear comparison tables and structured proportional indicators are used instead of decorative SaaS dashboard widgets.

---

## 2. Evaluation Metrics & Formulation

Let $y_i$ be the actual measured remaining travel time to station $i$, and $\hat{y}_i$ be the predicted remaining travel time.

### 1. Mean Absolute Error (MAE)
Measures the average magnitude of arrival forecasting errors in minutes:
$$\text{MAE} = \frac{1}{N} \sum_{i=1}^N \left| y_i - \hat{y}_i \right|$$

### 2. Root Mean Squared Error (RMSE)
Heavily penalizes large forecasting misses or outlier disruptions:
$$\text{RMSE} = \sqrt{\frac{1}{N} \sum_{i=1}^N \left( y_i - \hat{y}_i \right)^2}$$

### 3. Precision Tolerance Windows ($\pm 5\text{m}$, $\pm 10\text{m}$, $\pm 15\text{m}$)
Measures the percentage of station arrival forecasts falling within operational punctuality windows:
$$\text{Accuracy}_{\pm K} = \frac{1}{N} \sum_{i=1}^N \mathbb{I}\left( \left| y_i - \hat{y}_i \right| \le K \right) \times 100\%$$
where $K \in \{5, 10, 15\}$ minutes.

### 4. Coefficient of Determination ($R^2$)
Measures the proportion of travel time variance explained by the model:
$$R^2 = 1 - \frac{\sum_{i=1}^N (y_i - \hat{y}_i)^2}{\sum_{i=1}^N (y_i - \bar{y})^2}$$

---

## 3. Measured Empirical Comparison: Baseline vs. XGBoost ML

| Metric | Deterministic Baseline | XGBoost Dynamic ML | Operational Gain / Variance |
| :--- | :---: | :---: | :---: |
| **MAE** | $6.35\text{ min}$ | **$2.69\text{ min}$** | **$-3.66\text{ min}$ ($-57.6\%$)** |
| **RMSE** | $7.98\text{ min}$ | **$3.51\text{ min}$** | **$-4.47\text{ min}$ ($-56.0\%$)** |
| **$\pm 5$ min Accuracy** | $48.9\%$ | **$83.6\%$** | **$+34.7\%$ precision gain** |
| **$\pm 10$ min Accuracy** | $74.3\%$ | **$99.3\%$** | **$+25.0\%$ precision gain** |
| **$\pm 15$ min Accuracy** | $94.3\%$ | **$100.0\%$** | **$+5.7\%$ precision gain** |
| **$R^2$ Score** | $0.9989$ | **$0.9998$** | $+0.0009$ |

*Evaluated on $N = 280$ holdout validation station-pair observations across coaching trains $12302$, $12952$, and $22436$.*

---

## 4. Sectional Performance & Recovery Tendency Formulation

For every block section between station $A$ and station $B$:

1. **Average Running Time ($\mu_{\text{run}}$)**:
   $$\mu_{\text{run}} = \frac{1}{M} \sum_{j=1}^M \left( t_{\text{actual\_arrival}, B} - t_{\text{actual\_departure}, A} \right)$$
2. **Average Delay ($\mu_{\text{delay}}$)**:
   $$\mu_{\text{delay}} = \frac{1}{M} \sum_{j=1}^M \left( t_{\text{actual\_arrival}, B} - t_{\text{scheduled\_arrival}, B} \right)$$
3. **Delay Variance ($\sigma^2_{\text{delay}}$)**:
   Unbiased sample variance measuring operational volatility across the block section:
   $$\sigma^2_{\text{delay}} = \frac{1}{M - 1} \sum_{j=1}^M \left( \text{delay}_j - \mu_{\text{delay}} \right)^2$$
4. **Recovery Tendency ($\Delta_{\text{recovery}}$)**:
   Measures whether trains systematically make up time or lose time across the section:
   $$\Delta_{\text{recovery}} = \frac{1}{M} \sum_{j=1}^M \left( \text{departure\_delay}_{A, j} - \text{arrival\_delay}_{B, j} \right)$$
   - **Positive ($\Delta_{\text{recovery}} > +0.5\text{m}$)**: **Slack Recovery Zone** (e.g. `CNB->PRYJ` $+2.19\text{m}$, `DHN->ASN` $+2.01\text{m}$).
   - **Negative ($\Delta_{\text{recovery}} < -0.5\text{m}$)**: **Bottleneck / Congested Block** (e.g. `NDLS->CNB` $-4.25\text{m}$, `PRYJ->DDU` $-3.69\text{m}$).
   - **Neutral**: $|\Delta_{\text{recovery}}| \le 0.5\text{m}$.

---

## 5. Measured Sectional Performance Table

| Track Block Section | Samples | Avg Running Time | Avg Delay | Delay Variance ($\sigma^2$) | Recovery Tendency | Section Characteristic |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **NDLS &rarr; CNB** | 70 | $265.8\text{ min}$ | $+8.2\text{ min}$ | $23.1\text{ min}^2$ | **$-4.25\text{ min}$** | **Bottleneck / Congested** |
| **CNB &rarr; PRYJ** | 70 | $120.8\text{ min}$ | $+6.8\text{ min}$ | $21.7\text{ min}^2$ | **$+2.19\text{ min}$** | **Slack Recovery Zone** |
| **PRYJ &rarr; DDU** | 35 | $63.7\text{ min}$ | $+10.9\text{ min}$ | $34.7\text{ min}^2$ | **$-3.69\text{ min}$** | **Bottleneck / Congested** |
| **DDU &rarr; GAYA** | 35 | $134.7\text{ min}$ | $+11.0\text{ min}$ | $33.5\text{ min}^2$ | $+0.35\text{ min}$ | Neutral Section |
| **GAYA &rarr; DHN** | 35 | $160.4\text{ min}$ | $+9.6\text{ min}$ | $36.5\text{ min}^2$ | **$+1.63\text{ min}$** | **Slack Recovery Zone** |
| **DHN &rarr; ASN** | 35 | $52.0\text{ min}$ | $+8.4\text{ min}$ | $45.1\text{ min}^2$ | **$+2.01\text{ min}$** | **Slack Recovery Zone** |
| **ASN &rarr; HWH** | 35 | $178.6\text{ min}$ | $+8.9\text{ min}$ | $43.1\text{ min}^2$ | $+0.36\text{ min}$ | Neutral Section |
| **NDLS &rarr; KOTA** | 35 | $275.5\text{ min}$ | $+3.2\text{ min}$ | $12.3\text{ min}^2$ | $-0.53\text{ min}$ | Neutral Section |
| **KOTA &rarr; BRC** | 35 | $360.4\text{ min}$ | $+4.2\text{ min}$ | $11.8\text{ min}^2$ | $-0.38\text{ min}$ | Neutral Section |
| **BRC &rarr; MMCT** | 35 | $284.9\text{ min}$ | $+4.7\text{ min}$ | $13.8\text{ min}^2$ | $+0.12\text{ min}$ | Neutral Section |
| **PRYJ &rarr; BSB** | 35 | $109.6\text{ min}$ | $+7.3\text{ min}$ | $20.7\text{ min}^2$ | $+0.37\text{ min}$ | Neutral Section |

---

## 6. API Integration

### Endpoint: `GET /api/trains/analytics/model-performance`
Serves structured JSON conforming to `ModelAnalyticsResponse` schema with zero fabricated values. Tested via unit/integration suite in `tests/test_analytics.py`.
