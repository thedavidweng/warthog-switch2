#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#include "cseries.h"
#include "errors.h"
#include "cache/cache_files.h"
#include "cache/physical_memory_map.h"
#include "math/real_math.h"
#include "tag_files/tag_groups.h"
#include "port_config.h"
#include "thread_stop.h"
#include "headless_engine.h"
#include "headless_engine_checks.h"
#include "switch2_mman.h"
#include "warthog_log.h"
#include "switch2_campaign.h"

/* Kept in sync with the private on-disk structure in cache_files.c. */
struct cache_file_header
{
	unsigned long header_signature;
	long version, file_length;
	byte reservedC[4];
	long tag_data_offset, tag_data_size;
	byte reserved18[8];
	char name[0x20], build[0x20];
	byte reserved60[4];
	unsigned long checksum;
	byte reserved68[0x794];
	unsigned long footer_signature;
};
_Static_assert(sizeof(XPTR(void)) == 4, "XPTR size");
_Static_assert(sizeof(struct cache_file_header) == 0x800, "cache header");
_Static_assert(TICKS_PER_SECOND == 30, "Halo simulation rate must remain 30 Hz");

void platform_xbox_memory_reset_for_shutdown(void);
void xbox_heap_reset_for_shutdown(void);
const char *platform_data_root(void);
void nx2ExitCleanupNow(void);

static int check_gameplay_map(const char *root, const char *file, const char *scenario)
{
	char path[1024];
	char diagnostic[256];
	long previous_count = 0;
	unsigned long previous_checksum = 0;
	int failed = 0;

	if (snprintf(path, sizeof(path), "%s/maps/%s", root, file) >= sizeof(path))
	{
		warthog_log("ERROR", "FAIL: headless %s path too long", file);
		return 1;
	}
	if (access(path, R_OK) != 0)
	{
		warthog_log("INFO", "SKIP: headless %s not present", file);
		return 0;
	}
	if (!switch2_campaign_validate_map(path, diagnostic, sizeof(diagnostic)))
	{
		warthog_log("ERROR", "FAIL: %s", diagnostic);
		return 1;
	}
	for (size_t resource = 0; resource < 2; ++resource)
	{
		const char *name = resource ? "sounds.map" : "bitmaps.map";
		unsigned type = resource ? 'snd!' : 'bitm';
		if (snprintf(path, sizeof(path), "%s/maps/%s", root, name) >= sizeof(path))
			return 1;
		if (access(path, R_OK) == 0 &&
			!switch2_campaign_validate_resource(path, type, diagnostic, sizeof(diagnostic)))
		{
			warthog_log("ERROR", "FAIL: %s", diagnostic);
			return 1;
		}
	}
	tag_files_open();
	for (int pass = 0; pass < 2; ++pass)
	{
		long scnr = scenario_tags_load(scenario), count = 0;
		unsigned long checksum;
		struct tag_iterator it;
		if (scnr == NONE)
		{
			failed = 1;
			break;
		}
		checksum = tag_groups_checksum();
		tag_iterator_new(&it, NONE);
		while (tag_iterator_next(&it) != NONE)
			++count;
		if (!tag_get('scnr', scnr) || !count || !checksum ||
			(pass && (count != previous_count || checksum != previous_checksum)))
			failed = 1;
		previous_count = count;
		previous_checksum = checksum;
		scenario_tags_unload();
		if (failed)
			break;
	}
	tag_files_close();
	if (failed)
		warthog_log("ERROR", "FAIL: headless %s repeated load", file);
	else
		warthog_log("INFO", "PASS: headless %s loaded twice (tags=%ld, checksum=%#lx)",
			file, previous_count, previous_checksum);
	return failed;
}

