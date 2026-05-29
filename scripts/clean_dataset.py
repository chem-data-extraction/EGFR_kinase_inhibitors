#!/usr/bin/env python3
"""Clean and normalize merged or extracted records into the final dataset."""

from __future__ import annotations

import json
import math
import re
import urllib.parse
import requests
import time
from pathlib import Path

import numpy as np
import pandas as pd

from rdkit import Chem
from rdkit.Chem import Descriptors, SaltRemover

ROOT = Path(__file__).resolve().parents[1]

MERGED_PATH = ROOT / "data/interim/merged_records.csv"
PDF_CSV = ROOT / "data/extracted/pdf_extracted_records.csv"
WEB_CSV = ROOT / "data/extracted/web_extracted_records.csv"
SCHEMA_PATH = ROOT / "specs/dataset_schema.json"
DATASET_PATH = ROOT / "data/processed/dataset.csv"

MISSING_TOKENS = {"", "na", "n/a", "none", "null", "-", "nan", "unknown"}
COMPOUNDS_IUPAC = {
    '9a': 'Tert-butyl (2-((2-((2-acrylamido-5-methoxy-4-((4-(1-methyl-1H-indol-3-yl)pyrimidin-2-yl)amino)phenyl)(methyl)amino)ethyl)amino)-2-oxoethyl)carbamate',
    '9b': 'Tert-butyl (R)-(1-((2-((2-acrylamido-5-methoxy-4-((4-(1-methyl-1H-indol-3-yl)pyrimidin-2-yl)amino)phenyl)(methyl)amino)ethyl)amino)-1-oxopropan-2-yl)carbamate',
    '9c': 'Tert-butyl (R)-(1-((2-((2-acrylamido-5-methoxy-4-((4-(1-methyl-1H-indol-3-yl)pyrimidin-2-yl)amino)phenyl)(methyl)amino)ethyl)amino)-4-methyl-1-oxopentan-2-yl)carbamate',
    '9d': 'Tert-butyl (S)-2-((2-((2-acrylamido-5-methoxy-4-((4-(1-methyl-1H-indol-3-yl)pyrimidin-2-yl)amino)phenyl)(methyl)amino)ethyl)carbamoyl)pyrrolidine-1-carboxylate',
    '9e': 'Tert-butyl ((2R,3R)-1-((2-((2-acrylamido-5-methoxy-4-((4-(1-methyl-1H-indol-3-yl)pyrimidin-2-yl)amino)phenyl)(methyl)amino)ethyl)amino)-3-methyl-1-oxopentan-2-yl)carbamate',
    '9f': 'Tert-butyl (R)-(1-((2-((2-acrylamido-5-methoxy-4-((4-(1-methyl-1H-indol-3-yl)pyrimidin-2-yl)amino)phenyl)(methyl)amino)ethyl)amino)-1-oxo-3-phenylpropan-2-yl)carbamate',
    '9g': 'Tert-butyl (R)-(1-((2-((2-acrylamido-5-methoxy-4-((4-(1-methyl-1H-indol-3-yl)pyrimidin-2-yl)amino)phenyl)(methyl)amino)ethyl)amino)-3-methyl-1-oxobutan-2-yl)carbamate',
    '9h': 'Tert-butyl (1-((2-((2-acrylamido-5-methoxy-4-((4-(1-methyl-1H-indol-3-yl)pyrimidin-2-yl)amino)phenyl)(methyl)amino)ethyl)amino)-4-(methylthio)-1-oxobutan-2-yl)carbamate',
    '9i': 'Tert-butyl (2-((3-((2-acrylamido-5-methoxy-4-((4-(1-methyl-1H-indol-3-yl)pyrimidin-2-yl)amino)phenyl)(methyl)amino)propyl)amino)-2-oxoethyl)carbamate',
    '9j': 'Tert-butyl (R)-(1-((3-((2-acrylamido-5-methoxy-4-((4-(1-methyl-1H-indol-3-yl)pyrimidin-2-yl)amino)phenyl)(methyl)amino)propyl)amino)-1-oxopropan-2-yl)carbamate',
    '9k': 'Tert-butyl (R)-(1-((3-((2-acrylamido-5-methoxy-4-((4-(1-methyl-1H-indol-3-yl)pyrimidin-2-yl)amino)phenyl)(methyl)amino)propyl)amino)-4-methyl-1-oxopentan-2-yl)carbamate',
    '9l': 'Tert-butyl (S)-2-((3-((2-acrylamido-5-methoxy-4-((4-(1-methyl-1H-indol-3-yl)pyrimidin-2-yl)amino)phenyl)(methyl)amino)propyl)carbamoyl)pyrrolidine-1-carboxylate',
    '9m': 'Tert-butyl ((2R,3R)-1-((3-((2-acrylamido-5-methoxy-4-((4-(1-methyl-1H-indol-3-yl)pyrimidin-2-yl)amino)phenyl)(methyl)amino)propyl)amino)-3-methyl-1-oxopentan-2-yl)carbamate',
    '9n': 'Tert-butyl (R)-(1-((3-((2-acrylamido-5-methoxy-4-((4-(1-methyl-1H-indol-3-yl)pyrimidin-2-yl)amino)phenyl)(methyl)amino)propyl)amino)-1-oxo-3-phenylpropan-2-yl)carbamate',
    '9o': 'Tert-butyl (R)-(1-((3-((2-acrylamido-5-methoxy-4-((4-(1-methyl-1H-indol-3-yl)pyrimidin-2-yl)amino)phenyl)(methyl)amino)propyl)amino)-3-methyl-1-oxobutan-2-yl)carbamate',
    '10a': 'N-(2-((2-(2-Aminoacetamido)ethyl)(methyl)amino)-4-methoxy-5-((4-(1-methyl-1H-indol-3-yl)pyrimidin-2-yl)amino)phenyl)acrylamide',
    '10b': '(R)-N-(2-((2-(2-Aminopropanamido)ethyl)(methyl)amino)-4-methoxy-5-((4-(1-methyl-1H-indol-3-yl)pyrimidin-2-yl)amino)phenyl)acrylamide',
    '10c': '(R)-N-(2-((2-Acrylamido-5-methoxy-4-((4-(1-methyl-1H-indol-3-yl)pyrimidin-2-yl)amino)phenyl)(methyl)amino)ethyl)-2-amino-4-methylpentanamide',
    '10d': '(S)-N-(2-((2-Acrylamido-5-methoxy-4-((4-(1-methyl-1H-indol-3-yl)pyrimidin-2-yl)amino)phenyl)(methyl)amino)ethyl)pyrrolidine-2-carboxamide',
    '10e': '(2R,3R)-N-(2-((2-Acrylamido-5-methoxy-4-((4-(1-methyl-1H-indol-3-yl)pyrimidin-2-yl)amino)phenyl)(methyl)amino)ethyl)-2-amino-3-methylpentanamide',
    '10f': '(R)-N-(2-((2-(2-Amino-3-phenylpropanamido)ethyl)(methyl)amino)-4-methoxy-5-((4-(1-methyl-1H-indol-3-yl)pyrimidin-2-yl)amino)phenyl)acrylamide',
    '10g': '(R)-N-(2-((2-Acrylamido-5-methoxy-4-((4-(1-methyl-1H-indol-3-yl)pyrimidin-2-yl)amino)phenyl)(methyl)amino)ethyl)-2-amino-3-methylbutanamide',
    '10i': 'N-(2-((3-(2-Aminoacetamido)propyl)(methyl)amino)-4-methoxy-5-((4-(1-methyl-1H-indol-3-yl)pyrimidin-2-yl)amino)phenyl)acrylamide',
    '10j': '(R)-N-(2-((3-(2-Aminopropanamido)propyl)(methyl)amino)-4-methoxy-5-((4-(1-methyl-1H-indol-3-yl)pyrimidin-2-yl)amino)phenyl)acrylamide',
    '10k': '(R)-N-(3-((2-Acrylamido-5-methoxy-4-((4-(1-methyl-1H-indol-3-yl)pyrimidin-2-yl)amino)phenyl)(methyl)amino)propyl)-2-amino-4-methylpentanamide',
    '10l': '(S)-N-(3-((2-Acrylamido-5-methoxy-4-((4-(1-methyl-1H-indol-3-yl)pyrimidin-2-yl)amino)phenyl)(methyl)amino)propyl)pyrrolidine-2-carboxamide',
    '10m': '(2R,3R)-N-(3-((2-Acrylamido-5-methoxy-4-((4-(1-methyl-1H-indol-3-yl)pyrimidin-2-yl)amino)phenyl)(methyl)amino)propyl)-2-amino-3-methylpentanamide',
    '10n': '(R)-N-(2-((3-(2-Amino-3-phenylpropanamido)propyl)(methyl)amino)-4-methoxy-5-((4-(1-methyl-1H-indol-3-yl)pyrimidin-2-yl)amino)phenyl)acrylamide',
    '10o': '(R)-N-(3-((2-Acrylamido-5-methoxy-4-((4-(1-methyl-1H-indol-3-yl)pyrimidin-2-yl)amino)phenyl)(methyl)amino)propyl)-2-amino-3-methylbutanamide'
}


