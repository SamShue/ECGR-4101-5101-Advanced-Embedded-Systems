#!/usr/bin/env python3
"""
Generate a USB data packet and plot the D+ and D- waveforms as an image.

- Low-speed (1.5 Mbit/s) or full-speed (12 Mbit/s), selectable below
- DATA0 / DATA1 packet: SYNC, PID, data bytes (LSB first), CRC-16, EOP
- NRZI encoding (0 = transition, 1 = no transition)
- Bit stuffing applied (a 0 is inserted after six consecutive 1s)
- Finite rise/fall time so the D+ and D- crossings are visible

Line states:
    Full-speed: J = (D+ high, D- low),  K = (D+ low,  D- high)
    Low-speed:  J = (D+ low,  D- high), K = (D+ high, D- low)
    SE0       = (D+ low, D- low)   -> used for End Of Packet (EOP)
The bus idles in the J state.
"""

import matplotlib.pyplot as plt

# ================== CONFIG ==================
SPEED          = "low"           # "low" or "full"
PID_NAME       = "DATA0"         # "DATA0" or "DATA1"
DATA_BYTES     = [0x3F]          # Payload bytes (sent LSB first)
IDLE_BITS      = 3               # Idle (J) bit times before SYNC and after EOP
RISE_FRACTION  = 0.2             # Rise/fall time as a fraction of one bit time
V_HIGH         = 3.3             # Logic-high voltage (V)
V_LOW          = 0.0             # Logic-low voltage (V)
SHOW_ANSWER    = True            # Print the decoded answer to the console
OUTPUT_FILE    = "usb_waveform.png"
# ============================================

# Bit time in nanoseconds for each speed
BIT_TIME_NS = {"low": 1e3 / 1.5, "full": 1e3 / 12.0}

PIDS = {"DATA0": 0b0011, "DATA1": 0b1011}

SYNC = "00000001"                # Sent LSB first: KJKJKJKK after NRZI


def int_to_bits_lsb_first(value: int, width: int) -> str:
    """Return 'width' bits of value, least significant bit first."""
    return "".join(str((value >> i) & 1) for i in range(width))


def compute_crc16_usb(data_bytes) -> str:
    """
    Compute USB CRC-16 (x^16 + x^15 + x^2 + 1) over the data bytes.
    Data is processed LSB first, the register starts at 0xFFFF and the
    result is inverted. The CRC is transmitted MSB first.
    """
    crc = 0xFFFF
    for byte in data_bytes:
        for i in range(8):
            bit = (byte >> i) & 1
            if ((crc >> 15) & 1) ^ bit:
                crc = ((crc << 1) ^ 0x8005) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    crc ^= 0xFFFF
    return format(crc, "016b")


def build_packet_bits(pid_name: str, data_bytes):
    """Return (pre-stuffing bits, field dict) for SYNC + PID + DATA + CRC16."""
    pid = PIDS[pid_name]
    pid_byte = ((~pid & 0xF) << 4) | pid         # PID check nibble in upper bits
    pid_bits = int_to_bits_lsb_first(pid_byte, 8)
    data_bits = "".join(int_to_bits_lsb_first(b, 8) for b in data_bytes)
    crc_bits = compute_crc16_usb(data_bytes)

    fields = {"SYNC": SYNC, "PID": pid_bits, "DATA": data_bits, "CRC16": crc_bits}
    return SYNC + pid_bits + data_bits + crc_bits, fields


def stuff_bits(bits: str) -> str:
    """
    Apply USB bit stuffing: after six consecutive 1s, insert a 0.
    The final 1 of SYNC counts toward the run.
    """
    stuffed = ""
    ones = 0
    for b in bits:
        stuffed += b
        ones = ones + 1 if b == "1" else 0
        if ones == 6:
            stuffed += "0"
            ones = 0
    return stuffed


def nrzi_encode(bits: str) -> str:
    """
    NRZI encode to line states 'J' / 'K', starting from the idle J state.
    0 = toggle the line state, 1 = keep the line state.
    """
    state = "J"
    out = ""
    for b in bits:
        if b == "0":
            state = "K" if state == "J" else "J"
        out += state
    return out


def build_line_states(stuffed_bits: str, idle_bits: int) -> str:
    """Idle + NRZI packet + EOP (SE0, SE0, J) + idle. SE0 is shown as '0'."""
    return "J" * idle_bits + nrzi_encode(stuffed_bits) + "00J" + "J" * idle_bits


