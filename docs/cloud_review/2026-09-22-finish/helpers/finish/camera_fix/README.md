# 相机原子更新候选（尚未部署或运行）

独立代理 `/root/cloud_code_review`。本目录仅本地准备，未上传应用源码、未启动服务或
执行 UI/模型/native 回归。原 529 测试仍属于 source c33，不自动归属此新候选。

## 应用候选与原件

`src/holocue/viewer_scene.py` 完整复制自服务器当前文件，只用 apply_patch 将
`cam.up_direction / cam.position / cam.look_at` 三赋值包入 `with self.client.atomic():`。
其他几何、相机计算、模型和焦点参数未变。差异见 `viewer_scene_atomic.patch`。

- `viewer_scene.original.py` SHA256：336b53785d732a05e0d3f06712a09b8323effc862a7fa377c4cc498c558bf71a
- 候选 `src/holocue/viewer_scene.py` SHA256：98006df1f6b922b58136d814e8ee97d30d94c8505adeede0cd2850c66ed8f331

依据是实际失败中 position 已为 BASKET detail，但 look_at 保持 inspection -Y 方向；
客户端/Python 同步且稳定时契约焦点仍在相机后面。Viser 的 position setter 会自动
平移 look_at，当前三次赋值可能暴露中间状态。atomic 是待验证的最小候选，不把
推断写成已证明的具体消息交错，也不放宽焦点断言。

## 有界真实回归

`verify_camera_atomic.py` 在独立真实 Shelf 会话发送原始场景指令，保留模型原回复，
等待 RED→BASKET 原任务到达等待确认的终点并暂停。随后 10 轮 BLUE inspection→
BASKET detail，共 20 次调用原 Audit.select_view；每次附加实际 CLIENT_READ 与
Python 相机核对，按契约点和实际客户端 forward 检查正深度/焦点一致。每轮保存
view/snapshot/client/focus/screenshot，要求任务状态和实体位姿不变。不启动 exporter
或 Blender；它是 UI 相机回归，不宣称完整工作流或 native 通过。任一动作失败立即
停止，保存原失败证据，不 retry。最后不确认或改写暂停计划。

必须通过既有 record.py/90% guard 调用，且 resume03 已由主线程启动并 readiness。
工具首先调用既有 service_generation.py check --generation resume03，要求当前
viewer_scene SHA 与明确候选一致，输出目录必须新建且位于当前 RUN 下。

```bash
source .work/cloud_finish90_20260921/phase_env.sh
export HOLOCUE_RECORD_RSS_GB=8
"$APP_PYTHON" .work/cloud_update_20260921/record.py camera_atomic_live \
  "$APP_PYTHON" .work/cloud_finish90_20260921/camera_fix/verify_camera_atomic.py \
  --generation resume03 \
  --expected-viewer-source-sha256 98006df1f6b922b58136d814e8ee97d30d94c8505adeede0cd2850c66ed8f331 \
  --out "$RUN_DIR/camera_atomic_live"
```

## Shelf 配对新 attempt

`capture_changed_pairs_attempt.py` 复制原 `.work/cloud_update_20260921/capture_changed_pairs.py`，
只增加可选 `--out` 和说明文字，所有采样、任务、视图、Audit.capture 及断言保持。
原 helper 完整字节保留为 `capture_changed_pairs.original.py`，SHA256：
`b832603744d3aba2ab948839d71dab435c9289704bd56309a0367e2806fd739b`。
旧服务器 helper、失败目录及前两阶段图像均不改。

```bash
"$APP_PYTHON" .work/cloud_update_20260921/record.py pairs_shelf_picking_attempt02 \
  "$APP_PYTHON" .work/cloud_finish90_20260921/camera_fix/capture_changed_pairs_attempt.py \
  --scene shelf_picking --out "$RUN_DIR/changed_pairs/shelf_picking_attempt02"
```

以上命令仅供主线程审阅后执行。本目录未代主线程执行；新 attempt 的来源必须在
最终选择器按实际 --out/命令记录映射，不能与旧 pairs_shelf_picking 失败混同。
