#!/usr/bin/env python3
"""Structural validation for the generated Terra-Audit presentation."""

from __future__ import annotations

import hashlib
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
PPTX = ROOT / "docs" / "Terra-Audit_SE801_Midterm_Presentation.pptx"
ASSETS = ROOT / "docs" / "presentation" / "assets"
NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def natural_key(name: str) -> list[object]:
    return [int(v) if v.isdigit() else v for v in re.split(r"(\d+)", name)]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    problems: list[str] = []
    with zipfile.ZipFile(PPTX) as zf:
        bad = zf.testzip()
        if bad:
            problems.append(f"corrupt ZIP member: {bad}")

        names = set(zf.namelist())
        slide_names = sorted(
            (n for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
            key=natural_key,
        )
        note_names = [n for n in names if re.fullmatch(r"ppt/notesSlides/notesSlide\d+\.xml", n)]
        media_names = [n for n in names if n.startswith("ppt/media/")]

        if len(slide_names) != 34:
            problems.append(f"expected 34 slides, found {len(slide_names)}")
        if len(note_names) != len(slide_names):
            problems.append(f"expected notes on every slide, found {len(note_names)} notes for {len(slide_names)} slides")

        presentation = ET.fromstring(zf.read("ppt/presentation.xml"))
        size = presentation.find("p:sldSz", NS)
        width = int(size.attrib["cx"])
        height = int(size.attrib["cy"])
        tolerance = 2000
        outside: list[str] = []
        all_text: list[str] = []

        for slide_name in slide_names:
            root = ET.fromstring(zf.read(slide_name))
            all_text.extend(t.text or "" for t in root.findall(".//a:t", NS))
            for xfrm in root.findall(".//a:xfrm", NS):
                off = xfrm.find("a:off", NS)
                ext = xfrm.find("a:ext", NS)
                if off is None or ext is None:
                    continue
                x, y = int(off.attrib["x"]), int(off.attrib["y"])
                cx, cy = int(ext.attrib["cx"]), int(ext.attrib["cy"])
                if x < -tolerance or y < -tolerance or x + cx > width + tolerance or y + cy > height + tolerance:
                    outside.append(f"{slide_name}: ({x}, {y}, {cx}, {cy})")

            rel_name = slide_name.replace("ppt/slides/", "ppt/slides/_rels/") + ".rels"
            if rel_name in names:
                rel_root = ET.fromstring(zf.read(rel_name))
                for rel in rel_root.findall("pr:Relationship", NS):
                    target = rel.attrib.get("Target", "")
                    if target.startswith("../media/"):
                        member = "ppt/media/" + target.split("../media/", 1)[1]
                        if member not in names:
                            problems.append(f"missing media target: {member}")

        if outside:
            problems.append("objects outside slide bounds: " + "; ".join(outside[:8]))

        combined = "\n".join(all_text)
        required_text = [
            "Kazi Nahid",
            "BSSE Roll: 1437",
            "Dr. Emon Kumar Dey",
            "2 August 2026",
            "Eighteen functional requirements",
            "STEP 15",
            "VM0051",
            "VM0042",
            "AI remains experimental",
        ]
        for phrase in required_text:
            if phrase not in combined:
                problems.append(f"missing required text: {phrase}")

        media_hashes = {digest(zf.read(n)) for n in media_names}
        expected_assets = [
            *(ASSETS / "demo_steps").glob("step*.png"),
            *(ASSETS / "report_v3").glob("fig*.png"),
            ASSETS / "component_architecture.svg",
            ROOT / "docs" / "diagrams" / "fig22_gantt_serial_fixed.png",
        ]
        missing_assets = [str(p.relative_to(ROOT)) for p in expected_assets if digest(p.read_bytes()) not in media_hashes]
        # The component PNG and original Gantt are intentionally replaced by
        # a vector component diagram and the corrected Gantt chart.
        missing_assets = [
            p for p in missing_assets
            if not p.endswith("report_v3/fig21.png") and not p.endswith("report_v3/fig22.png")
        ]
        if missing_assets:
            problems.append("source assets not embedded: " + ", ".join(missing_assets))

    print(f"slides={len(slide_names)} notes={len(note_names)} media={len(media_names)}")
    if problems:
        print("VALIDATION FAILED")
        for issue in problems:
            print(f"- {issue}")
        return 1
    print("VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
