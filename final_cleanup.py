#!/usr/bin/env python3
"""
cleanup_resume_pass2.py

Second pass: catches variable names, method names, headers, and phrases
the first regex list missed (e.g. "Key Metrics", "_generate_performance_summary",
local variable `resume`, "KEY METRICS SUMMARY").

Run from repo root:
    python3 cleanup_resume_pass2.py
"""

import re
from pathlib import Path

ROOT = Path(".").resolve()

# Order matters: longer/more specific patterns first so shorter ones
# don't clobber a replacement that already happened.
REPLACEMENTS = [
    # Method / function names
    (r"_generate_performance_summary", "_generate_performance_summary"),
    (r"generate_summary_from", "generate_summary_from"),

    # Variable name `resume` used as PerformanceSummary() instance
    (r"\bresume\.load_baseline\b", "summary.load_baseline"),
    (r"\bresume\.load_optimized\b", "summary.load_optimized"),
    (r"\bresume\.generate\b", "summary.generate"),
    (r"\bresume\.save_json\b", "summary.save_json"),
    (r"\bresume\.save\b", "summary.save"),
    (r"\bresume = PerformanceSummary\(\)", "summary = PerformanceSummary()"),

    # Headers / section titles
    (r"## Key Metrics", "## Key Metrics"),
    (r"Key Metrics", "Key Metrics"),
    (r"KEY METRICS SUMMARY \(copy this to your CV\):", "KEY METRICS SUMMARY:"),
    (r"KEY METRICS SUMMARY", "KEY METRICS SUMMARY"),

    # Descriptive / log text
    (r"Copy these directly onto your resume\. Every number is from real simulation data\.",
     "Every number below is from real simulation data."),
    (r"Generates professional resume content from optimization results\.",
     "Generates a performance summary from optimization results."),
    (r"Automatically produces a performance summary and supporting talking points",
     "Automatically produces a performance summary and supporting talking points"),
    (r"# Format numbers for summary output", "# Format numbers for summary output"),
    (r"Performance summary saved: %s", "Performance summary saved: %s"),
    (r"Performance summary generated: %s", "Performance summary generated: %s"),
    (r"No valid optimized metrics to generate performance summary from",
     "No valid optimized metrics to generate performance summary from"),
    (r"performance summary\s*:", "Performance summary:"),
    (r"#\s*-\s*performance summary", "#   - Performance summary"),
    (r"Resume\s*:\s*%s/performance_summary\.md", "Summary      : %s/performance_summary.md"),

    # Catch-all, case-insensitive, for anything still saying "resume" near "metric"
    (r"\bresume metrics\b", "performance summary", re.IGNORECASE),
    (r"\bresume-generation\b", "summary-generation", re.IGNORECASE),
]

TEXT_EXTS = {".py", ".md", ".sh", ".txt", ".yml", ".yaml", ".cfg", ".ini"}


def patch_text_files():
    patched = 0
    for path in ROOT.rglob("*"):
        if path.is_dir() or ".git" in path.parts:
            continue
        if path.suffix.lower() not in TEXT_EXTS:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue

        new_content = content
        for item in REPLACEMENTS:
            pattern, repl = item[0], item[1]
            flags = item[2] if len(item) > 2 else 0
            new_content = re.sub(pattern, repl, new_content, flags=flags)

        if new_content != content:
            path.write_text(new_content, encoding="utf-8")
            print(f"[OK] patched {path.relative_to(ROOT)}")
            patched += 1

    if patched == 0:
        print("[WARN] nothing patched this pass — check remaining grep output manually")


if __name__ == "__main__":
    patch_text_files()
    print("\nNow re-run: grep -ri resume . --include=*.py --include=*.md")
    print("Also note: rename_performance.py itself will always show up in the grep")
    print("(it's the script defining the patterns) — that's expected, delete it")
    print("once you're done, e.g.: rm rename_performance.py cleanup_resume_pass2.py")
