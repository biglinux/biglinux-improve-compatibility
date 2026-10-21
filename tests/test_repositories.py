"""pacman.conf on the BigLinux repositories, as $repo/$arch lines."""

from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "biglinux-improve-compatibility/usr/share/libalpm/scripts"
    / "biglinux-improve-compatibility-repositories"
)
BIG = "https://packages.biglinux.com.br"
COMMUNITY = "https://repo.communitybig.org"
OLD = "https://repo.biglinux.com.br"
REPO_LINE = {"biglinux": f"Server = {BIG}/$repo/$arch", "community": f"Server = {COMMUNITY}/$repo/$arch"}

OPTIONS = """[options]
Architecture = auto
SigLevel = Required DatabaseNever
"""
MANJARO = """[core]
SigLevel = PackageRequired
Include = /etc/pacman.d/mirrorlist

[extra]
SigLevel = PackageRequired
Include = /etc/pacman.d/mirrorlist

[multilib]
SigLevel = PackageRequired
Include = /etc/pacman.d/mirrorlist
"""
EXAMPLE = """# An example of a custom package repository.
#[custom]
#Server = file:///home/custompkgs
"""


def section(name, line):
    return f"[{name}]\nSigLevel = PackageRequired\n{line}\n"


def old(repo):
    return section(f"biglinux-{repo}", f"Server = {OLD}/{repo}/$arch")


def per_folder(name):
    family, folder = name.split("-", 1)
    return section(name, f"Server = {BIG if family == 'biglinux' else COMMUNITY}/{folder}/$arch")


def with_repo(name):
    return section(name, REPO_LINE[name.split("-", 1)[0]])


def conf(*parts):
    return "\n".join(parts)


COMMUNITY_OLD = conf(per_folder("community-testing"), per_folder("community-stable"),
                     per_folder("community-extra"))
# pacman.conf of a BigLinux installed from the ISOs before the move.
OLD_ISO = conf(OPTIONS, old("update-stable"), MANJARO, old("stable"), EXAMPLE)
ALL = ("biglinux-priority", "biglinux-stable", "biglinux-extra")


class RepositoriesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="biglinux-repositories-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.conf = self.root / "pacman.conf"
        self.mirrorlists = self.root / "pacman.d"
        self.mirrorlists.mkdir()
        (self.root / "root").mkdir()
        # A third-party repository whose file opens its own section.
        self.third = self.root / "openai-chatgpt.conf"
        self.third.write_text("[openai-chatgpt]\nServer = https://example.org/$arch\n")

    def mirrorlist_include(self, folder):
        """What the retired biglinux-mirrorlist package had systems write."""
        path = self.mirrorlists / f"biglinux-{folder}-mirrorlist"
        path.write_text(f"Server = {BIG}/{folder}/$arch\n")
        return f"Include = {path}"

    def run_script(self):
        env = {**os.environ, "PACMAN_CONF": str(self.conf), "MIRRORLIST_DIR": str(self.mirrorlists),
               "ROOT_DIR": str(self.root / "root"), "SKIP_OWNER_CHECK": "1", "SKIP_KEY": "1"}
        subprocess.run(["bash", str(SCRIPT)], env=env, check=True, capture_output=True, text=True)
        return self.conf.read_text()

    def migrate(self, text):
        """Write text, run as on an upgrade, and check that a second run changes nothing."""
        self.conf.write_text(text)
        first = self.run_script()
        self.assertEqual(self.run_script(), first, "a second run changed the file")
        self.assertEqual(list(self.root.glob("pacman.conf.biglinux-*")), [], "temporary file left")
        return first

    def servers(self, text):
        """{section: [Server/Include lines]} as pacman reads them (Include that opens a section ends one)."""
        result, current = {}, None
        for raw in text.splitlines():
            line = raw.strip()
            header = re.fullmatch(r"\[([^]]+)\]", line)
            if header:
                current = header.group(1)
                result.setdefault(current, [])
            elif line == f"Include = {self.third}":
                current = "openai-chatgpt"
                result.setdefault(current, [])
            elif current and re.match(r"(Server|Include)\s*=", line):
                result[current].append(re.sub(r"\s*=\s*", " = ", line, count=1))
        return result

    def assert_repo_lines(self, text, names):
        found = self.servers(text)
        for name in names:
            self.assertEqual(found.get(name), [REPO_LINE[name.split("-", 1)[0]]], name)
        sections = re.findall(r"^\[([^]]+)\]", text, re.M)
        self.assertEqual(len(sections), len(set(sections)), "duplicated section")
        self.assertEqual(sections[sections.index("core") - 1], "biglinux-priority")
        ours = [n for n in sections if n.startswith(("biglinux-", "community-")) and n != "biglinux-priority"]
        expected = [n for n in ("community-testing", "community-stable", "community-extra",
                                "biglinux-testing", "biglinux-stable", "biglinux-extra") if n in names]
        self.assertEqual(ours, expected, "section order")
        live = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
        self.assertNotIn(OLD, live)
        self.assertNotIn("mirrorlist", "\n".join(l for l in live.splitlines() if "biglinux-" in l))

    def test_old_iso_moves_everything_to_repo_lines(self):
        text = self.migrate(OLD_ISO)
        self.assert_repo_lines(text, ALL)
        self.assertIn(EXAMPLE, text, "comments after a dropped section are kept")

    def test_old_iso_with_testing_keeps_testing(self):
        text = self.migrate(conf(OPTIONS, old("update-stable"), MANJARO,
                                 old("testing"), old("stable")))
        self.assert_repo_lines(text, ALL + ("biglinux-testing",))

    def test_commented_testing_is_not_enabled(self):
        text = self.migrate(conf(OPTIONS, old("update-stable"), MANJARO,
                                 f"#[biglinux-testing]\n#Server = {OLD}/testing/$arch\n", old("stable")))
        self.assert_repo_lines(text, ALL)
        self.assertIn("#[biglinux-testing]", text)

    def test_system_without_biglinux_stable_gets_it(self):
        text = self.migrate(conf(OPTIONS, old("update-stable"), MANJARO))
        self.assert_repo_lines(text, ALL)

    def test_server_per_folder_moves_to_repo_lines(self):
        text = self.migrate(conf(OPTIONS, per_folder("biglinux-priority"), MANJARO,
                                 per_folder("biglinux-testing"), per_folder("biglinux-stable"),
                                 per_folder("biglinux-extra")))
        self.assert_repo_lines(text, ALL + ("biglinux-testing",))

    def test_mirrorlist_include_moves_to_repo_lines(self):
        """Systems moved by the earlier version of this hook (the Include of biglinux-mirrorlist)."""
        parts = [section(f"biglinux-{f}", self.mirrorlist_include(f)) for f in ("testing", "stable", "extra")]
        text = self.migrate(conf(OPTIONS, section("biglinux-priority", self.mirrorlist_include("priority")),
                                 MANJARO, *parts, f"Include = {self.third}\n"))
        self.assert_repo_lines(text, ALL + ("biglinux-testing",))
        self.assertEqual(self.servers(text)["openai-chatgpt"], [])
        self.assertIn(f"Include = {self.third}", text)

    def test_already_on_repo_lines_is_left_as_is(self):
        original = conf(OPTIONS, with_repo("biglinux-priority"), MANJARO,
                        *(with_repo(n) for n in ALL[1:]))
        self.assertEqual(self.migrate(original), original)

    def test_third_party_include_after_the_old_stable_is_kept(self):
        text = self.migrate(OLD_ISO.replace(f"Server = {OLD}/stable/$arch\n",
                                            f"Server = {OLD}/stable/$arch\n\nInclude = {self.third}\n"))
        self.assert_repo_lines(text, ALL)
        self.assertIn(f"Include = {self.third}", text)

    def test_carriage_returns_are_whitespace(self):
        text = self.migrate(OLD_ISO.replace("\n", "\r\n"))
        self.assert_repo_lines(text, ALL)

    def test_bigcommunity_sections_follow_the_same_rules(self):
        """BigCommunity installs this package next to comm-improve-compatibility."""
        text = self.migrate(conf(OPTIONS, old("update-stable"), MANJARO, COMMUNITY_OLD, old("stable")))
        self.assert_repo_lines(text, ALL + ("community-testing", "community-stable", "community-extra"))

    def test_own_mirrors_are_left_alone(self):
        mine = "Server = https://mirror.example.org/biglinux/stable/$arch"
        two = f"Server = {COMMUNITY}/extra/$arch\nServer = https://mirror.example.org/community/extra/$arch"
        text = self.migrate(conf(OPTIONS, old("update-stable"), MANJARO, per_folder("community-stable"),
                                 section("community-extra", two), section("biglinux-stable", mine)))
        found = self.servers(text)
        self.assertEqual(found["biglinux-stable"], [mine])
        self.assertEqual(found["community-extra"], two.splitlines())
        self.assertEqual(found["community-stable"], [REPO_LINE["community"]])
        self.assertEqual(found["biglinux-extra"], [REPO_LINE["biglinux"]])

    def test_rustdesk_copies_are_removed_and_nothing_else(self):
        root = self.root / "root"
        (root / "usr/share/rustdesk/files").mkdir(parents=True)
        (root / "usr/share/applications").mkdir(parents=True)
        for name in ("rustdesk.desktop", "rustdesk-link.desktop"):
            (root / "usr/share/rustdesk/files" / name).write_text("[Desktop Entry]\n")
            (root / "usr/share/applications" / name).write_text("[Desktop Entry]\nName[pt_BR]=RustDesk\n")
        (root / "usr/share/applications/other.desktop").write_text("[Desktop Entry]\n")
        self.migrate(OLD_ISO)
        self.assertEqual(sorted(p.name for p in (root / "usr/share/applications").iterdir()), ["other.desktop"])


if __name__ == "__main__":
    unittest.main()
