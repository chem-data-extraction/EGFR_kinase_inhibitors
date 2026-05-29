# Practice 4 — Web extraction

## Selected web sites

| source_id | page_id | URL |
|-----------|---------|-----|
| db_chembl_api | chembl_egfr_activities | https://www.ebi.ac.uk/chembl/api/data/activity.json |
| db_pubchem_api | pubchem_egfr_assays | https://pubchem.ncbi.nlm.nih.gov/rest/pug/assay |
| db_bindingdb | bindingdb_egfr_target_results | https://www.bindingdb.org/rest/getLigandsByUniprots |
| gn_gnn_zenodo | zenodo_egfr_gnn_csv | https://zenodo.org/records/11122146 |

## Why these sites were selected

- **ChEMBL**: The gold-standard public biological database for drug discovery. It contains peer-reviewed, high-quality, and manually curated bioactivity data for small molecules against both wild-type and mutant EGFR, directly linked to original scientific literature.
- **PubChem**: The largest free public repository of chemical substances and screening bioassays. It serves as a vital complementary resource to expand chemical space and validate chemical structures via compound CIDs.
- **BindingDB**: A target-centric database focusing heavily on thermodynamic properties (Ki, Kd, and IC50). It is selected to collect diverse affinity metrics and complement typical activity records.
- **Zenodo (GraphEGFR)**: A pre-curated, machine-learning-ready dataset containing over 18,000 records mapped across 11 key EGFR mutations. It serves as an excellent independent external benchmark to validate downstream predictive models.

## Page structure

- **ChEMBL API**: A programmatic REST API returning hierarchical JSON data. It uses standard offset-based pagination via `limit` and `offset` query parameters. The actual bioactivity entries are stored under the `"activities"` root array.
- **PubChem PUG REST API**: A REST API returning JSON structured in a concise tabular format. The response contains a list of headers under the `"Columns"` key and values nested under the `"Row"` key. Additional POST queries return a simple list of property dictionaries (including SMILES) mapped to CIDs under the `"Properties"` key.
- **BindingDB REST API**: A REST endpoint returning structured JSON. Currently, the API contains a server-side typo where the root response key is named `"getLindsByUniprotsResponse"` instead of `"getLigandsByUniprotsResponse"`. The actual measurements reside in a list of dictionaries under the nested `"affinities"` key.
- **Zenodo Archive**: A static GZip Tar archive (`.tar.gz`). Inside the archive, the target path `GraphEGFR/resources/LigEGFR/data` contains 11 individual CSV files named after specific EGFR mutations (e.g., `L858R.csv`, `T790M.csv`). Each file contains an unnamed index column (due to missing `index=False` when saved by the authors), `SMILES_NS`, and logarithmic activity `pIC50`.

## Extraction methods

- **Tools Used**:
  - The `requests` library is used for HTTP requests (GET for ChEMBL/PubChem/BindingDB, POST for chunked PubChem SMILES queries, and streaming GET for downloading the 2.9 GB Zenodo archive).
  - The `tarfile` module is utilized for selective folder extraction, preventing unnecessary unpacking of heavy deep learning model weights.
  - The `pandas` library is used for reading extracted local CSV files and building the final dataset.
- **Throttling & Rate Limits**:
  - ChEMBL API requests are politely throttled with a `1.5`-second delay between pagination pages.
  - PubChem POST requests are queried in batches of up to 1000 CIDs with a `1.0`-second delay to comply with PUG REST guidelines (max 5 requests per second).
  - Single, low-frequency requests are made to BindingDB and Zenodo to prevent server load.
  - All APIs are open-access and permit automated research queries.

## Extracted fields

Raw extracted fields from different web formats were mapped to the standardized project schema columns:

| Schema Column | ChEMBL Source | PubChem Source | BindingDB Source | Zenodo Source |
|---|---|---|---|---|
| **record_id** | `chembl_` + `activity_id` | `pubchem_` + `CID` + row index | `bindingdb_` + `monomerid` + row index | `zenodo_` + mutation + row index |
| **compound_id** | `molecule_chembl_id` | `CID` | `monomerid` | Generated index |
| **compound_smiles** | `canonical_smiles` | `SMILES` (from POST lookup) | `smile` | `SMILES_NS` |
| **egfr_variant** | `assay_description` | `Assay Name` | `target` | Filename (mutation type) |
| **standard_type** | `standard_type` | `Activity Name` | `affinity_type` | Fixed to `"IC50"` |
| **standard_value** | `standard_value` | `Activity Value [uM]` | `affinity` | Calculated as: $10^{9 - pIC50}$ |
| **standard_units** | `standard_units` | `Activity Unit` | Fixed to `"nM"` | Fixed to `"nM"` |
| **source_id** | `db_chembl_api` | `db_pubchem_api` | `db_bindingdb` | `gn_gnn_zenodo` |
| **notes** | `assay_description` | `Assay Name` | `target` | Missed |

## Extraction problems

1. **BindingDB API Typo**: The API returns a root JSON key with a typo (`getLindsByUniprotsResponse`). To prevent the parser from breaking if the database developers ever fix this, the python parser is designed defensively to dynamically query the first root key regardless of its name.
2. **PubChem Payload Limits**: Sending thousands of compound CIDs in a single POST request to retrieve SMILES triggers a `413 Payload Too Large` error. This was resolved by chunking the unique CID list into batches of 1000 and merging the results.
3. **Massive Zenodo Archive Scale**: Unpacking the entire 2.9 GB archive is slow and consumes excessive disk space because we only need a few megabytes of CSV files. This was resolved by implementing a streaming download with console logging and performing selective tar extraction of the target data folder.
4. **macOS Metadata Pollutants**: The inclusion of hidden index files starting with `._` (e.g., `._L858R.csv`) inside the Zenodo archive causes parsing errors in pandas. This was solved by filtering out files starting with `._` during both extraction and scanning.
5. **Unnamed Index Column in Zenodo**: Zenodo files include an unnamed first column with index numbers. This was cleanly resolved by using `index_col=0` in `pd.read_csv`.

## Output files

- `data/extracted/web_extracted_records.csv` - Unified flat table containing all extracted raw web records.
- `data/raw/web/chembl_egfr_activities.json` - Raw ChEMBL API response snapshot.
- `data/raw/web/pubchem_egfr_assays.json` - Raw PubChem bioassay and SMILES response snapshot.
- `data/raw/web/bindingdb_egfr_results.html` - Raw BindingDB response snapshot.
- `data/raw/web/zenodo_egfr_gnn_dataset.csv` - **NOT DOWNLOADED** - The original Zenodo archive (2.9 GB) was not stored locally due to its large size. Only the selectively extracted mutation CSV files were retained in `data/raw/web/extracted_zenodo/`.
- `data/raw/web/extracted_zenodo/...` - Folder containing selectively extracted mutation CSV files.
- `data/extracted/zenodo_extracted_records.csv` - Unified flat table containing all extracted Zenodo records.
- `data/extracted/extraction_log.jsonl` - General extraction log registering timestamps, statuses, and record counts.