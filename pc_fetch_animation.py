"""
Program Counter / Instruction Fetch Animation
==============================================

A focused animation that isolates just the Program Counter (PC) portion of
the single-cycle datapath, so students can see -- in isolation -- how the
PC drives instruction fetch and how it advances from one cycle to the next.

Each cycle shown does the following:
    1. The PC's current address value is sent to the Instruction Memory.
    2. The Instruction Memory reads out the instruction stored at that
       address (shown in a "Fetched instruction" display).
    3. In parallel with the fetch, the PC's value and the constant 4 are
       fed into a dedicated adder.
    4. The adder computes PC + 4, and that result is loaded back into the
       PC register, ready for the next cycle.

The animation repeats for several instructions in a row so you can watch
the PC value climb by 4 every cycle: 0x00 -> 0x04 -> 0x08 -> 0x0C ...

Run:
    python3 pc_fetch_animation.py

Output:
    pc_fetch_animation.gif
"""

import numpy as np
import matplotlib

matplotlib.use("Agg")  # headless rendering
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Polygon, Circle
from matplotlib.animation import FuncAnimation, PillowWriter


# --------------------------------------------------------------------------- #
#  Made-up little "program" -- just enough instructions to show several
#  fetch/increment cycles in a row.
# --------------------------------------------------------------------------- #
INSTR_LIST = [
    "ADD X1, X2, X3",
    "SUB X4, X5, X6",
    "AND X7, X8, X9",
    "ORR X9, X10, X11",
]
ADDRESSES = [i * 4 for i in range(len(INSTR_LIST))]  # 0, 4, 8, 12 ...

# Colours
CLR_WIRE = "#9fb4c4"
CLR_ACTIVE = "#ff5722"
CLR_ACTIVE2 = "#1e88e5"
CLR_BOX = "#eef3f7"
CLR_BOX_EDGE = "#2b3a46"
CLR_ALU = "#dfeee0"
CLR_TEXT = "#1c2833"


# --------------------------------------------------------------------------- #
#  Drawing helpers  (same conventions as datapath_add_animation.py)
# --------------------------------------------------------------------------- #
def box(ax, x, y, w, h, label, face=CLR_BOX, fontsize=10, edge=CLR_BOX_EDGE):
    p = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.06",
        linewidth=1.6, edgecolor=edge, facecolor=face, zorder=3,
    )
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, label, ha="center", va="center",
            fontsize=fontsize, color=CLR_TEXT, zorder=4, weight="bold")
    return (x, y, w, h)


def alu(ax, x, y, w, h, label="ALU"):
    """Classic notched ALU shape pointing right (used here for the +4 adder)."""
    notch = h * 0.16
    verts = [
        (x, y),
        (x + w, y + h * 0.28),
        (x + w, y + h * 0.72),
        (x, y + h),
        (x, y + h * 0.55 + notch / 2),
        (x + w * 0.22, y + h / 2),
        (x, y + h * 0.45 - notch / 2),
    ]
    p = Polygon(verts, closed=True, linewidth=1.6,
                edgecolor=CLR_BOX_EDGE, facecolor=CLR_ALU, zorder=3)
    ax.add_patch(p)
    ax.text(x + w * 0.6, y + h / 2, label, ha="center", va="center",
            fontsize=11, color=CLR_TEXT, weight="bold", zorder=4)
    return (x, y, w, h)


def wire(ax, pts, color=CLR_WIRE, lw=2.2, z=2):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    ax.plot(xs, ys, color=color, lw=lw, solid_capstyle="round",
            solid_joinstyle="round", zorder=z)


def polyline_points(pts, n):
    """Resample a polyline into n evenly spaced points along its length."""
    pts = np.array(pts, dtype=float)
    seg = np.sqrt(((pts[1:] - pts[:-1]) ** 2).sum(axis=1))
    cum = np.concatenate([[0], np.cumsum(seg)])
    total = cum[-1]
    if total == 0:
        return np.repeat(pts[:1], n, axis=0)
    d = np.linspace(0, total, n)
    xs = np.interp(d, cum, pts[:, 0])
    ys = np.interp(d, cum, pts[:, 1])
    return np.column_stack([xs, ys])


