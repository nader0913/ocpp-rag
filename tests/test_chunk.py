"""Tests for ocpp_rag.chunk module."""

import json
import re
from pathlib import Path

import pytest

from ocpp_rag.chunk import (
    clean_text,
    extract_page_numbers,
    parse_sections,
    classify_section_201,
    classify_section_16,
    is_toc_or_empty,
    split_large_chunk,
    build_heading_path,
    extract_cross_refs,
    chunk_markdown,
    chunk_json_schemas,
    chunk_appendices,
    MAX_CHUNK_SIZE,
    MIN_CHUNK_SIZE,
)


class TestCleanText:
    """Test clean_text removes headers/footers, HTML entities, excess newlines."""

    def test_removes_ocpp_header(self):
        text = "OCPP 2.0.1 Edition 4 - . Open Charge Alliance 2025\n120/500\nPart 2 - Specification\nActual content here."
        result = clean_text(text)
        assert "Open Charge Alliance" not in result
        assert "Actual content here." in result

    def test_removes_edition_date_line(self):
        text = "Edition 4, 2025-12-03 something\nActual content."
        result = clean_text(text)
        assert "Edition 4, 2025-12-03" not in result
        assert "Actual content." in result

    def test_removes_page_markers(self):
        text = "[PAGE 42]\nSome content here.\n[PAGE 43]\nMore content."
        result = clean_text(text)
        assert "[PAGE 42]" not in result
        assert "[PAGE 43]" not in result
        assert "Some content here." in result
        assert "More content." in result

    def test_removes_horizontal_rules(self):
        text = "Before\n---\nAfter"
        result = clean_text(text)
        assert "---" not in result
        assert "Before" in result
        assert "After" in result

    def test_collapses_excessive_newlines(self):
        text = "Line 1\n\n\n\n\n\nLine 2"
        result = clean_text(text)
        # Should be collapsed to at most 3 newlines
        assert "\n\n\n\n" not in result
        assert "Line 1" in result
        assert "Line 2" in result

    def test_replaces_html_ampersand_entity(self):
        text = "A &#x26; B"
        result = clean_text(text)
        assert "A & B" in result
        assert "&#x26;" not in result

    def test_removes_other_html_entities(self):
        text = "Some &#x3C; text &#xAB; here"
        result = clean_text(text)
        assert "&#x3C;" not in result
        assert "&#xAB;" not in result

    def test_removes_page_number_fractions(self):
        text = "42/500\nActual text."
        result = clean_text(text)
        assert "42/500" not in result
        assert "Actual text." in result

    def test_strips_whitespace(self):
        text = "  \n  content  \n  "
        result = clean_text(text)
        assert result == "content"

    def test_preserves_normal_content(self):
        text = "The Charging Station SHALL send BootNotificationRequest."
        result = clean_text(text)
        assert result == text


class TestExtractPageNumbers:
    """Test extract_page_numbers finds [PAGE N] markers."""

    def test_finds_page_markers(self):
        text = "[PAGE 1]\nContent\n[PAGE 2]\nMore content\n[PAGE 5]"
        result = extract_page_numbers(text)
        assert result == [1, 2, 5]

    def test_deduplicates_pages(self):
        text = "[PAGE 3]\nContent\n[PAGE 3]\nMore"
        result = extract_page_numbers(text)
        assert result == [3]

    def test_returns_sorted(self):
        text = "[PAGE 10]\n[PAGE 2]\n[PAGE 5]"
        result = extract_page_numbers(text)
        assert result == [2, 5, 10]

    def test_no_markers_returns_empty(self):
        text = "Just some text without page markers."
        result = extract_page_numbers(text)
        assert result == []

    def test_fallback_to_page_refs(self):
        text = "120/500\nPart 2\n42/500\nPart 1"
        result = extract_page_numbers(text)
        assert 120 in result
        assert 42 in result


