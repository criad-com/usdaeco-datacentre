// 00_lib -- demo-datacentre-01 plan model + shared helpers for the Revit build suite.
// Runs first in the revit-repl session; later phases use the Dc static class
// and the plan record types defined here. No model mutations happen in this file.
// Units: the plan is metres; Revit internal is feet -- ALL geometry goes through
// Dc.M() / Dc.P() at the boundary.
using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;

// ---------------------------------------------------------------- plan model
// Mirrors out/build_plan.json (dataclasses.asdict of dcbuild Plan; tuples are
// JSON arrays). Only the fields the Revit build needs; unknown keys are ignored
// by System.Text.Json.

public class StoreyP { public string Id { get; set; } public string Name { get; set; } public double Elevation { get; set; } }

public class RoofP { public double Elevation { get; set; } public double Thickness { get; set; } }

public class GridLineP
{
    public string Id { get; set; }
    public string Label { get; set; }
    public string Axis { get; set; }          // "x" | "y"
    public double Value { get; set; }
    public double Start { get; set; }
    public double End { get; set; }
}

public class WallTypeSpecP
{
    public double Thickness { get; set; }
    public string Material { get; set; }
    [JsonPropertyName("fire_rating")] public string FireRating { get; set; }
}

public class WallOpeningP
{
    [JsonPropertyName("door_id")] public string DoorId { get; set; }
    public double[] At { get; set; }
    public double Width { get; set; }
    public double Height { get; set; }
}

public class WallP
{
    public string Id { get; set; }
    public string Storey { get; set; }
    public string Kind { get; set; }          // external | fire | internal
    public double[] P1 { get; set; }
    public double[] P2 { get; set; }
    public double Height { get; set; }
    public double Thickness { get; set; }
    public string Left { get; set; }
    public string Right { get; set; }
    public List<WallOpeningP> Openings { get; set; } = new List<WallOpeningP>();
}

public class DoorP
{
    public string Id { get; set; }
    public string Name { get; set; }
    public string Kind { get; set; }          // single | double | roller
    [JsonPropertyName("wall_id")] public string WallId { get; set; }
    public string Storey { get; set; }
    public double[] Pos { get; set; }
    public double Width { get; set; }
    public double Height { get; set; }
    public bool External { get; set; }
}

public class ColumnP
{
    public string Id { get; set; }
    public double[] Pos { get; set; }
    public double Height { get; set; }
    public double Size { get; set; }
}

public class SlabP
{
    public List<double[]> Outline { get; set; }
    [JsonPropertyName("inner_loops")] public List<double[]> InnerLoops { get; set; }
    public string Id { get; set; }
    public string Kind { get; set; }          // ground | upper | roof | pad
    public double X { get; set; }
    public double Y { get; set; }
    public double W { get; set; }
    public double D { get; set; }
    [JsonPropertyName("top_elevation")] public double TopElevation { get; set; }
    public double Thickness { get; set; }
    public List<double[]> Voids { get; set; } = new List<double[]>();   // (x, y, w, d)
}

public class EquipP
{
    public string Id { get; set; }
    public string Cls { get; set; }
    public string Name { get; set; }
    public string Discipline { get; set; }
    public string Space { get; set; }
    public string Pad { get; set; }
    public double[] Pos { get; set; }         // footprint centre at FFL (x, y, z)
    public double[] Size { get; set; }        // (w, d, h), w along local X before rot
    public double Rot { get; set; }           // degrees CCW about +Z
    public string Shape { get; set; } = "box";
    public string Side { get; set; }
    public string Loop { get; set; }
}

public class RackP
{
    public string Id { get; set; }
    public string Hall { get; set; }
    public string Row { get; set; }
    public int Index { get; set; }
    public double[] Pos { get; set; }         // footprint centre (x, y)
    public double[] Size { get; set; }
    public double Kw { get; set; }
    public string Space { get; set; }
    public string Cooling { get; set; }       // dlc | air
}

public class RunP
{
    public string Id { get; set; }
    public string Kind { get; set; }          // busway | tray | manifold_supply | manifold_return
    public string Row { get; set; }
    public string Side { get; set; }
    public double Y { get; set; }
    public double Z { get; set; }
    [JsonPropertyName("x_start")] public double XStart { get; set; }
    [JsonPropertyName("x_end")] public double XEnd { get; set; }
    public List<double> Taps { get; set; } = new List<double>();
    public double[] Size { get; set; }        // (w, h) or (d, d) for pipes
    public string Shape { get; set; } = "box";
    public string Feed { get; set; }
}

