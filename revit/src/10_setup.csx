// 10_setup -- new metric project doc, levels from plan.storeys (+ roof), grids.
// Stores the doc in Dc.Doc; every later phase uses Dc.Doc, NOT the repl global doc.
using System.IO;

Dc.Ui=uiapp;
var plan10 = Dc.LoadPlan();

// Reattach only the exact background path. Never close or activate a document.
var modelPath10 = Path.GetFullPath(Path.Combine(Dc.OutDir, "demo-datacentre-01.rvt"));
bool update10 = Environment.GetEnvironmentVariable("AECO_REVIT_UPDATE") == "1";
if (update10 && !File.Exists(modelPath10))
    throw new Exception("Update requires the existing model file; no project created");
var resident10 = app.Documents.Cast<Document>().FirstOrDefault(d => !String.IsNullOrEmpty(d.PathName)
    && String.Equals(Path.GetFullPath(d.PathName), modelPath10, StringComparison.OrdinalIgnoreCase));
if (resident10 != null && String.Equals(uiapp.ActiveUIDocument?.Document?.PathName,resident10.PathName,StringComparison.OrdinalIgnoreCase))
    throw new Exception("Refusing the foreground document");
Dc.ResetDocState();

// -- template ----------------------------------------------------------------
string tpl10 = null;
try
{
    var rtes = Directory.GetFiles(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "Autodesk", "RVT 2027"), "*.rte", SearchOption.AllDirectories);
    Func<string, int> rank = f =>
    {
        var n = Path.GetFileNameWithoutExtension(f).ToLowerInvariant();
        if (n == "defaultmetric") return 0;
        if (n.Contains("defaultmetric")) return 1;
        if (n.Contains("metric") && !n.Contains("imperial")) return 2;
        return 9;
    };
    tpl10 = rtes.Where(f => rank(f) < 9).OrderBy(rank).ThenBy(f => f.Length).FirstOrDefault();
}
catch (Exception ex) { Dc.Note("template-scan: " + ex.Message); }

Document ndoc = resident10 ?? (File.Exists(modelPath10) ? app.OpenDocumentFile(modelPath10) : null);
if (ndoc == null && tpl10 != null)
{
    try { ndoc = app.NewProjectDocument(tpl10); }
    catch (Exception ex) { Dc.Note("template-open " + tpl10 + ": " + ex.Message); }
}
if (ndoc == null)
{
    tpl10 = null;
    ndoc = app.NewProjectDocument(UnitSystem.Metric);
}
Dc.Doc = ndoc;
Directory.CreateDirectory(Dc.OutDir);
if (String.IsNullOrEmpty(ndoc.PathName)) ndoc.SaveAs(modelPath10, new SaveAsOptions { OverwriteExistingFile = false });
Dc.Note("template: " + (tpl10 ?? "builtin-metric"));

// -- levels + grids ----------------------------------------------------------
int nLevels10 = 0, nGrids10 = 0;
Dc.Tx("DC levels + grids", d =>
{
    foreach (var s in plan10.Storeys)
    {
        Dc.Levels[s.Id] = Dc.FindOrCreateLevel(s.Name, s.Elevation);
        Dc.SetMark(Dc.Levels[s.Id], s.Id);
        nLevels10++;
    }
    Dc.Levels["lvl.roof"] = Dc.FindOrCreateLevel("Roof", plan10.Roof.Elevation);
    nLevels10++;

    foreach (var g in plan10.GridLines)
    {
        try
        {
            Line ln = g.Axis == "x"
                ? Line.CreateBound(Dc.P(g.Value, g.Start, 0.0), Dc.P(g.Value, g.End, 0.0))
                : Line.CreateBound(Dc.P(g.Start, g.Value, 0.0), Dc.P(g.End, g.Value, 0.0));
            var grid = new FilteredElementCollector(d).OfClass(typeof(Grid)).Cast<Grid>().FirstOrDefault(x=>x.Name==g.Label) ?? Grid.Create(d, ln);
            try { grid.Name = g.Label; }
            catch (Exception ex) { Dc.Note("grid-name " + g.Label + ": " + ex.Message); }
            Dc.IdMap[g.Id] = grid.Id;
            nGrids10++;
        }
        catch (Exception ex) { Dc.Note("grid-fail " + g.Id + ": " + ex.Message); }
    }
});

Directory.CreateDirectory(Dc.OutDir);
var sao10 = new SaveAsOptions { OverwriteExistingFile = true };
ndoc.Save();
foreach (var e in new FilteredElementCollector(ndoc).WhereElementIsNotElementType())
{
    if (e is MEPCurve) continue; // legacy run/route Marks may be inherited by unmarked segments
    if (e is FamilyInstance child && child.SuperComponent != null) continue;
    var mark=e.get_Parameter(BuiltInParameter.ALL_MODEL_MARK)?.AsString();
    if (String.IsNullOrEmpty(mark) || !Dc.Plan.Identities.ContainsKey(mark)) continue;
    if (Dc.IdMap.ContainsKey(mark)) throw new Exception("Duplicate Mark: "+mark);
    Dc.IdMap[mark]=e.Id;
    if(e is Wall wall) Dc.WallsById[mark]=wall;
}

$"10_setup ok: template={(tpl10 == null ? "builtin-metric" : Path.GetFileName(tpl10))}, {nLevels10} levels, {nGrids10} grids, saved {Path.Combine(Dc.OutDir, "demo-datacentre-01.rvt")}"
