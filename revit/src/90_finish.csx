// Save the owned background model and publish only a successful IFC4x3 export.
Dc.RequireDoc();
var d90=Dc.Doc;
if(String.Equals(uiapp.ActiveUIDocument?.Document?.PathName,d90.PathName,StringComparison.OrdinalIgnoreCase)) throw new Exception("Refusing foreground document");
Dc.Tx("DC export preparation",d=>
{
    d.Regenerate();
    foreach(var kv in Dc.IdMap)
    {
        var e=d.GetElement(kv.Value);
        if(e!=null && !(e is Grid) && Dc.Plan.Identities.ContainsKey(kv.Key)) Dc.SetMark(e,kv.Key);
    }
});
d90.Save();
var options90=new IFCExportOptions
{
    FileVersion=IFCVersion.IFC4x3, ExportBaseQuantities=true,
    WallAndColumnSplitting=false, SpaceBoundaryLevel=1
};
options90.AddOption("ExportIFCCommonPropertySets","true");
options90.AddOption("ExportInternalRevitPropertySets","true");
options90.AddOption("ExportUserDefinedPsets","true");
options90.AddOption("ExportUserDefinedPsetsFileName",Path.Combine(Dc.OutDir,"camera-psets.txt"));
options90.AddOption("StoreIFCGUID","true");
options90.AddOption("ExportRoomsInView","true");
var temp90=Path.Combine(Dc.OutDir,"export-pending");
Directory.CreateDirectory(temp90);
Dc.Tx("DC IFC4x3 export",d=>
{
    if(!d.Export(temp90,"demo-datacentre-01-revit.ifc",options90)) throw new Exception("IFC4x3 export returned false");
});
File.Move(Path.Combine(temp90,"demo-datacentre-01-revit.ifc"),Path.Combine(Dc.OutDir,"demo-datacentre-01-revit.ifc"),true);
d90.Save();
var counts90=new FilteredElementCollector(d90).WhereElementIsNotElementType().Where(e=>e.Category!=null)
    .GroupBy(e=>e.Category.Name).OrderBy(g=>g.Key).ToDictionary(g=>g.Key,g=>g.Count());
File.WriteAllText(Path.Combine(Dc.OutDir,"native-diagnostics.json"),JsonSerializer.Serialize(new{warnings=Dc.Log,categories=counts90}));
JsonSerializer.Serialize(new{phase="90_finish",ifc="IFC4X3",marked=Dc.IdMap.Count,categories=counts90,diagnostics=Dc.Log.Count})
