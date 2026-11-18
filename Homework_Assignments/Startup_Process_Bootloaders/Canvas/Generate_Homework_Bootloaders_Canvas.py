#!/usr/bin/env python3
"""
Build the Canvas-friendly HTML version of the "Startup Process and
Bootloaders" homework.

Produces the same problems as ../LaTeX/homework_bootloaders.tex, as a single
self-contained HTML file per variant (student / instructor key). The flash
map diagram for Problems 2 and 3 is drawn with matplotlib and embedded as a
base64 data URI, so the HTML can be pasted straight into Canvas's Rich
Content Editor "</> HTML Editor" view with no separate file upload. The same
PNG is also written to ./build/images/.

Usage:
    python Generate_Homework_Bootloaders_Canvas.py
"""

import base64
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
IMAGES_DIR = BUILD / "images"
DIAGRAM_PATH = IMAGES_DIR / "flash_map.png"

sys.dont_write_bytecode = True


def draw_flash_map(path: Path) -> None:
    """Flash memory map: bootloader at the base of flash, application above."""
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=150)
    ax.set_xlim(0, 10.5)
    ax.set_ylim(0, 6)
    ax.axis("off")

    left, width = 3.0, 3.8
    boot_h, app_h = 1.8, 3.2
    boot_y, app_y = 0.4, 0.4 + boot_h

    ax.add_patch(Rectangle((left, app_y), width, app_h, fc="#eef0ff", ec="black", lw=1.2))
    ax.add_patch(Rectangle((left, boot_y), width, boot_h, fc="#fdeedd", ec="black", lw=1.2))

    cx = left + width / 2
    ax.text(cx, app_y + app_h / 2,
            "Application\n0x0800_8000 \u2013 0x080F_FFFF\n"
            "has its own vector table\nat its base (0x0800_8000)",
            ha="center", va="center", fontsize=10, family="serif", linespacing=1.5)
    ax.text(cx, boot_y + boot_h / 2,
            "Bootloader\n0x0800_0000 \u2013 0x0800_7FFF\n"
            "has its own vector table\nat its base (0x0800_0000)",
            ha="center", va="center", fontsize=10, family="serif", linespacing=1.5)

    # Hardware fetch: horizontal arrow into the bootloader's base (bottom edge).
    ax.annotate("", xy=(left, boot_y), xytext=(left - 1.0, boot_y),
                arrowprops=dict(arrowstyle="->", lw=1.6, color="black"))
    ax.text(left - 1.1, boot_y, "hardware fetches the\ninitial SP and reset\n"
            "vector from here, always",
            ha="right", va="center", fontsize=9, family="serif")

    # Bootloader jump: out the bootloader's side, then into the application's base.
    jump_x = left + width + 0.8
    mid_y = boot_y + boot_h / 2
    ax.plot([left + width, jump_x], [mid_y, mid_y], ls="--", lw=1.6, color="black")
    ax.plot([jump_x, jump_x], [mid_y, app_y], ls="--", lw=1.6, color="black")
    ax.annotate("", xy=(left + width, app_y), xytext=(jump_x, app_y),
                arrowprops=dict(arrowstyle="->", lw=1.6, color="black", ls="--"))
    ax.text(jump_x + 0.15, (mid_y + app_y) / 2, "bootloader jumps here\nwhen it decides to run\n"
            "the application",
            ha="left", va="center", fontsize=9, family="serif")

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def img_data_uri(path: Path) -> str:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{data}"


def question(text: str, space_em: int, key_text: str, key: bool) -> str:
    """One lettered sub-question: prompt, ruled answer space, and (in key
    mode) the instructor's answer in red."""
    space = (f'<div style="height:{space_em}em; border-top:1px solid #000; '
             f'margin:14px 0 4px 0;"></div>')
    key_html = (f'<p style="color:#b00000;"><strong>Key:</strong> {key_text}</p>'
                if key else "")
    return f"<li>{text}\n{space}\n{key_html}</li>"


def lettered_list(items) -> str:
    return '<ol type="a">\n' + "\n".join(items) + "\n</ol>"


