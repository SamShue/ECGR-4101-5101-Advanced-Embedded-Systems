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

### Flash Write Granularity

Although the USB peripheral hands the bootloader its data one byte at a time, the flash controller does not allow writes at that resolution. On the STM32L4 family used in this lab, flash memory must be programmed in aligned 64-bit (8-byte) chunks, referred to as double words. Attempting to program a single byte, or a chunk that isn't aligned to an 8-byte boundary, is not permitted by the hardware.

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

## 2. Create the Application Project

The application project is built the same way, but without any of the USB configuration above - in this lab, only the bootloader talks to the PC over USB. Repeat the same board-selector and default-peripheral steps as Lab 1, then name the project something like `Lab3_Application` in the Project Manager tab, keep **Advanced** structure and **CMake** toolchain, and generate the code.

At this point you should have two separate project folders on disk, each with its own `.ioc` file, `CMakeLists.txt`, and `Core/` folder - completely independent of one another, just like the bootloader and application are independent programs on the microcontroller.

## 3. Modify the Linker Scripts to Share Flash

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

## 4. Set Up Python on Your Computer

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

## 5. Open a Serial Connection to the Bootloader

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

## 6. Locate the Compiled Application Binary

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

