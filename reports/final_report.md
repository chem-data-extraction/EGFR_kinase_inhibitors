# Final report

## Project summary

* **Project Title**: EGFR Kinase Inhibitors Bioactivity Benchmark Dataset
* **Authors**: Litvinova Viktoria
* **Version**: 0.1.0
* **Scope**: A curated, chemical-biological benchmark dataset of small-molecule inhibitors targeting wild-type and mutant forms of the Epidermal Growth Factor Receptor (EGFR / ErbB1). It integrates raw data from major public web databases with manually parsed structural data from publications.
* **License**: CC-BY-SA 4.0

## Dataset goal

### Scientific Question:
How do structural modifications in small-molecule inhibitors correlate with their selectivity and potency profiles across wild-type EGFR and its various clinical drug-resistance mutants (e.g., L858R, T790M, C797S, and Exon 19 deletions)?

### Intended Audience:
This benchmark dataset is designed for:
1. **Computational Chemists and ML Researchers**: To train, validate, and benchmark Quantitative Structure-Activity Relationship (QSAR) models, multi-task deep neural networks, and graph neural network (GNN) architectures for mutation-specific drug discovery.
2. **Medicinal Chemists**: To study structural activity landscapes and design strategies targeting resistant EGFR mutations.

## Source summary

### Source Count by Group:
* **Web Databases**: 3 primary databases (ChEMBL API, PubChem API, and BindingDB) providing a massive foundation of raw experimental assays.
* **Scientific Literature**: 3 publications (represented by manual extractions, e.g., Lim et al., 2023) to capture recent, structurally complex, and literature-exclusive clinical candidates.

### Key Papers and Databases:
* **ChEMBL**: Target ID `CHEMBL203` (EGFR) and related mutant target cards.
* **Lim et al., 2023**: Provided highly detailed, therapeutic third- and fourth-generation covalent EGFR inhibitors with complex peptide-like structures.

### License Overview:
The processed dataset is distributed under the **Creative Commons Attribution 4.0 International (CC-BY 4.0)** license, ensuring open-access, reproducibility, and unrestricted academic and commercial reuse.

## Extraction summary

### PDF Literature Extraction:
* **Methods**: Manual parsing of bioactivity tables, OCR extraction of mutant variants, and semi-automated conversion of internal compound short-codes (e.g., `9a`, `10b`) to complete IUPAC strings. 
* **Record Count**: 140 raw records.
* **Main Issues**: Paper-specific structural codes, inconsistent naming of mutations, and sparse reporting of physical assay conditions.
* **Reference Report**: [Practice 3 PDF Extraction Report](https://github.com/chem-data-extraction/EGFR_kinase_inhibitors/blob/main/reports/practice_03_pdf_extraction.md)

### Web Scraped Extraction:
* **Methods**: REST API queries extracting bioactivity parameters, relationships, target classifications, and structural SMILES from the ChEMBL database.
* **Record Count**: 107,420 raw records.
* **Main Issues**: Incomplete mutation information, experiment data hidden in notes, and assay type ambiguity.
* **Reference Report**: [Practice 4 Web Extraction Report](https://github.com/chem-data-extraction/EGFR_kinase_inhibitors/blob/main/reports/practice_04_web_extraction.md)

## Cleaning and normalization summary

A programmatic pipeline was applied via `scripts/clean_dataset.py` to convert raw records (107,560 combined rows) into a clean, model-ready format:

1. **Short-code Resolution**: Resolved short PDF paper codes to complete SMILES via local mappings or the Opsin API.
2. **Activity Filtering**: Standardized values and retained only comparable activity types (`IC50`, `Ki`, `Kd`, `EC50`).
3. **Unit Normalization**: Converted all concentration units (e.g., `uM`, `10^-5 mol/L`, `10^-2M`, and mass-based `ug.mL-1`) to nanomolar (`nM`). Mass-based concentration units were resolved individually using molecular weights calculated with RDKit:
   $$\text{Value in nM} = \left(\frac{\text{Value in } \mu\text{g/mL}}{\text{MW}}\right) \times 1\ 000\ 000.0$$
4. **Parameter Extraction**: Extracted target mutations, assay types, cell lines, ATP, and covalent flags from raw text notes using regex and RDKit SMARTS acrylamide searches.
5. **Structure Standardization**: Standardized chemical structures by stripping salt counter-ions and generating canonical isomeric SMILES and 2D InChIKeys using RDKit.
6. **Consensus Deduplication**: Grouped duplicates by `(inchikey, egfr_variant, assay_type, standard_units)`.
   * Resolved low-variance groups ($\Delta pChEMBL \le 1.0$ log unit) using the median value.
   * Excluded highly conflicting groups ($\Delta pChEMBL > 1.0$) to eliminate experimental discrepancies.
   * This step successfully reduced the dataset to **6,334** high-quality consensus rows.

## Validation summary

* **Script Execution**: `scripts/validate_project.py` was executed successfully.
* **Errors**: 0
* **Warnings**: 0
* **Test Suite**: Handled via `pytest`. Core tests successfully verified unit conversion mathematics, regex extraction boundaries, and salt-stripping structure correctness.
* **Result**: Passed. The dataset fully complies with the target schema and contains no duplicate records, undefined fields, or unparseable SMILES strings.

## Limitations

1. **Assay Condition Heterogeneity**: Although raw assays were classified into broad `biochemical` and `cellular` types, the detailed assay conditions (such as pH, incubation times, substrate choices, or ATP concentrations) are frequently unreported in public databases, resulting in missing values in the `atp_concentration_uM` column.
2. **No ADME/Tox Profiles**: The dataset focuses strictly on bioactivity and does not include absorption, distribution, metabolism, excretion, or systemic toxicity measurements.
3. **SMILES Resolution Limits**: A very small fraction of literature compounds (~1%) that lacked explicit IUPAC names, 2D coordinates, or registration IDs in the original paper had to be excluded because their structures could not be resolved.

## Final artifacts

| Artifact | Path |
|----------|------|
| Processed dataset | `data/processed/dataset.csv` |
| Schema | `specs/dataset_schema.json` |
| Source map | `specs/source_map.json` |
| Dataset card | `dataset_card.md` |
| Citation | `CITATION.cff` |
| License | `LICENSE` |
