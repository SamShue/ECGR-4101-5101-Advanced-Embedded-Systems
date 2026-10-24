# Overview

In this lab, we will use the on-board USB peripheral to receive data and perform a firmware update using a bootloader. The bootloader initializes the USB interface and receives data from an application running on a PC, which transmits the compiled application binary to the bootloader byte by byte over the USB connection. The bootloader then uses that data to overwrite the application's flash region, replacing the old application firmware with the new one. This lab will give you insight into how firmware updates are delivered to embedded systems after they have already been programmed and shipped from the factory.

# Required Materials

- NUCLEO-L496ZG-P development board (same board used in Lab 1)
- Two USB Micro-B cables - one connects the ST-LINK programmer (used to load the bootloader itself), and the other connects to the board's USB OTG FS port (used by the bootloader to receive the application firmware)
- Laptop with Python development tools installed

# Background

## What is a Bootloader?

When a product containing an embedded system is developed, it is sometimes necessary to update its firmware after the device has been deployed or sold - for example, to patch a bug or add a new feature. Normally, we use a device called a programmer to flash new firmware directly onto a microcontroller. However, it is expensive and impractical to ship a programmer with every device that uses the deployed microcontroller.

The solution is to have the microcontroller run two programs instead of one. The first program is the actual application that the microcontroller is designed to run. The second program is called a bootloader. In typical use, the bootloader simply launches the application. However, the bootloader can also overwrite the program memory used by the main application before launching it, taking over the job normally done by a hardware programmer.

Bootloaders are not objectively better than a hardware programmer, though. They cannot perform debugging, and they introduce a risk of "bricking" the microcontroller: if the bootloader itself becomes corrupted, it can no longer upload new application code, nor will it be able to launch the existing application. Bootloaders are therefore a compromise - they let us update application firmware in the field without requiring expensive programmer hardware to be built into every product.

## What Happens on Startup?

Before we can understand how a microcontroller switches from running one program to another, we first need to understand what happens during startup in a typical single-application scenario - how the microcontroller fetches its program and sets up memory.

Everything the microcontroller needs to run its application is stored in flash memory. Flash is the non-volatile section of memory that holds not only our program code, but also other information, such as the contents of the `.data` and `.bss` regions, as well as the handler pointers for the interrupt vector table.

```
Application Flash region
0x08000000
+---------------------------+
| .isr_vector               |  <-- vector table
| Initial MSP               |
| Reset_Handler             |
| NMI_Handler               |
| HardFault_Handler         |
| ...                       |
+---------------------------+
| .text                     |  <-- executable code
| Reset_Handler code        |
| main()                    |
| interrupt handlers        |
| other functions           |
+---------------------------+
| .rodata                   |
| constants                 |
+---------------------------+
| ...                       |
+---------------------------+
```

When an STM32 microcontroller first starts up, it begins by reading the values in the interrupt vector table. It looks for this table at address 0x00000000. This address is aliased by the hardware to the beginning of flash memory at 0x08000000. Because of how the data is organized, when we flash our program into memory, its interrupt vector table ends up aligned with this very first address.

The STM32 device reads the first 4-byte (32-bit) entry in the vector table, which contains the initial main stack pointer (MSP) and establishes the stack frame. The second entry contains the address of the reset handler, which is then called to begin setting up everything the program needs to run - including copying the constants and other values that live in the `.data` and `.bss` regions into the appropriate locations in SRAM.

## How do Bootloaders Work?

The idea behind a bootloader is that we launch one program first - the bootloader - which performs some operation and then eventually launches a second program, the application, in its place. The bootloader runs first because its vector table is linked to the memory address that the microcontroller always checks on startup. Once the bootloader finishes its work (for example, checking for and installing a new application image), it resets the stack pointer, sets the program counter to the application's starting address, and calls the reset handler associated with the application program.

### Sharing Memory with Two Programs

We fit two programs onto the microcontroller by dividing the available flash memory into two separate regions: one for the bootloader and one for the application. Each program needs its own text region and its own interrupt vector table.

Let's start by considering the text region. On most STM32 microcontrollers, flash memory begins at address 0x08000000; in this case it spans 1 MB (1024 KB). We might designate the lower 64 KB of this memory for the bootloader, and the remaining ~960 KB, starting at address 0x08010000, for the application.

