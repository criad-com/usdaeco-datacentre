// Interior rooms use plan rectangles and native levels; yards remain outdoors.
Dc.RequireDoc();
int rooms25=0;
Dc.Tx("DC rooms",d=>
{
    var planType=new FilteredElementCollector(d).OfClass(typeof(ViewFamilyType)).Cast<ViewFamilyType>().First(v=>v.ViewFamily==ViewFamily.FloorPlan);
    foreach(var levelPlan in Dc.Plan.Storeys)
    {
        var level=Dc.Levels[levelPlan.Id];
        var view=new FilteredElementCollector(d).OfClass(typeof(ViewPlan)).Cast<ViewPlan>().FirstOrDefault(v=>!v.IsTemplate && v.GenLevel?.Id==level.Id)
            ?? ViewPlan.Create(d,planType.Id,level.Id);
        var sketch=SketchPlane.Create(d,Plane.CreateByNormalAndOrigin(XYZ.BasisZ,new XYZ(0,0,level.Elevation)));
        foreach(var space in Dc.Plan.Spaces.Where(s=>!s.External && s.Storey==levelPlan.Id))
        {
            var room=new FilteredElementCollector(d).OfCategory(BuiltInCategory.OST_Rooms).WhereElementIsNotElementType().Cast<Room>().FirstOrDefault(r=>r.Number==space.Id);
            if(room==null)
            {
                var corners=new[]{Dc.P(space.X,space.Y,levelPlan.Elevation),Dc.P(space.X+space.W,space.Y,levelPlan.Elevation),
                    Dc.P(space.X+space.W,space.Y+space.D,levelPlan.Elevation),Dc.P(space.X,space.Y+space.D,levelPlan.Elevation)};
                var curves=new CurveArray();
                for(int i=0;i<4;i++) curves.Append(Line.CreateBound(corners[i],corners[(i+1)%4]));
                d.Create.NewRoomBoundaryLines(sketch,curves,view);
                d.Regenerate();
                room=d.Create.NewRoom(level,new UV(Dc.M(space.X+space.W/2),Dc.M(space.Y+space.D/2)));
            }
            room.Number=space.Id; room.Name=space.Name;
            room.get_Parameter(BuiltInParameter.ROOM_UPPER_LEVEL).Set(level.Id);
            room.get_Parameter(BuiltInParameter.ROOM_UPPER_OFFSET).Set(Dc.M(space.Height));
            Dc.SetMark(room,space.Id); Dc.IdMap[space.Id]=room.Id;
            rooms25++;
        }
    }
    d.Regenerate();
    foreach(Room room in new FilteredElementCollector(d).OfCategory(BuiltInCategory.OST_Rooms).WhereElementIsNotElementType())
        if(room.Area<=0) throw new Exception("Room has no enclosed area: "+room.Number);
});
$"25_rooms ok: {rooms25} interior rooms"
