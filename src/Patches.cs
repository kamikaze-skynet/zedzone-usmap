using System;
using System.Collections.Generic;
using System.IO;
using BepInEx;
using HarmonyLib;
using UnityEngine;

namespace USMap
{
    internal static class Patches
    {
        // true while the loaded / generating map is the United States
        internal static bool Active;
        static IntPtr _terrainGen;
        static float _hMin = -0.25f, _hMax = 0.55f;
        static int _savedSizeX, _savedSizeY;
        static bool _sizeChanged;
        static readonly HashSet<string> _usMapIds = new();
        static string ListPath => Path.Combine(Paths.ConfigPath, "USMap.maps.txt");

        internal static void Apply(Harmony h)
        {
            try { if (File.Exists(ListPath)) foreach (var l in File.ReadAllLines(ListPath)) if (l.Trim().Length > 0) _usMapIds.Add(l.Trim()); }
            catch (Exception e) { BLog.Warn("Couldn't read " + ListPath + ": " + e.Message); }
            h.PatchAll(typeof(Patches));
            BLog.Info($"Patched. Known US maps: {_usMapIds.Count}");
        }

        static MapConfigData CurrentConfig()
        {
            try { return GameController.instance?.gameData?.mapConfigData; } catch { return null; }
        }

        // Decides whether the map being loaded is a US map. New maps qualify by name.
        static bool DecideActive(MapController mc)
        {
            var cfg = CurrentConfig();
            string id = null, name = null;
            try { id = cfg?.mapId; name = cfg?.mapName; } catch { }
            bool known = id != null && _usMapIds.Contains(id);
            bool named = name != null && Plugin.NameTrigger.Value.Length > 0 &&
                         name.IndexOf(Plugin.NameTrigger.Value, StringComparison.OrdinalIgnoreCase) >= 0;
            bool fresh = false;
            try { fresh = mc != null && mc.mapData == null; } catch { }
            // an existing non-US map that happens to be renamed later keeps its own world
            bool on = known || (named && fresh);
            BLog.Info($"Map \"{name}\" ({id}): known US map={known}, name match={named}, new map={fresh} -> US map {(on ? "ON" : "off")}");
            return on;
        }

        static void Remember(string id)
        {
            if (string.IsNullOrEmpty(id) || !_usMapIds.Add(id)) return;
            try { File.AppendAllText(ListPath, id + Environment.NewLine); BLog.Info("Remembered US map " + id); }
            catch (Exception e) { BLog.Warn("Couldn't save " + ListPath + ": " + e.Message); }
        }

        static void SetSize(bool us)
        {
            if (us)
            {
                if (!_sizeChanged) { _savedSizeX = MapController.mapSizeX; _savedSizeY = MapController.mapSizeY; _sizeChanged = true; }
                MapController.mapSizeX = UsData.CW; MapController.mapSizeY = UsData.CH;
                BLog.Info($"Map size set to {UsData.CW}x{UsData.CH} chunks (was {_savedSizeX}x{_savedSizeY}).");
            }
            else if (_sizeChanged)
            {
                MapController.mapSizeX = _savedSizeX; MapController.mapSizeY = _savedSizeY; _sizeChanged = false;
                BLog.Info($"Map size restored to {_savedSizeX}x{_savedSizeY}.");
            }
        }

        // ---- loading a map: decide, set size, and cache what the per-tile hooks need
        [HarmonyPrefix, HarmonyPatch(typeof(MapController), nameof(MapController.LoadMapData))]
        static void LoadMapData_Pre(MapController __instance)
        {
            try { Active = DecideActive(__instance); SetSize(Active); _terrainGen = IntPtr.Zero; }
            catch (Exception e) { BLog.Error("LoadMapData prefix", e); Active = false; }
        }

        [HarmonyPostfix, HarmonyPatch(typeof(MapController), nameof(MapController.LoadMapData))]
        static void LoadMapData_Post(MapController __instance)
        {
            if (!Active) return;
            try
            {
                var md = __instance.mapData;
                if (md != null)
                {
                    _hMin = md.terrainHeightMin; _hMax = md.terrainHeightMax;
                    if (!(_hMax > _hMin)) { _hMin = -0.25f; _hMax = 0.55f; }
                    Remember(md.mapId);
                    int n = md.simpleChunkDataList?.Count ?? 0;
                    BLog.Info($"US map loaded: {n} chunks, terrain height range {_hMin:0.###}..{_hMax:0.###}.");
                }
            }
            catch (Exception e) { BLog.Error("LoadMapData postfix", e); }
        }

        // ---- generating a new map: overwrite the random grid with the real one
        [HarmonyPostfix, HarmonyPatch(typeof(MapData), nameof(MapData.GetRandomMapData), new[] { typeof(ShapeSettings) })]
        static void GetRandomMapData_Post(MapData __result)
        {
            if (!Active || __result == null) return;
            try { BuildUs(__result); }
            catch (Exception e) { BLog.Error("Building the US map failed", e); }
        }

