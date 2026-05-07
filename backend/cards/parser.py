"""
Parse eBay sports card listing titles into structured fields.

Handles messiness like:
  "2024 Panini Prizm Shedeur Sanders RC Rookie Auto /99 BGS 9.5"
  "Shedeur Sanders 2025 Topps Chrome Auto Patch Logo /5 PSA 10"
  "2024 Select Blue Die Cut /149 Shedeur Sanders"
"""

import re
from typing import Optional

# ── Known set patterns (order matters — more specific first) ──────────────────

_SETS = [
    # Football
    ("Panini National Treasures", ["national treasures"]),
    ("Panini Flawless",           ["flawless"]),
    ("Panini Immaculate",         ["immaculate"]),
    ("Panini One",                ["panini one"]),
    ("Panini Prizm",              ["prizm"]),
    ("Panini Select",             ["select"]),
    ("Panini Mosaic",             ["mosaic"]),
    ("Panini Contenders",         ["contenders"]),
    ("Donruss Optic",             ["donruss optic", "optic"]),
    ("Panini Score",              ["panini score"]),
    ("Panini Donruss",            ["donruss"]),
    ("Panini Legacy",             ["legacy"]),
    # Baseball
    ("Topps Dynasty",             ["dynasty"]),
    ("Topps Definitive",          ["definitive"]),
    ("Topps Transcendent",        ["transcendent"]),
    ("Bowman Chrome",             ["bowman chrome"]),
    ("Topps Chrome",              ["topps chrome"]),
    ("Topps Finest",              ["finest"]),
    ("Topps Heritage High Number",["heritage high number"]),
    ("Topps Heritage",            ["heritage"]),
    ("Topps Stadium Club",        ["stadium club"]),
    ("Allen & Ginter",            ["allen & ginter", "allen and ginter", "a&g"]),
    ("Topps Series 1",            ["topps series 1", "series 1"]),
    ("Topps Series 2",            ["topps series 2", "series 2"]),
    ("Topps Opening Day",         ["opening day"]),
    ("Bowman",                    ["bowman"]),
    # Basketball
    ("Panini Hoops Premium Stock",["hoops premium"]),
    ("Panini Hoops",              ["hoops"]),
]

# ── Grading company patterns ──────────────────────────────────────────────────

_GRADE_RE = re.compile(
    r'\b(PSA|BGS|SGC|CSG|HGA)\s+(\d+(?:\.\d+)?)\b',
    re.IGNORECASE,
)

# ── Print run ─────────────────────────────────────────────────────────────────

_PRINT_RUN_RE = re.compile(r'(?<!\d)/(\d+)\b')

# ── Year ─────────────────────────────────────────────────────────────────────

_YEAR_RE = re.compile(r'\b(20\d{2}|19[89]\d)\b')

# ── 1/1 ───────────────────────────────────────────────────────────────────────

_ONE_OF_ONE_RE = re.compile(r'\b1/1\b|\b1\s+of\s+1\b|\bsuperfractor\b|\blogoman\b', re.IGNORECASE)


def parse_title(title: str) -> dict:
    """
    Return a dict with extracted card attributes from an eBay title.

    Keys: year, set_name, print_run, is_auto, is_patch, is_rookie,
          grade, insert_type, is_graded, raw_title
    """
    t = title
    tl = t.lower()

    # Year
    ym = _YEAR_RE.search(t)
    year: Optional[int] = int(ym.group(1)) if ym else None

    # Print run — prefer "1/1" handling first
    print_run: Optional[int] = None
    if _ONE_OF_ONE_RE.search(tl):
        print_run = 1
    else:
        prm = _PRINT_RUN_RE.search(t)
        if prm:
            print_run = int(prm.group(1))

    # Grading
    gm = _GRADE_RE.search(t)
    grade: Optional[str] = f"{gm.group(1).upper()} {gm.group(2)}" if gm else None
    is_graded = grade is not None

    # Auto
    is_auto = bool(re.search(r'\bauto\b|\ba/u\b|\bautograph\b', tl))

    # Patch
    is_patch = bool(re.search(r'\bpatch\b|\brpa\b|\bjumbo patch\b|\blog(o)?\b', tl))

    # Rookie
    is_rookie = bool(re.search(r'\brc\b|\brookie\b', tl))

    # Set detection
    set_name: Optional[str] = None
    for name, patterns in _SETS:
        for pat in patterns:
            if pat in tl:
                set_name = name
                break
        if set_name:
            break

    # Synthesize insert type
    if print_run == 1:
        if is_patch and is_auto:
            insert_type = "Logoman / 1/1 Auto Patch"
        elif is_auto:
            insert_type = "Auto 1/1"
        else:
            insert_type = "1/1"
    elif is_patch and is_auto:
        insert_type = "Auto Patch"
    elif is_auto:
        insert_type = "Auto"
    elif is_patch:
        insert_type = "Patch"
    else:
        # Check for refractor/prizm parallels
        if re.search(r'\brefractor\b|\bprizm\b|\bchrome\b|\boptic\b', tl):
            insert_type = "Refractor / Prizm"
        else:
            insert_type = "Base"

    return {
        "year":        year,
        "set_name":    set_name,
        "print_run":   print_run,
        "is_auto":     is_auto,
        "is_patch":    is_patch,
        "is_rookie":   is_rookie,
        "is_graded":   is_graded,
        "grade":       grade,
        "insert_type": insert_type,
        "raw_title":   title,
    }


def group_key(parsed: dict) -> str:
    """Stable grouping key for a parsed card."""
    yr   = parsed.get("year") or "?"
    s    = parsed.get("set_name") or "Unknown Set"
    it   = parsed.get("insert_type") or "Base"
    pr   = parsed.get("print_run")
    pr_s = f"/{pr}" if pr else "unnumbered"
    gr   = parsed.get("grade") or "raw"
    return f"{yr}|{s}|{it}|{pr_s}|{gr}"
