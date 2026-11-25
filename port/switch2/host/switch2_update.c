#define _POSIX_C_SOURCE 200809L
#include "switch2_update.h"
#include "tomlc17.h"

#include <ctype.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int switch2_update_asset_name(const char *flavor, char *out, size_t size)
{
	if (!flavor || !out || (strcmp(flavor, "release") && strcmp(flavor, "debug")))
		return 0;
	int n = snprintf(out, size, "warthog-switch2-%s.zip", flavor);
	return n >= 0 && (size_t)n < size;
}

int switch2_update_url_allowed(const char *url)
{
	const char *prefix = "https://github.com/" SWITCH2_UPDATE_REPO "/releases/";
	if (!url || strncmp(url, prefix, strlen(prefix))) return 0;
	const char *p = url + strlen(prefix);
	if (!strncmp(p, "tag/build-", 10)) p += 10;
	else if (!strncmp(p, "download/build-", 15)) p += 15;
	else return 0;
	if (!isdigit((unsigned char)*p)) return 0;
	while (isdigit((unsigned char)*p)) ++p;
	return !*p || !strcmp(p, "/warthog-switch2-release.zip") ||
	       !strcmp(p, "/warthog-switch2-debug.zip");
}

static uint32_t u32(const uint8_t *p)
{
	return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

static uint64_t u64(const uint8_t *p)
{
	return (uint64_t)u32(p) | (uint64_t)u32(p + 4) << 32;
}

int switch2_update_verify_nro(const uint8_t *data, size_t size)
{
	if (!data || size < 128 || memcmp(data + 8, "HOMEBREWNRO0", 12))
		return 0;
	uint32_t mod = u32(data + 4), image = u32(data + 24);
	if (mod > size - 4 || memcmp(data + mod, "MOD0", 4) ||
	    image > size - 56 || memcmp(data + image, "ASET", 4))
		return 0;
	int found = 0;
	for (size_t i = 0; i + 4 <= image; ++i)
		if (!memcmp(data + i, "OUN0", 4)) { found = 1; break; }
	uint64_t offset = u64(data + image + 24), length = u64(data + image + 32);
	if (!found || length != 16384 || offset > size - image ||
	    length > size - image - offset)
		return 0;
	return !memcmp(data + image + (size_t)offset, "Warthog\0", 8);
}


#include <dirent.h>
#include <errno.h>
#include <sys/stat.h>
#include <unistd.h>

static uint16_t u16(const uint8_t *p)
{
	return (uint16_t)(p[0] | (uint16_t)p[1] << 8);
}

static uint32_t crc32_bytes(const uint8_t *p, size_t size)
{
	uint32_t crc = ~0u;
	while (size--) {
		crc ^= *p++;
		for (int i = 0; i < 8; ++i)
			crc = (crc >> 1) ^ (0xedb88320u & -(crc & 1u));
	}
	return ~crc;
}

static int valid_name(const char *name)
{
	if (strstr(name, "..") || strchr(name, '\\') || name[0] == '/') return 0;
	if (!strcmp(name, "warthog.nro") || !strcmp(name, "brokers.txt") ||
	    !strcmp(name, "LICENSE") || !strcmp(name, "THIRD-PARTY-NOTICES.txt") ||
	    !strcmp(name, "README.md")) return 1;
	if (strncmp(name, "menus/", 6)) return 0;
	const char *style = name + 6, *file = strchr(style, '/');
	if (!file || file == style || !file[1] || strchr(file + 1, '/')) return 0;
	size_t len = strlen(file + 1);
	return len > 4 && !strcmp(file + 1 + len - 4, ".xml");
}

static int path_join(char *out, size_t size, const char *dir, const char *name)
{
	int n = snprintf(out, size, "%s/%s", dir, name);
	return n >= 0 && (size_t)n < size;
}

static int remove_tree(const char *path)
{
	struct stat st;
	if (lstat(path, &st)) return errno == ENOENT;
	if (!S_ISDIR(st.st_mode)) return unlink(path) == 0;
	DIR *dir = opendir(path);
	if (!dir) return 0;
	struct dirent *entry;
	int ok = 1;
	while ((entry = readdir(dir))) {
		if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, "..")) continue;
		char child[4096];
		if (!path_join(child, sizeof(child), path, entry->d_name) || !remove_tree(child)) { ok = 0; break; }
	}
	if (closedir(dir)) ok = 0;
	return ok && rmdir(path) == 0;
}

