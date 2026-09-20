# HoloCue 独立证据与资源审查

审查者：独立代理 `/root/repair_provenance_review`。日期：2026-09-21（北京时间）。只读审查；没有启动模型、测试、渲染或服务，没有修改服务器仓库。已完成一次初始审查及一次有限最终补充。下方初始结果保留当时范围，最终状态见补充部分。

项目：4029 `/home/hdd3/zhanghaonan/projects/holocue`。运行目录：`runs/simulation/repair_review_20260920_25bcc909`。读取时 HEAD：`9f1f896ed207dd03aa7dbab9601f3b8d563b2cef`。

## 已独立核验

- 通过包内公开的快照函数只读重新计算 115 个源码文件与 98 个资产/fixture 文件。源码摘要为 `2ef99b6626387225afacc10502e6d3b83e1359a0c7e528d7036e54f683002366`；资产摘要为 `1926ec8e7f696dd3565ce016f144f640c630c6d305441062921c5e18efc1280d`，与本批最终执行记录一致。另逐文件比较实际长度及 SHA256，全部匹配。
- 对照 `preflight_command/execution.json` 的原始资产清单，22 个固定 fixture 文件原始字节全部保持。`src/holocue/modeling.py` 实际 SHA256 为 `0a7bdcb1e06ede04fb4fcd4689a25aa5cce9a4e347fe68420dffd0c9130837aa`。
- `assets.provenance.json` 明确请求及完成 12 个场景、76 个生成 GLB，完整标志为 true；另对 `build_verification.json` 所列 12 份 payload、12 份 `.blend`、12 张原始 Blender 图像逐一重新计算 SHA256，36 项全部匹配。
- `build_command`、`build_verification_command`、`pytest_command`、`geometry_command`、`environment_command`、`live_command`、`mirror_command`、`viewer_response_command`、`response_command`、`support_views_command`、`commits_command` 实际执行记录返回码均为 0，执行前后源码均为最终摘要。构建记录资产从旧摘要变为最终摘要，其余上述执行记录资产前后均为最终摘要。
- 读取 42 份资源 JSONL，共 13,357 条含主机可用内存的采样记录；此次读取的最低可用内存为 71.9041 GiB。记录中 GPU 身份只出现物理 GPU 1（`GPU-7ba69fc7-12ac-3dfb-8265-3476ce2504b6`）及 GPU 2（`GPU-dfaeaa7c-32c8-ebb4-aa59-ab7f829805f1`）。这是读取时的采样范围，后续运行需要最终补充核查。
- 实际守卫源码使用 `max(requested_reserve, 0.20 * host_total)`；已完成命令 stdout 明确记录主机保留阈值 `50.30907897949219` GiB。CPU 外层检查为 8 GiB RSS，模型外层/内层 32 GiB，原生桥接内层指定物理 GPU 2 与 12 GiB。模型脚本保留 8192 context、单请求、0.70 GPU fraction、关闭 thinking、enforce-eager 等既有设置。
- `.work/task_env.sh` 配置应用空 CUDA、线程数 4、TMP/TEMP/XDG/PIP/Python/Trition/CUDA 缓存位于项目 `.work`。守卫将已授权物理 GPU 转换为 UUID 后传递 CUDA_VISIBLE_DEVICES。
- 对修复包 `MANIFEST.json` 的 18 个声明文件重新核对长度与 SHA256，全部匹配。

## 必须保留的归属边界

`preflight_command`、`readers_dev_command`、`environment_derivation_command` 与 `mirror_prebuild*` 属于历史/开发材料，不能标为最终 current 验收。尤其 `mirror_prebuild_r4_command` 使用最终源码，但执行期间资产发生构建变化，且输入会话来自此前记录；即使返回码为 0，仍需要历史归档。`mirror_prebuild_r2_command` 实际返回码为 1，应保留失败证据。

读取时 `bridge_command`、`model_command`、`api_command`、`viewer_command` 只有 started.json，正在执行。此阶段不判定四场景桥接完成，不声称服务已经停止。返回码仅代表进程结果；视觉质量与任务正确性由相应报告及独立视觉审查说明。

## 实际读取范围与限制