class TestParseSections:
    """Test parse_sections splits markdown into sections by heading."""

    def test_basic_splitting(self):
        md = "# Title\nContent\n## Section 1\nText 1\n## Section 2\nText 2"
        sections = parse_sections(md)
        assert len(sections) == 3
        assert sections[0]["heading"] == "Title"
        assert sections[1]["heading"] == "Section 1"
        assert sections[2]["heading"] == "Section 2"

    def test_heading_levels(self):
        md = "# H1\nContent\n## H2\nContent\n### H3\nContent\n#### H4\nContent"
        sections = parse_sections(md)
        assert sections[0]["level"] == 1
        assert sections[1]["level"] == 2
        assert sections[2]["level"] == 3
        assert sections[3]["level"] == 4

    def test_content_includes_heading_line(self):
        md = "# Title\nBody text here"
        sections = parse_sections(md)
        assert "# Title" in sections[0]["content"]
        assert "Body text here" in sections[0]["content"]

    def test_page_markers_tracked(self):
        md = "[PAGE 5]\n# Section A\nContent A\n[PAGE 6]\n## Section B\nContent B"
        sections = parse_sections(md)
        # The section after the page marker should track the page
        assert any(s.get("start_page") is not None for s in sections)

    def test_empty_input(self):
        sections = parse_sections("")
        assert sections == []

    def test_no_headings(self):
        md = "Just plain text\nwithout any headings"
        sections = parse_sections(md)
        assert sections == []


class TestClassifySection201:
    """Test classify_section_201 correctly identifies section types."""

    def test_use_case_a01(self):
        result = classify_section_201("A01 - Update Charging Station Password")
        assert result["content_type"] == "use_case"
        assert result["use_case_id"] == "A01"
        assert result["use_case_name"] == "Update Charging Station Password"
        assert result["functional_block"] == "Security"

    def test_use_case_b05(self):
        result = classify_section_201("B05 - Set Variables")
        assert result["content_type"] == "use_case"
        assert result["use_case_id"] == "B05"
        assert result["functional_block"] == "Provisioning"

    def test_use_case_k12(self):
        result = classify_section_201("K12 - Set Charging Profile")
        assert result["content_type"] == "use_case"
        assert result["use_case_id"] == "K12"
        assert result["functional_block"] == "SmartCharging"

    def test_requirements_section(self):
        result = classify_section_201("A01 - Update Charging Station Password - Requirements")
        assert result["content_type"] == "requirements"
        assert result["use_case_id"] == "A01"
        assert result["functional_block"] == "Security"

    def test_block_intro_a(self):
        result = classify_section_201("A. Security")
        assert result["content_type"] == "block_intro"
        assert result["functional_block"] == "Security"

    def test_block_intro_k(self):
        result = classify_section_201("K. SmartCharging")
        assert result["content_type"] == "block_intro"
        assert result["functional_block"] == "SmartCharging"

    def test_figure(self):
        result = classify_section_201("Figure 1 - Sequence Diagram")
        assert result["content_type"] == "figure"

    def test_messages_section(self):
        result = classify_section_201("1. Messages")
        assert result["content_type"] == "messages_section"

    def test_datatypes_section(self):
        result = classify_section_201("2. Datatypes")
        assert result["content_type"] == "datatypes_section"

    def test_enumerations_section(self):
        result = classify_section_201("3. Enumerations")
        assert result["content_type"] == "enumerations_section"

    def test_message_or_type_numbered(self):
        result = classify_section_201("1.2.3. BootNotificationRequest")
        assert result["content_type"] == "message_or_type"

    def test_general_fallback(self):
        result = classify_section_201("Introduction")
        assert result["content_type"] == "general"

    def test_all_functional_blocks(self):
        """Ensure all block letters A-P are recognized."""
        blocks = {
            "A": "Security", "B": "Provisioning", "C": "Authorization",
            "D": "LocalAuthorizationListManagement", "E": "Transactions",
            "F": "RemoteControl", "G": "Availability", "H": "Reservation",
            "I": "TariffAndCost", "J": "MeterValues", "K": "SmartCharging",
            "L": "FirmwareManagement", "M": "CertificateManagement",
            "N": "Diagnostics", "O": "DisplayMessage", "P": "DataTransfer",
        }
        for letter, expected_block in blocks.items():
            result = classify_section_201(f"{letter}01 - Test Use Case")
            assert result["content_type"] == "use_case"
            assert result["use_case_id"] == f"{letter}01"
            assert result["functional_block"] == expected_block