public class RouteP
{
    public string Id { get; set; }
    public string Kind { get; set; }          // pipe | tray | cable
    [JsonPropertyName("system")] public string SystemName { get; set; }
    public List<double[]> Waypoints { get; set; } = new List<double[]>();
    public double? Diameter { get; set; }
    public double[] Size { get; set; }
    [JsonPropertyName("from_id")] public string FromId { get; set; }
    [JsonPropertyName("to_id")] public string ToId { get; set; }
}

public class CameraP
{
    public string Id { get; set; }
    [JsonPropertyName("global_id")] public string GlobalId { get; set; }
    public string Type { get; set; }
    public string Level { get; set; }
    public string Family { get; set; }
    [JsonPropertyName("target_density")] public double TargetDensity { get; set; }
    [JsonPropertyName("native_target_density")] public double NativeTargetDensity { get; set; }
    [JsonPropertyName("preset_order")] public List<string> PresetOrder { get; set; }
    public Dictionary<string,string> Contract { get; set; }
    [JsonPropertyName("type_contract")] public Dictionary<string,string> TypeContract { get; set; }
    public string Space { get; set; }
    public double[] Pos { get; set; }
    public double Pan { get; set; }
    public double Tilt { get; set; }
    public double Roll { get; set; }
    [JsonPropertyName("device_rotation")] public double DeviceRotation { get; set; }
    [JsonPropertyName("focal_length")] public double FocalLength { get; set; }
    public double Range { get; set; }
    public string Scenario { get; set; }
    public string Mount { get; set; }
    public string Phase { get; set; }
    public string System { get; set; }
    public List<string> Targets { get; set; }
    public Dictionary<string, JsonElement> Presets { get; set; }
    public List<string> Tour { get; set; }
}

public class SpaceP
{
    [JsonPropertyName("z_offset")] public double ZOffset {get;set;}
    public string Id {get;set;}
    public string Name {get;set;}
    public string Storey {get;set;}
    public double X {get;set;} public double Y {get;set;}
    public double W {get;set;} public double D {get;set;}
    public double Height {get;set;}
    public bool External {get;set;}
}
public class StairP
{
    public string Id {get;set;} public string Storey {get;set;} public string Space {get;set;}
    public double X {get;set;} public double Y {get;set;} public double Z {get;set;}
    public double Width {get;set;} public List<double[]> Profile {get;set;}
}
public class PlanData
{
    [JsonPropertyName("revit_scope")] public string Scope {get;set;}
    [JsonPropertyName("revit_datums")] public List<StoreyP> Datums {get;set;} = new List<StoreyP>();
    [JsonPropertyName("revit_stairs")] public List<StairP> Stairs {get;set;} = new List<StairP>();
    [JsonPropertyName("revit_arch_ids")] public List<string> ArchIds {get;set;} = new List<string>();
    [JsonPropertyName("revit_status")] public JsonElement Status {get;set;}
    [JsonPropertyName("revit_identities")] public Dictionary<string,string> Identities {get;set;}

    public List<CameraP> Cameras { get; set; } = new List<CameraP>();
    public JsonElement Security { get; set; }
    public List<SpaceP> Spaces { get; set; }
    public List<StoreyP> Storeys { get; set; }
    public RoofP Roof { get; set; }
    [JsonPropertyName("grid_lines")] public List<GridLineP> GridLines { get; set; }
    [JsonPropertyName("wall_types")] public Dictionary<string, WallTypeSpecP> WallTypes { get; set; }
    public List<WallP> Walls { get; set; }
    public List<DoorP> Doors { get; set; }
    public List<ColumnP> Columns { get; set; }
    public List<SlabP> Slabs { get; set; }
    public List<EquipP> Equipment { get; set; }
    public List<RackP> Racks { get; set; }
    public List<RunP> Runs { get; set; }
    public List<RouteP> Routes { get; set; }
}

// ---------------------------------------------------------- failure handling
// Preserve diagnostics; unresolved errors roll back without opening a dialog.
public class DcFailureSwallower : IFailuresPreprocessor
{
    public FailureProcessingResult PreprocessFailures(FailuresAccessor fa)
    {
        foreach (var f in fa.GetFailureMessages())
        {
            Dc.Note("native " + f.GetSeverity() + ": " + f.GetDescriptionText());
            if (f.GetSeverity() != FailureSeverity.Warning) return FailureProcessingResult.ProceedWithRollBack;
            fa.DeleteWarning(f);
        }
        return FailureProcessingResult.Continue;
    }
}

