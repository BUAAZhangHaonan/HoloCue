from __future__ import annotations
import asyncio
from .config import load_scene,load_policy
from .models import UserMessage,Decision
from .store import Store
from .projection import packet

class Service:
    def __init__(self,store:Store,planner):
        self.store=store;self.planner=planner;self.tasks={};self.policy=load_policy()
    def create(self,scene_id):
        load_scene(scene_id)
        return self.store.create(scene_id,self.planner.mode)
    async def submit(self,sid,msg:UserMessage):
        job,s,new=self.store.begin(sid,msg)
        if new:
            old=self.tasks.get(sid)
            if old and not old.done():old.cancel()
            self.tasks[sid]=asyncio.create_task(self._run(job['id'],s,msg))
        return self.store.job(job['id'])
    async def _run(self,jid,s,msg):
        trace={}
        try:
            scene=load_scene(s.scene_id)
            d,trace=await self.planner.decide(s,scene,msg)
            self.store.commit(jid,d,scene,trace)
        except asyncio.CancelledError:
            # epoch invalidation already prevents a late response from committing.
            self.store.fail(jid,'request cancelled')
            raise
        except Exception as e:
            self.store.fail(jid,f'{type(e).__name__}: {e}',getattr(e,'trace',trace))
    def manual(self,sid,revision,operation):
        s=self.store.get(sid)
        if operation not in ('pause','resume','complete'):raise ValueError('unsupported manual operation')
        labels={'pause':'动作已暂停。','resume':'继续已保存的任务。','complete':'已记录当前步骤完成。'}
        return self.store.manual(sid,revision,Decision(operation=operation,assistant_message=labels[operation]),load_scene(s.scene_id))
    def display(self,sid):
        s=self.store.get(sid)
        return packet(s,load_scene(s.scene_id),self.policy)
    async def close(self):
        for t in self.tasks.values():
            if not t.done():t.cancel()
        await asyncio.gather(*self.tasks.values(),return_exceptions=True)
