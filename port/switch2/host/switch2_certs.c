#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int switch2_seed_certificates(const char *root, const char *bundle)
{
	char path[1024], part[1030];
	if (snprintf(path, sizeof(path), "%s/cacert.pem", root) >= (int)sizeof(path) ||
	    snprintf(part, sizeof(part), "%s.part", path) >= (int)sizeof(part))
		return 0;
	if (access(path, F_OK) != 0)
	{
		FILE *file = fopen(part, "wb");
		if (!file) return 0;
		size_t size = strlen(bundle);
		int ok = fwrite(bundle, 1, size, file) == size && fflush(file) == 0 && fsync(fileno(file)) == 0;
		if (fclose(file) != 0) ok = 0;
		if (!ok || rename(part, path) != 0)
		{
			unlink(part);
			return 0;
		}
	}
	return setenv("SSL_CERT_FILE", path, 1) == 0;
}
