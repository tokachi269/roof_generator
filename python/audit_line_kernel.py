# SPDX-License-Identifier: GPL-3.0-or-later
"""Separate frozen input families and failure owners for the full-Line kernel."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from python.roof_kernel.boundary import BoundaryPath,Line,RoofIntent,InvalidBoundary,InvalidIntent,UnspecifiedModel
from python.roof_kernel.wavefront import construct
from python.roof_kernel.admissibility import InconsistentIntent
from python.roof_kernel.precision import PrecisionLimit
from python.roof_kernel.complex import KernelFailure,KernelLimit
from python.roof_kernel.mesh import view,MeshResolutionError


def record_model(record):
    points=tuple(tuple(p) for p in record['footprint'])
    ids=tuple(record.get('source_ids',[f'edge{i}' for i in range(len(points))]))
    path=BoundaryPath(tuple(Line(sid,a,b) for sid,a,b in zip(ids,points,points[1:]+points[:1])))
    roles=record.get('roles',['EAVE']*len(points))
    return path,RoofIntent(tuple(zip(ids,roles)))


def oracle(result):
    import numpy as np
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    xyz=np.asarray(result.coordinates())
    original=Polygon(np.asarray(result.boundary.outline,dtype=float))
    projected=[]
    for face in result.patches+result.walls:
        points=xyz[list(face.loop)]
        if np.linalg.svd(points-points.mean(axis=0),compute_uv=False)[-1]>1e-7:
            raise AssertionError('independent SVD found a nonplanar source patch')
        if face in result.patches:
            shape=Polygon(points[:,:2])
            if not shape.is_valid or shape.area<=0:raise AssertionError('independent projected face is invalid')
            projected.append(shape)
    union=unary_union(projected)
    error=union.symmetric_difference(original).area
    overlap=sum(p.area for p in projected)-union.area
    tolerance=1e-9*max(original.area,1)
    if error>tolerance or abs(overlap)>tolerance:raise AssertionError('independent projected coverage/overlap mismatch')
    return {'coverage_error':error,'overlap_error':overlap,'roof_patches':len(projected)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus',type=Path,default=ROOT/'python/docs/canonical/coverage_inputs_v1.json.gz')
    parser.add_argument('--category',action='append')
    parser.add_argument('--limit',type=int)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--oracle',action='store_true')
    args=parser.parse_args()
    data=args.corpus.read_bytes()
    if args.corpus.suffix=='.gz':data=gzip.decompress(data)
    corpus=json.loads(data)
    summaries={};details=[]
    for category,records in corpus['corpora'].items():
        if args.category and category not in args.category:continue
        counts=Counter();start=time.perf_counter()
        for i,record in enumerate(records[:args.limit]):
            row={'category':category,'name':record['name'],'requested_intent':record.get('roles','explicit all-eave'),
                 'footprint':False,'completed_complex':False,'independent_validation':False}
            begin=time.perf_counter()
            try:
                path,intent=record_model(record);row['footprint']=True
                result=construct(path,intent)
                row.update(completed_complex=True,vertices=len(result.vertices),roof_patches=len(result.patches),
                           walls=len(result.walls),events=len(result.events),work=result.work,predicates=result.precision.inspect())
                counts['completed_complex']+=1
                mesh=view(result,include_walls=True)
                row.update(float_mesh=True,mesh_vertices=len(mesh.vertices),mesh_faces=len(mesh.faces))
                counts['float_mesh']+=1
                if args.oracle:row['oracle']=oracle(result);row['independent_validation']=True
                if args.oracle:counts['independent_validation']+=1
            except InvalidBoundary as exc:row.update(owner='input_geometry',reason=str(exc))
            except InvalidIntent as exc:row.update(owner='intent_syntax',reason=str(exc))
            except InconsistentIntent as exc:row.update(owner='intent_nonexistence',reason=str(exc),certificate=exc.certificate)
            except UnspecifiedModel as exc:row.update(owner='model_rule',reason=str(exc))
            except (PrecisionLimit,KernelLimit) as exc:row.update(owner='execution_incomplete',reason=str(exc))
            except KernelFailure as exc:row.update(owner='kernel_bug',reason=str(exc))
            except MeshResolutionError as exc:row.update(owner='mesh_resolution',reason=str(exc))
            except AssertionError as exc:row.update(owner='independent_validation_failure',reason=str(exc))
            except Exception as exc:row.update(owner='unexpected_bug',reason=type(exc).__name__+': '+str(exc))
            row['total_ms']=(time.perf_counter()-begin)*1000
            counts['inputs']+=1;counts['footprint']+=row['footprint']
            if 'owner' in row:counts[row['owner']]+=1;row['input']=record
            details.append(row)
            if (i+1)%20==0:print(category,i+1,dict(counts),round(time.perf_counter()-start,1),flush=True)
        summaries[category]=dict(counts)
    report={'scope':'full-Line kernel, separate frozen corpora; not production addon coverage',
            'wall_model':'stationary source wall patches are separate from inclined roof patches',
            'corpora':summaries}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    args.output.with_suffix('.jsonl.gz').write_bytes(gzip.compress(''.join(json.dumps(row)+'\n' for row in details).encode(),mtime=0))
    print(json.dumps(summaries),flush=True)


if __name__=='__main__':main()