// ------------------------------------------------------------------ helpers
public static class Dc
{
    public static string OutDir = Environment.GetEnvironmentVariable("AECO_REVIT_WORKDIR") ?? "demo-output";
    public static string FamilyDir = Environment.GetEnvironmentVariable("AECO_REVIT_FAMILY_DIR") ?? "<camera-family-directory>";
    public static bool Full = Environment.GetEnvironmentVariable("AECO_REVIT_VARIANT") == "full";
    public static string ModelName = Full ? "demo-datacentre-01-full.rvt" : "demo-datacentre-01.rvt";
    public static string ExportName = Full ? "demo-datacentre-01-full-revit.ifc" : "demo-datacentre-01-revit.ifc";
    public static string PlanPath = Path.Combine(OutDir, Full ? "build_plan-full.json" : "build_plan.json");
    public static string FamiliesPath = Path.Combine(OutDir, "families.yaml");

    public static int CameraStart=0, CameraCount=5;
    public static UIApplication Ui;
    public static Document Doc;                 // the demo-datacentre-01 project doc, set by 10_setup
    public static PlanData Plan;
    public static bool StatusBound=false;
    public static List<string> Log = new List<string>();
    public static Dictionary<string, ElementId> IdMap = new Dictionary<string, ElementId>();
    public static Dictionary<string, Level> Levels = new Dictionary<string, Level>();       // storey id (+ "lvl.roof") -> Level
    public static Dictionary<string, Wall> WallsById = new Dictionary<string, Wall>();
    public static Dictionary<string, double> StoreyElev = new Dictionary<string, double>(); // storey id -> metres

    static HashSet<string> _once = new HashSet<string>();
    static Dictionary<string, WallType> _wallTypeCache = new Dictionary<string, WallType>();
    static Dictionary<string, string> _rfaIndex;

    public static void Note(string msg) { Log.Add(msg); }
    public static void NoteOnce(string key, string msg) { if (_once.Add(key)) Log.Add(msg); }
    public static string LogTail(int n)
    {
        int start = Math.Max(0, Log.Count - n);
        return string.Join(" | ", Log.Skip(start));
    }

    // -- units --------------------------------------------------------------
    public static double M(double metres) => UnitUtils.ConvertToInternalUnits(metres, UnitTypeId.Meters);
    public static double Mm(double feet) => UnitUtils.ConvertFromInternalUnits(feet, UnitTypeId.Millimeters);
    public static XYZ P(double xM, double yM, double zM) => new XYZ(M(xM), M(yM), M(zM));

    // -- plan ---------------------------------------------------------------
    public static PlanData LoadPlan()
    {
        if (Plan != null) return Plan;
        if (!File.Exists(PlanPath)) throw new Exception("plan missing at " + PlanPath + " -- run driver.py upload first");
        var opts = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
        Plan = JsonSerializer.Deserialize<PlanData>(File.ReadAllText(PlanPath), opts);
        StoreyElev.Clear();
        foreach (var s in Plan.Storeys) StoreyElev[s.Id] = s.Elevation;
        return Plan;
    }

    public static void RequireDoc()
    {
        if (Doc == null || !Doc.IsValidObject) throw new Exception("Dc.Doc not set -- run 10_setup first");
        if (String.Equals(Ui?.ActiveUIDocument?.Document?.PathName, Doc.PathName, StringComparison.OrdinalIgnoreCase))
            throw new Exception("Refusing the foreground document");
        var expected = Path.GetFullPath(Path.Combine(OutDir, ModelName));
        if (!String.Equals(Path.GetFullPath(Doc.PathName), expected, StringComparison.OrdinalIgnoreCase))
            throw new Exception("Refusing a document outside the configured model path");
    }

    public static void ResetDocState()
    {
        // Called by 10_setup on re-run: drop everything tied to the old document.
        IdMap.Clear(); Levels.Clear(); WallsById.Clear();
        StatusBound=false;
        _wallTypeCache.Clear();
    }

    // -- transactions -------------------------------------------------------
    public static void Tx(string name, Action<Document> act)
    {
        RequireDoc();
        using (var t = new Transaction(Doc, name))
        {
            t.Start();
            var fho = t.GetFailureHandlingOptions();
            fho.SetFailuresPreprocessor(new DcFailureSwallower());
            fho.SetClearAfterRollback(true);
            t.SetFailureHandlingOptions(fho);
            act(Doc);
            if(StatusBound) StampStatus();
            if (t.Commit() != TransactionStatus.Committed) throw new Exception("Transaction rolled back: " + name);
        }
    }

