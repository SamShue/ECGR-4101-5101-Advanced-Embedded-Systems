#!/usr/bin/env python3
"""
Build the Canvas-friendly HTML version of the "USB and CAN Frame Decoding"
homework.

Produces the same three problems as the LaTeX/ version (same frame data,
from ../frame_data.py, so both outputs describe identical frames), but as a
single self-contained HTML file per variant (student / instructor key).
Waveform images are embedded directly as base64 data URIs, so the HTML can
be pasted straight into Canvas's Rich Content Editor "</> HTML Editor" view
with no separate file upload required. The same PNGs are also written to
./build/images/ in case an instructor prefers to upload them to Canvas Files
and use lighter-weight <img> references instead.

Usage:
    python Generate_Homework_USB_CAN_Canvas.py
"""

import base64
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
IMAGES_DIR = BUILD / "images"

sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE.parent))
import frame_data as fd   # noqa: E402


def img_data_uri(path: Path) -> str:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{data}"


def html_escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;"))


def key_span(text: str) -> str:
    return f'<span style="color:#b00000;"><strong>Key:</strong> {text}</span>'


def blank(width_em: int = 10) -> str:
    return (f'<span style="display:inline-block; min-width:{width_em}em; '
            f'border-bottom:1px solid #000;">&nbsp;</span>')


def answer_space(height_em: int = 4) -> str:
    return (f'<div style="height:{height_em}em; border-top:1px solid #000; '
            f'margin:14px 0 4px 0;"></div>')


def usb_problem(number: int, title: str, image_uri: str, case: dict,
                key: bool) -> str:
    stuff_key = (f"Stuff bit(s) at bit time(s) {case['stuff_cells']}. "
                 f"SYNC {case['ranges']['Sync'][0]}-{case['ranges']['Sync'][1]}, "
                 f"PID {case['ranges']['Pid'][0]}-{case['ranges']['Pid'][1]}, "
                 f"DATA {case['ranges']['Data'][0]}-{case['ranges']['Data'][1]}, "
                 f"CRC16 {case['ranges']['Crc'][0]}-{case['ranges']['Crc'][1]}, "
                 f"EOP {case['eop_cells'][0]}-{case['eop_cells'][1]}.")
    data_hex = fd.tex_hex(case["data_bytes"])
    pid_line = f"<br>{key_span(case['pid_name'])}" if key else ""
    data_line = f"<br>{key_span(data_hex)}" if key else ""

    return f"""
<h2>Problem {number}: {html_escape(title)}</h2>
<p>The figure below is a capture of the D+ and D- lines during a single
<strong>{html_escape(case['speed'])}-speed</strong> USB data packet. The
numbers along the top count the bit times, and each dotted line marks the
boundary between two bit times.</p>
<p><img src="{image_uri}" alt="USB {html_escape(case['speed'])}-speed waveform"
    style="max-width:100%;"></p>
<p>Label any stuff bit(s) and the boundaries of the SYNC, PID, DATA, CRC16,
and EOP fields directly on the figure above.</p>
{key_span(stuff_key) if key else ""}
{answer_space()}
<ol>
  <li>Decode the PID field. What type of packet is this? {blank()}
    {pid_line}</li>
  <li>What data byte(s) does this packet carry? Give your answer in hex.
    {blank(16)}
    {data_line}</li>
</ol>
"""


