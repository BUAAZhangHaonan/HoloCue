# RUN4 最终有限隐私补查

结论：本次核查范围未检出真实凭据，未产生需要删除或脱敏的材料。未修改项目、helper、媒体或旧审查报告，也未执行最终 selector、编码、解码或实验。实际最终 ZIP 与后续新增交付日志仍待单独核验。

审查会话：`/root/cloud_provenance_review`。目标：`/home/hdd3/zhanghaonan/projects/holocue/runs/simulation/cloud_finish90_20260921_e67b574`。主体扫描完成时间为 `2026-09-21T18:46:53Z`，新增已关闭交付记录补扫截至 `2026-09-21T18:48:43.798839Z`；其后仅对下载器解释器修正做了精确字节差异核对。

最终证据清单含 4,605 个文件、428,887,400 字节；与旧报告相比，3,225 文件身份未变，1,380 项新增或变化。逐项路径、大小、SHA256、状态、来源归属及补查方式保存在相邻 JSON。凭据候选为 0，跳过为 0。原先变化中的 `api_resources.jsonl` 已稳定核查：1,755,978 字节，SHA256 `ae4b7b0c7670f255d32b9c85b0c868d8d78b279eb9af28f437a5f97cee34b176`。

范围为 RUN4 文本日志、实际模型回复、视频/解码帧元数据、相机 d8 阶段及新 Shelf 配对记录，以及交付 helper 顶层文件、保存版本、camera_fix 小目录和 selector 明确列出的 20 个 runtimefix 文件。单文件上限 64 MiB，总文本上限 512 MiB；没有触发上限。未读取模型、缓存、node_modules、SSH 配置或数据库；媒体二进制仅做下述哈希验证，没有 OCR 或画面隐私识别。

检查类别与前次一致：私钥、常见提供商 token、Bearer 授权、含凭据 URL，以及显式密码/API key/secret 字面量。报告不输出任何匹配值。规则扫描不能保证识别任意未知格式的秘密。

## 命令和服务闭合

截至闭合核验，121 个 command 目录均存在已结束的 execution，缺失/未结束记录为 0。主体扫描期间完成的 `video_acceptance`、`combine_introductions` 及关联新增文本另行补查 16 文件，未发现候选或不稳定文件。

`shutdown_resume03` 和 `verify_cleanup_final` 均 rc0。独立退出证明包含 94 个已记录身份，全部 `exited`，存活所属身份为 0；三个 resume03 服务的 remaining_owned_processes 为空。只读连接检查中 8000、8750、8780 均不监听。关闭记录中的 GPU 1/2 均为 4 MiB；这是停服记录所载结果，不冒称新的 GPU 采样。

旧失败记录保持原字节：尤其 Shelf attempt02 的相对路径在预检时被拒绝、没有输出目录；该命令 rc1 不代表相机/native 实验失败。下载第一次调用因系统 Python 缺少 hashlib.file_digest 而在复制前失败，不能记作成功传输。

## 8 个超大媒体的审阅副本

现场全部 8 个不小于 47 MiB 的原件，与 `review_videos/index.json` 的 8 项原件集合完全一致，没有漏项或额外替代项。逐项通过：原件与副本实际大小/SHA256、proof 和 verification_evidence_files 哈希、三条编码/验证命令 rc0 及其各自稳定源码/资产身份、原分辨率/fps、完整解码帧数、首尾时间/时长和所有逐帧相对 PTS。8 项最大相对 PTS 误差均为 0；各副本均严格小于 47 MiB。

这些验证复核现有完整解码记录，没有重跑 ffmpeg。副本可审阅不改变原始成功/失败状态；包括失败的 engine_attempt01 原件仍作为失败证据保留。本地完整原件最终交付与 ZIP 实际入选尚需后续交叉审计，不能由本报告替代。

## 最后下载器修正及待验范围

已只读确认最新 download_videos.py 的 SHA256 为 `ed3b4f4a6eec01157a060ba1d6d14eecfc6c25b5f0d3ae79f7be75d7fd610e4c`。它与已完整扫描的 `9ede5f88…` 版本只差固定项目 Python 解释器常量及其调用；未改变检查算法，也没有加入凭据。旧版本的完整字节和新版本差异均已核对；未额外运行该 helper 或合成测试。

本地下载失败/成功日志尚未全部复制到 RUN/local_delivery_logs，本报告不覆盖未来字节；后续 pack 的凭据检查和实际 ZIP 独立核验仍须执行。最终压缩包、成员精确集合、CRC、每成员哈希、本地完整媒体交付，以及封存后新增报告的来源边界，均维持待验。旧 `privacy_review.md/json` 保持不变。