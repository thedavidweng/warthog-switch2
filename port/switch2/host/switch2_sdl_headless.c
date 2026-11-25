/*
SDL_HEADLESS.C

The few SDL functions the platform units the server shares with the game
call (port_config.c, menu_files.c, browser.c, dsound_sdl.c, gl_functions.c),
for a server built without SDL (tools/server_build.py): files and folders
with the C library, and no audio device or OpenGL to open. Each behaves as
SDL 3's does for what those units ask of it. Built with the host's ABI, as
SDL is; only SDL's headers are needed, for the declarations. On Windows
(the Windows server, tools/windows_build.py) the folders are the C
runtime's and a search is FindFirstFile's.
*/

#include <SDL3/SDL.h>

#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include "switch2_campaign.h"

#ifdef _WIN32
#include <direct.h>
#include <io.h>
#include <windows.h>
/* (port/windows/include/posix: clock_gettime, readlink of /proc/self/exe) */
#include <unistd.h>
#define strncasecmp _strnicmp
#define mkdir(path, mode) _mkdir(path)
#ifndef PATH_MAX
#define PATH_MAX 1024
#endif
#ifndef S_ISREG
#define S_ISREG(mode) (((mode) & _S_IFMT) == _S_IFREG)
#define S_ISDIR(mode) (((mode) & _S_IFMT) == _S_IFDIR)
#endif
#else
#include <dirent.h>
#include <fnmatch.h>
#include <switch.h>
#include <SDL3/SDL_opengl.h>
#include <strings.h>
#include <unistd.h>
#endif

#ifdef __SWITCH2__
void warthog_log(const char *level, const char *format, ...);

void host_storage_commit(void)
{
	Result result = fsdevCommitDevice("sdmc");
	if (R_FAILED(result))
		warthog_log("WARN", "sd card: the filesystem was not committed (%08x)", result);
}
#endif

static char headless_error[128] = "";

static void headless_set_error(const char *text)
{
	snprintf(headless_error, sizeof(headless_error), "%s", text);
}

const char *SDL_GetError(void)
{
	return headless_error;
}

void SDL_free(void *memory)
{
	free(memory);
}

int SDL_strncasecmp(const char *first, const char *second, size_t length)
{
	return strncasecmp(first, second, length);
}

bool SDL_SetHint(const char *name, const char *value)
{
	(void)name;
	(void)value;
	return true;
}

/* ---------- files */

/* the whole file, with a NUL after it (as SDL's), or NULL */
void *SDL_LoadFile(const char *path, size_t *size)
{
	FILE *file = fopen(path, "rb");
	char *data = NULL;
	size_t length = 0, capacity = 0;

	if (size)
		*size = 0;
	if (!file)
	{
		headless_set_error(strerror(errno));
		return NULL;
	}
	for (;;)
	{
		size_t got;

		if (length + 4096 + 1 > capacity)
		{
			char *grown;

			capacity = capacity ? capacity * 2 : 65536;
			grown = realloc(data, capacity);
			if (!grown)
			{
				free(data);
				fclose(file);
				headless_set_error("out of memory");
				return NULL;
			}
			data = grown;
		}
		got = fread(data + length, 1, capacity - length - 1, file);
		length += got;
		if (got == 0)
			break;
	}
	if (ferror(file))
	{
		free(data);
		fclose(file);
		headless_set_error("read error");
		return NULL;
	}
	fclose(file);
	data[length] = 0;
	if (size)
		*size = length;
	return data;
}

bool SDL_SaveFile(const char *path, const void *data, size_t size)
{
	if (!switch2_campaign_write_atomic(path, data, size))
	{
		headless_set_error(strerror(errno));
		return false;
	}
	return true;
}

/* a file written as a stream (port_config.c's config.toml: to a new file,
flushed to the disk, then renamed over the old one) */
SDL_IOStream *SDL_IOFromFile(const char *path, const char *mode)
{
	FILE *file = fopen(path, mode);

	if (!file)
		headless_set_error(strerror(errno));
	return (SDL_IOStream *)file;
}

size_t SDL_WriteIO(SDL_IOStream *stream, const void *data, size_t size)
{
	return fwrite(data, 1, size, (FILE *)stream);
}