int switch2_update_finish_pending(const char *card_dir)
{
	char current[4096], pending[4096], old[4096];
	if (!card_dir || !path_join(current, sizeof(current), card_dir, "menus") ||
	    !path_join(pending, sizeof(pending), card_dir, "menus.new") ||
	    !path_join(old, sizeof(old), card_dir, "menus.old")) return 0;
	struct stat st;
	int had_current = lstat(current, &st) == 0;
	if (!had_current && errno != ENOENT) return 0;
	int had_pending = lstat(pending, &st) == 0;
	if (!had_pending && errno != ENOENT) return 0;
	int had_old = lstat(old, &st) == 0;
	if (!had_old && errno != ENOENT) return 0;
	if (had_old && had_current && !remove_tree(old)) return 0;
	if (!had_current && had_old) {
		if (rename(had_pending ? pending : old, current)) return 0;
		return !had_pending || remove_tree(old);
	}
	if (!had_pending) return 1;
	if (had_current && rename(current, old)) return 0;
	if (rename(pending, current)) {
		if (had_current) rename(old, current);
		return 0;
	}
	return !had_current || remove_tree(old);
}

struct update_entry {
	char name[1024];
	const uint8_t *data;
	size_t size, local_offset;
	uint32_t crc;
	int seen;
};

int switch2_update_apply_zip(const char *card_dir, const uint8_t *zip, size_t size,
                            char *err, size_t err_size)
{
	struct update_entry *entries = NULL;
	size_t count = 0, offset = 0;
	int ok = 0, found_nro = 0, has_menus = 0;
	const char *reason = "invalid update archive";
	if (!card_dir || !zip) goto done;
	while (offset <= size && size - offset >= 4 && u32(zip + offset) == 0x04034b50) {
		if (size - offset < 30) goto done;
		const uint8_t *h = zip + offset;
		uint16_t flags = u16(h + 6), method = u16(h + 8), namesize = u16(h + 26), extra = u16(h + 28);
		uint32_t length = u32(h + 18);
		size_t header = 30u + namesize + extra;
		if (flags & 9 || method || length != u32(h + 22) || header > size - offset ||
		    length > size - offset - header || namesize <= 15 || namesize >= 1039 ||
		    memcmp(h + 30, "switch/warthog/", 15) || memchr(h + 30, 0, namesize)) goto done;
		struct update_entry entry;
		memcpy(entry.name, h + 45, namesize - 15);
		entry.name[namesize - 15] = 0;
		entry.data = h + header;
		entry.size = length;
		entry.local_offset = offset;
		entry.crc = u32(h + 14);
		entry.seen = 0;
		if (!valid_name(entry.name) || crc32_bytes(entry.data, entry.size) != u32(h + 14)) goto done;
		for (size_t i = 0; i < count; ++i) if (!strcmp(entries[i].name, entry.name)) goto done;
		if (!strcmp(entry.name, "warthog.nro")) {
			if (!switch2_update_verify_nro(entry.data, entry.size)) goto done;
			found_nro = 1;
		}
		if (!strncmp(entry.name, "menus/", 6)) has_menus = 1;
		struct update_entry *next = realloc(entries, (count + 1) * sizeof(*entries));
		if (!next) { reason = "out of memory"; goto done; }
		entries = next; entries[count++] = entry;
		offset += header + length;
	}
	if (!found_nro || size - offset < 4 || u32(zip + offset) != 0x02014b50) goto done;
	size_t central_start = offset, central_count = 0;
	while (size - offset >= 4 && u32(zip + offset) == 0x02014b50) {
		if (size - offset < 46) goto done;
		const uint8_t *h = zip + offset;
		size_t namesize = u16(h + 28), extra = u16(h + 30), comment = u16(h + 32);
		size_t record_size = 46 + namesize + extra + comment;
		if (record_size > size - offset || u16(h + 8) & 9 || u16(h + 10) ||
		    u16(h + 34) || namesize <= 15 || memcmp(h + 46, "switch/warthog/", 15)) goto done;
		struct update_entry *entry = NULL;
		for (size_t i = 0; i < count; ++i)
			if (entries[i].local_offset == u32(h + 42)) { entry = &entries[i]; break; }
		if (!entry || entry->seen || namesize != strlen(entry->name) + 15 ||
		    memcmp(h + 61, entry->name, namesize - 15) ||
		    u32(h + 16) != entry->crc || u32(h + 20) != entry->size ||
		    u32(h + 24) != entry->size) goto done;
		entry->seen = 1;
		++central_count;
		offset += record_size;
	}
	if (size - offset < 22 || u32(zip + offset) != 0x06054b50 ||
	    u16(zip + offset + 4) || u16(zip + offset + 6) ||
	    u16(zip + offset + 8) != count || u16(zip + offset + 10) != count ||
	    central_count != count || u32(zip + offset + 12) != offset - central_start ||
	    u32(zip + offset + 16) != central_start ||
	    22u + u16(zip + offset + 20) != size - offset) goto done;
	reason = "cannot stage update";
	char pending[4096], staging[4096];
	if (!path_join(pending, sizeof(pending), card_dir, "menus.new") ||
	    !path_join(staging, sizeof(staging), card_dir, "menus.tmp")) goto done;
	if (has_menus && (!remove_tree(staging) || mkdir(staging, 0777))) goto done;
	for (size_t i = 0; i < count; ++i) {
		char path[4096], temp[4096];
		const char *name = entries[i].name;
		if (!strncmp(name, "menus/", 6)) {
			const char *rel = name + 6, *slash = strchr(rel, '/');
			char style[1024];
			size_t n = (size_t)(slash - rel);
			memcpy(style, rel, n); style[n] = 0;
			if (!path_join(path, sizeof(path), staging, style) ||
			    (mkdir(path, 0777) && errno != EEXIST) ||
			    !path_join(temp, sizeof(temp), path, slash + 1)) goto done;
		} else {
			if (!path_join(path, sizeof(path), card_dir, name)) goto done;
			int n = snprintf(temp, sizeof(temp), "%s.new", path);
			if (n < 0 || (size_t)n >= sizeof(temp)) goto done;
		}
		FILE *file = fopen(temp, "wb");
		if (!file) goto done;
		int written = fwrite(entries[i].data, 1, entries[i].size, file) == entries[i].size &&
		              fflush(file) == 0 && fsync(fileno(file)) == 0;
		if (fclose(file)) written = 0;
		if (!written || (strncmp(name, "menus/", 6) && rename(temp, path))) goto done;
	}
	if (has_menus && (!remove_tree(pending) || rename(staging, pending))) goto done;
	ok = 1;
done:
	if (!ok && err && err_size) snprintf(err, err_size, "%s", reason);
	free(entries);
	return ok;
}


