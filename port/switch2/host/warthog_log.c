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

/* kaiHEN attaches to the process as a debugger (InfoType_DebuggerAttached == 1),
   which makes libounce's __libnx_exception_entry skip __libnx_exception_handler
   unless __nx_exception_ignoredebug is non-zero. */
u32 __nx_exception_ignoredebug = 1;

/* Override libounce's 1 KiB weak exception stack so fault handlers never
   overflow into __nx_exceptiondump while formatting and syncing crash records. */
_Alignas(16) u8 __nx_exception_stack[0x8000];
u64 __nx_exception_stack_size = sizeof(__nx_exception_stack);

static FILE *log_file;
static int log_fd = -1;
static volatile int log_presenting;
static volatile int fault_logged;
extern const u8 __start__[];

static int fault_open_fd(bool *opened)
{
	if (log_fd >= 0)
	{
		*opened = false;
		return log_fd;
	}
	*opened = true;
	return open(WARTHOG_LOG_PATH, O_WRONLY | O_CREAT | O_APPEND, 0666);
}

static void fault_finish_fd(int fd, bool opened)
{
	fsync(fd);
	if (opened)
		close(fd);
}

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
	bool opened = false;
	fault_logged = 1;
	int fd = fault_open_fd(&opened);
	if (fd < 0) return;
	if (!log_file) raw_text(fd, "--- launch ---\n");
	raw_text(fd, "FAULT_KIND: CPU_EXCEPTION\n");
	raw_field(fd, "error_desc: ", ctx->error_desc);
	raw_field(fd, "pc: ", ctx->pc.x);
	raw_field(fd, "lr: ", ctx->lr.x);
	raw_field(fd, "sp: ", ctx->sp.x);
	raw_field(fd, "far: ", ctx->far.x);
	raw_field(fd, "MODULE_BASE: ", warthog_module_base());
	raw_frame(fd, 0, ctx->pc.x);
	raw_frames(fd, ctx->fp.x, 1);
	fault_finish_fd(fd, opened);
}

void warthog_dk_debug_callback(void *user_data, const char *context, DkResult result, const char *message)
{
	bool opened = false;
	(void)user_data;
	if (result == DkResult_Success)
		return;
	fault_logged = 1;
	warthog_log_sync();
	int fd = fault_open_fd(&opened);
	if (fd < 0) return;
	raw_text(fd, "FAULT_KIND: GPU_FAULT\ncontext: ");
	raw_text(fd, context ? context : "");
	raw_field(fd, "\nDkResult: ", result);
	raw_text(fd, "message: ");
	raw_text(fd, message ? message : "");
	raw_text(fd, "\n");
	raw_field(fd, "MODULE_BASE: ", warthog_module_base());
	raw_frames(fd, (u64)(uintptr_t)__builtin_frame_address(0), 0);
	fault_finish_fd(fd, opened);
}

void NX_NORETURN __real_diagAbortWithResult(Result res);
void NX_NORETURN __wrap_diagAbortWithResult(Result res);
void NX_NORETURN __wrap_diagAbortWithResult(Result res)
{
	bool opened = false;
	u64 lr = (u64)(uintptr_t)__builtin_return_address(0);
	fault_logged = 1;
	warthog_log_sync();
	int fd = fault_open_fd(&opened);
	if (fd >= 0)
	{
		raw_text(fd, "FAULT_KIND: DIAG_ABORT\n");
		raw_field(fd, "result: ", res);
		raw_field(fd, "module: ", R_MODULE(res));
		raw_field(fd, "description: ", R_DESCRIPTION(res));
		raw_field(fd, "lr: ", lr);
		raw_field(fd, "MODULE_BASE: ", warthog_module_base());
		raw_frame(fd, 0, lr);
		raw_frames(fd, (u64)(uintptr_t)__builtin_frame_address(0), 1);
		fault_finish_fd(fd, opened);
	}
	__real_diagAbortWithResult(res);
}

void __real_abort(void) __attribute__((noreturn));
void __wrap_abort(void) __attribute__((noreturn));
void __wrap_abort(void)
{
	bool opened = false;
	u64 lr = (u64)(uintptr_t)__builtin_return_address(0);
	fault_logged = 1;
	warthog_log_sync();
	int fd = fault_open_fd(&opened);
	if (fd >= 0)
	{
		raw_text(fd, "FAULT_KIND: C_ABORT\n");
		raw_field(fd, "lr: ", lr);
		raw_field(fd, "MODULE_BASE: ", warthog_module_base());
		raw_frame(fd, 0, lr);
		raw_frames(fd, (u64)(uintptr_t)__builtin_frame_address(0), 1);
		fault_finish_fd(fd, opened);
	}
	__real_abort();
}

void NX_NORETURN __real_svcBreak(u32 breakReason, uintptr_t address, uintptr_t size);
void NX_NORETURN __wrap_svcBreak(u32 breakReason, uintptr_t address, uintptr_t size);
void NX_NORETURN __wrap_svcBreak(u32 breakReason, uintptr_t address, uintptr_t size)
{
	if (!fault_logged)
	{
		bool opened = false;
		u64 lr = (u64)(uintptr_t)__builtin_return_address(0);
		fault_logged = 1;
		warthog_log_sync();
		int fd = fault_open_fd(&opened);
		if (fd >= 0)
		{
			raw_text(fd, "FAULT_KIND: DIAG_ABORT\n");
			raw_field(fd, "result: ", (size >= 4 && address) ? *(const u32 *)address : breakReason);
			raw_field(fd, "lr: ", lr);
			raw_field(fd, "MODULE_BASE: ", warthog_module_base());
			raw_frame(fd, 0, lr);
			raw_frames(fd, (u64)(uintptr_t)__builtin_frame_address(0), 1);
			fault_finish_fd(fd, opened);
		}
	}
	__real_svcBreak(breakReason, address, size);
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
	log_fd = log_file ? fileno(log_file) : -1;
	log_presenting = 0;
	return log_file != NULL;
}

void warthog_log_set_presenting(bool presenting)
{
	__atomic_store_n(&log_presenting, presenting ? 1 : 0, __ATOMIC_RELAXED);
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
		if (!__atomic_load_n(&log_presenting, __ATOMIC_RELAXED) ||
			to_console || !level || strcmp(level, "INFO") != 0)
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
	log_fd = -1;
	log_presenting = 0;
	fclose(log_file);
	log_file = NULL;
}
