# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent finite-model checks for axis and end preference."""
from itertools import combinations, product
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'addon'))
from python.roof_preference import recommend
from python.roof_intent import RoofIntent, IntentError, gable_configurations
from roof_generator.core.footprint import analyze, EPS
from roof_generator.core.member_layout import member_layout
from roof_generator.core.roof_regions import propose_regions


class ArchitecturalPreference(unittest.TestCase):
    def test_transverse_axis_remains_legal_when_compatible_ends_require_it(self):
        outline=[(0,0),(10,0),(10,4),(0,4)]
        fp=analyze(outline);layout=member_layout(propose_regions(fp,(outline,),source='declared'))
        region=layout.candidate.regions[0]
        size=[max(p[k] for p in region.boundary)-min(p[k] for p in region.boundary) for k in (0,1)]
        long=0 if size[0]>size[1] else 1
        edge=next(i for i,(a,b) in enumerate(zip(fp.vertices,fp.vertices[1:]+fp.vertices[:1]))
                  if abs(a[long]-b[long])>EPS)
        self.assertEqual(gable_configurations(layout,(edge,),axes=((long,),)).configurations,())
        pool=recommend(layout,(edge,))
        self.assertTrue(pool.complete)
        self.assertEqual(len(pool.configurations),1)
        self.assertEqual(pool.configurations[0].axis_domains,((1-long,),))
        # Restoring the natural end alternatives prefers the long ridge axis.
        pool=recommend(layout,range(4))
        self.assertEqual({c.axis_domains for c in pool.configurations},{((long,),)})

    def test_componentwise_preferences_equal_exhaustive_model_order(self):
        outline=[(0,0),(6,0),(6,3),(8,3),(8,6),(1,6),(1,3),(0,3)]
        regions=([(1,0),(6,0),(6,6),(1,6)],[(0,0),(1,0),(1,3),(0,3)],[(6,3),(8,3),(8,6),(6,6)])
        fp=analyze(outline);layout=member_layout(propose_regions(fp,regions,source='declared'))
        long=[]
        for region in layout.candidate.regions:
            sizes=[max(p[k] for p in region.boundary)-min(p[k] for p in region.boundary) for k in (0,1)]
            long.append({0,1} if abs(sizes[0]-sizes[1])<=4*EPS else {0 if sizes[0]>sizes[1] else 1})
        available=(0,1,2,4,5,6);conflicts=((0,1),(2,4))
        feasible=[]
        for axes in product((0,1),repeat=len(layout.supports)):
            for count in range(1,len(available)+1):
                for selected in combinations(available,count):
                    if any(a in selected and b in selected for a,b in conflicts):continue
                    try:RoofIntent.from_caps(layout,axes,selected)
                    except IntentError:continue
                    transverse=frozenset(i for i,a in enumerate(axes) if a not in long[i])
                    feasible.append((selected,axes,transverse))
        preferred=[(s,a,t) for s,a,t in feasible if not any(u<t for _,_,u in feasible)]
        expected={(s,a) for s,a,t in preferred if not any(a==b and set(s)<set(r) for r,b,u in preferred)}
        pool=recommend(layout,available,conflicts,max_work=1000000)
        self.assertTrue(pool.complete)
        actual={(c.selected,a) for c in pool.configurations for a in product(*c.axis_domains)}
        self.assertEqual(actual,expected)
        limited=recommend(layout,available,conflicts,max_work=1)
        self.assertFalse(limited.complete)
        self.assertEqual(limited.configurations,())


if __name__=='__main__':unittest.main()