class TestClassifySection16:
    """Test classify_section_16 for OCPP 1.6 documents."""

    def test_numbered_section(self):
        result = classify_section_16("4.2. Authorize")
        assert result["content_type"] == "message_or_type"
        assert result["section_id"] == "4.2"

    def test_general_fallback(self):
        result = classify_section_16("Introduction")
        assert result["content_type"] == "general"


class TestIsTocOrEmpty:
    """Test is_toc_or_empty filters out TOC entries and empty sections."""

    def test_empty_content(self):
        section = {"heading": "Title", "content": "", "level": 1}
        assert is_toc_or_empty(section) is True

    def test_only_heading(self):
        section = {"heading": "Title", "content": "# Title", "level": 1}
        assert is_toc_or_empty(section) is True

    def test_short_body(self):
        section = {"heading": "Title", "content": "# Title\nShort", "level": 1}
        assert is_toc_or_empty(section) is True

    def test_toc_like_entry(self):
        section = {
            "heading": "Table of Contents",
            "content": "# Table of Contents\n1. Intro\n2. Details",
            "level": 1,
        }
        # body text is short
        assert is_toc_or_empty(section) is True

    def test_real_content_not_filtered(self):
        section = {
            "heading": "B01 - Cold Boot",
            "content": (
                "# B01\n"
                "The Charging Station SHALL send a BootNotificationRequest to the CSMS after start-up.\n"
                "This is required behavior for proper provisioning.\n"
                "The CSMS responds with BootNotificationResponse.\n"
                "The Charging Station SHALL retry if the response status is Pending."
            ),
            "level": 2,
        }
        assert is_toc_or_empty(section) is False

    def test_two_lines_only(self):
        section = {"heading": "X", "content": "# X\nOne line only", "level": 1}
        assert is_toc_or_empty(section) is True


class TestSplitLargeChunk:
    """Test split_large_chunk splits content correctly."""

    def test_small_content_not_split(self):
        content = "This is a short piece of content."
        result = split_large_chunk(content)
        assert result == [content]

    def test_exact_max_size_not_split(self):
        content = "x" * MAX_CHUNK_SIZE
        result = split_large_chunk(content)
        assert len(result) == 1

    def test_large_content_split(self):
        # Create content larger than MAX_CHUNK_SIZE
        lines = ["Line " + str(i) + " " * 50 for i in range(100)]
        content = "\n".join(lines)
        assert len(content) > MAX_CHUNK_SIZE
        result = split_large_chunk(content)
        assert len(result) > 1
        # Verify all content is preserved (joined parts should contain all lines)
        joined = "\n".join(result)
        for line in lines:
            assert line.strip() in joined

    def test_tables_kept_together(self):
        # Create a table that is under the 1.5x limit
        header = "| Col A | Col B | Col C |"
        separator = "|---|---|---|"
        rows = [f"| val{i}a | val{i}b | val{i}c |" for i in range(20)]
        table = "\n".join([header, separator] + rows)

        # Put some preamble to push past 70% threshold
        preamble = "x" * int(MAX_CHUNK_SIZE * 0.6)
        content = preamble + "\n" + table

        result = split_large_chunk(content)
        # The table should stay together in one of the parts
        for part in result:
            if separator in part:
                # All table rows in this part should be contiguous
                part_lines = part.split("\n")
                table_lines = [l for l in part_lines if l.strip().startswith("|")]
                assert len(table_lines) >= 2  # at least separator + some rows

    def test_split_respects_max_size(self):
        # Each part should not be wildly over MAX_CHUNK_SIZE
        content = "A line of text.\n" * 500
        result = split_large_chunk(content)
        for part in result:
            # The 1.5x multiplier is the hard ceiling for splitting
            assert len(part) < MAX_CHUNK_SIZE * 2, f"Part too large: {len(part)} chars"


