#ifndef SWITCH2_UPDATE_H
#define SWITCH2_UPDATE_H

#include <stddef.h>
#include <stdint.h>

#define SWITCH2_UPDATE_REPO "thedavidweng/warthog-switch2"

/* Returns an HTTP status or a negative value on failure. Body ownership
 * passes to the caller, which frees it. */
typedef int (*switch2_update_http_fn)(void *ctx, const char *url, int follow_redirects,
                                      uint8_t **out_body, size_t *out_size,
                                      char *out_location, size_t loc_size);
int switch2_update_asset_name(const char *flavor, char *out, size_t size);
int switch2_update_url_allowed(const char *url);
int switch2_update_verify_nro(const uint8_t *data, size_t size);
int switch2_update_apply_zip(const char *card_dir, const uint8_t *zip_bytes,
                            size_t zip_size, char *err, size_t err_size);
int switch2_update_finish_pending(const char *card_dir);
int switch2_update_check(const char *card_dir, const char *flavor, int current_build,
                         switch2_update_http_fn http_fn, void *ctx, char *err, size_t err_size);

#endif