def normalize_missing_values(value: object):
    if pd.isna(value):
        return None
    text = str(value).strip().lower()
    if text in MISSING_TOKENS:
        return None
    return value


def iupac_to_smiles_via_opsin(iupac_name: str) -> str | None:
    clean_name = " ".join(iupac_name.split())
    encoded_name = urllib.parse.quote(clean_name)
    url = f"https://opsin.ch.cam.ac.uk/opsin/{encoded_name}.json"
    try:
        response = requests.get(url, timeout=15)
        json_data = response.json()
        if json_data.get('status') == 'SUCCESS':
            return json_data.get('smiles')
    except Exception:
        pass
    return None


def resolve_pdf_compounds_smiles(df: pd.DataFrame, smiles_col: str = 'compound_smiles', name_col: str = 'compound_name') -> pd.DataFrame:
    df_resolved = df.copy()
    
    local_map_path = ROOT / "smiles_mapping.json"
    smiles_mapping = {}
    if local_map_path.is_file():
        try:
            with local_map_path.open('r', encoding='utf-8') as f:
                smiles_mapping = json.load(f)
        except Exception:
            pass

    print("Resolving PDF paper compound IDs to SMILES structures...")
    for comp_id, iupac in COMPOUNDS_IUPAC.items():
        if comp_id not in smiles_mapping or smiles_mapping[comp_id] == "CONVERSION_FAILED":
            smiles = iupac_to_smiles_via_opsin(iupac)
            if smiles:
                smiles_mapping[comp_id] = smiles
            else:
                smiles_mapping[comp_id] = "CONVERSION_FAILED"

    def map_smiles(row):
        current_smiles = row[smiles_col]
        if pd.isna(current_smiles) or str(current_smiles).strip() == '':
            name = str(row[name_col]).strip()
            if name in smiles_mapping and smiles_mapping[name] != "CONVERSION_FAILED":
                return smiles_mapping[name]
        return current_smiles

    df_resolved[smiles_col] = df_resolved.apply(map_smiles, axis=1)
    return df_resolved


