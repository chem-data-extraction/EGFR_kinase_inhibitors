#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_pdf.py

Extracts EGFR kinase inhibitor activity data from PDF sources and supplementary files.
Implements specific, structured parsers for three major sources:
1. Lim et al. (2023) - using hybrid PDF processing or LLama Cloud agentic parsing.
2. Men et al. (2025) - using regex and structural layout extraction via pdfplumber.
3. Damghani et al. (2026) - using layout extraction via pdfplumber.

Outputs a consolidated dataset compliant with the specs/dataset_schema.json format.
"""

import os
import re
import io
import json
import argparse
import logging
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import pandas as pd
import pdfplumber
import pypdf
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "specs/pdf_extraction_manifest.json"
SCHEMA_PATH = ROOT / "specs/dataset_schema.json"
LOG_PATH = ROOT / "data/extracted/extraction_log.jsonl"


def append_log(entry: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def parse_relation_and_value(val_str: Any) -> Tuple[str, Optional[float]]:
    if val_str is None:
        return "=", None
    
    val_str = str(val_str).strip().replace(" ", "").replace(",", "")
    if val_str.upper() in ["NT", "NOTTEST", "N/A", "NAN", "-", ""]:
        return "=", None

    relation = "="
    if val_str.startswith(">"):
        relation = ">"
        val_str = val_str[1:]
    elif val_str.startswith("<"):
        relation = "<"
        val_str = val_str[1:]
    elif val_str.startswith("="):
        relation = "="
        val_str = val_str[1:]

    match = re.search(r"([\d\.]+)", val_str)
    if match:
        try:
            return relation, float(match.group(1))
        except ValueError:
            return "=", None
    return "=", None


def normalize_target(target_name: str) -> str:
    t_clean = str(target_name).strip().upper()
    
    if any(wt_term in t_clean for wt_term in ["WILD-TYPE", "WT", "PARENTAL"]) and "C797S" not in t_clean and "T790M" not in t_clean:
        return "WT"
    
    if "19DEL/T790M/C797S" in t_clean or "DEL19/T790M/C797S" in t_clean:
        return "del19/T790M/C797S"
    if "L858R/T790M/C797S" in t_clean:
        return "L858R/T790M/C797S"
    if "19DEL/C797S" in t_clean or "DEL19/C797S" in t_clean:
        return "del19/C797S"
    if "L858R/C797S" in t_clean:
        return "L858R/C797S"
    if "L858R/T790M" in t_clean or "L858M_T790M" in t_clean:
        return "L858R/T790M"
    if "T790M/C797S" in t_clean:
        return "T790M/C797S"
    if "19DEL" in t_clean or "DEL19" in t_clean:
        return "del19"
    if "L858R" in t_clean:
        return "L858R"
    if "T790M" in t_clean:
        return "T790M"
    if "C797S" in t_clean:
        return "C797S"
        
    return target_name.strip()


async def extract_lim_2023(
    pdf_path: str,
    parsed_md_path: str,
    pages_used: List[int],
    api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    records = []
    
    if os.path.exists(parsed_md_path):
        logger.info(f"Loading pre-parsed markdown for Lim 2023 from: {parsed_md_path}")
        with open(parsed_md_path, "r", encoding="utf-8") as f:
            parsed_content = f.read()
    else:
        if not api_key:
            api_key = os.getenv("LLAMA_CLOUD_API_KEY")
            
        if not api_key:
            logger.warning(
                f"Parsed file {parsed_md_path} not found and LLAMA_CLOUD_API_KEY is missing. "
                "Skipping Llama Cloud extraction for Lim et al. (2023)."
            )
            return []

        if not os.path.exists(pdf_path):
            logger.error(f"Source PDF for Lim 2023 not found at: {pdf_path}")
            return []
            
        trimmed_pdf_path = pdf_path.with_name(pdf_path.stem + "_trimmed.pdf")
        logger.info(f"Trimming first 8 pages of Lim 2023 to: {trimmed_pdf_path}")
        try:
            reader = pypdf.PdfReader(pdf_path)
            writer = pypdf.PdfWriter()
            target_pages = min(8, len(reader.pages))
            for page_idx in range(target_pages):
                writer.add_page(reader.pages[page_idx])
            with open(trimmed_pdf_path, "wb") as out_file:
                writer.write(out_file)
        except Exception as e:
            logger.error(f"Failed to trim PDF: {e}")
            return []

        try:
            from llama_cloud import AsyncLlamaCloud
            logger.info("Initializing Llama Cloud parser...")
            client = AsyncLlamaCloud(api_key=api_key)
            
            logger.info("Uploading trimmed PDF to Llama Cloud...")
            file_obj = await client.files.create(file=trimmed_pdf_path, purpose="parse")
            
            logger.info("Running agentic parser...")
            result = await client.parsing.parse(
                file_id=file_obj.id,
                tier="agentic",
                version="latest",
                expand=["markdown_full", "text_full"],
            )
            parsed_content = result.markdown_full
            
            os.makedirs(os.path.dirname(parsed_md_path), exist_ok=True)
            with open(parsed_md_path, "w", encoding="utf-8") as f:
                f.write(parsed_content)
            logger.info(f"Successfully saved parsed markdown to: {parsed_md_path}")
            
        except ImportError:
            logger.error("llama_cloud package is not installed. Please run 'pip install llama-cloud'")
            return []
        except Exception as e:
            logger.error(f"Llama Cloud parsing failed: {e}")
            return []

    soup = BeautifulSoup(parsed_content, "html.parser")
    current_figure = "Unknown"

    for table in soup.find_all("table"):
        prev_siblings = list(table.find_all_previous(string=True))

        for sib in prev_siblings:
            sib_clean = sib.strip()
            if not sib_clean: 
                continue
            if "Figure 2" in sib_clean: 
                current_figure = "Figure 2"
                break
            elif "Figure 3" in sib_clean: 
                current_figure = "Figure 3"
                break
            elif "Figure 4" in sib_clean: 
                current_figure = "Figure 4"
                break
            elif "Figure 5" in sib_clean: 
                current_figure = "Figure 5"
                break

        try:
            df_temp = pd.read_html(io.StringIO(str(table)))[0]
        except Exception as e:
            logger.warning(f"Could not read table structure with pandas: {e}")
            continue

        if isinstance(df_temp.columns, pd.MultiIndex):
            df_temp.columns = [" ".join([str(level) for level in col]).strip() for col in df_temp.columns]

        if any("Kinase" in str(col) for col in df_temp.columns):
            kinase_col = [c for c in df_temp.columns if "Kinase" in str(c)][0]
            for _, row in df_temp.iterrows():
                kinase_text = str(row[kinase_col])
                bbt_raw = str(row.iloc[1])
                osi_raw = str(row.iloc[2])
                atp_cond = "Km ATP" if "Km" in kinase_text else "1 mmol/L ATP"
                
                mut = "EGFR WT"
                for m in ["19Del/C797S", "19Del/T790M/C797S", "L858R/C797S", "L858R/T790M/C797S"]:
                    if m in kinase_text: 
                        mut = f"EGFR {m}"
                        break

                for raw, comp in [(bbt_raw, "BBT-176"), (osi_raw, "Osimertinib")]:
                    rel, val = parse_relation_and_value(raw)
                    if val is not None:
                        records.append({
                            "compound_name": comp,
                            "egfr_variant": normalize_target(mut),
                            "assay_type": "biochemical",
                            "cell_line": None,
                            "standard_type": "IC50",
                            "standard_relation": rel,
                            "standard_value": val,
                            "standard_units": "nM",
                            "source_id": "paper_lim_2023",
                            "table_origin": f"{current_figure} ({atp_cond})"
                        })

        else:
            mut_col = None
            for col in df_temp.columns:
                if any(key in str(df_temp[col].values) for key in ["Parental", "19Del", "L858R"]):
                    mut_col = col
                    break

            if mut_col is not None:
                compounds = ["Erlotinib", "Afatinib", "Dacomitinib", "Osimertinib", "BBT-176"]
                for _, row in df_temp.iterrows():
                    mut_text = str(row[mut_col])
                    if not any(m in mut_text for m in ["Parental", "WT", "19Del", "L858R"]): 
                        continue

                    for comp in compounds:
                        found_cols = [c for c in df_temp.columns if comp in str(c)]
                        if found_cols:
                            rel, val = parse_relation_and_value(row[found_cols[0]])
                            if val is not None:
                                records.append({
                                    "compound_name": comp,
                                    "egfr_variant": normalize_target(mut_text),
                                    "assay_type": "cellular",
                                    "cell_line": "Ba/F3",
                                    "standard_type": "IC50",
                                    "standard_relation": rel,
                                    "standard_value": val,
                                    "standard_units": "nM",
                                    "source_id": "paper_lim_2023",
                                    "table_origin": f"{current_figure} (Cell growth inhibition)"
                                })

    return records


def extract_damghani_2026(pdf_path: str, pages_used: List[int]) -> List[Dict[str, Any]]:
    records = []
    if not os.path.exists(pdf_path):
        logger.error(f"Source PDF for Damghani 2026 not found at: {pdf_path}")
        return records

    with pdfplumber.open(pdf_path) as pdf:
        text16 = pdf.pages[15].extract_text()
        current_cell_line = "Ba/F3"

        for line in text16.split('\n'):
            line = line.strip()
            if "Ba/F3" in line:
                current_cell_line = "Ba/F3"
            elif "A431" in line:
                current_cell_line = "A431"
            elif "PC-9" in line:
                current_cell_line = "PC-9"

            match = re.search(r'^(.*?)\s+([<>]?[\d\.]+)\s+([<>]?[\d\.]+)\s*$', line)
            if match:
                label = match.group(1).strip()
                val1_str = match.group(2)
                val2_str = match.group(3)
                
                if any(x in label for x in ["Genotype", "Values", "Table", "Author", "ACS"]):
                    continue

                genotype = label
                if "WT (added EGF)" in genotype or "WT amplification" in genotype:
                    genotype = "WT"
                elif "parental del19 genotype" in genotype:
                    genotype = "del19"

                for comp, raw_val in [("BI-4732", val1_str), ("BI-8128", val2_str)]:
                    rel, val = parse_relation_and_value(raw_val)
                    if val is not None:
                        records.append({
                            "compound_name": comp,
                            "egfr_variant": normalize_target(genotype),
                            "assay_type": "cellular",
                            "cell_line": current_cell_line,
                            "standard_type": "IC50",
                            "standard_relation": rel,
                            "standard_value": val,
                            "standard_units": "nM",
                            "source_id": "paper_damghani_2026",
                            "table_origin": "Table 1"
                        })

        text17 = pdf.pages[16].extract_text()
        table2_started = False
        for line in text17.split('\n'):
            line = line.strip()
            if "Biochemical Potencies against" in line:
                table2_started = True
                continue
            if table2_started:
                match = re.search(r'^([A-Z0-9/ ]+)\s+([<>]?[\d\.]+)\s+([<>]?[\d\.]+)\s*$', line)
                if match:
                    target = match.group(1).strip()
                    val1_str = match.group(2)
                    val2_str = match.group(3)
                    
                    for comp, raw_val in [("BI-8128", val1_str), ("BI-4732", val2_str)]:
                        rel, val = parse_relation_and_value(raw_val)
                        if val is not None:
                            records.append({
                                "compound_name": comp,
                                "egfr_variant": normalize_target(target),
                                "assay_type": "biochemical",
                                "cell_line": None,
                                "standard_type": "IC50",
                                "standard_relation": rel,
                                "standard_value": val,
                                "standard_units": "nM",
                                "source_id": "paper_damghani_2026",
                                "table_origin": "Table 2"
                            })
                            
    return records


def extract_men_2025(
    pdf_path: str, 
    pages_used: List[int], 
    supp_pdf_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    records = []
    if not os.path.exists(pdf_path):
        logger.error(f"Source PDF for Men 2025 not found at: {pdf_path}")
        return records

    with pdfplumber.open(pdf_path) as pdf:
        text4 = pdf.pages[3].extract_text()

        t1_matches = re.findall(
            r'\b(10\s*[a-o]|Osimertinib)\s+(\d)\s+([<>]?[\d\.]+)\s+([<>]?[\d\.]+|NT)\b', 
            text4
        )
        for comp_raw, _, val1_str, val2_str in t1_matches:
            comp = comp_raw.replace(" ", "")
            
            rel1, v1 = parse_relation_and_value(val1_str)
            if v1 is not None:
                records.append({
                    "compound_name": comp,
                    "egfr_variant": "L858R/T790M",
                    "assay_type": "cellular",
                    "cell_line": "H1975",
                    "standard_type": "IC50",
                    "standard_relation": rel1,
                    "standard_value": float(v1) * 1000.0,
                    "standard_units": "nM",
                    "source_id": "paper_men_2025",
                    "table_origin": "Table 1"
                })
                
            rel2, v2 = parse_relation_and_value(val2_str)
            if v2 is not None:
                records.append({
                    "compound_name": comp,
                    "egfr_variant": "L858R/T790M",
                    "assay_type": "biochemical",
                    "cell_line": None,
                    "standard_type": "IC50",
                    "standard_relation": rel2,
                    "standard_value": float(v2) * 1000.0,
                    "standard_units": "nM",
                    "source_id": "paper_men_2025",
                    "table_origin": "Table 1"
                })

        osim_t1 = re.search(r'\b(Osimertinib)\s+([<>]?[\d\.]+)\s+([<>]?[\d\.]+|NT)\b', text4)
        if osim_t1:
            val1_str, val2_str = osim_t1.group(2), osim_t1.group(3)
            rel1, v1 = parse_relation_and_value(val1_str)
            if v1 is not None:
                records.append({
                    "compound_name": "Osimertinib",
                    "egfr_variant": "L858R/T790M",
                    "assay_type": "cellular",
                    "cell_line": "H1975",
                    "standard_type": "IC50",
                    "standard_relation": rel1,
                    "standard_value": float(v1) * 1000.0,
                    "standard_units": "nM",
                    "source_id": "paper_men_2025",
                    "table_origin": "Table 1"
                })
            rel2, v2 = parse_relation_and_value(val2_str)
            if v2 is not None:
                records.append({
                    "compound_name": "Osimertinib",
                    "egfr_variant": "L858R/T790M",
                    "assay_type": "biochemical",
                    "cell_line": None,
                    "standard_type": "IC50",
                    "standard_relation": rel2,
                    "standard_value": float(v2) * 1000.0,
                    "standard_units": "nM",
                    "source_id": "paper_men_2025",
                    "table_origin": "Table 1"
                })

        t2_matches = re.findall(
            r'\b(10\s*[a-o]|Osimertinib)\s+([<>]?[\d\.]+|NT)\s+([<>]?[\d\.]+|NT)\s+([<>]?[\d\.]+|NT)\s+([<>]?[\d\.]+|NT)\b', 
            text4
        )
        for comp_raw, pc9_val, a549_val, t790m_val, wt_val in t2_matches:
            comp = comp_raw.replace(" ", "")
            targets_map = [
                (pc9_val, "del19", "cellular", "PC-9"),
                (a549_val, "WT", "cellular", "A549"),
                (t790m_val, "T790M", "biochemical", None),
                (wt_val, "WT", "biochemical", None)
            ]
            for val_str, target, assay, cell in targets_map:
                rel, v = parse_relation_and_value(val_str)
                if v is not None:
                    records.append({
                        "compound_name": comp,
                        "egfr_variant": normalize_target(target),
                        "assay_type": assay,
                        "cell_line": cell,
                        "standard_type": "IC50",
                        "standard_relation": rel,
                        "standard_value": float(v) * 1000.0,
                        "standard_units": "nM",
                        "source_id": "paper_men_2025",
                        "table_origin": "Table 2"
                    })

    if supp_pdf_path and os.path.exists(supp_pdf_path):
        logger.info(f"Parsing Men 2025 supplementary file: {supp_pdf_path}")
        with pdfplumber.open(supp_pdf_path) as supp_pdf:
            for page_idx in range(min(4, len(supp_pdf.pages))):
                text = supp_pdf.pages[page_idx].extract_text()
                s1_matches = re.findall(
                    r'\b(9\s*[a-o]|10\s*[a-o])\s+(\d)\s+([<>]?[\d\.]+\s*(?:%|μM|µM)[a-zA-Z]*|NT)\b', 
                    text
                )
                for comp_raw, _, val_str in s1_matches:
                    comp = comp_raw.replace(" ", "")
                    rel, clean_val = parse_relation_and_value(val_str)
                    if clean_val is not None:
                        if "%" in val_str:
                            metric = "Inhibition Rate"
                            multiplier = 1.0
                            unit = "%"
                        else:
                            metric = "IC50"
                            multiplier = 1000.0
                            unit = "nM"

                        records.append({
                            "compound_name": comp,
                            "egfr_variant": "L858R/T790M",
                            "assay_type": "cellular",
                            "cell_line": "H1975",
                            "standard_type": metric,
                            "standard_relation": rel,
                            "standard_value": float(clean_val) * multiplier,
                            "standard_units": unit,
                            "source_id": "supp_men_2025",
                            "table_origin": "Table S1"
                        })

            text4 = supp_pdf.pages[3].extract_text()
            if "Table S2" in text4:
                t2_part = text4.split("Table S2")[1]
                s2_matches = re.findall(r'\b(9\s*[a-o]|10\s*[a-o]|Osimertinib)\s+([<>]?[\d\.]+)\b', t2_part)
                for comp_raw, val_str in s2_matches:
                    comp = comp_raw.replace(" ", "")
                    rel, clean_val = parse_relation_and_value(val_str)
                    if clean_val is not None:
                        records.append({
                            "compound_name": comp,
                            "egfr_variant": "WT",
                            "assay_type": "biochemical",
                            "cell_line": None,
                            "standard_type": "IC50",
                            "standard_relation": rel,
                            "standard_value": float(clean_val),
                            "standard_units": "nM",
                            "source_id": "supp_men_2025",
                            "table_origin": "Table S2"
                        })
    else:
        logger.warning(f"Supplementary PDF for Men 2025 not found or skipped: {supp_pdf_path}")

    return records


async def run_pipeline() -> None:
    if not MANIFEST.exists():
        logger.error(f"Manifest not found at {MANIFEST}")
        return

    with MANIFEST.open(encoding="utf-8") as f:
        manifest = json.load(f)

    print(manifest.get("pdf_extraction_process", "PDF extraction"))
    
    output_records_rel = manifest.get("output_records_file", "data/extracted/pdf_extracted_records.csv")
    output_records_path = ROOT / output_records_rel
    output_records_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Output: {output_records_path}")
    print("\nPDFs to process:")

    all_records = []

    for src in manifest.get("input_sources", []):
        pdf_id = src.get("pdf_id")
        pdf_path_rel = src.get("pdf_path")
        pdf_path = ROOT / pdf_path_rel
        source_id = src.get("source_id")
        pages_used = src.get("pages_used", [])
        status_in_manifest = src.get("extraction_status", "pending")

        print(f"  - {pdf_id}: {pdf_path_rel} (source_id={source_id}, status={status_in_manifest})")

        if not pdf_path.exists():
            logger.error(f"PDF File {pdf_path.name} not found at {pdf_path}")
            append_log({
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "step": "pdf_extraction",
                "source_id": source_id,
                "status": "failed",
                "tool": "extract_pdf.py",
                "output": str(output_records_rel),
                "issue": f"File not found: {pdf_path_rel}"
            })
            continue

        extracted_subset = []

        try:
            if pdf_id == "paper_lim_2023":
                parsed_md_path = pdf_path.parent / (pdf_path.stem + "_parsed.md")
                extracted_subset = await extract_lim_2023(
                    pdf_path=pdf_path,
                    parsed_md_path=parsed_md_path,
                    pages_used=pages_used
                )
            elif pdf_id == "paper_damghani_2026":
                extracted_subset = extract_damghani_2026(
                    pdf_path=pdf_path,
                    pages_used=pages_used
                )
            elif pdf_id == "paper_men_2025":
                supp_pdf_path = pdf_path.parent / "supp_men_2025.pdf"
                extracted_subset = extract_men_2025(
                    pdf_path=pdf_path,
                    pages_used=pages_used,
                    supp_pdf_path=supp_pdf_path if supp_pdf_path.exists() else None
                )
            else:
                logger.warning(f"Unknown pdf_id {pdf_id} specified in manifest.")
                continue

            all_records.extend(extracted_subset)
            status = "success" if extracted_subset else "warning"
            issue = None if extracted_subset else "No records could be extracted from this PDF"
            
            print(f"    ✓ Extracted {len(extracted_subset)} records from {pdf_id}")
            
            append_log({
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "step": "pdf_extraction",
                "source_id": source_id,
                "status": status,
                "tool": "extract_pdf.py",
                "output": str(output_records_rel),
                "records_extracted": len(extracted_subset),
                "issue": issue
            })
            
        except Exception as e:
            logger.error(f"    ✗ Pipeline crashed on {pdf_id}: {e}")
            append_log({
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "step": "pdf_extraction",
                "source_id": source_id,
                "status": "failed",
                "tool": "extract_pdf.py",
                "output": str(output_records_rel),
                "issue": str(e)
            })

    if all_records:
        df = pd.DataFrame(all_records)
        
        with SCHEMA_PATH.open(encoding="utf-8") as f:
            schema = json.load(f)
        schema_cols = [field["name"] for field in schema["fields"]]    
                
        extra_cols = [c for c in df.columns if c not in schema_cols]
        final_cols = schema_cols + extra_cols
        df = df[final_cols]
        
        df.to_csv(output_records_path, index=False, encoding="utf-8")
        
        print(f"\nExtraction complete! Consolidated records: {len(df)}")
        print(f"Saved into: {output_records_path.relative_to(ROOT)}")
    else:
        logger.error("No entries extracted from any of the sources.")


def main():
    asyncio.run(run_pipeline())


if __name__ == "__main__":
    main()
