#ifndef WARTHOG_HEADLESS_ENGINE_CHECKS_H
#define WARTHOG_HEADLESS_ENGINE_CHECKS_H

#include <math.h>
#include <stdint.h>

static inline int warthog_verify_simulation_ticks(void)
{
	const float dt = 1.0f / TICKS_PER_SECOND;
	const int rates[] = {30, 60, 120};
	if (TICKS_PER_SECOND != 30 || dt != 1.0f / 30.0f)
		return 0;
	for (int i = 0; i < 3; ++i)
	{
		int accumulator = 0, ticks = 0;
		for (int frame = 0; frame < rates[i]; ++frame)
		{
			accumulator += TICKS_PER_SECOND;
			while (accumulator >= rates[i])
			{
				accumulator -= rates[i];
				++ticks;
			}
		}
		if (ticks != 30 || accumulator != 0)
			return 0;
	}
	return 1;
}

/* Include after the rewritten engine's cseries.h and math/real_math.h. */
static inline int warthog_verify_deterministic_math(void)
{
	uint32_t seed = 0x12345678U;
	uint32_t expected = seed;
	real_vector3d direction, repeated;
	real_matrix4x3 matrix;
	real_point3d point = { .x = 1.f, .y = 2.f, .z = 3.f }, result;

	for (int i = 0; i < 4; ++i)
	{
		expected = 1664525U * expected + 1013904223U;
		if (seed_random(&seed) != (expected >> 16) || seed != expected)
			return 0;
	}
	expected = seed;
	seed_random_direction3d(&seed, &direction);
	seed_random_direction3d(&expected, &repeated);
	if (seed != expected || direction.i != repeated.i ||
		direction.j != repeated.j || direction.k != repeated.k ||
		fabsf(direction.i * direction.i + direction.j * direction.j +
			direction.k * direction.k - 1.f) > 1e-6f)
		return 0;

	matrix4x3_rotation_from_angles(&matrix, 0.f, 0.f, 0.f);
	matrix4x3_transform_point(&matrix, &point, &result);
	return fabsf(result.x - 1.f) <= 1e-6f &&
		fabsf(result.y - 2.f) <= 1e-6f && fabsf(result.z - 3.f) <= 1e-6f;
}

#endif