int warthog_headless_engine_run(void)
{
	int failed = 0;
	void *regions[4];
	char ui_path[1024];
	const char *root;

	setenv("HALO_DATA_ROOT", "sdmc:/switch/warthog", 0);
	setenv("HALO_SAVE_ROOT", "sdmc:/switch/warthog/save", 0);
	root = getenv("HALO_DATA_ROOT");
	if (access(root, F_OK) == 0)
		chdir(root);
	(void)config_changes();
	warthog_log("INFO", "PASS: headless config (data_root=%s, interpolation=%d)",
		platform_data_root(), config_boolean("display.interpolation"));
	physical_memory_allocate();
	physical_memory_verify();
	regions[0] = physical_memory_get_game_state_base_address();
	regions[1] = physical_memory_get_tag_cache_base_address();
	regions[2] = physical_memory_get_texture_cache_base_address();
	regions[3] = physical_memory_get_sound_cache_base_address();
	if (!xbox_address_space_base)
		failed = 1;
	for (int i = 0; i < 4; ++i)
		if (!regions[i] || xbox_pointer(xbox_address(regions[i])) != regions[i])
			failed = 1;
	warthog_log(failed ? "ERROR" : "INFO", "%s: headless address translation",
		failed ? "FAIL" : "PASS");
	cseries_initialize();
	errors_initialize();
	real_math_initialize();
	if (!warthog_verify_deterministic_math())
	{
		failed = 1;
		warthog_log("ERROR", "FAIL: headless deterministic math");
	}
	else
		warthog_log("INFO", "PASS: headless deterministic math");
	if (!warthog_verify_simulation_ticks())
	{
		failed = 1;
		warthog_log("ERROR", "FAIL: headless 30 Hz simulation");
	}
	else
		warthog_log("INFO", "PASS: headless 30 Hz simulation");

	if (snprintf(ui_path, sizeof(ui_path), "%s/maps/ui.map", root) >= sizeof(ui_path))
	{
		failed = 1;
		warthog_log("ERROR", "FAIL: headless ui.map path too long");
	}
	else if (access(ui_path, R_OK) != 0)
	{
		failed = 1;
		warthog_log("ERROR", "FAIL: headless ui.map not present at %s", ui_path);
	}
	else
	{
		long scnr, count = 0;
		unsigned long checksum = 0;
		struct tag_iterator it;
		/* tag_files_open/close already initialize/dispose the cache. */
		tag_files_open();
		scnr = scenario_tags_load("ui");
		if (scnr != NONE)
		{
			checksum = tag_groups_checksum();
			tag_iterator_new(&it, NONE);
			while (tag_iterator_next(&it) != NONE)
				++count;
			if (!tag_get('scnr', scnr) || !count || !checksum)
				failed = 1;
			else
				warthog_log("INFO", "PASS: headless ui.map loaded (tags=%ld, scnr=%#lx, checksum=%#lx)",
					(long)count, (unsigned long)scnr, (unsigned long)checksum);
			scenario_tags_unload();
		}
		else
			failed = 1;
		if (scnr == NONE || !count || !checksum)
			warthog_log("ERROR", "FAIL: headless ui.map load");
		tag_files_close();
	}
	failed |= check_gameplay_map(root, "bloodgulch.map", "levels\\test\\bloodgulch\\bloodgulch");
	failed |= check_gameplay_map(root, "a10.map", "levels\\a10\\a10");
	for (size_t i = 1; i < 10; ++i)
	{
		char file[32], scenario[64];
		const char *mission = switch2_campaign_mission_id(i);
		snprintf(file, sizeof(file), "%s.map", mission);
		snprintf(scenario, sizeof(scenario), "levels\\%s\\%s", mission, mission);
		failed |= check_gameplay_map(root, file, scenario);
	}
	thread_stop_all(200);
	nx2ExitCleanupNow();
	real_math_dispose();
	errors_dispose();
	cseries_dispose();
	physical_memory_free();
	platform_xbox_memory_reset_for_shutdown();
	xbox_heap_reset_for_shutdown();
	switch2_mman_shutdown();
	return failed;
}
