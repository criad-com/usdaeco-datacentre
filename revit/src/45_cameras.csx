// 45_cameras -- level-based Security Devices; repeat by Mark updates in place.
// The driver evaluates bounded batches; all input units are metres/degrees/mm.
public static class DcCameras
{
    static Dictionary<string,Tuple<Parameter,double>> Expected=new Dictionary<string,Tuple<Parameter,double>>();
    static Dictionary<string,Tuple<Parameter,string>> ExpectedText=new Dictionary<string,Tuple<Parameter,string>>();
    public static void Number(Element e, string name, double value)
    {
        var p=e.LookupParameter(name);
        if(p==null || p.IsReadOnly) throw new Exception("Required camera parameter unavailable: "+name);
        if(p.Definition.GetDataType()==SpecTypeId.Angle) value*=Math.PI/180.0;
        else if(p.Definition.GetDataType()==SpecTypeId.Length) value=Dc.M(value);
        if(p.StorageType==StorageType.Integer)
        {
            if(value!=Math.Truncate(value)) throw new Exception("Integer camera parameter cannot represent "+name);
            p.Set((int)value);
        }
        else p.Set(value);
        Expected[e.Id.Value+"|"+name]=Tuple.Create(p,value);
    }
    public static void Text(Element e,string name,string value)
    {
        var p=e.LookupParameter(name);
        if(p==null || p.IsReadOnly) throw new Exception("Required camera text unavailable: "+name);
        p.Set(value);
        ExpectedText[e.Id.Value+"|"+name]=Tuple.Create(p,value);
    }
    public static FamilySymbol Symbol(CameraP camera)
    {
        string path=Path.Combine(Dc.FamilyDir,camera.Family);
        if(!File.Exists(path)) throw new Exception("Camera family file missing: "+camera.Family);
        var family=new FilteredElementCollector(Dc.Doc).OfClass(typeof(Family)).Cast<Family>()
            .FirstOrDefault(f=>f.Name==Path.GetFileNameWithoutExtension(camera.Family));
        if(family==null && !Dc.Doc.LoadFamily(path,out family)) throw new Exception("Camera family load failed: "+camera.Family);
        var symbols=family.GetFamilySymbolIds().Select(id=>(FamilySymbol)Dc.Doc.GetElement(id)).ToList();
        string name="DC "+camera.Type;
        var symbol=symbols.FirstOrDefault(s=>s.Name==name);
        if(symbol==null)
        {
            var source=symbols.OrderByDescending(s=>s.LookupParameter("FOV Horizontal Maximum")?.AsDouble()??0)
                .ThenBy(s=>s.Name,StringComparer.Ordinal).First();
            symbol=(FamilySymbol)source.Duplicate(name);
        }
        if(symbol.Category.Id.Value!=(long)BuiltInCategory.OST_SecurityDevices) throw new Exception("Camera must be a Security Device");
        var cfg=Dc.Plan.Security.GetProperty("camera_types").GetProperty(camera.Type);
        foreach(var fields in new[]{new[]{"focal_range","FOV Focal Length Minimum","FOV Focal Length Maximum"},
                 new[]{"hfov_range","FOV Horizontal Maximum","FOV Horizontal Minimum"},
                 new[]{"vfov_range","FOV Vertical Maximum","FOV Vertical Minimum"},
                 new[]{"pixels","FOV Horizontal Resolution","FOV Vertical Resolution"}})
        {
            Number(symbol,fields[1],cfg.GetProperty(fields[0])[0].GetDouble());
            Number(symbol,fields[2],cfg.GetProperty(fields[0])[1].GetDouble());
        }
        Number(symbol,"PTZ",camera.Type=="ptz_4k"?1:0);
        Text(symbol,"Export Type to IFC As","IfcAudioVisualApplianceType");
        Text(symbol,"Type IFC Predefined Type","CAMERA");
        foreach(var kv in camera.TypeContract) Text(symbol,kv.Key=="Type"?"AecoCctvType":"AecoCctvType"+kv.Key,kv.Value);
        Dc.Activate(symbol);
        return symbol;
    }
    public static void Pose(FamilyInstance fi,string prefix,double pan,double tilt,double focal,double range,double density)
    {
        if(density<=0) throw new Exception("Native camera density must be positive");
        string panName=fi.LookupParameter(prefix+"Pan")!=null?prefix+"Pan":prefix+"Camera Rotation";
        string tiltName=fi.LookupParameter(prefix+"Tilt")!=null?prefix+"Tilt":prefix+"Camera Tilt";
        // Zero density leaves the nested family formulas stale, including radii.
        Number(fi,prefix+"Target Pixel Density",density);
        Number(fi,panName,pan); Number(fi,tiltName,tilt);
        Number(fi,prefix+"Desired Focal Length",focal);
        Number(fi,prefix+"Distance to Object",range);
    }
    static IEnumerable<FamilyInstance> Children(FamilyInstance parent)
    {
        foreach(var id in parent.GetSubComponentIds())
            if(Dc.Doc.GetElement(id) is FamilyInstance child)
            {
                yield return child;
                foreach(var nested in Children(child)) yield return nested;
            }
    }
    static void VerifyGuides(FamilyInstance camera,CameraP plan)
    {
        var guides=Children(camera).Where(c=>c.LookupParameter("Horizontal Angle")!=null).ToList();
        if(guides.Count==0) throw new Exception("Camera has no native FOV observations: "+plan.Id);
        foreach(var guide in guides)
        {
            double angle=guide.LookupParameter("Horizontal Angle").AsDouble();
            double pixels=guide.LookupParameter("Horizontal Res").AsInteger();
            double range=UnitUtils.ConvertFromInternalUnits(guide.LookupParameter("FOV Distance to Object").AsDouble(),UnitTypeId.Meters);
            if(!Double.IsFinite(angle) || angle<=0 || Math.Abs(range-plan.Range)>1e-6
                || guide.LookupParameter("T_Res_UD").AsInteger()!=plan.NativeTargetDensity)
                throw new Exception("Native FOV inputs differ: "+plan.Id);
            foreach(string band in new[]{"Det","Obs","Rec","Id","UD"})
            {
                double density=guide.LookupParameter("T_Res_"+band).AsInteger();
                double radius=UnitUtils.ConvertFromInternalUnits(guide.LookupParameter("RG_Length_"+band).AsDouble(),UnitTypeId.Meters);
                double expected=Math.Min(range,pixels/(2*angle*density));
                if(density<=0 || !Double.IsFinite(radius) || Math.Abs(radius-expected)>0.001)
                    throw new Exception("Native FOV radius differs after regeneration: "+plan.Id+" "+band);
            }
        }
    }
    public static string Run()
    {
        Dc.LoadPlan(); Dc.RequireDoc();
        int created=0,updated=0;
        Expected.Clear();
        ExpectedText.Clear();
        var existing=new FilteredElementCollector(Dc.Doc).OfCategory(BuiltInCategory.OST_SecurityDevices)
            .WhereElementIsNotElementType().OfType<FamilyInstance>().Where(f=>f.SuperComponent==null)
            .GroupBy(f=>f.get_Parameter(BuiltInParameter.ALL_MODEL_MARK)?.AsString()??"")
            .Where(g=>g.Key.StartsWith("sec.cam.")).ToDictionary(g=>g.Key,g=>g.ToList());
        if(existing.Any(kv=>kv.Value.Count!=1)) throw new Exception("Duplicate native camera Mark");
        Dc.Tx("DC camera batch",d=>
        {
            foreach(var c in Dc.Plan.Cameras.Skip(Dc.CameraStart).Take(Dc.CameraCount))
            {
                var symbol=Symbol(c); var level=Dc.Levels[c.Level];
                FamilyInstance fi;
                if(existing.ContainsKey(c.Id))
                {
                    fi=existing[c.Id].Single();
                    if(fi.LevelId!=level.Id) throw new Exception("Existing camera has a different level: "+c.Id);
                    if(fi.Symbol.Id!=symbol.Id) fi.Symbol=symbol;
                    updated++;
                }
                else { fi=d.Create.NewFamilyInstance(Dc.P(c.Pos[0],c.Pos[1],c.Pos[2]),symbol,level,StructuralType.NonStructural); created++; }
                d.Regenerate();
                var location=(LocationPoint)fi.Location;
                ElementTransformUtils.MoveElement(d,fi.Id,Dc.P(c.Pos[0],c.Pos[1],c.Pos[2])-location.Point);
                var frame=fi.GetTransform();
                double delta=c.DeviceRotation*Math.PI/180-Math.Atan2(frame.BasisX.Y,frame.BasisX.X);
                if(Math.Abs(delta)>1e-12) ElementTransformUtils.RotateElement(d,fi.Id,Line.CreateUnbound(location.Point,XYZ.BasisZ),delta);
                bool ptz=fi.LookupParameter("Preset 1")!=null;
                Pose(fi,ptz&&fi.LookupParameter("FOV Pan")==null?"FOV 1 ":"FOV ",c.Pan,c.Tilt,c.FocalLength,c.Range,c.NativeTargetDensity);
                if(fi.LookupParameter("Corridor Format")!=null) Number(fi,"Corridor Format",c.Roll==90?1:0);
                if(ptz)
                {
                    for(int n=1;n<=4;n++)
                    {
                        bool enabled=n<=c.PresetOrder.Count;
                        Number(fi,"Preset "+n,enabled?1:0);
                        Number(fi,"FOV "+n+" Target Pixel Density",c.NativeTargetDensity);
                        Number(fi,"FOV "+n+" Distance to Object",c.Range);
                        if(!enabled) continue;
                        var preset=c.Presets[c.PresetOrder[n-1]];
                        Pose(fi,"FOV "+n+" ",preset.GetProperty("pan").GetDouble(),preset.GetProperty("tilt").GetDouble(),
                            preset.GetProperty("focalLength").GetDouble(),c.Range,c.NativeTargetDensity);
                    }
                }
                Dc.SetMark(fi,c.Id); Dc.IdMap[c.Id]=fi.Id;
                Text(fi,"Export to IFC As","IfcAudioVisualAppliance"); Text(fi,"IFC Predefined Type","CAMERA");
                foreach(var kv in c.Contract) Text(fi,"AecoCctv"+kv.Key,kv.Value);
                d.Regenerate();
                if(((LocationPoint)fi.Location).Point.DistanceTo(Dc.P(c.Pos[0],c.Pos[1],c.Pos[2]))>Dc.M(0.001))
                    throw new Exception("Camera position differs after regeneration: "+c.Id);
                VerifyGuides(fi,c);
            }
            d.Regenerate();
            foreach(var pair in Expected)
            {
                var p=pair.Value.Item1; double expected=pair.Value.Item2;
                double actual=p.StorageType==StorageType.Integer?p.AsInteger():p.AsDouble();
                if(Math.Abs(actual-expected)>1e-9) throw new Exception("Camera parameter read-back differs after regeneration: "+p.Definition.Name+" "+actual+" vs "+expected);
            }
            foreach(var pair in ExpectedText)
                if(pair.Value.Item1.AsString()!=pair.Value.Item2) throw new Exception("Camera text read-back differs");
        });
        return JsonSerializer.Serialize(new{phase="45_cameras",created,updated,start=Dc.CameraStart,count=Dc.CameraCount});
    }
}
DcCameras.Run()
