# SPDX-License-Identifier: GPL-3.0-or-later
"""Mesh the independent convex proof as-is; not an addon generator adapter."""
import argparse
import json
from pathlib import Path
import sys
import bpy
import bmesh

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from python.roof_kernel_proof import construct, from_record
from python.blender_smoke_test import render


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'python/out/kernel-proof/blender')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    args.output.mkdir(parents=True,exist_ok=True)
    records=json.loads((ROOT/'python/tests/fixtures/kernel_line_proofs_v1.json').read_text())['records']
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    rows=[]
    for record in records:
        if record['proof']!='construction':continue
        result=construct(*from_record(record))
        data=bpy.data.meshes.new(record['name'])
        data.from_pydata(result.coordinates(),[],[p.loop for p in result.patches])
        data.update()
        assert not data.validate(verbose=True,clean_customdata=False)
        obj=bpy.data.objects.new(record['name'],data)
        bpy.context.scene.collection.objects.link(obj)
        obj.location=(len(rows)%3*19.,len(rows)//3*19.,0.)
        source_ids=sorted(s.id for s in result.boundary.sources)
        attribute=data.attributes.new('roof_source_i','INT','FACE')
        palette=((.32,.62,.78,1.),(.8,.45,.22,1.),(.52,.72,.38,1.),(.69,.4,.68,1.),(.78,.69,.3,1.),(.46,.6,.68,1.))
        for i,patch in enumerate(result.patches):
            material=bpy.data.materials.new(record['name']+'_'+patch.source)
            material.diffuse_color=palette[i%len(palette)]
            data.materials.append(material);data.polygons[i].material_index=i
            attribute.data[i].value=source_ids.index(patch.source)
        obj['source_ids']=json.dumps(source_ids)
        obj['boundary_intent']=json.dumps(dict(result.intent.roles))
        obj['authority']='independent convex space-time proof; not production generator'
        bm=bmesh.new();bm.from_mesh(data)
        try:
            assert len(bm.verts)-len(bm.edges)+len(bm.faces)==1
            assert all(e.is_boundary or e.is_manifold for e in bm.edges)
            assert all(v.is_manifold for v in bm.verts)
            assert all(f.normal.z>0 and f.calc_area()>1e-8 for f in bm.faces)
            assert all(abs((v.co-f.verts[0].co).dot(f.normal))<2e-5 for f in bm.faces for v in f.verts)
        finally:bm.free()
        for old in bpy.context.selected_objects:old.select_set(False)
        obj.select_set(True);bpy.context.view_layer.objects.active=obj
        bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
        assert bpy.ops.uv.smart_project(island_margin=.03)=={'FINISHED'}
        bpy.ops.object.mode_set(mode='OBJECT')
        assert data.uv_layers.active and any(abs(v.uv.x)+abs(v.uv.y)>0 for v in data.uv_layers.active.data)
        assert len(data.vertices)==len(result.vertices)
        assert [tuple(p.vertices) for p in data.polygons]==[p.loop for p in result.patches]
        rows.append({'name':record['name'],'vertices':len(data.vertices),'faces':len(data.polygons),
                     'planar_manifold_disk':True,'normals':True,'uv':True,'materials':True,
                     'source_provenance':True,'topology_modified':False})
    render(args.output)
    bpy.ops.wm.save_as_mainfile(filepath=str((args.output/'proofs.blend').resolve()))
    (args.output/'report.json').write_text(json.dumps({'production_adapter':False,'meshes':rows},indent=2)+'\n')
    print(json.dumps({'proof_meshes':len(rows),'status':'validated'}))


if __name__=='__main__':main()