def build_body(diagram_uri: str, key: bool) -> str:
    p1 = [
        question(
            "Describe the sequence of events that take place on a generic "
            "Cortex-M microcontroller between power-up and the execution of "
            "the first instruction in <code>main()</code>. (Long answer "
            "&mdash; a full paragraph or a numbered list is fine.)",
            8,
            "Hardware automatically loads the initial stack pointer value from "
            "the base of the vector table, then automatically loads the address "
            "of the reset handler from the vector table and begins fetching "
            "instructions there. The reset handler then runs early core/device "
            "setup (clock tree, FPU, etc.), copies the initial values of the "
            "<code>.data</code> section out of flash and into SRAM, "
            "zero-initializes the <code>.bss</code> section in SRAM, and "
            "finally calls <code>main()</code>.", key),
        question(
            "There is no operating system loader on a bare-metal "
            "microcontroller. What actually performs the memory-setup job "
            "that an OS loader would normally do on a desktop system?",
            4,
            "The startup/reset-handler code that runs immediately after reset "
            "(provided by the vendor's startup file and tied to the linker "
            "script) performs this job &mdash; there is no OS or loader to do "
            "it for you.", key),
        question(
            "A student declares a global variable <code>static int "
            "sampleCount;</code> with no explicit initializer. At power-up, "
            "the SRAM holding that variable contains leftover, essentially "
            "random bits from before reset. Using what you know about the "
            "<code>.bss</code> section, explain why <code>sampleCount</code> "
            "is nonetheless guaranteed to read as <code>0</code> the very "
            "first time <code>main()</code> runs.",
            4,
            "Startup code explicitly zeroes the entire <code>.bss</code> "
            "region in SRAM before <code>main()</code> runs, overwriting "
            "whatever garbage was left there, regardless of what the memory "
            "happened to contain at power-up.", key),
        question(
            "Suppose the startup code's copy of <code>.data</code> from flash "
            "into SRAM were accidentally skipped. For a global variable "
            "declared <code>int sensorGain = 5;</code>, what value would it "
            "actually have the first time <code>main()</code> reads it? Why?",
            4,
            "Whatever leftover/garbage value already happened to be sitting "
            "in that SRAM location at power-up, not 5 &mdash; nothing ever "
            "copied the initializer value out of flash into SRAM.", key),
    ]

    p2 = [
        question(
            "At reset, hardware does not know anything about a "
            "&ldquo;bootloader&rdquo; or an &ldquo;application&rdquo; "
            "&mdash; it always fetches the initial stack pointer and reset "
            "vector from the same fixed base address of flash. Using the "
            "diagram above, which program is hardware guaranteed to run first "
            "after reset, and why must that particular program be the one "
            "placed at that fixed base address?",
            5,
            "The bootloader. Hardware unconditionally reads the fixed base "
            "address of flash on every reset, so whichever program's vector "
            "table sits there is the one that runs first &mdash; that has to "
            "be the bootloader, since it is the program responsible for "
            "deciding whether/when to run the application at all.", key),
        question(
            "Once the bootloader is done (for example, checking for a new "
            "firmware image) it jumps into the application's own reset "
            "handler. The application has its own vector table, located "
            "elsewhere in flash. If the application's startup code does "
            "nothing to tell the processor about this new vector table "
            "location, whose interrupt handlers will actually execute the "
            "next time an interrupt fires &mdash; the bootloader's or the "
            "application's? Explain why.",
            5,
            "The bootloader's. The processor's vector-table pointer was set "
            "once, at the very first reset, to the bootloader's table, and "
            "nothing has changed it. So even though the application's code is "
            "now running, any interrupt still looks up its handler address in "
            "the bootloader's vector table.", key),
        question(
            "Name the one step the application's startup code must perform so "
            "that interrupts are correctly routed to its own handlers instead "
            "of the bootloader's.",
            3,
            "It must update the processor's vector-table pointer/offset to the "
            "base address of the application's own vector table.", key),
        question(
            "This step is easy to forget during development. Why does "
            "skipping it not show up as an obvious problem right away, and "
            "what symptom would you expect to eventually see because of it?",
            4,
            "Everything else about the handoff &mdash; jumping to the "
            "application's reset handler, running <code>main()</code>, normal "
            "code execution &mdash; looks completely fine, because none of "
            "that depends on the vector table. The bug only shows up the next "
            "time an interrupt actually fires: the processor jumps into one "
            "of the bootloader's old handlers instead of the application's, "
            "typically causing a crash, hard fault, or other unexplained "
            "misbehavior.", key),
    ]

    p3 = [
        question(
            "The bootloader and the application are two completely separate "
            "projects, each with its own linker script. What does each linker "
            "script need to specify about its own program's flash region so "
            "that both programs can live in the same physical flash chip "
            "without one overwriting the other?",
            4,
            "Each linker script defines its own flash origin address and "
            "length for its program, and the two regions must not overlap "
            "each other.", key),
        question(
            "Explain, in your own words, why the bootloader and the "
            "application cannot simply be written as two functions compiled "
            "together into one single program.",
            5,
            "The whole point of a bootloader is to be able to update or "
            "replace the application later without rebuilding or disturbing "
            "the bootloader (and vice versa). That requires each one to be "
            "its own independently buildable, independently flashable program "
            "&mdash; with its own memory region, reset handler, and vector "
            "table &mdash; which is only possible if they are compiled and "
            "linked separately.", key),
        question(
            "If you wanted to update only the application in the field, "
            "without re-flashing the bootloader, what has to be true about "
            "how the two programs were originally loaded into flash for that "
            "to be possible?",
            4,
            "They must occupy separate, non-overlapping flash regions coming "
            "from separate linker scripts/builds, so that reprogramming only "
            "the application's region leaves the bootloader's region (and its "
            "vector table) completely untouched.", key),
        question(
            "Give one practical reason a shipped product would include a "
            "bootloader at all, instead of just shipping the application "
            "firmware by itself.",
            3,
            "Any reasonable answer tied to the material is acceptable, e.g.: "
            "remotely updating firmware on a device already deployed in the "
            "field without physical access to reprogram it, validating a new "
            "image before running it, recovering from a bad/incomplete "
            "update, or supporting more than one firmware image.", key),
    ]

    alt = ("Flash memory map: the bootloader (0x0800_0000 - 0x0800_7FFF) sits "
           "at the base of flash and the application (0x0800_8000 - "
           "0x080F_FFFF) sits above it. Each has its own vector table at its "
           "base. Hardware fetches the initial SP and reset vector from the "
           "bootloader's base; the bootloader jumps to the application's base.")

    return f"""
<h2>Problem 1: What Happens Before <code>main()</code> Runs</h2>
<p>On a desktop computer, an operating system loader reads your compiled
program and sets up memory for you before your <code>main</code> function ever
runs. A microcontroller has no operating system to do this job for it.</p>
{lettered_list(p1)}

<h2>Problem 2 &amp; 3 Setup: One Flash Chip, Two Programs</h2>
<p>A bootloader and the application it manages are built as two completely
separate programs. Both still have to live on the same physical flash chip, as
shown below (addresses are representative, not to scale).</p>
<p style="text-align:center;"><img src="{diagram_uri}" alt="{alt}"
  style="max-width:100%;"></p>

<h2>Problem 2: Relocating the Interrupt Vector Table</h2>
{lettered_list(p2)}

<h2>Problem 3: Two Programs, One Flash</h2>
{lettered_list(p3)}
"""


