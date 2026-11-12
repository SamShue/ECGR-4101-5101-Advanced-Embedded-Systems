# STM32 Custom Bootloader

Example STM32CubeIDE/CubeMX project demonstrating a minimal custom bootloader
that resides in its own section of flash, separate from an application image.
Pairs with the [STM32_Bootloader_Demo_Application](../STM32_Bootloader_Demo_Application)
project. Target: NUCLEO-L496ZG-P (STM32L496ZGTxP).

## Flash memory map

The 1MB flash on the STM32L496ZG is split between this bootloader and the
paired application:

| Region      | Address range             | Size  |
|-------------|---------------------------|-------|
| Bootloader  | `0x08000000` - `0x08007FFF` | 32 KB |
| Application | `0x08008000` - `0x080FFFFF` | 992 KB |

This is configured via the `FLASH` entry in each project's
`STM32L496xx_FLASH.ld` linker script. The application also relocates its
vector table to `0x08008000` (`VECT_TAB_OFFSET` in `system_stm32l4xx.c`) so
that interrupts/exceptions are serviced by its own handlers once running.

## Behavior

1. On reset, this bootloader runs first and blinks the onboard user LED
   (LD2, PB7) 10 times to show that it is alive.
2. It then validates and jumps to the application image at `0x08008000`
   (`JumpToApplication()` in `Core/Src/main.c`), relocating the vector table
   and stack pointer before branching to the application's reset handler.
3. If no valid application is programmed at that address (i.e. the initial
   stack pointer read from the application's vector table doesn't point into
   SRAM), the bootloader stays resident and blinks LD2 quickly instead of
   jumping into undefined memory.

## Flashing both images

Build and flash both projects independently (e.g. with STM32CubeIDE,
STM32CubeProgrammer, or the generated CMake project) - each one only writes
to its own flash region, so flashing the application does not erase the
bootloader and vice versa. Reset the board after flashing both for the full
bootloader -> application hand-off to run.