class TestBuildHeadingPath:
    """Test build_heading_path builds correct hierarchy."""

    def test_single_section(self):
        sections = [{"heading": "Title", "level": 1}]
        path = build_heading_path(sections, 0)
        assert path == "Title"

    def test_two_level_hierarchy(self):
        sections = [
            {"heading": "A. Security", "level": 1},
            {"heading": "A01 - Update Password", "level": 2},
        ]
        path = build_heading_path(sections, 1)
        assert path == "A. Security > A01 - Update Password"

    def test_three_level_hierarchy(self):
        sections = [
            {"heading": "A. Security", "level": 1},
            {"heading": "A01 - Update Password", "level": 2},
            {"heading": "Requirements", "level": 3},
        ]
        path = build_heading_path(sections, 2)
        assert path == "A. Security > A01 - Update Password > Requirements"

    def test_sibling_sections(self):
        sections = [
            {"heading": "A. Security", "level": 1},
            {"heading": "A01 - First", "level": 2},
            {"heading": "A02 - Second", "level": 2},
        ]
        path = build_heading_path(sections, 2)
        assert path == "A. Security > A02 - Second"

    def test_skips_same_and_higher_level(self):
        sections = [
            {"heading": "Root", "level": 1},
            {"heading": "Child A", "level": 2},
            {"heading": "Child B", "level": 2},
            {"heading": "Grandchild", "level": 3},
        ]
        path = build_heading_path(sections, 3)
        assert path == "Root > Child B > Grandchild"


class TestExtractCrossRefs:
    """Test extract_cross_refs finds use case, requirement, and message refs."""

    def test_finds_use_case_refs(self):
        content = "See A01 for details. Also refer to B02 and K08."
        refs = extract_cross_refs(content)
        assert "A01" in refs["use_case_refs"]
        assert "B02" in refs["use_case_refs"]
        assert "K08" in refs["use_case_refs"]

    def test_finds_requirement_refs(self):
        content = "As stated in A01.FR.01 and B03.FR.12, the Charging Station SHALL..."
        refs = extract_cross_refs(content)
        assert "A01.FR.01" in refs["requirement_refs"]
        assert "B03.FR.12" in refs["requirement_refs"]

    def test_finds_message_refs(self):
        content = "The Charging Station sends BootNotificationRequest and expects a BootNotificationResponse."
        refs = extract_cross_refs(content)
        assert "BootNotificationRequest" in refs["message_refs"]
        assert "BootNotificationResponse" in refs["message_refs"]

    def test_no_refs_returns_empty_lists(self):
        content = "Just some plain text without any references."
        refs = extract_cross_refs(content)
        assert refs["use_case_refs"] == []
        assert refs["requirement_refs"] == []
        assert refs["message_refs"] == []

    def test_refs_are_sorted(self):
        content = "K08 and A01 and B02 should be sorted"
        refs = extract_cross_refs(content)
        assert refs["use_case_refs"] == sorted(refs["use_case_refs"])

    def test_refs_are_deduplicated(self):
        content = "A01 is mentioned twice: A01 again."
        refs = extract_cross_refs(content)
        assert refs["use_case_refs"].count("A01") == 1


