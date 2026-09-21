"""Write post-package delivery metadata; never changes sealed package inputs."""
import hashlib
import json
from pathlib import Path

root = Path('C:/Users/zhn19/Downloads/2/HoloCue_Final_20260921')
read = lambda p: json.loads(p.read_text(encoding='utf-8'))
index = read(root / 'upload/UPLOAD_INDEX.json')
verification = read(root / 'upload/LOCAL_VERIFICATION.json')
assert verification['passed']
videos = read(root / 'videos/VIDEO_FILES.json')
archives = index['archives']
paths = [root / 'upload' / row['archive'] for row in archives]
paths += [root / 'upload' / name for name in ('UPLOAD_INDEX.json', 'SHA256SUMS', 'LOCAL_VERIFICATION.json')]
lines = ['# 全部上传文件', '', '每个 ZIP 均可独立解压；全部 ZIP 共同组成完整审阅资料。', '',
         f'独立 ZIP：{len(archives)} 份；总大小：{sum(row["bytes"] for row in archives):,} 字节。', '',
         'SHA256 见 upload/UPLOAD_INDEX.json 与 upload/SHA256SUMS。', '']
lines += [f'- `{path.as_posix()}`' for path in paths]
lines += ['', '## 封包后的交付说明与独立复核', '']
lines += [f'- `{(root / name).as_posix()}`' for name in (
    'DELIVERY_RESULT.md', 'FINAL_SUMMARY.md', 'REVIEW_NOTES.md', 'NEXT_REVIEW_PROMPT.md',
    'COVERAGE.json', 'SOURCE_PHASES.json', 'VIDEO_ACCEPTANCE.json', 'review_selection.json',
    'final_archive_audit.md', 'final_archive_audit.json', 'GIT_DELIVERY.json')]
lines += ['', '## 单独保留的原始媒体与播放入口', '',
          f'- `{(root / "videos/VIDEO_FILES.json").as_posix()}`：逐个原件绝对路径、大小、SHA256。',
          f'- `{(root / "videos/VIDEO_INDEX.html").as_posix()}`：十二场景介绍与完整流程视频。',
          f'- `{(root / "videos/all_scenes_introduction/twelve_scenes_introduction.mp4").as_posix()}`：282 秒介绍合集。', '']
(root / 'UPLOAD_FILES.md').write_text('\n'.join(lines), encoding='utf-8')
result = f'''# HoloCue 最终交付结果

本批代码修改、规定场景检查、十二场介绍视频与真实 Viser 页面端到端演示、独立检查、资料回传和服务清理已经完成。

## 实际结果

- 最新相机原子更新代码：529 项测试通过，0 失败、0 错误、0 跳过；实际页面 10 轮、20 次视角切换通过；Shelf 四阶段原生配对检查通过。
- 相机修复前阶段：十二场真实 Qwen 流程、30 个任务步骤通过；十二场均交付完整原始 WebM、流程 MP4 和介绍 MP4。
- 十二场原生 199 阶段证据跨不同源码阶段积累。最新源码没有重新执行全部 199 阶段，也没有重新录制十二场视频；阶段、资产和来源差异明确记录在 SOURCE_PHASES.json、COVERAGE.json 与 FINAL_SUMMARY.md。
- 场景介绍合集：282 秒、7050 帧。介绍使用实际页面截图；流程视频保留真实页面操作与等待时间，不能用作人工操作速度或模型响应延迟基准。
- 独立视觉检查查看 179 张来源原图、251 张视频代表帧、8 张副本对照图。部分遮挡、裁切、提示对比度等视觉限制和全部历史失败保留在报告中。
- 本次创建的 model/API/Viser 服务已安全停止；最终核对本任务进程无存活，8000/8750/8780 端口关闭。

## 文件及验证

- 审阅 ZIP：{len(archives)} 份，{sum(row['bytes'] for row in archives):,} 字节；每份小于 48 MiB。
- 本地验证：{verification['archives_verified']} 份 ZIP、{verification['members_verified']} 个成员，逐包大小/SHA256/CRC与逐成员SHA256全部通过。
- 显式选入 9,345 个文件；自动补入源码等内容后共 9,575 个项目成员，另有 6 个索引成员。全部上传文件绝对路径见 [UPLOAD_FILES.md](UPLOAD_FILES.md)。
- 独立实际 ZIP 审查通过，errors=[]：核对源码阶段、最终检查、封存视觉报告、103 份资产输入、原始模型回复、十二场视频与八项替代证明。完整审查见 final_archive_audit.md/json。
- 视频原件与播放入口：[VIDEO_INDEX.html](videos/VIDEO_INDEX.html)；完整文件身份见 [VIDEO_FILES.json](videos/VIDEO_FILES.json)。八份超大原件完整保留在本地，ZIP 使用有来源记录、分辨率及全帧时序核验的审阅副本。
- 完整阶段结果及未执行范围：[FINAL_SUMMARY.md](FINAL_SUMMARY.md)、[REVIEW_NOTES.md](REVIEW_NOTES.md)。下次网页端审阅提示：[NEXT_REVIEW_PROMPT.md](NEXT_REVIEW_PROMPT.md)。
- 本文件在封包之后生成，独立于封存 ZIP；最终 Git 推送信息另见 GIT_DELIVERY.json，独立压缩包审查见 final_archive_audit.md/json。

源码摘要：`{index['source_digest']}`。
资产摘要：`36866cf33627a522897a66a3e1247587608d72959dc792d029de0136a0b78af8`。
本地交付目录：`{root.as_posix()}`。
'''
(root / 'DELIVERY_RESULT.md').write_text(result, encoding='utf-8')
print(json.dumps({'archives': len(archives), 'members': verification['members_verified'], 'output': str(root)}, ensure_ascii=False))
