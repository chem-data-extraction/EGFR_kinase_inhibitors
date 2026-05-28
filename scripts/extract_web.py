#!/usr/bin/env python3
"""
Web extraction driver for EGFR Kinase Inhibitors dataset.
Extracts data from ChEMBL, PubChem, BindingDB, and Zenodo,
creates local raw snapshots, and formats them into a unified CSV schema.
"""

from __future__ import annotations

import json
import os
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "specs/web_extraction_manifest.json"
SCHEMA_PATH = ROOT / "specs/dataset_schema.json"
LOG_PATH = ROOT / "data/extracted/extraction_log.jsonl"


def append_log(entry: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def process_chembl(page: dict, raw_path: Path) -> dict:
    if raw_path.exists():
        print(f"    Using ChEMBL local snapshot: {raw_path.relative_to(ROOT)}")
        with raw_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    url = "https://www.ebi.ac.uk/chembl/api/data/activity.json"
    params = {
        "target_chembl_id": "CHEMBL203",
        "standard_type__in": "IC50,Ki,Kd,EC50",
        "limit": 500,
        "_format": "json"
    }
    
    all_activities = []
    page_num = 0
    print("    Downloading ChEMBL data via API...")

    while True:
        params["offset"] = params["limit"] * page_num
        time.sleep(1.5)
        try:
            response = requests.get(url, params=params, timeout=60)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                print("    Rate limit exceeded (429). Waiting 15 seconds...")
                time.sleep(15)
                continue
            raise e

        data = response.json()
        activities = data.get("activities", [])
        if not activities:
            break

        all_activities.extend(activities)
        print(f"    Downloaded {len(all_activities)} ChEMBL records...")
        page_num += 1

    payload = {"activities": all_activities}
    with raw_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        
    return payload


def extract_chembl_records(data: dict, source_id: str) -> list[dict]:
    records = []
    for act in data.get("activities", []):
        act_id = act.get("activity_id")
        if not act_id:
            continue
        records.append({
            "record_id": f"chembl_{act_id}",
            "compound_id": act.get("molecule_chembl_id"),
            "compound_smiles": act.get("canonical_smiles"),
            "compound_name": act.get("molecule_pref_name"),
            "standard_type": act.get("standard_type"),
            "standard_value": act.get("standard_value"),
            "standard_units": act.get("standard_units"),
            "standard_relation": act.get("standard_relation") or act.get("relation") or "=",
            "source_id": source_id,
            "extraction_confidence": "high",
            "extraction_method": "web_scrape",
            "notes": act.get("assay_description")
        })
    return records


def process_pubchem(page: dict, raw_path: Path) -> dict:
    if raw_path.exists():
        print(f"    Using PubChem local snapshot: {raw_path.relative_to(ROOT)}")
        with raw_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    target_accession = "P00533"
    print("    Downloading bioassays from PubChem...")
    bioassay_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/assay/target/accession/{target_accession}/concise/json"
    
    response = requests.get(bioassay_url, timeout=60)
    response.raise_for_status()
    concise_data = response.json()

    rows = concise_data.get("Table", {}).get("Row", [])
    columns = concise_data.get("Table", {}).get("Columns", {}).get("Column", [])
    cid_idx = columns.index("CID") if "CID" in columns else -1
    
    cids = []
    if cid_idx != -1:
        for r in rows:
            cid_val = r.get("Cell", [])[cid_idx]
            if cid_val:
                try:
                    cids.append(int(cid_val))
                except ValueError:
                    continue

    unique_cids = list(set(cids))
    print(f"    Found {len(unique_cids)} CIDs. Downloading SMILES in batches of 1000...")
    
    smiles_map = {}
    chunk_size = 1000
    smiles_url = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/property/SMILES,IUPACName/json"

    for i in range(0, len(unique_cids), chunk_size):
        chunk = unique_cids[i:i+chunk_size]
        cids_string = ",".join(map(str, chunk))
        time.sleep(1.0)
        try:
            resp = requests.post(smiles_url, data={"cid": cids_string}, timeout=60)
            resp.raise_for_status()
            properties = resp.json().get("PropertyTable", {}).get("Properties", [])
            for prop in properties:
                cid = prop.get("CID")
                smiles = prop.get("SMILES")
                if cid and smiles:
                    smiles_map[str(cid)] = smiles
        except Exception as e:
            print(f"    ! Error downloading SMILES batch: {e}")

    payload = {
        "concise_table": concise_data,
        "smiles_map": smiles_map
    }

    with raw_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        
    return payload


def extract_pubchem_records(data: dict, source_id: str) -> list[dict]:
    records = []
    concise_table = data.get("concise_table", {})
    smiles_map = data.get("smiles_map", {})

    rows = concise_table.get("Table", {}).get("Row", [])
    columns = concise_table.get("Table", {}).get("Columns", {}).get("Column", [])
    
    col_map = {col: idx for idx, col in enumerate(columns)}
    
    cid_idx = col_map.get("CID", -1)
    val_idx = col_map.get("Activity Value [uM]", -1)
    type_idx = col_map.get("Activity Name", -1)
    name_idx = col_map.get("Assay Name", -1)
    unit_idx = col_map.get("Activity Unit", -1)
    db_assay_type_idx = col_map.get("Assay Type", -1)

    for idx, r in enumerate(rows):
        cells = r.get("Cell", [])
        if not cells:
            continue

        cid = cells[cid_idx] if cid_idx != -1 and cid_idx < len(cells) else None
        val = cells[val_idx] if val_idx != -1 and val_idx < len(cells) else None
        act_type = cells[type_idx] if type_idx != -1 and type_idx < len(cells) else None
        assay_name = cells[name_idx] if name_idx != -1 and name_idx < len(cells) else None
        db_assay_type = cells[db_assay_type_idx] if db_assay_type_idx != -1 and db_assay_type_idx < len(cells) else ""
        unit = cells[unit_idx] if unit_idx != -1 and unit_idx < len(cells) else "uM"

        if not cid or not val:
            continue

        smiles_entry = smiles_map.get(str(cid))
        if isinstance(smiles_entry, dict):
            smiles = smiles_entry.get("smiles")
            compound_name = smiles_entry.get("iupac_name")
        else:
            smiles = smiles_entry
            compound_name = None

        assay_name_str = str(assay_name) if assay_name else ""
        
        records.append({
            "record_id": f"pubchem_{cid}_{idx}",
            "compound_id": str(cid),
            "compound_smiles": smiles,
            "compound_name": compound_name,
            "standard_type": act_type,
            "standard_value": val,
            "standard_units": unit,
            "source_id": source_id,
            "extraction_confidence": "high",
            "extraction_method": "web_scrape",
            "notes": assay_name_str
        })
    return records


def process_bindingdb(page: dict, raw_path: Path) -> dict:
    if raw_path.exists():
        print(f"    Using local BindingDB snapshot: {raw_path.relative_to(ROOT)}")
        with raw_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    uniprot_id = "P00533"
    url = f"https://www.bindingdb.org/rest/getLigandsByUniprots?uniprot={uniprot_id}&cutoff=100000"
    
    print("    Downloading data from BindingDB REST API...")
    response = requests.get(url, timeout=90)
    response.raise_for_status()
    payload = response.json()

    with raw_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        
    return payload


def extract_bindingdb_records(data: dict, source_id: str) -> list[dict]:
    records = []
    root_keys = list(data.keys())
    if not root_keys:
        return records

    first_key = root_keys[0]
    affinities = data[first_key].get("affinities", [])

    for idx, aff in enumerate(affinities):
        monomer_id = aff.get("monomerid")
        if not monomer_id:
            continue

        records.append({
            "record_id": f"bindingdb_{monomer_id}_{idx}",
            "compound_id": str(monomer_id),
            "compound_smiles": aff.get("smile"),
            "compound_name": aff.get("inhibitor") or aff.get("monomer_name") or aff.get("name"),
            "standard_type": aff.get("affinity_type"),
            "standard_value": aff.get("affinity"),
            "standard_units": "nM",
            "source_id": source_id,
            "extraction_confidence": "high",
            "extraction_method": "web_scrape",
            "notes": aff.get("target")
        })
    return records


def process_zenodo(page: dict, raw_path: Path) -> str:
    if not raw_path.exists():
        url = "https://zenodo.org/records/11122146/files/GraphEGFR.tar.gz?download=1"
        print("    Zenodo archive not found. Starting streaming download (~2.9 GB)...")
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            downloaded = 0
            with raw_path.open("wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024 * 100):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            print(f"      Downloaded {downloaded / (1024*1024):.1f} of {total_size / (1024*1024):.1f} MB ({(downloaded/total_size)*100:.1f}%)")
                        else:
                            print(f"      Downloaded {downloaded / (1024*1024):.1f} MB")

    extract_dir = raw_path.parent / "extracted_zenodo"
    target_prefix = "GraphEGFR/resources/LigEGFR/data"
    data_folder = extract_dir / "GraphEGFR" / "resources" / "LigEGFR" / "data"

    if not data_folder.exists():
        print(f"    Unpacking {target_prefix} folder from archive...")
        extract_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(raw_path, "r:gz") as tar:
            members = []
            for m in tar.getmembers():
                if m.name.startswith(target_prefix):
                    filename = os.path.basename(m.name)
                    if not filename.startswith("._"):
                        members.append(m)
            try:
                tar.extractall(path=extract_dir, members=members, filter='data')
            except TypeError:
                tar.extractall(path=extract_dir, members=members)
                
    return str(data_folder)


def extract_zenodo_records(data_folder_str: str, source_id: str) -> list[dict]:
    records = []
    data_folder = Path(data_folder_str)

    for csv_file in data_folder.glob("*.csv"):
        if csv_file.name.startswith("._"):
            continue

        print(f"    Reading Zenodo files: {csv_file.name}...")
        df = pd.read_csv(csv_file, index_col=0)
        
        if "SMILES_NS" not in df.columns or "pIC50" not in df.columns:
            continue

        df["pIC50"] = pd.to_numeric(df["pIC50"], errors="coerce")
        df = df.dropna(subset=["pIC50", "SMILES_NS"])
        
        mutation = csv_file.stem

        for idx, row in df.iterrows():
            pic50 = row["pIC50"]
            smiles = row["SMILES_NS"]
            ic50_nm = 10 ** (9 - pic50)

            records.append({
                "record_id": f"zenodo_{mutation}_{idx}",
                "compound_smiles": smiles,
                "egfr_variant": mutation,
                "standard_type": "IC50",
                "standard_value": ic50_nm,
                "standard_units": "nM",
                "pchembl_value": pic50,
                "source_id": source_id,
                "extraction_confidence": "high",
                "extraction_method": "web_scrape"
            })
    return records


def main() -> None:
    with MANIFEST.open(encoding="utf-8") as f:
        manifest = json.load(f)

    print(f"Web extraction v{manifest.get('web_extraction_version')}")
    print(f"Script: {manifest.get('script')}")
    print(f"Output: {manifest.get('output_records_file')}")
    print("\nStarting extraction pipeline:")

    all_records = []

    for page in manifest.get("input_pages", []):
        page_id = page['page_id']
        source_id = page['source_id']
        raw_path = ROOT / page['raw_snapshot_path']
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"\nProcessing page/assay: {page_id} (source_id={source_id})...")
        
        try:
            records = []
            if page_id == "chembl_egfr_activities":
                raw_data = process_chembl(page, raw_path)
                records = extract_chembl_records(raw_data, source_id)
                all_records.extend(records)
                
            elif page_id == "pubchem_egfr_assays":
                raw_data = process_pubchem(page, raw_path)
                records = extract_pubchem_records(raw_data, source_id)
                all_records.extend(records)
                
            elif page_id == "bindingdb_egfr_target_results":
                raw_data = process_bindingdb(page, raw_path)
                records = extract_bindingdb_records(raw_data, source_id)
                all_records.extend(records)
                
            elif page_id == "zenodo_egfr_gnn_csv":
                data_folder_str = process_zenodo(page, raw_path)
                records = extract_zenodo_records(data_folder_str, source_id)
                zenodo_records = records
                
            else:
                print(f"    X Unknown page_id in manifest: {page_id}")
                continue

            print(f"    -> Extracted records: {len(records)}")

            append_log({
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "step": "web_extraction",
                "source_id": source_id,
                "status": "success",
                "tool": "extract_web.py",
                "output": str(raw_path.relative_to(ROOT)),
                "records_count": len(records)
            })

        except Exception as e:
            print(f"    X Error during processing {page_id}: {e}")
            append_log({
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "step": "web_extraction",
                "source_id": source_id,
                "status": "failed",
                "tool": "extract_web.py",
                "output": str(raw_path.relative_to(ROOT)),
                "issue": str(e)
            })

    if all_records:
        output_csv = ROOT / manifest.get("output_records_file", "data/extracted/web_extracted_records.csv")
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        
        df_output = pd.DataFrame(all_records)
        
        with SCHEMA_PATH.open(encoding="utf-8") as f:
            schema = json.load(f)
        schema_cols = [field["name"] for field in schema["fields"]]
        
        for col in schema_cols:
            if col not in df_output.columns:
                df_output[col] = None
                
        extra_cols = [c for c in df_output.columns if c not in schema_cols]
        final_cols = schema_cols + extra_cols
        df_output = df_output[final_cols]
        
        df_output.to_csv(output_csv, index=False, encoding="utf-8")
        
        print(f"\n✓ Successfully saved {len(df_output)} records to file: {output_csv.relative_to(ROOT)}")
    else:
        logger.error("\nNo records were extracted.")

    if zenodo_records:
        zenodo_csv = ROOT / "data/extracted/zenodo_extracted_records.csv"
        df_zenodo = pd.DataFrame(zenodo_records)
        df_zenodo.to_csv(zenodo_csv, index=False)
        print(f"\n✓ Saved {len(df_zenodo)} Zenodo-specific records to: {zenodo_csv.relative_to(ROOT)}")
    else:
        print("\nNo Zenodo records were extracted.")


if __name__ == "__main__":
    main()