/* (as SDL's: the C library's buffer, then the system's to the disk) */
bool SDL_FlushIO(SDL_IOStream *stream)
{
	FILE *file = (FILE *)stream;

	if (fflush(file) != 0)
		return false;
#ifdef _WIN32
	return _commit(_fileno(file)) == 0;
#else
	return fsync(fileno(file)) == 0;
#endif
}

bool SDL_CloseIO(SDL_IOStream *stream)
{
	return !stream || fclose((FILE *)stream) == 0;
}

/* (over a file that is there, as SDL's: MoveFileEx on Windows, here also
written through to the disk before it returns) */
bool SDL_RenamePath(const char *old_path, const char *new_path)
{
#ifdef _WIN32
	if (!MoveFileExA(old_path, new_path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH))
	{
		headless_set_error("cannot rename the file");
		return false;
	}
#else
	if (rename(old_path, new_path) != 0)
	{
		headless_set_error(strerror(errno));
		return false;
	}
#endif
	return true;
}

bool SDL_RemovePath(const char *path)
{
	if (remove(path) != 0)
	{
		headless_set_error(strerror(errno));
		return false;
	}
	return true;
}

/* whether the path is there, and what it is */
#ifndef HALO_SWITCH2_GRAPHICAL
bool SDL_GetPathInfo(const char *path, SDL_PathInfo *info)
{
	struct stat status;

	if (stat(path, &status) != 0)
	{
		headless_set_error(strerror(errno));
		return false;
	}
	if (info)
	{
		memset(info, 0, sizeof(*info));
		info->type = S_ISREG(status.st_mode) ? SDL_PATHTYPE_FILE :
			S_ISDIR(status.st_mode) ? SDL_PATHTYPE_DIRECTORY : SDL_PATHTYPE_OTHER;
		info->size = (Uint64)status.st_size;
		info->modify_time = (SDL_Time)status.st_mtime * 1000000000;
		info->create_time = info->modify_time;
		info->access_time = (SDL_Time)status.st_atime * 1000000000;
	}
	return true;
}
#endif

/* the executable's folder, with a / after it */
const char *SDL_GetBasePath(void)
{
	static char base[PATH_MAX + 1];

	if (!base[0])
	{
#ifdef __SWITCH2__
		const char *root = getenv("HALO_DATA_ROOT");
		size_t length;

		if (!root || !*root)
			root = "sdmc:/switch/warthog";
		length = strlen(root);
		if (length + (root[length - 1] != '/') >= sizeof(base))
		{
			headless_set_error("data root path is too long");
			return NULL;
		}
		memcpy(base, root, length);
		if (base[length - 1] != '/')
			base[length++] = '/';
		base[length] = 0;
#else
		ssize_t length = readlink("/proc/self/exe", base, sizeof(base) - 2);
		char *slash;

		if (length <= 0)
		{
			headless_set_error("cannot find the executable");
			return NULL;
		}
		base[length] = 0;
		slash = strrchr(base, '/');
		if (slash)
			slash[1] = 0;
#endif
	}
	return base;
}

#ifdef _WIN32
#define SEPARATOR_BACKSLASH 1
#else
#define SEPARATOR_BACKSLASH 0
#endif

/* the folder, and the ones above it that it needs */
bool SDL_CreateDirectory(const char *path)
{
	char partial[PATH_MAX];
	size_t index;

	snprintf(partial, sizeof(partial), "%s", path);
	for (index = 1; partial[index]; index++)
	{
		char separator = partial[index];

		/* (on Windows a backslash too, and not the one after a drive letter) */
		if (separator == '/' || (separator == '\\' && SEPARATOR_BACKSLASH))
		{
			if (index == 2 && partial[1] == ':')
				continue;
			partial[index] = 0;
			mkdir(partial, 0755);
			partial[index] = separator;
		}
	}
	if (mkdir(partial, 0755) != 0 && errno != EEXIST)
	{
		headless_set_error(strerror(errno));
		return false;
	}
	return true;
}

