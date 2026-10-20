"""Record the original STEP provenance and recover its GB18030 product labels."""
import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path.home() / "文档/HERO.STEP"


def main():
    raw = SOURCE.read_bytes()
    source = raw.decode("gb18030")
    products = re.findall(r"#(\d+)\s*=\s*PRODUCT\s*\(\s*'((?:[^']|'')*)'", source)
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    with (reports / "source_products.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n", quoting=csv.QUOTE_ALL)
        writer.writerow(["step_entity", "product_label"])
        writer.writerows(products)
    manifest = {
        "source": str(SOURCE),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "header": source[:source.index("ENDSEC;") + 7],
        "label_encoding": "gb18030 (strict decode succeeded)",
        "product_definitions": len(products),
        "assembly_occurrences": len(re.findall(r"=\s*NEXT_ASSEMBLY_USAGE_OCCURRENCE\s*\(", source)),
        "source_attribution": "User identifies source as SJTU JiaoLong HERO open source; release/license not yet verified",
    }
    (reports / "source_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    # Convert only non-ASCII STEP strings into standard Unicode escapes for OCCT.
    # The original STEP is never modified; all geometry numbers are preserved.
    def encode_string(match):
        value = match.group(0)
        return re.sub(r"[^\x00-\x7f]+", lambda m: "\\X2\\" + m.group(0).encode("utf-16-be").hex().upper() + "\\X0\\", value)
    normalized = re.sub(r"'(?:[^']|'')*'", encode_string, source)
    target = Path("/tmp/zenith-hero-utf8.step")
    target.write_text(normalized, encoding="ascii")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print("Import copy:", target)


if __name__ == "__main__":
    main()
