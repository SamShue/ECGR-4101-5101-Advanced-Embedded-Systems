#!/usr/bin/env python3
"""
Generate the USB and CAN waveform PNGs used by the "USB and CAN Bus" quiz.

This script builds one USB packet and one CAN frame for each quiz version
(A and B), renders their bus waveforms with numbered bit times, and saves
the images directly into versionA/ and versionB/ so they can be included by
quiz_usb_can.tex and quiz_usb_can_large_print.tex. It also prints the
decoded answer-key data (PID, data bytes, stuff-bit bit times, field
boundaries, identifier) used to write the multiple-choice questions and the
solutions guide.

Reuses USB_Frame_Generator.py and CAN_Bus_Frame_Generator.py from
../../Serial_Waveform_Generation for all bit-level generation (NRZI, bit
stuffing, CRC) -- the same generators used by the USB/CAN frame decoding
homework and in-class activity.

Usage:
    python generate_waveforms.py
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE.parent.parent / "Serial_Waveform_Generation"))
import USB_Frame_Generator as usb       # noqa: E402
import CAN_Bus_Frame_Generator as can   # noqa: E402

IDLE_BITS = 3

# ================== Frame parameters for each quiz version =================
VERSION_A = {
    "usb": {"speed": "full", "pid": "DATA1", "data": [0x81]},
    "can": {"can_id": 0x245, "data": [0x5A], "rtr": 0, "ide": 0, "r0": 0},
}
VERSION_B = {
    "usb": {"speed": "low", "pid": "DATA0", "data": [0xFE]},
    "can": {"can_id": 0x1C8, "data": [0x3D, 0x56], "rtr": 0, "ide": 0, "r0": 0},
}

# Reference PID codes (4-bit) used to build the "decode the PID" answer-choice
# table in the quiz; students are given the resulting 8-bit bus patterns
# directly rather than being expected to know the PID codes from memory.
PID_CODES = {"DATA0": 0b0011, "DATA1": 0b1011, "ACK": 0b0010, "OUT": 0b0001}
# ============================================================================


def pid_bus_bits(pid_value: int) -> str:
    """8-bit PID byte (check nibble + PID, LSB first) as it appears on the
    bus, using the same formula as USB_Frame_Generator.build_packet_bits."""
    pid_byte = ((~pid_value & 0xF) << 4) | pid_value
    return usb.int_to_bits_lsb_first(pid_byte, 8)


def tex_hex(data_bytes):
    return ", ".join(f"0x{b:02X}" for b in data_bytes)


def usb_stuff_cells(stuffed_bits: str):
    """1-based bit times (counting idle bits) of each USB stuff bit."""
    cells, ones, next_is_stuff = [], 0, False
    for i, b in enumerate(stuffed_bits):
        if next_is_stuff:
            cells.append(IDLE_BITS + i + 1)
            next_is_stuff = False
            ones = 0
            continue
        ones = ones + 1 if b == "1" else 0
        if ones == 6:
            next_is_stuff = True
    return cells


def can_stuff_cells(stuffed_bits: str):
    """1-based bit times (counting idle bits) of each CAN stuff bit."""
    cells = []
    if not stuffed_bits:
        return cells
    run_len, last_bit = 1, stuffed_bits[0]
    i = 1
    while i < len(stuffed_bits):
        if run_len == 5:
            cells.append(IDLE_BITS + i + 1)
            run_len = 0
            i += 1
            continue
        b = stuffed_bits[i]
        run_len = run_len + 1 if b == last_bit else 1
        last_bit = b
        i += 1
    return cells


def usb_field_ranges(stuffed_bits: str, num_bytes: int):
    """(first, last) 1-based bit times of each USB field, counting idle bits
    and stuff bits (mirrors the homework's field-range logic)."""
    stuff = set(i - IDLE_BITS - 1 for i in usb_stuff_cells(stuffed_bits))
    real = [i for i in range(len(stuffed_bits)) if i not in stuff]
    lengths = [("SYNC", 8), ("PID", 8), ("DATA", 8 * num_bytes), ("CRC16", 16)]
    ranges, start = {}, 0
    for name, length in lengths:
        ranges[name] = (IDLE_BITS + real[start] + 1,
                        IDLE_BITS + real[start + length - 1] + 1)
        start += length
    return ranges


def build_usb_case(cfg: dict) -> dict:
    pre_bits, fields = usb.build_packet_bits(cfg["pid"], cfg["data"])
    stuffed_bits = usb.stuff_bits(pre_bits)
    states = usb.build_line_states(stuffed_bits, IDLE_BITS)
    eop_first = IDLE_BITS + len(stuffed_bits) + 1
    return {
        "speed": cfg["speed"],
        "bit_time_ns": usb.BIT_TIME_NS[cfg["speed"]],
        "states": states,
        "pid_name": cfg["pid"],
        "data_bytes": cfg["data"],
        "stuff_cells": usb_stuff_cells(stuffed_bits),
        "ranges": usb_field_ranges(stuffed_bits, len(cfg["data"])),
        "num_bits": len(states),
        "eop_first": eop_first,
    }


def can_field_ranges(stuffed_core_crc: str, num_bytes: int):
    """(first, last) 1-based bit times of each CAN field, counting idle bits
    and stuff bits (mirrors the homework's field-range logic). Only
    SOF..CRC are subject to bit stuffing; the trailing fixed fields follow
    immediately after the stuffed region."""
    stuff = set(i - IDLE_BITS - 1 for i in can_stuff_cells(stuffed_core_crc))
    real = [i for i in range(len(stuffed_core_crc)) if i not in stuff]
    lengths = [("SOF", 1), ("ID", 11), ("RTR", 1), ("IDE", 1), ("r0", 1),
               ("DLC", 4), ("DATA", 8 * num_bytes), ("CRC", 15)]
    ranges, start = {}, 0
    for name, length in lengths:
        ranges[name] = (IDLE_BITS + real[start] + 1,
                        IDLE_BITS + real[start + length - 1] + 1)
        start += length

    fixed_start = IDLE_BITS + len(stuffed_core_crc) + 1
    for name, length in [("CRC delim", 1), ("ACK", 1), ("ACK delim", 1),
                         ("EOF", 7), ("IFS", 3)]:
        ranges[name] = (fixed_start, fixed_start + length - 1)
        fixed_start += length
    return ranges


def build_can_case(cfg: dict) -> dict:
    can_id, data = cfg["can_id"], cfg["data"]
    id_bits = can.int_to_bits(can_id, 11)
    rtr_bit = "1" if cfg["rtr"] else "0"
    ide_bit = "1" if cfg["ide"] else "0"
    r0_bit = "1" if cfg["r0"] else "0"
    dlc_bits = can.int_to_bits(len(data), 4)
    data_bits = "".join(can.int_to_bits(b, 8) for b in data)
    core_bits = "0" + id_bits + rtr_bit + ide_bit + r0_bit + dlc_bits + data_bits
    crc_bits = can.compute_crc15_can(core_bits)

    stuffed_core_crc = can.stuff_bits(core_bits + crc_bits)
    trailer = "1" + "1" + "1" + "1111111" + "111"
    stuffed_frame = stuffed_core_crc + trailer
    full_frame = "1" * IDLE_BITS + stuffed_frame

    return {
        "can_id": can_id,
        "data_bytes": data,
        "num_data_bytes": len(data),
        "frame_text": full_frame,
        "stuff_cells": can_stuff_cells(stuffed_core_crc),
        "ranges": can_field_ranges(stuffed_core_crc, len(data)),
        "num_bits": len(full_frame),
    }


def main() -> int:
    print("PID reference table (8-bit bus pattern, LSB first):")
    for name, code in PID_CODES.items():
        print(f"  {name:6s} ({code:04b}) -> {pid_bus_bits(code)}")
    print()

    for label, version in (("A", VERSION_A), ("B", VERSION_B)):
        out_dir = HERE / f"version{label}"
        out_dir.mkdir(exist_ok=True)

        usb_case = build_usb_case(version["usb"])
        can_case = build_can_case(version["can"])

        usb_path = out_dir / "usb_waveform.png"
        can_path = out_dir / "can_waveform.png"
        usb.plot_usb_waveform(usb_case["states"], usb_case["speed"],
                              filename=str(usb_path), number_bits=True)
        can.plot_can_waveform(can_case["frame_text"], bit_time=can.BIT_TIME,
                              filename=str(can_path), number_bits=True)

        print(f"=== Version {label} ===")
        print(f"USB: {usb_case['speed']}-speed, PID={usb_case['pid_name']}, "
              f"data={tex_hex(usb_case['data_bytes'])}, "
              f"bits 1..{usb_case['num_bits']}, "
              f"stuff bit(s) at {usb_case['stuff_cells'] or 'none'}, "
              f"EOP starts at bit {usb_case['eop_first']}")
        print("  fields:", ", ".join(f"{k} {v[0]}-{v[1]}" for k, v in usb_case["ranges"].items()))
        print(f"CAN: ID=0x{can_case['can_id']:03X}, "
              f"data={tex_hex(can_case['data_bytes'])}, "
              f"num_data_bytes={can_case['num_data_bytes']}, "
              f"bits 1..{can_case['num_bits']}, "
              f"stuff bit(s) at {can_case['stuff_cells'] or 'none'}")
        print("  fields:", ", ".join(f"{k} {v[0]}-{v[1]}" for k, v in can_case["ranges"].items()))
        print(f"Wrote {usb_path.name} and {can_path.name} to {out_dir}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