```
STM32 Internal Flash
Example: Bootloader + Main Application

Higher Address
0x080FFFFF
+---------------------------------------------------+
|                                                   |
|              Main Application Region              |
|                                                   |
|  0x08010000                                       |
|  +--------------------------------------------+   |
|  | .isr_vector                                |   |
|  |                                            |   |
|  | Initial MSP                                |   |
|  | Reset_Handler address                      |   |
|  | NMI_Handler address                        |   |
|  | HardFault_Handler address                  |   |
|  | Peripheral interrupt handler addresses     |   |
|  +--------------------------------------------+   |
|  | .text                                      |   |
|  |                                            |   |
|  | Reset_Handler code                         |   |
|  | main()                                     |   |
|  | Application functions                      |   |
|  | Interrupt service routines                 |   |
|  | HAL / driver code                          |   |
|  +--------------------------------------------+   |
|  | .rodata                                    |   |
|  |                                            |   |
|  | Constants                                  |   |
|  | Strings                                    |   |
|  | Lookup tables                              |   |
|  +--------------------------------------------+   |
|  | Initial values for .data                   |   |
|  | and other application Flash contents       |   |
|  +--------------------------------------------+   |
|  |                                            |   |
|  |            Unused Application Flash        |   |
|  |                                            |   |
+--+--------------------------------------------+---+ <---- Application starts at 0x08010000
+--------------------------------------------------+ 0x0800FFFF
|                                                   |
|                Bootloader Region                  |
|                                                   |
|  0x08000000                                       |
|  +--------------------------------------------+   |
|  | .isr_vector                                |   |
|  |                                            |   |
|  | Initial MSP                                |   |
|  | Reset_Handler address                      |   |
|  | NMI_Handler address                        |   |
|  | HardFault_Handler address                  |   |
|  | Peripheral interrupt handler addresses     |   |
|  +--------------------------------------------+   |
|  | .text                                      |   |
|  |                                            |   |
|  | Reset_Handler code                         |   |
|  | Bootloader main()                          |   |
|  | USB CDC code                               |   |
|  | Flash erase/program routines               |   |
|  | Application validation                     |   |
|  | Jump-to-application routine                |   |
|  +--------------------------------------------+   |
|  | .rodata                                    |   |
|  |                                            |   |
|  | USB descriptors                            |   |
|  | Constants                                  |   |
|  | Strings                                    |   |
|  +--------------------------------------------+   |
|  | Initial values for .data                   |   |
|  | and other bootloader Flash contents        |   |
|  +--------------------------------------------+   |
|  |            Unused Bootloader Space         |   |
+--+--------------------------------------------+---+  <--- Bootloader starts at 0x08000000

0x08000000
Lower Address
```

### Relocating the Interrupt Vector Table

We also have to consider the interrupt vectors.

The bootloader and the application are both separate programs, each with its own set of interrupts and interrupt handlers. When both programs are sitting in flash, we can see that each has its own vector table region.

The problem is that the vector table alias at address 0x00000000 always points to the fixed hardware address 0x08000000 - the very start of flash memory, where the bootloader's vector table lives. When we switch over to running the application, we need a way to tell the processor to look for the vector table at the application's location instead.

STM32 devices include a special hardware register for exactly this purpose, called the VTOR (Vector Table Offset Register). By writing a new base address into the VTOR register, we tell the processor where its interrupt vector table now begins.

```
At reset:

VTOR = 0x00000000

0x00000000 alias -> 0x08000000
                         |
                         v
                 Bootloader vectors


After bootloader handoff:

VTOR = 0x08010000
             |
             v
       Application vectors
```

If we don't relocate the vector table, the application will still launch and run as normal. However, when it tries to service an interrupt, the processor will still look up the handler in the bootloader's vector table instead of the application's, since VTOR was never updated to point at the application's table. This means the wrong handler function will run.

## Typical Bootloader Applications

One of the most common uses of a bootloader is to allow application firmware updates after deployment, without needing a hardware programmer.

This is typically done by sending the bytes of a new application over a serial interface, such as UART, SPI, USB, or even a wireless link. In this lab, we will use USB to transmit the compiled application firmware from a desktop or laptop host machine to the target STM32 device.

## The USB Peripheral

Up to this point, we've discussed how a bootloader is laid out in flash memory and how it eventually hands control over to the application. The remaining piece is how the bootloader actually receives the new application image from your laptop in the first place. In this lab, we will use the microcontroller's built-in USB peripheral to carry that data across the cable connecting your laptop to the Nucleo board.

### Host and Device Roles

USB (Universal Serial Bus) connections are organized around a host and a device. The host is almost always a PC or laptop - it is in charge of the connection and decides when and how often data is exchanged. The device is whatever peripheral is plugged into the host, such as a mouse, a flash drive, or, in our case, the STM32 microcontroller itself. A device can never start a conversation on its own; it can only respond when the host asks it to. This is an important detail to keep in mind, because it means our bootloader is always reacting to requests coming from the Python application running on your laptop, rather than pushing data out whenever it feels like it.

### Enumeration and Descriptors

When you first plug a USB device into a host, the host does not yet know what kind of device it is or how to talk to it. The host resolves this through a process called enumeration. During enumeration, the host asks the device a series of standard questions, and the device answers with small blocks of information called descriptors. These descriptors tell the host things such as who manufactured the device, what kind of device it claims to be, and how many logical communication channels it needs. Only after enumeration finishes does the host know how to properly exchange data with the device.

Each of these logical communication channels is called an endpoint. You can think of an endpoint as a single lane on a highway - data traveling to or from the device moves through the lane it was assigned, and a single device can have several endpoints open for different purposes at the same time. We won't go into endpoint-level detail in this course, but it is worth knowing that even a simple USB connection is already relying on this enumeration and endpoint negotiation to work behind the scenes.

### USB Device Classes

Rather than inventing a new way of communicating for every USB product, most USB devices identify themselves during enumeration as belonging to a standard device class. A device class is simply an agreed-upon pattern for how a type of device communicates, so that host operating systems can ship one generic driver that works with any device claiming that class, instead of requiring a custom driver for every single product. Common classes include HID (Human Interface Device, used for keyboards and mice) and Mass Storage (used for flash drives).

