"""LlamaParse pipeline for OCPP PDF documents.

Parses all PDF documents registered in config.ALL_DOCS into markdown,
preserving tables, requirement IDs, sequence diagrams, and structure.

Usage:
    python -m ocpp_rag.parse [--force] [--doc ocpp201_part2] [--list]
"""

import os
import json
import argparse
import logging
from pathlib import Path
from dotenv import load_dotenv
try:
    from llama_cloud_services.parse import LlamaParse
except ImportError:
    from llama_parse import LlamaParse
from .config import SOURCE_DOCS_DIR, PARSED_DIR, ALL_DOCS

load_dotenv()

logger = logging.getLogger(__name__)

# Doc IDs that are specification-heavy and need aggressive table extraction
# plus detailed parsing instructions for OCPP-specific content.
SPEC_HEAVY_DOCS = {
    "ocpp201_part2",
    "ocpp201_part4",
    "ocpp201_part6",
    "ocpp16_spec",
    "ocpp16_j",
}

# Doc IDs that contain many sequence diagrams and architectural figures.
DIAGRAM_HEAVY_DOCS = {
    "ocpp201_part1",
    "ocpp201_part2",
    "ocpp201_part5",
}

OCPP_PARSING_INSTRUCTION = (
    "This is an OCPP (Open Charge Point Protocol) technical specification document. "
    "Preserve ALL requirement IDs exactly (e.g. A01.FR.01, B03.FR.12). "
    "Preserve ALL use case IDs (e.g. A01, B01, K08). "
    "Preserve all message names (e.g. BootNotificationRequest, AuthorizeResponse). "
    "Preserve table structures with proper alignment. "
    "For sequence diagrams, describe all actors (Charging Station, CSMS, etc.) "
    "and the complete message flow with arrows showing direction."
)


def get_parser(doc_id: str, doc_info: dict) -> LlamaParse:
    """Create a LlamaParse instance with optimal settings for the given document.

    Args:
        doc_id: The document identifier from ALL_DOCS.
        doc_info: The document metadata dict (title, file, ocpp_version).

    Returns:
        A configured LlamaParse instance.
    """
    kwargs = {
        "api_key": os.getenv("LLAMA_CLOUD_API_KEY"),
        "result_type": "markdown",
        "verbose": True,
        "language": "en",
        "continuous_mode": True,
        "hide_headers": True,
        "hide_footers": True,
        "merge_tables_across_pages_in_markdown": True,
        "adaptive_long_table": True,
        "page_prefix": "\n[PAGE {page_number}]\n",
    }

    if doc_id in SPEC_HEAVY_DOCS:
        kwargs["aggressive_table_extraction"] = True
        kwargs["system_prompt_append"] = OCPP_PARSING_INSTRUCTION

    if doc_id in DIAGRAM_HEAVY_DOCS:
        kwargs["extract_charts"] = True

    return LlamaParse(**kwargs)


def parse_document(
    doc_id: str, doc_info: dict, force: bool = False
) -> dict | None:
    """Parse a single PDF document with LlamaParse.

    Args:
        doc_id: The document identifier from ALL_DOCS.
        doc_info: The document metadata dict (title, file, ocpp_version).
        force: If True, re-parse even if output already exists.

    Returns:
        A metadata dict with parsing results, or None if skipped/failed.
    """
    output_path = PARSED_DIR / f"{doc_id}.md"

    if output_path.exists() and not force:
        logger.info("Skipping %s — already parsed at %s", doc_id, output_path)
        return None

    pdf_path = SOURCE_DOCS_DIR / doc_info["file"]
    if not pdf_path.exists():
        logger.warning(
            "PDF not found for %s: %s (you may need to download it first)",
            doc_id,
            pdf_path,
        )
        return None

    logger.info("Parsing %s: %s", doc_id, doc_info["title"])
    logger.info("  Source: %s", pdf_path)

    try:
        parser = get_parser(doc_id, doc_info)
        documents = parser.load_data(str(pdf_path))
    except Exception:
        logger.exception("LlamaParse failed on %s", doc_id)
        return None

    text = "\n\n---\n\n".join(doc.text for doc in documents)

    PARSED_DIR.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    logger.info("  Saved markdown: %s (%d chars)", output_path, len(text))

    # Attempt to extract and save images if the parser supports it.
    images_dir = PARSED_DIR / f"{doc_id}_images"
    images_saved = 0
    try:
        images = parser.get_images(documents, download_path=str(images_dir))
        if images:
            images_saved = len(images)
            logger.info("  Saved %d images to %s", images_saved, images_dir)
    except AttributeError:
        # get_images may not be available in all LlamaParse versions.
        logger.debug("  Image extraction not available for this LlamaParse version")
    except Exception:
        logger.debug("  Image extraction failed for %s", doc_id, exc_info=True)

    # Also check if individual document objects carry image data.
    if images_saved == 0:
        for doc in documents:
            doc_images = getattr(doc, "images", None)
            if doc_images:
                images_dir.mkdir(parents=True, exist_ok=True)
                for i, img in enumerate(doc_images):
                    if isinstance(img, dict) and "data" in img:
                        ext = img.get("type", "png")
                        img_path = images_dir / f"{doc_id}_img_{images_saved + i}.{ext}"
                        img_path.write_bytes(img["data"])
                    elif isinstance(img, bytes):
                        img_path = images_dir / f"{doc_id}_img_{images_saved + i}.png"
                        img_path.write_bytes(img)
                images_saved += len(doc_images)
        if images_saved > 0:
            logger.info("  Saved %d images to %s", images_saved, images_dir)

    metadata = {
        "doc_id": doc_id,
        "title": doc_info["title"],
        "ocpp_version": doc_info.get("ocpp_version"),
        "pages": len(documents),
        "chars": len(text),
        "images": images_saved,
        "file": str(pdf_path),
    }
    return metadata


