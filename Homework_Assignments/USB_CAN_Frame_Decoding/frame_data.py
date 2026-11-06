#!/usr/bin/env python3
"""
Shared frame data for the "Decoding USB and CAN Frames" homework.

This module builds the USB (full-speed and low-speed) and CAN example
frames, computes their answer-key data (field bit-time ranges, stuff-bit
positions, PID/ID/data decode, CRC), and generates the waveform PNGs used by
both output formats. It has no knowledge of LaTeX or HTML -- the LaTeX/ and
Canvas/ generator scripts both import this module so the two outputs always
describe the exact same frames.

Reuses USB_Frame_Generator.py and CAN_Bus_Frame_Generator.py from
../../Serial_Waveform_Generation for all bit-level generation (NRZI, bit
stuffing, CRC), the same code used by the in-class activity.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE.parent.parent / "Serial_Waveform_Generation"))
import USB_Frame_Generator as usb       # noqa: E402
import CAN_Bus_Frame_Generator as can   # noqa: E402

IDLE_BITS = 3

# ================== Frame parameters (chosen so each example contains at
# least one stuff bit, which makes for a more interesting problem) ==========
USB_FULL = {"speed": "full", "pid": "DATA1", "data": [0xED, 0xBF]}
USB_LOW = {"speed": "low", "pid": "DATA0", "data": [0x6D, 0x7F]}
CAN_FRAME = {"can_id": 0x7A6, "data": [0x1C, 0x2E], "rtr": 0, "ide": 0, "r0": 0}
# ============================================================================


def tex_hex(data_bytes):
    return ", ".join(f"0x{b:02X}" for b in data_bytes)


# ---------------------------------------------------------------- USB -----
def usb_stuff_positions(stuffed_bits: str):
    """Return the indexes in stuffed_bits that are USB stuff bits."""
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


def usb_field_cell_ranges(stuffed_bits: str, idle_bits: int, num_bytes: int):
    """(first, last) 1-based bit times of each USB field, counting stuff bits."""
    stuff = set(usb_stuff_positions(stuffed_bits))
    real = [i for i in range(len(stuffed_bits)) if i not in stuff]
    lengths = [("Sync", 8), ("Pid", 8), ("Data", 8 * num_bytes), ("Crc", 16)]
    ranges = {}
    start = 0
    for name, length in lengths:
        ranges[name] = (idle_bits + real[start] + 1,
                        idle_bits + real[start + length - 1] + 1)
        start += length
    return ranges


def build_usb_case(cfg: dict) -> dict:
    """Return the student-visible frame data plus the full answer key for one
    USB packet."""
    pre_bits, fields = usb.build_packet_bits(cfg["pid"], cfg["data"])
    stuffed_bits = usb.stuff_bits(pre_bits)
    stuff_idx = usb_stuff_positions(stuffed_bits)
    states = usb.build_line_states(stuffed_bits, IDLE_BITS)
    ranges = usb_field_cell_ranges(stuffed_bits, IDLE_BITS, len(cfg["data"]))
    eop_first = IDLE_BITS + len(stuffed_bits) + 1

    return {
        "speed": cfg["speed"],
        "bit_time_ns": usb.BIT_TIME_NS[cfg["speed"]],
        "states": states,                            # raw J/K/0 states, for plotting
        "states_text": states.replace("0", "S"),      # S = SE0, for readability
        "pid_name": cfg["pid"],
        "data_bytes": cfg["data"],
        "stuffed_bits": stuffed_bits,
        "pre_stuff_bits": pre_bits,
        "crc16": fields["CRC16"],
        "num_stuff": len(stuff_idx),
        "stuff_cells": ", ".join(str(IDLE_BITS + i + 1) for i in stuff_idx) or "none",
        "ranges": ranges,
        "eop_cells": (eop_first, eop_first + 1),
    }


# ---------------------------------------------------------------- CAN -----
def can_stuff_positions(stuffed_bits: str):
    """
    Return the indexes in stuffed_bits (the stuffed core+CRC region only)
    that are CAN stuff bits, found by replaying the same run-length rule the
    encoder uses: after five consecutive identical bits, the next bit is a
    stuff bit.
    """
    positions = []
    if not stuffed_bits:
        return positions
    run_len = 1
    last_bit = stuffed_bits[0]
    i = 1
    while i < len(stuffed_bits):
        if run_len == 5:
            positions.append(i)
            run_len = 0
            i += 1
            continue
        b = stuffed_bits[i]
        if b == last_bit:
            run_len += 1
        else:
            run_len = 1
            last_bit = b
        i += 1
    return positions


def can_field_cell_ranges(stuffed_core_crc: str, idle_bits: int, num_bytes: int):
    """(first, last) 1-based bit times of each CAN field, counting stuff bits.
    Only SOF..CRC are subject to bit stuffing; the trailing fixed fields
    (CRC delimiter, ACK slot, ACK delimiter, EOF, IFS) are never stuffed and
    immediately follow the stuffed region."""
    stuff = set(can_stuff_positions(stuffed_core_crc))
    real = [i for i in range(len(stuffed_core_crc)) if i not in stuff]
    # Note: for the LaTeX output, field names become macro name fragments
    # (e.g. "Can" + name + "First"), so they must be letters only -- no
    # digits are allowed in a LaTeX control word name.
    lengths = [("Sof", 1), ("Id", 11), ("Rtr", 1), ("Ide", 1), ("Rsvd", 1),
               ("Dlc", 4), ("Data", 8 * num_bytes), ("Crc", 15)]
    ranges = {}
    start = 0
    for name, length in lengths:
        ranges[name] = (idle_bits + real[start] + 1,
                        idle_bits + real[start + length - 1] + 1)
        start += length

    fixed_start = idle_bits + len(stuffed_core_crc) + 1
    for name, length in [("CrcDelim", 1), ("Ack", 1), ("AckDelim", 1),
                         ("Eof", 7), ("Ifs", 3)]:
        ranges[name] = (fixed_start, fixed_start + length - 1)
        fixed_start += length
    return ranges


def build_can_case(cfg: dict) -> dict:
    """Return the student-visible frame data plus the full answer key for the
    CAN frame."""
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
    stuff_idx = can_stuff_positions(stuffed_core_crc)

    trailer = "1" + "1" + "1" + "1111111" + "111"   # CRC delim, ACK, ACK delim, EOF, IFS
    stuffed_frame = stuffed_core_crc + trailer
    idle = "1" * IDLE_BITS
    full_frame = idle + stuffed_frame

    ranges = can_field_cell_ranges(stuffed_core_crc, IDLE_BITS, len(data))

    return {
        "can_id": can_id,
        "data_bytes": data,
        "frame_text": full_frame,
        "stuffed_core_crc": stuffed_core_crc,
        "destuffed_core_crc": core_bits + crc_bits,
        "core_bits": core_bits,
        "crc15": crc_bits,
        "num_stuff": len(stuff_idx),
        "stuff_cells": ", ".join(str(IDLE_BITS + i + 1) for i in stuff_idx) or "none",
        "ranges": ranges,
    }


def build_all_cases():
    """Return (usb_full, usb_low, can_case) built from the module parameters."""
    return (build_usb_case(USB_FULL), build_usb_case(USB_LOW),
            build_can_case(CAN_FRAME))


def generate_waveform_images(usb_full: dict, usb_low: dict, can_case: dict,
                             out_dir: Path):
    """Render the three waveform PNGs (numbered bit times) into out_dir and
    return their paths as (usb_full_path, usb_low_path, can_path)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    usb_full_path = out_dir / "usb_full_waveform.png"
    usb_low_path = out_dir / "usb_low_waveform.png"
    can_path = out_dir / "can_waveform.png"

    usb.plot_usb_waveform(usb_full["states"], usb_full["speed"],
                          filename=str(usb_full_path), number_bits=True)
    usb.plot_usb_waveform(usb_low["states"], usb_low["speed"],
                          filename=str(usb_low_path), number_bits=True)
    can.plot_can_waveform(can_case["frame_text"], bit_time=can.BIT_TIME,
                          filename=str(can_path), number_bits=True)
    return usb_full_path, usb_low_path, can_path