实际读取：包内 CODEX_PROMPT.md、TASKS.md、EVIDENCE_SPEC.md 中证据/资源/独立审查要求；MANIFEST.json；tools/review_bundle.py 的摘要算法；运行目录各 `*_command/execution.json` 或 started.json；preflight.json、kit_verification.json、environment.json、assets.provenance.json、build_verification.json；42 份资源 JSONL；`.work/task_env.sh`、scripts/ops/serve_model.sh、scripts/guard/resource_guard.py、scripts/tests/audit_bridge_live.py 的资源相关实现；115 个源码、98 个资产、36 个构建产物的实际字节。

本次短审查没有复跑测试，没有观看图片或录像，没有验证尚未生成的 review_selection.json、COVERAGE.json、ZIP 清单或远程 push，也没有作出持续运行全过程无资源异常的结论。上述最终状态等待主线程提供材料后作一次有限补充。

## 最终有限补充

此次重新读取 bridge/report.json、bridge_command/execution.json、shutdown_command/execution.json、三个服务 execution.json、service_shutdown.json、coverage_draft.json、selection_draft.json、两份 review_videos/*.json、四份视频转码/核验执行记录，并重新汇总最终资源 JSONL。没有追加实验。

- `bridge_command` 返回码 0，四场景报告均为 passed，engine_bay / optical_bench / server_rack / shelf_picking 分别有 18 / 17 / 14 / 14 个阶段，共 63 个阶段，browser_errors 均为空。此处核查实际报告及身份，不独立评定画面。
- `shutdown_command` 返回码 0。viewer、API、model 的停止记录匹配本任务启动时的 PID 与 create_time；停止脚本逐个验证身份并只处理所属子进程。本次实际检查，记录中的非 zombie 所属进程全部消失，8000、8750、8780、8783 均没有监听，GPU 1 与 GPU 2 各占用 4 MiB。三个服务包装命令在明确 SIGINT 停止后返回 1，selection 保留真实返回码及原因，没有伪造正常退出码。
- 最终读取 112 份资源 JSONL、86,150 条主机可用内存采样，最低仍为 71.90411376953125 GiB；GPU 身份仅有物理 1、2，所读 JSONL 未发现 reason/event 终止条目。阈值与先前核查一致。此结论覆盖实际记录采样及本次终止状态。
- 再次计算源码与资产摘要，与本报告前文完整摘要一致。对草稿所有 current passed/failed 条目的执行记录逐项检查，source_before、source_after、assets_after 全部匹配最终身份，未发现摘要不一致。
- selection_draft.json 的 1,686 个显式选择文件全部存在，路径没有重复。四个重点场景实际 `.blend` 均选入。包工具默认收集场景配置引用的 76 个 GLB 与 22 个 fixture；已经核查该默认逻辑和当前 98 个文件摘要。失败的 mirror_prebuild_r2 与其他开发/构建前材料已明确 historical/recorded。
- engine_bay 审阅 MP4 与原始 WebM 的记录均为 800×500、25 fps、74,296 帧、2,971.84 秒；optical_bench 为 800×500、25 fps、91,892 帧、3,675.68 秒。检查实际 FFmpeg 命令没有裁切时间或缩放参数；对这四个实际文件重新计算 SHA256，与证明报告一致。两份转码及两份帧数核验记录返回码均为 0。没有观看完整录像，也没有独立再次解码视频。server_rack 与 shelf_picking 已选择原始 WebM。

## 草稿发现及交付前待完成

资料选择存在一项明确遗漏：EVIDENCE_SPEC.md 第 7 行要求将 `runs/simulation/acceptance_20260919_1706/` 的历史结果以独立 historical/recorded run 导出。读取的 selection_draft.json 只有 previous_closeout 的五份文档，尚未选择该旧验收目录的原始报告。已通知主线程补入旧验收的核心报告、状态、摘要和缺失阶段记录，保留原日期及结果，无须重跑旧验收。此审查尚未核验补入后的最终 selection。

草稿 privacy_reviewed=false、evidence_verification=not_run 为主线程明确保留的占位；最终文件需要基于实际核验结果重新生成。本审查没有提前认可这些状态。

ZIP 尚未生成；压缩包成员、48 MiB 上限、CRC、SHA256、独立解压、下载到本地后的再次校验由主线程的包工具及本地校验完成。本审查未验证该未来结果。最终文档提交与 push 状态也由主线程完成；已读取 selection 中第一次 push 128 及 keepalive push 0 的真实记录，但没有独立核对远程 HEAD。
