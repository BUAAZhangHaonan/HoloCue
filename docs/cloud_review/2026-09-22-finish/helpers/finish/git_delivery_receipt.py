"""Read-only post-push receipt, stored outside the committed repository."""
import datetime
import json
import subprocess
from pathlib import Path

prefix = 'cd /home/hdd3/zhanghaonan/projects/holocue && '
def remote(command):
    return subprocess.check_output(['ssh', '4029', prefix + command], text=True, encoding='utf-8').strip()

head = remote('git rev-parse HEAD')
upstream = remote('git ls-remote origin refs/heads/master').split()[0]
status = remote('git status --porcelain')
assert head == upstream and status == '', (head, upstream, status)
result = {'verified_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'repository': 'BUAAZhangHaonan/HoloCue', 'branch': 'master', 'head': head,
    'remote_master': upstream, 'remote_matches_head': True, 'working_tree_clean': True,
    'uncommitted_tracked_or_untracked_files': [],
    'ignored_evidence': 'Large run media and project caches remain ignored; delivered through verified ZIPs and local original media.',
    'commits_since_previous_pushed_baseline': remote('git log --format="%H %s" e67b574..HEAD').splitlines(),
    'receipt_scope': 'Generated after push; not embedded into its own committed Git tree.'}
path = Path('C:/Users/zhn19/Downloads/2/HoloCue_Final_20260921/GIT_DELIVERY.json')
path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
