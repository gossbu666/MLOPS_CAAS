# 07_Final — Final Deliverables

All final submission artifacts live here. Created 2026-04-09.

```
07_Final/
├── report/                  ← Final report LaTeX + PDF
│   ├── final_report_CAAS.tex
│   ├── sections/            ← One .tex per chapter (modular)
│   │   ├── 01_introduction.tex
│   │   ├── 02_data_engineering.tex
│   │   ├── 03_ml_development.tex
│   │   ├── 04_mlops.tex
│   │   ├── 05_performance_analysis.tex
│   │   ├── 06_conclusion.tex
│   │   ├── 07_references.tex
│   │   └── 08_appendix.tex
│   └── figures/             ← Symlinks or copies of figures from 01_Proposal/
├── slides/                  ← Presentation (10 min + demo)
│   ├── CAAS_final.pptx      ← TO BE CREATED
│   ├── assets/              ← Images, screenshots, logos
│   └── exports/             ← PDF exports of slides for submission
└── video/                   ← Demo recording (required deliverable)
    └── CAAS_demo.mp4        ← TO BE RECORDED
```

## Report structure (per final_ref.md rubric)

Required sections:
1. **Introduction** — problem + significance
2. **Data Engineering** — pipeline design, tools, justification
3. **Machine Learning Model Development** — model, rationale, evaluation
4. **MLOps Implementation** — deployment, monitoring, CI/CD
5. **Performance Analysis** — metrics + scalability + **cost calculation ($/day)**
6. **Conclusion** — findings + future work
7. **References**
8. **Appendix** — step-by-step reproduction guide

## Number authoritative source

**Always pull metrics from these files, NOT from the progress report tables:**
- `../03_Data/results/xgboost_summary.json`
- `../03_Data/results/lstm_summary.json`
- `../03_Data/results/ablation_summary.json`

## Compile instructions

```bash
cd 07_Final/report
pdflatex final_report_CAAS.tex && pdflatex final_report_CAAS.tex
open final_report_CAAS.pdf
```
