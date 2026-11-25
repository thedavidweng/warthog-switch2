#ifndef WARTHOG_SWITCH2_NET_H
#define WARTHOG_SWITCH2_NET_H

#include <stddef.h>

int switch2_net_commit_downloaded_map(const char *part_path, const char *dest_map_path,
	char *error, size_t error_size);
int switch2_net_cleanup_stale_map_parts(const char *data_root);

#endif
