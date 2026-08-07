"""
Instruction Decode Stage Animation
====================================

Focuses on the decode stage of a LEGv8-style single-cycle processor.
The 32-bit ADD instruction leaving the Instruction Memory fans out
simultaneously onto four field buses, each annotated with a tick mark
showing its bus width.

    ADD X1, X2, X3      (LEGv8 R-type, 0x8B030041)

    Format: opcode[31:21] | Rm[20:16] | shamt[15:10] | Rn[9:5] | Rd[4:0]

Fields decoded and animated:
    [31:21]  11 bits  →  opcode  →  Control unit
    [20:16]   5 bits  →  Rm      →  Read register 2
    [ 9: 5]   5 bits  →  Rn      →  Read register 1
    [ 4: 0]   5 bits  →  Rd      →  Write register

Diagonal tick marks (╱ with count) annotate every wire segment with its
bus width.  No blocks other than the Instruction Memory are rendered.

Run:
    python3 decode_animation.py

Output:
    decode_animation.gif
"""

import numpy as np
import matplotlib

matplotlib.use("Agg")  # headless rendering
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle
from matplotlib.animation import FuncAnimation, PillowWriter


# ─────────────────────────────────────────────────────────────────────────── #
#  Instruction: ADD X1, X2, X3  (LEGv8 R-type, 32-bit)
#  opcode[31:21] | Rm[20:16] | shamt[15:10] | Rn[9:5] | Rd[4:0]
# ─────────────────────────────────────────────────────────────────────────── #
INSTR_TEXT  = "ADD X1, X2, X3"
OPCODE_BITS = "10001011000"   # 11 bits  (ADD)
RM_BITS     = "00011"         #  5 bits  (X3 = register 3)
SHAMT_BITS  = "000000"        #  6 bits  (shift amount = 0)
RN_BITS     = "00010"         #  5 bits  (X2 = register 2)
RD_BITS     = "00001"         #  5 bits  (X1 = register 1)
FULL_BITS   = OPCODE_BITS + RM_BITS + SHAMT_BITS + RN_BITS + RD_BITS
INSTR_HEX   = f"0x{int(FULL_BITS, 2):08X}"   # 0x8B030041


# ─────────────────────────────────────────────────────────────────────────── #
#  Colour palette
# ─────────────────────────────────────────────────────────────────────────── #
CLR_WIRE     = "#9fb4c4"
CLR_BOX      = "#eef3f7"
CLR_BOX_EDGE = "#2b3a46"
CLR_TEXT     = "#1c2833"
CLR_TICK     = "#2b3a46"   # tick mark strokes

CLR_MAIN   = "#546e7a"   # dark teal-gray   — full 32-bit instruction bus
CLR_OPCODE = "#e53935"   # red              — opcode field
CLR_RM     = "#1e88e5"   # blue             — Rm field
CLR_RN     = "#43a047"   # green            — Rn field
CLR_RD     = "#8e24aa"   # purple           — Rd field

FIELD_ORDER  = ("opcode", "Rm", "Rn", "Rd")
FIELD_COLORS = {
    "opcode": CLR_OPCODE,
    "Rm":     CLR_RM,
    "Rn":     CLR_RN,
    "Rd":     CLR_RD,
}


# ─────────────────────────────────────────────────────────────────────────── #
#  Drawing helpers
# ─────────────────────────────────────────────────────────────────────────── #
def box(ax, x, y, w, h, label, face=CLR_BOX, fontsize=10, edge=CLR_BOX_EDGE):
    p = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.06",
        linewidth=1.6, edgecolor=edge, facecolor=face, zorder=3,
    )
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, label,
            ha="center", va="center", fontsize=fontsize,
            color=CLR_TEXT, zorder=4, weight="bold")
    return (x, y, w, h)


def wire(ax, pts, color=CLR_WIRE, lw=2.2, z=2):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    ax.plot(xs, ys, color=color, lw=lw,
            solid_capstyle="round", solid_joinstyle="round", zorder=z)


