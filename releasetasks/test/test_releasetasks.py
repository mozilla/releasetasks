# -*- coding: utf-8 -*-
import unittest

from releasetasks import make_task_graph as make_task_graph_orig


def get_task_by_name(graph, name):
    for t in graph["tasks"]:
        if t["task"]["extra"]["task_name"] == name:
            return t
    return None


def get_task_by_slugid(graph, slugid):
    for t in graph["tasks"]:
        if t["taskId"] == slugid:
            return t
    return None


def make_task_graph(*args, **kwargs):
    return make_task_graph_orig(*args, running_tests=True, **kwargs)


class TestMakeTaskGraph(unittest.TestCase):
    """Because of huge the graph gets, verifying every character of it is
    impossible to maintain. Instead, we verify aspects of it. Eg, making sure
    the correct number of funsize partials are happening, rather than verifying
    the entire funsize tasks."""
    maxDiff = 30000

    def _do_common_assertions(self, graph):
        if graph["tasks"]:
            for t in graph["tasks"]:
                task = t["task"]
                self.assertEqual(task["priority"], "high")
                self.assertIn("task_name", task["extra"])

    def test_source_task_definition(self):
        graph = make_task_graph(
            source_enabled=True,
            l10n_platforms=[],
            repo_path="releases/foo",
            revision="fedcba654321",
            branch="foo",
            updates_enabled=False,
        )

        self._do_common_assertions(graph)

        task = get_task_by_name(graph, "foo_source")["task"]
        payload = task["payload"]
        self.assertEqual(task["provisionerId"], "aws-provisioner-v1")
        self.assertEqual(task["workerType"], "opt-linux64")
        self.assertTrue(payload["image"].startswith("taskcluster/desktop-build:"))
        self.assertTrue("cache" in payload)
        self.assertTrue("artifacts" in payload)
        self.assertTrue("env" in payload)
        self.assertTrue("command" in payload)

        expected_graph_scopes = set([
            "docker-worker:cache:tc-vcs",
            "docker-worker:image:taskcluster/builder:*",
            "queue:define-task:aws-provisioner-v1/opt-linux64",
            "queue:create-task:aws-provisioner-v1/opt-linux64",
            "queue:define-task:aws-provisioner-v1/build-c4-2xlarge",
            "queue:create-task:aws-provisioner-v1/build-c4-2xlarge",
            "docker-worker:cache:build-linux64-workspace",
            "docker-worker:cache:tooltool-cache"
        ])
        self.assertTrue(expected_graph_scopes.issubset(graph["scopes"]))
        expected_task_scopes = set([
            "docker-worker:cache:tc-vcs",
            "docker-worker:image:taskcluster/builder:0.5.7",
            "queue:define-task:aws-provisioner-v1/opt-linux64",
            "queue:create-task:aws-provisioner-v1/opt-linux64",
            "queue:define-task:aws-provisioner-v1/build-c4-2xlarge",
            "queue:create-task:aws-provisioner-v1/build-c4-2xlarge",
            "docker-worker:cache:build-linux64-workspace",
            "docker-worker:cache:tooltool-cache"
        ])
        self.assertTrue(expected_task_scopes.issubset(task["scopes"]))

    def test_required_graph_scopes(self):
        graph = make_task_graph(
            updates_enabled=False,
            source_enabled=False,
            l10n_platforms=[],
        )

        self._do_common_assertions(graph)
        self.assertEqual(graph["tasks"], None)

        expected_scopes = set([
            "signing:format:gpg",
            "queue:define-task:buildbot-bridge/buildbot-bridge",
            "queue:create-task:buildbot-bridge/buildbot-bridge",
            "queue:task-priority:high",
        ])
        self.assertTrue(expected_scopes.issubset(graph["scopes"]))

    def test_funsize_en_US_deps(self):
        graph = make_task_graph(
            source_enabled=False,
            updates_enabled=True,
            l10n_platforms=[],
            enUS_platforms=["win32", "macosx64"],
            partial_updates={
                "38.0": {
                    "buildNumber": 1,
                },
                "37.0": {
                    "buildNumber": 2,
                },
            },
            branch="mozilla-beta",
            repo_path="releases/mozilla-beta",
            product="firefox",
            revision="abcdef123456",
            balrog_api_root="https://fake.balrog/api",
            signing_class="release-signing",
        )

        self._do_common_assertions(graph)

        for p in ("win32", "macosx64"):
            for v in ("38.0build1", "37.0build2"):
                generator = get_task_by_name(graph, "{}_en-US_{}_funsize_update_generator".format(p, v))
                signing = get_task_by_name(graph, "{}_en-US_{}_funsize_signing_task".format(p, v))
                balrog = get_task_by_name(graph, "{}_en-US_{}_funsize_balrog_task".format(p, v))

                self.assertIsNone(generator.get("requires"))
                self.assertEqual(signing.get("requires"), [generator["taskId"]])
                self.assertEqual(balrog.get("requires"), [signing["taskId"]])

    def test_funsize_en_US_scopes(self):
        graph = make_task_graph(
            source_enabled=False,
            updates_enabled=True,
            l10n_platforms=[],
            enUS_platforms=["win32", "macosx64"],
            partial_updates={
                "38.0": {
                    "buildNumber": 1,
                },
                "37.0": {
                    "buildNumber": 2,
                },
            },
            branch="mozilla-beta",
            product="firefox",
            revision="abcdef123456",
            balrog_api_root="https://fake.balrog/api",
            signing_class="release-signing",
        )

        self._do_common_assertions(graph)
        expected_scopes = set([
            "queue:*", "docker-worker:*", "scheduler:*",
            "signing:format:gpg", "signing:format:mar",
            "signing:cert:release-signing",
            "docker-worker:feature:balrogVPNProxy"
        ])
        self.assertTrue(expected_scopes.issubset(graph["scopes"]))

        for p in ("win32", "macosx64"):
            for v in ("38.0build1", "37.0build2"):
                generator = get_task_by_name(graph, "{}_en-US_{}_funsize_update_generator".format(p, v))
                signing = get_task_by_name(graph, "{}_en-US_{}_funsize_signing_task".format(p, v))
                balrog = get_task_by_name(graph, "{}_en-US_{}_funsize_balrog_task".format(p, v))

                self.assertIsNone(generator["task"].get("scopes"))
                self.assertItemsEqual(signing["task"]["scopes"], ["signing:cert:release-signing", "signing:format:mar", "signing:format:gpg"])
                self.assertItemsEqual(balrog["task"]["scopes"], ["docker-worker:feature:balrogVPNProxy"])

    def test_funsize_en_US_scopes_dep_signing(self):
        graph = make_task_graph(
            source_enabled=False,
            updates_enabled=True,
            l10n_platforms=[],
            enUS_platforms=["win32", "macosx64"],
            partial_updates={
                "38.0": {
                    "buildNumber": 1,
                },
                "37.0": {
                    "buildNumber": 2,
                },
            },
            branch="mozilla-beta",
            product="firefox",
            revision="abcdef123456",
            balrog_api_root="https://fake.balrog/api",
            signing_class="dep-signing",
        )

        self._do_common_assertions(graph)
        expected_scopes = set([
            "queue:*", "docker-worker:*", "scheduler:*",
            "signing:format:gpg", "signing:format:mar",
            "signing:cert:dep-signing",
        ])
        self.assertTrue(expected_scopes.issubset(graph["scopes"]))
        self.assertNotIn("docker-worker:feature:balrogVPNProxy", graph["scopes"])

        for p in ("win32", "macosx64"):
            for v in ("38.0build1", "37.0build2"):
                generator = get_task_by_name(graph, "{}_en-US_{}_funsize_update_generator".format(p, v))
                signing = get_task_by_name(graph, "{}_en-US_{}_funsize_signing_task".format(p, v))
                balrog = get_task_by_name(graph, "{}_en-US_{}_funsize_balrog_task".format(p, v))

                self.assertIsNone(generator["task"].get("scopes"))
                self.assertItemsEqual(signing["task"]["scopes"], ["signing:cert:dep-signing", "signing:format:mar", "signing:format:gpg"])
                self.assertIsNone(balrog["task"].get("scopes"))

    def test_l10n_one_chunk(self):
        graph = make_task_graph(
            source_enabled=False,
            updates_enabled=False,
            l10n_platforms=["win32"],
            enUS_platforms=["win32"],
            branch="mozilla-beta",
            product="firefox",
            repo_path="releases/mozilla-beta",
            revision="abcdef123456",
            l10n_changesets={
                "de": "default",
                "en-GB": "default",
                "zh-TW": "default",
            },
            l10n_chunks=1,
        )

        self._do_common_assertions(graph)

        task = get_task_by_name(graph, "mozilla-beta_firefox_win32_l10n_repack_1")

        payload = task["task"]["payload"]
        properties = payload["properties"]

        self.assertEqual(task["task"]["provisionerId"], "buildbot-bridge")
        self.assertEqual(task["task"]["workerType"], "buildbot-bridge")
        self.assertEqual(payload["buildername"], "mozilla-beta_firefox_win32_l10n_repack")
        self.assertEqual(properties["locales"], "de:default en-GB:default zh-TW:default")

        # Make sure only one chunk was generated
        self.assertIsNone(get_task_by_name(graph, "mozilla-beta_firefox_win32_l10n_repack_0"))
        self.assertIsNone(get_task_by_name(graph, "mozilla-beta_firefox_win32_l10n_repack_2"))

    def test_l10n_multiple_chunks(self):
        graph = make_task_graph(
            source_enabled=False,
            updates_enabled=False,
            l10n_platforms=["win32"],
            enUS_platforms=["win32"],
            branch="mozilla-beta",
            product="firefox",
            repo_path="releases/mozilla-beta",
            revision="abcdef123456",
            l10n_changesets={
                "de": "default",
                "en-GB": "default",
                "ru": "default",
                "uk": "default",
                "zh-TW": "default",
            },
            l10n_chunks=2,
        )

        self._do_common_assertions(graph)

        chunk1 = get_task_by_name(graph, "mozilla-beta_firefox_win32_l10n_repack_1")
        chunk2 = get_task_by_name(graph, "mozilla-beta_firefox_win32_l10n_repack_2")

        chunk1_locales = chunk1["task"]["payload"]["properties"]["locales"]
        chunk2_locales = chunk2["task"]["payload"]["properties"]["locales"]

        self.assertEqual(chunk1["task"]["payload"]["buildername"], "mozilla-beta_firefox_win32_l10n_repack")
        self.assertEqual(chunk1_locales, "de:default en-GB:default ru:default")
        self.assertEqual(chunk2["task"]["payload"]["buildername"], "mozilla-beta_firefox_win32_l10n_repack")
        self.assertEqual(chunk2_locales, "uk:default zh-TW:default")

        self.assertEqual(get_task_by_name(graph, "mozilla-beta_firefox_win32_l10n_repack_3"), None)
