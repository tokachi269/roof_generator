# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "addon"))
from roof_generator.dependencies import find_host_python


class HostPythonTests(unittest.TestCase):
    @patch("roof_generator.dependencies.subprocess.run")
    @patch("roof_generator.dependencies.shutil.which")
    def test_windows_alias_does_not_block_working_python(self, which, run):
        which.side_effect = ["python3.exe", "python.exe", "py.exe"]
        run.side_effect = [
            subprocess.CompletedProcess([], 9009, "", "Python "),
            subprocess.CompletedProcess([], 0, "pip 25.1 from site-packages", ""),
        ]
        self.assertEqual(find_host_python(), "python.exe")
        self.assertEqual(
            run.call_args_list[0].args[0], ["python3.exe", "-m", "pip", "--version"]
        )
        self.assertEqual(
            run.call_args_list[1].args[0], ["python.exe", "-m", "pip", "--version"]
        )

    @patch("roof_generator.dependencies.subprocess.run")
    @patch("roof_generator.dependencies.shutil.which")
    def test_explicit_selection_is_validated_without_switching(self, which, run):
        run.return_value = subprocess.CompletedProcess(
            [], 1, "", "No module named pip"
        )
        with self.assertRaisesRegex(RuntimeError, "chosen.exe: No module named pip"):
            find_host_python("chosen.exe")
        which.assert_not_called()

    @patch("roof_generator.dependencies.subprocess.run")
    @patch("roof_generator.dependencies.shutil.which")
    def test_unlaunchable_candidate_does_not_block_launcher(self, which, run):
        which.side_effect = ["missing.exe", None, "py.exe"]
        run.side_effect = [
            OSError("cannot launch"),
            subprocess.CompletedProcess([], 0, "pip 25", ""),
        ]
        self.assertEqual(find_host_python(), "py.exe")

    @patch("roof_generator.dependencies.subprocess.run")
    def test_blender_is_not_invoked_as_python(self, run):
        with self.assertRaisesRegex(RuntimeError, "Blender is not a host Python"):
            find_host_python("blender.exe", blender_binary="blender.exe")
        run.assert_not_called()

    @patch("roof_generator.dependencies.shutil.which", return_value=None)
    def test_missing_host_reports_required_action(self, which):
        with self.assertRaisesRegex(
            RuntimeError, "addon preferences.*no Python executable"
        ):
            find_host_python()
