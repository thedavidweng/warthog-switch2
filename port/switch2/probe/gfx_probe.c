/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <switch.h>
#include <deko3d.h>
#include <uam2rt.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include "warthog_build.h"
#include "gfx_probe_shaders.h"

#define SIZE 64
#define CMD_SIZE 0x100000
#define CODE_SIZE 0x100000

static FILE *log_file;
static DkDevice device;
static DkQueue queue;
static DkCmdBuf commands;
static DkMemBlock cmd_mem, code_mem, data_mem, texture_mem, texture2_mem, target_mem, read_mem, desc_mem, swap_mem;
static DkSwapchain swapchain;
static DkImage swap_images[2];
static DkImage const *swap_image_ptrs[] = {&swap_images[0], &swap_images[1]};

static void debug_callback(void *user, const char *context, DkResult result, const char *message)
{
	(void)user;
	fprintf(log_file, "gpu.debug.context=%s result=%d message=%s\n",
		context ? context : "", (int)result, message ? message : "");
	fflush(log_file);
}

static DkMemBlock block(uint32_t size, uint32_t flags)
{
	DkMemBlockMaker maker;
	dkMemBlockMakerDefaults(&maker, device, (size + DK_MEMBLOCK_ALIGNMENT - 1) & ~(DK_MEMBLOCK_ALIGNMENT - 1));
	maker.flags = flags;
	return dkMemBlockCreate(&maker);
}

struct dksh_header {
	uint32_t magic, header_size, control_size, code_size, programs_offset, program_count;
};

static int compile_shader(DkShader *shader, const char *source, Uam2rtStage stage, uint32_t *offset)
{
	size_t size = 0;
	char *message = NULL;
	void *binary = uam2rt_compile_glsl(source, stage, &size, &message);
	fprintf(log_file, "shader.%d.size=%zu\nshader.%d.log=%s\n", stage, size, stage, message ? message : "");
	free(message);
	if (!binary || size < sizeof(struct dksh_header)) {
		free(binary);
		return 0;
	}
	struct dksh_header h;
	memcpy(&h, binary, sizeof(h));
	*offset = (*offset + DK_SHADER_CODE_ALIGNMENT - 1) & ~(DK_SHADER_CODE_ALIGNMENT - 1);
	if (h.magic != 0x48534b44 || h.control_size > size || h.code_size > size - h.control_size ||
	    *offset > CODE_SIZE - DK_SHADER_CODE_UNUSABLE_SIZE ||
	    h.code_size > CODE_SIZE - DK_SHADER_CODE_UNUSABLE_SIZE - *offset) {
		free(binary);
		return 0;
	}
	memcpy((uint8_t *)dkMemBlockGetCpuAddr(code_mem) + *offset, (uint8_t *)binary + h.control_size, h.code_size);
	DkShaderMaker maker;
	dkShaderMakerDefaults(&maker, code_mem, *offset);
	maker.control = binary;
	dkShaderInitialize(shader, &maker);
	*offset += h.code_size;
	free(binary);
	return dkShaderIsValid(shader);
}

static int image_create(DkImage *image, DkMemBlock *memory, uint32_t width, uint32_t height, uint32_t flags)
{
	DkImageLayoutMaker maker;
	DkImageLayout layout;
	dkImageLayoutMakerDefaults(&maker, device);
	maker.flags = flags;
	maker.format = DkImageFormat_RGBA8_Unorm;
	maker.dimensions[0] = width;
	maker.dimensions[1] = height;
	dkImageLayoutInitialize(&layout, &maker);
	*memory = block(dkImageLayoutGetSize(&layout) + dkImageLayoutGetAlignment(&layout),
		DkMemBlockFlags_GpuCached | DkMemBlockFlags_Image);
	if (!*memory)
		return 0;
	dkImageInitialize(image, &layout, *memory, 0);
	return 1;
}

