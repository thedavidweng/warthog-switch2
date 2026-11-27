/*
WARTHOG LOG

The startup program's log, and the file a crash report is read from
(ticket #3). Ticket #4 extends this: it adds the exception handler's CPU
exception records and Drako3D's GPU fault records, which is why the file is
opened once, written a line at a time, and fsynced before the program
returns.

The log lives at sdmc:/switch/warthog/logs/warthog.log, which is what the
release requirements and the hardware workflow name. Directories are made
when they are missing, and a log that cannot be written does not stop the
program: the console's screen says so instead.

SPDX-License-Identifier: GPL-3.0-or-later
*/

#pragma once

#include <stdbool.h>
#include <stdint.h>
#include <drako3d.h>

/* __start__ is an absolute linker symbol; take its address PC-relatively so
 * PIE relocation does not leave an absolute zero in the GOT. */
static inline uintptr_t warthog_module_base(void)
{
	uintptr_t base;
	__asm__("adrp %0, __start__\n\tadd %0, %0, :lo12:__start__" : "=r"(base));
	return base;
}

/* Opens the log, making sdmc:/switch/warthog/logs as needed. False when the
card is not mounted or the file cannot be written. */
bool warthog_log_open(void);

/* One line, with a timestamp and a level ("INFO", "WARN", "ERROR"). */
void warthog_log(const char *level, const char *format, ...);

/* The console's screen as well as the file: what a player without an FTP
server can read. */
void warthog_log_console(const char *level, const char *format, ...);

/* Writes what is buffered to the card and makes it durable. */
void warthog_log_sync(void);

/* Syncs and closes. Safe to call when nothing was opened. */
void warthog_log_close(void);

/* Switches INFO buffering once steady-state frame presentation begins. */
void warthog_log_set_presenting(bool presenting);

void warthog_dk_debug_callback(void *user_data, const char *context, DkResult result, const char *message);
