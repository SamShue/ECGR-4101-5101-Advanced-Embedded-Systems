#!/usr/bin/env python3
"""
Build the LaTeX/PDF version of the "USB and CAN Frame Decoding" homework.

Each problem shows a waveform figure (generated the same way as the in-class
activity) with numbered bit times, but -- unlike the in-class activity -- no
PID table or field-format diagram is given. Students must look up the USB
2.0 / classical CAN (ISO 11898-1) specifications themselves to know what to
look for; that research is an intentional part of the assignment.

Students work directly on the figure: they label any stuff bit(s) and the
field boundaries on the waveform itself (by bit time), then answer a few
short decode questions (PID, data bytes, identifier, CRC check) below it.
Blank space is left under each figure for that annotation work.

All frame data (bit sequences, field ranges, CRCs, etc.) comes from
../frame_data.py, which is shared with the Canvas/ HTML version so both
outputs describe the exact same frames.

Everything is written to ./build (waveform PNGs, generated .tex fragment,
homework_usb_can_student.pdf and homework_usb_can_key.pdf) via pdflatex.

Usage:
    python Generate_Homework_USB_CAN_LaTeX.py           # compile PDFs
    python Generate_Homework_USB_CAN_LaTeX.py --no-pdf  # only write .tex data
"""

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
TEX_FILE = "homework_usb_can.tex"

sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE.parent))
import frame_data as fd   # noqa: E402


def build_data_tex(usb_full: dict, usb_low: dict, can_case: dict) -> str:
    """Answer-key values for homework_usb_can.tex, written as LaTeX macros."""
    macros = {}

    for prefix, case in (("UsbFull", usb_full), ("UsbLow", usb_low)):
        macros[f"{prefix}States"] = case["states_text"]
        macros[f"{prefix}Speed"] = case["speed"]
        macros[f"{prefix}BitTimeNs"] = f"{case['bit_time_ns']:.0f}"
        macros[f"{prefix}PidName"] = case["pid_name"]
        macros[f"{prefix}DataBytes"] = fd.tex_hex(case["data_bytes"])
        macros[f"{prefix}StuffedBits"] = case["stuffed_bits"]
        macros[f"{prefix}PreStuffBits"] = case["pre_stuff_bits"]
        macros[f"{prefix}NumStuff"] = str(case["num_stuff"])
        macros[f"{prefix}StuffCells"] = case["stuff_cells"]
        macros[f"{prefix}EopFirst"] = str(case["eop_cells"][0])
        macros[f"{prefix}EopLast"] = str(case["eop_cells"][1])
        for name, (first, last) in case["ranges"].items():
            macros[f"{prefix}{name}First"] = str(first)
            macros[f"{prefix}{name}Last"] = str(last)

    macros["CanFrameText"] = can_case["frame_text"]
    macros["CanId"] = f"0x{can_case['can_id']:03X}"
    macros["CanDataBytes"] = fd.tex_hex(can_case["data_bytes"])
    macros["CanDestuffedCoreCrc"] = can_case["destuffed_core_crc"]
    macros["CanNumStuff"] = str(can_case["num_stuff"])
    macros["CanStuffCells"] = can_case["stuff_cells"]
    for name, (first, last) in can_case["ranges"].items():
        macros[f"Can{name}First"] = str(first)
        macros[f"Can{name}Last"] = str(last)

    return "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in macros.items())


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
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-pdf", action="store_true", help="skip pdflatex")
    args = ap.parse_args()

    usb_full, usb_low, can_case = fd.build_all_cases()

    BUILD.mkdir(exist_ok=True)
    fd.generate_waveform_images(usb_full, usb_low, can_case, BUILD)

    (BUILD / "homework_data.tex").write_text(
        build_data_tex(usb_full, usb_low, can_case))

    print(f"USB full-speed {fd.USB_FULL['pid']}, data = {fd.tex_hex(fd.USB_FULL['data'])}, "
          f"{usb_full['num_stuff']} stuff bit(s)")
    print(f"USB low-speed  {fd.USB_LOW['pid']}, data = {fd.tex_hex(fd.USB_LOW['data'])}, "
          f"{usb_low['num_stuff']} stuff bit(s)")
    print(f"CAN ID=0x{fd.CAN_FRAME['can_id']:03X}, data = {fd.tex_hex(fd.CAN_FRAME['data'])}, "
          f"{can_case['num_stuff']} stuff bit(s)")

    if args.no_pdf:
        return 0
    ok = compile_pdf("homework_usb_can_student", key=False)
    ok = compile_pdf("homework_usb_can_key", key=True) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
