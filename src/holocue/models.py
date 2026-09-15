"""Versioned semantic contracts. All extra fields, including N/sigma from an LLM, are rejected."""
from __future__ import annotations
from typing import Literal
import math
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

class Pose(Strict):
    position_m: tuple[float,float,float] = (0.,0.,0.)
    wxyz: tuple[float,float,float,float] = (1.,0.,0.,0.)
    @field_validator('wxyz')
    @classmethod
    def unit_quaternion(cls,v):
        if abs(sum(x*x for x in v)-1)>1e-4:
            raise ValueError('wxyz must be a unit quaternion')
        return v

class SceneObject(Strict):
    object_id: str = Field(pattern=r'^[A-Za-z][A-Za-z0-9_-]{0,47}$')
    label: str
    asset: str
    pose: Pose
    color: tuple[int,int,int] = (160,175,190)
    capabilities: list[Literal['point','rotate','inspect_back','insert','assemble','wait']]
    anchors: dict[str,tuple[float,float,float]] = Field(default_factory=dict)
    description: str = ''

class SceneSpec(Strict):
    schema_version: Literal['1.0'] = '1.0'
    scene_id: str
    title: str
    units: Literal['m'] = 'm'
    axes: Literal['right_handed_z_up'] = 'right_handed_z_up'
    objects: list[SceneObject]
    initial_instruction: str
    camera_position_m: tuple[float,float,float] = (.8,-.85,.72)
    camera_look_at_m: tuple[float,float,float] = (0.,.12,.08)
    @model_validator(mode='after')
    def unique_ids(self):
        ids=[x.object_id for x in self.objects]
        if len(ids)!=len(set(ids)):raise ValueError('duplicate scene object IDs')
        return self

class CueSemantic(Strict):
    target_id: str
    action: Literal['point','rotate','inspect_back','insert','assemble','wait']
    cue_type: Literal['highlight','ring_arrow','straight_arrow','label','ghost_motion']
    task_role: Literal['current','next','background']
    priority: int = Field(ge=0,le=5)
    depth_requirement: Literal['precise','persistent','neutral']
    instruction: str = Field(min_length=1,max_length=180)
    angle_deg: float | None = Field(default=None,ge=-360,le=360)
    reference_id: str | None = None
    @model_validator(mode='after')
    def action_parameters(self):
        if self.action=='rotate' and self.angle_deg is None:
            raise ValueError('rotate requires an explicit angle_deg')
        if self.action in ('insert','assemble') and not self.reference_id:
            raise ValueError('insert/assemble requires a reference_id')
        if self.task_role=='current' and self.priority==0:
            raise ValueError('current cue requires positive priority')
        return self

class Decision(Strict):
    operation: Literal['replace','interrupt','resume','complete','pause','clarify']
    assistant_message: str = Field(min_length=1,max_length=300)
    cues: list[CueSemantic] = Field(default_factory=list,max_length=8)
    @model_validator(mode='after')
    def decision_shape(self):
        new_plan=self.operation in ('replace','interrupt')
        if new_plan:
            if not self.cues or self.cues[0].task_role!='current':
                raise ValueError('new plan must start with exactly one current cue')
            if sum(c.task_role=='current' for c in self.cues)!=1:
                raise ValueError('new plan must have exactly one current cue')
            seen_background = False
            for cue in self.cues:
                if cue.task_role == 'background': seen_background = True
                elif seen_background: raise ValueError('background cues must follow all actionable steps')
            if len({c.target_id for c in self.cues}) != len(self.cues):
                raise ValueError('one cue per target in a display plan')
        elif self.cues:
            raise ValueError('only replace/interrupt may carry new cues')
        return self

class Task(Strict):
    task_id: str
    semantic: CueSemantic

class Session(Strict):
    session_id: str
    scene_id: str
    revision: int = 0
    epoch: int = 0
    execution: Literal['idle','running','paused','planning','error'] = 'idle'
    queue: list[Task] = Field(default_factory=list)
    suspended: list[list[Task]] = Field(default_factory=list)
    completed: list[Task] = Field(default_factory=list)
    history: list[dict[str,str]] = Field(default_factory=list)
    assistant_message: str = ''
    last_error: str | None = None
    backend_mode: str

class UserMessage(Strict):
    text: str = Field(min_length=1,max_length=1200)
    request_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    expected_revision: int = Field(ge=0)
    # Optional single JPEG/PNG. Semantic scene geometry remains the authoritative position source.
    image_base64: str | None = Field(default=None,max_length=2_000_000)
    image_mime: Literal['image/png','image/jpeg'] = 'image/png'

class RevisionRequest(Strict):
    expected_revision: int = Field(ge=0)

class DisplayCue(Strict):
    task_id: str
    target_id: str
    task_role: str
    cue_type: str
    action: str
    instruction: str
    priority: int
    depth_requirement: str
    n_gaussians: int = Field(ge=0)
    sigma_value: float = Field(gt=0)
    sigma_units: Literal['relative','m']
    sigma_profile: str
    pose: Pose
    goal_pose: Pose | None = None
    angle_deg: float | None = None
    reference_id: str | None = None

class DisplayPacket(Strict):
    schema_version: Literal['1.0'] = '1.0'
    session_id: str
    scene_id: str
    revision: int
    epoch: int
    execution: str
    renderer_kind: Literal['semantic_preview','calibrated_optical']
    axes: Literal['right_handed_z_up'] = 'right_handed_z_up'
    units: Literal['m'] = 'm'
    calibration_id: str
    budget_total: int
    cues: list[DisplayCue]
