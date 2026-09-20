"""Formal contracts and deployment inputs invalidate a frozen source review."""
import pytest
from scripts.release import check_review_gate as gate

@pytest.fixture
def repository(tmp_path,monkeypatch):
    monkeypatch.setattr(gate,'ROOT',tmp_path)
    for name in gate.SOURCE_FILES:
        (tmp_path/name).write_text('original',encoding='utf-8')
    return tmp_path

@pytest.mark.parametrize('relative',[
    'schemas/scene.schema.json','schemas/display_packet.schema.json','schemas/openapi.json',
    'schemas/semantic_decision.schema.json','requirements-simulation.txt','.env.example',
    'GOAL_EXECUTION_PROMPT.md','CLAUDE.md',
    '.claude/agents/architecture-reviewer.md','scene_agent/reviewers.md',
])
def test_formal_input_edits_invalidate_review(repository,relative):
    path=repository/relative;path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text('original',encoding='utf-8')
    before=gate.source_digest()
    path.write_text('changed contract',encoding='utf-8')
    assert gate.source_digest()!=before

def test_evidence_and_runtime_cache_do_not_change_source_digest(repository):
    before=gate.source_digest()
    for relative in ['runs/reviews/report.json','.work/cache/result.json',
                     'src/holocue/__pycache__/module.pyc','MANIFEST.sha256']:
        path=repository/relative;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('generated',encoding='utf-8')
    assert gate.source_digest()==before
