// Read the owned native model for export handoff and repeat-phase comparison.
Dc.RequireDoc();
if(uiapp.ActiveUIDocument?.Document==Dc.Doc) throw new Exception("Refusing foreground document");
var auditRows=Dc.Plan.Cameras.Select(c=>
{
    var found=new FilteredElementCollector(Dc.Doc).OfCategory(BuiltInCategory.OST_SecurityDevices)
        .WhereElementIsNotElementType().OfType<FamilyInstance>().Where(f=>f.SuperComponent==null
            && f.get_Parameter(BuiltInParameter.ALL_MODEL_MARK)?.AsString()==c.Id).ToList();
    if(found.Count!=1) throw new Exception("Camera census differs: "+c.Id);
    var fi=found.Single(); var point=((LocationPoint)fi.Location).Point;
    string prefix=fi.LookupParameter("FOV Pan")!=null?"FOV ":"FOV 1 ";
    double pan=fi.LookupParameter(prefix+"Pan").AsDouble()*180/Math.PI;
    double tilt=fi.LookupParameter(prefix+"Tilt").AsDouble()*180/Math.PI;
    double focal=fi.LookupParameter(prefix+"Desired Focal Length").AsDouble();
    double range=fi.LookupParameter(prefix+"Distance to Object").AsDouble()*0.3048;
    double density=fi.LookupParameter(prefix+"Target Pixel Density").AsInteger();
    string guid=fi.get_Parameter(BuiltInParameter.IFC_GUID).AsString();
    if(point.DistanceTo(Dc.P(c.Pos[0],c.Pos[1],c.Pos[2]))>Dc.M(.001) || Math.Abs(pan-c.Pan)>1e-6
        || Math.Abs(tilt-c.Tilt)>1e-6 || Math.Abs(focal-c.FocalLength)>1e-6 || Math.Abs(range-c.Range)>1e-6
        || Math.Abs(density-c.TargetDensity)>1e-6 || guid!=c.GlobalId || fi.LevelId!=Dc.Levels[c.Level].Id)
        throw new Exception("Native camera parity differs: "+c.Id);
    return new{id=c.Id,uniqueId=fi.UniqueId,globalId=guid,level=c.Level,position=new[]{point.X*.3048,point.Y*.3048,point.Z*.3048},pan,tilt,focal,range,density};
}).ToArray();
File.WriteAllText(Path.Combine(Dc.OutDir,"native-cameras.json"),JsonSerializer.Serialize(auditRows));
JsonSerializer.Serialize(new{cameras=auditRows.Length,verified=auditRows.Length})