def get_smiles_from_pubchem(name: str) -> str | None:
    try:
        import pubchempy as pcp
        results = pcp.get_compounds(name, 'name')
        if results:
            return results[0].smiles
        return None
    except Exception as e:
        print(f"Warning: Failed to retrieve SMILES from PubChem for {name}: {e}")
        return None


def get_canonical_smiles(smiles: object) -> str | None:
    if pd.isna(smiles) or not isinstance(smiles, str):
        return None
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol:
            remover = SaltRemover.SaltRemover()
            mol = remover.StripMol(mol, dontRemoveEverything=True)
            return Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)
        return None
    except Exception:
        return None


def calculate_pchembl(value_nm: float) -> float | None:
    if pd.isna(value_nm) or value_nm <= 0:
        return np.nan
    try:
        return round(9.0 - math.log10(value_nm), 3)
    except Exception:
        return np.nan


def clean_initial_garbage(df: pd.DataFrame) -> pd.DataFrame:
    df_cleaned = df.copy()
    
    bio_cols = ['standard_value', 'standard_type', 'standard_units']
    name_col = 'compound_name'
    smiles_col = 'compound_smiles'

    for col in df_cleaned.columns:
        df_cleaned[col] = df_cleaned[col].map(normalize_missing_values)

    df_cleaned = df_cleaned.dropna(subset=bio_cols, how='any')
    df_cleaned = df_cleaned.dropna(subset=[name_col, smiles_col], how='all')
    
    return df_cleaned


