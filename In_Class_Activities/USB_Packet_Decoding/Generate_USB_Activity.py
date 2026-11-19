#!/usr/bin/env python3
"""
Build the "Decoding a USB Packet" in-class activity.

Uses USB_Frame_Generator.py from ../Serial_Waveform_Generation to create the
waveform, then writes the figure and the answer data that usb_activity.tex
needs, and compiles a student handout and an instructor key with pdflatex.

Everything is written to ./build (waveform PNG, generated .tex fragments,
usb_activity_student.pdf and usb_activity_key.pdf).

Examples:
    python Generate_USB_Activity.py                    # defaults from USB_Frame_Generator.py
    python Generate_USB_Activity.py --speed full --pid DATA1 --data 3C,A5,F0
    python Generate_USB_Activity.py --seed 7           # random variant (repeatable)
    python Generate_USB_Activity.py --no-pdf           # only write figure and .tex data
"""

import argparse
import random
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
TEX_FILE = "usb_activity.tex"

sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE.parent / "Serial_Waveform_Generation"))
import USB_Frame_Generator as usb  # noqa: E402

NUM_RANDOM_BYTES = 1


def stuff_positions(stuffed_bits: str):
    """Return the indexes in stuffed_bits that are stuff bits."""
    positions = []
    ones = 0
    next_is_stuff = False
    for i, b in enumerate(stuffed_bits):
        if next_is_stuff:
            positions.append(i)
            next_is_stuff = False
            ones = 0
            continue
        ones = ones + 1 if b == "1" else 0
        if ones == 6:
            next_is_stuff = True
    return positions


def random_variant(seed: int):
    """Pick a speed, PID and data bytes; make sure at least one stuff bit occurs."""
    rng = random.Random(seed)
    while True:
        speed = rng.choice(["low", "full"])
        pid_name = rng.choice(["DATA0", "DATA1"])
        data = [rng.randrange(256) for _ in range(NUM_RANDOM_BYTES)]
        pre, _ = usb.build_packet_bits(pid_name, data)
        if len(usb.stuff_bits(pre)) > len(pre):
            return speed, pid_name, data


def field_cell_ranges(stuffed_bits: str, idle_bits: int, num_bytes: int):
    """(first, last) 1-based bit times of each packet field, counting stuff bits."""
    stuff = set(stuff_positions(stuffed_bits))
    real = [i for i in range(len(stuffed_bits)) if i not in stuff]
    lengths = [("Sync", 8), ("Pid", 8), ("Data", 8 * num_bytes), ("Crc", 16)]
    ranges = {}
    start = 0
    for name, length in lengths:
        ranges[name] = (idle_bits + real[start] + 1,
                        idle_bits + real[start + length - 1] + 1)
        start += length
    return ranges


def build_data_tex(speed, pid_name, states, stuffed_bits, stuff_idx,
                   idle_bits, data_bytes) -> str:
    """Answer-key values for usb_activity.tex, written as LaTeX macros."""
    stuff_cells = ", ".join(str(idle_bits + i + 1) for i in stuff_idx) or "none"
    eop_first = idle_bits + len(stuffed_bits) + 1
    macros = {
        "usbSpeed": speed,
        "usbOtherSpeed": "full" if speed == "low" else "low",
        "usbIdleHigh": "D-" if speed == "low" else "D+",
        "usbIdleLow": "D+" if speed == "low" else "D-",
        "usbOtherIdleHigh": "D+" if speed == "low" else "D-",
        "usbBitTimeNs": f"{usb.BIT_TIME_NS[speed]:.0f}",
        "usbPidName": pid_name,
        "usbDataBytes": ", ".join(f"0x{b:02X}" for b in data_bytes),
        "usbNumStuff": str(len(stuff_idx)),
        "usbStuffCells": stuff_cells,
        "usbEopFirst": str(eop_first),
        "usbEopLast": str(eop_first + 1),
        "usbStates": states.replace("0", "S"),
        "usbBits": stuffed_bits,
    }
    ranges = field_cell_ranges(stuffed_bits, idle_bits, len(data_bytes))
    for name, (first, last) in ranges.items():
        macros[f"usb{name}First"] = str(first)
        macros[f"usb{name}Last"] = str(last)
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
    ap.add_argument("--speed", choices=["low", "full"], default=usb.SPEED)
    ap.add_argument("--pid", choices=sorted(usb.PIDS), default=usb.PID_NAME)
    ap.add_argument("--data", help="comma-separated hex bytes, e.g. 48,FF,1F")
    ap.add_argument("--seed", type=int, help="random speed/PID/data (repeatable)")
    ap.add_argument("--no-pdf", action="store_true", help="skip pdflatex")
    args = ap.parse_args()

    speed, pid_name, data_bytes = args.speed, args.pid, list(usb.DATA_BYTES)
    if args.seed is not None:
        speed, pid_name, data_bytes = random_variant(args.seed)
    if args.data:
        data_bytes = [int(x, 16) for x in args.data.split(",")]

    pre_bits, fields = usb.build_packet_bits(pid_name, data_bytes)
    stuffed = usb.stuff_bits(pre_bits)
    stuff_idx = stuff_positions(stuffed)
    states = usb.build_line_states(stuffed, usb.IDLE_BITS)

    BUILD.mkdir(exist_ok=True)
    usb.plot_usb_waveform(states, speed, filename=str(BUILD / "usb_waveform.png"),
                          number_bits=True)
    (BUILD / "usb_data.tex").write_text(
        build_data_tex(speed, pid_name, states, stuffed, stuff_idx,
                       usb.IDLE_BITS, data_bytes))

    print(f"USB {speed}-speed {pid_name}, data = "
          + " ".join(f"0x{b:02X}" for b in data_bytes)
          + f", {len(stuff_idx)} stuff bit(s), {len(states)} bit times")

    if args.no_pdf:
        return 0
    ok = compile_pdf("usb_activity_student", key=False)
    ok = compile_pdf("usb_activity_key", key=True) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
