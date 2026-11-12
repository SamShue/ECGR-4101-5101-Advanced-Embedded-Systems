# STM32 Bootloader Demo Application

Example STM32CubeIDE/CubeMX application project meant to be loaded by the
paired [STM32_Custom_Bootloader](../STM32_Custom_Bootloader) project, which
resides in its own, separate section of flash. Target: NUCLEO-L496ZG-P
(STM32L496ZGTxP).

## Flash memory map

The 1MB flash on the STM32L496ZG is split between the bootloader and this
application:

| Region      | Address range             | Size  |
|-------------|---------------------------|-------|
| Bootloader  | `0x08000000` - `0x08007FFF` | 32 KB |
| Application | `0x08008000` - `0x080FFFFF` | 992 KB |

This project's `STM32L496xx_FLASH.ld` sets `FLASH ORIGIN = 0x08008000`, and
`Core/Src/system_stm32l4xx.c` relocates the vector table to the same address
(`USER_VECT_TAB_ADDRESS` / `VECT_TAB_OFFSET = 0x8000`) so interrupts and
exceptions are serviced correctly once control is handed off from the
bootloader.

## Behavior

Once the bootloader jumps into this application, it turns the onboard user
LED (LD2, PB7) on and keeps it steady (as opposed to the bootloader's
blinking pattern), to visually confirm that the application image is
running.

## Flashing both images

Build and flash both projects independently (e.g. with STM32CubeIDE,
STM32CubeProgrammer, or the generated CMake project) - each one only writes
to its own flash region, so flashing this application does not erase the
bootloader and vice versa. Reset the board after flashing both for the full
bootloader -> application hand-off to run.