def normalize_activity_data(df: pd.DataFrame, smiles_col: str = 'compound_smiles') -> pd.DataFrame:
    df_clean = df.copy()

    valid_types = ['IC50', 'Ki', 'Kd', 'EC50']
    df_clean = df_clean[df_clean['standard_type'].isin(valid_types)].copy()

    def extract_from_raw(row):
        rel = row['standard_relation']
        val = row['standard_value']

        if pd.notna(rel) and str(rel).strip() != '':
            return rel, val

        if isinstance(val, str):
            s = val.strip()
            found_rel = "="
            for op in [">=", "<=", ">", "<", "="]:
                if s.startswith(op):
                    found_rel = op
                    s = s[len(op):].strip()
                    break
            try:
                num_s = re.sub(r'[^\d\.\-eE]', '', s)
                return found_rel, float(num_s)
            except ValueError:
                return found_rel, np.nan

        return "=", val

    extracted = df_clean.apply(extract_from_raw, axis=1, result_type='expand')
    df_clean['standard_relation'] = extracted[0]
    df_clean['standard_value'] = extracted[1]

    relation_mapping = {
        '=': '=', '~': '=', '>>': '>', '>': '>', '<': '<', '>=': '>=', '<=': '<='
    }
    df_clean['standard_relation'] = df_clean['standard_relation'].astype(str).map(lambda x: relation_mapping.get(x, '='))

    def convert_row_to_nm(row):
        val = row['standard_value']
        unit = row['standard_units']
        smiles = row.get(smiles_col, None)

        if pd.isna(val) or pd.isna(unit):
            return np.nan

        try:
            val = float(val)
        except (TypeError, ValueError):
            return np.nan

        unit_str = str(unit).strip()
        if unit_str == 'nM':
            return val
        elif unit_str in ('uM', 'μm', 'µm', 'micromolar'):
            return val * 1000.0
        elif unit_str == '10^3 uM':
            return val * 1_000_000.0
        elif unit_str == '10^-5 mol/L':
            return val * 10_000.0
        elif unit_str == '10^-2M':
            return val * 10_000_000.0
        elif unit_str == 'ug.mL-1':
            if pd.isna(smiles) or not isinstance(smiles, str):
                return np.nan
            try:
                mol = Chem.MolFromSmiles(smiles)
                if mol:
                    mw = Descriptors.MolWt(mol)
                    return (val / mw) * 1_000_000.0
            except Exception:
                pass
        return np.nan

    df_clean['normalized_value_nm'] = df_clean.apply(convert_row_to_nm, axis=1)
    df_clean = df_clean.dropna(subset=['normalized_value_nm']).copy()

    df_clean['standard_value'] = df_clean['normalized_value_nm']
    df_clean['standard_units'] = 'nM'
    df_clean = df_clean.drop(columns=['normalized_value_nm'])

    return df_clean


