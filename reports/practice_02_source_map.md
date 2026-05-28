# Practice 2 — Source map

## Source search strategy

Our search strategy relied on a broad initial literature query followed by a targeted manual filtering process to meet the project's technical requirements:
1. **Initial Broad Query:** We performed a baseline search using the term `"egfr inhibitor"` in academic search systems (PubMed, Google Scholar, Semantic Scholar) to gather candidate publications.
2. **Technical Selection Criteria:** From the search results, we manually selected four representative papers that satisfy specific parsing challenges:
   - *Lim et al. 2023:* Selected to practice image table parsing of structured 4th-generation C797S inhibitor assays.
   - *Men et al. 2025:* Selected to practice text extraction of baseline mutational inhibition values from very recent (2025) osimertinib conjugate assays not yet indexed in database releases.
   - *Damghani et al. 2026*: Selected to practice extracting complex structural and kinetic values (IC50 and PDB co-crystal IDs) from the main text and tables.
3. **Database & External Benchmark Reference:** In parallel, we mapped structured databases (ChEMBL, PubChem and BindingDB) using the target UniProt ID `P00533` to serve as a high-volume reference, and integrated pre-existing compiled dataset from Zenodo and.

## Source groups

We have structured our resources into four major groups in `specs/source_map.json`:

- **scientific_papers:** Primary literature PDFs representing discovery or profiling assays of landmark inhibitors. These contain both explicitly tabulated and inline-text bioactivities.
- **supplementary_materials:** Additional attachments linked to primary papers. These often contain larger, more comprehensive compound screening matrices against mutant panels than the main text.
- **databases:** Highly structured web resources (ChEMBL, PubChem,  and BindingDB) queried via API endpoints to automatically pull thousands of historical inhibition records.
- **github_repositories:** Publicly accessible compiled dataset (from Zenodo) that provides simplified molecule-target records.

## Priority sources

Sources are categorized and ranked below by their structural role in the project, data volume, and extraction feasibility:

### 1. Databases: Key Core Resources [Priority: High]
*   **ChEMBL Database API (`db_chembl_api`), PubChem REST API (`db_pubchem_api`), BindingDB (`db_bindingdb`):** 
    These structured databases are prioritized first. They provide the large statistical backbone of historical, curated wild-type and mutant EGFR records with standardized chemical identifiers. Gathering these records forms the core training set for the molecular representation pipeline.

### 2. Scientific Papers: Capturing Recent Research [Priority: High/Medium]
*   **Lim et al. 2023 (`paper_lim_2023`), Men et al. 2025 (`paper_men_2025` & `supp_men_2025`), Damghani et al. 2026 (`paper_damghani_2026`):**
    These primary papers and their supplements are prioritized next. They are used to extract modern compounds. Because these ultra-recent assays (2023–2026) are not yet fully indexed in database releases due to standard curation lag, manual or semi-automated PDF parsing is required to keep our dataset up-to-date.

### 3. Pre-compiled Datasets: Pipeline Validation and Comparison [Priority: Low]
*   **Zenodo EGFR GNN Dataset (`gh_zenodo_gnn`):** 
    This pre-compiled dataset is mapped with low extraction priority for the main pipeline. It will not be integrated into our active training data. Instead, it is reserved purely as an independent external validator to cross-check model predictions and evaluate pipeline performance against a major external benchmark.

## Access conditions

- **Scientific Papers and Supplementary PDFs:**
  - All articles and their supplementary materials are available under open access conditions.
  - No subscription keys are needed to parse these PDFs.
- **Databases & Aggregators:**
  - **ChEMBL API:** Open access, no API keys are required. Queries are throttled to limit request sizes (maximum 50,000 records per call) to prevent timeouts.
  - **PubChem PUG REST:** Open access. Programmatic queries are throttled to 5 requests per second and 100 requests per minute to comply with NCBI rules.
  - **BindingDB:** Accessible without registration. Data will be parsed from the downloadable flat TSV files to reduce live network calls.
  - **Zenodo:** Openly downloadable directly.

## Expected data types

Our extraction workflow is structured to parse the following formats:
- **Inline PDF Text:** Unstructured sentences in the article body (e.g., in `paper_damghani_2026` where specific IC50 values are written in text paragraphs).
- **PDF Tables:** Image or vector_based grid tables within the figures (such as Table 1 in `paper_men_2025`).
- **Supplemental PDFs:** Structured tables and figures containing additional screening data (e.g., Table S2 in `supp_men_2025`).
- **REST API JSON:** Nested structured objects returned by EBI and NCBI endpoints.
- **Tabular Text Files:** Flat TSV and CSV structures downloaded from BindingDB and Zenodo repository.

## Expected conflicts and overlaps

- **Database Overlaps:** BindingDB and ChEMBL often index the same scientific papers.
  - *Resolution Rule:* Records with identical PMIDs (PubMed IDs) and canonicalized SMILES will be deduplicated.
- **Value Discrepancies:** If ChEMBL and BindingDB report slightly different numerical values for the same assay due to rounding:
  - *Resolution Rule:* The pipeline will cross-reference the value directly with the primary PDF. **The value written in the primary paper's PDF will be treated as correct.**
- **Assay Condition Discrepancies:** Different papers report different IC50 values for the same compound-target pair due to differences in assay ATP concentration.
  - *Resolution Rule:* These records will **not** be averaged. They will be stored as separate rows, provided that fields like `atp_concentration_uM` or `cell_line` are populated to retain context.

## Coverage gaps and External Datasets Analysis

### Evaluation of External Datasets (Zenodo)
We mapped external pre-compiled dataset: the **Zenodo GraphEGFR dataset (`gh_zenodo_gnn`)**. This is a high-yield dataset containing 18,282 records annotated across 11 distinct EGFR mutant variants. Despite being "flat" in terms of cellular assay metadata, it preserves the vital biological context (exact mutations) needed for selectivity modeling.

### Integration Strategy
1. **ChEMBL API (`db_chembl_api`), PubChem API (`db_pubchem_api`) & BindingDB (`db_bindingdb`):** These resources will serve as our **primary training backbone**, providing a highly standardized, curated core of historical small-molecule inhibition pairs.
2. **Zenodo EGFR GNN (`gh_zenodo_gnn`):** This dataset will be utilized strictly as an **External Validation Set and Comparator**, as it contains pre-compiled historical data for 11 mutations.
3. **Manual Literature Extractions (2023, 2025, 2026):** These ultra-recent publications will be used to **enrich and update our core dataset** with cutting-edge chemical space (such as BI-8128 structures or osimertinib conjugates), directly filling the curation lag of standard databases.

### Standard Gaps
1. **Curation Lags for Recent Resistance Mutations:** Databases like ChEMBL have a time lag before curating very recent papers on emerging mutations. We address this by extracting these data points directly from primary papers (`paper_lim_2023`, `paper_men_2025`, `paper_damghani_2026`).
2. **Incomplete Assay Metadata:** Curated databases often omit the specific ATP concentration used in kinase assays, making it difficult to convert IC50s to comparable $K_i$ values. We handle this by making `atp_concentration_uM` an optional field and documenting cases where it is unavailable.
3. **Proprietary Pharmaceutical Data:** A significant volume of SAR profiling data is kept in private corporate databases and is not published. Our dataset is therefore limited to academic and patent records that have been made public.