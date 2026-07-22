import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPLOY_PATH = ROOT / "scripts" / "deploy.py"
DEPLOY_SPEC = importlib.util.spec_from_file_location("capability_library_deploy", DEPLOY_PATH)
deploy_module = importlib.util.module_from_spec(DEPLOY_SPEC)
DEPLOY_SPEC.loader.exec_module(deploy_module)
sys.path.insert(0, str(ROOT / "scripts"))
import package_release


MANAGED_TARGETS = {target for _source, target in deploy_module.MANAGED_FILES}


class DeployTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.target = self.root / "user-library"

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write(self, relative_path, content):
        path = self.target / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    @staticmethod
    def _hash(content):
        return hashlib.sha256(content).hexdigest()

    def test_update_preserves_all_user_owned_and_unknown_files(self):
        protected = {
            "CAPABILITY.md": b"custom capability\n",
            "capability-entry/SKILL.md": b"custom entry\n",
            "capability-entry/references/private.md": b"private reference\n",
            "skills/custom/SKILL.md": b"custom skill\n",
            "mcps/registry.json": b'[{"name":"private"}]\n',
            "tools/mcp/custom_server.py": b"custom server\n",
            "docs/user-note.md": b"custom note\n",
        }
        for relative_path, content in protected.items():
            self._write(relative_path, content)
        self._write("README.md", b"old readme\n")
        self._write("tools/mcp/echo_mcp.py", b"old managed echo\n")

        result = deploy_module.deploy(self.target)

        for relative_path, content in protected.items():
            self.assertEqual((self.target / relative_path).read_bytes(), content)
        self.assertEqual(
            (self.target / "README.md").read_bytes(),
            (deploy_module.ROOT / "user-version/README.md").read_bytes(),
        )
        self.assertNotEqual(
            (self.target / "README.md").read_bytes(),
            (deploy_module.ROOT / "README.md").read_bytes(),
        )
        self.assertEqual(
            (self.target / "tools/mcp/echo_mcp.py").read_bytes(),
            (deploy_module.ROOT / "tools/mcp/echo_mcp.py").read_bytes(),
        )
        self.assertIn("README.md", result["updated"])
        self.assertIn("tools/mcp/echo_mcp.py", result["updated"])
        self.assertTrue((self.target / deploy_module.STATE_FILE).is_file())

    def test_seed_files_are_created_once_and_then_preserved(self):
        first = deploy_module.deploy(self.target)
        expected_targets = {target for _source, target in deploy_module.SEED_FILES}
        self.assertEqual(set(first["seeded"]), expected_targets)

        custom_entry = b"user edited entry\n"
        (self.target / "capability-entry/SKILL.md").write_bytes(custom_entry)
        second = deploy_module.deploy(self.target)

        self.assertEqual(
            (self.target / "capability-entry/SKILL.md").read_bytes(), custom_entry
        )
        self.assertIn("capability-entry/SKILL.md", second["preserved"])
        self.assertEqual(second["seeded"], [])

    def test_entry_readme_marker_accepts_windows_path_separators(self):
        self._write(
            "capability-entry/SKILL.md",
            "使用前读取 D:\\library\\capability-library\\README.md\n".encode("utf-8"),
        )

        result = deploy_module.deploy(self.target, check=True)

        self.assertFalse(any("手动迁移" in item for item in result["warnings"]))

    def test_legacy_entry_gets_manual_readme_migration_warning(self):
        self._write(
            "capability-entry/SKILL.md",
            "使用前读取 ../docs/MCP使用指南.md\n".encode("utf-8"),
        )

        result = deploy_module.deploy(self.target, check=True)

        self.assertTrue(any("用户版 README" in item for item in result["warnings"]))

    def test_legacy_mcp_guide_is_not_created_for_new_users(self):
        fresh = deploy_module.deploy(self.target)
        self.assertFalse((self.target / "docs/MCP使用指南.md").exists())
        self.assertNotIn("docs/MCP使用指南.md", fresh["created"])

    def test_unchanged_managed_files_are_not_rewritten(self):
        deploy_module.deploy(self.target)
        readme = self.target / "README.md"
        state = self.target / deploy_module.STATE_FILE
        readme_mtime = readme.stat().st_mtime_ns
        state_mtime = state.stat().st_mtime_ns

        result = deploy_module.deploy(self.target)

        self.assertIn("README.md", result["unchanged"])
        self.assertEqual(readme.stat().st_mtime_ns, readme_mtime)
        self.assertEqual(state.stat().st_mtime_ns, state_mtime)

    def test_check_mode_reports_changes_without_writing(self):
        result = deploy_module.deploy(self.target, check=True)

        self.assertFalse(self.target.exists())
        self.assertEqual(set(result["created"]), MANAGED_TARGETS)
        self.assertEqual(
            set(result["seeded"]),
            {target for _source, target in deploy_module.SEED_FILES},
        )

    def test_removed_managed_file_is_deleted_only_when_unmodified(self):
        deploy_module.deploy(self.target)
        removable = self._write("tools/obsolete.py", b"old managed content\n")
        preserved = self._write("tools/modified.py", b"user changed content\n")
        state_path = self.target / deploy_module.STATE_FILE
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["managed_files"]["tools/obsolete.py"] = self._hash(removable.read_bytes())
        state["managed_files"]["tools/modified.py"] = self._hash(b"old shipped content\n")
        state_path.write_text(json.dumps(state), encoding="utf-8")

        result = deploy_module.deploy(self.target)

        self.assertFalse(removable.exists())
        self.assertTrue(preserved.exists())
        self.assertIn("tools/obsolete.py", result["removed"])
        self.assertIn("tools/modified.py", result["preserved"])
        self.assertTrue(any("modified.py" in item for item in result["warnings"]))

    def test_untrusted_state_cannot_escape_target(self):
        deploy_module.deploy(self.target)
        outside = self.root / "outside.txt"
        outside.write_bytes(b"must stay\n")
        state_path = self.target / deploy_module.STATE_FILE
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["managed_files"]["../outside.txt"] = self._hash(outside.read_bytes())
        state_path.write_text(json.dumps(state), encoding="utf-8")

        result = deploy_module.deploy(self.target)

        self.assertEqual(outside.read_bytes(), b"must stay\n")
        self.assertTrue(any("不安全路径" in item for item in result["warnings"]))

    def test_fresh_deploy_can_load_use_and_close_echo_mcp(self):
        deploy_module.deploy(self.target)
        load_script = self.target / "tools/mcp/load_mcp.py"
        use_script = self.target / "tools/mcp/use_tool.py"

        def run(*arguments):
            return subprocess.run(
                [sys.executable, *map(str, arguments)],
                cwd=self.target,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
                check=False,
            )

        one_shot = run(load_script, "--name", "本地回声 MCP")
        self.assertEqual(one_shot.returncode, 0, one_shot.stderr)
        self.assertTrue(json.loads(one_shot.stdout)["ok"])

        one_shot_use = run(
            use_script,
            "--mcp",
            "本地回声 MCP",
            "--tool",
            "echo",
            "--params-json",
            '{"text":"one-shot-ok"}',
        )
        self.assertEqual(one_shot_use.returncode, 0, one_shot_use.stderr)
        self.assertTrue(json.loads(one_shot_use.stdout)["ok"])

        keep_alive_started = False
        try:
            keep_alive = run(
                load_script,
                "--name",
                "本地回声 MCP",
                "--keep-alive",
                "--owner",
                "none",
                "--idle-timeout",
                "60",
            )
            self.assertEqual(keep_alive.returncode, 0, keep_alive.stderr)
            self.assertTrue(json.loads(keep_alive.stdout)["ok"])
            keep_alive_started = True

            keep_alive_use = run(
                use_script,
                "--mcp",
                "本地回声 MCP",
                "--tool",
                "echo",
                "--params-json",
                '{"text":"keep-alive-ok"}',
            )
            self.assertEqual(keep_alive_use.returncode, 0, keep_alive_use.stderr)
            self.assertTrue(json.loads(keep_alive_use.stdout)["ok"])
        finally:
            if keep_alive_started:
                closed = run(load_script, "--name", "本地回声 MCP", "--close")
                self.assertEqual(closed.returncode, 0, closed.stderr)
                self.assertTrue(json.loads(closed.stdout)["ok"])

    def test_user_release_contains_only_deployed_user_files(self):
        releases = self.root / "releases"
        zip_path = package_release.build_release("test-user", releases)

        with zipfile.ZipFile(zip_path) as archive:
            names = {
                name.removeprefix("test-user/")
                for name in archive.namelist()
                if not name.endswith("/")
            }

        expected = MANAGED_TARGETS | {
            target for _source, target in deploy_module.SEED_FILES
        } | {deploy_module.STATE_FILE}
        self.assertEqual(names, expected)
        self.assertNotIn("scripts/deploy.py", names)
        self.assertNotIn("AGENTS.md", names)
        self.assertNotIn("tests/test_deploy.py", names)

    def test_exported_docs_do_not_reference_local_deploy_script(self):
        deploy_module.deploy(self.target)
        markdown_files = list(self.target.rglob("*.md"))
        managed_markdown = [
            path
            for path in markdown_files
            if path.relative_to(self.target).as_posix() in MANAGED_TARGETS
        ]

        for path in managed_markdown:
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("python scripts/deploy.py", content)
            self.assertNotIn("templates/", content)
            self.assertNotIn("tests/", content)


if __name__ == "__main__":
    unittest.main()