def tick_mark(ax, x, y, count, color=CLR_TICK):
    """Diagonal slash through a horizontal wire at (x, y) with bit-count label.

    The slash rises left-to-right (~50°) and the count appears just above its
    upper tip, matching standard logic-diagram bus-width notation.
    """
    dx, dy = 0.090, 0.155
    ax.plot([x - dx, x + dx], [y - dy, y + dy],
            color=color, lw=2.1, solid_capstyle="round", zorder=6)
    ax.text(x + dx + 0.07, y + dy + 0.07, str(count),
            ha="left", va="bottom", fontsize=8.5,
            color=color, weight="bold", zorder=7)


def polyline_points(pts, n):
    """Resample a polyline to n evenly-spaced points (used for packet animation)."""
    pts = np.array(pts, dtype=float)
    seg = np.sqrt(((pts[1:] - pts[:-1]) ** 2).sum(axis=1))
    cum = np.concatenate([[0], np.cumsum(seg)])
    total = cum[-1]
    if total == 0:
        return np.repeat(pts[:1], n, axis=0)
    d = np.linspace(0, total, n)
    return np.column_stack([np.interp(d, cum, pts[:, 0]),
                            np.interp(d, cum, pts[:, 1])])


# ─────────────────────────────────────────────────────────────────────────── #
#  Canvas
# ─────────────────────────────────────────────────────────────────────────── #
fig, ax = plt.subplots(figsize=(17.0, 10.4))
ax.set_xlim(0, 17.0)
ax.set_ylim(0, 10.4)
ax.axis("off")
fig.patch.set_facecolor("white")


# ─────────────────────────────────────────────────────────────────────────── #
#  Static layout geometry
# ─────────────────────────────────────────────────────────────────────────── #
# Instruction Memory block
IM = box(ax, 1.1, 4.4, 2.3, 2.0, "Instruction\nMemory", fontsize=10.5)

# Key x / y coordinates derived from IM geometry
IM_OUT  = (IM[0] + IM[2], IM[1] + IM[3] * 0.5)   # right-centre output port (3.4, 5.4)
SPINE_X = 5.4                                       # x of the vertical fan-out spine
JUNCT_Y = IM_OUT[1]                                 # y where main bus meets the spine (5.4)

SPINE_BOT = 2.4      # bottom of the vertical spine
SPINE_TOP = 8.9      # top of the vertical spine

# y-coordinates of each field's horizontal branch wire
BRANCH_Y = {
    "opcode": 8.6,
    "Rm":     7.0,
    "Rn":     JUNCT_Y,   # 5.4  — straight through from main bus
    "Rd":     3.7,
}
BRANCH_END_X = 13.9   # where each branch wire terminates (endpoint labels start here)

# Bit widths for tick marks
FIELD_WIDTHS = {"opcode": 11, "Rm": 5, "Rn": 5, "Rd": 5}

# Bit values carried on each branch packet
FIELD_BITS = {
    "opcode": OPCODE_BITS,
    "Rm":     RM_BITS,
    "Rn":     RN_BITS,
    "Rd":     RD_BITS,
}

# Human-readable destination for each field
FIELD_DEST = {
    "opcode": ("→ Control unit",    f"{OPCODE_BITS}  (ADD)"),
    "Rm":     ("→ Read register 2", f"{RM_BITS}             (X3)"),
    "Rn":     ("→ Read register 1", f"{RN_BITS}             (X2)"),
    "Rd":     ("→ Write register",  f"{RD_BITS}             (X1)"),
}

# Field bit-range labels shown near the spine
FIELD_SPANS = {"opcode": "[31:21]", "Rm": "[20:16]", "Rn": "[9:5]", "Rd": "[4:0]"}


