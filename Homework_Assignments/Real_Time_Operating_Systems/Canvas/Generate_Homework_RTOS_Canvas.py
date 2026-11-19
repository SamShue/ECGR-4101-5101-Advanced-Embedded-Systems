#!/usr/bin/env python3
"""
Build the Canvas-friendly HTML version of the "Real-Time Operating Systems"
homework.

Produces the same problems as ../LaTeX/homework_rtos.tex, as a single
self-contained HTML file per variant (student / instructor key). The
priority-inversion timeline used in Problem 5 is drawn with matplotlib and
embedded as a base64 data URI, so the HTML can be pasted straight into
Canvas's Rich Content Editor "</> HTML Editor" view with no separate file
upload. The same PNG is also written to ./build/images/.

Usage:
    python Generate_Homework_RTOS_Canvas.py
"""

import base64
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
IMAGES_DIR = BUILD / "images"
DIAGRAM_PATH = IMAGES_DIR / "priority_inversion.png"

sys.dont_write_bytecode = True


def draw_priority_inversion(path: Path) -> None:
    """Timeline: TaskL acquires a mutex, TaskH becomes ready and blocks on
    that same mutex, and TaskM (which never touches the mutex) preempts
    TaskL in the meantime, delaying TaskH even though nothing of higher
    priority than TaskH is actually running."""
    fig, ax = plt.subplots(figsize=(9, 3.4), dpi=150)
    ax.set_xlim(-1.4, 6.2)
    ax.set_ylim(0.3, 4.2)
    ax.axis("off")

    rows = {"TaskH (high)": 3, "TaskM (medium)": 2, "TaskL (low)": 1}
    for label, y in rows.items():
        ax.text(-1.5, y, label, ha="right", va="center", fontsize=11, family="serif")

    for x in range(0, 6):
        ax.plot([x, x], [0.5, 3.9], color="0.8", lw=1, ls=":", zorder=0)
    ax.annotate("", xy=(6.1, 0.5), xytext=(-1.4, 0.5),
                arrowprops=dict(arrowstyle="->", lw=1.4, color="black"))
    ax.text(6.15, 0.5, "time", ha="left", va="center", fontsize=10, family="serif")

    bar = dict(height=0.35, lw=0)
    # TaskL runs and acquires the mutex at t0.
    ax.add_patch(Rectangle((0, 1 - bar["height"] / 2), 1, bar["height"], fc="orange"))
    # TaskH becomes ready at t1 but blocks waiting on the mutex until t4.
    ax.add_patch(Rectangle((1, 3 - bar["height"] / 2), 3, bar["height"], fc="#f8b4b4"))
    # TaskM becomes ready at t1 and, having no interest in the mutex,
    # immediately preempts TaskL.
    ax.add_patch(Rectangle((1, 2 - bar["height"] / 2), 2, bar["height"], fc="blue"))
    # TaskL resumes once TaskM finishes, then releases the mutex at t4.
    ax.add_patch(Rectangle((3, 1 - bar["height"] / 2), 1, bar["height"], fc="orange"))
    # TaskH finally runs starting at t4.
    ax.add_patch(Rectangle((4, 3 - bar["height"] / 2), 1.6, bar["height"], fc="red"))

    ax.text(1.0, 3.55, "t1: TaskH ready,\nblocks on mutex",
            ha="left", va="bottom", fontsize=8.5, family="serif")
    ax.text(1.6, 2.5, "t1\u2013t3: TaskM preempts\nTaskL (mutex still held)",
            ha="left", va="center", fontsize=8.5, family="serif")
    ax.text(4.0, 3.55, "t4: mutex released,\nTaskH finally runs",
            ha="left", va="bottom", fontsize=8.5, family="serif")

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def img_data_uri(path: Path) -> str:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{data}"


def question(text: str, space_em: int, key_text: str, key: bool) -> str:
    """One lettered sub-question: prompt, ruled answer space, and (in key
    mode) the instructor's answer in red."""
    space = (f'<div style="height:{space_em}em; border-top:1px solid #000; '
             f'margin:14px 0 4px 0;"></div>')
    key_html = (f'<p style="color:#b00000;"><strong>Key:</strong> {key_text}</p>'
                if key else "")
    return f"<li>{text}\n{space}\n{key_html}</li>"


def lettered_list(items) -> str:
    return '<ol type="a">\n' + "\n".join(items) + "\n</ol>"


