/* SPDX-License-Identifier: GPL-3.0-or-later */
#define _POSIX_C_SOURCE 200809L
#include "switch2_gamedata.h"
#include "switch2_custom_edition.h"

#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <unistd.h>

static int path_join(char *out, size_t size, const char *base, const char *name)
{
	int n = snprintf(out, size, "%s/%s", base, name);
	return n >= 0 && (size_t)n < size;
}

static int find_name(const char *folder, const char *name, char *out, size_t size)
{
	DIR *dir = opendir(folder);
	struct dirent *entry;
	if (!dir)
		return 0;
	while ((entry = readdir(dir)))
		if (!strcasecmp(entry->d_name, name))
		{
			int result = path_join(out, size, folder, entry->d_name);
			closedir(dir);
			return result;
		}
	closedir(dir);
	return 0;
}

static int has_ui(const char *root)
{
	char maps[4096], ui[4096];
	struct stat st;
	return find_name(root, "maps", maps, sizeof(maps)) &&
		find_name(maps, "ui.map", ui, sizeof(ui)) && stat(ui, &st) == 0 && S_ISREG(st.st_mode);
}

/* Copy missing entries only; existing entries and the source are never removed. */
static int merge_tree(const char *source, const char *target)
{
	struct stat st;
	if (lstat(source, &st) != 0)
		return errno == ENOENT;
	if (S_ISDIR(st.st_mode))
	{
		DIR *dir;
		struct dirent *entry;
		if (mkdir(target, 0755) && errno != EEXIST)
			return 0;
		if (lstat(target, &st) || !S_ISDIR(st.st_mode))
			return 0;
		dir = opendir(source);
		if (!dir)
			return 0;
		for (int pass = 0; pass < 2; pass++)
		{
			rewinddir(dir);
			while ((entry = readdir(dir)))
			{
				char from[4096], to[4096];
				if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, "..") ||
					((strcasecmp(entry->d_name, "ui.map") == 0) != pass))
					continue;
				if (!path_join(from, sizeof(from), source, entry->d_name) ||
					(!find_name(target, entry->d_name, to, sizeof(to)) &&
					!path_join(to, sizeof(to), target, entry->d_name)) || !merge_tree(from, to))
				{
					closedir(dir);
					return 0;
				}
			}
		}
		return closedir(dir) == 0;
	}
	if (S_ISREG(st.st_mode))
	{
		char buffer[4096];
		int in, out;
		char temporary[4096];
		ssize_t count;
		if (lstat(target, &st) == 0)
			return 1;
		if (errno != ENOENT)
			return 0;
		in = open(source, O_RDONLY);
		if (in < 0)
			return 0;
		if (snprintf(temporary, sizeof(temporary), "%s.tmp.XXXXXX", target) >= (int)sizeof(temporary))
		{
			close(in);
			return 0;
		}
		out = mkstemp(temporary);
		if (out < 0)
		{
			close(in);
			return 0;
		}
		while ((count = read(in, buffer, sizeof(buffer))) > 0)
		{
			ssize_t pos = 0;
			while (pos < count)
			{
				ssize_t n = write(out, buffer + pos, (size_t)(count - pos));
				if (n <= 0)
				{
					count = -1;
					break;
				}
				pos += n;
			}
			if (count < 0)
				break;
		}
		if (count < 0 || fsync(out) != 0)
		{
			close(in);
			close(out);
			unlink(temporary);
			return 0;
		}
		close(in);
		if (close(out) != 0)
		{
			unlink(temporary);
			return 0;
		}
		if (lstat(target, &st) == 0)
		{
			unlink(temporary);
			return 1;
		}
		if (errno != ENOENT || rename(temporary, target) != 0)
		{
			unlink(temporary);
			return 0;
		}
		return 1;
	}
	return 0;
}

static int migrate(const char *root, const char *legacy)
{
	static const char *const names[] = { "save", "profile", "maps_ce", "bink", "config.toml", "maps" };
	size_t i;
	for (i = 0; i < sizeof(names) / sizeof(names[0]); ++i)
	{
		char from[4096], to[4096];
		int exists;
		if (!find_name(legacy, names[i], from, sizeof(from)))
			continue;
		exists = find_name(root, names[i], to, sizeof(to));
		if (!exists)
		{
			if (!path_join(to, sizeof(to), root, names[i])) return 0;
			if (rename(from, to) == 0) continue;
		}
		if (!merge_tree(from, to))
			return 0;
	}
	return 1;
}

/* XDVDFS layout and language selection follow the upstream xiso.c reader. */
struct disc_entry { char path[1024]; uint32_t sector, size; int directory, movie; };
struct disc {
	int fd;
	uint64_t partition, length;
	struct disc_entry *entries;
	int count;
};

