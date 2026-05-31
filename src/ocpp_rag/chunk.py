import re
import json
import argparse
from pathlib import Path
from .config import (
    PARSED_DIR, CHUNKS_DIR, SCHEMAS_DIR, APPENDICES_DIR,
    ALL_DOCS, FUNCTIONAL_BLOCKS,
)

MAX_CHUNK_SIZE = 2500
MIN_CHUNK_SIZE = 50
OVERLAP_LINES = 3


def clean_text(text):
    text = re.sub(
        r"OCPP 2\.0\.1 Edition 4 - . Open Charge Alliance 2025\s+\d+/\d+\s+Part \d+ - \w+",
        "", text,
    )
    text = re.sub(r"^Edition 4, 2025-12-03.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\[PAGE \d+\]\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^---\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    text = re.sub(r"&#x26;", "&", text)
    text = re.sub(r"&#x\w+;", "", text)
    text = re.sub(r"^\d+/\d+\s*$", "", text, flags=re.MULTILINE)
    return text.strip()


def extract_page_numbers(text):
    pages = re.findall(r"\[PAGE (\d+)\]", text)
    if pages:
        return sorted(set(int(p) for p in pages))
    page_refs = re.findall(r"(\d+)/\d+\s+Part", text)
    if page_refs:
        return sorted(set(int(p) for p in page_refs))
    return []


def parse_sections(md_text):
    lines = md_text.split("\n")
    sections = []
    current_heading = None
    current_level = 0
    current_lines = []
    current_page = None

    for line in lines:
        page_match = re.match(r"^\[PAGE (\d+)\]", line)
        if page_match:
            current_page = int(page_match.group(1))
            continue

        heading_match = re.match(r"^(#{1,4})\s+(.+)$", line)
        if heading_match:
            if current_heading is not None:
                sections.append({
                    "heading": current_heading,
                    "level": current_level,
                    "content": "\n".join(current_lines),
                    "start_page": sections[-1].get("start_page") if sections else current_page,
                })
            current_heading = heading_match.group(2).strip()
            current_level = len(heading_match.group(1))
            current_lines = [line]
            if current_page:
                sections_start_page = current_page
        else:
            current_lines.append(line)

    if current_heading is not None:
        sections.append({
            "heading": current_heading,
            "level": current_level,
            "content": "\n".join(current_lines),
            "start_page": current_page,
        })

    return sections


def classify_section_201(heading):
    uc_match = re.match(r"^([A-P])(\d{2})\s*-\s*(.+?)(\s*-\s*Requirements)?$", heading)
    if uc_match:
        block_letter = uc_match.group(1)
        uc_num = uc_match.group(2)
        uc_name = uc_match.group(3).strip()
        is_req = bool(uc_match.group(4))
        return {
            "content_type": "requirements" if is_req else "use_case",
            "use_case_id": f"{block_letter}{uc_num}",
            "use_case_name": uc_name,
            "functional_block": FUNCTIONAL_BLOCKS.get(block_letter, block_letter),
        }

    block_match = re.match(r"^([A-P])\.\s+(.+)$", heading)
    if block_match:
        letter = block_match.group(1)
        return {
            "content_type": "block_intro",
            "functional_block": FUNCTIONAL_BLOCKS.get(letter, letter),
        }

    if re.match(r"^Figure \d+", heading):
        return {"content_type": "figure"}

    if re.match(r"^\d+\.\d+\.\d+\.", heading):
        return {"content_type": "message_or_type"}

    if heading.startswith("1. Messages"):
        return {"content_type": "messages_section"}
    if heading.startswith("2. Datatypes"):
        return {"content_type": "datatypes_section"}
    if heading.startswith("3. Enumerations"):
        return {"content_type": "enumerations_section"}

    return {"content_type": "general"}


def classify_section_16(heading):
    uc_match = re.match(r"^(\d+\.\d+)\.\s+(.+)$", heading)
    if uc_match:
        return {
            "content_type": "message_or_type",
            "section_id": uc_match.group(1),
        }
    return {"content_type": "general"}


def is_toc_or_empty(section):
    content = section["content"].strip()
    lines = [l.strip() for l in content.split("\n") if l.strip()]
    if len(lines) <= 2:
        return True
    non_heading = [l for l in lines if not l.startswith("#")]
    if not non_heading:
        return True
    body_text = " ".join(non_heading)
    if len(body_text) < 40:
        return True
    return False


def split_large_chunk(content, max_size=MAX_CHUNK_SIZE):
    if len(content) <= max_size:
        return [content]

    parts = []
    lines = content.split("\n")
    current_part = []
    current_len = 0
    in_table = False

    for line in lines:
        is_table_sep = bool(re.match(r"^\|[\s\-:|]+\|$", line.strip()))
        is_table_row = line.strip().startswith("|") and not is_table_sep

        current_part.append(line)
        current_len += len(line) + 1

        if is_table_sep:
            in_table = True
            continue
        if in_table and not is_table_row:
            in_table = False

        should_split = False
        if not in_table and current_len > max_size * 0.7:
            should_split = True
        elif current_len > max_size * 1.5:
            should_split = True

        if should_split:
            text = "\n".join(current_part).strip()
            if text:
                parts.append(text)
            current_part = []
            current_len = 0
            in_table = False

    if current_part:
        text = "\n".join(current_part).strip()
        if text:
            parts.append(text)

    return parts


def build_heading_path(sections, current_idx):
    current = sections[current_idx]
    path = [current["heading"]]
    target_level = current["level"]

    for i in range(current_idx - 1, -1, -1):
        sec = sections[i]
        if sec["level"] < target_level:
            path.insert(0, sec["heading"])
            target_level = sec["level"]
        if target_level <= 1:
            break

    return " > ".join(path)


def extract_cross_refs(content):
    uc_refs = set(re.findall(r"\b([A-P]\d{2})\b", content))
    req_refs = set(re.findall(r"\b([A-P]\d{2}\.FR\.\d{2,3})\b", content))
    msg_refs = set(re.findall(r"\b(\w+(?:Request|Response))\b", content))
    return {
        "use_case_refs": sorted(uc_refs) if uc_refs else [],
        "requirement_refs": sorted(req_refs) if req_refs else [],
        "message_refs": sorted(msg_refs) if msg_refs else [],
    }


def chunk_plaintext_by_page(md_path, doc_id, doc_info):
    with open(md_path) as f:
        raw = f.read()

    pages = re.split(r"\n\[PAGE (\d+)\]\n", raw)
    chunks = []
    current_page = None

    i = 0
    while i < len(pages):
        if i + 1 < len(pages) and pages[i].strip() == "":
            current_page = int(pages[i + 1]) if pages[i + 1].isdigit() else None
            text = pages[i + 2] if i + 2 < len(pages) else ""
            i += 3
        else:
            text = pages[i]
            i += 1

        if current_page is None and not text.strip():
            continue

        text = text.strip()
        if len(text) < MIN_CHUNK_SIZE:
            continue

        # Try to detect a heading from the first non-empty line
        lines = [l for l in text.split("\n") if l.strip()]
        heading = lines[0].strip()[:100] if lines else f"Page {current_page}"

        refs = extract_cross_refs(text)
        metadata = {
            "doc_id": doc_id,
            "doc_title": doc_info["title"],
            "ocpp_version": doc_info.get("ocpp_version"),
            "content_type": "general",
            "heading": heading,
            "heading_path": heading,
        }
        if current_page:
            metadata["page_number"] = current_page
        if refs["use_case_refs"]:
            metadata["use_case_refs"] = ", ".join(refs["use_case_refs"])
        if refs["message_refs"]:
            metadata["message_refs"] = ", ".join(refs["message_refs"])

        for part_idx, part in enumerate(split_large_chunk(text)):
            chunk_meta = dict(metadata)
            if part_idx > 0:
                chunk_meta["chunk_part"] = part_idx + 1
            chunks.append({"content": part, "metadata": chunk_meta})

    return chunks


def chunk_markdown(md_path, doc_id, doc_info):
    with open(md_path) as f:
        raw = f.read()

    # If no markdown headings found, fall back to page-based chunking
    if not re.search(r"^#{1,4}\s+", raw, re.MULTILINE):
        return chunk_plaintext_by_page(md_path, doc_id, doc_info)

    page_numbers = extract_page_numbers(raw)
    cleaned = clean_text(raw)
    sections = parse_sections(raw)

    is_201_part2 = doc_id == "ocpp201_part2"
    is_16 = doc_info.get("ocpp_version") == "1.6"

    chunks = []
    current_block = None
    current_use_case = None

    for idx, sec in enumerate(sections):
        if is_toc_or_empty(sec):
            continue

        heading = sec["heading"]

        if is_201_part2:
            info = classify_section_201(heading)
        elif is_16:
            info = classify_section_16(heading)
        else:
            info = {"content_type": "general"}

        content_type = info.get("content_type", "general")

        if content_type == "figure":
            continue

        if content_type == "block_intro":
            current_block = info.get("functional_block")
            current_use_case = None
        elif content_type in ("use_case", "requirements"):
            current_use_case = info.get("use_case_id")
            if not current_block:
                uc_id = info.get("use_case_id", "")
                if uc_id and uc_id[0] in FUNCTIONAL_BLOCKS:
                    current_block = FUNCTIONAL_BLOCKS[uc_id[0]]

        content = clean_text(sec["content"])
        if len(content) < MIN_CHUNK_SIZE:
            continue

        heading_path = build_heading_path(sections, idx)

        metadata = {
            "doc_id": doc_id,
            "doc_title": doc_info["title"],
            "ocpp_version": doc_info.get("ocpp_version"),
            "content_type": content_type,
            "heading": heading,
            "heading_path": heading_path,
        }

        if sec.get("start_page"):
            metadata["page_number"] = sec["start_page"]

        if current_block:
            metadata["functional_block"] = current_block
        if current_use_case:
            metadata["use_case_id"] = current_use_case

        uc_id = info.get("use_case_id")
        if uc_id:
            metadata["use_case_id"] = uc_id
        uc_name = info.get("use_case_name")
        if uc_name:
            metadata["use_case_name"] = uc_name

        refs = extract_cross_refs(content)
        if refs["use_case_refs"]:
            metadata["use_case_refs"] = ", ".join(refs["use_case_refs"])
        if refs["message_refs"]:
            metadata["message_refs"] = ", ".join(refs["message_refs"])

        fig_refs = re.findall(r"Figure (\d+[a-z]?)\.", content)
        if fig_refs:
            metadata["figure_refs"] = ", ".join(fig_refs)

        content_parts = split_large_chunk(content)
        for part_idx, part in enumerate(content_parts):
            chunk_meta = dict(metadata)
            if len(content_parts) > 1:
                chunk_meta["chunk_part"] = part_idx + 1
                chunk_meta["total_parts"] = len(content_parts)
            chunks.append({"content": part, "metadata": chunk_meta})

    return chunks


def chunk_json_schemas(schemas_path):
    if not schemas_path.exists():
        return []

    with open(schemas_path) as f:
        schemas = json.load(f)

    chunks = []
    for schema in schemas:
        msg_name = schema.get("message_name", "Unknown")
        direction = "Request" if msg_name.endswith("Request") else "Response"
        base_name = re.sub(r"(Request|Response)$", "", msg_name)

        content_parts = [f"## {msg_name}\n"]
        content_parts.append(f"**Type**: OCPP 2.0.1 Message Schema ({direction})")
        content_parts.append(f"**Base Message**: {base_name}\n")

        props = schema.get("properties", [])
        if props:
            content_parts.append("### Properties\n")
            content_parts.append("| Field | Type | Required | Description |")
            content_parts.append("|-------|------|----------|-------------|")
            for prop in props:
                req = "Yes" if prop.get("required") else "No"
                desc = prop.get("description", "")
                content_parts.append(
                    f"| {prop['name']} | {prop.get('type', 'any')} | {req} | {desc} |"
                )

        content_parts.append(f"\n### Full JSON Schema\n```json\n{json.dumps(schema.get('schema', {}), indent=2)}\n```")

        content = "\n".join(content_parts)

        for part_idx, part in enumerate(split_large_chunk(content)):
            meta = {
                "doc_id": "ocpp201_json_schemas",
                "doc_title": "OCPP 2.0.1 JSON Schemas",
                "ocpp_version": "2.0.1",
                "content_type": "json_schema",
                "heading": msg_name,
                "heading_path": f"JSON Schemas > {base_name} > {msg_name}",
                "message_name": msg_name,
                "message_direction": direction,
            }
            if part_idx > 0:
                meta["chunk_part"] = part_idx + 1
            chunks.append({"content": part, "metadata": meta})

    return chunks


def chunk_appendices(appendices_path):
    if not appendices_path.exists():
        return []

    with open(appendices_path) as f:
        data = json.load(f)

    chunks = []

    components = data.get("components", [])
    if components:
        content_parts = ["## OCPP 2.0.1 Device Model Components\n"]
        content_parts.append("| Component | Description |")
        content_parts.append("|-----------|-------------|")
        for comp in components:
            name = comp.get("name", comp.get("component", ""))
            desc = comp.get("description", "")
            content_parts.append(f"| {name} | {desc} |")
        content = "\n".join(content_parts)

        for part_idx, part in enumerate(split_large_chunk(content)):
            meta = {
                "doc_id": "ocpp201_appendices",
                "doc_title": "OCPP 2.0.1 Appendices - Components & Variables",
                "ocpp_version": "2.0.1",
                "content_type": "component_variable",
                "heading": "Device Model Components",
                "heading_path": "Appendices > Components",
            }
            if part_idx > 0:
                meta["chunk_part"] = part_idx + 1
            chunks.append({"content": part, "metadata": meta})

    variables = data.get("variables", [])
    if variables:
        by_component = {}
        for var in variables:
            comp = var.get("component", "General")
            by_component.setdefault(comp, []).append(var)

        for comp_name, comp_vars in by_component.items():
            content_parts = [f"## Component: {comp_name} - Variables\n"]
            content_parts.append("| Variable | DataType | Mutability | Description |")
            content_parts.append("|----------|----------|------------|-------------|")
            for v in comp_vars:
                content_parts.append(
                    f"| {v.get('name', v.get('variable', ''))} "
                    f"| {v.get('dataType', v.get('data_type', ''))} "
                    f"| {v.get('mutability', '')} "
                    f"| {v.get('description', '')} |"
                )
            content = "\n".join(content_parts)

            for part_idx, part in enumerate(split_large_chunk(content)):
                meta = {
                    "doc_id": "ocpp201_appendices",
                    "doc_title": "OCPP 2.0.1 Appendices - Components & Variables",
                    "ocpp_version": "2.0.1",
                    "content_type": "component_variable",
                    "heading": f"Component: {comp_name}",
                    "heading_path": f"Appendices > Variables > {comp_name}",
                    "component_name": comp_name,
                }
                if part_idx > 0:
                    meta["chunk_part"] = part_idx + 1
                chunks.append({"content": part, "metadata": meta})

    for key in ("reason_codes", "security_events", "units_of_measure"):
        items = data.get(key, [])
        if not items:
            continue
        title = key.replace("_", " ").title()
        content_parts = [f"## OCPP 2.0.1 {title}\n"]
        for item in items:
            if isinstance(item, dict):
                parts = [f"- **{v}**" if i == 0 else str(v)
                         for i, (k, v) in enumerate(item.items())]
                content_parts.append(": ".join(parts))
            else:
                content_parts.append(f"- {item}")
        content = "\n".join(content_parts)

        for part_idx, part in enumerate(split_large_chunk(content)):
            meta = {
                "doc_id": "ocpp201_appendices",
                "doc_title": f"OCPP 2.0.1 Appendices - {title}",
                "ocpp_version": "2.0.1",
                "content_type": "appendix",
                "heading": title,
                "heading_path": f"Appendices > {title}",
            }
            if part_idx > 0:
                meta["chunk_part"] = part_idx + 1
            chunks.append({"content": part, "metadata": meta})

    return chunks


def chunk_all(doc_ids=None):
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    all_chunks = []

    docs_to_process = ALL_DOCS if doc_ids is None else {
        k: v for k, v in ALL_DOCS.items() if k in doc_ids
    }

    for doc_id, doc_info in docs_to_process.items():
        md_path = PARSED_DIR / f"{doc_id}.md"
        if not md_path.exists():
            print(f"[SKIP] {doc_id}: not parsed yet ({md_path})")
            continue

        print(f"[CHUNK] {doc_id}: {doc_info['title']}...")
        chunks = chunk_markdown(md_path, doc_id, doc_info)
        print(f"  -> {len(chunks)} chunks")

        out_path = CHUNKS_DIR / f"{doc_id}_chunks.json"
        with open(out_path, "w") as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False)

        all_chunks.extend(chunks)

    schemas_path = SCHEMAS_DIR / "all_schemas.json"
    if schemas_path.exists() and (doc_ids is None or "ocpp201_json_schemas" in (doc_ids or [])):
        print("[CHUNK] JSON schemas...")
        schema_chunks = chunk_json_schemas(schemas_path)
        print(f"  -> {len(schema_chunks)} chunks")
        all_chunks.extend(schema_chunks)

        out_path = CHUNKS_DIR / "ocpp201_json_schemas_chunks.json"
        with open(out_path, "w") as f:
            json.dump(schema_chunks, f, indent=2, ensure_ascii=False)

    appendices_path = APPENDICES_DIR / "all_appendices.json"
    if appendices_path.exists() and (doc_ids is None or "ocpp201_appendices" in (doc_ids or [])):
        print("[CHUNK] Appendices data...")
        appendix_chunks = chunk_appendices(appendices_path)
        print(f"  -> {len(appendix_chunks)} chunks")
        all_chunks.extend(appendix_chunks)

        out_path = CHUNKS_DIR / "ocpp201_appendices_chunks.json"
        with open(out_path, "w") as f:
            json.dump(appendix_chunks, f, indent=2, ensure_ascii=False)

    combined_path = CHUNKS_DIR / "_all_chunks.json"
    with open(combined_path, "w") as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"Total chunks: {len(all_chunks)}")

    type_counts = {}
    doc_counts = {}
    version_counts = {}
    for c in all_chunks:
        t = c["metadata"].get("content_type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
        d = c["metadata"].get("doc_id", "unknown")
        doc_counts[d] = doc_counts.get(d, 0) + 1
        v = c["metadata"].get("ocpp_version", "other")
        version_counts[v] = version_counts.get(v, 0) + 1

    print("\nBy content type:")
    for t, count in sorted(type_counts.items()):
        print(f"  {t}: {count}")

    print("\nBy document:")
    for d, count in sorted(doc_counts.items()):
        print(f"  {d}: {count}")

    print("\nBy OCPP version:")
    for v, count in sorted(version_counts.items(), key=lambda x: str(x[0])):
        print(f"  {v}: {count}")

    uc_ids = sorted(set(
        c["metadata"]["use_case_id"]
        for c in all_chunks
        if c["metadata"].get("use_case_id")
    ))
    print(f"\nUnique use case IDs: {len(uc_ids)}")

    sizes = [len(c["content"]) for c in all_chunks]
    if sizes:
        print(f"Chunk sizes: min={min(sizes)}, max={max(sizes)}, avg={sum(sizes)//len(sizes)}")

    print(f"\nSaved to {combined_path}")
    return all_chunks


def main():
    parser = argparse.ArgumentParser(description="Chunk parsed OCPP documents")
    parser.add_argument("--doc", action="append", help="Specific doc_id(s) to chunk")
    args = parser.parse_args()

    chunk_all(doc_ids=args.doc)


if __name__ == "__main__":
    main()
