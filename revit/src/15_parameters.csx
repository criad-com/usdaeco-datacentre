// Bind neutral contract parameters only in the owned project; restore app state.
Dc.RequireDoc();
string previousShared15=app.SharedParametersFilename;
try
{
    app.SharedParametersFilename=Path.Combine(Dc.OutDir,"shared-parameters.txt");
    var file15=app.OpenSharedParameterFile();
    if(file15==null) throw new Exception("Shared parameter definitions unavailable");
    Dc.Tx("DC contract parameters",d=>
    {
        var cameraCats=app.Create.NewCategorySet();
        cameraCats.Insert(d.Settings.Categories.get_Item(BuiltInCategory.OST_SecurityDevices));
        foreach(Definition definition in file15.Groups.First().Definitions)
        {
            if (Dc.Full && definition.Name != "Status") continue;
            if(definition.Name=="Status")
            {
                var statusCats=app.Create.NewCategorySet();
                foreach(var name in Dc.Plan.Status.GetProperty("categories").EnumerateArray())
                    statusCats.Insert(d.Settings.Categories.get_Item(Enum.Parse<BuiltInCategory>(name.GetString())));
                Definition existing=null;
                var iterator=d.ParameterBindings.ForwardIterator();
                while(iterator.MoveNext())
                {
                    if(iterator.Key.Name!="Status") continue;
                    if(!(iterator.Current is InstanceBinding oldBinding) || iterator.Key.GetDataType()!=SpecTypeId.String.Text)
                        throw new Exception("Existing Status must be an instance text parameter");
                    existing=iterator.Key;
                    foreach(Category category in oldBinding.Categories) statusCats.Insert(category);
                    break;
                }
                var statusBinding=app.Create.NewInstanceBinding(statusCats);
                bool bound=existing==null ? d.ParameterBindings.Insert(definition,statusBinding,GroupTypeId.IdentityData)
                    : d.ParameterBindings.ReInsert(existing,statusBinding,GroupTypeId.IdentityData);
                if(!bound) throw new Exception("Status binding refused");
                Dc.StatusBound=true;
                continue;
            }
            if(d.ParameterBindings.Contains(definition)) continue;
            bool onType=definition.Name.StartsWith("AecoCctvType");
            Binding binding=onType ? (Binding)app.Create.NewTypeBinding(cameraCats) : app.Create.NewInstanceBinding(cameraCats);
            if(!d.ParameterBindings.Insert(definition,binding,GroupTypeId.IdentityData)) throw new Exception("Parameter binding refused: "+definition.Name);
        }
    });
}
finally {app.SharedParametersFilename=previousShared15;}
"15_parameters ok"