    // Every authoring phase stamps all bound products, including nested guides
    // and unmarked service segments. Verify the native input before commit.
    public static int StampStatus()
    {
        var categories=Plan.Status.GetProperty("categories").EnumerateArray()
            .Select(v=>(long)Enum.Parse<BuiltInCategory>(v.GetString())).ToHashSet();
        string value=Plan.Status.GetProperty("value").GetString();
        if(value!="NEW") throw new Exception("Unsupported build Status");
        var products=new FilteredElementCollector(Doc).WhereElementIsNotElementType()
            .Where(e=>e.Category!=null && categories.Contains(e.Category.Id.Value)).ToList();
        foreach(var e in products)
        {
            var p=e.LookupParameter("Status");
            if(p==null || p.IsReadOnly || p.StorageType!=StorageType.String)
                throw new Exception("Writable Status missing on category "+e.Category.Name);
            if(p.AsString()!=value) p.Set(value);
        }
        Doc.Regenerate();
        if(products.Any(e=>e.LookupParameter("Status").AsString()!=value))
            throw new Exception("Status read-back differs after regeneration");
        return products.Count;
    }

    // -- identity -----------------------------------------------------------
    public static void SetMark(Element e, string specId)
    {
        if (e == null || string.IsNullOrEmpty(specId)) throw new Exception("Missing product identity");
        var mark = e.get_Parameter(BuiltInParameter.ALL_MODEL_MARK) ?? e.LookupParameter("Mark");
        if (mark != null && !mark.IsReadOnly) mark.Set(specId);
        else if (!(e is Level) && !(e is Room)) throw new Exception("Mark unavailable: " + specId);
        string guid;
        if (Plan.Identities.TryGetValue(specId, out guid))
        {
            var p = e.get_Parameter(BuiltInParameter.IFC_GUID);
            if (p == null || p.IsReadOnly) throw new Exception("IFC_GUID unavailable: " + specId);
            p.Set(guid);
        }
    }

    public static void ExportClass(Element e, string entity, string predefined)
    {
        if (!Full) return;
        var cls=e.get_Parameter(BuiltInParameter.IFC_EXPORT_ELEMENT_AS);
        var pre=e.get_Parameter(BuiltInParameter.IFC_EXPORT_PREDEFINEDTYPE);
        if (cls == null || cls.IsReadOnly || pre == null || pre.IsReadOnly)
            throw new Exception("Writable IFC export classification is missing");
        cls.Set(entity); pre.Set(predefined);
    }

    // -- levels -------------------------------------------------------------
    public static Level FindOrCreateLevel(string name, double elevM)
    {
        RequireDoc();
        double elev = M(elevM);
        var existing = new FilteredElementCollector(Doc).OfClass(typeof(Level)).Cast<Level>()
            .FirstOrDefault(l => Math.Abs(l.Elevation - elev) < 0.004);       // ~1.2 mm
        if (existing != null)
        {
            try { if (existing.Name != name) existing.Name = name; }
            catch (Exception ex) { Note("level-rename " + name + ": " + ex.Message); }
            return existing;
        }
        var lvl = Level.Create(Doc, elev);
        try { lvl.Name = name; }
        catch (Exception ex) { Note("level-name " + name + ": " + ex.Message); }
        return lvl;
    }

    public static Level LevelFor(double zM)
    {
        // highest known level at or below z (small tolerance upward)
        Level best = null;
        double zLimit = M(zM) + 0.01;
        foreach (var l in Levels.Values)
            if (l.Elevation <= zLimit && (best == null || l.Elevation > best.Elevation)) best = l;
        return best ?? Levels.Values.OrderBy(l => l.Elevation).First();
    }