# --------------------------------------------------------------------------- #
#  Build the static (PC-only) datapath
# --------------------------------------------------------------------------- #
fig, ax = plt.subplots(figsize=(12.5, 8))
ax.set_xlim(0, 13.2)
ax.set_ylim(0, 9.3)
ax.axis("off")
fig.patch.set_facecolor("white")

# --- component geometry ---------------------------------------------------- #
# The adder sits up and to the right of the PC (not stacked on top of it),
# in the gap between the PC and the Instruction Memory.
PC = box(ax, 0.8, 1.0, 1.7, 1.6, "PC", face="#f3ead7", fontsize=13)
ADDER = alu(ax, 3.2, 4.3, 1.9, 1.9, "Add")
IM = box(ax, 5.0, 1.0, 3.0, 1.9, "Instruction\nMemory", fontsize=12)

# --- key node coordinates -------------------------------------------------- #
pc_out       = (PC[0] + PC[2], PC[1] + PC[3] * 0.5)       # PC -> IM (address)
pc_tap       = (PC[0] + PC[2] * 0.5, PC[1] + PC[3])       # top of PC, feeds adder
adder_in_top = (ADDER[0], ADDER[1] + ADDER[3] * 0.72)     # PC value input
adder_in_bot = (ADDER[0], ADDER[1] + ADDER[3] * 0.28)     # constant "4" input
adder_out    = (ADDER[0] + ADDER[2], ADDER[1] + ADDER[3] * 0.5)
pc_in        = (PC[0], PC[1] + PC[3] * 0.25)              # feedback into PC (register D input)
im_in        = (IM[0], pc_out[1])                         # address in (left side, level with PC out)
im_out       = (IM[0] + IM[2], IM[1] + IM[3] * 0.75)      # instruction out (right side)
const4_pt    = (2.3, adder_in_bot[1])
BUS_EDGE_X   = 13.15                                      # where the instruction bus leaves the frame

# --------------------------------------------------------------------------- #
#  Static wires
# --------------------------------------------------------------------------- #
# PC -> Instruction Memory (address bus)
wire(ax, [pc_out, im_in])
# PC value tapped upward into the +4 adder's top input
wire(ax, [pc_tap, (pc_tap[0], adder_in_top[1]), adder_in_top])
ax.add_patch(Circle(pc_tap, 0.05, color=CLR_WIRE, zorder=3))
# constant 4 into the adder's bottom input
wire(ax, [const4_pt, adder_in_bot])
ax.text(const4_pt[0] - 0.15, const4_pt[1], "4", ha="right", va="center",
        fontsize=12, weight="bold", color=CLR_TEXT)
# adder result wraps up and over the top of the adder, then down the far
# left side and into the PC register (next PC) -- this keeps the feedback
# wire well clear of the Instruction Memory and its output bus.
loop_path = [adder_out, (adder_out[0], ADDER[1] + ADDER[3] + 0.4),
             (0.3, ADDER[1] + ADDER[3] + 0.4), (0.3, pc_in[1]), pc_in]
wire(ax, loop_path)
ax.text(1.55, 0.55, "next PC  (loaded on the clock edge)", ha="center",
        va="center", fontsize=8.5, style="italic", color=CLR_TEXT)

# Instruction Memory's data-out bus: this would normally fan out to the rest
# of the datapath (control, register file, etc.) -- here it just heads off
# the right edge of the frame to represent "the rest of the processor".
wire(ax, [im_out, (BUS_EDGE_X, im_out[1])])
ax.text(BUS_EDGE_X - 0.1, im_out[1] + 0.28, "to rest of the\nprocessor",
        ha="right", va="center", fontsize=8, style="italic", color=CLR_TEXT)

