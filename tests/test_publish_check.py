#!/usr/bin/env python3
"""Game-free checks of the publication guard using synthetic file names only."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

CHECK = Path(__file__).resolve().parents[1] / 'publish-check.sh'
ROOT = CHECK.parent


class PublishCheckTests(unittest.TestCase):
    def check(self, filename):
        with tempfile.TemporaryDirectory(prefix='publish-check-test-') as temporary:
            root = Path(temporary)
            shutil.copy2(CHECK, root / 'publish-check.sh')
            shutil.copy2(ROOT / 'name_policy.py', root / 'name_policy.py')
            (root / 'docs').mkdir()
            shutil.copy2(ROOT / 'docs/names-kept.md', root / 'docs/names-kept.md')
            (root / filename).write_text('synthetic fixture\n')
            return subprocess.run(['bash', str(root / 'publish-check.sh')], cwd=root,
                                  text=True, capture_output=True, check=False)

    def test_options_and_environment_files_of_both_names_are_refused(self):
        for project in ('hookshot', 'longshot'):
            for suffix in ('_options.ini', '_env.txt'):
                name = project + suffix
                with self.subTest(name=name):
                    result = self.check(name)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn(name, result.stdout)
                    self.assertTrue(result.stdout.rstrip().endswith('FAIL'))

    def test_plain_source_document_passes(self):
        result = self.check('README.md')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(result.stdout.rstrip().endswith('PASS'))

    def test_the_flag_maps_manifest_rows_are_not_read_as_facts_but_other_files_still_are(self):
        item = 'Item_' + 'Hook' + 'shot'   # (a name the naming policy counts, built here so that this file needs no exception)
        row = '["docs/oot/flags/a.md", "%s", 1, "a flag name of the flag map"]'
        with tempfile.TemporaryDirectory(prefix='publish-check-test-') as temporary:
            root = Path(temporary)
            shutil.copy2(CHECK, root / 'publish-check.sh')
            shutil.copy2(ROOT / 'name_policy.py', root / 'name_policy.py')
            (root / 'docs/oot/flags').mkdir(parents=True)
            manifest = (ROOT / 'docs/names-kept.md').read_text().replace('<!-- kept-literals:end -->', '')
            manifest = manifest.rstrip('`\n') + '\n' + row % item + '\n```\n<!-- kept-literals:end -->\n'
            (root / 'docs/names-kept.md').write_text(manifest)
            (root / 'docs/oot/flags/a.md').write_text('| `%s` |\n' % item)
            result = subprocess.run(['bash', str(root / 'publish-check.sh')], cwd=root, text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('OK    nothing that smells like facts', result.stdout)
            (root / 'notes.md').write_text('Ite' + 'm_Plain_Name_Here\n')   # (outside docs/oot/: still read; built here so that this file is not read itself)
            result = subprocess.run(['bash', str(root / 'publish-check.sh')], cwd=root, text=True, capture_output=True, check=False)
            self.assertIn('READ', result.stdout)
            self.assertIn('notes.md:1', result.stdout)


if __name__ == '__main__':
    unittest.main()