def parse_all(
    force: bool = False, doc_ids: list[str] | None = None
) -> list[dict]:
    """Parse all (or selected) OCPP PDF documents.

    Args:
        force: If True, re-parse even if output already exists.
        doc_ids: If provided, only parse these document IDs.

    Returns:
        A list of metadata dicts for successfully parsed documents.
    """
    PARSED_DIR.mkdir(parents=True, exist_ok=True)

    if doc_ids:
        docs_to_parse = {
            k: v for k, v in ALL_DOCS.items() if k in doc_ids
        }
        unknown = set(doc_ids) - set(ALL_DOCS.keys())
        if unknown:
            logger.warning("Unknown doc IDs (skipping): %s", ", ".join(sorted(unknown)))
    else:
        docs_to_parse = ALL_DOCS

    results = []
    for doc_id, doc_info in docs_to_parse.items():
        meta = parse_document(doc_id, doc_info, force=force)
        if meta:
            results.append(meta)

    # Save manifest with all successful parse results.
    manifest_path = PARSED_DIR / "_manifest.json"
    # Merge with existing manifest entries for docs we didn't re-parse.
    existing_manifest = {}
    if manifest_path.exists():
        try:
            existing_manifest = {
                entry["doc_id"]: entry
                for entry in json.loads(manifest_path.read_text(encoding="utf-8"))
            }
        except (json.JSONDecodeError, KeyError):
            pass

    for meta in results:
        existing_manifest[meta["doc_id"]] = meta

    manifest_list = sorted(existing_manifest.values(), key=lambda m: m["doc_id"])
    manifest_path.write_text(
        json.dumps(manifest_list, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Manifest saved to %s (%d entries)", manifest_path, len(manifest_list))

    # Print summary.
    print("\n" + "=" * 60)
    print("PARSE SUMMARY")
    print("=" * 60)
    for meta in results:
        print(
            f"  {meta['doc_id']:30s}  {meta['pages']:4d} pages  "
            f"{meta['chars']:>9,d} chars  {meta['images']:3d} images"
        )
    print("-" * 60)
    total_chars = sum(m["chars"] for m in results)
    total_pages = sum(m["pages"] for m in results)
    total_images = sum(m["images"] for m in results)
    print(
        f"  {'TOTAL':30s}  {total_pages:4d} pages  "
        f"{total_chars:>9,d} chars  {total_images:3d} images"
    )
    print(f"  Parsed {len(results)} / {len(docs_to_parse)} documents")
    print("=" * 60)

    return results


def list_documents() -> None:
    """Print a table of all registered documents and their parse status."""
    print(f"\n{'Doc ID':30s}  {'Version':8s}  {'Status':8s}  Title")
    print("-" * 90)
    for doc_id, doc_info in ALL_DOCS.items():
        parsed_path = PARSED_DIR / f"{doc_id}.md"
        pdf_path = SOURCE_DOCS_DIR / doc_info["file"]
        if parsed_path.exists():
            status = "PARSED"
        elif pdf_path.exists():
            status = "READY"
        else:
            status = "NO PDF"
        version = doc_info.get("ocpp_version") or "-"
        print(f"  {doc_id:30s}  {version:8s}  {status:8s}  {doc_info['title']}")
    print()


def main() -> None:
    """CLI entry point for the parse pipeline."""
    parser = argparse.ArgumentParser(
        description="Parse OCPP PDF documents with LlamaParse",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-parse documents even if output already exists",
    )
    parser.add_argument(
        "--doc",
        action="append",
        dest="doc_ids",
        metavar="DOC_ID",
        help="Specific document ID(s) to parse (repeatable). "
        "If omitted, all documents are parsed.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_docs",
        help="List all available documents and their parse status, then exit",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.list_docs:
        list_documents()
        return

    parse_all(force=args.force, doc_ids=args.doc_ids)


if __name__ == "__main__":
    main()
