from __future__ import annotations
import asyncio
from .config import load_scene,load_policy,scene_fingerprint
from .models import UserMessage,Decision
from .store import Store
from .projection import packet
from .state import DomainError


def session_scene(session):
    scene=load_scene(session.scene_id)
    if session.scene_fingerprint!=scene_fingerprint(scene):
        raise DomainError('Scene geometry has changed. Create a new session for the current scene.')
    return scene

class Service:
    def __init__(self,store:Store,planner):
        self.store=store;self.planner=planner;self.tasks={};self.policy=load_policy()
    def create(self,scene_id):
        scene=load_scene(scene_id)
        return self.store.create(scene_id,self.planner.mode,scene_fingerprint(scene))
    async def submit(self,sid,msg:UserMessage):
        session_scene(self.store.get(sid))
        job,s,new=self.store.begin(sid,msg)
        if new:
            old=self.tasks.get(sid)
            if old and not old.done():old.cancel()
            self.tasks[sid]=asyncio.create_task(self._run(job['id'],s,msg))
        return self.store.job(job['id'])
    async def _run(self,jid,s,msg):
        trace={}
        try:
            scene=session_scene(s)
            d,trace=await self.planner.decide(s,scene,msg)
            self.store.commit(jid,d,scene,trace)
        except asyncio.CancelledError:
            # epoch invalidation already prevents a late response from committing.
            self.store.fail(jid,'request cancelled')
            raise
        except Exception as e:
            self.store.fail(jid,f'{type(e).__name__}: {e}',getattr(e,'trace',trace))
            raise
    def manual(self,sid,revision,operation):
        s=self.store.get(sid)
        if operation not in ('pause','resume','complete'):raise ValueError('unsupported manual operation')
        labels={'pause':'动作已暂停。','resume':'继续已保存的任务。','complete':'已记录当前步骤完成。'}
        return self.store.manual(sid,revision,Decision(operation=operation,assistant_message=labels[operation]),session_scene(s))
    def display(self,sid):
        s=self.store.get(sid)
        return packet(s,session_scene(s),self.policy)
    def snapshot(self,sid):
        s=self.store.get(sid)
        return {'state':s.model_dump(mode='json'),
                'display':packet(s,session_scene(s),self.policy).model_dump(mode='json')}
    async def close(self):
        for t in self.tasks.values():
            if not t.done():t.cancel()
        await asyncio.gather(*self.tasks.values(),return_exceptions=True)
