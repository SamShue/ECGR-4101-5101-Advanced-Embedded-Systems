"""
Single-Cycle ARM (LEGv8-style) Datapath Animation
==================================================

Generates an animated GIF that walks students through how an LDUR (load)
instruction flows through the same simple single-cycle datapath:

    LDUR X1, [X2, #8]      ; X1 <- Mem[X2 + 8]

Stages animated:
    1. PC drives the Instruction Memory (fetch).
    2. The 32-bit instruction is read out.
    3. The instruction is broken apart:
         - opcode bits [31-21]      -> Control unit  (shown as "LDUR")
         - Rn [9-5]                 -> register-file read port 1 (base)
         - immediate                -> sign-extend unit
         - Rt [4-0]                 -> register-file write port
    4. Base register and sign-extended offset are sent to the ALU.
    5. The ALU computes the effective address.
    6. Data memory is read at that address.
    7. The loaded value loops back (through the WB mux) into Rt.

The full instruction and its field breakdown stay on screen the whole time.

Run:
    python3 datapath_load_animation.py

Output:
    datapath_load_animation.gif
"""

import numpy as np
import matplotlib

matplotlib.use("Agg")  # headless rendering
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Ellipse, Polygon, Circle
from matplotlib.animation import FuncAnimation, PillowWriter


# --------------------------------------------------------------------------- #
#  Example instruction + made-up register/memory contents
# --------------------------------------------------------------------------- #
OPCODE = "LDUR"
INSTR_TEXT = "LDUR X1, [X2, #8]"
RN_VAL = 1000        # contents of X2 (base register)
RM_VAL = 8           # sign-extended immediate offset
ADDR = RN_VAL + RM_VAL
RESULT = 73          # memory value loaded from address ADDR

# Colours
CLR_WIRE = "#9fb4c4"
CLR_ACTIVE = "#ff5722"
CLR_BOX = "#eef3f7"
CLR_BOX_EDGE = "#2b3a46"
CLR_CTRL = "#d7ecff"
CLR_ALU = "#dfeee0"
CLR_TEXT = "#1c2833"


# --------------------------------------------------------------------------- #
#  Drawing helpers
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


def mux(ax, x, y, w, h, label=""):
    """A vertical 2:1 mux: wide input side (left, 2 inputs), narrow output side (right)."""
    taper = h * 0.16
    verts = [
        (x, y),
        (x + w, y + taper),
        (x + w, y + h - taper),
        (x, y + h),
    ]
    p = Polygon(verts, closed=True, linewidth=1.4,
                edgecolor=CLR_BOX_EDGE, facecolor="#e8eef3", zorder=3)
    ax.add_patch(p)
    if label:
        ax.text(x + w / 2, y + h / 2, label, ha="center", va="center",
                fontsize=7, color=CLR_TEXT, rotation=90, zorder=4)
    return (x, y, w, h)


def alu(ax, x, y, w, h, label="ALU"):
    """Classic notched ALU shape pointing right."""
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


def control(ax, x, y, w, h):
    e = Ellipse((x + w / 2, y + h / 2), w, h, linewidth=1.6,
                edgecolor="#1f6fb2", facecolor=CLR_CTRL, zorder=3)
    ax.add_patch(e)
    ax.text(x + w / 2, y + h / 2, "Control", ha="center", va="center",
            fontsize=11, color="#124a78", weight="bold", zorder=4)
    return (x, y, w, h)


def and_gate(ax, x, y, w, h):
    """A logic AND gate: flat left side, semicircular right side, pointing right."""
    r = h / 2.0
    cy = y + r
    th = np.linspace(-np.pi / 2, np.pi / 2, 24)
    arc = [(x + (w - r) + r * np.cos(t), cy + r * np.sin(t)) for t in th]
    verts = [(x, y), (x + w - r, y)] + arc + [(x + w - r, y + h), (x, y + h)]
    p = Polygon(verts, closed=True, linewidth=1.4,
                edgecolor=CLR_BOX_EDGE, facecolor="#e8eef3", zorder=3)
    ax.add_patch(p)
    ax.text(x + (w - r) * 0.5, cy, "AND", ha="center", va="center",
            fontsize=6.5, color=CLR_TEXT, zorder=4)
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
#  Build the static datapath   (roomy layout, xlim 0..18.5, ylim 0..10)
# --------------------------------------------------------------------------- #
fig, ax = plt.subplots(figsize=(16, 10.7))
ax.set_xlim(0, 18.5)
ax.set_ylim(0, 12.4)
ax.axis("off")
fig.patch.set_facecolor("white")