def can_problem(image_uri: str, case: dict, key: bool) -> str:
    r = case["ranges"]
    stuff_key = (f"Stuff bit(s) at bit time(s) {case['stuff_cells']}. "
                 f"SOF {r['Sof'][0]}-{r['Sof'][1]}, ID {r['Id'][0]}-{r['Id'][1]}, "
                 f"RTR {r['Rtr'][0]}-{r['Rtr'][1]}, IDE {r['Ide'][0]}-{r['Ide'][1]}, "
                 f"r0 {r['Rsvd'][0]}-{r['Rsvd'][1]}, DLC {r['Dlc'][0]}-{r['Dlc'][1]}, "
                 f"DATA {r['Data'][0]}-{r['Data'][1]}, CRC {r['Crc'][0]}-{r['Crc'][1]}, "
                 f"CRC delimiter {r['CrcDelim'][0]}-{r['CrcDelim'][1]}, "
                 f"ACK {r['Ack'][0]}-{r['Ack'][1]}, EOF {r['Eof'][0]}-{r['Eof'][1]}.")
    can_id_hex = f"0x{case['can_id']:03X}"
    data_hex = fd.tex_hex(case["data_bytes"])
    id_line = f"<br>{key_span(can_id_hex)}" if key else ""
    data_line = f"<br>{key_span(data_hex)}" if key else ""

    return f"""
<h2>Problem 3: CAN Data Frame</h2>
<p>The figure below is a capture of the CAN_H and CAN_L lines during a
single <strong>standard frame</strong> (11-bit identifier) CAN data frame.
The numbers along the top count the bit times, and each dotted line marks
the boundary between two bit times. (Recall that for CAN, a dominant bit is
a logical <code>0</code> and a recessive bit is a logical <code>1</code>.)</p>
<p><img src="{image_uri}" alt="CAN waveform" style="max-width:100%;"></p>
<p>Label any stuff bit(s) and the boundaries of the SOF, identifier, RTR,
IDE, r0, DLC, DATA, CRC, CRC delimiter, ACK, and EOF fields directly on the
figure above. (Note that CAN's bit-stuffing rule is different from USB's.)</p>
{key_span(stuff_key) if key else ""}
{answer_space()}
<ol>
  <li>Decode the 11-bit identifier. Give your answer in hex. {blank()}
    {id_line}</li>
  <li>What data byte(s) does this frame carry? Give your answer in hex.
    {blank(16)}
    {data_line}</li>
</ol>
"""


def build_html(usb_full: dict, usb_low: dict, can_case: dict,
               usb_full_uri: str, usb_low_uri: str, can_uri: str,
               key: bool) -> str:
    suffix = " -- Instructor Key" if key else ""
    body = "".join([
        usb_problem(1, "USB Full-Speed Packet", usb_full_uri, usb_full, key),
        usb_problem(2, "USB Low-Speed Packet", usb_low_uri, usb_low, key),
        can_problem(can_uri, can_case, key),
    ])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Homework: Decoding USB and CAN Frames{suffix}</title>
</head>
<body style="font-family: Georgia, 'Times New Roman', serif; max-width:900px; margin:0 auto;">
<h1>ECGR 4101/5101 -- Advanced Embedded Systems</h1>
<h2 style="margin-top:-10px;">Homework: Decoding USB and CAN Frames{suffix}</h2>
<p>Each problem below gives you a waveform captured directly off the bus for
one frame. No reference tables or diagrams are provided -- you are expected
to look up the relevant encoding rules, field formats, and PID codes in the
USB 2.0 specification (Problems 1-2) and the classical CAN / ISO 11898-1
specification (Problem 3). Finding this information yourself is part of the
assignment. <strong>On each figure, label any stuff bit(s) you find and the
boundaries of each field (by bit time), then answer the short questions
below it.</strong></p>
{body}
</body>
</html>
"""


def main() -> int:
    usb_full, usb_low, can_case = fd.build_all_cases()

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    usb_full_path, usb_low_path, can_path = fd.generate_waveform_images(
        usb_full, usb_low, can_case, IMAGES_DIR)

    usb_full_uri = img_data_uri(usb_full_path)
    usb_low_uri = img_data_uri(usb_low_path)
    can_uri = img_data_uri(can_path)

    student_html = build_html(usb_full, usb_low, can_case,
                              usb_full_uri, usb_low_uri, can_uri, key=False)
    key_html = build_html(usb_full, usb_low, can_case,
                          usb_full_uri, usb_low_uri, can_uri, key=True)

    (BUILD / "homework_usb_can_student.html").write_text(student_html, encoding="utf-8")
    (BUILD / "homework_usb_can_key.html").write_text(key_html, encoding="utf-8")

    print(f"USB full-speed {fd.USB_FULL['pid']}, data = {fd.tex_hex(fd.USB_FULL['data'])}, "
          f"{usb_full['num_stuff']} stuff bit(s)")
    print(f"USB low-speed  {fd.USB_LOW['pid']}, data = {fd.tex_hex(fd.USB_LOW['data'])}, "
          f"{usb_low['num_stuff']} stuff bit(s)")
    print(f"CAN ID=0x{fd.CAN_FRAME['can_id']:03X}, data = {fd.tex_hex(fd.CAN_FRAME['data'])}, "
          f"{can_case['num_stuff']} stuff bit(s)")
    print(f"Wrote {BUILD / 'homework_usb_can_student.html'}")
    print(f"Wrote {BUILD / 'homework_usb_can_key.html'}")
    print(f"Wrote reference images to {IMAGES_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