    // -- wall types ---------------------------------------------------------
    public static WallType ResolveWallType(string kind, double thickM)
    {
        RequireDoc();
        WallType cached;
        if (_wallTypeCache.TryGetValue(kind, out cached)) return cached;
        string wanted = "DC " + char.ToUpperInvariant(kind[0]) + kind.Substring(1);
        var basics = new FilteredElementCollector(Doc).OfClass(typeof(WallType)).Cast<WallType>()
            .Where(w => w.Kind == WallKind.Basic).ToList();
        if (basics.Count == 0) { Note("wall-type-none: template has no basic wall types"); return null; }
        var byName = basics.FirstOrDefault(w => w.Name == wanted);
        if (byName != null) { _wallTypeCache[kind] = byName; return byName; }

        double target = M(thickM);
        var nearest = basics.OrderBy(w => Math.Abs(w.Width - target)).First();
        WallType result = nearest;
        try
        {
            var dup = nearest.Duplicate(wanted) as WallType;
            var cs = dup.GetCompoundStructure();
            if (cs != null)
            {
                var layers = cs.GetLayers();
                if (layers.Count == 1)
                {
                    cs.SetLayerWidth(0, target);
                    dup.SetCompoundStructure(cs);
                }
                else
                {
                    int widest = 0;
                    for (int i = 1; i < layers.Count; i++) if (layers[i].Width > layers[widest].Width) widest = i;
                    double others = layers.Sum(l => l.Width) - layers[widest].Width;
                    double newW = target - others;
                    if (newW > M(0.01)) { cs.SetLayerWidth(widest, newW); dup.SetCompoundStructure(cs); }
                }
            }
            result = dup;
        }
        catch (Exception ex) { Note("wall-type-dup " + kind + ": " + ex.Message); result = nearest; }
        Note("wall-type " + kind + ": " + result.Name + " width " + Mm(result.Width).ToString("0")
             + "mm vs plan " + (thickM * 1000).ToString("0") + "mm");
        _wallTypeCache[kind] = result;
        return result;
    }