#ifndef HALO_SWITCH2_GRAPHICAL
char **SDL_GlobDirectory(const char *path, const char *pattern, SDL_GlobFlags flags, int *count)
{
    DIR *dir = opendir(path); struct dirent *entry; size_t used = 0, bytes = sizeof(char *); char **tmp = NULL, **result; char *text;
    (void)flags; if (count) *count = 0; if (!dir) return NULL;
    while ((entry = readdir(dir))) { if (fnmatch(pattern, entry->d_name, 0)) continue; char **next = realloc(tmp, (used+1)*sizeof(*tmp)); if (!next) break; tmp=next; tmp[used]=strdup(entry->d_name); if (!tmp[used]) break; bytes+=sizeof(char*)+strlen(tmp[used])+1; used++; }
    closedir(dir); if (!used) { free(tmp); return NULL; }
    result=malloc(bytes); if (result) { text=(char *)(result+used+1); for (size_t i=0;i<used;i++) { result[i]=text; strcpy(text,tmp[i]); text+=strlen(text)+1; } result[used]=NULL; if (count) *count=(int)used; }
    for (size_t i=0;i<used;i++) free(tmp[i]); free(tmp); return result;
}
#endif

/* ---------- no devices */

SDL_FunctionPointer SDL_GL_GetProcAddress(const char *name)
{
	(void)name;
	headless_set_error("the server has no OpenGL");
	return NULL;
}

bool SDL_GL_ExtensionSupported(const char *extension)
{
	(void)extension;
	return false;
}

#ifndef HALO_SWITCH2_GRAPHICAL
SDL_AudioDeviceID *SDL_GetAudioPlaybackDevices(int *count)
{
	if (count)
		*count = 0;
	headless_set_error("the server plays no sound");
	return NULL;
}
#endif

#ifndef HALO_SWITCH2_GRAPHICAL
const char *SDL_GetAudioDeviceName(SDL_AudioDeviceID device)
{
	(void)device;
	return NULL;
}
#endif

#ifndef HALO_SWITCH2_GRAPHICAL
void SDL_DestroyAudioStream(SDL_AudioStream *stream)
{
	(void)stream;
}
#endif

/* (milliseconds since the server started, as SDL counts them) */
Uint64 SDL_GetTicks(void)
{
	static struct timespec start;
	struct timespec now;

	if (!start.tv_sec && !start.tv_nsec)
		clock_gettime(CLOCK_MONOTONIC, &start);
	clock_gettime(CLOCK_MONOTONIC, &now);
	return (Uint64)((long long)(now.tv_sec - start.tv_sec) * 1000 +
		(now.tv_nsec - start.tv_nsec) / 1000000);
}

#ifndef HALO_SWITCH2_GRAPHICAL
SDL_AudioDeviceID SDL_GetAudioStreamDevice(SDL_AudioStream *stream)
{
	(void)stream;
	return 0;
}
#endif

bool SDL_GetAudioDeviceFormat(SDL_AudioDeviceID device, SDL_AudioSpec *specification, int *sample_frames)
{
	(void)device;
	(void)specification;
	(void)sample_frames;
	headless_set_error("the server plays no sound");
	return false;
}

#ifndef HALO_SWITCH2_GRAPHICAL
SDL_AudioStream *SDL_OpenAudioDeviceStream(SDL_AudioDeviceID device, const SDL_AudioSpec *specification,
	SDL_AudioStreamCallback callback, void *userdata)
{
	(void)device;
	(void)specification;
	(void)callback;
	(void)userdata;
	headless_set_error("the server plays no sound");
	return NULL;
}
#endif

#ifndef HALO_SWITCH2_GRAPHICAL
bool SDL_ResumeAudioStreamDevice(SDL_AudioStream *stream)
{
	(void)stream;
	return false;
}
#endif

#ifndef HALO_SWITCH2_GRAPHICAL
bool SDL_PutAudioStreamData(SDL_AudioStream *stream, const void *buffer, int length)
{
	(void)stream;
	(void)buffer;
	(void)length;
	return false;
}
#endif

Uint64 SDL_GetPerformanceCounter(void) { return armGetSystemTick(); }
Uint64 SDL_GetPerformanceFrequency(void) { return armGetSystemTickFreq(); }