For this lab, our bootloader will enumerate as a CDC (Communications Device Class) device. CDC is the class used to make a USB device appear to the host as a virtual serial (COM) port. This is extremely convenient for us: Windows, macOS, and Linux all already include a generic CDC driver, so as soon as our bootloader enumerates, your laptop will simply show a new serial port, with no custom driver installation required. From the Python application's point of view, sending data to the bootloader is no different than writing bytes out to any other serial port.

```
Laptop (Host)                               Nucleo Board (Device)
+-------------------------+                  +--------------------------------+
| Python application      |                  | USB Peripheral (OTG FS)        |
| writes .bin file bytes  |<== USB cable ==> | enumerates as CDC device       |
| to the virtual COM port |                  | (acts like a virtual COM port) |
+-------------------------+                  +--------------------------------+
                                                              |
                                                              v

                                              Bootloader reads the incoming bytes
                                              and writes them into the
                                              application's Flash region
```

### Putting It Together

You will not need to implement the USB protocol yourself for this lab. STM32 provides a USB device library, part of the STM32Cube software package, that already implements enumeration, descriptors, and the CDC class on your behalf. Your bootloader will configure and initialize this library so that the board enumerates as a virtual COM port, and then use the functions the library provides to receive incoming bytes as they arrive. We will cover the specific functions and configuration steps later in the lab procedure - for now, the important concept to take away is that the Python application will treat the connection like an ordinary serial port, writing the compiled `.bin` file byte by byte, while the bootloader's job is to receive each of those bytes and use them to reconstruct the application image in flash memory.

## Overwriting the Application Flash

Once the bootloader has received the bytes of a new application image over USB, it still cannot simply drop those bytes directly into flash memory the way you might write to a file or to RAM. Flash memory has some unusual physical properties that the bootloader has to work around, and misunderstanding them is one of the easiest ways to accidentally corrupt a device. This section covers the concepts you'll need before your bootloader can safely rewrite the application's flash region.

### What Is Flash Memory, and Why Is It Different from RAM?

Up to this point in your coursework, most of the memory you've worked with directly has probably been SRAM - the memory used for variables, the stack, and the heap. SRAM is volatile: it only holds whatever was last written to it while the chip has power, and it can be rewritten freely, one byte at a time, with no special preparation. The instant power is removed, its contents are gone.

Flash memory is built very differently, and for a specific reason: it needs to still contain your compiled program the instant the microcontroller powers on, long after whatever programmed it has been unplugged. To make that possible, flash memory is non-volatile - it retains its contents with no power applied at all.

It achieves this by storing each bit in a transistor with an extra, electrically isolated "floating gate" buried inside it. Trapping a small electric charge on that floating gate (or leaving it uncharged) permanently shifts how the transistor behaves, in a way that can be read back later as a `0` or a `1` - and because the gate is electrically isolated from the rest of the circuit, that trapped charge has nowhere to leak away to, even with the power off. This is a fundamentally different physical mechanism from the volatile storage cells used in SRAM, and it comes with a major trade-off: adding charge to a single floating gate (programming a bit to `0`) is a quick, localized operation, but removing that charge (erasing a bit back to `1`) requires a much stronger, longer voltage pulse - one that is only practical to apply across a whole group of cells at once, rather than to a single isolated bit. That one asymmetry is the root cause of nearly everything in this section: it's why flash has to be erased in blocks, why you can't just overwrite old data directly, and why a "page" exists as a concept at all.

### Erasing Before Writing

Flash memory stores each bit using a tiny transistor that can only be changed in one direction by a normal write operation. Programming a flash memory location can only change bits from `1` to `0`; it cannot change a bit from `0` back to `1`. In order to set bits back to `1`, the flash controller has to perform a separate operation called an erase, which resets an entire block of memory back to all `1`s (every erased byte reads back as `0xFF`) all at once.

This has an important consequence for your bootloader: you cannot simply program new data directly over old application data and expect it to come out correctly, because programming can only turn additional bits off, never back on. Before the bootloader can write a new application image into flash, it must first erase the pages that make up the application's flash region.

```
Before erase (old application data):
0x08010000: 0x3F  0x00  0xA2  0x18 ...

After erasing the page:
0x08010000: 0xFF  0xFF  0xFF  0xFF ...

After programming the new application data:
0x08010000: 0x20  0x00  0x08  0x08 ...
```

Erasing is also much coarser than programming - a single erase command wipes out an entire page at once, not just the handful of bytes you intend to change. This means the bootloader needs to erase every page the new application image will occupy before it starts writing, or it risks leaving old application bytes mixed in with new ones.

### Pages: The Smallest Unit You Can Erase

The erase pulse described above is naturally applied to many flash cells at once rather than one at a time - building separate erase circuitry for every individual byte would be impractical. So instead, chip manufacturers divide flash memory into fixed-size blocks called pages, and the erase operation always targets one or more whole pages. A page is the smallest region of flash the hardware can erase in a single operation: you cannot erase "just the first half" of a page, and erasing a page always resets every byte in it back to `0xFF`, whether you needed all of it or not.