# --------------------------------------------------------------------------- #
#  Dynamic value displays (updated every stage)
# --------------------------------------------------------------------------- #
pc_val_text = ax.text(PC[0] + PC[2] / 2, PC[1] + PC[3] / 2 - 0.42, "",
                      ha="center", va="center", fontsize=11.5,
                      weight="bold", color="#8a3b12", zorder=5)

im_addr_text = ax.text(IM[0] + IM[2] / 2, IM[1] + IM[3] + 0.22, "",
                       ha="center", va="center", fontsize=9,
                       style="italic", color=CLR_TEXT, zorder=5)

# persistent "fetched instruction" display box (like the reference box in
# datapath_add_animation.py) so the last fetched instruction stays visible,
# placed up and to the right, clear of the adder
ref = FancyBboxPatch((5.6, 6.6), 6.6, 1.7,
                     boxstyle="round,pad=0.05,rounding_size=0.08",
                     linewidth=1.6, edgecolor="#1f6fb2",
                     facecolor="#f5fbff", zorder=5)
ax.add_patch(ref)
ax.text(5.8, 7.95, "Fetched instruction:", ha="left", va="center",
        fontsize=10, weight="bold", color="#124a78", zorder=6)
instr_val_text = ax.text(5.8, 7.45, "-", ha="left", va="center",
                         fontsize=13, family="monospace", color=CLR_TEXT,
                         zorder=6)
instr_addr_text = ax.text(5.8, 6.95, "", ha="left", va="center",
                          fontsize=9.5, family="monospace",
                          color="#5a6b78", zorder=6)

title = ax.text(6.6, 9.0, "", ha="center", va="center",
                fontsize=15, weight="bold", color=CLR_TEXT)

# highlight overlay for the currently active component
highlight = FancyBboxPatch((0, 0), 0.1, 0.1,
                           boxstyle="round,pad=0.05,rounding_size=0.08",
                           linewidth=3, edgecolor=CLR_ACTIVE,
                           facecolor="none", zorder=7, alpha=0.0)
ax.add_patch(highlight)


def set_highlight(comp, on=True):
    if comp is None or not on:
        highlight.set_alpha(0.0)
        return
    x, y, w, h = comp
    highlight.set_bounds(x - 0.10, y - 0.10, w + 0.20, h + 0.20)
    highlight.set_alpha(1.0)


# moving packets: one orange (primary value), one blue (second operand,
# used when PC and constant-4 travel into the adder together)
packet = Circle(pc_out, 0.13, color=CLR_ACTIVE, zorder=8)
ax.add_patch(packet)
packet_label = ax.text(0, 0, "", ha="center", va="bottom", fontsize=10,
                       weight="bold", color="#b3300a", zorder=9)

packet2 = Circle((-5, -5), 0.13, color=CLR_ACTIVE2, zorder=8)
ax.add_patch(packet2)
packet2.set_visible(False)
packet2_label = ax.text(0, 0, "", ha="center", va="bottom", fontsize=10,
                        weight="bold", color="#0d47a1", zorder=9)
packet2_label.set_visible(False)

trail = [Circle((-5, -5), 0.075, color=CLR_ACTIVE, alpha=0.0, zorder=6)
         for _ in range(30)]
for c in trail:
    ax.add_patch(c)


def fmt(addr):
    return f"0x{addr:02X}"


