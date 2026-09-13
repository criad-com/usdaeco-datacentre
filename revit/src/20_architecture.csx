// 20_architecture -- walls (typed per plan kind), doors (family or Opening
// fallback), floors/roofs/pads from plan.slabs (incl. void loops). Everything
// Marked with its dc id; wall elements tracked for door hosting.

var plan20 = Dc.LoadPlan();
Dc.RequireDoc();

int nWalls20 = 0, nDoors20 = 0, nOpen20 = 0, nFloors20 = 0, nStairs20 = 0, nSkip20 = 0;

Dc.Tx("DC architecture", d =>
{
    // -- wall types per plan kind -------------------------------------------
    var wtByKind = new Dictionary<string, WallType>();
    foreach (var kv in plan20.WallTypes)
        wtByKind[kv.Key] = Dc.ResolveWallType(kv.Key, kv.Value.Thickness);

    // -- walls ---------------------------------------------------------------
    foreach (var w in plan20.Walls)
    {
        try
        {
            if(Dc.IdMap.ContainsKey(w.Id)) { nWalls20++; continue; }
            var lvl = Dc.Levels[w.Storey];
            WallType wt;
            if (!wtByKind.TryGetValue(w.Kind, out wt) || wt == null)
            {
                Dc.Note("wall-skip " + w.Id + ": no wall type for kind " + w.Kind);
                nSkip20++;
                continue;
            }
            var line = Line.CreateBound(Dc.P(w.P1[0], w.P1[1], 0.0), Dc.P(w.P2[0], w.P2[1], 0.0));
            var wall = Wall.Create(d, line, wt.Id, lvl.Id, Dc.M(w.Height), 0.0, false, false);
            if (Dc.Full)
            {
                WallUtils.DisallowWallJoinAtEnd(wall, 0);
                WallUtils.DisallowWallJoinAtEnd(wall, 1);
            }
            Dc.SetMark(wall, w.Id);
            Dc.ExportClass(wall,"IfcWall",w.Kind == "internal" ? "PARTITIONING" : "SOLIDWALL");
            Dc.WallsById[w.Id] = wall;
            Dc.IdMap[w.Id] = wall.Id;
            nWalls20++;
        }
        catch (Exception ex) { if (Dc.Full) throw; Dc.Note("wall-fail " + w.Id + ": " + ex.Message); nSkip20++; }
    }
    d.Regenerate();

    // -- doors ---------------------------------------------------------------
    var doorSyms = new FilteredElementCollector(d).OfClass(typeof(FamilySymbol))
        .OfCategory(BuiltInCategory.OST_Doors).Cast<FamilySymbol>().ToList();
    Func<FamilySymbol, double> symWidth = s =>
    {
        var p = s.get_Parameter(BuiltInParameter.DOOR_WIDTH) ?? s.get_Parameter(BuiltInParameter.FAMILY_WIDTH_PARAM);
        return (p != null && p.StorageType == StorageType.Double) ? p.AsDouble() : -1.0;
    };
    Dc.Note("door-symbols: " + doorSyms.Count + " in template");

    foreach (var door in plan20.Doors)
    {
        if(Dc.IdMap.ContainsKey(door.Id)) { nDoors20++; continue; }
        Wall host;
        if (!Dc.WallsById.TryGetValue(door.WallId, out host))
        {
            Dc.Note("door-nohost " + door.Id + " (wall " + door.WallId + ")");
            nSkip20++;
            continue;
        }
        var lvl = Dc.Levels[door.Storey];
        double zBase = Dc.StoreyElev[door.Storey];
        bool placed = false;

        if (door.Kind != "roller" && doorSyms.Count > 0)
        {
            bool wantDouble = door.Kind == "double";
            double target = Dc.M(door.Width);
            var sym = doorSyms.OrderBy(s =>
            {
                double score = Math.Abs(symWidth(s) - target);
                bool isDouble = s.FamilyName.ToLowerInvariant().Contains("double");
                if (wantDouble != isDouble) score += Dc.M(0.45);   // prefer matching leaf count
                return score;
            }).First();
            try
            {
                string typeName="DC door "+door.Kind+" "+door.Width+" x "+door.Height;
                sym=doorSyms.FirstOrDefault(s=>s.Name==typeName) ?? (FamilySymbol)sym.Duplicate(typeName);
                if(!doorSyms.Any(s=>s.Id==sym.Id)) doorSyms.Add(sym);
                foreach(var item in new[]{new KeyValuePair<BuiltInParameter,double>(BuiltInParameter.DOOR_WIDTH,door.Width),new KeyValuePair<BuiltInParameter,double>(BuiltInParameter.DOOR_HEIGHT,door.Height)})
                {
                    var parameter=sym.get_Parameter(item.Key);
                    if(parameter!=null&&!parameter.IsReadOnly) parameter.Set(Dc.M(item.Value));
                }
                Dc.Activate(sym);
                var pt = Dc.P(door.Pos[0], door.Pos[1], zBase);
                var fi = d.Create.NewFamilyInstance(pt, sym, host, lvl,
                    Autodesk.Revit.DB.Structure.StructuralType.NonStructural);
                // flex instance size if the family allows it
                var wp = fi.LookupParameter("Width");
                if (wp != null && !wp.IsReadOnly) { try { wp.Set(Dc.M(door.Width)); } catch { } }
                var hp = fi.LookupParameter("Height");
                if (hp != null && !hp.IsReadOnly) { try { hp.Set(Dc.M(door.Height)); } catch { } }
                double actual = symWidth(fi.Symbol);
                if (actual > 0 && Math.Abs(actual - target) > Dc.M(0.05))
                    Dc.Note("door-size-sub " + door.Id + ": " + fi.Symbol.FamilyName + "/" + fi.Symbol.Name
                             + " " + Dc.Mm(actual).ToString("0") + "mm vs plan " + (door.Width * 1000).ToString("0") + "mm");
                Dc.SetMark(fi, door.Id);
                Dc.ExportClass(fi,"IfcDoor","DOOR");
                Dc.IdMap[door.Id] = fi.Id;
                nDoors20++;
                placed = true;
            }
            catch (Exception ex) { Dc.Note("door-fam-fail " + door.Id + ": " + ex.Message + " -- opening fallback"); }
        }

        if (!placed)
        {
            try
            {
                var wpl = plan20.Walls.First(x => x.Id == door.WallId);
                double dx = wpl.P2[0] - wpl.P1[0], dy = wpl.P2[1] - wpl.P1[1];
                double len = Math.Sqrt(dx * dx + dy * dy);
                double ux = dx / len, uy = dy / len, hw = door.Width / 2.0;
                var pA = Dc.P(door.Pos[0] - ux * hw, door.Pos[1] - uy * hw, zBase);
                var pB = Dc.P(door.Pos[0] + ux * hw, door.Pos[1] + uy * hw, zBase + door.Height);
                var op = d.Create.NewOpening(host, pA, pB);
                double rotation=Math.Atan2(uy,ux)*180/Math.PI;
                var leaf=Dc.DsBox(BuiltInCategory.OST_Doors,door.Id,door.Pos[0],door.Pos[1],zBase,door.Width,0.06,door.Height,rotation);
                Dc.ExportClass(leaf,"IfcDoor",door.Kind == "roller" ? "GATE" : "DOOR");
                var exportAs=leaf.LookupParameter("Export to IFC As");
                if(exportAs!=null&&!exportAs.IsReadOnly) exportAs.Set("IfcDoor");
                nDoors20++;
                Dc.Note("door-as-directshape-with-opening " + door.Id + " (" + door.Kind + " " + (door.Width * 1000).ToString("0") + "mm)");
                nOpen20++;
            }
            catch (Exception ex) { Dc.Note("door-opening-fail " + door.Id + ": " + ex.Message); nSkip20++; }
        }
    }

    // -- floors / roofs / pads ----------------------------------------------
    var floorTypeId = d.GetDefaultElementTypeId(ElementTypeGroup.FloorType);
    if (floorTypeId == null || floorTypeId == ElementId.InvalidElementId)
    {
        var ft = new FilteredElementCollector(d).OfClass(typeof(FloorType)).Cast<FloorType>().FirstOrDefault();
        floorTypeId = ft != null ? ft.Id : null;
    }
    if (floorTypeId == null)
    {
        Dc.Note("floor-type-none: skipping all slabs");
    }
    else
    {
        Func<double, double, double, double, double, CurveLoop> rect = (x, y, w, dd, z) =>
        {
            var lp = new CurveLoop();
            lp.Append(Line.CreateBound(Dc.P(x, y, z), Dc.P(x + w, y, z)));
            lp.Append(Line.CreateBound(Dc.P(x + w, y, z), Dc.P(x + w, y + dd, z)));
            lp.Append(Line.CreateBound(Dc.P(x + w, y + dd, z), Dc.P(x, y + dd, z)));
            lp.Append(Line.CreateBound(Dc.P(x, y + dd, z), Dc.P(x, y, z)));
            return lp;
        };
        foreach (var s in plan20.Slabs)
        {
            try
            {
                if(Dc.IdMap.ContainsKey(s.Id)) { nFloors20++; continue; }
                var outer = rect(s.X, s.Y, s.W, s.D, s.TopElevation);
                if (s.Outline != null)
                {
                    outer = new CurveLoop();
                    for (int i=0; i<s.Outline.Count; i++)
                    {
                        var a=s.Outline[i]; var b=s.Outline[(i+1)%s.Outline.Count];
                        outer.Append(Line.CreateBound(Dc.P(a[0],a[1],s.TopElevation),Dc.P(b[0],b[1],s.TopElevation)));
                    }
                }
                var loops = new List<CurveLoop> { outer };
                foreach (var v in s.InnerLoops ?? s.Voids) loops.Add(rect(v[0], v[1], v[2], v[3], s.TopElevation));
                var typeId = floorTypeId;
                if (Dc.Full)
                {
                    string typeName = "DC slab " + (s.Thickness*1000).ToString("0") + " mm";
                    var floorType = new FilteredElementCollector(d).OfClass(typeof(FloorType)).Cast<FloorType>()
                        .FirstOrDefault(t => t.Name == typeName);
                    if (floorType == null)
                    {
                        floorType = (FloorType)((FloorType)d.GetElement(floorTypeId)).Duplicate(typeName);
                        var compound = CompoundStructure.CreateSimpleCompoundStructure(new List<CompoundStructureLayer> {
                            new CompoundStructureLayer(Dc.M(s.Thickness), MaterialFunctionAssignment.Structure, ElementId.InvalidElementId) });
                        compound.EndCap = EndCapCondition.NoEndCap;
                        floorType.SetCompoundStructure(compound);
                    }
                    typeId = floorType.Id;
                }
                var lvl = Dc.LevelFor(s.TopElevation);
                var fl = Floor.Create(d, loops, typeId, lvl.Id);
                var off = fl.get_Parameter(BuiltInParameter.FLOOR_HEIGHTABOVELEVEL_PARAM);
                if (off != null && !off.IsReadOnly) off.Set(Dc.M(s.TopElevation) - lvl.Elevation);
                Dc.SetMark(fl, s.Id);
                Dc.ExportClass(fl,"IfcSlab",s.Kind == "roof" ? "ROOF" : s.Kind == "ground" ? "BASESLAB" : "FLOOR");
                Dc.IdMap[s.Id] = fl.Id;
                if (s.Kind == "roof") Dc.Note("roof-as-floor " + s.Id);
                if (s.Kind == "pad") Dc.NoteOnce("pad-as-floor", "pads authored as Floor elements");
                if (!Dc.Full) Dc.NoteOnce("floor-type-default",
                    "floors use the template default floor type; plan thicknesses not matched");
                nFloors20++;
            }
            catch (Exception ex) { if (Dc.Full) throw; Dc.Note("slab-fail " + s.Id + ": " + ex.Message); nSkip20++; }
        }
    }
    foreach (var stair in plan20.Stairs)
    {
        var loop = new CurveLoop();
        for (int i=0; i<stair.Profile.Count; i++)
        {
            var a=stair.Profile[i]; var b=stair.Profile[(i+1)%stair.Profile.Count];
            loop.Append(Line.CreateBound(Dc.P(stair.X,stair.Y+a[0],stair.Z+a[1]),
                                        Dc.P(stair.X,stair.Y+b[0],stair.Z+b[1])));
        }
        var body = GeometryCreationUtilities.CreateExtrusionGeometry(new List<CurveLoop>{loop},XYZ.BasisX,Dc.M(stair.Width));
        var native = DirectShape.CreateElement(d,new ElementId(BuiltInCategory.OST_Stairs));
        native.SetShape(new List<GeometryObject>{body});
        native.Name = "Office Stair";
        Dc.SetMark(native,stair.Id);
        Dc.ExportClass(native,"IfcStair","STRAIGHT_RUN_STAIR");
        Dc.IdMap[stair.Id] = native.Id;
        nStairs20++;
    }
    if (Dc.Full && (nSkip20 != 0 || plan20.ArchIds.Any(id => !Dc.IdMap.ContainsKey(id))))
        throw new Exception("Full architecture is incomplete; no partial package may be delivered");
});

$"20_architecture ok: {nWalls20} walls, {nDoors20} doors, {nOpen20} openings, {nFloors20} floors, {nStairs20} stairs, {nSkip20} skipped, log: {Dc.LogTail(12)}"
