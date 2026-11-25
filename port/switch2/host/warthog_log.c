/*
WARTHOG LOG

See warthog_log.h. The log is the only thing this program leaves behind on
the console, so it is written with what the console has: svcGetSystemTick for
a timestamp (seconds since boot, which is all a launch log needs), stdio for
the line, fflush and fsync so a crash cannot take the last lines with it, and
printf for the screen so a player without an FTP server can read it too.

SPDX-License-Identifier: GPL-3.0-or-later
*/

#include "warthog_log.h"

#include <stdarg.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#include <switch.h>
#include <switch/arm/thread_context.h>

/* sdmc:/switch/warthog, as the release requirements name it */
#define WARTHOG_DIR "sdmc:/switch/warthog"
#define WARTHOG_LOG_DIR WARTHOG_DIR "/logs"
#define WARTHOG_LOG_PATH WARTHOG_LOG_DIR "/warthog.log"

/* the console's tick rate: 19.2 MHz, which is what svcGetSystemTick counts */
#define TICKS_PER_SECOND 19200000ull

static FILE *log_file;
extern const u8 __start__[];

/* Exception records avoid stdio and allocation, including integer formatting. */
static void raw_text(int fd, const char *text)
{
	const char *end = text;
	while (*end) end++;
	while (text < end)
	{
		ssize_t written = write(fd, text, end - text);
		if (written <= 0) return;
		text += written;
	}
}

static void raw_hex(int fd, u64 value)
{
	char buffer[19] = "0x";
	static const char digits[] = "0123456789abcdef";
	for (int i = 0; i < 16; i++)
		buffer[2 + i] = digits[(value >> ((15 - i) * 4)) & 15];
	buffer[18] = 0;
	raw_text(fd, buffer);
}

static void raw_field(int fd, const char *name, u64 value)
{
	raw_text(fd, name);
	raw_hex(fd, value);
	raw_text(fd, "\n");
}

static void raw_frame(int fd, unsigned number, u64 pc)
{
	char index[] = "FRAME #00: ";
	index[7] = '0' + number / 10;
	index[8] = '0' + number % 10;
	raw_text(fd, index);
	raw_hex(fd, pc);
	if (pc >= warthog_module_base())
	{
		raw_text(fd, " (warthog.elf+");
		raw_hex(fd, pc - warthog_module_base());
		raw_text(fd, ")");
	}
	raw_text(fd, "\n");
}

static void raw_frames(int fd, u64 fp, unsigned number)
{
	while (number < 32 && fp && !(fp & 15))
	{
		MemoryInfo info;
		u32 page;
		if (R_FAILED(svcQueryMemory(&info, &page, fp)) || !(info.perm & Perm_R) ||
			fp < info.addr || info.size < 16 || fp - info.addr > info.size - 16)
			break;
		const u64 *frame = (const u64 *)(uintptr_t)fp;
		u64 next = frame[0], lr = frame[1];
		raw_frame(fd, number++, lr);
		if (next <= fp) break;
		fp = next;
	}
}

void __libnx_exception_handler(ThreadExceptionDump *ctx)
{
	int fd = open(WARTHOG_LOG_PATH, O_WRONLY | O_CREAT | O_APPEND, 0666);
	if (fd < 0) return;
	raw_text(fd, "FAULT_KIND: CPU_EXCEPTION\n");
	raw_field(fd, "error_desc: ", ctx->error_desc);
	raw_field(fd, "pc: ", ctx->pc.x);
	raw_field(fd, "lr: ", ctx->lr.x);
	raw_field(fd, "sp: ", ctx->sp.x);
	raw_field(fd, "far: ", ctx->far.x);
	raw_field(fd, "MODULE_BASE: ", warthog_module_base());
	raw_frame(fd, 0, ctx->pc.x);
	raw_frames(fd, ctx->fp.x, 1);
	fsync(fd);
	close(fd);
}

void warthog_dk_debug_callback(void *user_data, const char *context, DkResult result, const char *message)
{
	(void)user_data;
	warthog_log_sync();
	int fd = open(WARTHOG_LOG_PATH, O_WRONLY | O_CREAT | O_APPEND, 0666);
	if (fd < 0) return;
	raw_text(fd, "FAULT_KIND: GPU_FAULT\ncontext: ");
	raw_text(fd, context ? context : "");
	raw_field(fd, "\nDkResult: ", result);
	raw_text(fd, "message: ");
	raw_text(fd, message ? message : "");
	raw_text(fd, "\n");
	raw_frames(fd, (u64)(uintptr_t)__builtin_frame_address(0), 0);
	fsync(fd);
	close(fd);
}

/* made with mkdir rather than fsdev, so the log does not depend on which
filesystem services the launch context granted: sdmc is already mounted by
libnx's startup */
static void make_directories(void)
{
	/* EEXIST is the ordinary answer here: the card keeps the folder between
	runs, and a second launch must not be an error */
	mkdir("sdmc:/switch", 0777);
	mkdir(WARTHOG_DIR, 0777);
	mkdir(WARTHOG_LOG_DIR, 0777);
}

bool warthog_log_open(void)
{
	make_directories();
	log_file = fopen(WARTHOG_LOG_PATH, "a");
	return log_file != NULL;
}

static void stamp(char *buffer, size_t size)
{
	u64 ticks = svcGetSystemTick();
	unsigned long long seconds = ticks / TICKS_PER_SECOND;
	unsigned long long milliseconds = (ticks % TICKS_PER_SECOND) * 1000 / TICKS_PER_SECOND;

	snprintf(buffer, size, "%llu.%03llus", seconds, milliseconds);
}

static void write_line(const char *level, const char *format, va_list arguments, bool to_console)
{
	char time_buffer[32];
	va_list to_file;
	va_list to_screen;

	stamp(time_buffer, sizeof(time_buffer));
	/* a va_list is consumed by the first vfprintf, so each destination gets
	its own copy */
	va_copy(to_file, arguments);
	va_copy(to_screen, arguments);
	if (log_file)
	{
		fprintf(log_file, "[%s] %-5s ", time_buffer, level);
		vfprintf(log_file, format, to_file);
		fputc('\n', log_file);
		fflush(log_file);
	}
	if (to_console)
	{
		printf("[%s] %-5s ", time_buffer, level);
		vprintf(format, to_screen);
		putchar('\n');
	}
	va_end(to_file);
	va_end(to_screen);
}

void warthog_log(const char *level, const char *format, ...)
{
	va_list arguments;

	va_start(arguments, format);
	write_line(level, format, arguments, false);
	va_end(arguments);
}

void warthog_log_console(const char *level, const char *format, ...)
{
	va_list arguments;

	va_start(arguments, format);
	write_line(level, format, arguments, true);
	va_end(arguments);
}

void warthog_log_sync(void)
{
	if (!log_file)
		return;
	fflush(log_file);
	fsync(fileno(log_file));
}

void warthog_log_close(void)
{
	if (!log_file)
		return;
	warthog_log_sync();
	fclose(log_file);
	log_file = NULL;
}