# --- component geometry ---------------------------------------------------- #
PC = box(ax, 0.4, 4.7, 0.9, 1.0, "PC", face="#f3ead7")
IM = box(ax, 1.9, 4.0, 2.3, 2.2, "Instruction\nMemory", fontsize=10)
CTRL = control(ax, 7.5, 7.9, 2.2, 1.1)
REGMUX = mux(ax, 6.3, 4.5, 0.35, 1.3, "M\nu\nx")        # Reg2Loc mux
REGS = box(ax, 7.0, 3.4, 2.7, 3.1, "", fontsize=11)
ALUMUX = mux(ax, 10.5, 3.35, 0.4, 1.6, "M\nu\nx")       # ALUSrc mux
ALU = alu(ax, 11.6, 3.7, 1.9, 2.6, "ALU")
DMEM = box(ax, 14.4, 3.8, 2.0, 2.0, "Data\nMemory", fontsize=10)
WBMUX = mux(ax, 16.9, 4.3, 0.4, 1.4, "M\nu\nx")         # MemToReg mux
SEXT = box(ax, 6.8, 1.4, 1.7, 1.0, "Sign-\nextend", fontsize=9, face="#f0e6f5")

# "Registers" title sits at the top edge of the register file so it does not
# collide with the internal port labels.
ax.text(REGS[0] + REGS[2] / 2, REGS[1] + REGS[3] - 0.25, "Registers",
        ha="center", va="center", fontsize=11, weight="bold", color=CLR_TEXT, zorder=4)

# register-file port labels (well separated)
ax.text(REGS[0] + 0.12, 6.10, "Read\nreg 1", ha="left", va="center", fontsize=7.5, color=CLR_TEXT)
ax.text(REGS[0] + 0.12, 5.10, "Read\nreg 2", ha="left", va="center", fontsize=7.5, color=CLR_TEXT)
ax.text(REGS[0] + 0.12, 4.20, "Write\nreg",  ha="left", va="center", fontsize=7.5, color=CLR_TEXT)
ax.text(REGS[0] + 0.12, 3.70, "Write\ndata", ha="left", va="center", fontsize=7.5, color=CLR_TEXT)
ax.text(REGS[0] + REGS[2] - 0.12, 5.90, "Read\ndata 1", ha="right", va="center", fontsize=7.5, color=CLR_TEXT)
ax.text(REGS[0] + REGS[2] - 0.12, 4.40, "Read\ndata 2", ha="right", va="center", fontsize=7.5, color=CLR_TEXT)

# --- key node coordinates -------------------------------------------------- #
pc_out   = (PC[0] + PC[2], 5.2)
im_in    = (IM[0], 5.2)
im_out   = (IM[0] + IM[2], 5.0)
split_x  = 5.2                       # instruction fan-out spine

ctrl_in  = (7.6, 8.2)
rr1_in   = (REGS[0], 6.10)
rr2_in   = (REGS[0], 5.10)
wr_in    = (REGS[0], 4.20)
wd_in    = (REGS[0], 3.70)

rd1_out  = (REGS[0] + REGS[2], 5.90)
rd2_out  = (REGS[0] + REGS[2], 4.40)

alumux_out = (ALUMUX[0] + ALUMUX[2], 4.15)
alu_in_top = (ALU[0], 5.85)
alu_in_bot = (ALU[0], 4.15)
alu_out    = (ALU[0] + ALU[2], 5.00)
wb_out     = (WBMUX[0] + WBMUX[2], 5.00)

# --------------------------------------------------------------------------- #
#  Static wires
# --------------------------------------------------------------------------- #
wire(ax, [pc_out, im_in])
wire(ax, [im_out, (split_x, 5.0)])
# fan-out spine
wire(ax, [(split_x, 1.9), (split_x, 8.2)])
# opcode -> control
wire(ax, [(split_x, 8.2), ctrl_in])
# Rn -> read reg 1
wire(ax, [(split_x, 6.10), rr1_in])
# Rm [20-16] -> Reg2Loc mux (top input, straight)
wire(ax, [(split_x, 5.10), (REGMUX[0], 5.10)])
# Rd [4-0] -> write reg  (and branch up into Reg2Loc mux bottom input)
wire(ax, [(split_x, 4.20), wr_in])
wire(ax, [(5.9, 4.20), (5.9, 4.80), (REGMUX[0], 4.80)])
# Reg2Loc mux output -> read reg 2 port
wire(ax, [(REGMUX[0] + REGMUX[2], 5.10), rr2_in])
# imm [31-0] -> sign extend
wire(ax, [(split_x, 1.9), (SEXT[0], 1.9)])

