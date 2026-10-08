# SPDX-License-Identifier: GPL-3.0-or-later
"""The distributable API and planar mesh adapter run without binary packages."""

from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]


class RuntimeProof(unittest.TestCase):
    def test_canonical_api_and_adapter_in_isolated_stdlib_process(self):
        code = """import sys, importlib.abc
sys.path.insert(0, sys.argv[1]+'/addon')
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self,name,path=None,target=None):
  if name.split('.')[0] in {'numpy','shapely'}:raise RuntimeError('binary dependency: '+name)
sys.meta_path.insert(0,Block())
from roof_generator.core.generation import generate_roof, prepare_generation, GenerationSettings
from roof_generator.mesh_input import generate_footprint_mesh
from roof_generator.core.errors import UnsupportedRoofError
points=((0,0),(12,0),(12,6),(0,6))
for kind in ('gable','hip','shed','flat'):
 result=generate_roof(points,GenerationSettings(kind,seed=42))
 assert result.mesh.faces
 assert generate_footprint_mesh(tuple((*p,0) for p in points),((0,1,2,3),),GenerationSettings(kind)).spec.faces
compound=((0,0),(16,0),(16,4),(10,4),(10,10),(6,10),(6,4),(0,4))
assert prepare_generation(compound).geometry_problem.faces
assert len(generate_roof(compound,GenerationSettings('flat')).mesh.faces)==1
assert generate_roof(compound).mesh.faces
assert not {'numpy','shapely'}.intersection(sys.modules)
"""
        out = subprocess.run(
            [sys.executable, "-I", "-c", code, str(ROOT)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(out.returncode, 0, out.stderr)


if __name__ == "__main__":
    unittest.main()
