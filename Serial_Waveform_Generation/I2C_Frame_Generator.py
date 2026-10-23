#!/usr/bin/env python3
"""
Generate the signal waveform of an I2C transaction and plot SCL/SDA as an image.

Supports:
  - 7-bit slave addressing
  - Write-to-register:
      START | ADDR+W | ACK | REG_ADDR | ACK | DATA[0] | ACK | ... | DATA[n] | ACK | STOP
  - Read-from-register:
      START | ADDR+W | ACK | REG_ADDR | ACK | Sr | ADDR+R | ACK | DATA[0] | ACK | ... | DATA[n-1] | ACK | DATA[n] | NACK | STOP
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ================== CONFIG ==================
SLAVE_ADDR   = 0x48          # 7-bit slave address
OPERATION    = 'read'       # 'write' or 'read'
REG_ADDR     = 0x2C          # 8-bit register address
DATA_BYTES   = [0x56]  # Bytes to write (ignored for read)
READ_LEN     = 1             # Number of bytes to read (used only for reads)
IDLE_BITS    = 4             # Recessive (high) idle half-cycles before START
# ============================================

# Waveform resolution: each half-bit period = this many plot samples
SAMPLES_PER_HALF = 2


# ---------------------------------------------------------------------------
# Waveform builder helpers
# ---------------------------------------------------------------------------

class WaveformBuilder:
    """Accumulates (scl, sda) sample pairs."""

    def __init__(self, samples_per_half: int = 2):
        self.scl: list[float] = []
        self.sda: list[float] = []
        self.sph = samples_per_half
        self.annotations: list[tuple[int, str, str]] = []  # (sample_index, label, color)

    def _append(self, scl_val: float, sda_val: float, n: int = 1):
        self.scl.extend([scl_val] * n)
        self.sda.extend([sda_val] * n)

    def idle(self, half_periods: int = 1):
        """SCL=1, SDA=1 for given number of half-periods."""
        for _ in range(half_periods):
            self._append(1.0, 1.0, self.sph)

    def start(self, label: str = "S"):
        """START condition: SDA falls while SCL high."""
        # SCL high, SDA high -> SDA falls -> SCL falls
        self._append(1.0, 1.0, self.sph)   # idle
        idx = len(self.scl)
        self._append(1.0, 0.0, self.sph)   # SDA falls (START)
        self._append(0.0, 0.0, self.sph)   # SCL falls
        self.annotations.append((idx, label, "green"))

    def stop(self):
        """STOP condition: SDA rises while SCL high."""
        # SCL falls, SDA low -> SCL rises -> SDA rises
        self._append(0.0, 0.0, self.sph)   # SCL low, SDA low (setup)
        idx = len(self.scl)
        self._append(1.0, 0.0, self.sph)   # SCL rises
        self._append(1.0, 1.0, self.sph)   # SDA rises (STOP)
        self._append(1.0, 1.0, self.sph)   # bus idle
        self.annotations.append((idx, "P", "red"))

    def data_bit(self, bit: int):
        """One data bit: SCL low (SDA set), SCL high (sampled)."""
        sda_val = float(bit)
        self._append(0.0, sda_val, self.sph)  # SCL low, SDA valid
        self._append(1.0, sda_val, self.sph)  # SCL high, sampled

    def byte(self, value: int, label: str = "", color: str = "blue"):
        """8-bit byte MSB-first."""
        idx = len(self.scl)
        for i in range(7, -1, -1):
            self.data_bit((value >> i) & 1)
        if label:
            self.annotations.append((idx, label, color))

    def ack(self, nack: bool = False, driven_by: str = "slave"):
        """
        ACK (SDA=0) or NACK (SDA=1) bit.
        driven_by: 'slave' or 'master' (affects annotation color only)
        """
        idx = len(self.scl)
        self.data_bit(1 if nack else 0)
        tag = "NACK" if nack else "ACK"
        color = "purple" if driven_by == "slave" else "darkorange"
        self.annotations.append((idx, tag, color))


# ---------------------------------------------------------------------------
# Frame builders
# ---------------------------------------------------------------------------

def build_i2c_write(slave_addr: int, reg_addr: int, data_bytes: list[int],
                    idle_bits: int = 4) -> WaveformBuilder:
    """
    Build an I2C write transaction:
    IDLE | START | ADDR+W | ACK | REG | ACK | DATA... | ACK | STOP
    """
    wb = WaveformBuilder(SAMPLES_PER_HALF)

    wb.idle(idle_bits)
    wb.start("S")

    # Address + W (bit = 0)
    addr_byte = (slave_addr << 1) | 0
    wb.byte(addr_byte,
            label=f"ADDR=0x{slave_addr:02X}+W",
            color="navy")
    wb.ack(nack=False, driven_by="slave")

    # Register address
    wb.byte(reg_addr, label=f"REG=0x{reg_addr:02X}", color="teal")
    wb.ack(nack=False, driven_by="slave")

    # Data bytes
    for i, b in enumerate(data_bytes):
        wb.byte(b, label=f"DATA[{i}]=0x{b:02X}", color="darkblue")
        wb.ack(nack=False, driven_by="slave")

    wb.stop()
    return wb


def build_i2c_read(slave_addr: int, reg_addr: int, read_len: int,
                   idle_bits: int = 4) -> WaveformBuilder:
    """
    Build an I2C read transaction (register-addressed):
    IDLE | START | ADDR+W | ACK | REG | ACK | Sr | ADDR+R | ACK | DATA... | NACK | STOP

    Data bytes are shown as 0xFF (bus released by master, slave drives).
    """
    wb = WaveformBuilder(SAMPLES_PER_HALF)

    wb.idle(idle_bits)
    wb.start("S")

    # Address + W
    addr_byte_w = (slave_addr << 1) | 0
    wb.byte(addr_byte_w,
            label=f"ADDR=0x{slave_addr:02X}+W",
            color="navy")
    wb.ack(nack=False, driven_by="slave")

    # Register address
    wb.byte(reg_addr, label=f"REG=0x{reg_addr:02X}", color="teal")
    wb.ack(nack=False, driven_by="slave")

    # Repeated START
    wb.start("Sr")

    # Address + R (bit = 1)
    addr_byte_r = (slave_addr << 1) | 1
    wb.byte(addr_byte_r,
            label=f"ADDR=0x{slave_addr:02X}+R",
            color="darkgreen")
    wb.ack(nack=False, driven_by="slave")

    # Data bytes (slave drives SDA; shown as 0xFF placeholder)
    for i in range(read_len):
        is_last = (i == read_len - 1)
        wb.byte(0xFF, label=f"DATA[{i}]", color="coral")
        # Master sends NACK after last byte, ACK otherwise
        wb.ack(nack=is_last, driven_by="master")

    wb.stop()
    return wb


# ---------------------------------------------------------------------------
# Text description
# ---------------------------------------------------------------------------

def describe_transaction(slave_addr: int, operation: str, reg_addr: int,
                         data_bytes: list[int], read_len: int):
    print("=== I2C Transaction ===")

    # Q1
    print(f"Q: What is the address of the device being interacted with?")
    print(f"A: 0x{slave_addr:02X}  (7-bit slave address)")
    print()

    # Q2
    print(f"Q: Are we reading from the device or writing to it?")
    if operation == 'write':
        print(f"A: Writing to the device.")
    else:
        print(f"A: Reading from the device.")
    print()

    # Q3
    print(f"Q: What register are we accessing?")
    print(f"A: Register 0x{reg_addr:02X}")
    print()

    # Q4
    print(f"Q: What is the data being {'written' if operation == 'write' else 'read'}?")
    if operation == 'write':
        data_str = ", ".join(f"0x{b:02X}" for b in data_bytes)
        print(f"A: {data_str}  ({len(data_bytes)} byte{'s' if len(data_bytes) != 1 else ''})")
    else:
        print(f"A: {read_len} byte{'s' if read_len != 1 else ''} will be read from register "
              f"0x{reg_addr:02X}.  (Actual values are driven by the slave at runtime.)")
    print()


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def plot_i2c_waveform(wb: WaveformBuilder, filename: str = "i2c_waveform.png"):
    """Plot SCL and SDA waveforms with annotations."""
    n = len(wb.scl)
    t = list(range(n + 1))

    scl_step = wb.scl + [wb.scl[-1]]
    sda_step = wb.sda + [wb.sda[-1]]

    fig, axes = plt.subplots(2, 1, figsize=(16, 5), sharex=True,
                             gridspec_kw={"hspace": 0.05})

    # SCL
    ax_scl = axes[0]
    ax_scl.step(t, scl_step, where="post", color="steelblue",
                linewidth=1.5, label="SCL")
    ax_scl.set_ylim(-0.3, 1.5)
    ax_scl.set_yticks([0, 1])
    ax_scl.set_yticklabels(["LOW", "HIGH"])
    ax_scl.set_ylabel("SCL")
    ax_scl.grid(False)

    # SDA
    ax_sda = axes[1]
    ax_sda.step(t, sda_step, where="post", color="darkorange",
                linewidth=1.5, label="SDA")
    ax_sda.set_ylim(-0.3, 1.5)
    ax_sda.set_yticks([0, 1])
    ax_sda.set_yticklabels(["LOW", "HIGH"])
    ax_sda.set_ylabel("SDA")
    ax_sda.set_xlabel("Time")
    ax_sda.grid(False)

    # Dotted vertical lines at each SCL rising edge
    for i in range(1, n):
        if wb.scl[i - 1] == 0.0 and wb.scl[i] == 1.0:
            for ax in axes:
                ax.axvline(x=i, color="gray", linestyle=":", linewidth=0.8)

    axes[0].set_title("I2C Bus Waveform")
    plt.tight_layout()
    plt.savefig(filename, dpi=150)
    plt.close()
    print(f"Waveform image saved as '{filename}'")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    op = OPERATION.strip().lower()

    describe_transaction(SLAVE_ADDR, op, REG_ADDR, DATA_BYTES, READ_LEN)

    if op == 'write':
        wb = build_i2c_write(SLAVE_ADDR, REG_ADDR, DATA_BYTES,
                              idle_bits=IDLE_BITS)
    elif op == 'read':
        wb = build_i2c_read(SLAVE_ADDR, REG_ADDR, READ_LEN,
                             idle_bits=IDLE_BITS)
    else:
        raise ValueError(f"OPERATION must be 'write' or 'read', got '{OPERATION}'")

    plot_i2c_waveform(wb, filename="i2c_waveform.png")
