// 50_containment -- busways + trays from plan.runs as CableTray segments
// (types "DC Busway" / "DC Tray" duplicated from stock; width/height are
// instance params), vertical dropper segments per tap (busways down to 2.3 m,
// trays to 2.25 m; dropper Marks use the IFC-side key format <run>.dropNNN).
// plan.routes kind tray/cable: chained CableTray segments along waypoints
// (type "DC Cable Run" for cables). Elbow/tee fittings skipped in v1 (counted).
// If the template has no CableTrayType at all: DirectShape fallback boxes.

var plan50 = Dc.LoadPlan();
Dc.RequireDoc();

int nSeg50 = 0, nDrop50 = 0, nRoute50 = 0, nDsFall50 = 0, nFitSkip50 = 0;

Dc.Tx("DC containment", d =>
{
    var trayTypes = new FilteredElementCollector(d).OfClass(typeof(Autodesk.Revit.DB.Electrical.CableTrayType))
        .Cast<Autodesk.Revit.DB.Electrical.CableTrayType>().ToList();
    Func<string, Autodesk.Revit.DB.Electrical.CableTrayType> trayType = wanted =>
    {
        var hit = trayTypes.FirstOrDefault(t => t.Name == wanted);
        if (hit != null) return hit;
        if (trayTypes.Count == 0) return null;
        try
        {
            var dup = trayTypes.First().Duplicate(wanted) as Autodesk.Revit.DB.Electrical.CableTrayType;
            trayTypes.Add(dup);
            return dup;
        }
        catch (Exception ex) { Dc.Note("tray-type-dup " + wanted + ": " + ex.Message); return trayTypes.First(); }
    };
    var busType = trayType("DC Busway");
    var trType = trayType("DC Tray");
    var cblType = trayType("DC Cable Run");
    if (busType == null) Dc.Note("cabletray-type-none: template has no cable tray types -- DirectShape fallback");

    var lvlId = Dc.Levels["lvl.l0"].Id;

    // one straight tray segment a->b (metres), instance width/height set, optional Mark
    Func<Autodesk.Revit.DB.Electrical.CableTrayType, double[], double[], double, double, string, Element> seg =
        (tt, a, b, wM, hM, mark) =>
    {
        if (tt == null)
        {
            nDsFall50++;
            return Dc.DsSegmentBox(BuiltInCategory.OST_CableTray, mark, a, b, wM, hM);
        }
        var ct = Autodesk.Revit.DB.Electrical.CableTray.Create(d, tt.Id,
            Dc.P(a[0], a[1], a[2]), Dc.P(b[0], b[1], b[2]), lvlId);
        var wp = ct.get_Parameter(BuiltInParameter.RBS_CABLETRAY_WIDTH_PARAM);
        if (wp != null && !wp.IsReadOnly) { try { wp.Set(Dc.M(wM)); } catch { Dc.NoteOnce("ctw" + wM, "tray-width-unset " + wM); } }
        var hp = ct.get_Parameter(BuiltInParameter.RBS_CABLETRAY_HEIGHT_PARAM);
        if (hp != null && !hp.IsReadOnly) { try { hp.Set(Dc.M(hM)); } catch { Dc.NoteOnce("cth" + hM, "tray-height-unset " + hM); } }
        if (mark != null) { Dc.SetMark(ct, mark); Dc.IdMap[mark] = ct.Id; }
        return ct;
    };

    // -- runs: busways + row trays ------------------------------------------
    foreach (var run in plan50.Runs.Where(r => r.Kind == "busway" || r.Kind == "tray"))
    {
        try
        {
            var tt = run.Kind == "busway" ? busType : trType;
            double dropBottom = run.Kind == "busway" ? 2.3 : 2.25;
            seg(tt,
                new[] { run.XStart, run.Y, run.Z }, new[] { run.XEnd, run.Y, run.Z },
                run.Size[0], run.Size[1], run.Id);
            nSeg50++;
            int i = 0;
            foreach (var tx in run.Taps)
            {
                i++;
                seg(tt,
                    new[] { tx, run.Y, run.Z }, new[] { tx, run.Y, dropBottom },
                    0.15, 0.05, run.Id + ".drop" + i.ToString("000"));
                nDrop50++;
                nFitSkip50++;               // the tee that would join tap to run
            }
        }
        catch (Exception ex) { Dc.Note("run-fail " + run.Id + ": " + ex.Message); }
    }

    // -- routes: spine trays + cable runs -----------------------------------
    foreach (var rt in plan50.Routes.Where(r => r.Kind == "tray" || r.Kind == "cable"))
    {
        try
        {
            var tt = rt.Kind == "cable" ? cblType : trType;
            double w = rt.Size != null ? rt.Size[0] : 0.15;
            double h = rt.Size != null ? rt.Size[1] : 0.05;
            if (rt.Size == null)
                Dc.NoteOnce("cable-size", "cable routes have no size in plan -- using 150x50");
            for (int i = 0; i + 1 < rt.Waypoints.Count; i++)
            {
                var a = rt.Waypoints[i];
                var b = rt.Waypoints[i + 1];
                double len = Math.Abs(a[0] - b[0]) + Math.Abs(a[1] - b[1]) + Math.Abs(a[2] - b[2]);
                if (len < 1e-6) continue;
                seg(tt, a, b, w, h, i == 0 ? rt.Id : null);
                nSeg50++;
            }
            nFitSkip50 += Math.Max(0, rt.Waypoints.Count - 2);
            nRoute50++;
        }
        catch (Exception ex) { Dc.Note("route-fail " + rt.Id + ": " + ex.Message); }
    }
});

$"50_containment ok: {nSeg50} tray segments, {nDrop50} droppers, {nRoute50} routes, {nFitSkip50} fittings skipped (v1), {nDsFall50} directshape fallbacks, log: {Dc.LogTail(8)}"
