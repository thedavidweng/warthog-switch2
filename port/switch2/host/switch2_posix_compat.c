#include <switch.h>
#include <errno.h>
#include <pthread.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

static pthread_mutex_t seek_lock = PTHREAD_MUTEX_INITIALIZER;

static ssize_t positioned_io(int fd, void *buffer, size_t count, off_t offset, int write_mode)
{
	ssize_t result = -1;
	int saved_errno;
	pthread_mutex_lock(&seek_lock);
	off_t previous = lseek(fd, 0, SEEK_CUR);
	if (previous != (off_t)-1 && lseek(fd, offset, SEEK_SET) != (off_t)-1)
	{
		result = write_mode ? write(fd, buffer, count) : read(fd, buffer, count);
		saved_errno = errno;
		if (lseek(fd, previous, SEEK_SET) == (off_t)-1)
			result = -1;
		else
			errno = saved_errno;
	}
	pthread_mutex_unlock(&seek_lock);
	return result;
}

ssize_t pread(int fd, void *buffer, size_t count, off_t offset)
{
	return positioned_io(fd, buffer, count, offset, 0);
}

ssize_t pwrite(int fd, const void *buffer, size_t count, off_t offset)
{
	return positioned_io(fd, (void *)buffer, count, offset, 1);
}

long sysconf(int name)
{
	switch (name)
	{
	case _SC_PAGESIZE: return 4096;
	case _SC_PHYS_PAGES: return (long)(heapGetTotalSize() / 4096);
	case _SC_AVPHYS_PAGES: return (long)(heapGetFreeSize() / 4096);
	case _SC_NPROCESSORS_ONLN: return 4;
	default: errno = EINVAL; return -1;
	}
}

int clock_nanosleep(clockid_t clock_id, int flags, const struct timespec *request, struct timespec *remaining)
{
	if (flags & TIMER_ABSTIME)
	{
		struct timespec now, delta;
		if (clock_gettime(clock_id, &now) != 0) return errno;
		delta.tv_sec = request->tv_sec - now.tv_sec;
		delta.tv_nsec = request->tv_nsec - now.tv_nsec;
		if (delta.tv_nsec < 0) { delta.tv_nsec += 1000000000; --delta.tv_sec; }
		if (delta.tv_sec < 0) return 0;
		return nanosleep(&delta, NULL) == 0 ? 0 : errno;
	}
	return nanosleep(request, remaining) == 0 ? 0 : errno;
}

int pause(void)
{
	struct timespec delay = { 0, 1000000 };
	nanosleep(&delay, NULL);
	errno = EINTR;
	return -1;
}

int utimensat(int dirfd, const char *path, const struct timespec times[2], int flags)
{
	(void)dirfd; (void)path; (void)times; (void)flags;
	return 0;
}

int backtrace(void **buffer, int size)
{
	(void)buffer; (void)size;
	return 0;
}