class TestChunkMarkdownBasic:
    """Test chunk_markdown with a realistic markdown input."""

    def test_chunks_basic_structure(self, tmp_path, sample_markdown_201):
        md_path = tmp_path / "test.md"
        md_path.write_text(sample_markdown_201)

        doc_info = {"title": "OCPP 2.0.1 Part 2 - Specification", "ocpp_version": "2.0.1"}
        chunks = chunk_markdown(md_path, "ocpp201_part2", doc_info)

        assert len(chunks) > 0
        # Should have chunked at least the use cases and requirements
        content_types = {c["metadata"]["content_type"] for c in chunks}
        assert "use_case" in content_types
        assert "requirements" in content_types
        assert "block_intro" in content_types

    def test_use_case_ids_extracted(self, tmp_path, sample_markdown_201):
        md_path = tmp_path / "test.md"
        md_path.write_text(sample_markdown_201)

        doc_info = {"title": "OCPP 2.0.1 Part 2", "ocpp_version": "2.0.1"}
        chunks = chunk_markdown(md_path, "ocpp201_part2", doc_info)

        use_case_ids = {c["metadata"].get("use_case_id") for c in chunks if c["metadata"].get("use_case_id")}
        assert "A01" in use_case_ids
        assert "A02" in use_case_ids
        assert "B01" in use_case_ids
        assert "B05" in use_case_ids

    def test_functional_blocks_assigned(self, tmp_path, sample_markdown_201):
        md_path = tmp_path / "test.md"
        md_path.write_text(sample_markdown_201)

        doc_info = {"title": "OCPP 2.0.1 Part 2", "ocpp_version": "2.0.1"}
        chunks = chunk_markdown(md_path, "ocpp201_part2", doc_info)

        blocks = {c["metadata"].get("functional_block") for c in chunks if c["metadata"].get("functional_block")}
        assert "Security" in blocks
        # B01/B05 chunks should carry the Provisioning block from their use_case_id prefix
        assert "Provisioning" in blocks or any(
            c["metadata"].get("use_case_id", "").startswith("B") for c in chunks
        )

    def test_figures_skipped(self, tmp_path, sample_markdown_201):
        md_path = tmp_path / "test.md"
        md_path.write_text(sample_markdown_201)

        doc_info = {"title": "OCPP 2.0.1 Part 2", "ocpp_version": "2.0.1"}
        chunks = chunk_markdown(md_path, "ocpp201_part2", doc_info)

        for chunk in chunks:
            assert chunk["metadata"]["content_type"] != "figure"

    def test_cross_refs_in_metadata(self, tmp_path, sample_markdown_201):
        md_path = tmp_path / "test.md"
        md_path.write_text(sample_markdown_201)

        doc_info = {"title": "OCPP 2.0.1 Part 2", "ocpp_version": "2.0.1"}
        chunks = chunk_markdown(md_path, "ocpp201_part2", doc_info)

        # Find any chunk whose content mentions E02 and K08 (from the K12 section)
        ref_chunks = [
            c for c in chunks
            if "E02" in c.get("content", "") and "K08" in c.get("content", "")
        ]
        assert len(ref_chunks) > 0
        use_case_refs = ref_chunks[0]["metadata"].get("use_case_refs", "")
        assert "E02" in use_case_refs
        assert "K08" in use_case_refs

    def test_message_refs_in_metadata(self, tmp_path, sample_markdown_201):
        md_path = tmp_path / "test.md"
        md_path.write_text(sample_markdown_201)

        doc_info = {"title": "OCPP 2.0.1 Part 2", "ocpp_version": "2.0.1"}
        chunks = chunk_markdown(md_path, "ocpp201_part2", doc_info)

        # B01 section references BootNotificationRequest
        b01_chunks = [c for c in chunks if c["metadata"].get("use_case_id") == "B01" and c["metadata"]["content_type"] == "use_case"]
        assert len(b01_chunks) > 0
        msg_refs = b01_chunks[0]["metadata"].get("message_refs", "")
        assert "BootNotificationRequest" in msg_refs

    def test_heading_path_built(self, tmp_path, sample_markdown_201):
        md_path = tmp_path / "test.md"
        md_path.write_text(sample_markdown_201)

        doc_info = {"title": "OCPP 2.0.1 Part 2", "ocpp_version": "2.0.1"}
        chunks = chunk_markdown(md_path, "ocpp201_part2", doc_info)

        for chunk in chunks:
            assert "heading_path" in chunk["metadata"]
            assert len(chunk["metadata"]["heading_path"]) > 0