static uint32_t u16(const unsigned char *p) { return (uint32_t)p[0] | (uint32_t)p[1] << 8; }
static uint32_t u32(const unsigned char *p) { return u16(p) | u16(p + 2) << 16; }

static int disc_read(struct disc *disc, uint64_t offset, void *buffer, size_t size)
{
	uint64_t at = disc->partition + offset;
	if (at > disc->length || size > disc->length - at || lseek(disc->fd, (off_t)at, SEEK_SET) < 0)
		return 0;
	while (size)
	{
		ssize_t n = read(disc->fd, buffer, size);
		if (n <= 0) return 0;
		buffer = (char *)buffer + n;
		size -= (size_t)n;
	}
	return 1;
}

static int tree(struct disc *disc, const unsigned char *table, uint32_t size, uint32_t pos,
	int depth, const char *prefix, int movie)
{
	const unsigned char *e;
	char name[256], path[1024];
	uint32_t len;
	if (depth > 64 || pos > size || size - pos < 14 || disc->count >= 4096)
		return 0;
	e = table + pos;
	len = e[13];
	if (!len || len > size - pos - 14) return 0;
	memcpy(name, e + 14, len);
	name[len] = 0;
	if (!strcmp(name, ".") || !strcmp(name, "..")) return 0;
	for (uint32_t i = 0; i < len; i++)
		if ((unsigned char)name[i] < 32 || (unsigned char)name[i] > 126 || strchr("/\\:*?\"<>|", name[i]))
			return 0;
	if (u16(e) && !tree(disc, table, size, u16(e) * 4, depth + 1, prefix, movie)) return 0;
	if (snprintf(path, sizeof(path), "%s%s%s", prefix, *prefix ? "/" : "", name) >= (int)sizeof(path))
		return 0;
	struct disc_entry *item = &disc->entries[disc->count++];
	strcpy(item->path, path);
	item->sector = u32(e + 4);
	item->size = u32(e + 8);
	item->directory = !!(e[12] & 16);
	item->movie = movie;
	if (u16(e + 2) && !tree(disc, table, size, u16(e + 2) * 4, depth + 1, prefix, movie)) return 0;
	return 1;
}

static int directory_read(struct disc *disc, uint32_t sector, uint32_t size, const char *prefix,
	int movie, int recurse, int depth)
{
	unsigned char *table;
	int first = disc->count, last;
	if (depth > 16 || size > 4 * 1024 * 1024) return 0;
	if (!size) return 1;
	table = malloc(size);
	if (!table) return 0;
	int ok = disc_read(disc, (uint64_t)sector * 2048, table, size) &&
		tree(disc, table, size, 0, 0, prefix, movie);
	free(table);
	if (!ok) return 0;
	last = disc->count;
	if (recurse)
		for (int i = first; i < last; i++)
			if (disc->entries[i].directory &&
				!directory_read(disc, disc->entries[i].sector, disc->entries[i].size,
					disc->entries[i].path, movie, 1, depth + 1)) return 0;
	return 1;
}

static int exact_size(const char *path, uint32_t size)
{
	struct stat st;
	return lstat(path, &st) == 0 && S_ISREG(st.st_mode) && (uint64_t)st.st_size == size;
}