CODE_BLOCK = """
<pre style="background:#f4f4f4; padding:10px; border:1px solid #ccc;"><code>void motorStepTask(void) {
  while (getTick() - lastStepTime &lt; 500);   // busy-wait right here
  stepMotorForward();
  lastStepTime = getTick();
}

void stopButtonTask(void) {
  if (stopButtonPressed())
    haltMotor();
}

while (1) {
  motorStepTask();
  stopButtonTask();
}
</code></pre>
"""


def build_body(diagram_uri: str, key: bool) -> str:
    p1 = [
        question(
            "Explain why a quick press-and-release of the stop button is "
            "likely to go completely undetected if it happens while "
            "<code>motorStepTask()</code> is busy-waiting, even though "
            "<code>stopButtonTask()</code> is called again and again inside "
            "the same <code>while(1)</code> loop.",
            4,
            "While <code>motorStepTask()</code> is stuck in its busy-wait "
            "loop, control never returns to the <code>while(1)</code> loop, "
            "so <code>stopButtonTask()</code> cannot run at all for up to "
            "500&nbsp;ms at a time. If the operator presses and releases the "
            "button entirely within that window, the input pin has already "
            "returned to its unpressed level by the time "
            "<code>stopButtonTask()</code> finally checks it, so the press "
            "is never seen at all &mdash; for a safety-related function like "
            "this, that is a serious problem, not just an inconvenience.", key),
        question(
            "Suppose <code>motorStepTask()</code> is rewritten so that it "
            "checks the elapsed time and returns immediately if 500&nbsp;ms "
            "have not yet passed, stepping the motor and returning only once "
            "they have &mdash; without ever busy-waiting inside the function. "
            "What is this general style of scheduling called, and what does "
            "it mean, conceptually, for a task to &ldquo;cooperate&rdquo; "
            "with the rest of the system?",
            4,
            "This is cooperative scheduling. &ldquo;Cooperating&rdquo; means "
            "each task is written so that it voluntarily and quickly gives "
            "up the CPU (by returning or otherwise yielding) rather than "
            "holding onto it, trusting that the other tasks will do the "
            "same.", key),
        question(
            "This rewritten <code>motorStepTask()</code> still needs a "
            "variable like <code>lastStepTime</code> to remember the tick "
            "count from the last time it ran. Explain why this value cannot "
            "simply be a local variable declared inside "
            "<code>motorStepTask()</code>, and what this implies about what "
            "a &ldquo;thread&rdquo; running under an RTOS needs to have of "
            "its own that a plain function call does not.",
            5,
            "A local variable's storage (the function's stack frame) is "
            "destroyed the moment the function returns, so a local "
            "<code>lastStepTime</code> would be reset to garbage every "
            "single call instead of remembering the previous step time. A "
            "thread needs its own persistent storage &mdash; in particular, "
            "its own stack and saved execution context &mdash; that survives "
            "across the many separate &ldquo;turns&rdquo; it is given, which "
            "is exactly what an RTOS sets up for each thread it creates.", key),
        question(
            "Now suppose the stop button is instead wired to trigger a "
            "hardware interrupt the instant it is pressed, and the interrupt "
            "handler itself halts the motor (rather than the main loop "
            "periodically asking &ldquo;has the button been pressed?&rdquo;). "
            "What general term describes this style of handling the "
            "stop-button task compared to the cooperative version in part "
            "(b), and why does it no longer matter how long "
            "<code>motorStepTask()</code> takes between checks, or how brief "
            "the button press is?",
            4,
            "This is preemptive scheduling/servicing: the button press "
            "itself forcibly interrupts whatever is currently running, "
            "rather than waiting for that code to voluntarily check whether "
            "the button is pressed. Because the hardware guarantees the "
            "handler runs immediately on the press, it no longer matters how "
            "long <code>motorStepTask()</code> takes between checks, nor "
            "whether the press-and-release happens faster than the main "
            "loop could have polled for it.", key),
        question(
            "As an application grows to include many tasks with very "
            "different timing requirements (some periodic, some triggered "
            "by external events, some with strict deadlines), explain why "
            "hand-coding all of their interactions inside one big "
            "<code>while(1)</code> loop &mdash; even a carefully cooperative "
            "one &mdash; eventually becomes impractical. What part of an "
            "RTOS exists specifically to take over this responsibility?",
            5,
            "With only a handful of tasks it is feasible for a programmer to "
            "reason about every possible ordering and timing interaction by "
            "hand, but as the number of tasks grows, the number of possible "
            "interleavings and worst-case delays grows far faster, making it "
            "increasingly difficult (and eventually impossible in practice) "
            "to guarantee by inspection that no task will miss a deadline or "
            "block another for too long. The scheduler is the part of an "
            "RTOS that takes over the job of deciding, at every moment, "
            "which ready task should run next.", key),
    ]

    p2 = [
        question(
            "In your own words, define what a &ldquo;thread&rdquo; is in "
            "the context of an RTOS running on a single-core "
            "microcontroller.",
            3,
            "A thread is an independent stream of execution &mdash; "
            "conceptually, just a function with its own associated state "
            "&mdash; that the scheduler can run, pause, and resume "
            "independently of any other thread, giving the illusion that it "
            "executes concurrently with the rest of the application.", key),
        question(
            "A single CPU core can only execute instructions from one "
            "thread at any given instant, yet several threads appear to "
            "make progress at the same time. Explain the mechanism that "
            "creates this illusion, and name the specific action the OS "
            "performs to stop running one thread and begin running another.",
            4,
            "The illusion is created by rapidly switching which thread's "
            "instructions the CPU is executing, giving each one a short "
            "slice of time so that, to an outside observer, all of them "
            "seem to progress at once even though only one is ever truly "
            "running at a time. The specific action that swaps the CPU from "
            "one thread's state to another's is called a context switch.", key),
        question(
            "During a context switch, the RTOS must save and later restore "
            "each thread's execution state in memory dedicated to that "
            "specific thread. List at least three distinct pieces of "
            "information that must be saved, and explain why each thread "
            "needs its own separate block of memory to hold this "
            "information rather than sharing one block among all threads.",
            5,
            "At minimum, the CPU registers (including the program counter "
            "and general-purpose registers), the thread's own stack "
            "pointer, and the contents of that thread's own stack (its "
            "local variables and call history) all need to be preserved. "
            "Each thread needs its own block of memory because its "
            "registers and stack contents will, in general, be completely "
            "different from every other thread's at the moment it gets "
            "paused &mdash; overwriting them with another thread's values "
            "(or sharing one stack among threads) would destroy the paused "
            "thread's ability to resume correctly later.", key),
        question(
            "Describe, in your own words, the difference between "
            "round-robin scheduling, cooperative scheduling, and preemptive "
            "priority-based scheduling. For each one, state specifically "
            "what determines when a currently running thread stops running "
            "and a different thread starts.",
            6,
            "Round-robin: every ready thread is given an equal, fixed slice "
            "of time in turn, and a thread stops running simply because its "
            "time slice has expired, regardless of priority. Cooperative: a "
            "thread keeps running until it voluntarily gives up the CPU (by "
            "blocking, finishing, or explicitly yielding) &mdash; the "
            "scheduler never forcibly interrupts it. Preemptive "
            "priority-based: a running thread is forcibly stopped the "
            "instant a higher-priority thread becomes ready to run, "
            "regardless of whether the running thread was willing to give "
            "up the CPU or not.", key),
        question(
            "Suppose a low-priority thread enters an infinite loop that "
            "never calls any blocking function and never returns. Under a "
            "preemptive scheduler, explain what hardware mechanism still "
            "allows a higher-priority thread to get CPU time, and what "
            "would happen to the rest of the system if that hardware "
            "mechanism did not exist.",
            5,
            "A periodic hardware timer interrupt (separate from anything "
            "the misbehaving thread does) forces control away from the "
            "currently running thread at a fixed interval, giving the "
            "scheduler a chance to run and switch to a higher-priority "
            "ready thread. Without this mechanism, a thread that never "
            "voluntarily returns control would run forever, permanently "
            "starving every other thread in the system &mdash; no "
            "higher-priority thread, no matter how urgent, would ever get "
            "to run again.", key),
        question(
            "Every RTOS includes a special, built-in &ldquo;idle&rdquo; "
            "thread that is always ready to run and is assigned the lowest "
            "possible priority. Explain why an OS needs a thread like this "
            "instead of simply leaving the CPU with nothing scheduled "
            "whenever every other thread is blocked or suspended.",
            4,
            "The scheduler always needs some thread to hand the CPU to; if "
            "every application thread happens to be blocked or suspended at "
            "the same moment, there still has to be something for the "
            "processor to execute. The idle thread exists purely to fill "
            "this need (and is commonly also used to perform low-priority "
            "housekeeping, such as freeing resources of deleted threads) "
            "whenever no other thread is ready.", key),
    ]

    p3 = [
        question(
            "Explain what specifically distinguishes a &ldquo;real-time&rdquo; "
            "operating system from a general-purpose operating system, in "
            "terms of what guarantee it must provide and over what kind of "
            "time scale that guarantee is expected to hold.",
            4,
            "A real-time OS must guarantee that certain operations complete "
            "within a specified time constraint, called a deadline, which is "
            "typically on the order of milliseconds or even microseconds. A "
            "general-purpose OS has no such guarantee &mdash; it may respond "
            "quickly most of the time, but nothing in its design promises an "
            "upper bound on how long a response might take.", key),
        question(
            "Desktop operating systems rely heavily on virtual memory, "
            "paging, and swapping data out to disk. Explain, in your own "
            "words, why page faults and disk-based swapping are "
            "fundamentally difficult to reconcile with meeting a hard "
            "real-time deadline, even though this behavior works perfectly "
            "well for everyday desktop applications.",
            5,
            "Servicing a page fault means pausing the running program, "
            "locating the needed data (possibly on a disk), and loading it "
            "back into RAM before execution can continue &mdash; and the "
            "amount of time this takes is not fixed; it depends on where "
            "the data physically lives and on whatever else the storage "
            "device happens to be doing at that moment. A system that "
            "cannot guarantee how long this pause will last cannot "
            "guarantee that any deadline will be met, which is why "
            "real-time systems generally avoid paging and swapping even "
            "though ordinary desktop use rarely notices the resulting "
            "delay.", key),
        question(
            "Explain why a thread's priority (used by the scheduler to "
            "decide which ready thread runs next) is a fundamentally "
            "different concept from the priority assigned to a hardware "
            "interrupt, and give an example of a situation where this "
            "distinction actually matters &mdash; that is, a moment when a "
            "high-priority thread is ready to run but is not actually the "
            "thing executing on the CPU.",
            5,
            "Thread priority only governs competition among threads for the "
            "CPU once an interrupt has finished and the scheduler is "
            "choosing which thread to resume; it says nothing about what "
            "happens while an interrupt service routine itself is "
            "executing. For example, while any interrupt service routine is "
            "running (even one unrelated to a given high-priority thread), "
            "that thread is formally &ldquo;ready&rdquo; and may even be the "
            "highest priority ready thread in the whole system, yet it is "
            "still not the thing actually executing on the CPU until the "
            "ISR finishes and the scheduler runs.", key),
    ]

    p4 = [
        question(
            "Describe, in your own words, the two mistakes that must both "
            "be avoided for this producer/consumer arrangement to work "
            "correctly: one mistake the producer could make, and one "
            "mistake the consumer could make.",
            4,
            "The producer must not keep writing new data into the buffer "
            "once it is completely full (overwriting data the consumer has "
            "not yet read). The consumer must not try to read data out of "
            "the buffer once it is completely empty (reading stale or "
            "meaningless data that was never actually produced).", key),
        question(
            "Explain how a message queue, as provided by an RTOS, prevents "
            "both of those mistakes automatically, including what "
            "specifically happens to a thread that tries to add an item to "
            "a full queue, or to a thread that tries to remove an item from "
            "an empty queue.",
            5,
            "A message queue keeps track of how many items it currently "
            "holds and enforces its fixed capacity. A thread that tries to "
            "add an item to a full queue is placed in the blocked state "
            "until at least one item is removed by some other thread, and "
            "likewise a thread that tries to remove an item from an empty "
            "queue is placed in the blocked state until some other thread "
            "adds a new item &mdash; in both cases the OS kernel "
            "automatically pauses the offending thread rather than letting "
            "it proceed incorrectly.", key),
        question(
            "A semaphore can conceptually be thought of as nothing more "
            "than a variable (a boolean flag, or a counter) that threads "
            "check before proceeding. Explain why a plain, unprotected "
            "global variable cannot safely serve as a semaphore in a "
            "multithreaded system, and what role the OS kernel has to play "
            "in order to make this safe.",
            5,
            "There is no guarantee that checking a variable's value and "
            "then updating it happens as a single, uninterruptible step; a "
            "thread could be preempted in between checking and updating the "
            "variable, allowing another thread to also &ldquo;succeed&rdquo; "
            "at the same check before the first thread finishes updating "
            "it, letting two threads believe they both safely acquired the "
            "same resource. The OS kernel must perform the check-and-update "
            "as an atomic operation (for example, by disabling interrupts "
            "or otherwise preventing a context switch during that brief "
            "step) so that only one thread can ever succeed at acquiring "
            "the semaphore at a time.", key),
        question(
            "Explain the conceptual difference between a binary semaphore "
            "and a counting semaphore. Then describe one resource-sharing "
            "scenario of your own (not one used in this course) where a "
            "counting semaphore with an initial count greater than one "
            "would be the appropriate choice.",
            5,
            "A binary semaphore can only be in one of two states (taken or "
            "available), so it is suited to situations where exactly one "
            "thread may hold the resource at a time. A counting semaphore "
            "starts with some initial count greater than one and is "
            "decremented every time it is acquired and incremented every "
            "time it is released, so up to that many threads may hold "
            "instances of the resource simultaneously, and a thread only "
            "blocks once the count reaches zero. Any reasonable example is "
            "acceptable, e.g., a pool of several identical hardware DMA "
            "channels, a fixed number of reusable network connection "
            "buffers, or a small pool of identical sensor-reading "
            "structures, where a counting semaphore initialized to the "
            "number of available resources in the pool lets that many "
            "threads proceed at once.", key),
    ]

    p5 = [
        question(
            "Using the diagram, describe in your own words the sequence of "
            "events that causes the high-priority <code>TaskH</code> to sit "
            "blocked for so long, even though no thread with higher "
            "priority than <code>TaskH</code> is running anywhere in the "
            "system during that time. This general problem is known as "
            "priority inversion.",
            6,
            "<code>TaskL</code> acquires the mutex first. Shortly after, "
            "<code>TaskH</code> becomes ready and tries to acquire that "
            "same mutex, but since <code>TaskL</code> is still holding it, "
            "<code>TaskH</code> must block and wait. Meanwhile, "
            "<code>TaskM</code> becomes ready at around the same time and, "
            "having higher priority than <code>TaskL</code> (and no "
            "interest in the mutex at all), immediately preempts "
            "<code>TaskL</code> and runs to completion. Only once "
            "<code>TaskM</code> finishes does <code>TaskL</code> resume, "
            "finish its critical section, and finally release the mutex "
            "&mdash; at which point <code>TaskH</code> can finally acquire "
            "it and run. The net effect is that the medium-priority "
            "<code>TaskM</code>, despite never touching the shared "
            "resource, has effectively delayed the highest-priority thread "
            "in the system.", key),
        question(
            "Explain the conceptual difference between a mutex and a "
            "semaphore in terms of ownership: who is expected to acquire "
            "and release each one.",
            4,
            "A mutex is meant to always be acquired and later released by "
            "that same thread, since it exists purely to protect a shared "
            "resource during the period that one specific thread is using "
            "it. A semaphore has no such ownership expectation &mdash; it "
            "is entirely normal, and often by design, for one thread (or "
            "even an interrupt handler) to release a semaphore that a "
            "completely different thread later acquires, since semaphores "
            "are also used to signal that some event has occurred rather "
            "than only to protect a resource.", key),
        question(
            "Describe the general strategy (sometimes called priority "
            "inheritance) that many RTOSes use to minimize priority "
            "inversion. Explain, specifically, how temporarily changing the "
            "priority of one of the three threads in the diagram above "
            "would have prevented <code>TaskM</code> from delaying "
            "<code>TaskL</code> (and therefore <code>TaskH</code>) for as "
            "long as it did.",
            6,
            "When a higher-priority thread is found to be blocked waiting "
            "on a mutex that a lower-priority thread currently holds, the "
            "OS temporarily raises the priority of the mutex-holding thread "
            "to match the priority of the thread waiting on it. In the "
            "diagram, this means that as soon as <code>TaskH</code> blocks "
            "waiting on the mutex held by <code>TaskL</code>, "
            "<code>TaskL</code>'s priority would be temporarily raised to "
            "<code>TaskH</code>'s level. <code>TaskM</code> would then no "
            "longer be able to preempt <code>TaskL</code>, since "
            "<code>TaskL</code> now effectively outranks it, so "
            "<code>TaskL</code> would finish its critical section and "
            "release the mutex much sooner, letting <code>TaskH</code> run "
            "far earlier &mdash; and only after the mutex is released would "
            "<code>TaskL</code>'s priority drop back down, finally allowing "
            "<code>TaskM</code> to run.", key),
        question(
            "Suppose priority inheritance were not implemented at all in "
            "this example. Explain, in the worst case, how additional "
            "medium-priority threads could prevent the high-priority "
            "<code>TaskH</code> from running for an arbitrarily long, "
            "essentially unbounded amount of time &mdash; a phenomenon "
            "sometimes called unbounded priority inversion.",
            5,
            "Without priority inheritance, <code>TaskL</code>'s priority "
            "never changes while it holds the mutex, so it remains just as "
            "vulnerable to being preempted by any medium-priority thread as "
            "it was before acquiring the mutex. If new medium-priority "
            "threads keep becoming ready one after another, each one will "
            "preempt <code>TaskL</code> in turn before it can finish its "
            "critical section and release the mutex, and <code>TaskH</code> "
            "remains blocked the entire time. Since there is no limit on "
            "how many such medium-priority threads could keep arriving, "
            "there is also no bound on how long <code>TaskH</code> &mdash; "
            "the highest-priority thread in the system &mdash; could be "
            "forced to wait.", key),
    ]

    alt = ("Priority-inversion timeline: TaskL acquires a shared mutex at t0. "
           "TaskH becomes ready at t1 and blocks waiting on that same mutex. "
           "TaskM also becomes ready at t1 and, having no interest in the "
           "mutex, immediately preempts TaskL until t3. TaskL then resumes, "
           "finishes, and releases the mutex at t4, finally letting TaskH run.")

    return f"""
<h2>Problem 1: From Busy-Waiting to a Scheduler</h2>
<p>Consider an embedded application controlling a small conveyor belt.
Among other things, it needs to pulse a stepper motor forward once every
500&nbsp;ms to keep the belt moving, and it also needs to react as quickly
as possible whenever an operator presses a momentary safety-stop button
wired to a digital input pin. A first attempt at this is written as:</p>
{CODE_BLOCK}
{lettered_list(p1)}

<h2>Problem 2: Threads, Context Switches, and Scheduling Policies</h2>
{lettered_list(p2)}

<h2>Problem 3: Real-Time Behavior and Determinism</h2>
{lettered_list(p3)}

<h2>Problem 4: Synchronization with Queues and Semaphores</h2>
<p>Suppose one thread continually produces data (for example, samples read
from a sensor) and a second thread continually consumes that data (for
example, computing a running average) by sharing a common buffer between
them.</p>
{lettered_list(p4)}

<h2>Problem 5: Mutexes and Priority Inversion</h2>
<p>The timeline below shows three threads of different priority:
<code>TaskH</code> (high priority), <code>TaskM</code> (medium priority),
and <code>TaskL</code> (low priority). <code>TaskL</code> and
<code>TaskH</code> both need to access the same shared resource and
therefore both acquire the same mutex before using it; <code>TaskM</code>
never touches that resource or that mutex at all.</p>
<p style="text-align:center;"><img src="{diagram_uri}" alt="{alt}"
  style="max-width:100%;"></p>
{lettered_list(p5)}
"""


