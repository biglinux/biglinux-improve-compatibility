"""Check the WirePlumber hook that keeps jamesdsp_sink from becoming the default."""

from pathlib import Path
import re
import shutil
import subprocess
import unittest


WIREPLUMBER = (
    Path(__file__).resolve().parents[1]
    / "biglinux-improve-compatibility/usr/share/wireplumber"
)
CONF = WIREPLUMBER / "wireplumber.conf.d/60-biglinux-jamesdsp-not-default.conf"
SCRIPT = WIREPLUMBER / "scripts/biglinux/jamesdsp-not-default.lua"

# Minimal stand-ins for the WirePlumber Lua API the script touches. The hook is
# captured on register() and run against a fake select-default-node event.
HARNESS = r"""
local captured
Log = { open_topic = function () return { debug = function () end } end }
Constraint = function (t) return t end
EventInterest = function (t) return t end
SimpleEventHook = function (spec)
  return { register = function () captured = spec end }
end
local function wrap (value)
  return { parse = function () return value end }
end
Json = {
  Object = function (t) return t end,
  Array = function (t) return wrap (t) end,
}

dofile (arg [1])

local names = {}
for name in string.gmatch (arg [2], "[^,]+") do
  table.insert (names, { ["node.name"] = name, ["media.class"] = "Audio/Sink" })
end

local data = { ["available-nodes"] = wrap (names) }
local replaced = false
local event = {
  get_data = function (_, key) return data [key] end,
  set_data = function (_, key, value) data [key] = value; replaced = true end,
  get_properties = function () return { ["default-node.type"] = "audio.sink" } end,
}

captured.execute (event)

local out = {}
for _, props in ipairs (data ["available-nodes"]:parse ()) do
  table.insert (out, props ["node.name"])
end
print (table.concat (out, ","))
print (tostring (replaced))
print (table.concat (captured.before, ","))
"""


class ConfTests(unittest.TestCase):
    def setUp(self):
        self.conf = CONF.read_text()

    def test_script_is_only_wanted(self):
        # The profile must require the virtual component, never the script:
        # required would take WirePlumber down on a load failure, optional
        # would not load it at all.
        self.assertRegex(self.conf, r"biglinux\.jamesdsp-not-default\s*=\s*required")
        self.assertNotRegex(self.conf, r"hooks\.biglinux\.jamesdsp-not-default\s*=")
        self.assertRegex(
            self.conf,
            r"type\s*=\s*virtual,\s*provides\s*=\s*biglinux\.jamesdsp-not-default\s*"
            r"wants\s*=\s*\[\s*hooks\.biglinux\.jamesdsp-not-default\s*\]",
        )

    def test_component_points_at_shipped_script(self):
        name = re.search(r"name\s*=\s*(\S+\.lua)", self.conf).group(1)
        self.assertEqual(WIREPLUMBER / "scripts" / name, SCRIPT)
        self.assertTrue(SCRIPT.is_file())


@unittest.skipUnless(shutil.which("lua") and shutil.which("luac"), "lua not installed")
class HookTests(unittest.TestCase):
    def run_hook(self, *names):
        result = subprocess.run(
            ["lua", "-", str(SCRIPT), ",".join(names)],
            input=HARNESS, capture_output=True, text=True, check=True,
        )
        kept, replaced, before = result.stdout.splitlines()
        return kept.split(",") if kept else [], replaced == "true", before.split(",")

    def test_compiles(self):
        subprocess.run(["luac", "-p", str(SCRIPT)], check=True)

    def test_drops_jamesdsp_sink(self):
        kept, replaced, _ = self.run_hook("alsa_speaker", "jamesdsp_sink", "bluez_headset")
        self.assertEqual(kept, ["alsa_speaker", "bluez_headset"])
        self.assertTrue(replaced)

    def test_leaves_candidates_alone_without_jamesdsp(self):
        kept, replaced, _ = self.run_hook("alsa_speaker", "bluez_headset")
        self.assertEqual(kept, ["alsa_speaker", "bluez_headset"])
        self.assertFalse(replaced)

    def test_runs_before_stock_selection(self):
        _, _, before = self.run_hook("alsa_speaker")
        self.assertEqual(
            sorted(before),
            sorted([
                "default-nodes/find-selected-default-node",
                "default-nodes/find-stored-default-node",
                "default-nodes/find-best-default-node",
                "default-nodes/apply-default-node",
            ]),
        )


if __name__ == "__main__":
    unittest.main()