static int extract_disc(const char *image, const char *root, uint64_t free_override, uint64_t limit,
	switch2_gamedata_progress progress, void *ctx, char *message, size_t message_size)
{
	static const uint64_t offsets[] = { 0, 0x18300000ULL, 0x0fd90000ULL, 0x02080000ULL };
	unsigned char descriptor[2048], buffer[65536];
	struct disc disc = { .fd = -1 };
	struct stat st;
	struct statvfs vfs;
	char partial[4096], final[4096], path[4096], temp[4096];
	int result = SWITCH2_GAMEDATA_INVALID_IMAGE, maps = -1, english = -1, first = -1;
	int bink = -1, root_count, has_map = 0;
	int file_count = 0, index = 0;
	uint64_t total = 0, needed = 16ULL * 1024 * 1024, done = 0, copied = 0, free_bytes;
	disc.fd = open(image, O_RDONLY);
	disc.entries = calloc(4096, sizeof(*disc.entries));
	if (disc.fd < 0 || !disc.entries || fstat(disc.fd, &st)) goto finish;
	disc.length = (uint64_t)st.st_size;
	for (size_t i = 0; i < sizeof(offsets) / sizeof(offsets[0]); i++)
	{
		disc.partition = offsets[i];
		if (disc_read(&disc, 32 * 2048, descriptor, sizeof(descriptor)) &&
			!memcmp(descriptor, "MICROSOFT*XBOX*MEDIA", 20)) break;
		if (i + 1 == sizeof(offsets) / sizeof(offsets[0])) goto finish;
	}
	if (!directory_read(&disc, u32(descriptor + 20), u32(descriptor + 24), "", 0, 0, 0)) goto finish;
	root_count = disc.count;
	for (int i = 0; i < root_count; i++)
	{
		struct disc_entry *e = &disc.entries[i];
		if (!e->directory) continue;
		if (!strcasecmp(e->path, "maps")) maps = i;
		else if (!strcasecmp(e->path, "maps_en")) english = i;
		else if (first < 0 && !strncasecmp(e->path, "maps_", 5) && strlen(e->path) == 7) first = i;
		else if (!strcasecmp(e->path, "bink")) bink = i;
	}
	if (maps < 0)
	{
		const char *locale = getenv("LC_ALL");
		if (!locale || !*locale) locale = getenv("LC_MESSAGES");
		if (!locale || !*locale) locale = getenv("LANG");
		if (locale && strlen(locale) >= 2)
			for (int i = 0; i < root_count; i++)
				if (disc.entries[i].directory && strlen(disc.entries[i].path) == 7 &&
					!strncasecmp(disc.entries[i].path, "maps_", 5) &&
					!strncasecmp(disc.entries[i].path + 5, locale, 2))
					maps = i;
		if (maps < 0) maps = english >= 0 ? english : first;
	}
	if (maps < 0 || !directory_read(&disc, disc.entries[maps].sector, disc.entries[maps].size, "", 0, 1, 0))
		goto finish;
	int map_end = disc.count;
	if (bink >= 0 && !directory_read(&disc, disc.entries[bink].sector, disc.entries[bink].size, "", 1, 0, 0))
		goto finish;
	if (!path_join(partial, sizeof(partial), root, "maps.partial") ||
		!path_join(final, sizeof(final), root, "maps")) goto finish;
	for (int i = root_count; i < disc.count; i++)
	{
		struct disc_entry *e = &disc.entries[i];
		size_t n = strlen(e->path);
		if (e->directory) continue;
		if (i >= map_end && (n < 4 || strcasecmp(e->path + n - 4, ".bik"))) continue;
		if (i < map_end && !strcasecmp(e->path, "ui.map")) has_map = 1;
		if ((uint64_t)e->sector * 2048 + e->size > disc.length - disc.partition) goto finish;
		if (snprintf(path, sizeof(path), "%s/%s%s", e->movie ? root : partial,
			e->movie ? "bink/" : "", e->path) >= (int)sizeof(path)) goto finish;
		total += e->size;
		if (!exact_size(path, e->size)) needed += e->size;
		file_count++;
	}
	if (!has_map) goto finish;
	if (free_override) free_bytes = free_override;
	else if (statvfs(root, &vfs) == 0) free_bytes = (uint64_t)vfs.f_bavail * vfs.f_frsize;
	else { result = SWITCH2_GAMEDATA_IO_ERROR; goto finish; }
	if (needed > free_bytes)
	{
		snprintf(message, message_size, "Insufficient space: need %llu MiB, free %llu MiB.",
			(unsigned long long)((needed + 1048575) / 1048576),
			(unsigned long long)(free_bytes / 1048576));
		result = SWITCH2_GAMEDATA_INSUFFICIENT_SPACE;
		goto finish;
	}
	result = SWITCH2_GAMEDATA_IO_ERROR;
	if (mkdir(partial, 0755) && errno != EEXIST) goto finish;
	for (int i = root_count; i < disc.count; i++)
	{
		struct disc_entry *e = &disc.entries[i];
		size_t n = strlen(e->path);
		if (i >= map_end && (e->directory || n < 4 || strcasecmp(e->path + n - 4, ".bik"))) continue;
		if (snprintf(path, sizeof(path), "%s/%s%s", e->movie ? root : partial,
			e->movie ? "bink/" : "", e->path) >= (int)sizeof(path)) goto finish;
		if (e->directory) { if (mkdir(path, 0755) && errno != EEXIST) goto finish; continue; }
		index++;
		if (e->movie)
		{
			char folder[4096], existing[4096];
			if (!path_join(folder, sizeof(folder), root, "bink")) goto finish;
			if (mkdir(folder, 0755) && errno != EEXIST) goto finish;
			if (find_name(folder, e->path, existing, sizeof(existing)))
			{
				done += e->size;
				if (progress) progress(ctx, index, file_count, e->path, done, total);
				continue;
			}
		}
		if (snprintf(temp, sizeof(temp), "%s.part", path) >= (int)sizeof(temp)) goto finish;
		if (unlink(temp) && errno != ENOENT) goto finish;
		if (exact_size(path, e->size))
		{
			done += e->size;
			if (progress) progress(ctx, index, file_count, e->path, done, total);
			continue;
		}
		int out = open(temp, O_WRONLY | O_CREAT | O_EXCL, 0644);
		if (out < 0) goto finish;
		uint32_t remaining = e->size, at = 0;
		while (remaining)
		{
			size_t amount = remaining < sizeof(buffer) ? remaining : sizeof(buffer);
			if (limit && copied + amount > limit) amount = (size_t)(limit - copied);
			if (!amount || !disc_read(&disc, (uint64_t)e->sector * 2048 + at, buffer, amount))
			{ close(out); goto finish; }
			size_t written = 0;
			while (written < amount)
			{
				ssize_t w = write(out, buffer + written, amount - written);
				if (w <= 0) { close(out); goto finish; }
				written += (size_t)w;
			}
			at += (uint32_t)amount; remaining -= (uint32_t)amount; copied += amount; done += amount;
			if (progress) progress(ctx, index, file_count, e->path, done, total);
		}
		if (fsync(out)) { close(out); goto finish; }
		if (close(out) || rename(temp, path)) goto finish;
	}
	if (rename(partial, final))
	{
		if (!merge_tree(partial, final)) goto finish;
	}
	snprintf(message, message_size, "Game data extracted.");
	result = SWITCH2_GAMEDATA_OK;
finish:
	if (result == SWITCH2_GAMEDATA_INVALID_IMAGE)
		snprintf(message, message_size, "Invalid or incomplete Xbox disc image: Halo maps/ui.map could not be unpacked.");
	else if (result == SWITCH2_GAMEDATA_IO_ERROR)
		snprintf(message, message_size, "Could not extract game data; retry with sufficient writable space.");
	if (disc.fd >= 0) close(disc.fd);
	free(disc.entries);
	return result;
}