def build_html(diagram_uri: str, key: bool) -> str:
    suffix = " -- Instructor Key" if key else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Homework: Real-Time Operating Systems{suffix}</title>
</head>
<body style="font-family: Georgia, 'Times New Roman', serif; max-width:900px; margin:0 auto;">
<h1>ECGR 4101/5101 -- Advanced Embedded Systems</h1>
<h2 style="margin-top:-10px;">Homework: Real-Time Operating Systems{suffix}</h2>
<p>This homework is about the concepts behind real-time operating systems,
not the syntax of any particular one. You will <strong>not</strong> be asked
to recall specific API function names, structs, or configuration macros from
FreeRTOS, CMSIS-RTOS2, or any other RTOS. Any pseudocode below uses plain,
made-up function names. Answer every question in your own words, in a
sentence or two unless a question says otherwise, based on what we covered
in class.</p>
{build_body(diagram_uri, key)}
</body>
</html>
"""


def main() -> int:
    BUILD.mkdir(parents=True, exist_ok=True)
    draw_priority_inversion(DIAGRAM_PATH)
    uri = img_data_uri(DIAGRAM_PATH)

    student = BUILD / "homework_rtos_student.html"
    key = BUILD / "homework_rtos_key.html"
    student.write_text(build_html(uri, key=False), encoding="utf-8")
    key.write_text(build_html(uri, key=True), encoding="utf-8")

    print(f"Wrote {student}")
    print(f"Wrote {key}")
    print(f"Wrote reference image to {DIAGRAM_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
