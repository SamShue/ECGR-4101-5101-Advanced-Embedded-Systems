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
2. It then jumps unconditionally to the application image at `0x08008000`
   (`JumpToApplication()` in `Core/Src/main.c`): it reads the application's
   initial stack pointer and reset vector straight out of its vector table,
   sets `SCB->VTOR` and the main stack pointer (`__set_MSP()`), and calls the
   application's reset handler.

This is intentionally the simplest version of a bootloader hand-off: there is
no validity check on the application image and no peripheral/clock
de-initialization before the jump. A production bootloader would typically
verify the application (e.g. a checksum/CRC, or at least checking that the
stack pointer looks like a RAM address) and reset peripherals/clocks to a
known state first, but neither is necessary to demonstrate the core concept:
set the stack pointer and vector table, then jump.

## Flashing both images

Build and flash both projects independently (e.g. with STM32CubeIDE,
STM32CubeProgrammer, or the generated CMake project) - each one only writes
to its own flash region, so flashing the application does not erase the
bootloader and vice versa. Reset the board after flashing both for the full
bootloader -> application hand-off to run.