# --------------------------------------------------------------------------- #
#  Build the per-cycle stage script
#  each stage: (title, narration, path, label, highlight-comp,
#               path2, label2, pc_display_addr, instr_display_idx)
# --------------------------------------------------------------------------- #
STAGES = []
for c, (addr, instr) in enumerate(zip(ADDRESSES, INSTR_LIST)):
    next_addr = addr + 4
    prev_instr = INSTR_LIST[c - 1] if c > 0 else None
    prev_addr = ADDRESSES[c - 1] if c > 0 else None

    STAGES.append((
        f"Cycle {c + 1} - Fetch",
        f"PC = {fmt(addr)} is sent to the Instruction Memory as the address of the next instruction.",
        [pc_out, im_in], fmt(addr), IM, None, None,
        addr, prev_instr, prev_addr, addr,
    ))
    STAGES.append((
        f"Cycle {c + 1} - Instruction Memory reads out the instruction",
        f"Instruction Memory[{fmt(addr)}] = \"{instr}\" is read out and sent off to the rest of the processor.",
        [im_out, (BUS_EDGE_X + 0.4, im_out[1])], instr, IM,
        None, None,
        addr, instr, addr, addr,
    ))
    STAGES.append((
        f"Cycle {c + 1} - PC and constant 4 enter the adder",
        "At the same time, the current PC value and the constant 4 are fed into a dedicated adder.",
        [pc_tap, (pc_tap[0], adder_in_top[1]), adder_in_top], fmt(addr), ADDER,
        [const4_pt, adder_in_bot], "4",
        addr, instr, addr, addr,
    ))
    STAGES.append((
        f"Cycle {c + 1} - PC <- PC + 4",
        f"The adder computes {fmt(addr)} + 4 = {fmt(next_addr)}, which is loaded into the PC for the next cycle.",
        loop_path, fmt(next_addr), PC, None, None,
        next_addr, instr, addr, addr,
    ))

# Frames per stage (movement) + a short pause between stages
MOVE_FRAMES = 22
PAUSE_FRAMES = 8
FRAMES_PER_STAGE = MOVE_FRAMES + PAUSE_FRAMES
TOTAL_FRAMES = FRAMES_PER_STAGE * len(STAGES)

# pre-resample each stage path
stage_paths = [polyline_points(s[2], MOVE_FRAMES) for s in STAGES]
stage_paths2 = [polyline_points(s[5], MOVE_FRAMES) if s[5] else None for s in STAGES]


def update(frame):
    stage_idx = min(frame // FRAMES_PER_STAGE, len(STAGES) - 1)
    local = frame % FRAMES_PER_STAGE

    (st_title, _st_narr, _pts, mlabel, comp, _p2, mlabel2,
     pc_addr, instr_disp, instr_addr, bus_addr) = STAGES[stage_idx]
    path = stage_paths[stage_idx]

    title.set_text(st_title)
    set_highlight(comp, True)

    pc_val_text.set_text(fmt(pc_addr))
    im_addr_text.set_text(f"address in = {fmt(bus_addr)}")
    if instr_disp is not None:
        instr_val_text.set_text(instr_disp)
        instr_addr_text.set_text(f"fetched from {fmt(instr_addr)}")
    else:
        instr_val_text.set_text("-")
        instr_addr_text.set_text("")

    move_i = min(local, MOVE_FRAMES - 1)
    px, py = path[move_i]
    packet.center = (px, py)
    packet_label.set_position((px, py + 0.22))
    packet_label.set_text(mlabel)

    path2 = stage_paths2[stage_idx]
    if path2 is not None:
        qx, qy = path2[move_i]
        packet2.center = (qx, qy)
        packet2.set_visible(True)
        packet2_label.set_position((qx, qy + 0.22))
        packet2_label.set_text(mlabel2)
        packet2_label.set_visible(True)
    else:
        packet2.set_visible(False)
        packet2_label.set_visible(False)

    for j, c in enumerate(trail):
        if j <= move_i:
            c.center = (path[j][0], path[j][1])
            c.set_alpha(max(0.0, 0.5 - 0.02 * (move_i - j)))
        else:
            c.set_alpha(0.0)

    return [packet, packet_label, packet2, packet2_label,
            title, highlight, pc_val_text, im_addr_text,
            instr_val_text, instr_addr_text, *trail]


anim = FuncAnimation(fig, update, frames=TOTAL_FRAMES, interval=60, blit=False)

out = "pc_fetch_animation.gif"
print(f"Rendering {TOTAL_FRAMES} frames -> {out} ...")
anim.save(out, writer=PillowWriter(fps=18))
print("Done:", out)
