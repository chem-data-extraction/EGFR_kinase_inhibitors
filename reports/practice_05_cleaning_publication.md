# Practice 5 — Cleaning, normalization and publication

## Input files

- `data/extracted/pdf_extracted_records.csv` — Raw dataset extracted from literature (140 rows)
- `data/extracted/web_extracted_records.csv` — Scraped dataset from databases (107,420 rows)
- `data/extracted/zenodo_extracted_records.csv` — Optional dataset downloaded from Zenodo (4899 rows)
- `data/interim/merged_records.csv` — Raw consolidated interim dataset containing all combined records before filtering (107,560 rows)

## Cleaning steps

The cleaning process was executed step-by-step according to the defined `specs/cleaning_pipeline.json`:

1. **Merge Sources (`merge_sources`)**: Combined PDF and Web extraction tables into a single raw interim table. During the merge, PDF paper records were assigned standardized sequential identifiers (`paper_1`, `paper_2`, etc.) to prevent key collisions with database IDs.
2. **Resolve PDF Structures (`resolve_pdf_structures`)**: Mapped short literature codes (e.g., `9a`, `10b`) from paper tables to complete IUPAC names. The IUPAC names were then programmatically converted to SMILES structures using the OPSIN API.
3. **Primary Garbage Collection (`primary_garbage_collection`)**: Removed non-informative rows. Records missing all crucial biological activity variables (`standard_value`, `standard_type`, and `standard_units`) or lacking both chemical name and structure were permanently excluded from the pipeline.
4. **Normalize Activity and Units (`normalize_activity_and_units`)**: Filtered and retained only comparable activity types: `IC50`, `Ki`, `Kd`, and `EC50`. Parsed inequality operators embedded within value strings (e.g., `>10000`) and mapped all relations to standardized symbols (`=`, `>`, `<`, `>=`, `<=`). All concentration metrics were converted into nanomolar (`nM`) units.
5. **Extract Assay Parameters (`extract_assay_parameters`)**: Extracted structured experiment details from the unstructured `notes` text. This step populated the `egfr_variant`, `assay_type`, `cell_line`, `atp_concentration_uM`, and `covalent_flag` columns, keeping existing valid entries unchanged as a fallback.
6. **Chemical Structure Canonicalization (`canonicalize_chemical_structures`)**: Utilized RDKit to standardise compound structures. Removed counter-ions and salt residues (desalting), converted structures into canonical isomeric SMILES to preserve stereocenters, and computed stable 2D `inchikey` identifiers. 
7. **Calculate pChEMBL Scales (`calculate_pchembl_scales`)**: Converted nanomolar concentrations into logarithmic scale values ($pChEMBL = 9.0 - \log_{10}(\text{Value in nM})$) for regression modeling.
8. **Consensus Deduplication (`consensus_deduplication`)**: Applied chemical-biological consensus deduplication. Duplicate records were grouped, evaluated for experimental variance, and consolidated or dropped.
9. **Export Final Dataset (`export_final_dataset`)**: Aligned the columns to strictly match `specs/dataset_schema.json` and saved the clean benchmark dataset.

## Normalization rules

### 1. Unit to nM Conversion
* **`nM`**: Multiplied by $1.0$ (remains unchanged).
* **`uM` / `μM` / `µM`**: Multiplied by $1000.0$.
* **`10^3 uM`** (Millimolar): Multiplied by $1\ 000\ 000.0$.
* **`10^-5 mol/L`**: Multiplied by $10\ 000.0$.
* **`10^-2M`**: Multiplied by $10\ 000\ 000.0$.
* **`ug.mL-1`** (Mass concentration): Converted to molar concentration via molecular weight (MW) calculated directly from the molecule's SMILES string using RDKit:
$$\text{Value in nM} = \left(\frac{\text{Value in } \mu\text{g/mL}}{\text{MW in g/mol}}\right) \times 1\ 000\ 000.0$$

### 2. Missing-Value Tokens
Any text strings matching `{"", "na", "n/a", "none", "null", "-", "nan", "unknown"}` (case-insensitive) were mapped to proper Python `None` / `np.nan` values.

## Deduplication strategy

* **Contextual Grouping Keys**: Duplicates were defined as rows sharing the identical combination of:
  `['inchikey', 'egfr_variant', 'assay_type', 'standard_units']`
* **Consensus Deduplication**: Duplicate records were grouped by their unique combination of `['inchikey', 'egfr_variant', 'assay_type', 'standard_units']`. Duplicate records were consolidated into a single row with the following fields:
  * `standard_value`: The median of the values of all duplicates.
  * `standard_type`: The median of the types of all duplicates.
  * `standard_units`: The median of the units of all duplicates.
  * `standard_relation`: The median of the relations of all duplicates.
* **Handling Censored Records**: Exact measurements (relation `=` or `~`) were prioritized over inequalities. Censored records (e.g. `>`) were preserved only if no exact biological measurements existed for the compound-variant-assay triad.
* **Resolution of Lab Variance**:
  * For groups with a $pChEMBL$ span $\le 1.0$ log unit (within a 10-fold concentration range), duplicates were consolidated by taking the **median** of their values, and their respective source IDs were combined using a semicolon (`;`).
  * For groups with a $pChEMBL$ span $> 1.0$ log unit, the conflict was deemed an experimental discrepancy, and the entire group was **fully excluded** from the final benchmark dataset.

## Validation results

Executing `scripts/validate_project.py` yields the following outcome:

* **Errors**: $0$
* **Warnings**: $0$
* **Result**: `Validation passed.` 
All required files exist, all JSON configurations parse without errors, column counts and naming conventions strictly match the schema, identifiers are unique, and chemical structures have been structurally validated as RDKit-compatible SMILES.

## Final dataset description

* **Row count**: $6,334$ fully cleaned, consolidated, and validated records.
* **Targets covered**: Wild-type EGFR (`WT`) alongside multiple clinical mutants, including but not limited to:
  * `delE746_A750` (Exon 19 deletion)
  * `L858R_T790M` (Double mutant)
  * `C797S_L858R` (Double mutant)
  * `C797S_L858R_T790M` (Triple mutant)
  * `C797S_T790M_delE746_A750` (Triple mutant)
  * `A750P` (Single mutant)
* **Date built**: May 2026
* **Dataset path**: `data/processed/dataset.csv`

## Publication readiness checklist

- [x] `dataset.csv` matches `specs/dataset_schema.json`
- [x] All `source_id` values documented in source map
- [x] LICENSE replaced (not placeholder)
- [x] `CITATION.cff` completed
- [x] `dataset_card.md` updated
- [x] `reports/final_report.md` complete