        static void BuildUs(MapData md)
        {
            var list = md.simpleChunkDataList;
            int bornX = UsData.ChunkX(UsData.BornX), bornY = UsData.ChunkY(UsData.BornY);
            float halfW = UsData.CW / 2f, halfH = UsData.CH / 2f;
            int changed = 0, outside = 0;
            var counts = new Dictionary<int, int>();
            for (int i = 0; i < list.Count; i++)
            {
                var c = list[i];
                int col = UsData.Col(c.coordinateX), row = UsData.Row(c.coordinateY);
                if (col < 0 || row < 0 || col >= UsData.CW || row >= UsData.CH) { outside++; continue; }
                int k = row * UsData.CW + col;
                int t = UsData.Types[k];
                // open sea is left as plain field chunks: the water and ocean hooks below cover them with sea,
                // and field generation already skips ocean tiles
                if (t == (int)ChunkType.Ocean) { t = (int)ChunkType.Field; c.vegetationDensity = 0; }
                c.chunkType = (ChunkType)t;
                if (UsData.Types[k] != (int)ChunkType.Ocean) c.vegetationDensity = UsData.Veg[k] / 255f;
                float dx = (c.coordinateX - bornX) / halfW, dy = (c.coordinateY - bornY) / halfH;
                c.chunkLevel = MathF.Min(1.5f, MathF.Sqrt(dx * dx + dy * dy));
                if (UsData.Types[k] == (int)ChunkType.Ocean || t == (int)ChunkType.Edge) { c.monsterNumber = 0; c.animalNumber = 0; c.hasNest = false; c.hasScavengerCamp = false; }
                c.safezone = t == (int)ChunkType.Born;
                counts[t] = counts.TryGetValue(t, out var v) ? v + 1 : 1;
                changed++;
            }
            try { md.lakeDataList?.Clear(); md.lakePlacementDoneFlag = true; } catch (Exception e) { BLog.Warn("lake reset: " + e.Message); }
            md.RefreshChunkDic();
            md.ConnectChunks();
            int mst = md.roadEdgeList?.Count ?? 0, added = 0;
            if (Plugin.InterstateRoads.Value && md.roadEdgeList != null)
            {
                var have = new HashSet<long>();
                foreach (var e in md.roadEdgeList) have.Add(Key(e.chunkAId, e.chunkBId));
                foreach (var (ax, ay, bx, by) in UsData.Edges)
                {
                    int a = Id(ax, ay), b = Id(bx, by);
                    if (md.GetSimpleChunkDataById(a) == null || md.GetSimpleChunkDataById(b) == null) continue;
                    if (!have.Add(Key(a, b))) continue;
                    md.roadEdgeList.Add(new RoadEdge(a, b, RoadTier.Highway));
                    added++;
                }
            }
            var sb = new System.Text.StringBuilder();
            foreach (var kv in counts) sb.Append(((ChunkType)kv.Key).ToString()).Append('=').Append(kv.Value).Append(' ');
            BLog.Info($"US map built: {changed} chunks set ({outside} outside the data), roads: {mst} game links + {added} interstate links. Types: {sb}");
        }

        static int Id(int col, int row) => UsData.ChunkY(row) * UsData.CW + UsData.ChunkX(col);
        static long Key(int a, int b) => a < b ? ((long)a << 32) | (uint)b : ((long)b << 32) | (uint)a;

        // ---- per-tile hooks
        [HarmonyPrefix, HarmonyPatch(typeof(MapController), nameof(MapController.CalculateWaterFloatByWorldPosition))]
        static bool Water_Pre(Vector2 worldPosition, ref float __result)
        {
            if (!Active) return true;
            float w = UsData.WaterAt(worldPosition.x, worldPosition.y);
            __result = Math.Clamp((w - 110f) / 80f, 0f, 1f);
            return false;
        }

        [HarmonyPrefix, HarmonyPatch(typeof(MapController), nameof(MapController.IsInOcean))]
        static bool Ocean_Pre(Vector3 m_worldPosition, ref bool __result)
        {
            if (!Active) return true;
            __result = UsData.OceanAt(m_worldPosition.x, m_worldPosition.y) >= 128f;
            return false;
        }

        [HarmonyPostfix, HarmonyPatch(typeof(ShapeGenerator), nameof(ShapeGenerator.CalculateTerrainPoint))]
        static void Terrain_Post(ShapeGenerator __instance, Vector3 worldPos, ref float __result)
        {
            if (!Active) return;
            if (_terrainGen == IntPtr.Zero)
            {
                try { var g = MapController.instance?.terrainShapeGenerator; if (g != null) _terrainGen = g.Pointer; } catch { }
                if (_terrainGen == IntPtr.Zero) return;
            }
            if (__instance.Pointer != _terrainGen) return;
            float m = UsData.ElevAt(worldPos.x, worldPos.y);
            float h01 = MathF.Pow(Math.Clamp(m / 3500f, 0f, 1f), 0.6f);
            float lo = Plugin.HeightLow.Value, hi = Plugin.HeightHigh.Value;
            float real = _hMin + (lo + (hi - lo) * h01) * (_hMax - _hMin);
            float b = Math.Clamp(Plugin.NoiseBlend.Value, 0f, 1f);
            __result = real * (1 - b) + __result * b;
        }
    }
}
