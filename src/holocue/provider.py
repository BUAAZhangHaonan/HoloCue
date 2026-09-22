from __future__ import annotations
import os, json, time, base64, hashlib
import io
from copy import deepcopy
import httpx
from PIL import Image
from .models import Decision, Session, SceneSpec, UserMessage
from .config import root


class PlannerError(RuntimeError):
    def __init__(self, message, trace):
        super().__init__(message)
        self.trace = trace


def permitted_operations(session: Session) -> list[str]:
    """Restrict decoding from persisted task state, never from instruction text."""
    allowed = ["replace", "pause", "clarify"]
    if session.queue or session.suspended:
        allowed.append("interrupt")
    if session.queue:
        allowed.append("complete")
    if (session.queue or session.suspended) and not (session.queue and session.suspended):
        allowed.append("resume")
    return allowed


def committed_history(session: Session) -> list[dict[str, str]]:
    """Only assistant-acknowledged turns are conversation context.

    Store.begin records each user request before planning; a later request can
    supersede it without an assistant commit. Consecutive user records therefore
    do not constitute several completed turns. The raw history remains in Store
    and is copied to the request trace for auditing.
    """
    result = []
    pending = None
    for message in session.history:
        if message.get("role") == "user":
            pending = message
        elif message.get("role") == "assistant":
            if pending is not None:
                result.append(dict(pending))
                pending = None
            result.append(dict(message))
        else:
            raise ValueError("history contains an unsupported conversation role")
    return result


def validate_model_decision(decision: Decision) -> None:
    """Reject an invalid model channel without rewriting any generated content.

    Domain controls may carry factual status text; generated non-clarification
    decisions carry only operation/cues and a null explanation field.
    """
    if decision.operation != "clarify" and decision.assistant_message is not None:
        raise ValueError("model assistant_message must be null except for clarify")


def decision_schema(session: Session, scene: SceneSpec) -> dict:
    """Expose domain operation/role constraints to the model's JSON decoder.

    Pydantic's after-validators are retained on the returned raw decision, but
    those validators do not automatically appear in model_json_schema().
    """
    base = Decision.model_json_schema()
    definitions = base.pop("$defs")
    # A generated plan has no separate execution narrative. Clarification keeps
    # a real model-written question; all task instructions remain model output.
    base["properties"] = {key: base["properties"][key] for key in ("operation", "cues", "assistant_message")}
    for name, roles in (
        ("CurrentCue", ["current"]),
        ("NextCue", ["next"]),
        ("BackgroundCue", ["background"]),
    ):
        variants = []
        for action in ("point", "rotate", "inspect_back", "insert", "assemble", "wait"):
            targets = [obj.object_id for obj in scene.objects if action in obj.capabilities]
            if not targets:
                continue
            cue = deepcopy(definitions["CueSemantic"])
            fields = cue["properties"]
            fields["target_id"] = {"type": "string", "enum": targets}
            fields["task_role"] = {"enum": roles, "type": "string"}
            fields["action"] = {"const": action, "type": "string"}
            fields["priority"]["minimum"] = 1
            # These semantic requirements already exist in the domain validator.
            # Exposing them to the decoder prevents omission, not inference of
            # the angle or receiver: the model still supplies both values.
            fields["angle_deg"] = (
                {"type": "number", "minimum": -360, "maximum": 360}
                if action == "rotate"
                else {"type": "null"}
            )
            fields["reference_id"] = (
                {"type": "string", "minLength": 1} if action in ("insert", "assemble") else {"type": "null"}
            )
            kinds = {
                "rotate": ["ring_arrow"],
                "insert": ["ghost_motion"],
                "assemble": ["ghost_motion"],
                "inspect_back": ["highlight"],
                "point": ["highlight", "straight_arrow", "label"],
                "wait": ["label"],
            }
            fields["cue_type"] = {"type": "string", "enum": kinds[action]}
            cue["required"] = list(fields)
            variants.append(cue)
        definitions[name] = {"anyOf": variants}
    definitions["FollowingCue"] = {
        "anyOf": [*definitions.pop("NextCue")["anyOf"], *definitions.pop("BackgroundCue")["anyOf"]]
    }
    allowed = permitted_operations(session)
    plan = deepcopy(base)
    plan["properties"]["operation"]["enum"] = [
        value for value in allowed if value in ("replace", "interrupt")
    ]
    plan["properties"]["assistant_message"] = {"type": "null"}
    plan["properties"]["cues"] = {
        "type": "array",
        "minItems": 1,
        "maxItems": 8,
        "prefixItems": [{"$ref": "#/$defs/CurrentCue"}],
        "items": {"$ref": "#/$defs/FollowingCue"},
    }
    plan["required"] = list(plan["properties"])
    control = deepcopy(base)
    control["properties"]["operation"]["enum"] = [
        value for value in allowed if value not in ("replace", "interrupt", "clarify")
    ]
    control["properties"]["assistant_message"] = {"type": "null"}
    control["properties"]["cues"] = {"type": "array", "maxItems": 0, "items": False}
    control["required"] = list(control["properties"])
    clarification = deepcopy(control)
    clarification["properties"]["operation"]["enum"] = ["clarify"]
    clarification["properties"]["assistant_message"] = {"type": "string", "minLength": 1, "maxLength": 300}
    return {"type": "object", "$defs": definitions, "anyOf": [plan, control, clarification]}