def extract_experiment_details(df: pd.DataFrame, notes_col: str = 'notes', smiles_col: str = 'compound_smiles') -> pd.DataFrame:
    df_extracted = df.copy()

    egfr_variants = []
    assay_types = []
    cell_lines = []
    atp_concs = []
    covalent_flags = []

    try:
        acrylamide_pattern = Chem.MolFromSmarts('[CX3]=[CX3][CX3](=[OX1])[NX3]')
    except Exception:
        acrylamide_pattern = None

    known_cells = {
        'a431': 'A431',
        'h1975': 'H1975',
        'pc-9': 'PC-9',
        'pc9': 'PC-9',
        'hcc827': 'HCC827',
        'ba/f3': 'Ba/F3',
        'baf3': 'Ba/F3',
        'a549': 'A549'
    }

    for idx, row in df_extracted.iterrows():
        note_text = str(row.get(notes_col, '')).strip()
        smiles = row.get(smiles_col, None)
        note_lower = note_text.lower() if note_text else ""

        # A. EGFR Variant Extraction
        existing_variant = row.get('egfr_variant', np.nan)
        if existing_variant is not None and not pd.isna(existing_variant):
            variant = existing_variant
        else:
            if not note_text or note_lower in ['nan', 'none', '']:
                variant = None
            elif re.search(r'\b(?:wild[- ]type|wt|wildtype)\b', note_lower):
                variant = 'WT'
            elif re.search(r'\b(?:del[eE]746[-_][aA]750|d746[-_]750|exon\s*19\s*del|ex19del)\b', note_lower):
                variant = 'delE746_A750'
            else:
                found_muts = re.findall(r'\b[A-Z]\d{3,4}[A-Z]\b', note_text)
                if found_muts:
                    unique_muts = sorted(list(set(found_muts)))
                    variant = '_'.join(unique_muts)
                else:
                    variant = None
        egfr_variants.append(variant)

        # B. Cell Line Extraction
        existing_cell = row.get('cell_line', np.nan)
        if existing_cell is not None and not pd.isna(existing_cell):
            cell = existing_cell
        else:
            cell = None
            if note_text and note_lower not in ['nan', 'none', '']:
                for key, val in known_cells.items():
                    if key in note_lower:
                        cell = val
                        break
        cell_lines.append(cell)

        # C. Assay Type Extraction
        existing_assay = row.get('assay_type', np.nan)
        if existing_assay is not None and not pd.isna(existing_assay):
            assay_type = existing_assay
        else:
            if cell is not None:
                assay_type = 'cellular'
            elif note_text and note_lower not in ['nan', 'none', '']:
                if any(kw in note_lower for kw in ['cell', 'cellular', 'proliferation', 'viability', 'growth']):
                    assay_type = 'cellular'
                elif any(kw in note_lower for kw in ['enzymatic', 'kinase assay', 'binding', 'htrf', 'adp-glo', 'recombinant']):
                    assay_type = 'enzymatic'
                else:
                    assay_type = None
            else:
                assay_type = None
        assay_types.append(assay_type)

        # D. ATP Concentration Extraction
        existing_atp = row.get('atp_concentration_uM', np.nan)
        if existing_atp is not None and not pd.isna(existing_atp):
            try:
                atp_val = float(existing_atp)
            except ValueError:
                atp_val = None
        else:
            atp_val = None
            if note_text and note_lower not in ['nan', 'none', '']:
                m1 = re.search(r'(\d+(?:\.\d+)?)\s*(?:um|μm|micromolar)\s*(?:of\s+)?atp', note_lower)
                if m1:
                    atp_val = float(m1.group(1))
                else:
                    m2 = re.search(r'atp\s*(?:conc|concentration|at)?\s*(?:is)?\s*(\d+(?:\.\d+)?)\s*(?:um|μm|micromolar)', note_lower)
                    if m2:
                        atp_val = float(m2.group(1))
        atp_concs.append(atp_val)

        # E. Covalent Flag Extraction
        existing_covalent = row.get('covalent_flag', np.nan)
        if pd.notna(existing_covalent) and str(existing_covalent).strip().lower() not in ['', 'nan', 'none', 'null']:
            if isinstance(existing_covalent, bool):
                is_covalent = existing_covalent
            else:
                is_covalent = str(existing_covalent).lower() in ['true', '1', 'yes', 'covalent']
        else:
            is_covalent = False
            if note_text and note_lower not in ['nan', 'none', ''] and any(kw in note_lower for kw in ['covalent', 'irreversible']):
                is_covalent = True
            elif pd.notna(smiles) and acrylamide_pattern:
                try:
                    mol = Chem.MolFromSmiles(smiles)
                    if mol and mol.HasSubstructMatch(acrylamide_pattern):
                        is_covalent = True
                except Exception:
                    pass
        covalent_flags.append(is_covalent)

    df_extracted['egfr_variant'] = egfr_variants
    df_extracted['assay_type'] = assay_types
    df_extracted['cell_line'] = cell_lines
    df_extracted['atp_concentration_uM'] = atp_concs
    df_extracted['covalent_flag'] = covalent_flags

    return df_extracted


