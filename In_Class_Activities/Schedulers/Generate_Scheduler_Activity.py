#!/usr/bin/env python3
"""
Build the "Schedulers" in-class activity.

The activity needs no generated data -- both timing charts are fixed TikZ
drawings -- so this script just compiles the student handout and the
instructor key (drawn with \\def\\keymode{1}) with pdflatex.

Everything is written to ./build (scheduler_activity_student.pdf and
scheduler_activity_key.pdf).

Example:
    python Generate_Scheduler_Activity.py
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
TEX_FILE = "scheduler_activity.tex"


def compile_pdf(jobname: str, key: bool) -> bool:
    pretex = r"\def\keymode{1}" if key else ""
    cmd = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
           f"-output-directory={BUILD}", f"-jobname={jobname}",
           f"{pretex}\\input{{{TEX_FILE}}}"]
    result = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout[-2000:])
        print(f"pdflatex failed for {jobname}")
        return False
    print(f"Wrote {BUILD / (jobname + '.pdf')}")
    return True


def main() -> int:
    BUILD.mkdir(exist_ok=True)
    ok = compile_pdf("scheduler_activity_student", key=False)
    ok = compile_pdf("scheduler_activity_key", key=True) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