# read data 1 -> ALU top input
wire(ax, [rd1_out, (11.4, 5.90), alu_in_top])
# read data 2 -> ALUSrc mux top input (straight)
wire(ax, [rd2_out, (ALUMUX[0], 4.40)])
# sign-extend -> ALUSrc mux bottom input
wire(ax, [(SEXT[0] + SEXT[2], 1.9), (10.3, 1.9), (10.3, 3.70), (ALUMUX[0], 3.70)])
# ALUSrc mux output -> ALU bottom input
wire(ax, [alumux_out, alu_in_bot])
# ALU -> data memory (address)
wire(ax, [alu_out, (DMEM[0], 5.00)])
# ALU result -> WB mux (bottom input), routed under data memory
wire(ax, [(13.6, 5.00), (13.6, 3.4), (16.7, 3.4), (16.7, 4.65), (WBMUX[0], 4.65)])
# data memory read data -> WB mux (top input)
wire(ax, [(DMEM[0] + DMEM[2], 5.35), (WBMUX[0], 5.35)])
# WB mux -> write-back loop -> write data port
wire(ax, [wb_out, (17.9, 5.00), (17.9, 0.6), (5.6, 0.6), (5.6, 3.70), wd_in])

# --------------------------------------------------------------------------- #
#  PC increment hardware  (PC + 4)  -- included for completeness; an ADD does
#  not use it, but every instruction still advances the program counter.
# --------------------------------------------------------------------------- #
PCADD = alu(ax, 2.3, 7.2, 1.3, 1.6, "Add")
# PC value feeds the adder (tapped off the PC -> Instruction Memory wire)
wire(ax, [(1.6, 5.2), (1.6, 8.50), (2.3, 8.50)])
ax.add_patch(Circle((1.6, 5.2), 0.055, color=CLR_WIRE, zorder=3))
# constant 4 feeds the adder's lower input
wire(ax, [(1.9, 7.50), (2.3, 7.50)])
ax.text(1.78, 7.50, "4", ha="right", va="center", fontsize=10,
        weight="bold", color=CLR_TEXT)
# PC + 4 result rises to the distribution bus (above the control lines)
wire(ax, [(3.6, 8.00), (3.6, 11.10)])
ax.text(3.75, 8.55, "PC + 4", ha="left", va="center", fontsize=8,
        style="italic", color=CLR_TEXT)

# --------------------------------------------------------------------------- #
#  Branch-target hardware  (unused by an ADD, shown for completeness).
#  Placed ABOVE the control unit / control lines so it stays clear of them:
#     branch target = (PC + 4) + (SignExtend(imm) << 2)
#     PCSrc mux selects  PC+4  vs  branch target,  enabled by (Branch AND Zero).
# --------------------------------------------------------------------------- #
SL2   = box(ax, 10.50, 9.55, 1.35, 0.58, "Shift\nleft 2", fontsize=7.5, face="#f0e6f5")
BADD  = alu(ax, 12.25, 9.45, 1.25, 1.40, "Add")
ANDG  = and_gate(ax, 14.00, 9.30, 0.78, 0.50)
PCMUX = mux(ax, 15.40, 9.90, 0.42, 1.45, "M\nu\nx")

# sign-extended immediate -> Shift left 2  (rising between the registers and ALU)
wire(ax, [(8.5, 1.9), (8.5, 1.15), (11.20, 1.15), (11.20, 9.55)])
ax.add_patch(Circle((8.5, 1.9), 0.055, color=CLR_WIRE, zorder=3))
# Shift left 2 -> branch adder (lower input)
wire(ax, [(SL2[0] + SL2[2], 9.84), (12.05, 9.84), (12.05, 9.71), (BADD[0], 9.71)])
# PC + 4 distribution bus feeds the branch adder and the PCSrc mux
wire(ax, [(3.60, 11.10), (15.10, 11.10)])
wire(ax, [(12.15, 11.10), (12.15, 10.59), (BADD[0], 10.59)])        # -> branch adder upper input
wire(ax, [(15.10, 11.10), (15.10, 11.00), (PCMUX[0], 11.00)])       # -> PCSrc mux input 0
# branch adder result -> PCSrc mux input 1
wire(ax, [(BADD[0] + BADD[2], 10.20), (14.90, 10.20), (14.90, 10.15), (PCMUX[0], 10.15)])
# ALU Zero flag -> AND gate (lower input)
ax.text(ALU[0] + ALU[2] - 0.15, 5.50, "Zero", ha="right", va="center",
        fontsize=8, style="italic", color=CLR_TEXT)