def generate_inchikeys(df: pd.DataFrame, smiles_col: str) -> pd.DataFrame:
    inchikeys = []
    for smiles in df[smiles_col]:
        try:
            mol = Chem.MolFromSmiles(smiles)
            ikey = Chem.MolToInchiKey(mol) if mol else np.nan
        except Exception:
            ikey = np.nan
        inchikeys.append(ikey)
    df_copy = df.copy()
    df_copy['inchikey'] = inchikeys
    return df_copy.dropna(subset=['inchikey']).copy()


def deduplicate_bioactivity_dataset(df: pd.DataFrame, smiles_col: str = 'compound_smiles') -> pd.DataFrame:
    if 'inchikey' not in df.columns:
        df_working = generate_inchikeys(df, smiles_col)
    else:
        df_working = df.copy()
        df_working = df_working.dropna(subset=['inchikey']).copy()

    df_working['standard_relation'] = df_working['standard_relation'].fillna('=')

    exact_mask = df_working['standard_relation'].isin(['=', '~'])
    df_exact = df_working[exact_mask].copy()
    df_censored = df_working[~exact_mask].copy()

    group_cols = ['inchikey', 'egfr_variant', 'assay_type', 'standard_units']

    deduplicated_exact_rows = []
    conflict_count = 0

    for keys, group in df_exact.groupby(group_cols):
        if len(group) == 1:
            deduplicated_exact_rows.append(group.iloc[0])
        else:
            p_values = group['pchembl_value'].values
            span = np.max(p_values) - np.min(p_values)

            if span <= 1.0:
                median_p = np.median(p_values)
                median_val_nm = 10 ** (9.0 - median_p)

                representative_row = group.iloc[0].copy()
                representative_row['pchembl_value'] = median_p
                representative_row['standard_value'] = median_val_nm
                representative_row['standard_relation'] = '='

                src_col = 'source_id' if 'source_id' in group.columns else 'source_reference'
                if src_col in group.columns:
                    all_sources = "; ".join(group[src_col].dropna().astype(str).unique())
                    representative_row[src_col] = all_sources if all_sources else np.nan

                deduplicated_exact_rows.append(representative_row)
            else:
                conflict_count += 1

    if len(deduplicated_exact_rows) > 0:
        df_exact_dedup = pd.DataFrame(deduplicated_exact_rows)
    else:
        df_exact_dedup = pd.DataFrame(columns=df_working.columns)

    if len(df_censored) > 0 and len(df_exact_dedup) > 0:
        exact_keys = set(df_exact_dedup[group_cols].apply(tuple, axis=1))
        df_censored_filtered = df_censored[~df_censored[group_cols].apply(tuple, axis=1).isin(exact_keys)].copy()
    else:
        df_censored_filtered = df_censored.copy()

    if len(df_censored_filtered) > 0:
        df_censored_dedup = df_censored_filtered.sort_values('standard_value', ascending=False).drop_duplicates(subset=group_cols, keep='first')
    else:
        df_censored_dedup = pd.DataFrame(columns=df_working.columns)

    print(f"  Conflict groups removed (pChEMBL range > 1.0): {conflict_count}")
    df_final = pd.concat([df_exact_dedup, df_censored_dedup], ignore_index=True)
    return df_final


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df_resolved = resolve_pdf_compounds_smiles(df, smiles_col='compound_smiles', name_col='compound_name')
    
    print("Executing initial garbage collection...")
    df_clean = clean_initial_garbage(df_resolved)
    print(f"  Rows remaining: {len(df_clean)}")

    missing_smiles_mask = df_clean['compound_smiles'].isna() & df_clean['compound_name'].notna()
    names_to_search = df_clean.loc[missing_smiles_mask, 'compound_name'].unique()
    if len(names_to_search) > 0:
        print(f"Searching PubChem for missing SMILES: {names_to_search}")
        web_pubchem_map = {}
        for name in names_to_search:
            smiles = get_smiles_from_pubchem(name)
            if smiles:
                web_pubchem_map[name] = smiles
            time.sleep(0.5)

        df_clean['compound_smiles'] = df_clean.apply(
            lambda row: web_pubchem_map.get(row['compound_name'], row['compound_smiles'])
            if pd.isna(row['compound_smiles']) else row['compound_smiles'],
            axis=1
        )
        df_clean = df_clean.dropna(subset=['compound_smiles']).copy()

    print("Normalizing biological activity values and concentration units...")
    df_normalized = normalize_activity_data(df_clean, smiles_col='compound_smiles')
    print(f"  Rows remaining: {len(df_normalized)}")

    print("Extracting biological assay parameters and covalent flags...")
    df_extracted = extract_experiment_details(df_normalized, notes_col='notes', smiles_col='compound_smiles')
    
    print("Filtering rows with undefined EGFR target variants...")
    df_extracted = df_extracted.dropna(subset=['egfr_variant']).copy()
    print(f"  Rows remaining: {len(df_extracted)}")

    print("Standardizing SMILES and stripping salt counter-ions...")
    df_extracted['compound_smiles'] = df_extracted['compound_smiles'].apply(get_canonical_smiles)
    df_extracted = df_extracted.dropna(subset=['compound_smiles']).copy()
    print(f"  Rows remaining: {len(df_extracted)}")

    print("Calculating log-scale pChEMBL values...")
    df_extracted['pchembl_value'] = df_extracted['standard_value'].apply(calculate_pchembl)

    print("Executing biological and chemical consensus deduplication...")
    df_final = deduplicate_bioactivity_dataset(df_extracted, smiles_col='compound_smiles')
    print(f"  Final rows remaining: {len(df_final)}")

    return df_final


def load_schema_columns() -> list[str]:
    with SCHEMA_PATH.open(encoding="utf-8") as f:
        schema = json.load(f)
    return [field["name"] for field in schema["fields"]]


def load_input_frame() -> pd.DataFrame:
    if MERGED_PATH.is_file():
        return pd.read_csv(MERGED_PATH, low_memory=False)
    import importlib.util

    build_path = ROOT / "scripts" / "build_dataset.py"
    spec = importlib.util.spec_from_file_location("build_dataset", build_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {build_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build()


def main() -> None:
    print("Loading merged input frame...")
    df = load_input_frame()
    cleaned = clean_dataframe(df)

    print("Formatting dataset according to schema specifications...")
    columns = load_schema_columns()
    for col in columns:
        if col not in cleaned.columns:
            cleaned[col] = None
    cleaned = cleaned[columns]

    DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(DATASET_PATH, index=False)
    print(f"Successfully wrote {len(cleaned)} cleaned rows to {DATASET_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
