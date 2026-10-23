#!/usr/bin/env python3
"""
Generate the signal waveform of one or more back-to-back UART frames and
plot TX as an image.

Frame format (LSB-first):
  IDLE | START | D0 | D1 | ... | D(n-1) | [PARITY] | STOP... | IDLE
"""

import matplotlib.pyplot as plt

# ================== CONFIG ==================
DATA_BYTES       = [0xF0, 0x3A]  # Bytes to transmit (one frame each)
DATA_BITS        = 8             # Number of data bits (5–9)
PARITY           = 'odd'         # 'even', 'odd', or 'none'
STOP_BITS        = 1             # Number of stop bits (1 or 2)
IDLE_BITS        = 4             # Idle bits before first and after last frame
INTER_FRAME_BITS = 0             # Idle bits between consecutive frames
SHOW_BIT_LABELS  = False          # Annotate each bit with its label on the plot
# ============================================

# Waveform resolution: each bit period = this many plot samples
SAMPLES_PER_BIT = 4


# ---------------------------------------------------------------------------
# Waveform builder
# ---------------------------------------------------------------------------

class WaveformBuilder:
    """Accumulates TX sample values and annotations."""

    def __init__(self, samples_per_bit: int = 4):
        self.tx: list[float] = []
        self.spb = samples_per_bit
        # (sample_index, label, color)
        self.annotations: list[tuple[int, str, str]] = []
        # (start_sample, end_sample) for each complete frame
        self.frame_regions: list[tuple[int, int]] = []

    def _append(self, val: float, n: int = 1):
        self.tx.extend([val] * n)

    def idle(self, n_bits: int = 1):
        """Idle line — TX high."""
        for _ in range(n_bits):
            self._append(1.0, self.spb)

    def start(self):
        """Start bit — TX low."""
        idx = len(self.tx)
        self._append(0.0, self.spb)
        self.annotations.append((idx, "START", "green"))

    def data_bit(self, bit: int, index: int):
        """One data bit with an annotation showing its position."""
        idx = len(self.tx)
        self._append(float(bit), self.spb)
        self.annotations.append((idx, f"D{index}={bit}", "navy"))

    def parity_bit(self, bit: int, parity_type: str):
        """Parity bit."""
        idx = len(self.tx)
        self._append(float(bit), self.spb)
        label = f"PAR={'1' if bit else '0'} ({parity_type[0].upper()})"
        self.annotations.append((idx, label, "purple"))

    def stop(self, count: int = 1):
        """Stop bit(s) — TX high."""
        for i in range(count):
            idx = len(self.tx)
            self._append(1.0, self.spb)
            label = "STOP" if count == 1 else f"STOP{i+1}"
            self.annotations.append((idx, label, "red"))


# ---------------------------------------------------------------------------
# Parity calculation
# ---------------------------------------------------------------------------

def calc_parity(value: int, n_bits: int, parity_type: str) -> int:
    """Return the parity bit value for the given data."""
    ones = bin(value & ((1 << n_bits) - 1)).count('1')
    if parity_type == 'even':
        return 0 if ones % 2 == 0 else 1   # make total ones even
    elif parity_type == 'odd':
        return 1 if ones % 2 == 0 else 0   # make total ones odd
    return 0  # shouldn't be called for 'none'


# ---------------------------------------------------------------------------
# Frame builder
# ---------------------------------------------------------------------------

def _append_frame(wb: WaveformBuilder, data_byte: int, data_bits: int,
                  parity: str, stop_bits: int):
    """Append one UART frame to an existing WaveformBuilder."""
    frame_start = len(wb.tx)

    wb.start()

    # Data bits, LSB first
    mask = (1 << data_bits) - 1
    value = data_byte & mask
    for i in range(data_bits):
        bit = (value >> i) & 1
        wb.data_bit(bit, i)

    # Optional parity bit
    p = parity.strip().lower()
    if p in ('even', 'odd'):
        pbit = calc_parity(value, data_bits, p)
        wb.parity_bit(pbit, p)

    # Stop bit(s)
    wb.stop(stop_bits)

    frame_end = len(wb.tx)
    wb.frame_regions.append((frame_start, frame_end))


def build_uart_frames(data_bytes: list[int], data_bits: int, parity: str,
                      stop_bits: int, idle_bits: int,
                      inter_frame_bits: int) -> WaveformBuilder:
    """
    Build one or more back-to-back UART frames.

    Layout: IDLE(idle_bits) | FRAME | IDLE(inter) | FRAME | ... | IDLE(idle_bits)
    """
    wb = WaveformBuilder(SAMPLES_PER_BIT)

    wb.idle(idle_bits)
    for i, byte in enumerate(data_bytes):
        if i > 0:
            wb.idle(inter_frame_bits)
        _append_frame(wb, byte, data_bits, parity, stop_bits)
    wb.idle(idle_bits)

    return wb