On the STM32L4 family used in this lab, each flash page is 2 KB (2048 bytes). Since the NUCLEO-L496ZG-P has 1 MB of flash in total, that works out to 512 pages across the whole chip. Combined with the memory map we set up back in Sharing Memory with Two Programs, this tells us exactly how many pages each region of flash occupies:

```
64 KB bootloader region    = (64 * 1024 bytes) / (2 * 1024 bytes/page)  = 32 pages   (pages 0-31)
960 KB application region  = (960 * 1024 bytes) / (2 * 1024 bytes/page) = 480 pages  (pages 32-511)
```

When your bootloader erases the application's flash region as part of Requirement 2, it needs to erase exactly these 480 pages - no fewer, or old application bytes will linger underneath the new image, and no more, since erasing even a single one of the bootloader's own 32 pages while the bootloader is still running from them would corrupt the very program doing the erasing. Always confirm the exact page size for your specific microcontroller in its reference manual before writing this code - it can differ between STM32 families, and even between different flash configurations of the same family.

### Flash Write Granularity

Although the USB peripheral hands the bootloader its data one byte at a time, the flash controller does not allow writes at that resolution. On the STM32L4 family used in this lab, flash memory must be programmed in aligned 64-bit (8-byte) chunks, referred to as double words. Attempting to program a single byte, or a chunk that isn't aligned to an 8-byte boundary, is not permitted by the hardware.

This restriction isn't arbitrary: the flash controller computes an error-detection code over each 64-bit chunk at the moment it's programmed, so that it can later detect (and in some cases correct) a corrupted bit when that location is read back. Computing that code requires having the full 8 bytes available at once, which is why the hardware only exposes a double-word-at-a-time programming operation rather than a byte-at-a-time one.

This means the bootloader cannot write each byte to flash the moment it arrives over USB. Instead, it needs to collect incoming bytes into a small buffer in RAM, and only once it has accumulated a full double word does it issue a flash program operation for that chunk, then go back to collecting bytes for the next one.

### Unlocking the Flash Controller

As one more safeguard against accidental corruption, the flash controller on STM32 devices is locked by default and will reject any erase or program command until it has been explicitly unlocked with a specific key sequence. Once the bootloader is done erasing and programming, it's good practice to lock the flash controller again. We won't go through the exact unlock sequence here - the STM32 HAL library we'll use in the lab procedure provides functions that handle this for us.

### Putting It All Together

Pulling these concepts together, the bootloader's job when receiving a new application image looks something like this: as bytes arrive over the USB CDC connection, the bootloader appends them to a buffer; once it has erased the application's flash region and accumulated enough buffered bytes to fill an aligned double word, it unlocks the flash controller, programs that double word into the application's flash region starting at address `0x08010000`, and then goes back to collecting more incoming bytes. This repeats until the entire compiled application binary has been written into flash.

Notice that the bootloader only ever erases and programs the application's flash region, starting at `0x08010000` - it never touches its own flash region while doing this. This is exactly why we dedicated a separate region of flash to the bootloader in the first place: if the bootloader accidentally erased or overwrote its own code while it was still running, there would be no way to recover the device.

# Project Structure

Everything we discussed in the Background section was conceptual - two programs, two flash regions, one VTOR register. Now we need to actually build that arrangement. This means creating two completely separate STM32CubeMX projects (one for the bootloader, one for the application), telling each project's linker where it is allowed to live in flash, and setting up a Python environment on your laptop that will act as the host-side application mentioned in the Overview. By the end of this section, you will have both STM32 projects generating code and building successfully, and a working Python environment ready to talk to the board over USB.

## 1. Create the Bootloader Project

