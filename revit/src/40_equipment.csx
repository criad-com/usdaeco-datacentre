// 40_equipment -- every plan.equipment item: candidate family per
// AECO_REVIT_WORKDIR / families.yaml (uploaded by driver.py; simple block-style subset
// parsed here), else DirectShape box/cylinder of e.size at e.pos rotated
// e.rot, category per docs/conventions.md. Racks: DirectShape boxes on
// Specialty Equipment. Mark = dc id everywhere.
using System.IO;

var plan40 = Dc.LoadPlan();
Dc.RequireDoc();

// -- families.yaml (block style only: "cls:" then "  - Family Name") ---------
var famMap40 = new Dictionary<string, List<string>>();
try
{
    if (File.Exists(Dc.FamiliesPath))
    {
        string cur = null;
        foreach (var raw in File.ReadAllLines(Dc.FamiliesPath))
        {
            var line = raw.Split('#')[0].TrimEnd();
            if (line.Trim().Length == 0) continue;
            if (!char.IsWhiteSpace(line[0]) && line.EndsWith(":"))
            {
                cur = line.Substring(0, line.Length - 1).Trim();
                famMap40[cur] = new List<string>();
            }
            else if (cur != null && line.TrimStart().StartsWith("- "))
            {
                var item = line.TrimStart().Substring(2).Trim().Trim('"', '\'');
                if (item.Length > 0) famMap40[cur].Add(item);
            }
        }
        Dc.Note("families-yaml: " + famMap40.Count + " classes mapped");
    }
    else Dc.Note("families-yaml missing at " + Dc.FamiliesPath + " -- DirectShape for everything");
}
catch (Exception ex) { Dc.Note("families-yaml parse: " + ex.Message); }

// -- spec class -> Revit category (docs/conventions.md table) ----------------
var catByCls40 = new Dictionary<string, BuiltInCategory>
{
    ["utility_intake"] = BuiltInCategory.OST_GenericModel,
    ["rmu"] = BuiltInCategory.OST_ElectricalEquipment,
    ["msb"] = BuiltInCategory.OST_ElectricalEquipment,
    ["uob"] = BuiltInCategory.OST_ElectricalEquipment,
    ["pdu"] = BuiltInCategory.OST_ElectricalEquipment,
    ["hdb"] = BuiltInCategory.OST_ElectricalEquipment,
    ["mcc"] = BuiltInCategory.OST_ElectricalEquipment,
    ["transformer"] = BuiltInCategory.OST_ElectricalEquipment,
    ["generator"] = BuiltInCategory.OST_ElectricalEquipment,
    ["ups"] = BuiltInCategory.OST_ElectricalEquipment,
    ["battery"] = BuiltInCategory.OST_ElectricalEquipment,
    ["fuel_tank"] = BuiltInCategory.OST_MechanicalEquipment,
    ["dry_cooler"] = BuiltInCategory.OST_MechanicalEquipment,
    ["chiller"] = BuiltInCategory.OST_MechanicalEquipment,
    ["pump"] = BuiltInCategory.OST_MechanicalEquipment,
    ["buffer_tank"] = BuiltInCategory.OST_MechanicalEquipment,
    ["dosing"] = BuiltInCategory.OST_MechanicalEquipment,
    ["heat_exchanger"] = BuiltInCategory.OST_MechanicalEquipment,
    ["cdu"] = BuiltInCategory.OST_MechanicalEquipment,
    ["crah"] = BuiltInCategory.OST_MechanicalEquipment,
    ["ahu"] = BuiltInCategory.OST_MechanicalEquipment,
    ["rack"] = BuiltInCategory.OST_SpecialityEquipment,
    ["carrier_rack"] = BuiltInCategory.OST_SpecialityEquipment,
    ["ava"] = BuiltInCategory.OST_SecurityDevices,
    ["iris"] = BuiltInCategory.OST_SecurityDevices,
};

int nFam40 = 0, nDs40 = 0, nRacks40 = 0;
var symCache40 = new Dictionary<string, FamilySymbol>();
var symMiss40 = new HashSet<string>();

Dc.Tx("DC equipment", d =>
{
    foreach (var e in plan40.Equipment)
    {
        if(Dc.IdMap.ContainsKey(e.Id)) { nFam40++; continue; }
        BuiltInCategory cat;
        if (!catByCls40.TryGetValue(e.Cls, out cat))
        {
            cat = BuiltInCategory.OST_GenericModel;
            Dc.NoteOnce("cls-" + e.Cls, "unknown class " + e.Cls + " -> GenericModel");
        }

        FamilySymbol sym = null;
        if (!symMiss40.Contains(e.Cls) && !symCache40.TryGetValue(e.Cls, out sym))
        {
            List<string> cands;
            if (famMap40.TryGetValue(e.Cls, out cands) && cands.Count > 0)
            {
                sym = Dc.FindSymbol(null, cands);
                if (sym != null) { symCache40[e.Cls] = sym; Dc.Note("fam-hit " + e.Cls + " -> " + sym.FamilyName + "/" + sym.Name); }
                else { symMiss40.Add(e.Cls); Dc.Note("fam-miss " + e.Cls + " -> DirectShape"); }
            }
            else symMiss40.Add(e.Cls);
        }

        bool placed = false;
        if (sym != null)
        {
            try
            {
                Dc.Activate(sym);
                var lvl = Dc.LevelFor(e.Pos[2]);
                var fi = d.Create.NewFamilyInstance(Dc.P(e.Pos[0], e.Pos[1], e.Pos[2]), sym, lvl,
                    Autodesk.Revit.DB.Structure.StructuralType.NonStructural);
                if (Math.Abs(e.Rot) > 1e-9)
                {
                    var axis = Line.CreateBound(Dc.P(e.Pos[0], e.Pos[1], 0.0), Dc.P(e.Pos[0], e.Pos[1], 10.0));
                    ElementTransformUtils.RotateElement(d, fi.Id, axis, e.Rot * Math.PI / 180.0);
                }
                Dc.SetMark(fi, e.Id);
                Dc.IdMap[e.Id] = fi.Id;
                nFam40++;
                placed = true;
            }
            catch (Exception ex) { Dc.Note("equip-fam-fail " + e.Id + ": " + ex.Message + " -- DirectShape"); }
        }
        if (!placed)
        {
            if (e.Shape == "cylinder")
                Dc.DsCylinder(cat, e.Id, e.Pos[0], e.Pos[1], e.Pos[2], e.Size[0], e.Size[2]);
            else
                Dc.DsBox(cat, e.Id, e.Pos[0], e.Pos[1], e.Pos[2], e.Size[0], e.Size[1], e.Size[2], e.Rot);
            nDs40++;
        }
    }

    // -- racks (DirectShape v1; footprint centre, bottom at hall FFL 0) ------
    foreach (var r in plan40.Racks)
    {
        if(Dc.IdMap.ContainsKey(r.Id)) { nRacks40++; continue; }
        Dc.DsBox(BuiltInCategory.OST_SpecialityEquipment, r.Id,
                  r.Pos[0], r.Pos[1], 0.0, r.Size[0], r.Size[1], r.Size[2], 0.0);
        nRacks40++;
    }
});

$"40_equipment ok: {nFam40} family instances, {nDs40} directshape equipment, {nRacks40} racks, log: {Dc.LogTail(14)}"
