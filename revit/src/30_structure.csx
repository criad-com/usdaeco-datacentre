// 30_structure -- columns from plan.columns: stock concrete-square structural
// column family if available (duplicated to 400x400), else DirectShape box on
// the Structural Columns category. Mark = dc id.

var plan30 = Dc.LoadPlan();
Dc.RequireDoc();

int nCols30 = 0, nDs30 = 0;

Dc.Tx("DC structure", d =>
{
    var baseLvl = Dc.Levels["lvl.l0"];
    Level roofLvl;
    if (!Dc.Levels.TryGetValue("lvl.roof", out roofLvl)) roofLvl = null;

    var stock = Dc.FindSymbol(BuiltInCategory.OST_StructuralColumns, new[]
    {
        "M_Concrete-Square-Column", "Concrete-Square-Column",
        "M_Concrete-Rectangular-Column", "Concrete-Rectangular-Column",
    });
    FamilySymbol colSym = null;
    if (stock != null)
    {
        try
        {
            colSym = stock.Duplicate("DC 400 x 400mm") as FamilySymbol;
            foreach (var pn in new[] { "b", "h" })
            {
                var p = colSym.LookupParameter(pn);
                if (p != null && !p.IsReadOnly) p.Set(Dc.M(0.4));
            }
        }
        catch (Exception ex) { Dc.Note("col-type-dup: " + ex.Message); colSym = stock; }
        Dc.Activate(colSym);
        Dc.Note("col-family: " + colSym.FamilyName + "/" + colSym.Name);
    }
    else Dc.Note("col-family-miss: DirectShape fallback for all columns");

    foreach (var c in plan30.Columns)
    {
        if(Dc.IdMap.ContainsKey(c.Id)) { nCols30++; continue; }
        bool placed = false;
        if (colSym != null)
        {
            try
            {
                var fi = d.Create.NewFamilyInstance(Dc.P(c.Pos[0], c.Pos[1], 0.0), colSym, baseLvl,
                    Autodesk.Revit.DB.Structure.StructuralType.Column);
                if (roofLvl != null)
                {
                    var topLvlP = fi.get_Parameter(BuiltInParameter.FAMILY_TOP_LEVEL_PARAM);
                    if (topLvlP != null && !topLvlP.IsReadOnly) topLvlP.Set(roofLvl.Id);
                    var topOffP = fi.get_Parameter(BuiltInParameter.FAMILY_TOP_LEVEL_OFFSET_PARAM);
                    if (topOffP != null && !topOffP.IsReadOnly) topOffP.Set(Dc.M(c.Height) - roofLvl.Elevation);
                }
                Dc.SetMark(fi, c.Id);
                Dc.IdMap[c.Id] = fi.Id;
                nCols30++;
                placed = true;
            }
            catch (Exception ex) { Dc.Note("col-fam-fail " + c.Id + ": " + ex.Message); }
        }
        if (!placed)
        {
            Dc.DsBox(BuiltInCategory.OST_StructuralColumns, c.Id,
                      c.Pos[0], c.Pos[1], 0.0, c.Size, c.Size, c.Height, 0.0);
            nDs30++;
        }
    }
});

$"30_structure ok: {nCols30} column instances, {nDs30} directshape columns, log: {Dc.LogTail(6)}"
