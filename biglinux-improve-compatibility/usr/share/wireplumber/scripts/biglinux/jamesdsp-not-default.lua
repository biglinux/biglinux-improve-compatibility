-- JamesDSP
--
-- Keep jamesdsp_sink out of the default node selection.
--
-- jamesdsp_sink is the virtual sink JamesDSP moves app streams into; its filter
-- then plays the processed audio on the real output. In automatic mode (the
-- default) JamesDSP picks that real output from default.audio.sink, and ignores
-- the key whenever it names jamesdsp_sink itself. So once jamesdsp_sink is the
-- default -- the user picked "JamesDSP Sink" in the desktop's output menu, for
-- instance -- JamesDSP never hears about output changes again: it stays bound
-- to whatever device it knew last, and playback goes silent as soon as that
-- device disappears (a Bluetooth headset disconnecting, or recreating its node
-- on a profile switch).
--
-- Instead of fighting over default.configured.audio.sink, drop jamesdsp_sink
-- from the candidate list before WirePlumber's own select-default-node hooks
-- run. The stock logic then works unchanged: a configured jamesdsp_sink is just
-- unavailable, so the stored history and the priorities pick the physical
-- output, exactly as if it had never been selected.

log = Log.open_topic ("s-biglinux-jamesdsp")

local JAMESDSP_SINK_NAME = "jamesdsp_sink"

SimpleEventHook {
  name = "biglinux/jamesdsp-not-default",
  before = { "default-nodes/find-selected-default-node",
             "default-nodes/find-stored-default-node",
             "default-nodes/find-best-default-node",
             "default-nodes/apply-default-node" },
  interests = {
    EventInterest {
      Constraint { "event.type", "=", "select-default-node" },
    },
  },
  execute = function (event)
    local available_nodes = event:get_data ("available-nodes")

    available_nodes = available_nodes and available_nodes:parse ()
    if not available_nodes then
      return
    end

    local kept = {}
    local dropped = false

    for _, node_props in ipairs (available_nodes) do
      if node_props ["node.name"] == JAMESDSP_SINK_NAME then
        dropped = true
      else
        table.insert (kept, Json.Object (node_props))
      end
    end

    if dropped then
      local props = event:get_properties ()
      log:debug ("not offering " .. JAMESDSP_SINK_NAME .. " as default " ..
          tostring (props ["default-node.type"]))
      event:set_data ("available-nodes", Json.Array (kept))
    end
  end
}:register ()
