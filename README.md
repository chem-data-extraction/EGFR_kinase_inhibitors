# EGFR kinase inhibitors

Publication-ready **dataset** for the course *Extraction and preparation of chemical information*.

## Scientific task

Collect and standardize experimentally reported bioactivity measurements of small-molecule inhibitors tested against wild-type and mutant human EGFR variants from literature and database sources to build a robust benchmark for variant-specific activity prediction.

## What is one record?

One **record** = one quantitative experimental measurement (IC50, Ki, Kd) for a unique small-molecule structure against a specific human EGFR mutational variant in a defined assay (one row in `data/processed/dataset.csv`). See `project.json` and `reports/practice_01_record_and_schema.md`.

## Repository structure

| Path | Role |
|------|------|
| `project.json` | Machine-readable project metadata |
| `specs/` | JSON schemas, source map, manifests, pipeline, validation rules |
| `data/raw/` | Unmodified PDFs, web snapshots, external exports |
| `data/extracted/` | Extraction outputs (CSV + `extraction_log.jsonl`) |
| `data/interim/` | Merged table before final cleaning |
| `data/processed/` | Publication dataset (`dataset.csv`) |
| `scripts/` | Reproducible extract, build, clean, validate |
| `reports/` | Human-readable practice and final reports |
| `notebooks/` | Optional exploration only |
| `tests/` | Pytest checks for required artifacts |

**Formats:** JSON for specs and manifests; CSV for tabular data; Python for pipelines; Markdown for reports and documentation only. Notebooks are optional.

## Five course practices

Develop the repository in five steps (see `reports/`):

1. **Record definition and dataset schema** — `specs/dataset_schema.json`, Practice 1 report  
2. **Source map** — `specs/source_map.json`, Practice 2 report  
3. **PDF extraction** — `specs/pdf_extraction_manifest.json`, `scripts/extract_pdf.py`, Practice 3 report  
4. **Web extraction** — `specs/web_extraction_manifest.json`, `scripts/extract_web.py`, Practice 4 report  
5. **Cleaning, normalization and publication** — `specs/cleaning_pipeline.json`, cleaning scripts, Practice 5 report  

Complete **`reports/final_report.md`** and **`dataset_card.md`** before submission.

## Data pipeline

```text
raw (PDF / web / external)
  → extract (pdf + web scripts) → data/extracted/*.csv
  → build (merge) → data/interim/merged_records.csv
  → clean → data/processed/dataset.csv
  → validate (rules + pytest)
```

## Required final artifacts

- `data/processed/dataset.csv` aligned with `specs/dataset_schema.json`
- Updated `specs/source_map.json` and extraction manifests
- Practice reports 1–5 and `reports/final_report.md`
- `dataset_card.md`, `LICENSE`, `CITATION.cff`
- Passing validation and tests

## How to run validation

```bash
pip install -r requirements.txt
python scripts/validate_project.py
pytest
```

## How to build the dataset

```bash
python scripts/build_dataset.py    # merge extracts → interim + processed
python scripts/clean_dataset.py    # normalize and write processed dataset
```

Placeholder extraction (no PDF/HTML libraries required):

```bash
python scripts/extract_pdf.py
python scripts/extract_web.py
```

## License and citation

- Replace the placeholder in **`LICENSE`** before publication (e.g. CC-BY-4.0 or CC0-1.0, subject to upstream source licenses).
- Fill in **`CITATION.cff`** with authors, version, and repository URL.
- Summarize the dataset for users in **`dataset_card.md`**.
