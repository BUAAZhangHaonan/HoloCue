from __future__ import annotations
import numpy as np

def quaternion_matrix(q):
    w,x,y,z=q
    return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                     [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                     [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]],dtype=float)

def quaternion_product(a,b):
    w,x,y,z=a;v,i,j,k=b
    return (w*v-x*i-y*j-z*k,w*i+x*v+y*k-z*j,w*j-x*k+y*v+z*i,w*k+x*j-y*i+z*v)

def display_pose(cue,elapsed:float,running:bool):
    """Preview-only motion; it never changes physical scene state or marks a task complete."""
    import math
    t=max(elapsed,0) if running else 0.
    phase=(1-math.cos(2*math.pi*t/4.))/2
    xyz=np.asarray(cue.pose.position_m,dtype=float)
    q=cue.pose.wxyz
    if cue.action in ('insert','assemble') and cue.goal_pose is not None:
        xyz=(1-phase)*xyz+phase*np.asarray(cue.goal_pose.position_m)
    elif cue.action in ('rotate','inspect_back'):
        angle=(cue.angle_deg if cue.angle_deg is not None else 180.)*phase*math.pi/180.
        q=quaternion_product(q,(math.cos(angle/2),0.,0.,math.sin(angle/2)))
    return tuple(float(x) for x in xyz),q

def primitive_pool(kind:str,count:int=8192,seed:int=7)->np.ndarray:
    """Fixed-seed, nested sampling of cue geometry, not learned optical Gaussians."""
    rng=np.random.default_rng(seed)
    u=rng.random(count)
    if kind=='ring_arrow':
        a=(.2+1.65*u)*np.pi
        p=np.stack([.052*np.cos(a),.052*np.sin(a),np.full(count,.065)],axis=1)
        end=int(.12*count)
        # Arrow tip portion.
        p[:end]=np.stack([.034+.018*rng.random(end),-.036+.018*rng.random(end),np.full(end,.065)],axis=1)
    elif kind=='straight_arrow':
        p=np.stack([np.zeros(count),.09*u,np.full(count,.075)],axis=1)
        mask=u>.7
        v=rng.random(mask.sum())
        p[mask,0]=np.where(v<.5,-1.,1.)*(1-(u[mask]-.7)/.3)*.023
    else:
        a=u*2*np.pi
        p=np.stack([.054*np.cos(a),.054*np.sin(a),np.full(count,.065)],axis=1)
    # A fixed shuffle makes every prefix cover the full cue rather than just its tip.
    p=p[rng.permutation(count)]
    return p.astype('float32')