The bootloader needs its own CubeMX project because it is its own program, with its own `main()`, its own vector table, and (as we'll set up in a moment) its own dedicated slice of flash. Follow the same CubeMX workflow you used in Lab 1:

1. Open **STM32CubeMX** and use the **Board Selector** to search for and select the **NUCLEO-L496ZG-P**, just as you did in Lab 1.
2. Click **Start Project**, and when prompted to initialize all peripherals with their default mode, click **Yes**. This gives you the same baseline LED, button, and ST-LINK UART configuration as before.
3. Before moving to the Project Manager tab, follow the steps below to enable the USB peripheral - this is the one configuration decision that differs from Lab 1.

### Enabling the USB Peripheral and CDC Class

Recall from The USB Peripheral section that our bootloader needs to enumerate as a CDC device so that it shows up on your laptop as an ordinary virtual COM port. CubeMX can generate all of the boilerplate code for this (the USB stack, descriptors, and CDC class driver), but only if you explicitly turn it on - it is not part of the default peripheral configuration.

1. While still in the **Pinout & Configuration** view, find the **Connectivity** category in the left-hand peripheral list and click **USB_OTG_FS**.
2. Set the **Mode** dropdown to **Device Only**. CubeMX will automatically assign and color the two pins this requires (USB D- and D+) - you do not need to configure them manually.
3. Next, find the **Middleware** (or **Middleware and Software Packs**) category and click **USB_DEVICE**.
4. Set the **Class For FS IP** dropdown to **Communication Device Class (Virtual Port Com)**. This is what tells CubeMX to generate the CDC class driver - the piece that is responsible for making the board present itself as a serial port - instead of some other USB device type.
5. Click over to the **Clock Configuration** tab. The USB peripheral requires a precise 48 MHz clock input, and enabling it will sometimes cause CubeMX to flag part of the clock tree in red. If this happens, click the **Resolve Clock Issues** button that appears, and CubeMX will automatically adjust the clock tree for you.
6. Return to the **Pinout & Configuration** view before continuing to the Project Manager tab.

With USB enabled, continue exactly as you did in Lab 1: open the **Project Manager** tab, give the project a name such as `Lab3_Bootloader`, choose a save location, leave **Application Structure** set to **Advanced**, and set **Toolchain / IDE** to **CMake**. Click **GENERATE CODE**, then open the generated folder in VS Code the same way you did in Lab 1.

## 2. Write the Bootloader Skeleton

CubeMX already generated a working `SystemClock_Config()`, `MX_GPIO_Init()`, and `MX_USB_DEVICE_Init()` for you, based on the USB configuration you just set up - these correctly drive the USB peripheral's 48 MHz clock requirement for your specific board and CubeMX version, so **leave them untouched**. Everything the bootloader still needs to do belongs in `main()` itself.

Open **Core → Src → main.c** in your `Lab3_Bootloader` project and replace the body of your generated `int main(void)` function with the version below. It already calls every initialization function CubeMX generated for you (including `MX_USB_DEVICE_Init()`, which starts USB enumeration) and marks, with `TODO` comments, exactly where each of the four Project Requirements belongs:

```c
int main(void)
{
  HAL_Init();
  SystemClock_Config();
  MX_GPIO_Init();
  MX_USB_DEVICE_Init();   /* Starts USB enumeration - your laptop will show a new
                              virtual COM port once this call returns. */

  /* TODO (Requirement 1): Decide here how the bootloader knows a new firmware
     image is about to arrive, versus just sitting idle until the user button
     is pressed (Requirement 4). A timeout window measured from this point,
     or a flag left behind by the application, are both reasonable options. */

  while (1)
  {
    /* TODO (Requirement 1, continued): Incoming USB bytes do not show up here
       automatically - they arrive in CDC_Receive_FS(), inside
       USB_DEVICE/App/usbd_cdc_if.c, which CubeMX already generated for you.
       You will need a way to get bytes from that callback into this loop
       (for example, a shared buffer and a flag), or do your flash
       programming directly from within that callback instead. Either way,
       figure out how you'll recognize when the full image has arrived. */

    /* TODO (Requirement 2): Once you have erased the application's flash
       region and accumulated a full aligned double word of incoming bytes,
       unlock the flash controller and program that double word starting at
       0x08010000. Repeat until the entire image has been written, then lock
       the flash controller again. */

    /* TODO (Requirement 4): Check whether the User button (B1_Pin on GPIOC)
       is pressed. If it is, relocate the vector table with SCB->VTOR, reset
       the stack pointer using the application's initial MSP value, and
       branch to the application's reset handler at 0x08010000 - this does
       not require a completed firmware transfer first. */
  }
}
```

> **Note:** Double-check `B1_Pin` and `B1_GPIO_Port` against your own project's `main.h` - these are the standard CubeMX names for the Nucleo's User button (B1, on PC13), but confirm them the same way you confirmed `LD1_Pin` back in Lab 1.

## 3. Create the Application Project

The application project is built the same way, but without any of the USB configuration above - in this lab, only the bootloader talks to the PC over USB. Repeat the same board-selector and default-peripheral steps as Lab 1, then name the project something like `Lab3_Application` in the Project Manager tab, keep **Advanced** structure and **CMake** toolchain, and generate the code.

At this point you should have two separate project folders on disk, each with its own `.ioc` file, `CMakeLists.txt`, and `Core/` folder - completely independent of one another, just like the bootloader and application are independent programs on the microcontroller.

## 4. Write a Minimal Blink Application

Before you start building the bootloader logic itself, it helps to have a tiny, disposable application to flash and re-flash while you test. Rather than hunting through the generated file for the right spots to add a few lines, simply replace the **entire contents** of **Core → Src → main.c** in your `Lab3_Application` project with the self-contained version below:

```c
#include "main.h"

#define FAST_BLINK 0   /* 0 = slow blink (original firmware), 1 = fast blink (updated firmware) */

#if FAST_BLINK
#define BLINK_DELAY_MS 100
#else
#define BLINK_DELAY_MS 500
#endif

void SystemClock_Config(void);
static void MX_GPIO_Init(void);

int main(void)
{
  HAL_Init();
  SystemClock_Config();
  MX_GPIO_Init();

  while (1)
  {
    HAL_GPIO_TogglePin(LD1_GPIO_Port, LD1_Pin);
    HAL_Delay(BLINK_DELAY_MS);
  }
}

void SystemClock_Config(void)
{
  /* This minimal application intentionally skips configuring the PLL and
     simply runs on the MCU's default reset clock (MSI). HAL_Delay() is
     still timed correctly against whatever clock is actually running, so
     the blink rate above is accurate regardless. */
}

static void MX_GPIO_Init(void)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};

  __HAL_RCC_GPIOD_CLK_ENABLE();

  HAL_GPIO_WritePin(LD1_GPIO_Port, LD1_Pin, GPIO_PIN_RESET);

  GPIO_InitStruct.Pin   = LD1_Pin;
  GPIO_InitStruct.Mode  = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull  = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(LD1_GPIO_Port, &GPIO_InitStruct);
}

void Error_Handler(void)
{
  __disable_irq();
  while (1)
  {
  }
}
```

This pulls in `LD1_Pin` and `LD1_GPIO_Port` from `main.h` (the same macros you located back in Lab 1), so there's nothing else to configure - it builds and runs entirely on its own, with no UART or button handling to get in the way of the one thing this test application needs to do.

> **Note:** `__HAL_RCC_GPIOD_CLK_ENABLE()` assumes LD1 lives on **GPIOD**, which is correct for the NUCLEO-L496ZG-P per Lab 1. If you open `main.h` and find `LD1_GPIO_Port` defined as a different port letter, change this one line to match (for example, `__HAL_RCC_GPIOB_CLK_ENABLE()` for GPIOB).

> **Note:** Because this replaces the whole file rather than living inside the `USER CODE` markers CubeMX normally preserves, regenerating code from CubeMX after this point will overwrite it. If that happens, just paste this same file back in.

Build the project once with `FAST_BLINK` set to `0` and flash it with the ST-LINK (exactly as you did in Lab 1) so the board starts out running a known-good application with a slow, once-per-second blink. Later, when you are ready to test your bootloader, change `FAST_BLINK` to `1`, rebuild, and use the resulting `.bin` file as the "new" firmware you transmit over USB - a correct update should be immediately obvious from the LED switching to a fast blink, with no need to inspect memory or attach a debugger to confirm it worked.

## 5. Modify the Linker Scripts to Share Flash

Right now, both freshly generated projects assume they own the *entire* flash chip starting at `0x08000000` - CubeMX has no way of knowing you intend to run two programs side by side. If you built and flashed both projects as-is, they would each try to occupy the exact same addresses, and the second one would simply overwrite the first. This is exactly the problem we solved conceptually in the Background section by splitting flash into a 64 KB bootloader region and a remaining application region starting at `0x08010000` - we now need to encode that split into each project.

Each generated project contains a linker script - a file ending in `_FLASH.ld` that tells the linker where in memory to place each section of your compiled program. Depending on your CubeMX version, you will find it either in the project's root folder or inside a `cmake/stm32cubemx/` subfolder; if you don't see it right away, use VS Code's file search (**Ctrl+P**) and type `.ld` to locate it quickly. Near the top of the file, you will find a `MEMORY` block similar to this:

```
MEMORY
{
  RAM    (xrw)    : ORIGIN = 0x20000000,   LENGTH = 320K
  FLASH    (rx)    : ORIGIN = 0x8000000,   LENGTH = 1024K
}
```

**In the bootloader project's linker script**, change the `FLASH` line so the bootloader can never grow past the 64 KB region we reserved for it:

```
FLASH    (rx)    : ORIGIN = 0x8000000,   LENGTH = 64K
```

**In the application project's linker script**, change the `FLASH` line so the application is linked to start where the bootloader's region ends, and occupies the rest of the chip:

```
FLASH    (rx)    : ORIGIN = 0x8010000,   LENGTH = 960K
```

> **Note:** CubeMX treats the linker script as generated output, not as your code - it does **not** live inside a `USER CODE` block. If you ever go back into CubeMX and click **GENERATE CODE** again after this point, it will silently overwrite this change, and you will need to reapply it.

> **Note:** Changing `ORIGIN` only tells the compiler and linker where the application's code *expects* to live - it does not, by itself, change where a programming tool writes the file. When you get to the flashing steps later in this lab, you will need to tell your flashing tool to write the application's `.bin` file starting at `0x08010000` instead of the default `0x08000000`. We will cover exactly how to do that when we reach the flashing instructions.

## 6. Set Up Python on Your Computer

The host-side application described in the Overview - the program that reads your compiled application `.bin` file and transmits it to the bootloader - will be written in Python. Python makes this convenient because it has a simple, well-supported library called `pyserial` for talking to serial (COM) ports, which is exactly what our USB CDC bootloader will look like to your laptop.

**On Windows:**
1. Go to **https://www.python.org/downloads/** and download the latest Python 3 installer.
2. Run the installer, and on the first screen, check the box labeled **Add python.exe to PATH** before clicking **Install Now**. This checkbox is easy to miss, but without it your terminal will not be able to find the `python` command.
3. Open a new terminal (PowerShell or Command Prompt) and confirm the installation by running:
   ```
   python --version
   ```

**On Linux:**
1. Most distributions already include Python 3. Confirm this by opening a terminal and running:
   ```
   python3 --version
   ```
2. If it is not installed, install it using your distribution's package manager, for example on Debian/Ubuntu-based systems:
   ```
   sudo apt update
   sudo apt install python3 python3-pip
   ```

**On both operating systems**, install the `pyserial` package, which provides the serial-port functionality we'll use in the next step:
```
pip install pyserial
```
(On Linux, use `pip3 install pyserial` if `pip` is not recognized.)

**Linking Python up with VS Code:**
1. Open the **Extensions** sidebar in VS Code (**Ctrl+Shift+X**) and install the official **Python** extension, published by Microsoft.
2. Open (or create) a folder for your host application and open it in VS Code.
3. Create a new file ending in `.py`, for example `firmware_sender.py`. VS Code will recognize it as a Python file and activate the extension's features for it.
4. Open the Command Palette (**Ctrl+Shift+P**), run **Python: Select Interpreter**, and choose the Python 3 installation you just set up. This tells VS Code which Python installation to use for running your script and for resolving the `pyserial` package you just installed.

## 7. Open a Serial Connection to the Bootloader

Once your bootloader project is flashed to the board and running (something we'll do later in this lab) and the board is connected to your laptop through its USB OTG FS port, your operating system will enumerate it as a new serial port, exactly as described in The USB Peripheral section.

- **On Windows**, open the **Device Manager**, expand **Ports (COM & LPT)**, and look for the new port that appears when the board is connected and running the bootloader (for example, `COM5`).
- **On Linux**, the device will typically appear as something like `/dev/ttyACM0`. You can confirm the name by running `ls /dev/tty*` before and after plugging in the board and comparing the two lists.

With `pyserial` installed, opening that port from Python is just a few lines:

```python
import serial

# Replace "COM5" with your port name (or "/dev/ttyACM0" on Linux)
ser = serial.Serial(port="COM5", baudrate=115200, timeout=1)
print(f"Connected to {ser.name}")
```

This is the same connection you will use later in the lab to actually send the bytes of your compiled application image to the bootloader.

## 8. Locate the Compiled Application Binary

The file your Python application needs to send is produced automatically every time you build the **application** project - you do not need to run any extra tools to create it. When you click **Build** in the STM32Cube panel (the same action you used in Lab 1), CubeMX's generated CMake project compiles your code into an `.elf` file as before, but it also automatically runs a post-build step that extracts a raw, binary copy of your program into a separate `.bin` file alongside it.

This distinction matters: the `.elf` file includes debugging information and symbol tables that are useful to your development tools, but are not part of the actual program. The `.bin` file is a raw, byte-for-byte image of exactly what should be written into flash - which is why it, and not the `.elf`, is the file your bootloader and Python application will work with.

After building the application project, look inside its `build/` folder (commonly `build/Debug/`, depending on which CMake preset you built) for a file structure similar to this:

```
Lab3_Application/
└── build/
    └── Debug/
        ├── Lab3_Application.elf   <-- debug build with symbols (not sent to the bootloader)
        ├── Lab3_Application.bin   <-- raw binary image (this is what gets sent)
        ├── Lab3_Application.hex   <-- ASCII-encoded image (alternate format, not used here)
        └── Lab3_Application.map   <-- memory map report from the linker
```

The full path to this `.bin` file is what your Python application will open in binary mode, read, and transmit byte by byte over the serial connection you opened in the previous step - exactly the process described all the way back in the Overview.

# Project Requirements

Everything up to this point has been scaffolding: both projects build, the linker scripts know about each other's flash region, and your laptop can open a serial connection to the board. What remains is the actual bootloader behavior described throughout the Background section. You will implement this yourself, in the `USER CODE` sections of the generated bootloader project and in your own Python script. The guidelines below describe *what* each piece must accomplish and *what to consider* while building it - they are intentionally not step-by-step instructions, since working out the details (and your reasoning for them) is the point of the lab.

Your completed lab should satisfy the following four required components.

## Requirement 1: Open the USB Port and Enter Update Mode

The bootloader must initialize the USB CDC stack so that the board enumerates as a virtual COM port, as described in The USB Peripheral section, and it must give the Python application a way to actually reach it with new firmware.

Think through the following as you design this piece:

- CubeMX already generated the initialization call for the USB device stack - your job is to decide what the bootloader *does* with that connection once it's active, not to re-implement enumeration.
- A bootloader that unconditionally waits forever for USB data would never be able to launch an already-installed application. Decide on a condition that tells the bootloader "a new image is coming" versus "just launch the existing application" - for example, a timeout window after reset or a flag left in memory by the application. (Requirement 4 below covers the button-driven side of this decision, so you don't need the button to do double duty here.)
- Figure out how your bootloader will know incoming data has *started* and, more importantly, when it has *ended*. The USB CDC driver will hand you bytes as they arrive (either through a receive callback or by polling a buffer) - you need a plan for recognizing the end of the transfer so the bootloader doesn't sit waiting for bytes that will never come. A length prefix, a sentinel value, and a timeout are all reasonable options; a solution that always assumes a fixed image size is not.

## Requirement 2: Overwrite the Application Firmware

Once bytes are arriving over USB, the bootloader must turn them into a correctly programmed application image at `0x08010000`, using the concepts from Overwriting the Application Flash.

Things you'll need to work out:

- The application's flash region must be erased before any of it is programmed. Determine how many flash pages that region spans (check the page size for this device family in the reference manual) and erase exactly those pages - no more, no fewer.
- Flash can only be programmed in aligned double-word (8-byte) chunks, but USB delivers bytes one (or a few) at a time. You will need a small RAM buffer that accumulates incoming bytes and triggers a flash program operation only once a full double word is ready.
- Decide what happens to the "leftover" bytes at the end of the file if the total size isn't an exact multiple of 8 - you still need to get every byte of the application into flash correctly.
- Remember to unlock the flash controller before erasing/programming and lock it again afterward, and make sure you are only ever erasing or programming the *application's* region, never the bootloader's own.
- Once every byte has been written, the bootloader has to actually hand off control: relocate the vector table with VTOR to the application's base address, reset the stack pointer using the application's initial MSP value, and branch to the application's reset handler - mirroring the startup sequence described in What Happens on Startup and Relocating the Interrupt Vector Table.

## Requirement 3: Transmit the Binary File from Python

Your Python script is the host-side half of this exchange. At minimum, it needs to:

- Open the serial port associated with the bootloader's CDC connection (the same one you tested in Open a Serial Connection to the Bootloader).
- Open the compiled application's `.bin` file in binary mode and transmit its contents over that connection.
- Communicate whatever "start" and "end" signaling your bootloader expects from Requirement 1 - for example, sending the file size up front if your bootloader is waiting for a length, or writing a defined sentinel sequence once the file has been fully sent.

Keep in mind that flash programming takes real time and USB transfers can arrive faster than the bootloader can consume them. If you send the entire file as one large write, consider whether your bootloader's receive buffer can keep up, and whether you need to send the data in smaller pieces with some form of pacing between them.

## Requirement 4: Transition to the Application via the User Button

The Nucleo board's onboard User button (the same blue button you used in Lab 1) must serve as the explicit control for leaving the bootloader and launching the application. While the bootloader is running and waiting (per Requirement 1), pressing this button should cause it to perform the same vector-table relocation, stack-pointer reset, and jump to the application's reset handler described in Requirement 2 - without requiring a new firmware image to be sent first.

Think through the following as you design this piece:

- Reuse the GPIO configuration CubeMX already generated for the User button in Lab 1 - you are just reading its state (or handling its interrupt) rather than toggling an LED with it this time. Either polling the pin or wiring up an EXTI interrupt is acceptable, as long as a press reliably triggers the transition.
- Pressing the button should only ever hand off control to the *existing* application image already sitting in flash - it must never itself erase or program anything. Writing a new image is strictly the job of Requirements 1 and 2; this requirement is only about handing off control afterward.
- Consider what should happen if the button is pressed before the application region has ever been programmed - jumping into erased flash (which reads back as `0xFF`) will fault. You don't need to build an elaborate recovery mechanism for this case, but you should think through how the board behaves and be able to explain the assumption you're making.
- This also gives you a convenient way to test Requirement 2 in isolation: run your Python transfer, then press the button to confirm the new application launches, rather than relying on an automatic jump the instant the transfer finishes.

## Success Criteria

At minimum, you should be able to: flash the bootloader, build the application project, trigger update mode, run your Python script against the correct `.bin` file, press the onboard User button, and then observe the application running on the board afterward (for example, via its LED or UART behavior from Lab 1) - without reprogramming the board through the ST-LINK a second time. If you modify the application code and rebuild it, a second run of your Python script followed by another button press should update the board to reflect those changes.

# Bonus Objectives

The requirements above are sufficient to complete the lab. If you'd like an extra challenge, pick one (or more) of the following. Each one builds directly on the pipeline you already have working, but asks you to question whether "it works" also means "it works correctly and safely" - which is a real concern for firmware updates delivered in the field.

### Bonus A: Encrypt the Firmware Image

Right now, anyone capturing the USB traffic between your laptop and the board could read out your entire application image in plain text - and worse, nothing stops a malicious party from sending their own unsigned binary to the bootloader. Modify your Python script to encrypt the `.bin` file with a symmetric cipher before transmitting it (a well-supported library such as Python's `cryptography` package is a reasonable choice), and modify the bootloader to decrypt each block before it is written to flash. Think about where the key lives (a bootloader built once to be deployed to many devices typically has it compiled in, which is itself a limitation worth noting in your writeup), and about how the cipher's block size interacts with the flash controller's double-word programming granularity.

### Bonus B: Verify the Firmware with a CRC

A transfer can be silently corrupted - a dropped byte, electrical noise, or a bug in your buffering logic could all leave the application's flash region in a bad state, and right now the bootloader would jump to it anyway. Have your Python script compute a checksum (CRC32 is a common choice) over the `.bin` file and send it to the bootloader along with the data. After programming finishes, have the bootloader recompute the checksum over what it just wrote to flash - either in software or using the microcontroller's built-in CRC peripheral - and only jump to the application if the two values match. Decide what the bootloader should do instead if they don't match (for example, refusing to launch and signaling the failure with an LED pattern).

### Bonus C: Make the Transfer Reliable

USB CDC over a cable is fairly reliable, but the lab's simple "just stream the bytes" protocol has no way to recover if something goes wrong mid-transfer. Design a small packet-based protocol instead: break the binary into fixed-size chunks, have the bootloader acknowledge (or reject) each chunk as it arrives, and have the Python script retry a chunk if it doesn't receive an acknowledgment. This mirrors the kind of flow control that real-world firmware update protocols rely on, and it's good practice for thinking about communication protocols as something more than "send bytes and hope."

