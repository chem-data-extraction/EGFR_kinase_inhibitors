#!/usr/bin/env python3
"""Merge extracted CSVs and write interim and processed datasets for EGFR inhibitors."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

PDF_CSV = ROOT / "data/extracted/pdf_extracted_records.csv"
WEB_CSV = ROOT / "data/extracted/web_extracted_records.csv"
SCHEMA_PATH = ROOT / "specs/dataset_schema.json"
MERGED_PATH = ROOT / "data/interim/merged_records.csv"
DATASET_PATH = ROOT / "data/processed/dataset.csv"


def load_schema_columns() -> list[str]:
    with SCHEMA_PATH.open(encoding="utf-8") as f:
        schema = json.load(f)
    return [field["name"] for field in schema["fields"]]


def map_pdf_row(row: pd.Series, idx: int) -> dict:
    name = str(row.get("compound_name", ""))
    
    if re.match(r'^(9|10)[a-o]$', name):
        confidence = 'low'
    else:
        confidence = 'medium'

    pdf_variant_mapping = {
        'del19': 'delE746_A750',
        'del19/C797S': 'C797S_delE746_A750',
        'L858R/T790M': 'L858R_T790M',
        'L858R/T790M/C797S': 'C797S_L858R_T790M',
        'del19/T790M': 'T790M_delE746_A750',
        'del19/T790M/C797S': 'C797S_T790M_delE746_A750'
    }
    raw_variant = str(row.get("egfr_variant", ""))
    mapped_variant = pdf_variant_mapping.get(raw_variant, raw_variant)
    if pd.notna(mapped_variant) and mapped_variant != "nan":
        mapped_variant = str(mapped_variant).replace('/', '_')
    else:
        mapped_variant = None

    return {
        "record_id": f"paper_{idx + 1}",
        "compound_id": f"paper_{idx + 1}",
        "compound_name": row.get("compound_name"),
        "compound_smiles": row.get("compound_smiles"),
        "egfr_variant": mapped_variant,
        "standard_type": row.get("standard_type"),
        "standard_relation": row.get("standard_relation"),
        "standard_value": row.get("standard_value"),
        "standard_units": row.get("standard_units"),
        "pchembl_value": None,  # Will be calculated during the cleaning step
        "assay_type": row.get("assay_type"),
        "cell_line": row.get("cell_line"),
        "atp_concentration_uM": row.get("atp_concentration_uM"),
        "covalent_flag": row.get("covalent_flag", False),
        "source_id": row.get("source_id", "paper_lim_2023"),
        "extraction_method": "pdf_parsing",
        "extraction_confidence": confidence,
        "notes": row.get("notes"),
        "inchikey": None,  # Will be calculated during the cleaning step
    }


def map_web_row(row: pd.Series) -> dict:
    return {
        "record_id": row.get("record_id"),
        "compound_id": row.get("compound_id"),
        "compound_name": row.get("compound_name"),
        "compound_smiles": row.get("compound_smiles"),
        "egfr_variant": row.get("egfr_variant"),
        "standard_type": row.get("standard_type"),
        "standard_relation": row.get("standard_relation"),
        "standard_value": row.get("standard_value"),
        "standard_units": row.get("standard_units"),
        "pchembl_value": row.get("pchembl_value"),
        "assay_type": row.get("assay_type"),
        "cell_line": row.get("cell_line"),
        "atp_concentration_uM": row.get("atp_concentration_uM"),
        "covalent_flag": row.get("covalent_flag", False),
        "source_id": row.get("source_id"),
        "extraction_method": "web_scrape",
        "extraction_confidence": row.get("extraction_confidence", "high"),
        "notes": row.get("notes"),
        "inchikey": None,  # Will be calculated during the cleaning step
    }


def build() -> pd.DataFrame:
    if not PDF_CSV.is_file():
        raise FileNotFoundError(f"Missing PDF raw data at: {PDF_CSV}")
    if not WEB_CSV.is_file():
        raise FileNotFoundError(f"Missing Web raw data at: {WEB_CSV}")

    pdf_df = pd.read_csv(PDF_CSV, low_memory=False)
    web_df = pd.read_csv(WEB_CSV, low_memory=False)

    print(f"Loading {len(pdf_df)} rows from PDF extraction...")
    print(f"Loading {len(web_df)} rows from Web extraction...")

    rows = [map_pdf_row(r, idx) for idx, r in pdf_df.iterrows()]
    rows += [map_web_row(r) for _, r in web_df.iterrows()]

    columns = load_schema_columns()
    return pd.DataFrame(rows, columns=columns)


def main() -> None:
    MERGED_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)

    print("Building raw merged dataset...")
    df = build()
    df.to_csv(MERGED_PATH, index=False)
    # Save a copy as placeholder for procesed dataset (will be overwritten by clean_dataset.py)
    df.to_csv(DATASET_PATH, index=False)

    print(f"Wrote {len(df)} merged rows to {MERGED_PATH.relative_to(ROOT)}")
    print(f"Wrote {len(df)} initial rows to {DATASET_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