# ─────────────────────────────────────────────────────────────────────────── #
#  PC address stub (dashed arrow into IM — PC block not shown)
# ─────────────────────────────────────────────────────────────────────────── #
ax.annotate(
    "", xy=(IM[0], JUNCT_Y), xytext=(0.35, JUNCT_Y),
    arrowprops=dict(arrowstyle="->", color=CLR_WIRE, lw=1.6,
                    linestyle="dashed", mutation_scale=14),
    zorder=2,
)
ax.text(0.28, JUNCT_Y + 0.26, "PC\naddress", ha="center", va="bottom",
        fontsize=7.5, style="italic", color=CLR_WIRE, zorder=5)


# ─────────────────────────────────────────────────────────────────────────── #
#  Main instruction bus   IM output → spine
# ─────────────────────────────────────────────────────────────────────────── #
wire(ax, [IM_OUT, (SPINE_X, JUNCT_Y)], color=CLR_MAIN, lw=3.0)

# 32-bit tick mark on the main horizontal bus
MID_MAIN_X = (IM_OUT[0] + SPINE_X) / 2   # 4.4
tick_mark(ax, MID_MAIN_X, JUNCT_Y, 32, color=CLR_TICK)

ax.text(MID_MAIN_X, JUNCT_Y - 0.30, "Instruction [31:0]",
        ha="center", va="top", fontsize=8.0,
        style="italic", color=CLR_MAIN, zorder=5)

# Junction dot where the main bus meets the spine
ax.add_patch(Circle((SPINE_X, JUNCT_Y), 0.075, color=CLR_MAIN, zorder=4))


# ─────────────────────────────────────────────────────────────────────────── #
#  Vertical fan-out spine
# ─────────────────────────────────────────────────────────────────────────── #
wire(ax, [(SPINE_X, SPINE_BOT), (SPINE_X, SPINE_TOP)], color=CLR_MAIN, lw=3.0)


# ─────────────────────────────────────────────────────────────────────────── #
#  Branch wires, tap dots, tick marks, and labels
# ─────────────────────────────────────────────────────────────────────────── #
TICK_X = (SPINE_X + BRANCH_END_X) / 2    # midpoint of each branch wire

for field in FIELD_ORDER:
    by  = BRANCH_Y[field]
    clr = FIELD_COLORS[field]

    # Horizontal branch wire from spine to endpoint
    wire(ax, [(SPINE_X, by), (BRANCH_END_X, by)], color=clr, lw=2.4)

    # Tap dot on the spine (Rn shares the same y as the main-bus junction dot)
    if by != JUNCT_Y:
        ax.add_patch(Circle((SPINE_X, by), 0.070, color=clr, zorder=4))

    # Tick mark at mid-branch, coloured to match the field
    tick_mark(ax, TICK_X, by, FIELD_WIDTHS[field], color=clr)

    # Bit-range label just right of the spine, above the wire
    ax.text(SPINE_X + 0.20, by + 0.20, FIELD_SPANS[field],
            ha="left", va="bottom", fontsize=7.5,
            color=clr, style="italic", zorder=5)

    # Endpoint: destination name (bold) + bit value (monospace)
    dest_line1, dest_line2 = FIELD_DEST[field]
    ax.text(BRANCH_END_X + 0.14, by + 0.18, dest_line1,
            ha="left", va="bottom", fontsize=9.5,
            weight="bold", color=clr, zorder=5)
    ax.text(BRANCH_END_X + 0.14, by - 0.08, dest_line2,
            ha="left", va="top", fontsize=8.5,
            family="monospace", color=CLR_TEXT, zorder=5)


# ─────────────────────────────────────────────────────────────────────────── #
#  Instruction reference box (lower-left, below the IM)
# ─────────────────────────────────────────────────────────────────────────── #
ref_box = FancyBboxPatch(
    (0.30, 0.30), 4.65, 3.75,
    boxstyle="round,pad=0.05,rounding_size=0.08",
    linewidth=1.6, edgecolor="#1f6fb2", facecolor="#f5fbff", zorder=5,
)
ax.add_patch(ref_box)

ax.text(2.62, 3.79, f"Instruction:  {INSTR_TEXT}",
        ha="center", va="center", fontsize=11.0,
        weight="bold", color="#124a78", zorder=6)
