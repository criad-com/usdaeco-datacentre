{
  description = "Generated demo data centre and published USD variants";
  inputs = {
    toolchain.url = "github:criad-com/usdaeco-toolchain?ref=v0.3.9";
    validation_core.url = "github:criad-com/usdaeco-core?ref=v0.9.2";
    validation_core.flake = false;
    revit.url = "github:criad-com/usdaeco-revit?ref=v0.1.2";
    revit.flake = false;
    sync.url = "github:criad-com/usdaeco-sync?ref=v0.5.2";
    sync.flake = false;
    # Frozen generation fixtures, separate from the direct train URL pins.
    # Public GitHub attributes retain ordinary --override-input support.
    core = {
      type = "github";
      owner = "criad-com";
      repo = "usdaeco-core";
      ref = "v0.8.4";
      flake = false;
    };
    ifc = {
      type = "github";
      owner = "criad-com";
      repo = "usdaeco-ifc";
      ref = "v0.1.0";
      flake = false;
    };
    nixpkgs.follows = "toolchain/nixpkgs";
  };
  outputs = { self, nixpkgs, toolchain, core, validation_core, ifc, revit, sync }:
    let
      each = nixpkgs.lib.genAttrs [ "aarch64-darwin" "x86_64-linux" ];
      make = system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          kit = toolchain.lib.forSystem system;
          python = pkgs.python3.withPackages (ps: [
            kit.usdPython ps.numpy ps.pytest ps.packaging ps.pydantic ps.pyyaml ps.pillow ps.ifcopenshell
          ]);
          setup = ''
            export AECO_VALIDATION_CORE_ROOT=${validation_core}
            export AECO_CORE_ROOT=${core}
            export AECO_IFC_ROOT=${ifc}
            export AECO_REVIT_ROOT=${revit}
            export AECO_SYNC_ROOT=${sync}
            export AECO_TOOLCHAIN_ROOT=${toolchain}
            export USDRECORD=${kit.usd-dev}/bin/usdrecord
          '';
          dcbuild = pkgs.writeShellApplication {
            name = "dcbuild";
            runtimeInputs = [ python pkgs.git kit.usd-dev ];
            text = setup + ''
              env -u PYTHONPATH ${python}/bin/python ${self}/scripts/dcbuild.py "$@"
            '';
          };
          check = pkgs.runCommand "usdaeco-datacentre-check" {
            nativeBuildInputs = [ python pkgs.git kit.usd-dev ];
          } (setup + ''
            cp -R ${self} source
            chmod -R u+w source
            cd source
            env -u PYTHONPATH PYTHONPATH=${validation_core}:$PWD ${python}/bin/python check.py
            mkdir -p "$out"
            cp out/check.json "$out/"
          '');
        in { inherit pkgs python setup dcbuild check; };
    in {
      packages = each (system: { default = (make system).dcbuild; });
      apps = each (system: {
        default = { type = "app"; program = "${(make system).dcbuild}/bin/dcbuild"; };
      });
      checks = each (system: { data = (make system).check; });
      devShells = each (system: let p = make system; in {
        default = p.pkgs.mkShell {
          packages = [ p.python p.dcbuild ];
          shellHook = p.setup + "unset PYTHONPATH";
        };
      });
    };
}
