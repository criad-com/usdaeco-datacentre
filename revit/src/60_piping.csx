// 60_piping -- plan.routes kind=="pipe": Pipe.Create chained along waypoints,
// PipingSystemType duplicated per system ("DC FWS Supply", "DC TCS Return",
// "DC CHW Supply", ..., "DC Fuel"), diameter set per route (default DN100
// where the plan has none). Manifold runs (manifold_supply/_return, Hall A
// TCS): main pipe along the span at z + one drop per tap down to 2.2 m
// (DN50, Marked <run>.dropNNN). Bend/tee fittings skipped in v1 (counted).

var plan60 = Dc.LoadPlan();
Dc.RequireDoc();

int nPipe60 = 0, nDrop60 = 0, nRoute60 = 0, nDsFall60 = 0, nFitSkip60 = 0;

Dc.Tx("DC piping", d =>
{
    var pipeType = new FilteredElementCollector(d).OfClass(typeof(Autodesk.Revit.DB.Plumbing.PipeType))
        .Cast<Autodesk.Revit.DB.Plumbing.PipeType>().FirstOrDefault();
    var sysTypes = new FilteredElementCollector(d).OfClass(typeof(Autodesk.Revit.DB.Plumbing.PipingSystemType))
        .Cast<Autodesk.Revit.DB.Plumbing.PipingSystemType>().ToList();
    if (pipeType == null) Dc.Note("pipe-type-none: template has no pipe types -- DirectShape fallback");

    var sysCache = new Dictionary<string, Autodesk.Revit.DB.Plumbing.PipingSystemType>();
    Func<string, bool, Autodesk.Revit.DB.Plumbing.PipingSystemType> mepSys = (wanted, isReturn) =>
    {
        Autodesk.Revit.DB.Plumbing.PipingSystemType got;
        if (sysCache.TryGetValue(wanted, out got)) return got;
        got = sysTypes.FirstOrDefault(t => t.Name == wanted);
        if (got == null)
        {
            var basis = sysTypes.FirstOrDefault(t => t.SystemClassification ==
                            (isReturn ? MEPSystemClassification.ReturnHydronic : MEPSystemClassification.SupplyHydronic))
                        ?? sysTypes.FirstOrDefault();
            if (basis != null)
            {
                try { got = basis.Duplicate(wanted) as Autodesk.Revit.DB.Plumbing.PipingSystemType; sysTypes.Add(got); }
                catch (Exception ex) { Dc.Note("pipe-sys-dup " + wanted + ": " + ex.Message); got = basis; }
            }
        }
        sysCache[wanted] = got;
        return got;
    };

    // plan system id -> DC piping system name
    Func<string, string> sysName = s =>
    {
        s = (s ?? "").ToLowerInvariant();
        bool ret = s.Contains("return");
        if (s.Contains("fws")) return ret ? "DC FWS Return" : "DC FWS Supply";
        if (s.Contains("tcs")) return ret ? "DC TCS Return" : "DC TCS Supply";
        if (s.Contains("chw")) return ret ? "DC CHW Return" : "DC CHW Supply";
        if (s.Contains("fuel")) return "DC Fuel";
        return "DC Pipe";
    };

    var lvlId = Dc.Levels["lvl.l0"].Id;

    // one pipe segment a->b (metres) on the named system, diameter diaM, optional Mark
    Func<string, double[], double[], double, string, Element> seg = (sys, a, b, diaM, mark) =>
    {
        var pst = mepSys(sysName(sys), sys != null && sys.ToLowerInvariant().Contains("return"));
        if (pipeType == null || pst == null)
        {
            nDsFall60++;
            return Dc.DsSegmentBox(BuiltInCategory.OST_PipeCurves, mark, a, b, diaM, diaM);
        }
        var pipe = Autodesk.Revit.DB.Plumbing.Pipe.Create(d, pst.Id, pipeType.Id, lvlId,
            Dc.P(a[0], a[1], a[2]), Dc.P(b[0], b[1], b[2]));
        var dp = pipe.get_Parameter(BuiltInParameter.RBS_PIPE_DIAMETER_PARAM);
        if (dp != null && !dp.IsReadOnly)
        {
            try { dp.Set(Dc.M(diaM)); }
            catch { Dc.NoteOnce("dia" + diaM, "pipe-diameter-unset " + (diaM * 1000).ToString("0") + "mm (not in segment sizes)"); }
        }
        if (mark != null) { Dc.SetMark(pipe, mark); Dc.IdMap[mark] = pipe.Id; }
        return pipe;
    };

    // -- routes kind == "pipe" ----------------------------------------------
    foreach (var rt in plan60.Routes.Where(r => r.Kind == "pipe"))
    {
        try
        {
            double dia = rt.Diameter ?? 0.1;
            if (rt.Diameter == null)
                Dc.NoteOnce("pipe-nodia", "pipe routes without diameter -- defaulting DN100");
            for (int i = 0; i + 1 < rt.Waypoints.Count; i++)
            {
                var a = rt.Waypoints[i];
                var b = rt.Waypoints[i + 1];
                double len = Math.Abs(a[0] - b[0]) + Math.Abs(a[1] - b[1]) + Math.Abs(a[2] - b[2]);
                if (len < 1e-6) continue;
                seg(rt.SystemName, a, b, dia, i == 0 ? rt.Id : null);
                nPipe60++;
            }
            nFitSkip60 += Math.Max(0, rt.Waypoints.Count - 2);
            nRoute60++;
        }
        catch (Exception ex) { Dc.Note("pipe-route-fail " + rt.Id + ": " + ex.Message); }
    }

    // -- manifold runs (Hall A TCS headers with per-rack hose drops) ---------
    foreach (var run in plan60.Runs.Where(r => r.Kind == "manifold_supply" || r.Kind == "manifold_return"))
    {
        try
        {
            string sys = run.Kind == "manifold_supply" ? "sys.tcs.supply" : "sys.tcs.return";
            double dia = run.Size != null ? run.Size[0] : 0.1;
            seg(sys, new[] { run.XStart, run.Y, run.Z }, new[] { run.XEnd, run.Y, run.Z }, dia, run.Id);
            nPipe60++;
            int i = 0;
            foreach (var tx in run.Taps)
            {
                i++;
                seg(sys, new[] { tx, run.Y, run.Z }, new[] { tx, run.Y, 2.2 }, 0.05,
                    run.Id + ".drop" + i.ToString("000"));
                nDrop60++;
                nFitSkip60++;               // the tee that would join drop to header
            }
        }
        catch (Exception ex) { Dc.Note("manifold-fail " + run.Id + ": " + ex.Message); }
    }
});

$"60_piping ok: {nPipe60} pipe segments, {nDrop60} hose drops, {nRoute60} routes, {nFitSkip60} fittings skipped (v1), {nDsFall60} directshape fallbacks, log: {Dc.LogTail(8)}"
