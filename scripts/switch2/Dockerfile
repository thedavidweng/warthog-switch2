# Reproducible Nintendo Switch 2 (Ounce / kaiHEN) toolchain container for Warthog for Switch 2.
# All pins match UPSTREAM.json at the repository root.
FROM docker.io/devkitpro/devkita64:20260219@sha256:1fc388c3a0d34bd2045a6dadcb1020e069d5f876a187fd705de14b4440c00282 AS base

ARG OUNCE_REPO_URL=https://pkg.ouncebrew.org
ARG OUNCE_GPG_SHA256=ada63e4b1d465b0e5768fcdab9042e760ef5c9d25e82c96df592ed2c37a753a3

RUN set -eux; \
    rm /etc/apt/sources.list.d/devkitpro.list; \
    apt-get update -qq; \
    apt-get install -y -qq --no-install-recommends ca-certificates curl gnupg zstd bzip2 ccache; \
    curl -fsSL https://apt.llvm.org/llvm-snapshot.gpg.key | gpg --dearmor -o /usr/share/keyrings/llvm.gpg; \
    echo "deb [signed-by=/usr/share/keyrings/llvm.gpg] http://apt.llvm.org/bookworm/ llvm-toolchain-bookworm-22 main" \
        > /etc/apt/sources.list.d/llvm.list; \
    apt-get update -qq; \
    apt-get install -y -qq --no-install-recommends clang-22 lld-22 llvm-22; \
    ln -sf /usr/bin/clang-22 /usr/local/bin/clang; \
    ln -sf /usr/bin/clang++-22 /usr/local/bin/clang++; \
    ln -sf /usr/bin/ld.lld-22 /usr/local/bin/ld.lld; \
    ln -sf /usr/bin/llvm-ar-22 /usr/local/bin/llvm-ar; \
    rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    curl -fsSL -o /tmp/ounce.gpg "${OUNCE_REPO_URL}/ounce.gpg"; \
    echo "${OUNCE_GPG_SHA256}  /tmp/ounce.gpg" | sha256sum -c -; \
    fpr="$(gpg --batch --with-colons --show-keys /tmp/ounce.gpg | awk -F: '/^fpr:/ { print $10; exit }')"; \
    dkp-pacman-key --add /tmp/ounce.gpg; \
    dkp-pacman-key --lsign-key "${fpr}"; \
    rm -f /tmp/ounce.gpg; \
    dkp-pacman -Q \
        switch-tools switch-pkg-config dkp-toolchain-vars \
        switch-sdl2 switch-curl switch-mbedtls switch-zlib switch-bzip2; \
    sed -i 's/^#RemoteFileSigLevel = Optional$/RemoteFileSigLevel = Required/' \
        "${DEVKITPRO}/pacman/etc/pacman.conf"; \
    grep -Fx 'RemoteFileSigLevel = Required' "${DEVKITPRO}/pacman/etc/pacman.conf"; \
    dkp-pacman -U --noconfirm --needed \
        --overwrite '/opt/devkitpro/libounce/*' \
        --overwrite '/opt/devkitpro/portlibs/switch2/*' \
        --overwrite /opt/devkitpro/switch2vars.sh \
        "${OUNCE_REPO_URL}/libounce-20261125-1-any.pkg.tar.zst" \
        "${OUNCE_REPO_URL}/libkaihen-20261123-1-any.pkg.tar.zst" \
        "${OUNCE_REPO_URL}/ouncevk-20261123.1-1-any.pkg.tar.zst"; \
    test "$(dkp-pacman -Q libounce)" = "libounce 20261125-1"; \
    test "$(dkp-pacman -Q libkaihen)" = "libkaihen 20261123-1"; \
    test "$(dkp-pacman -Q ouncevk)" = "ouncevk 20261123.1-1"; \
    dkp-pacman -Scc --noconfirm

# ---------- Builder stage for drakotools, drako3d 0.5.0, and uam2 / libuam2rt ----------
FROM base AS sdk-builder

ARG DRAKOTOOLS_COMMIT=6569f54518b6cea88ef59c1b9486b3d163d31313
ARG DRAKO3D_COMMIT=93ba2e7fbf2d3dc648f9f9f08e8b3aef4a70945d
ARG UAM2_COMMIT=11f145faa1c13bc78da3c8bea55160b4cd672e40

