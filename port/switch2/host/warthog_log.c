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
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#include <switch.h>

/* sdmc:/switch/warthog, as the release requirements name it */
#define WARTHOG_DIR "sdmc:/switch/warthog"
#define WARTHOG_LOG_DIR WARTHOG_DIR "/logs"
#define WARTHOG_LOG_PATH WARTHOG_LOG_DIR "/warthog.log"

/* the console's tick rate: 19.2 MHz, which is what svcGetSystemTick counts */
#define TICKS_PER_SECOND 19200000ull

static FILE *log_file;

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