wire(ax, [(ALU[0] + ALU[2], 5.55), (13.60, 5.55), (13.60, 9.43), (ANDG[0], 9.43)])
# AND gate output -> PCSrc mux select (the control line that picks the next PC)
wire(ax, [(ANDG[0] + ANDG[2], 9.55), (15.61, 9.55), (15.61, 9.90)])
ax.text(15.50, 9.73, "PCSrc", ha="right", va="center", fontsize=7,
        style="italic", color=CLR_TEXT)
# PCSrc mux output -> back to the PC (next instruction address)
wire(ax, [(PCMUX[0] + PCMUX[2], 10.625), (16.30, 10.625), (16.30, 11.70),
          (0.85, 11.70), (0.85, 5.70)])
ax.text(4.0, 11.92, "next-PC path", ha="center", va="center",
        fontsize=8.5, style="italic", color=CLR_TEXT)

# --- static field labels (short; full breakdown is in the reference box) ---- #
def lab(x, y, t, c="#1f6fb2", fs=7.5, style="italic"):
    ax.text(x, y, t, fontsize=fs, color=c, style=style, zorder=5)

lab(5.35, 8.38, "Instr [31-21]")
lab(5.35, 6.28, "Instr [9-5]")
lab(5.35, 5.28, "Instr [20-16]")
lab(5.35, 4.38, "Instr [4-0]")
lab(5.35, 2.05, "Instr [31-0]")
ax.text(IM[0] + IM[2] + 0.08, 4.55, "Instruction\n[31-0]", fontsize=7,
        color=CLR_TEXT, style="italic")

# --------------------------------------------------------------------------- #
#  Control-unit signal wires  (light gray; turn light blue when active)
# --------------------------------------------------------------------------- #
CTRL_GRAY = "#c3ccd3"
CTRL_GRAY_TXT = "#8593a0"
CTRL_BLUE = "#3f9ae0"
CTRL_BLUE_TXT = "#1f6fb2"

# (name, route [control -> device], (label_x, label_y, ha), active-stage indices)
CTRL_DEFS = [
    ("Reg2Loc",  [(7.60, 8.10), (6.475, 8.10), (6.475, 5.80)], (6.30, 7.55, "right"), set()),
    ("RegWrite", [(8.35, 7.95), (8.35, 6.50)],                 (8.18, 7.20, "right"), {7}),
    ("ALUSrc",   [(9.50, 8.30), (10.70, 8.30), (10.70, 4.95)], (10.82, 6.85, "left"), {4}),
    ("ALUOp",    [(9.55, 8.50), (12.55, 8.50), (12.55, 6.30)], (12.40, 7.30, "right"), {4}),
    ("MemRead",  [(9.60, 8.68), (14.60, 8.68), (14.60, 5.80)], (14.70, 7.45, "left"), {5, 6}),
    ("MemWrite", [(9.62, 8.84), (16.20, 8.84), (16.20, 5.80)],  (16.05, 8.05, "right"), set()),
    ("MemToReg", [(9.64, 9.00), (17.10, 9.00), (17.10, 5.70)], (16.98, 6.60, "right"), {6, 7}),
    ("Branch",   [(9.66, 9.12), (9.66, 10.95), (13.75, 10.95), (13.75, 9.67), (14.00, 9.67)], (13.55, 10.62, "right"), set()),
]

control_objs = []
for _name, _pts, (_lx, _ly, _ha), _active in CTRL_DEFS:
    _xs = [p[0] for p in _pts]
    _ys = [p[1] for p in _pts]
    _ln, = ax.plot(_xs, _ys, color=CTRL_GRAY, lw=1.5, linestyle=(0, (5, 3)),
                   zorder=1.4, solid_capstyle="round")
    _tx = ax.text(_lx, _ly, _name, fontsize=7.5, color=CTRL_GRAY_TXT,
                  style="italic", ha=_ha, va="center", zorder=6)
    _dot = Circle(_pts[-1], 0.055, color=CTRL_GRAY, zorder=1.6)
    ax.add_patch(_dot)
    control_objs.append((_ln, _tx, _dot, _active))