static int update_enabled(const char *card_dir)
{
	char path[4096];
	if (!path_join(path, sizeof(path), card_dir, "config.toml")) return -1;
	FILE *file = fopen(path, "r");
	if (!file) return errno == ENOENT ? 1 : -1;
	fclose(file);
	toml_result_t result = toml_parse_file_ex(path);
	if (!result.ok) return -1;
	toml_datum_t setting = toml_seek(result.toptab, "update.auto");
	int enabled = setting.type == TOML_BOOLEAN ? setting.u.boolean : 1;
	toml_free(result);
	return enabled;
}

int switch2_update_check(const char *card_dir, const char *flavor, int current_build,
                         switch2_update_http_fn http_fn, void *ctx, char *err, size_t err_size)
{
	if (current_build <= 0) return 0;
	if (!card_dir || !http_fn) goto fail;
	int enabled = update_enabled(card_dir);
	if (!enabled) return 0;
	if (enabled < 0) goto fail;
	char asset[80], location[2048] = {0}, url[2048];
	if (!switch2_update_asset_name(flavor, asset, sizeof(asset))) goto fail;
	uint8_t *body = NULL;
	size_t size = 0;
	int status = http_fn(ctx, "https://github.com/" SWITCH2_UPDATE_REPO "/releases/latest",
	                     0, &body, &size, location, sizeof(location));
	free(body); body = NULL;
	if (status < 300 || status >= 400) goto fail;
	if (location[0] == '/') {
		int length = snprintf(url, sizeof(url), "https://github.com%s", location);
		if (length < 0 || (size_t)length >= sizeof(url)) goto fail;
		memcpy(location, url, (size_t)length + 1);
	}
	const char *tag = "https://github.com/" SWITCH2_UPDATE_REPO "/releases/tag/build-";
	if (!switch2_update_url_allowed(location) || strncmp(location, tag, strlen(tag))) goto fail;
	const char *number = location + strlen(tag);
	char *end;
	errno = 0;
	long build = strtol(number, &end, 10);
	if (errno || *end || build <= 0 || build > INT_MAX) goto fail;
	if (build <= current_build) return 0;
	int n = snprintf(url, sizeof(url), "https://github.com/" SWITCH2_UPDATE_REPO
	                 "/releases/download/build-%ld/%s", build, asset);
	if (n < 0 || (size_t)n >= sizeof(url) || !switch2_update_url_allowed(url)) goto fail;
	status = http_fn(ctx, url, 1, &body, &size, location, sizeof(location));
	if (status != 200 || !body) { free(body); goto fail; }
	int ok = switch2_update_apply_zip(card_dir, body, size, err, err_size);
	free(body);
	return ok ? 1 : -1;
fail:
	if (err && err_size) snprintf(err, err_size, "update check failed");
	return -1;
}