    // -- family lookup ------------------------------------------------------
    static void EnsureRfaIndex()
    {
        if (_rfaIndex != null) return;
        _rfaIndex = new Dictionary<string, string>();
        var roots = new[] { Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "Autodesk", "RVT 2027"), Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "Autodesk", "Libraries") };
        foreach (var root in roots)
        {
            try
            {
                if (!Directory.Exists(root)) continue;
                foreach (var f in Directory.GetFiles(root, "*.rfa", SearchOption.AllDirectories))
                {
                    var key = Path.GetFileNameWithoutExtension(f).ToLowerInvariant();
                    if (!_rfaIndex.ContainsKey(key)) _rfaIndex[key] = f;
                }
            }
            catch (Exception ex) { Note("rfa-index " + root + ": " + ex.Message); }
        }
        Note("rfa-index: " + _rfaIndex.Count + " families on disk");
    }

    public static FamilySymbol LoadFamilySymbol(string name)
    {
        // Must be called inside an open transaction.
        EnsureRfaIndex();
        var key = name.Trim().ToLowerInvariant();
        string path;
        if (!_rfaIndex.TryGetValue(key, out path))
            path = key.Length >= 4 ? _rfaIndex.FirstOrDefault(kv => kv.Key.Contains(key)).Value : null;
        if (path == null) return null;
        try
        {
            Family fam;
            if (!Doc.LoadFamily(path, out fam) || fam == null)
            {
                // may already be loaded under this name
                fam = new FilteredElementCollector(Doc).OfClass(typeof(Family)).Cast<Family>()
                    .FirstOrDefault(f => f.Name.ToLowerInvariant() == Path.GetFileNameWithoutExtension(path).ToLowerInvariant());
                if (fam == null) return null;
            }
            var sid = fam.GetFamilySymbolIds().FirstOrDefault();
            return sid == null ? null : Doc.GetElement(sid) as FamilySymbol;
        }
        catch (Exception ex) { Note("load-family " + name + ": " + ex.Message); return null; }
    }

    public static FamilySymbol FindSymbol(BuiltInCategory? cat, IList<string> candidates)
    {
        RequireDoc();
        var col = new FilteredElementCollector(Doc).OfClass(typeof(FamilySymbol));
        if (cat.HasValue) col = col.OfCategory(cat.Value);
        var syms = col.Cast<FamilySymbol>().ToList();
        foreach (var cand in candidates)
        {
            var c = (cand ?? "").Trim().ToLowerInvariant();
            if (c.Length == 0) continue;
            var hit = syms.FirstOrDefault(s => s.FamilyName.ToLowerInvariant() == c || s.Name.ToLowerInvariant() == c)
                   ?? syms.FirstOrDefault(s => s.FamilyName.ToLowerInvariant().StartsWith(c))
                   ?? (c.Length >= 4 ? syms.FirstOrDefault(s => s.FamilyName.ToLowerInvariant().Contains(c)) : null);
            if (hit != null) return hit;
        }
        foreach (var cand in candidates)
        {
            var s = LoadFamilySymbol(cand);
            if (s != null) return s;
        }
        return null;
    }

    public static void Activate(FamilySymbol s)
    {
        if (s != null && !s.IsActive) { s.Activate(); Doc.Regenerate(); }
    }

    // -- DirectShape builders ------------------------------------------------
    static DirectShape DsFromSolid(BuiltInCategory cat, string mark, Solid solid)
    {
        var catId = new ElementId(cat);
        if (!DirectShape.IsValidCategoryId(catId, Doc))
        {
            NoteOnce("ds-cat-" + cat, "ds-category-fallback " + cat + " -> GenericModel");
            catId = new ElementId(BuiltInCategory.OST_GenericModel);
        }
        var ds = DirectShape.CreateElement(Doc, catId);
        ds.SetShape(new List<GeometryObject> { solid });
        SetMark(ds, mark);
        if (mark != null) IdMap[mark] = ds.Id;
        return ds;
    }

    // Box: footprint centre (cx, cy), bottom at zBot, size w x d x h, rotated rotDeg CCW about +Z. All metres.
    public static DirectShape DsBox(BuiltInCategory cat, string mark, double cx, double cy, double zBot,
                                    double w, double d, double h, double rotDeg)
    {
        double hw = w / 2.0, hd = d / 2.0;
        var pts = new List<XYZ>
        {
            P(cx - hw, cy - hd, zBot), P(cx + hw, cy - hd, zBot),
            P(cx + hw, cy + hd, zBot), P(cx - hw, cy + hd, zBot),
        };
        if (Math.Abs(rotDeg) > 1e-9)
        {
            var tf = Transform.CreateRotationAtPoint(XYZ.BasisZ, rotDeg * Math.PI / 180.0, P(cx, cy, zBot));
            pts = pts.Select(pt => tf.OfPoint(pt)).ToList();
        }
        var loop = new CurveLoop();
        for (int i = 0; i < 4; i++) loop.Append(Line.CreateBound(pts[i], pts[(i + 1) % 4]));
        var solid = GeometryCreationUtilities.CreateExtrusionGeometry(
            new List<CurveLoop> { loop }, XYZ.BasisZ, M(Math.Max(h, 0.01)));
        return DsFromSolid(cat, mark, solid);
    }

    // Cylinder: centre (cx, cy), bottom at zBot, diameter dia, height h. All metres.
    public static DirectShape DsCylinder(BuiltInCategory cat, string mark, double cx, double cy, double zBot,
                                         double dia, double h)
    {
        double r = M(dia / 2.0);
        var c = P(cx, cy, zBot);
        var loop = new CurveLoop();
        loop.Append(Arc.Create(c, r, 0.0, Math.PI, XYZ.BasisX, XYZ.BasisY));
        loop.Append(Arc.Create(c, r, Math.PI, 2.0 * Math.PI, XYZ.BasisX, XYZ.BasisY));
        var solid = GeometryCreationUtilities.CreateExtrusionGeometry(
            new List<CurveLoop> { loop }, XYZ.BasisZ, M(Math.Max(h, 0.01)));
        return DsFromSolid(cat, mark, solid);
    }

    // Axis-aligned segment box between a and b (metres, orthogonal). w = cross width, h = cross height.
    // Horizontal runs treat z as the centreline; vertical runs are w x w in plan.
    public static DirectShape DsSegmentBox(BuiltInCategory cat, string mark, double[] a, double[] b,
                                           double w, double h)
    {
        double dx = Math.Abs(a[0] - b[0]), dy = Math.Abs(a[1] - b[1]), dz = Math.Abs(a[2] - b[2]);
        double x0 = Math.Min(a[0], b[0]), y0 = Math.Min(a[1], b[1]), z0 = Math.Min(a[2], b[2]);
        if (dz >= dx && dz >= dy)
            return DsBox(cat, mark, a[0], b[1], z0, w, w, Math.Max(dz, 0.01), 0.0);
        if (dx >= dy)
            return DsBox(cat, mark, x0 + dx / 2.0, a[1], z0 - h / 2.0, Math.Max(dx, 0.01), w, h, 0.0);
        return DsBox(cat, mark, a[0], y0 + dy / 2.0, z0 - h / 2.0, w, Math.Max(dy, 0.01), h, 0.0);
    }
}

$"00_lib ok: plan model + Dc helpers defined (plan path {Dc.PlanPath})"
