# SPDX-License-Identifier: GPL-3.0-or-later
"""Authority witnesses independent of the composer's member-port recognition."""

import unittest
from unittest.mock import patch
import python
from roof_generator.core.generation import prepare_generation
from roof_generator.core import topology_candidates


class ArchitectureAuthorityProof(unittest.TestCase):
    def test_composer_receives_architecture_not_a_decomposition(self):
        received = []
        original = topology_candidates.compose

        def observe(authority, *args, **kwargs):
            received.append(authority)
            return original(authority, *args, **kwargs)

        with patch.object(topology_candidates, "compose", observe):
            prepare_generation(((0, 0), (12, 0), (12, 4), (4, 4), (4, 10), (0, 10)))
        self.assertTrue(received)
        for authority in received:
            self.assertTrue(hasattr(authority, "architecture"))
            self.assertTrue(hasattr(authority, "relations"))
            self.assertTrue(hasattr(authority, "axes"))


if __name__ == "__main__":
    unittest.main()
