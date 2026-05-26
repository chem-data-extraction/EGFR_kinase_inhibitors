# Practice 2 — Source map

## Source search strategy

Our search strategy relied on a broad initial literature query followed by a targeted manual filtering process to meet the project's technical requirements:
1. **Initial Broad Query:** We performed a baseline search using the term `"egfr inhibitor"` in academic search systems (PubMed, Google Scholar, Semantic Scholar) to gather candidate publications.
2. **Technical Selection Criteria:** From the search results, we manually selected three representative papers that satisfy specific parsing challenges:
   - *Moyer et al. 1997:* Selected to practice text extraction of baseline wild-type EGFR inhibition values from inline body text.
   - *Schwartz et al. 2014:* Selected to practice extracting complex kinetic data (Kd, Ki) from both the main text and supplementary PDF tables.
   - *Lim et al. 2023:* Selected to practice image table parsing of structured 4th-generation C797S inhibitor assays.
3. **Database Reference:** In parallel, we mapped structured databases (ChEMBL and BindingDB) using the target UniProt ID `P00533` to serve as a high-volume reference for the final dataset.

## Source groups

We have structured our resources into four major groups in `specs/source_map.json`:

- **scientific_papers:** Primary literature PDFs representing discovery or profiling assays of landmark inhibitors. These contain both explicitly tabulated and inline-text bioactivities.
- **supplementary_materials:** Additional PDF and spreadsheet attachments linked to primary papers. These often contain larger, more comprehensive compound screening matrices against mutant panels than the main text.
- **databases:** Highly structured web resources (ChEMBL and PubChem) queried via REST API endpoints to automatically pull thousands of historical inhibition records.
- **aggregators:** Secondary aggregation platforms (BindingDB) mapped through structured tables and target-specific landing pages.

## Priority sources

Sources are ranked below by expected yield, data quality, and extraction feasibility:

1. **ChEMBL Database API (`db_chembl_api`) [Priority: High]:** Will be extracted first. This provides the highest volume of structured, pre-curated WT and mutant records with standardized canonical SMILES, dramatically accelerating dataset assembly.
2. **Covalent Inhibitor Study (`paper_schwartz_2014` + `supp_schwartz_2014`) [Priority: High]:** This source is prioritized for retrieving kinetic parameters ($k_{act}$, $K_i$) and reversible affinities ($K_d$) of covalent inhibitors against both WT and L858R/T790M mutant EGFR.
3. **BBT-176 Discovery Paper (`paper_lim_2023`) [Priority: High]:** Crucial for pulling modern "fourth-generation" C797S resistance mutation measurements. The main paper contains extremely clean biochemical tables.
4. **Erlotinib Benchmark Paper (`paper_moyer_1997`) [Priority: Medium]:** Contains historical baseline measurements of Erlotinib against WT EGFR. Values are mainly inline text and plots, requiring manual quality checks.
5. **PubChem REST API (`db_pubchem_api`) [Priority: Low]:** Extracted last to fill missing chemical gaps. Contains massive HTS screens but requires deep filtering to exclude low-quality or non-quantitative assays.

## Access conditions

- **Scientific Papers and Supplementary PDFs:**
  - `paper_lim_2023` is accessible under open access conditions.
  - `paper_schwartz_2014` and its supplement `supp_schwartz_2014` are openly accessible via PubMed Central (PMC).
  - `paper_moyer_1997` is available through semantic search indexes (Semantic Scholar).
  - No subscription keys are needed to parse these PDFs.
- **Databases & Aggregators:**
  - **ChEMBL API:** Open access, no API keys are required. Queries are throttled to limit request sizes (maximum 50,000 records per call) to prevent timeouts.
  - **PubChem PUG REST:** Open access. Programmatic queries are throttled to 5 requests per second and 100 requests per minute to comply with NCBI rules.
  - **BindingDB:** Accessible without registration. Data will be parsed from the downloadable flat TSV files to reduce live network calls.

## Expected data types

Our extraction workflow is structured to parse the following formats:
- **Inline PDF Text:** Unstructured sentences in the article body (e.g., in `paper_moyer_1997` where specific IC50 values are written in text paragraphs).
- **PDF Tables:** Image tables within the figures (such as Table 1 in `paper_lim_2023`).
- **Supplemental PDFs:** Structured tables and figures containing additional screening data (e.g., Table S6 in `supp_schwartz_2014`).
- **REST API JSON:** Nested structured objects returned by EBI and NCBI endpoints.
- **Tabular Text Files:** Flat TSV and CSV structures downloaded from BindingDB.

## Expected conflicts and overlaps

- **Database Overlaps:** BindingDB and ChEMBL often index the same scientific papers.
  - *Resolution Rule:* Records with identical PMIDs (PubMed IDs) and canonicalized SMILES will be deduplicated.
- **Value Discrepancies:** If ChEMBL and BindingDB report slightly different numerical values for the same assay due to rounding:
  - *Resolution Rule:* The pipeline will cross-reference the value directly with the primary PDF (e.g., `paper_schwartz_2014`). **The value written in the primary paper's PDF will be treated as correct.**
- **Assay Condition Discrepancies:** Different papers report different IC50 values for the same compound-target pair due to differences in assay ATP concentration.
  - *Resolution Rule:* These records will **not** be averaged. They will be stored as separate rows, provided that fields like `atp_concentration_uM` or `cell_line` are populated to retain context.

## Coverage gaps

1. **Curation Lags for Recent Resistance Mutations:** Databases like ChEMBL have a time lag before curating very recent papers on emerging mutations (such as C797S or Exon 20 insertions). We address this by extracting these data points directly from primary papers (`paper_lim_2023`, `paper_schwartz_2014`).
2. **Incomplete Assay Metadata:** Curated databases often omit the specific ATP concentration used in kinase assays, making it difficult to convert IC50s to comparable $K_i$ values. We handle this by making `atp_concentration_uM` an optional field and documenting cases where it is unavailable.
3. **Proprietary Pharmaceutical Data:** A significant volume of SAR profiling data is kept in private corporate databases and is not published. Our dataset is therefore limited to academic and patent records that have been made public.
