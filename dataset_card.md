# Dataset card — EGFR kinase inhibitors dataset

## Dataset title

EGFR Kinase inhibitors dataset (v0.1.0)

## Dataset summary

Tabular collection of experimentally reported small-molecule EGFR kinase inhibitor measurements, capturing exact target mutational status (wild-type and clinically relevant mutants), quantitative bioactivity metrics (IC50, Ki, Kd), assay context, and provenance.

## Scientific task

Support the comparison of inhibitor potencies and selectivities across different EGFR variants. This dataset serves as a benchmark for training machine learning models to predict variant-specific drug efficacy and design-out resistance.

## Record unit

One row = one experimentally reported bioactivity measurement for a unique small molecule tested against a specific human EGFR variant (wild-type or designated mutant) in a defined assay.

## Data sources

Defined in `specs/source_map.json`: journal PDFs, supplementary tables, molecule databases, metadata aggregators, GitHub releases, and optional ML dataset exports (with license review).

## Data extraction procedure

1. PDF: `scripts/extract_pdf.py` guided by `specs/pdf_extraction_manifest.json`
2. Web: `scripts/extract_web.py` guided by `specs/web_extraction_manifest.json`
3. Logs: `data/extracted/extraction_log.jsonl`

## Data cleaning and normalization

`scripts/build_dataset.py` merges extracts; `scripts/clean_dataset.py` normalizes chemical structure representations, converts activity values to standard nanomolar units (to nM), calculates negative log values, handles missing values, deduplicates entries per `specs/cleaning_pipeline.json`.

## Dataset schema

Field definitions, types, and examples: `specs/dataset_schema.json`. Final columns in `data/processed/dataset.csv`.

## Validation

Rules cpecified in `specs/validation_rules.json`; checks via `scripts/validate_project.py` and `tests/test_required_artifacts.py`.

## Known limitations

- Example DOIs and URLs are placeholders.
- Template rows are not verified against live sources.
- Some sources may be paywalled or not redistributable—confirm LICENSE before publication.

## Recommended use

Training regression or classification models to predict compound activity against wild-type or mutated EGFR; exploring kinase-selectivity profiles; benchmarking chemical parsing pipelines.

## Not recommended use

Clinical decision-making; uncritical meta-analysis without re-verifying primary sources; commercial use without license review.

## License

See `LICENSE` — CC-BY-4.0.

## Citation

See `CITATION.cff`.
