#!/usr/bin/env python3
"""
Generate the binary bitstream of a classical CAN data frame
and plot the CAN_H and CAN_L waveforms as an image.

- Standard 11-bit ID, data frame
- Bit stuffing applied
- CRC-15 included by default
"""

import matplotlib.pyplot as plt

# ================== CONFIG ==================
CAN_ID      = 0x012              # 11-bit identifier
DATA_BYTES  = [0x69, 0x02, 0x81]             #[0x11, 0x22, 0x33] # Up to 8 bytes
RTR         = 0                  # 0 = data frame, 1 = remote frame
IDE         = 0                  # 0 = standard ID, 1 = extended (not used here)
R0          = 0                  # Reserved bit
INCLUDE_CRC = True               # Set False to skip CRC computation
BIT_TIME    = 1.0                # Arbitrary time unit per bit
IDLE_BITS = 3                    # number of recessive bits before SOF
# ============================================

def int_to_bits(value: int, width: int) -> str:
    """Return 'width' bits (MSB first) for value."""
    return format(value, f"0{width}b")[-width:]

def compute_crc15_can(bitstring: str) -> str:
    """
    Compute CAN CRC-15 for given bitstring (SOF through last data bit, destuffed).
    Polynomial: x^15 + x^14 + x^10 + x^8 + x^7 + x^4 + x^3 + 1  (0x4599)
    """
    poly = 0x4599
    crc = 0x0000  # initial value

    for bit in bitstring:
        msb = (crc >> 14) & 0x1  # top bit of 15-bit CRC
        crc = ((crc << 1) & 0x7FFF) | int(bit)  # shift in new bit
        if msb:
            crc ^= poly

    return int_to_bits(crc, 15)

def stuff_bits(bits: str) -> str:
    """
    Apply CAN bit-stuffing: after 5 consecutive identical bits,
    insert one opposite bit and reset the count.
    """
    if not bits:
        return bits

    stuffed = bits[0]
    last_bit = bits[0]
    run_len = 1

    for b in bits[1:]:
        if b == last_bit:
            run_len += 1
        else:
            run_len = 1
            last_bit = b

        stuffed += b

        if run_len == 5:
            # Insert opposite bit
            stuffed += '1' if b == '0' else '0'
            run_len = 0  # reset sequence count; next bit starts a new run

    return stuffed

def build_can_frame_bits(can_id: int, data_bytes, rtr: int, ide: int, r0: int,
                         include_crc: bool = True, idle_bits: int = 0):
    """Return (destuffed_bits, stuffed_bits, stuff_bit_count)."""

    # ========== IDLE BEFORE FRAME ==========
    idle = '1' * idle_bits   # recessive idle bits

    # SOF
    sof = '0'

    # Arbitration Field
    id_bits  = int_to_bits(can_id, 11)
    rtr_bit  = '1' if rtr else '0'
    ide_bit  = '1' if ide else '0'
    r0_bit   = '1' if r0  else '0'

    # Control Field
    dlc = len(data_bytes)
    dlc_bits = int_to_bits(dlc, 4)

    # Data Field
    data_bits = ''.join(int_to_bits(b, 8) for b in data_bytes)

    # Core bits (SOF → end of DATA)
    core_bits = sof + id_bits + rtr_bit + ide_bit + r0_bit + dlc_bits + data_bits

    # CRC
    crc_bits = compute_crc15_can(core_bits) if include_crc else ""

    # Entire destuffed frame
    crc_delim = '1'
    ack_slot  = '1'
    ack_delim = '1'
    eof       = '1111111'
    ifs       = '111'

    destuffed_frame = core_bits + crc_bits + crc_delim + ack_slot + ack_delim + eof + ifs

    # ===== Bit Stuffing (only core+CRC) =====
    unstuffed_region = core_bits + crc_bits
    stuffed_region = stuff_bits(unstuffed_region)

    # Count stuff bits
    stuff_bit_count = len(stuffed_region) - len(unstuffed_region)

    stuffed_frame = stuffed_region + crc_delim + ack_slot + ack_delim + eof + ifs

    # Add idle before frame
    return (
        idle + destuffed_frame,
        idle + stuffed_frame,
        stuff_bit_count
    )

def bits_to_can_waveforms(bits: str):
    """
    Convert a stuffed CAN bitstring into CAN_H and CAN_L sample arrays.

    Dominant (0): CAN_H ~ 3.5V, CAN_L ~ 1.5V
    Recessive (1): CAN_H ~ 2.5V, CAN_L ~ 2.5V
    """
    can_h = []
    can_l = []
    for b in bits:
        if b == '0':  # dominant
            can_h.append(3.5)
            can_l.append(1.5)
        else:         # recessive
            can_h.append(2.5)
            can_l.append(2.5)
    return can_h, can_l

def plot_can_waveform(bits: str, bit_time: float = 1.0,
                      filename: str = "can_waveform.png"):
    """
    Plot CAN_H and CAN_L waveforms for the given stuffed bitstring,
    add vertical dotted lines between each bit boundary,
    and save to 'filename'.
    """
    num_bits = len(bits)
    t = [i * bit_time for i in range(num_bits + 1)]

    can_h, can_l = bits_to_can_waveforms(bits)

    # Duplicate last sample for step plot alignment
    can_h_step = can_h + [can_h[-1]]
    can_l_step = can_l + [can_l[-1]]

    plt.figure(figsize=(14, 5))
    plt.step(t, can_h_step, where="post", label="CAN_H", linewidth=1.5)
    plt.step(t, can_l_step, where="post", label="CAN_L", linewidth=1.5)

    # ===== Vertical dotted lines for each bit =====
    for i in range(num_bits + 1):
        x = i * bit_time
        plt.axvline(x=x, color="gray", linestyle=":", linewidth=0.8)

    plt.xlabel("Time (bit intervals)")
    plt.ylabel("Voltage (V)")
    plt.title("CAN Bus Waveform")

    # ===== Disable horizontal grid lines =====
    # Horizontal grid removed; vertical lines only are drawn manually above.
    plt.grid(False)

    plt.legend(loc="upper right")
    plt.tight_layout()
    plt.savefig(filename, dpi=150)
    plt.close()


if __name__ == "__main__":
    destuffed_bits, stuffed_bits, stuff_count = build_can_frame_bits(
        CAN_ID, DATA_BYTES, RTR, IDE, R0, INCLUDE_CRC, idle_bits=IDLE_BITS
    )

    print("=== CAN Frame (destuffed) ===")
    print(destuffed_bits)
    print("Length:", len(destuffed_bits), "bits\n")

    print("=== CAN Frame (stuffed, on the bus) ===")
    print(stuffed_bits)
    print("Length:", len(stuffed_bits), "bits\n")

    print(f"Stuff bits inserted: {stuff_count}")

    # Plot waveform for the stuffed (on-bus) bits
    plot_can_waveform(stuffed_bits, bit_time=BIT_TIME,
                      filename="can_waveform.png")
    print("Waveform image saved as 'can_waveform.png'")