ax.text(2.62, 3.35, f"Encoding:  {INSTR_HEX}",
        ha="center", va="center", fontsize=9.5,
        family="monospace", color="#124a78", zorder=6)

# One coloured row per field
REF_ROWS = [
    (CLR_OPCODE, f"[31:21]  {OPCODE_BITS}   opcode  (ADD)"),
    (CLR_RM,     f"[20:16]       {RM_BITS}   Rm      (X3) "),
    (CLR_RN,     f"[ 9: 5]       {RN_BITS}   Rn      (X2) "),
    (CLR_RD,     f"[ 4: 0]       {RD_BITS}   Rd      (X1) "),
]
for i, (clr, txt) in enumerate(REF_ROWS):
    ax.text(0.50, 2.80 - i * 0.60, txt,
            ha="left", va="center", fontsize=9.0,
            family="monospace", color=clr, zorder=6)


# ─────────────────────────────────────────────────────────────────────────── #
#  Title and narration text (updated each frame)
# ─────────────────────────────────────────────────────────────────────────── #
title = ax.text(10.8, 10.05, "",
                ha="center", va="center", fontsize=14.5,
                weight="bold", color=CLR_TEXT)

narr = ax.text(10.8, 9.52, "",
               ha="center", va="center", fontsize=9.5,
               style="italic", color="#445a66")


# ─────────────────────────────────────────────────────────────────────────── #
#  Highlight box (outlines the currently active component)
# ─────────────────────────────────────────────────────────────────────────── #
highlight = FancyBboxPatch(
    (0, 0), 0.1, 0.1,
    boxstyle="round,pad=0.05,rounding_size=0.08",
    linewidth=3, edgecolor="#ff5722", facecolor="none", zorder=7, alpha=0.0,
)
ax.add_patch(highlight)


def set_highlight(comp, on=True):
    if comp is None or not on:
        highlight.set_alpha(0.0)
        return
    x, y, w, h = comp
    highlight.set_bounds(x - 0.13, y - 0.13, w + 0.26, h + 0.26)
    highlight.set_alpha(1.0)


# ─────────────────────────────────────────────────────────────────────────── #
#  Animated packets
# ─────────────────────────────────────────────────────────────────────────── #

# Stage 0 — single packet representing the full 32-bit instruction word
main_pkt = Circle(IM_OUT, 0.15, color=CLR_MAIN, zorder=8)
ax.add_patch(main_pkt)
main_pkt.set_visible(False)

main_lbl = ax.text(0, -5, "", ha="center", va="bottom",
                   fontsize=9.0, weight="bold", color=CLR_MAIN, zorder=9)

# Stage 1 — one packet per field, all moving simultaneously
branch_pkts = {}
branch_lbls = {}
for field in FIELD_ORDER:
    clr = FIELD_COLORS[field]
    c = Circle((-5, -5), 0.14, color=clr, zorder=8)
    ax.add_patch(c)
    c.set_visible(False)
    t = ax.text(-5, -5, "", ha="center", va="bottom",
                fontsize=8.5, weight="bold", color=clr, zorder=9)
    t.set_visible(False)
    branch_pkts[field] = c
    branch_lbls[field] = t


# ─────────────────────────────────────────────────────────────────────────── #
#  Stage paths (pre-sampled for smooth animation)
# ─────────────────────────────────────────────────────────────────────────── #
PATH_MAIN = [IM_OUT, (SPINE_X, JUNCT_Y)]

# Each branch packet travels from the junction up/down the spine to its
# branch height, then right along the horizontal branch wire.
BRANCH_PATHS = {
    "opcode": [(SPINE_X, JUNCT_Y),
               (SPINE_X, BRANCH_Y["opcode"]),
               (BRANCH_END_X, BRANCH_Y["opcode"])],
    "Rm":     [(SPINE_X, JUNCT_Y),
               (SPINE_X, BRANCH_Y["Rm"]),
               (BRANCH_END_X, BRANCH_Y["Rm"])],
    "Rn":     [(SPINE_X, JUNCT_Y),
               (BRANCH_END_X, BRANCH_Y["Rn"])],      # straight through
    "Rd":     [(SPINE_X, JUNCT_Y),
               (SPINE_X, BRANCH_Y["Rd"]),
               (BRANCH_END_X, BRANCH_Y["Rd"])],
}