def build_html(diagram_uri: str, key: bool) -> str:
    suffix = " -- Instructor Key" if key else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Homework: Startup Process and Bootloaders{suffix}</title>
</head>
<body style="font-family: Georgia, 'Times New Roman', serif; max-width:900px; margin:0 auto;">
<h1>ECGR 4101/5101 -- Advanced Embedded Systems</h1>
<h2 style="margin-top:-10px;">Homework: Startup Process and Bootloaders{suffix}</h2>
<p>This homework is about building a conceptual picture of what a
microcontroller does between power-up and the first line of your
<code>main()</code> function, and of why a bootloader needs to exist at all.
You will <strong>not</strong> be asked to recall exact function names,
register bit layouts, or CubeMX steps &mdash; answer every question in your
own words, in a sentence or two, based on what we covered in class.</p>
{build_body(diagram_uri, key)}
</body>
</html>
"""


def main() -> int:
    BUILD.mkdir(parents=True, exist_ok=True)
    draw_flash_map(DIAGRAM_PATH)
    uri = img_data_uri(DIAGRAM_PATH)

    student = BUILD / "homework_bootloaders_student.html"
    key = BUILD / "homework_bootloaders_key.html"
    student.write_text(build_html(uri, key=False), encoding="utf-8")
    key.write_text(build_html(uri, key=True), encoding="utf-8")

    print(f"Wrote {student}")
    print(f"Wrote {key}")
    print(f"Wrote reference image to {DIAGRAM_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