class OpenAICompatiblePlanner:
    """Strict local-model requests with recorded inputs, outputs and execution errors."""

    mode = "live"

    def __init__(self):
        self.base = os.environ.get("HOLOCUE_MODEL_URL", "http://127.0.0.1:8000/v1").rstrip("/")
        self.model = os.environ.get("HOLOCUE_MODEL_NAME", "Qwen/Qwen3.5-4B")
        self.key = os.environ.get("HOLOCUE_MODEL_API_KEY", "")
        self.prompt = (root() / "prompts/planner.md").read_text(encoding="utf-8")

    def request_body(self, s: Session, scene: SceneSpec, msg: UserMessage):
        history = committed_history(s)
        scene_view = [
            {
                "object_id": o.object_id,
                "label": o.label,
                "description": o.description,
                "capabilities": o.capabilities,
                "rotation_axis_local": o.interaction.rotation_axis_local,
            }
            for o in scene.objects
        ]
        context = {
            "permitted_operations": permitted_operations(s),
            "task_state": (
                "temporary_task_active"
                if s.queue and s.suspended
                else "active_plan"
                if s.queue
                else "awaiting_resume"
                if s.suspended
                else "empty"
            ),
            "scene_id": scene.scene_id,
            "setting": scene.task_contract.setting,
            "objects": scene_view,
            "queue": [t.model_dump() for t in s.queue],
            "suspended": [[t.model_dump() for t in q] for q in s.suspended],
            "completed": [t.model_dump() for t in s.completed],
            "history": history,
            "execution": s.execution,
            "user_instruction": msg.text,
        }
        content = [{"type": "text", "text": json.dumps(context, ensure_ascii=False)}]
        if msg.image_base64:
            data = base64.b64decode(msg.image_base64, validate=True)
            if len(data) > 1_500_000:
                raise ValueError("image too large")
            with Image.open(io.BytesIO(data)) as image:
                if image.width * image.height > 1_048_576:
                    raise ValueError("resize image to at most 1024x1024")
                if image.format not in ("PNG", "JPEG"):
                    raise ValueError("only PNG/JPEG supported")
                if {"PNG": "image/png", "JPEG": "image/jpeg"}[image.format] != msg.image_mime:
                    raise ValueError("image MIME type and encoded format disagree")
                image.verify()
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{msg.image_mime};base64,{msg.image_base64}"},
                }
            )
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": self.prompt}, {"role": "user", "content": content}],
            "temperature": 0.2,
            "top_p": 0.8,
            "max_tokens": 1600,
            "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "semantic_decision",
                    "strict": True,
                    "schema": decision_schema(s, scene),
                },
            },
        }
        return body

    async def decide(self, s: Session, scene: SceneSpec, msg: UserMessage):
        t0 = time.perf_counter()
        body = self.request_body(s, scene, msg)
        headers = {"Authorization": f"Bearer {self.key}"} if self.key else {}
        # One request is the unit of evidence. Error bodies remain visible to the caller.
        trace = {
            "backend_mode": "live",
            "model": self.model,
            "request_body": body,
            "session_history": [dict(message) for message in s.history],
            "prompt_sha256": hashlib.sha256(self.prompt.encode()).hexdigest(),
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(90, connect=5)) as client:
                response = await client.post(self.base + "/chat/completions", json=body, headers=headers)
                trace.update({"http_status": response.status_code, "raw_http_body": response.text})
                response.raise_for_status()
                data = response.json()
            choice = data["choices"][0]
            raw = choice["message"].get("content")
            trace.update(
                {"usage": data.get("usage", {}), "raw_response": raw, "latency_s": time.perf_counter() - t0}
            )
            if choice.get("finish_reason") != "stop":
                raise RuntimeError("generation did not finish cleanly")
            if not isinstance(raw, str):
                raise RuntimeError("model returned no JSON content")
            d = Decision.model_validate_json(raw)
            validate_model_decision(d)
            if d.operation not in permitted_operations(s):
                raise ValueError(f"operation {d.operation} is not permitted by the current task state")
            return d, trace
        except Exception as e:
            trace["latency_s"] = time.perf_counter() - t0
            raise PlannerError(f"{type(e).__name__}: {e}", trace) from e