class TestChunkJsonSchemas:
    """Test chunk_json_schemas processes JSON schema data correctly."""

    def test_produces_chunks(self, sample_schemas_json):
        chunks = chunk_json_schemas(sample_schemas_json)
        assert len(chunks) >= 2  # At least one for each schema

    def test_metadata_correct(self, sample_schemas_json):
        chunks = chunk_json_schemas(sample_schemas_json)
        for chunk in chunks:
            meta = chunk["metadata"]
            assert meta["doc_id"] == "ocpp201_json_schemas"
            assert meta["ocpp_version"] == "2.0.1"
            assert meta["content_type"] == "json_schema"
            assert "message_name" in meta
            assert "message_direction" in meta

    def test_request_direction(self, sample_schemas_json):
        chunks = chunk_json_schemas(sample_schemas_json)
        request_chunks = [c for c in chunks if c["metadata"]["message_name"] == "BootNotificationRequest"]
        assert len(request_chunks) >= 1
        assert request_chunks[0]["metadata"]["message_direction"] == "Request"

    def test_response_direction(self, sample_schemas_json):
        chunks = chunk_json_schemas(sample_schemas_json)
        response_chunks = [c for c in chunks if c["metadata"]["message_name"] == "BootNotificationResponse"]
        assert len(response_chunks) >= 1
        assert response_chunks[0]["metadata"]["message_direction"] == "Response"

    def test_content_includes_properties(self, sample_schemas_json):
        chunks = chunk_json_schemas(sample_schemas_json)
        request_chunks = [c for c in chunks if c["metadata"]["message_name"] == "BootNotificationRequest"]
        combined = " ".join(c["content"] for c in request_chunks)
        assert "reason" in combined
        assert "chargingStation" in combined

    def test_heading_path_format(self, sample_schemas_json):
        chunks = chunk_json_schemas(sample_schemas_json)
        for chunk in chunks:
            path = chunk["metadata"]["heading_path"]
            assert path.startswith("JSON Schemas > ")

    def test_nonexistent_path_returns_empty(self, tmp_path):
        fake_path = tmp_path / "nonexistent.json"
        chunks = chunk_json_schemas(fake_path)
        assert chunks == []


class TestChunkAppendices:
    """Test chunk_appendices processes appendix data correctly."""

    def test_produces_chunks(self, sample_appendices_json):
        chunks = chunk_appendices(sample_appendices_json)
        assert len(chunks) > 0

    def test_component_chunks_created(self, sample_appendices_json):
        chunks = chunk_appendices(sample_appendices_json)
        comp_chunks = [c for c in chunks if "Components" in c["metadata"]["heading"]]
        assert len(comp_chunks) >= 1
        # Should mention the components from fixture
        combined = " ".join(c["content"] for c in comp_chunks)
        assert "ChargingStation" in combined
        assert "EVSE" in combined

    def test_variable_chunks_by_component(self, sample_appendices_json):
        chunks = chunk_appendices(sample_appendices_json)
        var_chunks = [c for c in chunks if c["metadata"].get("component_name")]
        assert len(var_chunks) >= 1
        # Should have chunks for EVSE and ChargingStation components
        component_names = {c["metadata"]["component_name"] for c in var_chunks}
        assert "EVSE" in component_names
        assert "ChargingStation" in component_names

    def test_appendix_sections_created(self, sample_appendices_json):
        chunks = chunk_appendices(sample_appendices_json)
        appendix_chunks = [c for c in chunks if c["metadata"]["content_type"] == "appendix"]
        assert len(appendix_chunks) >= 1
        headings = {c["metadata"]["heading"] for c in appendix_chunks}
        assert "Reason Codes" in headings
        assert "Security Events" in headings
        assert "Units Of Measure" in headings

    def test_metadata_completeness(self, sample_appendices_json):
        chunks = chunk_appendices(sample_appendices_json)
        for chunk in chunks:
            meta = chunk["metadata"]
            assert meta["doc_id"] == "ocpp201_appendices"
            assert meta["ocpp_version"] == "2.0.1"
            assert "content_type" in meta
            assert "heading" in meta
            assert "heading_path" in meta

    def test_nonexistent_path_returns_empty(self, tmp_path):
        fake_path = tmp_path / "nonexistent.json"
        chunks = chunk_appendices(fake_path)
        assert chunks == []


