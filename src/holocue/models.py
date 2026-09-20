"""Versioned semantic contracts. All extra fields, including N/sigma from an LLM, are rejected."""
from __future__ import annotations
from typing import Literal
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

class Interaction(Strict):
    rotation_axis_local: tuple[float,float,float] = (0.,0.,1.)
    pivot_local_m: tuple[float,float,float] = (0.,0.,0.)
    mating_pose: Pose = Field(default_factory=Pose)
    departure_axis_local: tuple[float,float,float] = (0.,0.,1.)
    departure_distance_m: float = Field(default=.08,gt=0)
    approach_axis_local: tuple[float,float,float] = (0.,0.,1.)
    approach_distance_m: float = Field(default=.12,gt=0)
    transit_height_m: float = Field(default=.15,ge=0)
    inspect_point_local_m: tuple[float,float,float] = (0.,0.,0.)
    inspect_normal_local: tuple[float,float,float] = (0.,1.,0.)
    inspect_extent_m: tuple[float,float] | None = None
    inspect_cue_clearance_m: float = Field(default=.002,ge=0)
    detail_direction_local: tuple[float,float,float] | None = None
    cue_offset_local_m: tuple[float,float,float] = (0.,0.,.04)
    duration_s: float = Field(default=3.,gt=0)
    @field_validator('rotation_axis_local','departure_axis_local','approach_axis_local','inspect_normal_local','detail_direction_local')
    @classmethod
    def normalized_axis(cls,v):
        if v is not None and abs(sum(x*x for x in v)-1)>1e-4:
            raise ValueError('interaction axes must be unit vectors')
        return v
    @field_validator('inspect_extent_m')
    @classmethod
    def positive_inspection_extent(cls,v):
        if v is not None and min(v)<=0:
            raise ValueError('inspection extents must be positive')
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
    frames: dict[str,Pose] = Field(default_factory=dict)
    interaction: Interaction = Field(default_factory=Interaction)
    recipe: str = ''
    size_m: tuple[float,float,float] = (.10,.10,.10)

class SceneProp(Strict):
    prop_id: str = Field(pattern=r'^[A-Za-z][A-Za-z0-9_-]{0,47}$')
    label: str = ''
    asset: str
    pose: Pose = Field(default_factory=Pose)
    scale_m: tuple[float,float,float] = (1.,1.,1.)

class RenderHints(Strict):
    ortho_scale_m: float = Field(default=.91,gt=0)
    grid_extent_m: float = Field(default=1.,gt=0)
    cue_scale: float = Field(default=1.,gt=0)
    label_offset_m: float = Field(default=.12,ge=0)
    fit_camera: bool = True
    fill_lights: list[tuple[float,float,float,float,float]] = Field(default_factory=list)
    fov_y_deg: float = Field(default=42.,ge=20,le=80)
    viewport_margin: float = Field(default=.14,ge=.05,le=.35)
    background_rgb: tuple[int,int,int] = (233,238,242)
    workspace_bounds_m: tuple[tuple[float,float,float],tuple[float,float,float]] | None = None

class TaskStep(Strict):
    target_id: str
    action: str
    reference_id: str | None = None
    angle_deg: float | None = None
    depth_requirement: Literal['precise','persistent','neutral'] = 'precise'

class TaskContract(Strict):
    setting: str
    ordered_steps: list[TaskStep]
    persistent_targets: list[str] = Field(default_factory=list)
    interrupt_target: str
    interrupt_instruction: str

class SceneSpec(Strict):
    schema_version: Literal['1.0','1.1'] = '1.1'
    scene_id: str
    title: str
    units: Literal['m'] = 'm'
    axes: Literal['right_handed_z_up'] = 'right_handed_z_up'
    objects: list[SceneObject]
    initial_instruction: str
    camera_position_m: tuple[float,float,float] = (.8,-.85,.72)
    camera_look_at_m: tuple[float,float,float] = (0.,.12,.08)
    asset_axes: Literal['gltf_y_up','project_z_up'] = 'project_z_up'
    environment: list[SceneProp] = Field(default_factory=list)
    render_hints: RenderHints = Field(default_factory=RenderHints)
    task_contract: TaskContract | None = None
    @model_validator(mode='after')
    def unique_ids(self):
        ids=[x.object_id for x in self.objects]
        if len(ids)!=len(set(ids)):raise ValueError('duplicate scene object IDs')
        prop_ids=[p.prop_id for p in self.environment]
        if len(prop_ids)!=len(set(prop_ids)):raise ValueError('duplicate environment prop IDs')
        if self.task_contract:
            references={s.target_id for s in self.task_contract.ordered_steps}
            references.update(s.reference_id for s in self.task_contract.ordered_steps if s.reference_id)
            references.update(self.task_contract.persistent_targets)
            references.add(self.task_contract.interrupt_target)
            if not references.issubset(ids):raise ValueError('task contract references an unknown object')
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
        if self.action not in ('insert','assemble') and self.reference_id is not None:
            raise ValueError('reference_id belongs to insert and assemble actions')
        if self.task_role=='current' and self.priority==0:
            raise ValueError('current cue requires positive priority')
        return self

class Decision(Strict):
    operation: Literal['replace','interrupt','resume','complete','pause','clarify']
    assistant_message: str | None = Field(min_length=1,max_length=300)
    cues: list[CueSemantic] = Field(default_factory=list,max_length=8)
    @model_validator(mode='after')
    def decision_shape(self):
        if self.operation=='clarify' and not (self.assistant_message and self.assistant_message.strip()):
            raise ValueError('clarify requires a nonempty question')
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
        elif self.cues:
            raise ValueError('only replace/interrupt may carry new cues')
        return self

class Task(Strict):
    task_id: str
    semantic: CueSemantic

class Session(Strict):
    session_id: str
    scene_id: str
    scene_fingerprint: str = ''
    revision: int = 0
    epoch: int = 0
    execution: Literal['idle','running','paused','planning','error'] = 'idle'
    queue: list[Task] = Field(default_factory=list)
    suspended: list[list[Task]] = Field(default_factory=list)
    completed: list[Task] = Field(default_factory=list)
    history: list[dict[str,str]] = Field(default_factory=list)
    assistant_message: str | None = ''
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
    interaction: Interaction = Field(default_factory=Interaction)
    cue_extent_m: float = Field(default=.10,gt=0)

class DisplayPacket(Strict):
    schema_version: Literal['1.0','1.1'] = '1.1'
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
    object_poses: dict[str,Pose] = Field(default_factory=dict)