static int run_probe(void)
{
	fprintf(log_file, "step=device\n");
	DkDeviceMaker dm;
	dkDeviceMakerDefaults(&dm);
	dm.cbDebug = debug_callback;
	dm.flags = DkDeviceFlags_DepthZeroToOne | DkDeviceFlags_OriginUpperLeft;
	device = dkDeviceCreate(&dm);
	if (!device) return 0;
	DkQueueMaker qm;
	dkQueueMakerDefaults(&qm, device);
	qm.flags = DkQueueFlags_Graphics;
	queue = dkQueueCreate(&qm);
	cmd_mem = block(CMD_SIZE, DkMemBlockFlags_CpuUncached | DkMemBlockFlags_GpuCached);
	code_mem = block(CODE_SIZE, DkMemBlockFlags_CpuUncached | DkMemBlockFlags_GpuCached | DkMemBlockFlags_Code);
	data_mem = block(0x8000, DkMemBlockFlags_CpuCached | DkMemBlockFlags_GpuCached);
	read_mem = block(SIZE * SIZE * 4, DkMemBlockFlags_CpuUncached | DkMemBlockFlags_GpuCached);
	desc_mem = block(0x1000, DkMemBlockFlags_CpuUncached | DkMemBlockFlags_GpuCached);
	if (!queue || !cmd_mem || !code_mem || !data_mem || !read_mem || !desc_mem) return 0;
	DkCmdBufMaker cm;
	dkCmdBufMakerDefaults(&cm, device);
	commands = dkCmdBufCreate(&cm);
	if (!commands) return 0;

	fprintf(log_file, "step=compile\n");
	if (!uam2rt_init()) return 0;
	DkShader shaders[2];
	uint32_t offset = 0;
	int compiled = compile_shader(&shaders[0], vertex_glsl, Uam2rtStage_Vertex, &offset) &&
		compile_shader(&shaders[1], fragment_glsl, Uam2rtStage_Fragment, &offset);
	uam2rt_exit();
	if (!compiled) return 0;

	fprintf(log_file, "step=offscreen\n");
	DkImage texture, texture2, target;
	if (!image_create(&texture, &texture_mem, SIZE, SIZE, DkImageFlags_Usage2DEngine) ||
	    !image_create(&texture2, &texture2_mem, SIZE, SIZE, DkImageFlags_Usage2DEngine) ||
	    !image_create(&target, &target_mem, SIZE, SIZE, DkImageFlags_UsageRender | DkImageFlags_Usage2DEngine))
		return 0;
	DkImageView texture_view, texture2_view, target_view;
	dkImageViewDefaults(&texture_view, &texture);
	dkImageViewDefaults(&texture2_view, &texture2);
	dkImageViewDefaults(&target_view, &target);
	DkSampler sampler;
	dkSamplerDefaults(&sampler);
	uint8_t *descriptors = dkMemBlockGetCpuAddr(desc_mem);
	dkImageDescriptorInitialize((DkImageDescriptor *)descriptors, &texture_view, false, false);
	dkImageDescriptorInitialize((DkImageDescriptor *)descriptors + 1, &texture_view, false, false);
	dkSamplerDescriptorInitialize((DkSamplerDescriptor *)(descriptors + 0x800), &sampler);
	dkSamplerDescriptorInitialize((DkSamplerDescriptor *)(descriptors + 0x800) + 1, &sampler);

	uint8_t *data = dkMemBlockGetCpuAddr(data_mem);
	memset(data, 0, 0x8000);
	float *constants = (float *)data;
	for (int i = 0; i < 4; ++i) constants[i * 4 + i] = 1.0f;
	for (int i = 0; i < 4; ++i) constants[16 + i] = 1.0f;
	static const float vertices[12] = {-1,-1,0.5f,1, 3,-1,0.5f,1, -1,3,0.5f,1};
	memcpy(data + 0x2000, vertices, sizeof(vertices));
	for (int i = 0; i < SIZE * SIZE; ++i) {
		data[0x4000 + i * 4] = 255;
		data[0x4000 + i * 4 + 3] = 128;
	}
	if (dkMemBlockFlushCpuCache(data_mem, 0, 0x8000) != DkResult_Success) return 0;

	dkCmdBufAddMemory(commands, cmd_mem, 0, CMD_SIZE);
	dkCmdBufBarrier(commands, DkBarrier_None, DkInvalidateFlags_Descriptors);
	DkGpuAddr data_gpu = dkMemBlockGetGpuAddr(data_mem);
	DkCopyBuf upload = {data_gpu + 0x4000, 0, 0};
	DkImageRect rect = {0, 0, 0, SIZE, SIZE, 1};
	dkCmdBufCopyBufferToImage(commands, &upload, &texture_view, &rect, 0);
	dkCmdBufBarrier(commands, DkBarrier_Full, DkInvalidateFlags_Image);
	DkGpuAddr desc_gpu = dkMemBlockGetGpuAddr(desc_mem);
	dkCmdBufBindImageDescriptorSet(commands, desc_gpu, 2);
	dkCmdBufBindSamplerDescriptorSet(commands, desc_gpu + 0x800, 2);
	DkResHandle handle = dkMakeTextureHandle(0, 0);
	dkCmdBufBindTextures(commands, DkStage_Fragment, 0, &handle, 1);
	dkCmdBufBindUniformBuffer(commands, DkStage_Vertex, 0, data_gpu, 3072);
	dkCmdBufBindUniformBuffer(commands, DkStage_Fragment, 0, data_gpu + 0x1000, 144);
	const DkImageView *views[] = {&target_view};
	dkCmdBufBindRenderTargets(commands, views, 1, NULL);
	DkViewport viewport = {0, 0, SIZE, SIZE, 0, 1};
	DkScissor scissor = {0, 0, SIZE, SIZE};
	dkCmdBufSetViewports(commands, 0, &viewport, 1);
	dkCmdBufSetScissors(commands, 0, &scissor, 1);
	dkCmdBufClearColorFloat(commands, 0, DkColorMask_RGBA, 0, 0, 0, 0);
	const DkShader *shader_ptrs[] = {&shaders[0], &shaders[1]};
	dkCmdBufBindShaders(commands, DkStageFlag_GraphicsMask, shader_ptrs, 2);
	DkRasterizerState raster;
	dkRasterizerStateDefaults(&raster);
	raster.cullMode = DkFace_None;
	dkCmdBufBindRasterizerState(commands, &raster);
	DkColorState color;
	dkColorStateDefaults(&color);
	dkColorStateSetBlendEnable(&color, 0, true);
	dkCmdBufBindColorState(commands, &color);
	DkBlendState blend;
	dkBlendStateDefaults(&blend);
	dkCmdBufBindBlendStates(commands, 0, &blend, 1);
	DkColorWriteState writes;
	dkColorWriteStateDefaults(&writes);
	dkCmdBufBindColorWriteState(commands, &writes);
	DkDepthStencilState depth;
	dkDepthStencilStateDefaults(&depth);
	depth.depthTestEnable = false;
	depth.depthWriteEnable = false;
	dkCmdBufBindDepthStencilState(commands, &depth);
	DkVtxAttribState attribute = {0};
	attribute.size = DkVtxAttribSize_4x32;
	attribute.type = DkVtxAttribType_Float;
	DkVtxBufferState buffer = {sizeof(float) * 4, 0};
	dkCmdBufBindVtxAttribState(commands, &attribute, 1);
	dkCmdBufBindVtxBufferState(commands, &buffer, 1);
	dkCmdBufBindVtxBuffer(commands, 0, data_gpu + 0x2000, sizeof(vertices));
	dkCmdBufDraw(commands, DkPrimitive_Triangles, 3, 1, 0, 0);
	dkCmdBufBarrier(commands, DkBarrier_Fragments, 0);
	DkCopyBuf readback = {dkMemBlockGetGpuAddr(read_mem), 0, 0};
	dkCmdBufCopyImageToBuffer(commands, &target_view, &rect, &readback, 0);
	dkQueueSubmitCommands(queue, dkCmdBufFinishList(commands));
	DkFence fence;
	dkQueueSignalFence(queue, &fence, true);
	DkResult result = dkFenceWait(&fence, 2000000000LL);
	if (result != DkResult_Success) {
		fprintf(log_file, "fence.result=%d\n", result);
		return 0;
	}
	const uint8_t *pixel = (const uint8_t *)dkMemBlockGetCpuAddr(read_mem) + (SIZE * (SIZE / 2) + SIZE / 2) * 4;
	fprintf(log_file, "pixel.rgba=%u,%u,%u,%u\n", pixel[0], pixel[1], pixel[2], pixel[3]);
	int passed = abs((int)pixel[0] - 128) <= 2 && pixel[1] <= 2 && pixel[2] <= 2 &&
		abs((int)pixel[3] - 128) <= 2;
	if (dkQueueIsInErrorState(queue)) return 0;

	/* The fence makes slot zero safe to rewrite before recording its reuse. */
	fprintf(log_file, "step=descriptor_reuse\n");
	for (int i = 0; i < SIZE * SIZE; ++i) {
		data[0x4000 + i * 4] = 0;
		data[0x4000 + i * 4 + 1] = 255;
	}
	if (dkMemBlockFlushCpuCache(data_mem, 0x4000, SIZE * SIZE * 4) != DkResult_Success) return 0;
	dkImageDescriptorInitialize((DkImageDescriptor *)descriptors, &texture2_view, false, false);
	dkSamplerDescriptorInitialize((DkSamplerDescriptor *)(descriptors + 0x800), &sampler);
	dkCmdBufClear(commands);
	dkCmdBufAddMemory(commands, cmd_mem, 0, CMD_SIZE);
	dkCmdBufBarrier(commands, DkBarrier_None, DkInvalidateFlags_Descriptors);
	dkCmdBufCopyBufferToImage(commands, &upload, &texture2_view, &rect, 0);
	dkCmdBufBarrier(commands, DkBarrier_Full, DkInvalidateFlags_Image);
	dkCmdBufBindImageDescriptorSet(commands, desc_gpu, 2);
	dkCmdBufBindSamplerDescriptorSet(commands, desc_gpu + 0x800, 2);
	dkCmdBufBindTextures(commands, DkStage_Fragment, 0, &handle, 1);
	dkCmdBufBindRenderTargets(commands, views, 1, NULL);
	dkCmdBufClearColorFloat(commands, 0, DkColorMask_RGBA, 0, 0, 0, 0);
	dkCmdBufDraw(commands, DkPrimitive_Triangles, 3, 1, 0, 0);
	dkCmdBufBarrier(commands, DkBarrier_Fragments, 0);
	dkCmdBufCopyImageToBuffer(commands, &target_view, &rect, &readback, 0);
	dkQueueSubmitCommands(queue, dkCmdBufFinishList(commands));
	dkQueueSignalFence(queue, &fence, true);
	result = dkFenceWait(&fence, 2000000000LL);
	if (result != DkResult_Success) {
		fprintf(log_file, "reuse.fence.result=%d\n", result);
		return 0;
	}
	fprintf(log_file, "reuse.pixel.rgba=%u,%u,%u,%u\n", pixel[0], pixel[1], pixel[2], pixel[3]);
	passed = passed && pixel[0] <= 2 && abs((int)pixel[1] - 128) <= 2 && pixel[2] <= 2 &&
		abs((int)pixel[3] - 128) <= 2;
	if (dkQueueIsInErrorState(queue)) return 0;

	fprintf(log_file, "step=present\n");
	u32 width = 0, height = 0;
	if (R_FAILED(nwindowGetDimensions(nwindowGetDefault(), &width, &height)) || !width || !height) return 0;
	fprintf(log_file, "display.width=%u\ndisplay.height=%u\n", width, height);
	DkImageLayoutMaker sm;
	DkImageLayout sl;
	dkImageLayoutMakerDefaults(&sm, device);
	sm.flags = DkImageFlags_UsageRender | DkImageFlags_UsagePresent | DkImageFlags_Usage2DEngine;
	sm.format = DkImageFormat_RGBA8_Unorm;
	sm.dimensions[0] = width;
	sm.dimensions[1] = height;
	dkImageLayoutInitialize(&sl, &sm);
	uint32_t image_size = (dkImageLayoutGetSize(&sl) + dkImageLayoutGetAlignment(&sl) - 1) &
		~(dkImageLayoutGetAlignment(&sl) - 1);
	swap_mem = block(image_size * 2, DkMemBlockFlags_GpuCached | DkMemBlockFlags_Image);
	if (!swap_mem) return 0;
	for (int i = 0; i < 2; ++i) dkImageInitialize(&swap_images[i], &sl, swap_mem, i * image_size);
	DkSwapchainMaker sw;
	dkSwapchainMakerDefaults(&sw, device, nwindowGetDefault(), swap_image_ptrs, 2);
	swapchain = dkSwapchainCreate(&sw);
	if (!swapchain) return 0;
	int slot = dkQueueAcquireImage(queue, swapchain);
	if (slot < 0) return 0;
	DkImageView swap_view;
	dkImageViewDefaults(&swap_view, &swap_images[slot]);
	const DkImageView *swap_views[] = {&swap_view};
	dkCmdBufClear(commands);
	dkCmdBufAddMemory(commands, cmd_mem, 0, CMD_SIZE);
	dkCmdBufBarrier(commands, DkBarrier_None, DkInvalidateFlags_Descriptors);
	dkCmdBufBindRenderTargets(commands, swap_views, 1, NULL);
	DkViewport swap_viewport = {0, 0, (float)width, (float)height, 0, 1};
	DkScissor swap_scissor = {0, 0, width, height};
	dkCmdBufSetViewports(commands, 0, &swap_viewport, 1);
	dkCmdBufSetScissors(commands, 0, &swap_scissor, 1);
	dkCmdBufClearColorFloat(commands, 0, DkColorMask_RGBA, passed ? 0 : 1, passed ? 1 : 0, 0, 1);
	dkQueueSubmitCommands(queue, dkCmdBufFinishList(commands));
	dkQueuePresentImage(queue, swapchain, slot);
	fprintf(log_file, "queue.error=%d\nreadback.pass=%d\n", dkQueueIsInErrorState(queue), passed);
	return passed && !dkQueueIsInErrorState(queue);
}

