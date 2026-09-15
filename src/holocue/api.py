from __future__ import annotations
import argparse,os,hmac
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI,Depends,HTTPException,Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from .config import root,list_scenes,load_scene
from .models import UserMessage,RevisionRequest,Strict
from .state import DomainError,ConflictError
from .store import Store
from .service import Service

class NewSession(Strict):scene_id:str

def create_app(service=None)->FastAPI:
    if service is None:
        from .provider import OpenAICompatiblePlanner,ReplayPlanner
        from .graph import GraphPlanner
        mode=os.environ.get('HOLOCUE_MODE','live')
        if mode not in ('live','replay'):raise ValueError('HOLOCUE_MODE must be live or replay')
        provider=OpenAICompatiblePlanner() if mode=='live' else ReplayPlanner(root()/'examples/replay.json')
        service=Service(Store(root()/'runs/state.sqlite'),GraphPlanner(provider))
    async def authorization(authorization:str|None=Header(default=None)):
        key=os.environ.get('HOLOCUE_API_KEY','')
        if key and not hmac.compare_digest(authorization or '',f'Bearer {key}'):
            raise HTTPException(401,'invalid API token')
    @asynccontextmanager
    async def lifespan(app):
        service.store.recover()
        yield
        await service.close()
    app=FastAPI(title='HoloCue',version='0.1.0',lifespan=lifespan,dependencies=[Depends(authorization)])
    app.state.service=service
    @app.exception_handler(ConflictError)
    async def conflict(req,e):return JSONResponse(status_code=409,content={'detail':str(e)})
    @app.exception_handler(DomainError)
    async def domain(req,e):return JSONResponse(status_code=422,content={'detail':str(e)})
    @app.exception_handler(KeyError)
    async def missing(req,e):return JSONResponse(status_code=404,content={'detail':str(e)})
    @app.exception_handler(FileNotFoundError)
    async def file_missing(req,e):return JSONResponse(status_code=404,content={'detail':'scene/resource not found'})
    @app.get('/health')
    def health():return {'status':'ok','backend_mode':service.planner.mode,'renderer_kind':'semantic_preview','schema_version':'1.0'}
    @app.get('/api/v1/scenes')
    def scenes():return list_scenes()
    @app.get('/api/v1/scenes/{scene_id}')
    def scene(scene_id:str):return load_scene(scene_id)
    @app.post('/api/v1/sessions',status_code=201)
    def new_session(body:NewSession):return service.create(body.scene_id)
    @app.get('/api/v1/sessions/{sid}')
    def session(sid:str):return service.store.get(sid)
    @app.post('/api/v1/sessions/{sid}/messages',status_code=202)
    async def message(sid:str,body:UserMessage):return await service.submit(sid,body)
    @app.get('/api/v1/jobs/{jid}')
    def job(jid:str):return service.store.job(jid)
    @app.get('/api/v1/sessions/{sid}/display')
    def display(sid:str):return service.display(sid)
    @app.get('/api/v1/sessions/{sid}/events')
    def events(sid:str):return service.store.events(sid)
    @app.post('/api/v1/sessions/{sid}/control/{operation}')
    def control(sid:str,operation:str,body:RevisionRequest):
        if operation not in ('pause','resume','complete'):raise HTTPException(422,'unknown control operation')
        return service.manual(sid,body.expected_revision,operation)
    return app

def main():
    p=argparse.ArgumentParser();p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=8750)
    a=p.parse_args()
    if a.host not in ('127.0.0.1','localhost','::1') and not os.environ.get('HOLOCUE_API_KEY'):
        raise SystemExit('Non-loopback binding requires HOLOCUE_API_KEY. Use SSH tunnels for phase 1.')
    import uvicorn
    uvicorn.run(create_app(),host=a.host,port=a.port,workers=1)
if __name__=='__main__':main()
