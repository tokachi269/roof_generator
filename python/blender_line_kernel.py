# SPDX-License-Identifier: GPL-3.0-or-later
"""Convert completed full-Line complexes without an addon or geometry repair."""
import argparse
import json
from pathlib import Path
import sys
import bpy
import bmesh

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from python.audit_line_kernel import record_model
from python.roof_kernel.wavefront import construct
from python.roof_kernel.mesh import view
from python.blender_smoke_test import render


def records():
    return json.loads((ROOT/'python/tests/fixtures/kernel_line_construction.json').read_text())['records']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'python/out/line-kernel/blender')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    args.output.mkdir(parents=True,exist_ok=True)
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    rows=[]
    palette=((.25,.52,.73,1.),(.83,.48,.25,1.),(.5,.69,.36,1.),(.67,.39,.64,1.),(.77,.67,.32,1.))
    for record in records():
        result=construct(*record_model(record));walls=record.get('include_walls',False)
        mesh=view(result,pitch=.65,eave_height=2.5,include_walls=walls)
        data=bpy.data.meshes.new(record['name']);data.from_pydata(mesh.vertices,[],mesh.faces);data.update()
        assert not data.validate(verbose=True,clean_customdata=False)
        obj=bpy.data.objects.new(record['name'],data);bpy.context.scene.collection.objects.link(obj)
        # Object display transforms have no influence on kernel input or output.
        lo=tuple(min(v[k] for v in mesh.vertices) for k in (0,1))
        hi=tuple(max(v[k] for v in mesh.vertices) for k in (0,1))
        display_scale=14./max(hi[k]-lo[k] for k in (0,1))
        obj.scale=(display_scale,)*3
        obj.location=(len(rows)%3*25.-lo[0]*display_scale,len(rows)//3*25.-lo[1]*display_scale,0.)
        obj.rotation_euler.z=.12*(len(rows)%3)
        attribute=data.attributes.new('source_patch_i','INT','FACE')
        obj['patch_sources']=json.dumps(mesh.sources);obj['boundary_intent']=json.dumps(dict(result.intent.roles))
        obj['authority']='completed full-Line wavefront complex; explicit intent'
        obj['surface_profile']='wall-inclusive complex' if walls else 'inclined roof surface'
        obj['source_vertices']=json.dumps(mesh.source_vertices)
        for i,role in enumerate(mesh.roles):
            mat=bpy.data.materials.new(record['name']+'_'+str(i));mat.diffuse_color=palette[i%len(palette)]
            data.materials.append(mat);data.polygons[i].material_index=i;attribute.data[i].value=i
        bm=bmesh.new();bm.from_mesh(data)
        try:
            assert len(bm.verts)-len(bm.edges)+len(bm.faces)==1
            assert all(e.is_boundary or e.is_manifold for e in bm.edges)
            assert all(v.is_manifold for v in bm.verts)
            assert all(f.calc_area()>1e-8 for f in bm.faces)
            assert all(f.normal.z>0 for f,role in zip(bm.faces,mesh.roles) if role=='EAVE')
            assert all(abs((v.co-f.verts[0].co).dot(f.normal))<2e-5 for f in bm.faces for v in f.verts)
        finally:bm.free()
        for old in bpy.context.selected_objects:old.select_set(False)
        obj.select_set(True);bpy.context.view_layer.objects.active=obj
        bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
        assert bpy.ops.uv.smart_project(island_margin=.03)=={'FINISHED'}
        bpy.ops.object.mode_set(mode='OBJECT')
        assert data.uv_layers.active and any(abs(v.uv.x)+abs(v.uv.y)>0 for v in data.uv_layers.active.data)
        assert len(data.vertices)==len(mesh.vertices)
        assert [tuple(p.vertices) for p in data.polygons]==list(mesh.faces)
        rows.append({'name':record['name'],'profile':obj['surface_profile'],'vertices':len(mesh.vertices),
                     'faces':len(mesh.faces),'events':len(result.events),'planar_manifold_disk':True,
                     'normals':True,'uv':True,'materials':True,'source_provenance':True,'topology_modified':False})
    render(args.output)
    bpy.ops.wm.save_as_mainfile(filepath=str((args.output/'complexes.blend').resolve()))
    (args.output/'report.json').write_text(json.dumps({'production_adapter':False,'meshes':rows},indent=2)+'\n')
    print(json.dumps({'completed_complex_meshes':len(rows),'status':'validated'}))


if __name__=='__main__':main()