int main(void)
{
	mkdir("sdmc:/switch", 0777);
	mkdir("sdmc:/switch/warthog", 0777);
	mkdir("sdmc:/switch/warthog/logs", 0777);
	log_file = fopen("sdmc:/switch/warthog/logs/gfx_probe.log", "w");
	if (!log_file) return 1;
	setvbuf(log_file, NULL, _IOLBF, 0);
	fprintf(log_file, "firmware=0x%x\napplet_type=%d\ndrako3d.version=%s\ndrako3d.commit=%s\nuam2.commit=%s\n",
		hosversionGet(), appletGetAppletType(), WARTHOG_SWITCH2_DRAKO3D_VERSION,
		WARTHOG_SWITCH2_DRAKO3D_COMMIT, WARTHOG_SWITCH2_UAM2_COMMIT);
	int passed = run_probe();
	fprintf(log_file, "step=cleanup\n");
	if (queue) {
		if (!dkQueueIsInErrorState(queue)) dkQueueWaitIdle(queue);
		int error = dkQueueIsInErrorState(queue);
		fprintf(log_file, "queue.final_error=%d\n", error);
		if (error) passed = 0;
	}
	if (swapchain) dkSwapchainDestroy(swapchain);
	if (commands) dkCmdBufDestroy(commands);
	if (swap_mem) dkMemBlockDestroy(swap_mem);
	if (desc_mem) dkMemBlockDestroy(desc_mem);
	if (read_mem) dkMemBlockDestroy(read_mem);
	if (target_mem) dkMemBlockDestroy(target_mem);
	if (texture2_mem) dkMemBlockDestroy(texture2_mem);
	if (texture_mem) dkMemBlockDestroy(texture_mem);
	if (data_mem) dkMemBlockDestroy(data_mem);
	if (code_mem) dkMemBlockDestroy(code_mem);
	if (cmd_mem) dkMemBlockDestroy(cmd_mem);
	if (queue) dkQueueDestroy(queue);
	if (device) dkDeviceDestroy(device);
	nwindowReleaseVi2Layer(nwindowGetDefault());
	appletSetCpuBoostMode(ApmCpuBoostMode_Normal);
	fprintf(log_file, "probe.pass=%d\n", passed);
	fclose(log_file);
	return passed ? 0 : 1;
}
