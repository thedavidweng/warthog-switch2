#include "switch2_net.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <pthread.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#ifdef __APPLE__
#include <sys/stdio.h>
#endif

static pthread_mutex_t map_commit_lock = PTHREAD_MUTEX_INITIALIZER;

static int map_error(char *error, size_t error_size, const char *format, ...)
{
	va_list arguments;
	va_start(arguments, format);
	if (error && error_size)
		vsnprintf(error, error_size, format, arguments);
	va_end(arguments);
	return 0;
}

static int map_file_is_valid(const char *path, char *error, size_t error_size)
{
	unsigned char header[0x800];
	struct stat status;
	int file;
	ssize_t received;
	uint32_t length;

	file = open(path, O_RDONLY);
	if (file < 0 || fstat(file, &status) != 0)
	{
		if (file >= 0) close(file);
		return map_error(error, error_size, "cannot inspect downloaded map");
	}
	received = read(file, header, sizeof(header));
	close(file);
	if (received != (ssize_t)sizeof(header) ||
		memcmp(header, "head", 4) != 0 ||
		memcmp(header + 0x7fc, "foot", 4) != 0)
		return map_error(error, error_size, "downloaded map has an invalid or truncated cache header");
	length = (uint32_t)header[8] | ((uint32_t)header[9] << 8) |
		((uint32_t)header[10] << 16) | ((uint32_t)header[11] << 24);
	if (length && (uint64_t)length > (uint64_t)status.st_size)
		return map_error(error, error_size, "downloaded map is truncated");
	return 1;
}

int switch2_net_commit_downloaded_map(const char *part_path, const char *dest_map_path,
	char *error, size_t error_size)
{
	int file;
	int result = 0;

	if (!map_file_is_valid(part_path, error, error_size))
	{
		unlink(part_path);
		return 0;
	}
	file = open(part_path, O_RDONLY);
	if (file < 0 || fsync(file) != 0)
	{
		if (file >= 0) close(file);
		unlink(part_path);
		return map_error(error, error_size, "cannot flush downloaded map");
	}
	close(file);
	pthread_mutex_lock(&map_commit_lock);
#ifdef __APPLE__
	result = renameatx_np(AT_FDCWD, part_path, AT_FDCWD, dest_map_path, RENAME_EXCL);
#elif defined(__SWITCH2__)
	if (access(dest_map_path, F_OK) != 0)
		result = rename(part_path, dest_map_path);
	else
		errno = EEXIST;
#else
	if (link(part_path, dest_map_path) == 0)
		result = unlink(part_path);
	else if (errno == EOPNOTSUPP || errno == EXDEV || errno == ENOTSUP)
	{
		if (access(dest_map_path, F_OK) == 0)
			errno = EEXIST;
		else
			result = rename(part_path, dest_map_path);
	}
#endif
	if (result != 0)
	{
		int saved = errno;
		unlink(part_path);
		pthread_mutex_unlock(&map_commit_lock);
		return map_error(error, error_size, "cannot install map: %s", strerror(saved));
	}
	pthread_mutex_unlock(&map_commit_lock);
	return 1;
}

static int remove_stale_parts(const char *directory)
{
	DIR *stream = opendir(directory);
	struct dirent *entry;
	char path[PATH_MAX];
	int result = 1;

	if (!stream)
		return errno == ENOENT;
	while ((entry = readdir(stream)))
	{
		size_t length = strlen(entry->d_name);
		if ((length < 9 || strcmp(entry->d_name + length - 9, ".map.part") != 0) &&
			(length < 4 || strcmp(entry->d_name + length - 4, ".tmp") != 0))
			continue;
		if (snprintf(path, sizeof(path), "%s/%s", directory, entry->d_name) >= (int)sizeof(path) ||
			unlink(path) != 0)
			result = 0;
	}
	closedir(stream);
	return result;
}

int switch2_net_cleanup_stale_map_parts(const char *data_root)
{
	char maps[PATH_MAX], maps_ce[PATH_MAX];
	if (snprintf(maps, sizeof(maps), "%s/maps", data_root) >= (int)sizeof(maps) ||
		snprintf(maps_ce, sizeof(maps_ce), "%s/maps_ce", data_root) >= (int)sizeof(maps_ce))
		return 0;
	return remove_stale_parts(maps) && remove_stale_parts(maps_ce);
}