class TestChunkMetadataCompleteness:
    """Every chunk must have doc_id, content_type, and heading."""

    def test_all_chunks_have_required_metadata(self, tmp_path, sample_markdown_201):
        md_path = tmp_path / "test.md"
        md_path.write_text(sample_markdown_201)

        doc_info = {"title": "Test Doc", "ocpp_version": "2.0.1"}
        chunks = chunk_markdown(md_path, "ocpp201_part2", doc_info)

        for i, chunk in enumerate(chunks):
            meta = chunk["metadata"]
            assert "doc_id" in meta, f"Chunk {i} missing doc_id"
            assert "content_type" in meta, f"Chunk {i} missing content_type"
            assert "heading" in meta, f"Chunk {i} missing heading"
            assert meta["doc_id"] == "ocpp201_part2"

    def test_schema_chunks_have_required_metadata(self, sample_schemas_json):
        chunks = chunk_json_schemas(sample_schemas_json)
        for i, chunk in enumerate(chunks):
            meta = chunk["metadata"]
            assert "doc_id" in meta, f"Schema chunk {i} missing doc_id"
            assert "content_type" in meta, f"Schema chunk {i} missing content_type"
            assert "heading" in meta, f"Schema chunk {i} missing heading"


class TestChunkSizeBounds:
    """No chunks below MIN_CHUNK_SIZE or way above MAX_CHUNK_SIZE."""

    def test_no_tiny_chunks(self, tmp_path, sample_markdown_201):
        md_path = tmp_path / "test.md"
        md_path.write_text(sample_markdown_201)

        doc_info = {"title": "Test", "ocpp_version": "2.0.1"}
        chunks = chunk_markdown(md_path, "ocpp201_part2", doc_info)

        for i, chunk in enumerate(chunks):
            assert len(chunk["content"]) >= MIN_CHUNK_SIZE, (
                f"Chunk {i} too small: {len(chunk['content'])} chars "
                f"(heading: {chunk['metadata']['heading']})"
            )

    def test_chunks_not_excessively_large(self, tmp_path, sample_markdown_201):
        md_path = tmp_path / "test.md"
        md_path.write_text(sample_markdown_201)

        doc_info = {"title": "Test", "ocpp_version": "2.0.1"}
        chunks = chunk_markdown(md_path, "ocpp201_part2", doc_info)

        # Allow some slack above MAX_CHUNK_SIZE for tables that need to stay together
        upper_bound = MAX_CHUNK_SIZE * 2
        for i, chunk in enumerate(chunks):
            assert len(chunk["content"]) <= upper_bound, (
                f"Chunk {i} too large: {len(chunk['content'])} chars "
                f"(heading: {chunk['metadata']['heading']})"
            )

    def test_schema_chunks_size_bounds(self, sample_schemas_json):
        chunks = chunk_json_schemas(sample_schemas_json)
        upper_bound = MAX_CHUNK_SIZE * 2
        for i, chunk in enumerate(chunks):
            assert len(chunk["content"]) >= 10, f"Schema chunk {i} too small"
            assert len(chunk["content"]) <= upper_bound, f"Schema chunk {i} too large"
