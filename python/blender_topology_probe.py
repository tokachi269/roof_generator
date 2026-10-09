# SPDX-License-Identifier: GPL-3.0-or-later
"""Inspect exported topology-prototype meshes in Blender; not addon acceptance."""
import argparse
import json
from pathlib import Path
import sys
import bpy


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--limit',type=int,default=10)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    args.output_dir=args.output_dir.resolve()
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    from blender_smoke_test import validate
    from blender_authority_acceptance import overlay,render
    rows=[]
    for row in json.loads(args.report.read_bytes())['rows']:
        if not row['embedded']:continue
        if len(rows)>=args.limit:break
        for obj in tuple(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
        graph=row['graph']
        data=bpy.data.meshes.new('roof')
        data.from_pydata([tuple(20*x for x in v) for v in row['vertices']],[],row['faces'])
        data.update()
        obj=bpy.data.objects.new('whole_polygon_roof',data)
        bpy.context.scene.collection.objects.link(obj)
        obj.select_set(True);bpy.context.view_layer.objects.active=obj
        material=bpy.data.materials.new('roof_material');material.diffuse_color=(.5,.2,.08,1)
        data.materials.append(material);data.uv_layers.new()
        features=data.attributes.new('roof_feature_i','INT','EDGE')
        data.attributes.new('roof_cell_i','INT','FACE')
        codes={'ridge':1,'hip':2,'valley':3,'eave':4,'gable_end':5}
        by_edge={tuple(e['vertices']):e['kind'] for e in graph['edges']}
        for edge in data.edges:features.data[edge.index].value=codes[by_edge[tuple(sorted(edge.vertices))]]
        validate(obj)
        overlay(obj)
        name=row.get('category','user_images')+'_'+row['name']
        output=args.output_dir/name;output.mkdir(parents=True,exist_ok=True)
        render(output)
        bpy.ops.wm.save_as_mainfile(filepath=str((output/'roof.blend').resolve()))
        rows.append({'name':name,'mesh_valid':True,'image':name+'/meshes.png',
                     'faces':len(data.polygons),'features':graph['features']})
    args.output_dir.mkdir(parents=True,exist_ok=True)
    report={'scope':__doc__,'blender':bpy.app.version_string,'cases':rows}
    (args.output_dir/'report.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
