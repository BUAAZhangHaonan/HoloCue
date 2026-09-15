from __future__ import annotations
import os,json,time,base64,hashlib
from pathlib import Path
import httpx
from .models import Decision,Session,SceneSpec,UserMessage
from .config import root

class PlannerError(RuntimeError):
    def __init__(self,message,trace):
        super().__init__(message);self.trace=trace

class OpenAICompatiblePlanner:
    """vLLM/SGLang JSON-schema requests. No text scraping, repair loops or hidden substitutions."""
    mode='live'
    def __init__(self):
        self.base=os.environ.get('HOLOCUE_MODEL_URL','http://127.0.0.1:8000/v1').rstrip('/')
        self.model=os.environ.get('HOLOCUE_MODEL_NAME','Qwen/Qwen3.5-4B')
        self.key=os.environ.get('HOLOCUE_MODEL_API_KEY','')
        self.prompt=(root()/'prompts/planner.md').read_text(encoding='utf-8')
    async def decide(self,s:Session,scene:SceneSpec,msg:UserMessage):
        t0=time.perf_counter()
        scene_view=[{'object_id':o.object_id,'label':o.label,'description':o.description,
                     'capabilities':o.capabilities} for o in scene.objects]
        context={'scene_id':scene.scene_id,'objects':scene_view,'queue':[t.model_dump() for t in s.queue],
                 'suspended':[[t.model_dump() for t in q] for q in s.suspended],
                 'completed':[t.semantic.instruction for t in s.completed],
                 'history':s.history,'execution':s.execution,'user_instruction':msg.text}
        content=[{'type':'text','text':json.dumps(context,ensure_ascii=False)}]
        if msg.image_base64:
            try:data=base64.b64decode(msg.image_base64,validate=True)
            except Exception as e:raise ValueError('invalid base64 image') from e
            if len(data)>1_500_000:raise ValueError('image too large')
            import io
            from PIL import Image
            with Image.open(io.BytesIO(data)) as image:
                if image.width*image.height>1_048_576:raise ValueError('resize image to at most 1024x1024')
                if image.format not in ('PNG','JPEG'):raise ValueError('only PNG/JPEG supported')
            content.append({'type':'image_url','image_url':{'url':f'data:{msg.image_mime};base64,{msg.image_base64}'}})
        body={'model':self.model,'messages':[{'role':'system','content':self.prompt},{'role':'user','content':content}],
              'temperature':0.2,'top_p':0.8,'max_tokens':1600,
              'chat_template_kwargs':{'enable_thinking':False},
              'response_format':{'type':'json_schema','json_schema':{'name':'semantic_decision','strict':True,'schema':Decision.model_json_schema()}}}
        headers={'Authorization':f'Bearer {self.key}'} if self.key else {}
        # One request is the unit of evidence. Error bodies remain visible to the caller.
        trace={'backend_mode':'live','model':self.model,'request_body':body,
               'prompt_sha256':hashlib.sha256(self.prompt.encode()).hexdigest()}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(90,connect=5)) as client:
                response=await client.post(self.base+'/chat/completions',json=body,headers=headers)
                trace.update({'http_status':response.status_code,'raw_http_body':response.text})
                response.raise_for_status();data=response.json()
            choice=data['choices'][0]
            raw=choice['message'].get('content')
            trace.update({'usage':data.get('usage',{}),'raw_response':raw,
                          'latency_s':time.perf_counter()-t0})
            if choice.get('finish_reason') not in ('stop',None):
                raise RuntimeError('generation did not finish cleanly')
            if not isinstance(raw,str):raise RuntimeError('model returned no JSON content')
            d=Decision.model_validate_json(raw)
            return d,trace
        except Exception as e:
            trace['latency_s']=time.perf_counter()-t0
            raise PlannerError(f'{type(e).__name__}: {e}',trace) from e

class ReplayPlanner:
    """Explicit fixture playback for plumbing tests only; it is never selected after live failure."""
    mode='replay'
    def __init__(self,path:Path):self.fixtures=json.loads(path.read_text(encoding='utf-8'))
    async def decide(self,s,scene,msg):
        for x in self.fixtures:
            if x['scene_id']==scene.scene_id and x['input']==msg.text:
                return Decision.model_validate(x['decision']),{'backend_mode':'replay','fixture':x['id'],'latency_s':0.}
        raise ValueError('No replay fixture for this exact input. Use live mode for natural language.')
