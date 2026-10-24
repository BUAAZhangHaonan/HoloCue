# Viser 1.1.1 绘制与相机协议修复

本目录保存修复源码和真实 Three.js 回归测试，保持 Viser 1.1.1 与原锁定依赖。相机协议的 Python 与客户端文件必须成套安装并重启本次拥有的 viewer。alpha_r1 的已完成构建与实际绘制证据保留在文末；不能用旧阶段通过代替相机协议修复的验收。

## 来源与许可证

GaussianSplatsHelpers.ts 的来源为[官方 v1.1.1 源码](https://github.com/viser-project/viser/blob/v1.1.1/src/viser/client/src/Splatting/GaussianSplatsHelpers.ts)，原文件 SHA256 为 e1bdf6a2a468470306ec8f045fd9f8d7c4458fac9bf567cd171c29983b6c2147。GaussianSplats.tsx 原件来自本次实际安装的 Viser 1.1.1，SHA256 为 0401d07715a8d167b8dedd4ae7e891b30e55ebc6512fb80edc07a61aee59fa14，与此前隔离副本一致。r2 的安装源输入已含前一 Helpers 修复，不能标为未经修改的上游检出；逐文件输入清单保留这一来源边界。

许可证原文保存在 LICENSE，与官方 v1.1.1 tag 及安装包中的 Apache 2.0 许可证一致。安装包 METADATA 将许可证标为 MIT，与两份原文不一致；本补丁保留实际许可证原文和上游来源。

## 有效设计

GaussianSplatsHelpers.ts 有三项修改：

- 保留正透明度的小点，不再使用 weightedDeterminant < 0.25 整点剔除。此前旋钮场景的实际输入中全部 6000 点落入该尺寸近似剔除范围；不改中心、协方差、颜色、透明度、N、σ 或解析响应参数。
- quad 顶点补入零 Z，提供三分量 position，满足 Three.js 包围球计算要求。shader 使用的 XY 不变。GaussianSplatsHelpers.test.ts 使用真实 Three.js 几何检查包围球有限，不替代浏览器像素验证。
- 保留支持域内的正透明度片元，将 B < 0.01 剔除改为 B <= 0.0。真实暂停会话中远景 B 的 5000 个点打包后透明度均为 1/255，旧阈值会全部丢弃。保留 A < -4.0 的既有支持域，以及中心、协方差、颜色、RGBA8 打包、N、σ 和解析响应参数；没有通过放大透明度改变响应模型。

GaussianSplats.tsx 有三项相机绘制修改：

- 在 mesh 的 onBeforeRender 调用现有 updateCamera。Three 先展开场景/相机世界矩阵，再调用该回调，随后上传 uniforms 与 DataTexture；普通帧、同步 resize 的直接 render 和虚拟相机 render 均经过此入口。useFrame 仅保留过渡动画。
- projection 在同次调用计算并写入当前 material，缓存包含 renderer 的实际 reversed-depth 模式；Gaussian 数量变化重建 material 时也写入缓存矩阵。投影宽高比使用 camera.aspect，与实体相机一致；viewport uniform 使用 getCurrentViewport 的整数物理像素宽高。DPR 舍入可能改变物理宽高比，不能用它重造相机投影。shader 用投影定位中心，再以物理 viewport 换算像素焦距和椭圆范围。
- 设置 frustumCulled=false。池化 quad 的 CPU 包围球不表示 shader 中全部 Gaussian 中心，不能用它提前跳过绘制及相机更新；实际提示仍由既有 shader 裁剪，不改提示数组或响应参数。

虚拟截图保留 render 前的显式 blockingSort：Three 的几何 attribute 上传早于 onBeforeRender，不能把阻塞排序移入该回调。普通绘制沿用异步排序，worker 结果仅按数量检查的既有边界未扩改，不能宣称首帧透明合成顺序完全同步。alpha/aspect 历史阶段未触发虚拟 get_render，仅完成源码时序兼容分析。下述 runtime camera 补丁增加当前缓冲的就绪检查及每次取图的同步排序；真实浏览器取图需独立验收。

## runtime camera 取图接口

`ClientHandle.get_render()` 调用连接客户端的 Three/WebGL 场景相机，返回 numpy 图像，不读取网页 DOM。`near`、`far`、`projection_aspect` 默认取当前会话相机；显式传入这些字段及 `wxyz`、`position`、`fov` 可绑定应用已冻结的观测。输出整数尺寸不反推相机投影。`timeout` 必须为正有限秒数，默认 30 秒，Python 等待和客户端等待均有限；请求 UUID 保持并发响应关联。

应用必须在 worker 中、锁和 `client.atomic()` 之外调用，并传入本次观测需要的全部 GLB 绝对节点路径 `expected_node_names=("/scene/model", ...)`。每个路径检查当前消息的 GLB byte 对象、实际挂载节点及其 LoadingManager 的纹理错误；旧加载结果不能满足新资源。环境图同时检查当前源、加载成功及实际安装到 scene；Gaussian 同步排序器须安装当前缓冲并完成既有渐入。就绪等待不依赖固定 sleep，也不修改点数、协方差、透明度、支持域或排序算法。这个屏障不覆盖未声明的 GLB、ImageMessage 或独立 background-image 解码；跨 broadcast/client 两个发送缓冲的原有顺序边界仍在，应用当前会话资产应通过对应 client 的同一消息链更新。

`transport_format="png", transparent_background=False` 直接在不透明白底绘制，PNG 解码仍返回 `(H,W,4)` RGBA；应用可验证 alpha 全为 255 后取得 RGB。`transparent_background=None` 保留 PNG 透明及 JPEG 白底旧语义，True 只适用于 PNG。没有自动改画质、尺寸或截图回退；资源错误、空编码、超时和断连均抛出异常。捕获参数/会话版本和图像提交由应用层记录，此 SDK 不伪装成服务器无浏览器渲染。

`CAMERA_RENDER.patch` 仅保存 MessageHandler.tsx 与 GlbLoaderUtils.ts 的增量。这两个基线文件的 SHA-256 和字节数均与已安装 Viser 1.1.1 分发包的 `dist-info/RECORD` 一致；没有与官方 Git 源码对照。`CAMERA_RENDER.inputs.json` 保存两个输入及补丁结果摘要和对应 RECORD 条目。安装元数据记录 `INSTALLER=pip`、wheel tag 为 `py3-none-any`，但没有 `direct_url.json`，因此未确定原安装索引或 wheel 下载地址。可从内容匹配的 Viser 1.1.1 分发包成员或已归档的精确输入恢复这两个基线，必须通过摘要检查；版本号本身不替代校验。安装包其他文件所含的历史 HoloCue 修复仍按各自来源记录。新的小型 cameraCapture 模块和测试跟随 `viser/` overlay，已有 Python/TypeScript 快照继续由项目统一格式化入口处理。

取图沿用同一 WebGL renderer，临时改变绘图缓冲尺寸但不改 CSS 布局；在实际 canvas 上发出冒泡事件 `viser:camera-capture-active`，`detail={render_uuid}`，同时设置 `dataset.viserCameraCaptureActive="true"`。只有交互相机在默认 framebuffer 完成正常 `scene.onAfterRender` 后才发 `viser:camera-capture-restored` 并设为 false。异常时也恢复尺寸、clear color/alpha 和排序索引。录像必须从正常相机完成帧复制到独立固定尺寸 canvas，并跳过 active 区间；直接对主 canvas 自动 captureStream 仍可能记录临时捕获帧。事件不承诺无成本，也不减少正常任务时钟。

局部验证入口：`test_camera_capture.py` 在完整候选包的 PYTHONPATH 下测真实 SDK 请求/解码、错误与 UUID 关联；`cameraCapture.test.ts` 测 Three 相机投影和就绪/超时状态；`cameraGlbReadiness.test.ts` 测实际 useGlbLoader 生命周期与 LoadingManager 纹理失败。它们不代替真实浏览器像素、录像隔离和 VLM 图像输入验收。

## 可复现构建

viser/ 子目录按安装包相对路径保存协议、相机控制、环境和取图模块。CameraControls.tsx 在 ViewerCameraMessage 中发送真实 three_camera.aspect，字段名为 projection_aspect；image_width 和 image_height 继续表示实际绘图缓冲的整数尺寸。_messages.py 与 WebsocketMessages.ts 声明同一必需字段，_viser.py 保存此值并通过 CameraHandle.aspect 返回。DPR 舍入后的缓冲尺寸比不能代替投影比例。旧客户端不支持这个必需字段，部署时关闭本次旧连接，成套安装两个 Python 文件及新客户端并重启 viewer，不增加旧协议回退。

Blender 消费端使用固定整数输出尺寸及像素宽高比补偿，保持相同投影。verify_consumed 读取实际 calc_matrix_camera 的横纵系数并与 live 相机比较，误差上限仍为 2e-5。深度约定依引擎而异，横纵系数一致不宣称全部矩阵或像素完全相同。

在项目根目录执行，选择未使用的新目录并保留历史证据。下列命令显式设置项目 Python、输出目录及项目内临时目录、缓存、浏览器和 Python bytecode 路径，不依赖未跟踪的历史 task_env 文件。相对路径先转为绝对路径，RUN_DIR 必须位于项目内；Python 虚拟环境入口不解引用符号链接。Viser 安装目录由所选 Python 查询，适用于该环境实际使用的 Python 版本。必须保留 viser/{client,_assets} 相对布局。当前整包安装源已经修复，应记录实际输入，不能将其整体标为原始上游。以下命令接受 CAMERA_RENDER 的两个文件均为已记录基线或均为已记录补丁结果的状态；前者应用补丁，后者不重复应用，其他状态一律拒绝。

~~~bash
set -euo pipefail
export HOLOCUE_ROOT="$PWD"
APP_PYTHON="${APP_PYTHON:-$HOLOCUE_ROOT/.venv-simulation/bin/python}"
case "$APP_PYTHON" in
  /*) ;;
  *) APP_PYTHON="$HOLOCUE_ROOT/$APP_PYTHON" ;;
esac
export APP_PYTHON
test -x "$APP_PYTHON"
RUN_DIR="${RUN_DIR:-$HOLOCUE_ROOT/runs/simulation/reconstructed}"
RUN_DIR="$("$APP_PYTHON" -B -c 'from pathlib import Path; import sys; project = Path(sys.argv[1]).resolve(); output = Path(sys.argv[2]).resolve(); assert output.is_relative_to(project), "RUN_DIR must remain inside the project"; print(output)' "$HOLOCUE_ROOT" "$RUN_DIR")"
export RUN_DIR
export CUDA_VISIBLE_DEVICES=""
export VISER_WORK="$HOLOCUE_ROOT/.work/viser-rebuild-next"
export VISER_LOG="$RUN_DIR/viser_rebuild_next"
test ! -e "$VISER_WORK"
test ! -e "$VISER_LOG"
export TMPDIR="$VISER_WORK/tmp"
export TMP="$TMPDIR" TEMP="$TMPDIR"
export XDG_CACHE_HOME="$VISER_WORK/cache"
export XDG_CONFIG_HOME="$VISER_WORK/config"
export XDG_DATA_HOME="$VISER_WORK/data"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPYCACHEPREFIX="$VISER_WORK/cache/pycache"
export NODE_COMPILE_CACHE="$VISER_WORK/cache/node"
export PLAYWRIGHT_BROWSERS_PATH="$HOLOCUE_ROOT/.work/browsers"
VISER_SOURCE="$("$APP_PYTHON" -B -c 'import importlib.util; from pathlib import Path; print(Path(importlib.util.find_spec("viser").origin).parent)')"
export VISER_SOURCE
test -d "$VISER_SOURCE"
mkdir -p "$VISER_WORK/viser" "$VISER_WORK/downloads" "$VISER_LOG" \
  "$TMPDIR" "$XDG_CACHE_HOME" "$XDG_CONFIG_HOME" "$XDG_DATA_HOME"
find "$VISER_SOURCE" -type f -print0 \
  | sort -z | xargs -0 sha256sum > "$VISER_LOG/installed_sources.sha256"
cp -a "$VISER_SOURCE/." "$VISER_WORK/viser/"
diff -qr "$VISER_SOURCE" "$VISER_WORK/viser"
cp -a scripts/patches/viser_1_1_1/viser/. "$VISER_WORK/viser/"
(
  cd "$VISER_WORK/viser/client"
  camera_patch_state="$("$APP_PYTHON" -B - "$HOLOCUE_ROOT/scripts/patches/viser_1_1_1/CAMERA_RENDER.inputs.json" <<'PY'
import hashlib, json, sys
from pathlib import Path
manifest = json.loads(Path(sys.argv[1]).read_text())
actual = {}
for name in manifest["sha256"]:
    source = Path(name).resolve()
    assert source.is_relative_to(Path.cwd()), name
    actual[name] = hashlib.sha256(source.read_bytes()).hexdigest()
if actual == manifest["sha256"]:
    print("baseline")
elif actual == manifest["patched_sha256"]:
    print("patched")
else:
    raise SystemExit("CAMERA_RENDER inputs are unknown or mixed; refusing to patch")
PY
)"
  if [ "$camera_patch_state" = baseline ]; then
    git apply --check "$HOLOCUE_ROOT/scripts/patches/viser_1_1_1/CAMERA_RENDER.patch"
    git apply "$HOLOCUE_ROOT/scripts/patches/viser_1_1_1/CAMERA_RENDER.patch"
  fi
  "$APP_PYTHON" -B - "$HOLOCUE_ROOT/scripts/patches/viser_1_1_1/CAMERA_RENDER.inputs.json" <<'PY'
import hashlib, json, sys
from pathlib import Path
manifest = json.loads(Path(sys.argv[1]).read_text())
for name, expected in manifest["patched_sha256"].items():
    assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == expected, name
PY
)
~~~

Node 固定 24.12.0 linux-x64，npm 固定 11.6.2。下载官方归档到项目目录并校验已记录摘要；不调用会在虚拟环境内安装 Node 的 Viser 默认安装器。

~~~bash
cd "$VISER_WORK/downloads"
curl --fail --location --output node-v24.12.0-linux-x64.tar.xz \
  https://nodejs.org/dist/v24.12.0/node-v24.12.0-linux-x64.tar.xz
echo 'bdebee276e58d0ef5448f3d5ac12c67daa963dd5e0a9bb621a53d1cefbc852fd  node-v24.12.0-linux-x64.tar.xz' | sha256sum --check
tar -xJf node-v24.12.0-linux-x64.tar.xz -C "$VISER_WORK"
export PATH="$VISER_WORK/node-v24.12.0-linux-x64/bin:$PATH"
export NODE_OPTIONS=--max-old-space-size=4096
export UV_THREADPOOL_SIZE=4 RAYON_NUM_THREADS=4 OMP_NUM_THREADS=4
export OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4
export npm_config_cache="$VISER_WORK/cache/npm"
export npm_config_update_notifier=false
test "$(node --version)" = v24.12.0
test "$(npm --version)" = 11.6.2
cd "$VISER_WORK/viser/client"
echo '2df518d57396831ac0bb1bbd736db6905bdbeb1c98f688b93503b856f6cb420e  package-lock.json' | sha256sum --check
"$APP_PYTHON" "$HOLOCUE_ROOT/scripts/guard/resource_guard.py" \
  --rss-limit-gb 8 --log "$VISER_LOG/install_resources.jsonl" \
  --execute -- npm ci --no-audit --no-fund > "$VISER_LOG/install.log" 2>&1
for file in GaussianSplats.tsx GaussianSplatsHelpers.ts GaussianSplatsHelpers.test.ts; do
  cp "$HOLOCUE_ROOT/scripts/patches/viser_1_1_1/$file" "src/Splatting/$file"
done
sha256sum src/Splatting/GaussianSplats* > "$VISER_LOG/patch_sources.sha256"
"$APP_PYTHON" "$HOLOCUE_ROOT/scripts/guard/resource_guard.py" \
  --rss-limit-gb 8 --log "$VISER_LOG/tests_resources.jsonl" \
  --execute -- npm exec -- vitest run --maxWorkers=1 \
  --reporter=default --reporter=json --outputFile="$VISER_LOG/vitest.json" \
  > "$VISER_LOG/tests.log" 2>&1
"$APP_PYTHON" "$HOLOCUE_ROOT/scripts/guard/resource_guard.py" \
  --rss-limit-gb 8 --log "$VISER_LOG/build_resources.jsonl" \
  --execute -- npm run build > "$VISER_LOG/build.log" 2>&1
echo '2df518d57396831ac0bb1bbd736db6905bdbeb1c98f688b93503b856f6cb420e  package-lock.json' | sha256sum --check
sha256sum --check "$VISER_LOG/patch_sources.sha256"
sha256sum --check "$VISER_LOG/installed_sources.sha256"
sha256sum build/index.html > "$VISER_LOG/bundle.sha256"
~~~

每步失败即停止，不改锁或依赖版本。本次 alpha_r1 使用此前同锁 node_modules 的独立副本：核对 hidden lock 的版本、来源和 integrity 与原锁一致，逐文件记录并验证 47043 项精确复制，结束后再次核对依赖源未变。不能仅因目录存在就直接复用。证据在 viser_alpha_build_r1/dependency_source_inventory.json 和 report.json。原锁依赖曾发出 Node engine 警告；实际日志保留警告，不以警告代替退出码和测试结果。

## 相机协议构建与原生投影检查

viser_aspect_build_r1_tests/report.json 记录 719 项前端测试、tsc/Vite 构建和使用完整候选 Python 包的 305 项项目测试通过。新客户端 index.html SHA256 为 d7a86b58a884879e1e6f09382d405bb69e761afe9fc8c1fdbe5eea6a787230e7。输入包、锁、依赖、候选源码及 src/tests 在结束时核对未变；formal 补丁副本与本文同步导致项目整体摘要变化，未冒称测试起止摘要相同。

viser_aspect_protocol_r1/report.json 使用上游字段转换器核对 ViewerCameraMessage 的全部字段，并完成真实 msgpack 序列化往返。完整类型生成器在已安装旧包与候选包均遇到原有 NDArray 类型断言失败，这项完整生成检查未通过；没有改写无关类型生成器或将局部检查标为完整生成成功。

viser_aspect_installation_r1.json 记录五个安装文件和 .work/viser-before-aspect-r1 备份。repair_runtime_r5.json 核对新 viewer_r17 实际进程环境及 HTTP 新包摘要，模型与 API 服务继续复用。相机协议必须由真实浏览器及同会话桥接另行验收。

formal_native_projection_readback_r1 使用 Blender 3.1.2 执行正式 Consumer.update 的原样数据应用段及正式 verify_consumed。四个明确离线案例通过，四次错误方像素负控均触发新增投影断言；真实宽窄记录的横纵系数误差最大为 5.79e-7。完整 Consumer.update 仍拒绝原始过期帧，未改时间戳，未渲染或保存场景，因此这份回归不是 live bridge 验收。

## 已完成的 alpha_r1 产物与验证边界

以下证据路径相对 runs/simulation/acceptance_20260919_1706/。viser_alpha_build_r1/report.json 记录实际 719/719 通过、npm run build（tsc && vite build）退出码 0、Node/npm 版本、命令、输入清单和产物摘要。CPU 8 GiB 守卫峰值 RSS 为 2.033 GiB，CUDA 为空；安装源、依赖源、候选源码和锁在结束时均核对未变。

| alpha_r1 文件 | SHA256 |
| --- | --- |
| GaussianSplats.tsx | 08f413d5fad0dea328a5df6a2c2643f11d92561f2cd1a2a0a56e6137ba98c23b |
| GaussianSplatsHelpers.ts | dee7a7c9ed9e06f021d0fff47687301030aa607eb7b5667978fb77c9969eb6ab |
| GaussianSplatsHelpers.test.ts | 03057a49c14ca30ae7f482238e3e9555a4c78cb75ca95830509e38bfd94e6432 |
| client/build/index.html | a8457e3a026d3d76d1ef1093829f7d4870f1295b991fa02d47791aca2195c1d9 |
| alpha_r1 report.json | 56600b22639a2ecaa73fb99f4638455e52d8e6b1420156570b1c2b100c907afd |

alpha_r1 构建目录为 .work/viser-alpha-r1/viser/client。构建与部署分开：仅复制 TS 不会更新浏览器接收的包。viser_alpha_installation_r1.json 记录 bundle、TSX 和 Helpers 安装对应关系及 .work/viser-before-alpha-r1/ 备份；repair_runtime_r4.json 记录 viewer_r16 的实际进程环境和 HTTP bundle SHA，与上表一致。上面的复现命令不自动部署或重启服务。

历史证据保留在 viser_client_build/、viser_client_full_tests/、viser_client_installation.json、viser_client_runtime.json、viser_camera_sync_build_r1/ 和 viser_camera_sync_build_r2/；原始准备清单为 .work/viser-client-fix/preparation.json。这些对应旧阶段，不能替代当前 UI 对照。

camera_sync_comparison_readback_r3 记录旧 alpha 阈值仍存在时的相机修复观察：实际查看 28 张原图和 506 个关键视频帧，已看范围未复现旧实体与提示空间错配；保留了 B 环远景消失的实际现象。独立 requestAnimationFrame 采集的 CPU 矩阵不能冒充每次 GPU draw 的读取。response_r15 验证了固定相机、尺寸、焦点的真实 N/σ 画布变化，也属于旧 alpha 阈值阶段。

faint_background_before_r1 与 faint_background_after_r1 使用同一真实暂停会话和相同脚本。初始工作区域和特写的相机、焦点、亮度、实际画布尺寸及 B/C 打包缓冲完全相同；实际查看图像确认正透明度修复恢复了 B 的远景提示，C 端子、定位键和文字仍可读。返回工作区域时旧包 backing 自动变成 1116×875，新包为 1276×1000，该组仅作视觉观察，不能作为相同分辨率的像素差实验。原始数据与边界见 faint_background_comparison_r1.json 及 faint_background_root_observation_r1.md。

严格响应测量通过 Viser 现有 Configuration & diagnostics / Dev Settings / Device Pixel Ratio 可见控件选择 1.0，以固定像素密度。N/σ 测量维持这一设置；十二场景亮度/焦点测量后恢复 Adaptive，常规工作区域、特写、结构检查和宽窄窗口流程继续验证默认自适应模式。没有修改产品默认设置、响应参数或相机。response_r16 的自动分辨率混杂被原一致性断言拒绝并完整保留，不能计作通过；后续运行仍保留该断言。

完整十二场景、多客户端、故障恢复、原生桥接和最终独立审查以同一最终代码的验收报告为准。安装/HTTP 摘要一致与 719 项测试通过均不能替代真实绘制证据；虚拟 get_render 与异步透明排序的限制见上文。
