# Practice 3 — PDF extraction

## Selected PDF sources

| source_id | pdf_id | Year | Path |
|-----------|--------|----------------|------|
| paper_lim_2023 | lim_2023 | 2023 | data/raw/pdf/lim_2023.pdf |
| paper_men_2025 | men_2025 | 2025 | data/raw/pdf/men_2025.pdf |
| paper_damghani_2026 | damghani_2026 | 2026 | data/raw/pdf/damghani_2026.pdf |

## Why these PDFs were selected

These primary papers and their supplements are used to extract modern compounds. Because these ultra-recent assays (2023–2026) are not yet fully indexed in database releases due to standard curation lag, manual or semi-automated PDF parsing is required to keep our dataset up-to-date:
*   **Relevance to Target Generations**: They contain quantitative activity metrics ($\text{IC}_{50}$) for clinical-grade comparative controls (Osimertinib, Erlotinib, Afatinib) and novel/developing drug candidates targeting complex resistance mutations (e.g., the triple mutant $\text{L858R/T790M/C797S}$ or $\text{del19/T790M/C797S}$).
*   **Quantitative Table Quality**: All selected publications report high-density tabular data presenting direct concentration response values ($\text{IC}_{50}$) rather than qualitative or graphic-only descriptions, enabling numerical standardization.
*   **Assay Diversity**: The papers present both biochemical kinase assays (evaluating direct target affinity) and cellular proliferation assays (mostly on $\text{Ba/F3}$ and cancer cell lines like $\text{H1975}$ and $\text{PC-9}$), allowing the comparison of in vitro potency with in cellulo efficacy.

## Pages used

*   **`lim_2023` (Lim et al.)**: 
    *   **Pages 5-7**: Processed because they contain the key biochemical profiling tables (under Figure 2), cellular proliferation measurements across mutant Ba/F3 lines (under Figure 3), and resistance evaluation tables (under Figure 4).
*   **`men_2025` (Men et al.)**: 
    *   **Page 4**: Contains Table 1 (cellular $\text{IC}_{50}$ in H1975 cell lines and biochemical $\text{IC}_{50}$ against L858R/T790M) and Table 2 (activity profiles for compounds across PC-9, A549, and biochemical assays).
    *   **Supplementary Pages 1–4 (`supp_men_2025.pdf`)**: Explored to extract Supplementary Table S1 (cellular potencies against H1975) and Supplementary Table S2 (biochemical profiling against WT EGFR).
*   **`damghani_2026` (Damghani et al.)**:
    *   **Page 15**: Contains Table 1, presenting cellular antiproliferative potencies for BI-4732 and BI-8128 against Ba/F3, A431, and PC-9 models.
    *   **Page 16**: Contains Table 2, providing biochemical potencies of BI-8128 and BI-4732 across WT, single, double, and triple mutants of recombinant EGFR.

## Extraction methods

TTo build a reliable and reproducible workflow, several extraction methods were assessed and applied:
*   **Agentic Parser / Llama Cloud** (used for `lim_2023`): Attempting raw layout extraction on `lim_2023` with standard Python tools caused jumbled text blocks due to the complex, multi-column academic formatting. Instead, the first 8 pages were compiled into a trimmed PDF and processed through an agentic Markdown parser (Llama Cloud API). The generated clean Markdown tables were subsequently extracted programmatically via `BeautifulSoup`.
*   **pdfplumber** (used for `damghani_2026` and `men_2025`): This was used for extracting structured layout text from targeted pages. It allowed exact row-by-row extraction of clean tables where columns were well-aligned.
*   **Python Regular Expressions (Regex)**: Raw text lines retrieved via `pdfplumber` were parsed using strict regex matches to capture chemical designations (e.g., `10a`, `10j`, `BI-4732`), relations, and numeric values.
*   **Manual Auditing and Correction**: Manual verification was conducted on the entire consolidated CSV file. Raw figures and tables from the source papers were checked to ensure no misalignments, incorrect unit assignments, or column offsets occurred during parsing.

## Extracted fields

| PDF Source Field / Context | Target Schema Field | Standardization / Mapping Details |
| :--- | :--- | :--- |
| Row Labels / Compound Code | `compound_name` | Mapped directly (e.g., `BI-4732`, `10a`, `Osimertinib`). Compound spacing was stripped. |
| Column / Sub-row target name | `egfr_variant` | Cleaned via regex. Variant names (e.g., `"19Del"`, `"parental del19 genotype"`, `"WT (added EGF)"`) mapped to standard variants (`WT`, `del19`, `del19/C797S`, etc.). |
| Table Context / Methodology | `assay_type` | Divided into `cellular` or `biochemical` based on assay conditions. |
| Table Header / Paragraph context | `cell_line` | Unified into standard cell lines (`Ba/F3`, `H1975`, `A431`, `PC-9`, `A549`). Recombinant kinase assays received `None`. |
| Value prefixes (`>`, `<`, `=`) | `standard_relation` | Raw symbols isolated via regex into distinct columns; defaults to `=` if absent. |
| Table Numbers | `standard_value` | Parsed to float. Values from `men_2025` were converted from micromolar ($\mu\text{M}$) to nanomolar ($\text{nM}$) by multiplying by $1000.0$. |
| Table Header Units | `standard_units` | Normalized to standard units (`nM` or `nmol/L`). |
| Document context / Metadata | `source_id` | Mapped to unique key (`paper_lim_2023`, `paper_men_2025`, `paper_damghani_2026`). |
| Caption / Title in PDF | `table_origin` | Identifies specific tables (e.g., `Table 1`, `Table S2`, `Figure 2C`, `Figure 3B`). |

## Extraction problems

Several layout and syntactic issues were encountered and resolved:
1.  **Multi-Column Layout Wraps**: The double-column layout in `lim_2023` caused standard text stream extractors to merge text from parallel columns. Using Llama Cloud to output Markdown before parsing resolved these alignment issues.
2.  **Relational Value Merges**: Text values like `>10000` or `>1000` required structural regex splitting to keep the relation indicator separate from the absolute concentration value.
3.  **Unit Heterogeneity**: Men et al. (2025) reported values in $\mu\text{M}$ within the main text tables, while the supplementary materials used a mix of percentage values (for inhibition rate) and nanomolar concentrations. Strict programmatic conversion rules were written to scale micromolar numeric values to nanomolar units consistently.
4.  **Layout Shifting in Supplementary Files**: Multi-page supplementary tables often lack static header layouts. The parser accommodated this by targeting specific string anchors (such as `"Table S2"`) and using substring splitting to isolate target areas.

## Output files

- `data/extracted/pdf_extracted_records.csv`
- `data/extracted/extraction_log.jsonl` (PDF-related lines)
- Raw PDFs under `data/raw/pdf/`