# Stage definitions: (title, narration, which-stage-index)
STAGE_DEFS = [
    (
        "Stage 1 — Instruction Memory Output",
        f"The Instruction Memory outputs the full 32-bit ADD encoding ({INSTR_HEX}) onto the instruction bus.",
    ),
    (
        "Stage 2 — Instruction Decode  (all fields simultaneously)",
        "The 32-bit bus fans out: every field is broadcast in parallel onto its own dedicated bus.",
    ),
    (
        "Stage 2 — Instruction Decode  (all fields simultaneously)",
        "Each bus carries the extracted bits to the Control unit or the appropriate register-file port.",
    ),
]

# ─────────────────────────────────────────────────────────────────────────── #
#  Timing
# ─────────────────────────────────────────────────────────────────────────── #
MOVE_FRAMES      = 30
PAUSE_FRAMES     = 14
FRAMES_PER_STAGE = MOVE_FRAMES + PAUSE_FRAMES
N_STAGES         = len(STAGE_DEFS)
TOTAL_FRAMES     = FRAMES_PER_STAGE * N_STAGES

path_main_pts = polyline_points(PATH_MAIN, MOVE_FRAMES)
branch_pts    = {f: polyline_points(p, MOVE_FRAMES) for f, p in BRANCH_PATHS.items()}


# ─────────────────────────────────────────────────────────────────────────── #
#  Animation update function
# ─────────────────────────────────────────────────────────────────────────── #
def update(frame):
    stage  = min(frame // FRAMES_PER_STAGE, N_STAGES - 1)
    local  = frame % FRAMES_PER_STAGE
    move_i = min(local, MOVE_FRAMES - 1)

    stage_title, stage_narr = STAGE_DEFS[stage]
    title.set_text(stage_title)
    narr.set_text(stage_narr)

    if stage == 0:
        # ── Phase: full instruction travels from IM to the fan-out spine ── #
        set_highlight(IM)
        px, py = path_main_pts[move_i]
        main_pkt.center = (px, py)
        main_pkt.set_visible(True)
        main_lbl.set_position((px, py + 0.23))
        main_lbl.set_text(INSTR_HEX)
        main_lbl.set_visible(True)
        for f in FIELD_ORDER:
            branch_pkts[f].set_visible(False)
            branch_lbls[f].set_visible(False)

    else:
        # ── Phase: four field packets fan out simultaneously ── #
        set_highlight(None)
        main_pkt.set_visible(False)
        main_lbl.set_visible(False)

        if stage == 2:
            # Final hold — freeze all packets at their endpoints
            move_i = MOVE_FRAMES - 1

        for f in FIELD_ORDER:
            pts = branch_pts[f]
            bx, by = pts[move_i]
            branch_pkts[f].center = (bx, by)
            branch_pkts[f].set_visible(True)
            branch_lbls[f].set_position((bx, by + 0.22))
            branch_lbls[f].set_text(FIELD_BITS[f])
            branch_lbls[f].set_visible(True)

    return (
        [main_pkt, main_lbl, highlight, title, narr]
        + list(branch_pkts.values())
        + list(branch_lbls.values())
    )


# ─────────────────────────────────────────────────────────────────────────── #
#  Render
# ─────────────────────────────────────────────────────────────────────────── #
anim = FuncAnimation(fig, update, frames=TOTAL_FRAMES, interval=60, blit=False)

out = "decode_animation.gif"
print(f"Rendering {TOTAL_FRAMES} frames → {out} ...")
anim.save(out, writer=PillowWriter(fps=18))
print("Done:", out)