# --------------------------------------------------------------------------- #
#  Persistent instruction reference box (stays on screen the whole time)
# --------------------------------------------------------------------------- #
ref = FancyBboxPatch((0.35, 0.9), 4.15, 2.55,
                     boxstyle="round,pad=0.05,rounding_size=0.08",
                     linewidth=1.6, edgecolor="#1f6fb2",
                     facecolor="#f5fbff", zorder=5)
ax.add_patch(ref)
ax.text(2.42, 3.18, f"Instruction:  {INSTR_TEXT}", ha="center", va="center",
        fontsize=11, weight="bold", color="#124a78", zorder=6)
ref_lines = [
    f"opcode [31-21]        =  {OPCODE}",
    f"Rn  [9-5]   = X2   -> base {RN_VAL}",
    f"imm offset  = #{RM_VAL} -> sign-extend",
    f"Rt  [4-0]   = X1   <- writes {RESULT}",
    f"Address:    X2 + #{RM_VAL} = {ADDR}",
    f"Operation:  X1 = Mem[{ADDR}] = {RESULT}",
]
for i, line in enumerate(ref_lines):
    ax.text(0.55, 2.72 - i * 0.36, line, ha="left", va="center",
            fontsize=9.5, family="monospace", color=CLR_TEXT, zorder=6)

# title + narration
title = ax.text(11.0, 12.05, "", ha="center", va="center",
                fontsize=15, weight="bold", color=CLR_TEXT)
narr = ax.text(9.25, 0.25, "", ha="center", va="center",
               fontsize=11.5, color="#8a3b12", weight="bold")

# moving packet (a glowing marker) + trailing label
packet = Circle((pc_out[0], pc_out[1]), 0.14, color=CLR_ACTIVE, zorder=8)
ax.add_patch(packet)
packet_label = ax.text(0, 0, "", ha="center", va="bottom", fontsize=10,
                       weight="bold", color="#b3300a", zorder=9)

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


# --------------------------------------------------------------------------- #
#  Write-back path (also used for its animation stage)
# --------------------------------------------------------------------------- #
writeback_path = [wb_out, (17.9, 5.00), (17.9, 0.6), (5.6, 0.6), (5.6, 3.70), wd_in]

# --------------------------------------------------------------------------- #
#  Animation stage script
#  each stage: (title, narration, path, moving-label, highlight-comp,
#              optional second-path, optional second-label)
# --------------------------------------------------------------------------- #
STAGES = [
    ("1. Fetch",
     f"PC selects the address; the instruction '{INSTR_TEXT}' is fetched from memory.",
     [pc_out, im_in], "PC", IM, None, None),

    ("2. Read Instruction",
     "The 32-bit instruction word is read out of Instruction Memory.",
     [im_out, (split_x, 5.0)], INSTR_TEXT, IM, None, None),

    ("3a. Decode - opcode -> Control",
        "Bits [31-21] decode to opcode LDUR and set the datapath control signals.",
     [(split_x, 5.0), (split_x, 8.2), ctrl_in], OPCODE, CTRL, None, None),

    ("3b. Decode - base register + immediate",
     "Rn = X2 indexes Read reg 1, while the offset field is sent down to Sign-extend.",
     [(split_x, 5.0), (split_x, 6.10), rr1_in], "Rn=X2", REGS,
     [(split_x, 5.0), (split_x, 1.9), (SEXT[0], 1.9)], "imm=#8"),

    ("3c. Decode - destination register",
     "Rt = X1 is routed to the register file's Write-register port.",
     [(split_x, 5.0), (split_x, 4.20), wr_in], "Rt=X1", REGS, None, None),

    ("4. Address Inputs",
     f"Base register X2 = {RN_VAL} and sign-extended offset #{RM_VAL} are selected as ALU inputs.",
     [(SEXT[0] + SEXT[2], 1.9), (10.3, 1.9), (10.3, 3.70), (ALUMUX[0], 3.70), alumux_out, alu_in_bot],
     f"offset = {RM_VAL}", REGS,
     [rd1_out, (11.4, 5.90), alu_in_top], f"base = {RN_VAL}"),

    ("5. Effective Address",
     f"The ALU computes address = base + offset = {RN_VAL} + {RM_VAL} = {ADDR} and sends it to Data Memory.",
     [alu_out, (DMEM[0], 5.00)], f"addr = {ADDR}", ALU, None, None),

    ("6. Memory Read",
     f"MemRead is asserted; Data Memory returns Mem[{ADDR}] = {RESULT} to the write-back mux.",
     [(DMEM[0] + DMEM[2], 5.35), (WBMUX[0], 5.35)],
     f"Mem[{ADDR}] = {RESULT}", DMEM, None, None),

    ("7. Write Back",
        f"MemToReg selects memory data and RegWrite is asserted; {RESULT} is written into X1.",
     writeback_path, f"{RESULT} -> X1", REGS, None, None),
]

