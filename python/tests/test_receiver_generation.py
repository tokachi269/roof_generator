# SPDX-License-Identifier: GPL-3.0-or-later
"""Previously unsupported screenshots through the canonical footprint entry."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'addon'))
from roof_generator.core.generation import generate_roof,prepare_generation,GenerationSettings
from roof_generator.core.errors import UnsupportedRoofError
from roof_generator.core.receiver_regions import receiver_regions
from roof_generator.core.footprint import analyze


class ReceiverGenerationProof(unittest.TestCase):
    def test_offset_bands_use_actual_receiver_supports_in_default_generation(self):
        records=json.loads((Path(__file__).parent/'fixtures/user_roof_images_v1.json').read_text(encoding='utf-8'))['inputs']
        for record in records:
            with self.subTest(record=record['name']):
                roof=generate_roof(record['footprint'])
                self.assertTrue(roof.mesh.faces)
                self.assertEqual(roof.mesh.graph,roof.generation.selected.graph)
                model=roof.generation.selected.architecture
                self.assertEqual(model.footprint,roof.generation.footprint)
                self.assertTrue(model.gable_edges)
                self.assertEqual({f.cells for f in roof.mesh.graph.faces},{(0,)})
                for edge in roof.mesh.graph.edges:
                    if edge.kind=='valley':
                        self.assertGreater(max(roof.mesh.vertices[i][2] for i in edge.vertices),0)

    def test_incomplete_receiver_search_never_uses_minimum_as_fallback(self):
        fp=analyze(((0,0),(12,0),(12,6),(0,6)))
        search=receiver_regions(fp,max_work=1)
        self.assertFalse(search.complete)
        with patch('roof_generator.core.polygon_generation.receiver_regions',return_value=search):
            with self.assertRaises(UnsupportedRoofError):prepare_generation(((0,0),(12,0),(12,6),(0,6)))

    def test_equivalent_rectangle_models_get_one_seed_probability(self):
        generation=prepare_generation(((0,0),(12,0),(12,6),(0,6)))
        self.assertEqual(len(generation.candidates.valid),1)
        self.assertEqual({g.proposal.source for g in generation.selected.guides},{'minimum_partition','receiver_regions'})

    def test_receiver_family_runs_even_when_minimum_already_constructs_a_roof(self):
        import roof_generator.core.polygon_generation as module
        raw=((0,0),(12,0),(12,6),(0,6))
        with patch.object(module,'receiver_regions',wraps=module.receiver_regions) as observer:
            prepare_generation(raw)
        observer.assert_called_once()

    def test_residential_actual_support_crosses_minimum_cells(self):
        from python.inspect_architectural_parts import fixture
        roof=generate_roof(fixture('residential_multi_reflex')['footprint'])
        from roof_generator.core.cells import decompose
        self.assertGreater(len(decompose(roof.generation.footprint).cells),1)
        self.assertEqual(roof.generation.selected.architecture.footprint,roof.generation.footprint)
        self.assertEqual({f.cells for f in roof.mesh.graph.faces},{(0,)})

    def test_seed_and_rigid_input_changes_preserve_receiver_topology(self):
        import math
        records=json.loads((Path(__file__).parent/'fixtures/user_roof_images_v1.json').read_text())['inputs']
        raw=records[3]['footprint'];angle=.37;c,s=math.cos(angle),math.sin(angle)
        moved=[(c*x-s*y+13,s*x+c*y-17) for x,y in reversed(raw)]
        a=generate_roof(raw,GenerationSettings(seed=71))
        b=generate_roof(moved,GenerationSettings(seed=71,reference_direction=(c,s)))
        self.assertEqual(a.generation.selected.id,b.generation.selected.id)

    def test_receiver_still_runs_when_minimum_has_no_finished_candidate(self):
        from dataclasses import replace
        from roof_generator.core.partition_candidates import candidates
        from roof_generator.core.architecture_selection import recommend
        from roof_generator.core.roof_candidates import roof_candidates
        from python.inspect_architectural_parts import fixture
        fp=analyze(fixture('cross')['footprint'])
        search=replace(candidates(fp,max_work=1),candidates=())
        interpretation=recommend(search,defer_ranking=True)
        self.assertFalse(interpretation.search.complete)
        self.assertFalse(interpretation.search.candidates)
        pool=roof_candidates(fp,interpretation,GenerationSettings())
        self.assertTrue(pool.regions.valid)
        self.assertFalse(pool.complete)
        self.assertEqual(pool.inspect_ranking()['selectable_candidate_ids'],[])
        with self.assertRaises(UnsupportedRoofError):pool.select(0)

    def test_sources_from_another_footprint_are_rejected(self):
        from roof_generator.core.partition_candidates import candidates
        from roof_generator.core.architecture_selection import recommend
        from roof_generator.core.roof_candidates import roof_candidates
        fp=analyze(((0,0),(12,0),(12,6),(0,6)))
        other=analyze(((0,0),(9,0),(9,7),(0,7)))
        with self.assertRaisesRegex(UnsupportedRoofError,'different footprints'):
            roof_candidates(fp,recommend(candidates(other),defer_ranking=True),GenerationSettings())

    def test_failed_embedding_retains_constructibility_evidence(self):
        from roof_generator.core.partition_candidates import candidates
        from roof_generator.core.architecture_selection import recommend
        from roof_generator.core.roof_candidates import roof_candidates
        from roof_generator.core.receiver_regions import ReceiverRegions
        fp=analyze(((0,0),(12,0),(12,6),(0,6)))
        with patch('roof_generator.core.roof_candidates.receiver_regions',return_value=ReceiverRegions((),True,0)), \
             patch('roof_generator.core.roof_candidates.solve',side_effect=UnsupportedRoofError('embedding witness')):
            pool=roof_candidates(fp,recommend(candidates(fp),defer_ranking=True),GenerationSettings())
        self.assertTrue(pool.constructible)
        self.assertFalse(pool.valid)
        self.assertFalse(pool.meshes)
        self.assertTrue(pool.inspect_ranking()['constructible_candidate_ids'])
        self.assertEqual(pool.inspect_ranking()['available_embedded_candidate_ids'],[])


if __name__=='__main__':unittest.main()