def state_to_levels(state: str, speed: str):
    """Return (D+, D-) voltages for a line state."""
    if state == "0":                       # SE0
        return V_LOW, V_LOW
    j_is_dplus_high = (speed == "full")
    dplus_high = (state == "J") == j_is_dplus_high
    return (V_HIGH, V_LOW) if dplus_high else (V_LOW, V_HIGH)


def line_states_to_waveforms(states: str, speed: str, bit_time: float,
                             rise_fraction: float):
    """
    Build piecewise-linear (time, D+, D-) points. Each bit boundary starts a
    ramp lasting rise_fraction * bit_time toward the new level.
    """
    rise = rise_fraction * bit_time
    t = [0.0]
    dp, dm = state_to_levels(states[0], speed)
    dplus, dminus = [dp], [dm]

    for i in range(1, len(states)):
        new_dp, new_dm = state_to_levels(states[i], speed)
        if (new_dp, new_dm) != (dp, dm):
            t += [i * bit_time, i * bit_time + rise]
            dplus += [dp, new_dp]
            dminus += [dm, new_dm]
            dp, dm = new_dp, new_dm

    t.append(len(states) * bit_time)
    dplus.append(dp)
    dminus.append(dm)
    return t, dplus, dminus


def plot_usb_waveform(states: str, speed: str, filename: str = "usb_waveform.png",
                      number_bits: bool = False):
    """
    Plot D+ and D- with dotted bit-boundary gridlines and save to 'filename'.
    If number_bits is True, each bit time is numbered (1..N) along the top.
    """
    bit_time_ns = BIT_TIME_NS[speed]
    t, dplus, dminus = line_states_to_waveforms(states, speed, bit_time_ns,
                                                RISE_FRACTION)
    t_us = [x / 1000.0 for x in t]

    plt.figure(figsize=(14, 3))
    plt.plot(t_us, dplus, label="D+", linewidth=1.5)
    plt.plot(t_us, dminus, label="D-", linewidth=1.5)

    # Dotted lines mark the boundaries between bit times; each bit's state/value
    # is read from the space between two boundaries, not at the lines themselves
    for i in range(1, len(states)):
        plt.axvline(x=i * bit_time_ns / 1000.0, color="gray",
                    linestyle=":", linewidth=0.8)

    if number_bits:
        for i in range(len(states)):
            plt.text((i + 0.5) * bit_time_ns / 1000.0, V_HIGH + 0.35, str(i + 1),
                     ha="center", va="center", fontsize=8)

    plt.xlabel("Time (\u00b5s)")
    plt.ylabel("Voltage (V)")
    plt.title("USB Bus Waveform")
    plt.ylim(V_LOW - 0.4, V_HIGH + 0.6)
    plt.xlim(0, len(states) * bit_time_ns / 1000.0)
    plt.grid(False)
    plt.legend(loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=2)
    plt.tight_layout()
    plt.savefig(filename, dpi=150)
    plt.close()


if __name__ == "__main__":
    pre_stuff_bits, fields = build_packet_bits(PID_NAME, DATA_BYTES)
    stuffed_bits = stuff_bits(pre_stuff_bits)
    stuff_count = len(stuffed_bits) - len(pre_stuff_bits)
    line_states = build_line_states(stuffed_bits, IDLE_BITS)

    if SHOW_ANSWER:
        print(f"=== USB {SPEED}-speed {PID_NAME} packet ===")
        print(f"Bit time: {BIT_TIME_NS[SPEED]:.1f} ns")
        for name, bits in fields.items():
            print(f"{name:6s}: {bits}")
        print("\nBits before stuffing (SYNC..CRC16):")
        print(pre_stuff_bits)
        print("Bits on the bus after stuffing:")
        print(stuffed_bits)
        print(f"Stuff bits inserted: {stuff_count}\n")
        print("Line states (J/K, 0 = SE0):")
        print(line_states)
        print("\nData bytes (LSB first -> hex):",
              " ".join(f"0x{b:02X}" for b in DATA_BYTES))

    plot_usb_waveform(line_states, SPEED, filename=OUTPUT_FILE)
    print(f"Waveform image saved as '{OUTPUT_FILE}'")