# ---------------------------------------------------------------------------
# Text description
# ---------------------------------------------------------------------------

def describe_frames(data_bytes: list[int], data_bits: int, parity: str, stop_bits: int):
    p = parity.strip().lower()
    mask = (1 << data_bits) - 1

    print("=== UART Transmission ===")
    print(f"  Frames     : {len(data_bytes)}")
    print(f"  Data bits  : {data_bits}")
    print(f"  Parity     : {p}")
    print(f"  Stop bits  : {stop_bits}")
    print()

    for idx, data_byte in enumerate(data_bytes):
        value = data_byte & mask
        print(f"  --- Frame {idx} --- 0x{value:02X} ({value})")
        bits_str = " | ".join(str((value >> i) & 1) for i in range(data_bits))
        if p in ('even', 'odd'):
            pbit = calc_parity(value, data_bits, p)
            ones = bin(value).count('1')
            bits_str += f" | {pbit}(P)"
            print(f"  binary={value:0{data_bits}b}  {ones} one(s) → parity bit = {pbit}")
        else:
            print(f"  binary={value:0{data_bits}b}")
        if stop_bits == 1:
            stop_str = "STOP(1)"
        else:
            stop_str = " | ".join(f"STOP{i+1}(1)" for i in range(stop_bits))
        print(f"  START(0) | {bits_str} | {stop_str}")
        print()


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def plot_uart_waveform(wb: WaveformBuilder, data_bytes: list[int], data_bits: int,
                       parity: str, stop_bits: int,
                       filename: str = "uart_waveform.png",
                       show_bit_labels: bool = True):
    """Plot the TX waveform with bit annotations and per-frame shading."""
    n = len(wb.tx)
    t = list(range(n + 1))
    tx_step = wb.tx + [wb.tx[-1]]

    p = parity.strip().lower()
    parity_label = p.capitalize() if p != 'none' else 'No'
    n_frames = len(data_bytes)
    config_str = (f"{n_frames} frame{'s' if n_frames > 1 else ''}  |  "
                  f"{data_bits} data bits  |  {parity_label} parity  |  "
                  f"{stop_bits} stop bit{'s' if stop_bits > 1 else ''}")

    fig, ax = plt.subplots(figsize=(max(14, n // 8), 4))

    ax.step(t, tx_step, where="post", color="steelblue", linewidth=2, label="TX")
    ax.set_ylim(-0.5, 1.8)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["LOW (0)", "HIGH (1)"])
    ax.set_ylabel("TX")
    ax.set_xlabel("Time (bit periods)")
    if show_bit_labels:
        ax.set_title(f"UART Waveform  —  {config_str}")
    ax.grid(False)

    # Shade each frame region, alternating colors
    shade_colors = ["steelblue", "darkorange"]
    mask = (1 << data_bits) - 1
    for fi, (fs, fe) in enumerate(wb.frame_regions):
        if show_bit_labels:
            ax.axvspan(fs, fe, alpha=0.08, color=shade_colors[fi % 2])
            mid_x = (fs + fe) / 2
            value = data_bytes[fi] & mask
            ax.text(mid_x, 1.72, f"Frame {fi}: 0x{value:02X}",
                    ha="center", va="top", fontsize=8,
                    color=shade_colors[fi % 2], fontweight="bold")

    # Vertical lines and (optionally) bit labels
    spb = wb.spb
    for s, label, color in wb.annotations:
        ax.axvline(x=s, color="lightgray", linestyle="--", linewidth=0.8)
        if show_bit_labels:
            mid = s + spb / 2
            ax.text(mid, 1.25, label, ha="center", va="bottom",
                    fontsize=7.5, color=color, rotation=30,
                    fontweight="bold")

    plt.tight_layout()
    plt.savefig(filename, dpi=150)
    plt.close()
    print(f"Waveform image saved as '{filename}'")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    p = PARITY.strip().lower()
    if p not in ('even', 'odd', 'none'):
        raise ValueError(f"PARITY must be 'even', 'odd', or 'none', got '{PARITY}'")
    if STOP_BITS not in (1, 2):
        raise ValueError(f"STOP_BITS must be 1 or 2, got '{STOP_BITS}'")
    if not (5 <= DATA_BITS <= 9):
        raise ValueError(f"DATA_BITS must be between 5 and 9, got '{DATA_BITS}'")
    if not DATA_BYTES:
        raise ValueError("DATA_BYTES must contain at least one byte")

    describe_frames(DATA_BYTES, DATA_BITS, p, STOP_BITS)

    wb = build_uart_frames(DATA_BYTES, DATA_BITS, p, STOP_BITS,
                           idle_bits=IDLE_BITS,
                           inter_frame_bits=INTER_FRAME_BITS)
    plot_uart_waveform(wb, DATA_BYTES, DATA_BITS, p, STOP_BITS,
                       filename="uart_waveform.png",
                       show_bit_labels=SHOW_BIT_LABELS)
