"""List all independent upload files after local and remote verification."""
import json
import sys
from pathlib import Path

directory=Path(sys.argv[1]).resolve()
read=lambda name:json.loads((directory/name).read_text(encoding='utf-8'))
index=read('UPLOAD_INDEX.json');verification=read('LOCAL_VERIFICATION.json');receipt=read('FINAL_RECEIPT.json')
assert verification['passed'] and receipt['worktree_clean'] and receipt['head']==receipt['remote_head']
assert len(index['archives'])==verification['archives_verified']
assert all(row['bytes']<48*1048576 for row in index['archives'])
lines=['# HoloCue 续跑上传文件绝对路径','',f'本地目录：`{directory.as_posix()}`。',
    f"服务器目录：`{receipt['remote_upload_directory']}`。",'',
    f"共 {len(index['archives'])} 个独立 ZIP，总计 {receipt['archive_total_bytes']/1048576:.2f} MiB，最大 {receipt['archive_max_bytes']/1048576:.2f} MiB。服务器、本地和独立审查均完成哈希、CRC及成员校验。",'',
    '上传全部 ZIP、UPLOAD_INDEX.json、SHA256SUMS，并附最终回执和核验补录；每份 ZIP 可以独立解压。','',
    '| ZIP 绝对路径 | MiB | SHA256 |','|---|---:|---|']
for row in index['archives']:
    path=directory/row['archive'];assert path.stat().st_size==row['bytes']
    lines.append(f"| [{path.as_posix()}]({path.as_posix()}) | {row['bytes']/1048576:.2f} | `{row['sha256']}` |")
lines+=['','## 总结、索引与核验补录','']
for name in ['UPLOAD_INDEX.json','SHA256SUMS','FINAL_SUMMARY.md','REVIEW_NOTES.md','COVERAGE.json','NEXT_REVIEW_PROMPT.md','FINAL_RECEIPT.json','LOCAL_VERIFICATION.json','provenance_archive_review.md','provenance_archive_review.json']:
    path=directory/name;assert path.is_file();lines.append(f'- [{path.as_posix()}]({path.as_posix()})')
lines+=['',f"master 本地与远程 HEAD：`{receipt['head']}`，工作区干净，本次 {len(receipt['commits_since_baseline'])} 个细分提交。",'',
    '本次新增CNC十八阶段通过；与此前blocks合计完成规定八场中的两场。connector因模型内存守卫停止而零阶段失败，另五场和三组定向配对未运行。此前519项pytest等保持各自历史执行身份。二十二个本批进程身份已退出，服务端口关闭。','']
(directory/'UPLOAD_FILES.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps({'archives':len(index['archives']),'members':verification['members_verified'],'head':receipt['head'],'upload_paths':str(directory/'UPLOAD_FILES.md')},ensure_ascii=False))
