Strengths
Clear and important problem framing: the proposal is well motivated by Chiang Mai’s recurring PM2.5 crisis and the need for a predictive early-warning system, not just reactive reporting.
Strong end-to-end architecture: the pipeline is one of the best parts, with Lambda ingestion, multi-tier S3 storage, MLflow, FastAPI, Streamlit, and Evidently AI organized into a coherent production-style workflow.
Good feature engineering design: build a fairly rich 44-feature dataset using PM2.5 history, rolling statistics, seasonality, weather, regional PM2.5, and NASA FIRMS hotspots.
Reasonable modeling plan: comparing XGBoost and LSTM is sensible, and the strict chronological split (2011–2022 / 2023 / 2024–2025) is appropriate for time-series forecasting.
Good MLOps awareness: the project includes validation, deployment, prediction serving, drift monitoring, and retraining logic, which fits the course well.
Weaknesses
Innovation is moderate rather than outstanding: the project is strongest as a well-integrated operational system, not as a novel forecasting method. The main models are standard choices.
Monitoring/retraining plan is not fully tight yet: the slides and report are not perfectly aligned on drift detection and retraining logic, with mentions of PSI, KS test, and rolling error thresholds not always presented consistently.
Some feasibility details are inconsistent: the monthly cost estimate differs between report and slides, and there is also inconsistency in the stated data source description.
Evaluation is good but not fully rigorous: include useful baselines and separate horizons (t+1 / t+3 / t+7), but the operational validation plan still feels less settled than the system architecture.
Always-on components may challenge the low-cost claim: FastAPI, Streamlit, MLflow, and Evidently AI make the deployment story somewhat heavier than the very low monthly budget suggests.
Recommendations
Unify the drift/retraining story: clearly define which signals actually trigger retraining, over what window, and how a new model is validated before promotion.
Resolve inconsistencies across report and slides: align the stated data source, monthly cost, and monitoring logic so the proposal feels fully settled.
Reframe the contribution accurately: present it as a strong production-oriented PM2.5 forecasting and alerting system, rather than implying major methodological novelty.
Strengthen the evaluation plan: make the alert validation and retraining criteria more concrete for each forecast horizon, not only the predictive metrics.
Clarify cost realism: explain how the low-cost target is maintained despite the always-on serving and monitoring components.
Github Action: What are the exact GitHub Actions stages in the retraining workflow—data snapshot, feature build, model training, validation, MLflow registration, and deployment—and which step can block promotion?. Also, any charge?