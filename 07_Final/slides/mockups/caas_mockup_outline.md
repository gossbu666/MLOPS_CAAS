# Slide 1: LightGBM wins MAE at all three horizons

**Visual: cards-3**

[Card 1: LightGBM]
{blue}Champion{/blue}
- MAE t+1: **5.12**
- MAE t+3: **6.77**
- MAE t+7: **8.25**
- AUROC ≥ 0.946 all horizons

[Card 2: XGBoost]
Strong secondary
- MAE t+1: 5.31
- MAE t+3: 7.08
- MAE t+7: 8.90
- AUROC ≥ 0.933 all horizons

[Card 3: LSTM]
Comparison baseline
- MAE t+1: 6.67
- MAE t+3: 8.87
- MAE t+7: 8.06
- AUROC ≥ 0.927 all horizons

**Chronological split:** train 2011–2022 · val 2023 · test 2024–2025 — no leakage.

---
