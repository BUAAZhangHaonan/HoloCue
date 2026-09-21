# 最终交付工具独立交叉审查

审查者：`/root/cloud_code_review`。范围限 prepare_delivery.py、download_videos.py、
combine_introductions.py；仅只读源码和既有记录，没有执行选择器、下载、合集或新实验。

首轮审查输入本地/远端 SHA256 一致：

- prepare_delivery.py：8c4d21f8d8c9a5fbd7d9157b0b481a8ed3e8da97df954fa8b0e6282b218db7e1
- download_videos.py：b52e3a4756fd354c0cc8ac1961c59f14938f63728d1fe4de023dcaf603d373d5
- combine_introductions.py：12366f7ae8d4f6bbda046192b6f63a2f247a44fd01cb91ecc6efc6c938da2cd8

发现一项 P2：prepare_delivery.py 原第 763–775 行按 service_shutdown_/shutdown_gpu_ports_
文件名前缀推断 owner，再将不存在的命令降为 delivery。实际
service_shutdown_resume01.json、shutdown_gpu_ports_resume01.json 来自
shutdown_resume01_client_fix_command（rc0），不是 shutdown_resume01_command。
原实现会丢失两份真实停服证据的命令归属。作者已在最终候选中新增
generation_output_owners（第 59–77 行），按已记录 service_generation.py 的 action
与 --generation 建映射、拒绝重复 owner；第 797–798 行用实际映射覆盖名称猜测。
本代理已只读复核，P2 逻辑闭合。最终 selector SHA 为
dee5d7fa35811d537bd4b30d5ee951b1f52732f00c9d3399d6d55550abc279f7，另外两工具不变。
已只读核实远端同步为该 SHA；此前 03 合成验证属于 8c4d21f8 版本，不改写其测试身份。

其余本次重点未发现新增静态缺陷：

- 三工具均要求恰好十二个显式 accepted 场景，校验完整 production manifest SHA、
  scene/session、一条接受记录和非空理由；不会自动选择较新的成功记录。
- 原拒绝 connector 的 raw 及制作目录全部 MP4 进入 rejected_attempts；未选产物保留，
  不进入十二场完整播放清单。下载没有 47 MiB 原件上限。
- 选择器按 capture/producer 实际 argv 及保存的工具版本 SHA 找归属；新 capture 的
  before/after、per-scene、served 主文档 SHA 与 canvas/ancestor opacity 实值交叉验证。
  旧 capture 明确标为没有每 session runtime build 测量，不虚构补测。
- RUN4 命令严格匹配当前 source/assets；RUN2 sealed 链和 RUN3 冻结继承保持 historical。
  UI 录像与 native 覆盖分列；viewer_response_final 不因 viewer_ 前缀冒充服务，服务集合
  还要求对应 repair_process 身份文件。
- Viser 修复只收录明确列出的源码、原件、锁、build、测试、说明与记录，不递归打包
  node_modules/cache；新 build 与安装 identity 绑定，依赖身份与应用摘要分开。

已只读核对 RUN4 既有 delivery_helpers_validation_01 rc2（启动失败）及 02/03 rc0。
03 的实际 stdout 记录十组合成契约检查，并绑定上述三个 SHA，source c33e1ae4… 前后
相同。这是合成检查，不是最终真实 selection、文件传输或媒体编码验收。除上述已修复
P2，未发现新增静态阻碍。最终仍需读取
实际交付命令的完成记录，不能由本报告推定已交付。

最后只读核实作者已有 delivery_helpers_validation_04 rc0，绑定最终 dee5d7fa/b52e3a47/
12366f7a 字节，增加实际 argv 自定义停服/readiness label 的归属边界检查，共十一组。
source c33e1ae4… 前后相同；本代理没有重跑该检查。
