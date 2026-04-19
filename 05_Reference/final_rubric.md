# CAAS — Final Project Rubric (AUTHORITATIVE)

> Source: instructor handout for AT82.9002 Data Engineering and MLOps, AIT (2026 cohort).
> This file is the single source of truth for what must be delivered and how it will be graded.
> Verbatim project description is preserved in **§6** below.

**Last saved:** 2026-04-18 (from student-provided rubric text).

---

## 1. Rubric table — who owns each bucket (SP = sub-project from finalization plan)

| # | Criterion | Weight | Covered by | Notes |
|--|--|--:|--|--|
| 1 | **Problem Selection** | 10% | SP8 | Relevance, complexity, real-world applicability. Framing matters — proposal feedback asked us to **position as "integration excellence" not "forecasting novelty"**. |
| 2 | **Data Engineering** | 25% | SP1 | Pipeline design + implementation + efficiency. Ingestion, cleaning, feature engineering, storage, versioning, orchestration. Heaviest bucket. |
| 3 | **Machine Learning Model Development** | 15% | SP7 | Model selection, hyperparameter tuning, training/evaluation, experiment tracking, model versioning. |
| 4 | **MLOps Implementation** | 20% | SP1, SP2, SP3, SP4, SP5 | Deployment as service, CI/CD, monitoring, IaC. Second-heaviest bucket; we have most scaffolding but nothing live yet. |
| 5 | **Project Report** | 10% | SP3, SP5, SP6 + *post-freeze report work* | Clarity, organization, completeness. Required sections listed in §3. |
| 6 | **Impact** | 5% | SP6, SP8 | Impact on real-world DE/MLOps applications. Cost realism + stakeholder analysis live here. |
| 7 | **Presentation & Demos** | 15% | *(frozen until SP1–8 complete)* | Presentation skills + communication + Q&A. **10 minutes presentation + demo, 5 minutes Q&A.** |
| | **Total** | **100%** | | |

---

## 2. Deliverables checklist

| Deliverable | Status | Location |
|--|--|--|
| **Final project report (PDF)** | 🟡 compiled at `07_Final/report/final_report_CAAS.pdf` (33 pp, 2.1 MB) — **frozen until system is finalized** | `07_Final/report/` |
| **Presentation slides** | ❌ only `SLIDES_OUTLINE.md` exists | `07_Final/slides/` |
| **Demo video recording** | ❌ not started | `07_Final/video/` |
| **Source code — data pipeline** | ✅ | `04_Scripts/parse_pm25.py`, `fetch_weather.py`, `fetch_firms.py`, `build_features.py` |
| **Source code — model training** | ✅ | `04_Scripts/train_xgboost.py`, `train_lstm.py`, `train_xgboost_no_firms.py` |
| **Source code — deployment** | ✅ | `04_Scripts/serve/app.py` (FastAPI), `Dockerfile`, `infra/*.tf` |
| **Source code — monitoring / CI / retrain** | ✅ | `04_Scripts/monitoring/evidently_report.py`, `.github/workflows/*.yml`, `validate_candidate.py`, `promote_model.py` |

---

## 3. Required report sections (per handout, verbatim order)

The final report **must** contain these 8 sections. Current status of each in `07_Final/report/sections/`:

1. **Introduction** — problem + significance → [`01_introduction.tex`](../07_Final/report/sections/01_introduction.tex) ✅
2. **Data Engineering** — pipeline design + tool/tech justification → [`02_data_engineering.tex`](../07_Final/report/sections/02_data_engineering.tex) ✅
3. **Machine Learning Model Development** — model + rationale + evaluation results → [`03_ml_development.tex`](../07_Final/report/sections/03_ml_development.tex) ✅
4. **MLOps Implementation** — deployment + monitoring + CI/CD → [`04_mlops.tex`](../07_Final/report/sections/04_mlops.tex) ✅
5. **Performance Analysis** — metrics + scalability analysis + **cost calculation ($/hour or $/day)** → [`05_performance_analysis.tex`](../07_Final/report/sections/05_performance_analysis.tex) ✅
6. **Conclusion** — findings + future work → [`06_conclusion.tex`](../07_Final/report/sections/06_conclusion.tex) ✅
7. **References** → [`07_references.tex`](../07_Final/report/sections/07_references.tex) ✅
8. **Appendix** — steps to create the proposed system → [`08_appendix.tex`](../07_Final/report/sections/08_appendix.tex) ✅

All 8 sections exist in scaffold form. Content accuracy to be verified once SP1–8 are complete and metric/cost data is stable — **no prose edits until the system freeze lifts**.

---

## 4. Per-area detailed requirements

### 4.1 Data Engineering (25%)
Required aspects:
- Data ingestion from various sources (APIs, databases, cloud storage)
- Data cleaning and preprocessing (missing values, outlier detection, feature engineering)
- Data transformation and aggregation
- Data storage and versioning
- Pipeline orchestration and scheduling

Tools suggested: Apache Spark, Apache Airflow, dbt, cloud data warehousing.
**CAAS stack:** Python scripts + GitHub Actions (no Spark/Airflow/dbt — documented tradeoff in report).

### 4.2 ML Model Development (15%)
Required aspects:
- Model selection and hyperparameter tuning
- Model training and evaluation
- Experiment tracking and model versioning (MLflow, W&B, etc.)

**CAAS stack:** XGBoost (champion) + LSTM (comparison) + MLflow local backend. **Gap: hyperparameter tuning evidence (Optuna run logs), LSTM t+3/t+7 still weak — SP7 addresses both.**