RUN set -eux; \
    apt-get update -qq; \
    apt-get install -y -qq --no-install-recommends \
        bison flex python3-pip pkg-config cbindgen spirv-tools \
        zlib1g-dev libzstd-dev libexpat1-dev libclang-22-dev; \
    apt-get install -y -qq --no-install-recommends -t bookworm-backports libdrm-dev; \
    pip3 install --no-cache-dir --break-system-packages 'meson>=1.7,<2' mako pyyaml; \
    rm -rf /var/lib/apt/lists/*

# 1. drakotools -> /usr/local/bin/{drakodef,drakomme}
RUN set -eux; \
    git init -q /tmp/drakotools; \
    git -C /tmp/drakotools fetch -q --depth 1 https://github.com/ouncebrew/drakotools.git "${DRAKOTOOLS_COMMIT}"; \
    git -C /tmp/drakotools checkout -q FETCH_HEAD; \
    meson setup /tmp/drakotools/build /tmp/drakotools --prefix=/usr/local; \
    ninja -C /tmp/drakotools/build install; \
    rm -rf /tmp/drakotools

# 2. drako3d 0.5.0 (Ampere) -> /opt/devkitpro/libounce/{include,lib}
RUN set -eux; \
    git init -q /tmp/drako3d; \
    git -C /tmp/drako3d fetch -q --depth 1 https://github.com/ouncebrew/drako3d.git "${DRAKO3D_COMMIT}"; \
    git -C /tmp/drako3d checkout -q FETCH_HEAD; \
    DEVKITPRO=/opt/devkitpro make -C /tmp/drako3d GPU_ARCH=ampere -j"$(nproc)" install; \
    test -f /opt/devkitpro/libounce/include/drako3d.h; \
    test -f /opt/devkitpro/libounce/lib/libdrako3d.a; \
    test -f /opt/devkitpro/libounce/lib/libdrako3dd.a; \
    rm -rf /tmp/drako3d

# 3. Rust + bindgen-cli for Mesa 26.3.0 NAK inside uam2
ENV RUSTUP_HOME=/opt/rustup CARGO_HOME=/opt/cargo PATH=/opt/cargo/bin:${PATH}
RUN set -eux; \
    curl -fsSL https://sh.rustup.rs | sh -s -- -y --default-toolchain stable --profile minimal -c rust-src; \
    LIBCLANG_PATH=/usr/lib/llvm-22/lib cargo install --locked bindgen-cli

# 4. uam2 (host CLI + Switch 2 libuam2rt.a with uam2rt_compile_glsl)
RUN pip3 install --no-cache-dir --break-system-packages packaging && cargo install --locked cbindgen
COPY port/switch2/uam2.patch /tmp/uam2.patch
RUN set -eux; \
    git init -q /tmp/uam2; \
    git -C /tmp/uam2 fetch -q --depth 1 https://github.com/ouncebrew/uam2.git "${UAM2_COMMIT}"; \
    git -C /tmp/uam2 checkout -q FETCH_HEAD; \
    git -C /tmp/uam2 apply /tmp/uam2.patch; \
    LIBCLANG_PATH=/usr/lib/llvm-22/lib meson setup /tmp/uam2/build-host /tmp/uam2 --prefix=/usr/local; \
    ninja -C /tmp/uam2/build-host install; \
    test -x /usr/local/bin/uam2

RUN set -eux; \
    sed -i 's|-exec cp {} "\$sysroot/lib/rustlib/\$tgt/lib/" +|-exec cp -t "$sysroot/lib/rustlib/$tgt/lib/" {} +|' /tmp/uam2/cross/rust/build-std-sysroot.sh; \
    sed -i 's|#include "main/consts_exts.h"|#include <climits>\n#include "main/consts_exts.h"|' /tmp/uam2/subprojects/mesa/src/compiler/glsl/glsl_lexer.ll; \
    (cd /tmp/uam2 && DEVKITPRO=/opt/devkitpro ./cross/rust/build-std-sysroot.sh); \
    LIBCLANG_PATH=/usr/lib/llvm-22/lib meson setup /tmp/uam2/build-switch2 /tmp/uam2 \
        --cross-file /tmp/uam2/cross/switch2.cross -Druntime=true; \
    ninja -C /tmp/uam2/build-switch2 install; \
    test -f /opt/devkitpro/portlibs/switch2/include/uam2rt.h; \
    test -f /opt/devkitpro/portlibs/switch2/lib/libuam2rt.a; \
    rm -rf /tmp/uam2 /tmp/uam2.patch

# ---------- Final toolchain image ----------
FROM base

COPY --from=sdk-builder /usr/local/bin/drakodef /usr/local/bin/drakodef
COPY --from=sdk-builder /usr/local/bin/drakomme /usr/local/bin/drakomme
COPY --from=sdk-builder /usr/local/bin/uam2 /usr/local/bin/uam2
COPY --from=sdk-builder /opt/devkitpro/libounce/ /opt/devkitpro/libounce/
COPY --from=sdk-builder /opt/devkitpro/portlibs/switch2/ /opt/devkitpro/portlibs/switch2/

ENV DEVKITPRO=/opt/devkitpro \
    DEVKITA64=/opt/devkitpro/devkitA64 \
    PATH=/opt/devkitpro/devkitA64/bin:/opt/devkitpro/tools/bin:${PATH}

RUN { \
      aarch64-none-elf-g++ --version | head -1; \
      clang --version | head -1; \
      uam2 --version; \
      dkp-pacman -Q libounce libkaihen ouncevk devkitA64 switch-sdl2 switch-curl switch-mbedtls; \
      printf "drako3d %s\nuam2 %s\ndrakotools %s\n" \
        "93ba2e7fbf2d3dc648f9f9f08e8b3aef4a70945d" \
        "11f145faa1c13bc78da3c8bea55160b4cd672e40" \
        "6569f54518b6cea88ef59c1b9486b3d163d31313"; \
    } > /opt/devkitpro/warthog-switch2-toolchain.txt
WORKDIR /src
