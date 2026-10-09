# SPDX-License-Identifier: GPL-3.0-or-later
"""Installed core's explicit region API rendered in Blender, not operator acceptance."""
import argparse
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--zip',type=Path,required=True)
    p.add_argument('--proposals',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    args.output_dir=args.output_dir.resolve()
    assert bpy.ops.preferences.addon_install(filepath=str(args.zip.resolve()),overwrite=True)=={'FINISHED'}
    assert bpy.ops.preferences.addon_enable(module='roof_generator')=={'FINISHED'}
    from roof_generator.core.footprint import analyze
    from roof_generator.core.roof_regions import propose_regions
    from roof_generator.core.region_generation import region_candidates
    from roof_generator.core.generation import GenerationSettings
    import roof_generator
    rows=[]
    for case in json.loads(args.proposals.read_text(encoding='utf-8'))['cases']:
        for obj in tuple(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
        fp=analyze(case['input']['footprint'])
        proposals=[propose_regions(fp,[tuple(fp.frame.world_xy(v) for v in r['boundary'])
                   for r in record['regions']],source=record['source'])
                   for record in case['records'] if 'id' in record]
        pool=region_candidates(proposals,GenerationSettings(max_axis_assignments=65536))
        row={'name':case['name'],'embedded_candidates':len(pool.valid),'complete':pool.complete,
             'scope':'installed explicit region API; not footprint operator acceptance'}
        if pool.valid:
            roof=pool.select(0)
            def mesh(name,points,faces,color):
                data=bpy.data.meshes.new(name);data.from_pydata(points,[],faces);data.update()
                obj=bpy.data.objects.new(name,data);bpy.context.scene.collection.objects.link(obj)
                mat=bpy.data.materials.new(name);mat.diffuse_color=(*color,1);data.materials.append(mat)
                return obj
            points=[fp.frame.world_xyz(v) for v in roof.mesh.vertices]
            obj=mesh('resolved_roof',points,roof.mesh.faces,(.5,.2,.08))
            attribute=obj.data.attributes.new('roof_feature_i','INT','EDGE')
            codes={'ridge':1,'hip':2,'valley':3,'eave':4,'gable_end':5}
            for edge in obj.data.edges:
                attribute.data[edge.index].value=codes[roof.mesh.edge_features[tuple(sorted(edge.vertices))]]
            colors=((.2,.4,.7),(.2,.6,.3),(.6,.3,.15))
            bounds=[fp.frame.world_xy(v) for v in fp.vertices]
            width=max(v[0] for v in bounds)-min(v[0] for v in bounds)
            for i,r in enumerate(roof.architecture.layout.candidate.regions):
                xy=[fp.frame.world_xy(v) for v in r.boundary]
                mesh('region_'+str(i),[(x-width*1.5,y,0) for x,y in xy],[(0,1,2,3)],colors[i%len(colors)])
            sys.path.insert(0,str(Path(__file__).resolve().parent))
            from blender_authority_acceptance import overlay,render
            overlay(obj)
            output=args.output_dir/case['name'];output.mkdir(parents=True,exist_ok=True)
            render(output)
            row.update(candidate_id=roof.id,vertices=len(obj.data.vertices),faces=len(obj.data.polygons),
                       image=case['name']+'/meshes.png')
            bpy.ops.wm.save_as_mainfile(filepath=str((output/'roof.blend').resolve()))
        rows.append(row)
        print(row,flush=True)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    report={'module_under_isolated_scripts':Path(roof_generator.__file__).is_relative_to(Path(bpy.utils.user_resource('SCRIPTS'))),
            'cases':rows}
    (args.output_dir/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