# Frames per stage (movement) + a short pause between stages
MOVE_FRAMES = 26
PAUSE_FRAMES = 8
FRAMES_PER_STAGE = MOVE_FRAMES + PAUSE_FRAMES
TOTAL_FRAMES = FRAMES_PER_STAGE * len(STAGES)

# pre-resample each stage path
stage_paths = [polyline_points(s[2], MOVE_FRAMES) for s in STAGES]
stage_paths2 = [polyline_points(s[5], MOVE_FRAMES) if s[5] else None for s in STAGES]

# trail markers (fading dots left behind along the active path)
trail = [Circle((-5, -5), 0.08, color=CLR_ACTIVE, alpha=0.0, zorder=6)
         for _ in range(MOVE_FRAMES)]
for c in trail:
    ax.add_patch(c)

# second packet (blue) - used when two operands travel at once (register read)
packet2 = Circle((-5, -5), 0.14, color="#1e88e5", zorder=8)
ax.add_patch(packet2)
packet2.set_visible(False)
packet2_label = ax.text(0, 0, "", ha="center", va="bottom", fontsize=10,
                        weight="bold", color="#0d47a1", zorder=9)
packet2_label.set_visible(False)


def update(frame):
    stage_idx = min(frame // FRAMES_PER_STAGE, len(STAGES) - 1)
    local = frame % FRAMES_PER_STAGE

    st_title, st_narr, _pts, mlabel, comp, _p2, mlabel2 = STAGES[stage_idx]
    path = stage_paths[stage_idx]

    title.set_text(st_title)
    narr.set_text(st_narr)
    set_highlight(comp, True)

    # light up the control signals that are actively driving a device this stage
    for ln, tx, dot, active in control_objs:
        if stage_idx in active:
            ln.set_color(CTRL_BLUE)
            ln.set_linewidth(2.6)
            ln.set_linestyle("solid")
            tx.set_color(CTRL_BLUE_TXT)
            dot.set_color(CTRL_BLUE)
        else:
            ln.set_color(CTRL_GRAY)
            ln.set_linewidth(1.5)
            ln.set_linestyle((0, (5, 3)))
            tx.set_color(CTRL_GRAY_TXT)
            dot.set_color(CTRL_GRAY)

    move_i = min(local, MOVE_FRAMES - 1)
    px, py = path[move_i]
    packet.center = (px, py)
    packet_label.set_position((px, py + 0.24))
    packet_label.set_text(mlabel)

    # optional simultaneous second operand (register read)
    path2 = stage_paths2[stage_idx]
    if path2 is not None:
        qx, qy = path2[move_i]
        packet2.center = (qx, qy)
        packet2.set_visible(True)
        packet2_label.set_position((qx, qy + 0.24))
        packet2_label.set_text(mlabel2)
        packet2_label.set_visible(True)
    else:
        packet2.set_visible(False)
        packet2_label.set_visible(False)

    # fading trail behind the packet
    for j, c in enumerate(trail):
        if j <= move_i:
            c.center = (path[j][0], path[j][1])
            c.set_alpha(max(0.0, 0.5 - 0.02 * (move_i - j)))
        else:
            c.set_alpha(0.0)

    return [packet, packet_label, packet2, packet2_label,
            title, narr, highlight, *trail]


anim = FuncAnimation(fig, update, frames=TOTAL_FRAMES, interval=60, blit=False)

out = "datapath_load_animation.gif"
print(f"Rendering {TOTAL_FRAMES} frames -> {out} ...")
anim.save(out, writer=PillowWriter(fps=18))
print("Done:", out)