### 4.3 MLOps Implementation (20%)
Required aspects:
- Model deployment as a service (Flask, FastAPI, cloud serving)
- CI/CD pipelines
- Model monitoring and performance tracking
- Infrastructure as code (IaC)

**CAAS stack:** FastAPI on Docker on EC2, GitHub Actions (4 workflows), Evidently drift monitoring, Terraform (S3+EC2+IAM). **Gap: nothing is actually deployed or has fired live yet — SP1 + SP2 address this.**

### 4.4 Impact (5%)
Required: impact of project on real-world DE/MLOps applications. **Novelty framing matters** per proposal feedback.

### 4.5 Presentation (15%)
- **10 minutes** presentation + demo
- **5 minutes** Q&A
- Graded on presentation skills, communication, Q&A quality
- **Address all comments received during progress report** (see `07_Final/FEEDBACK_FROM_PROPOSAL.md`)

---

## 5. Sub-project → rubric mapping (our 8-SP plan against the rubric)

Cross-reference for at-a-glance sanity check:

| SP | Name | Primary rubric bucket(s) | Secondary |
|--|--|--|--|
| 1 | AWS Foundation | DE 25%, MLOps 20% | — |
| 2 | CI/CD Live Runs | MLOps 20% | — |
| 3 | Test Hardening + Coverage | MLOps 20% | Report 10% |
| 4 | Drift/Retrain Technical | MLOps 20% | — |
| 5 | Security + Reproducibility | MLOps 20% | Report 10% |
| 6 | System Polish + Cleanup | Report 10% | Impact 5% |
| 7 | ML Model Quality | ML 15% | — |
| 8 | Business + Impact + Cost Realism | Problem 10%, Impact 5% | MLOps 20% *(cost realism claim)* |
| — | *Report edits (frozen)* | Report 10% | — |
| — | *Slides + Video (frozen)* | Presentation 15% | — |

**Rubric coverage after SP1–8:** 85% (100% minus 15% frozen Presentation bucket). Presentation unfreezes once SP1–8 complete.

---

## 6. Verbatim Project Description (from instructor handout)

> This project challenges you to apply the principles of data engineering and MLOps to build and deploy a robust and scalable machine learning pipeline. You will be responsible for selecting a real-world problem, designing and implementing a data pipeline to acquire, process, and prepare data, training a machine learning model, and deploying and monitoring the model in a production-like environment. This project emphasizes not only the performance of the model but also the reliability, maintainability, and scalability of the entire pipeline. The goal is to demonstrate a deep understanding of data engineering principles, machine learning model development, and MLOps best practices.

### Project Requirements (verbatim)

**Problem Selection:** Choose a real-world problem that is interesting, challenging, and relevant to the concepts covered in this course. The problem should be substantial enough to require the design and implementation of a non-trivial data pipeline and machine learning model. Consider problems from areas like:
- Predictive analytics
- Natural language processing
- Computer vision
- Recommender systems
- Time series analysis

> You are encouraged to explore publicly available datasets or open-source projects for inspiration, but the implementation and analysis must be your own work. If you are unsure about the suitability of a problem, please consult with the instructor.

**Data Engineering:** Design and implement a data pipeline to acquire, process, and prepare data for model training. This may involve:
- Data ingestion from various sources (e.g., APIs, databases, cloud storage).
- Data cleaning and preprocessing (e.g., handling missing values, outlier detection, feature engineering).
- Data transformation and aggregation.
- Data storage and versioning.
- Pipeline orchestration and scheduling.

Consider using appropriate data engineering tools and technologies (e.g., Apache Spark, Apache Airflow, dbt, cloud-based data warehousing solutions).

**Machine Learning Model Development:** Train a machine learning model to address the chosen problem. This should include:
- Model selection and hyperparameter tuning.
- Model training and evaluation.
- Experiment tracking and model versioning (e.g., using MLflow, Weights & Biases).

**MLOps Implementation:** Implement MLOps best practices to deploy and monitor the trained model. This may involve:
- Model deployment as a service (e.g., using Flask, FastAPI, cloud-based model serving solutions).
- Continuous integration and continuous delivery (CI/CD) pipelines.
- Model monitoring and performance tracking.
- Infrastructure as code (IaC).

**Project Report:** Prepare a comprehensive project report that includes the following sections:
- Introduction — clearly describe the problem you have chosen and its significance.
- Data Engineering — detail the data pipeline you have designed and implemented, justifying your choices of tools and technologies.
- Machine Learning Model Development — explain the model you have trained, including the rationale for your choices and the evaluation results.
- MLOps Implementation — describe the MLOps practices you have implemented, including deployment, monitoring, and CI/CD.
- Performance Analysis — present the performance of your model and pipeline, including metrics and scalability analysis. **Add cost calculation in your proposed system (cost per hour or cost per day is fine).**
- Conclusion — summarize your findings and discuss any future work.
- References — list any resources you have consulted.
- Appendix — show steps to create your proposed system.

**Deliverables:**
- Final project report and presentation slide.
- Source code (including data pipeline, model training, and deployment scripts).

### Grading Rubric (verbatim)

- **Problem Selection (10%):** Relevance, complexity, and real-world applicability of the chosen problem.
- **Data Engineering (25%):** Design, implementation, and efficiency of the data pipeline.
- **Machine Learning Model Development (15%):** Model performance, selection, and training methodology.
- **MLOps Implementation (20%):** Adherence to MLOps best practices, including deployment, monitoring, and CI/CD.
- **Project Report (10%):** Clarity, organization, and completeness of the report.
- **Impact (5%):** Impact of your project to real-world applications in DE and MLOPS.
- **Presentation and demos (15%):** Presentation skills, communications skill. Q&A.