int switch2_gamedata_prepare_limited(const char *root, const char *legacy, uint64_t free_bytes_override,
	uint64_t limit, switch2_gamedata_progress progress, void *ctx, char *message, size_t message_size)
{
	char maps[4096];
	struct stat st;
	DIR *directory;
	struct dirent *entry;
	int maps_present;
	char ce_message[256];

	if (!switch2_ce_prepare_directory(root, ce_message, sizeof(ce_message)))
	{
		snprintf(message, message_size, "%s", ce_message);
		return SWITCH2_GAMEDATA_IO_ERROR;
	}

	if (!has_ui(root) && has_ui(legacy) && !migrate(root, legacy))
	{
		snprintf(message, message_size, "Could not copy legacy game data; originals were preserved.");
		return SWITCH2_GAMEDATA_IO_ERROR;
	}
	if (has_ui(root))
	{
		if (switch2_ce_enumerate(root, legacy, NULL, NULL, ce_message, sizeof(ce_message)) < 0)
		{
			snprintf(message, message_size, "%s", ce_message);
			return SWITCH2_GAMEDATA_INVALID_IMAGE;
		}
		snprintf(message, message_size, "Game data found.");
		return SWITCH2_GAMEDATA_OK;
	}
	if (snprintf(maps, sizeof(maps), "%s/maps", root) >= (int)sizeof(maps))
	{
		snprintf(message, message_size, "Game data path is too long.");
		return SWITCH2_GAMEDATA_IO_ERROR;
	}
	maps_present = find_name(root, "maps", maps, sizeof(maps)) &&
		stat(maps, &st) == 0 && S_ISDIR(st.st_mode);
	directory = opendir(root);
	if (directory)
	{
		while ((entry = readdir(directory)))
		{
			size_t length = strlen(entry->d_name);
			if ((length >= 4 && !strcasecmp(entry->d_name + length - 4, ".iso")) ||
				(length >= 5 && !strcasecmp(entry->d_name + length - 5, ".xiso")))
			{
				char image[4096];
				int valid = path_join(image, sizeof(image), root, entry->d_name);
				closedir(directory);
				if (!valid) return SWITCH2_GAMEDATA_IO_ERROR;
				return extract_disc(image, root, free_bytes_override, limit, progress, ctx, message, message_size);
			}
		}
		closedir(directory);
	}
	if (maps_present)
	{
		snprintf(message, message_size, "Game data is incomplete: maps/ui.map is missing.");
		return SWITCH2_GAMEDATA_MISSING_UI_MAP;
	}
	snprintf(message, message_size, "Place your Xbox disc image or maps folder in %s.", root);
	return SWITCH2_GAMEDATA_NO_IMAGE;
}

int switch2_gamedata_prepare(const char *root, const char *legacy, uint64_t free_bytes_override,
	switch2_gamedata_progress progress, void *ctx, char *message, size_t message_size)
{
	return switch2_gamedata_prepare_limited(root, legacy, free_bytes_override, 0, progress, ctx,
		message, message_size);
}
