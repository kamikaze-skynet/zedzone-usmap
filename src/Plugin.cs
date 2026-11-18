using BepInEx;
using BepInEx.Configuration;
using BepInEx.Unity.IL2CPP;
using HarmonyLib;

namespace USMap
{
    [BepInPlugin(Guid, "US Map", Version)]
    public class Plugin : BasePlugin
    {
        public const string Guid = "girthy_mods.zedzone.usmap";
        public const string Version = "0.1.0";

        internal static ConfigEntry<bool> Enabled;
        internal static ConfigEntry<string> NameTrigger;
        internal static ConfigEntry<float> HeightLow;
        internal static ConfigEntry<float> HeightHigh;
        internal static ConfigEntry<float> NoiseBlend;
        internal static ConfigEntry<bool> InterstateRoads;
        internal static ConfigEntry<bool> VerboseLog;

        public override void Load()
        {
            Enabled = Config.Bind("General", "Enabled", true, "Turn the whole mod on or off.");
            NameTrigger = Config.Bind("General", "MapNameContains", "USA",
                "A new sandbox map whose name contains this text (any case) is built as the United States. Existing US maps are remembered in BepInEx\\config\\USMap.maps.txt.");
            InterstateRoads = Config.Bind("World", "InterstateRoads", true, "Lay highways along the real interstates.");
            HeightLow = Config.Bind("Terrain", "HeightLow", 0.35f,
                "Where sea level sits in the game's own terrain height range (0 = lowest, 1 = highest). Raise it if low land turns into marsh.");
            HeightHigh = Config.Bind("Terrain", "HeightHigh", 1.0f, "Where the highest mountains sit in the game's terrain height range.");
            NoiseBlend = Config.Bind("Terrain", "NoiseBlend", 0.3f,
                "How much of the game's own random terrain noise is mixed into the real elevation (0 = only real elevation, 1 = only noise). A little noise keeps flat land from looking bare.");
            VerboseLog = Config.Bind("Debug", "VerboseLog", false, "Extra detail in BepInEx\\USMap.log.");

            BLog.Verbose = VerboseLog.Value;
            BLog.Open(Log, Version);
            if (!Enabled.Value) { BLog.Info("Disabled in config."); return; }
            if (!UsData.Load()) { BLog.Error("usmap.bin missing or unreadable; the mod does nothing."); return; }
            Patches.Apply(new Harmony(Guid));
            BLog.Info($"US Map {Version} loaded. Name a new map with \"{NameTrigger.Value}\" in it to play on the United States.");
        }
    }
}
