import copy
import dataclasses
import importlib.util
import json
from pathlib import Path
import pytest
from dcbuild import layout, spec
from dcbuild.revit_payload import prepare

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def plan():
    return dataclasses.asdict(layout.resolve(spec.load()))


def test_payload_preserves_plan_and_contract(plan):
    original = copy.deepcopy(plan)
    payload = prepare(plan)
    assert plan == original
    assert len(payload['cameras']) == 45
    assert len({c['global_id'] for c in payload['cameras']}) == 45
    for c in payload['cameras']:
        assert c['level'] in {s['id'] for s in payload['storeys']}
        sensor = json.loads(c['contract']['Sensors'])[0]
        assert sensor['drivers']['aeco:cctvSensor:pan'] == c['pan']
        assert sensor['drivers']['aeco:cctvSensor:targetDensity'] == c['target_density']
        assert sensor['presets'] == c['presets']
        assert sensor['tour'] == c['tour']
        assert c['native_target_density'] == c['target_density'] == 250


def test_native_density_fallback_preserves_authored_contract(plan):
    plan['cameras'][0]['target_density'] = 0
    payload = prepare(plan)
    camera = payload['cameras'][0]
    assert camera['native_target_density'] == 250
    assert camera['target_density'] == plan['cameras'][0]['target_density'] == 0
    assert json.loads(camera['contract']['Sensors'])[0]['drivers']['aeco:cctvSensor:targetDensity'] == 0
    plan['cameras'][0]['target_density'] = 180
    assert prepare(plan)['cameras'][0]['native_target_density'] == 180


@pytest.mark.parametrize('density', [0, -1, float('nan'), float('inf'), 62.5, True])
def test_native_type_density_refused(plan, density):
    plan['security']['camera_types']['dome_5mp']['target_density'] = density
    with pytest.raises(ValueError, match='positive integer'):
        prepare(plan)


def test_status_payload_covers_all_authored_products(plan):
    status = prepare(plan)['revit_status']
    assert status['value'] == 'NEW'
    assert {'OST_SecurityDevices', 'OST_Walls', 'OST_Doors', 'OST_StructuralColumns',
            'OST_ElectricalEquipment', 'OST_MechanicalEquipment', 'OST_SpecialityEquipment',
            'OST_GenericModel', 'OST_Floors', 'OST_Rooms', 'OST_CableTray',
            'OST_PipeCurves', 'OST_PipeFitting'} <= set(status['categories'])


@pytest.mark.parametrize('field,value', [('pan', float('nan')), ('target_density', 62.5),
                                         ('focal_length', 500), ('global_id', 'wrong'), ('roll', 20)])
def test_payload_refuses_unrepresentable_camera(plan, field, value):
    plan['cameras'][0][field] = value
    with pytest.raises(ValueError):
        prepare(plan)


def test_duplicate_identity_refused(plan):
    plan['cameras'].append(copy.deepcopy(plan['cameras'][0]))
    with pytest.raises(ValueError, match='Duplicate'):
        prepare(plan)


def transport():
    from dcbuild.revit_runtime import setup
    setup()
    from usdaeco_revit import transport as module
    return module


def test_transport_does_not_replay_ambiguous_mutation(tmp_path):
    calls=[]
    def request(method, url, payload, timeout):
        calls.append(method)
        if method == 'GET':
            return {}
        raise TimeoutError('unknown native outcome')
    c=transport().Client('http://repl.example', request=request, lock_directory=tmp_path)
    with pytest.raises(transport().ReplStopped, match='unknown native outcome'):
        c.evaluate('mutation')
    with pytest.raises(RuntimeError, match='stopped'):
        c.evaluate('mutation')
    assert calls == ['GET','POST']


def test_transport_pages_checked(tmp_path):
    import base64,hashlib
    body=b'large receipt '*600
    offset=0
    calls=[]
    def request(method,url,payload,timeout):
        nonlocal offset
        calls.append(method)
        if method=='GET': return {}
        code=payload['code']
        if 'var phaseBytes' in code:
            return {'result': json.dumps({'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()})}
        if 'released' in code: return {'result':'released'}
        page=body[offset:offset+2400];offset+=len(page)
        return {'result':base64.b64encode(page).decode()}
    c=transport().Client('http://repl.example',request=request,lock_directory=tmp_path)
    assert c.phase('"receipt"') == body.decode()
    assert calls == ['GET','POST']*6


def test_live_launcher_preserves_source_arguments_and_exit_status(tmp_path, monkeypatch):
    import hashlib
    import types
    from revit import live
    source = tmp_path/'revit'
    package = source/'tools/usdaeco_revit/gates'
    package.mkdir(parents=True)
    runner = package/'cctv_revit.py'
    original = b"def main(args):\n    import json\n    from pathlib import Path\n    Path(args[args.index('--output')+1], 'arguments.json').write_text(json.dumps(args))\n    return 7\n"
    runner.write_bytes(original)
    module = types.ModuleType('usdaeco_revit.gates.cctv_revit')
    exec(original, module.__dict__)
    module.__file__ = str(runner)
    module.ReplClient = transport().ReplClient
    pin = {'repo': 'usdaeco-revit', 'ref': 'v0.1.0', 'revision': 'a'*40}
    monkeypatch.setattr(live, 'setup', lambda **kwargs: (source, pin))
    def imported(name):
        assert name == 'usdaeco_revit.gates.cctv_revit'
        return module
    monkeypatch.setattr(live.importlib, 'import_module', imported)
    output = tmp_path/'evidence'
    result = live.main(['--output', str(output), '--stage', 'seed.usda', '--cases', 'C-create'])
    assert result == 7
    assert json.loads((output/'arguments.json').read_text()) == [
        '--case-set', 'datacentre', '--output', str(output),
        '--stage', 'seed.usda', '--cases', 'C-create']
    assert runner.read_bytes() == original
    retained, = output.glob('runner-*')
    assert (retained/'released.py').read_bytes() == original
    assert json.loads((retained/'provenance.json').read_text()) == {
        'releasedSha256': hashlib.sha256(original).hexdigest(), 'changedAssertions': 0, **pin}
    assert not (retained/'adapted.py').exists()


class FakeEndpoint:
    """Protocol-level fake: uploads and paged replies exercise the real client."""
    def __init__(self, corrupt_upload=False):
        self.calls, self.phases, self.uploads = [], [], {}
        self.body, self.offset = b'', 0
        self.corrupt_upload = corrupt_upload

    def __call__(self, method, url, payload, timeout):
        import base64
        import hashlib
        import re
        previous = self.calls[-1][0] if self.calls else None
        self.calls.append((method, url, payload))
        if method == 'GET':
            assert url.endswith('/status')
            return {'busy': False}
        assert previous == 'GET'
        assert url.endswith('/eval')
        code = payload['code']
        target = re.search(r'System.IO.Path.Combine\("remote-work", "([^"/]+)"\)', code)
        if target:
            name = target.group(1)
            if 'new byte[0]' in code:
                self.uploads[name] = b''
                return {'result': 'created'}
            if 'FileMode.Append' in code:
                encoded = re.search(r'FromBase64String\("([^"]+)"\)', code).group(1)
                self.uploads[name] += base64.b64decode(encoded, validate=True)
                return {'result': 'appended'}
            assert 'HashData' in code
            return {'result': 'bad' if self.corrupt_upload else hashlib.sha256(self.uploads[name]).hexdigest()}
        if 'var phaseBytes' in code:
            self.phases.append(code)
            self.body = b'{"created":0,"updated":5}'
            self.offset = 0
            return {'result': json.dumps({'bytes': len(self.body), 'sha256': hashlib.sha256(self.body).hexdigest()})}
        if 'ToBase64String' in code:
            page = self.body[self.offset:self.offset+2400]
            self.offset += len(page)
            return {'result': base64.b64encode(page).decode()}
        return {'result': 'configured'}


def test_builder_update_through_shared_client(tmp_path, monkeypatch, plan):
    from functools import partial
    from revit import driver
    fake = FakeEndpoint()
    assert driver.Client is transport().Client
    monkeypatch.setattr(driver, 'Client', partial(transport().Client, request=fake, lock_directory=tmp_path/'locks'))
    path = tmp_path/'plan.json'; path.write_text(json.dumps(plan))
    args = ['--update', '--plan', str(path), '--endpoint', 'http://repl.example',
            '--workdir', 'remote-work', '--family-dir', 'camera-families']
    with pytest.raises(SystemExit) as stopped:
        driver.main([*args, '--dry-run'])
    assert stopped.value.code == 0
    assert fake.calls == []
    driver.main(args)
    assert len(fake.phases) == 13  # helpers, setup, parameters, nine camera batches, export
    assert sum('DcCameras.Run()' in code for code in fake.phases) == 9
    assert not any('DC containment' in code or 'DC piping' in code for code in fake.phases)
    assert set(fake.uploads) == {'build_plan.json', 'families.yaml', 'camera-psets.txt', 'shared-parameters.txt'}
    assert json.loads(fake.uploads['build_plan.json']) == json.loads(json.dumps(prepare(plan)))


def test_builder_corrupt_upload_stops_before_native_phases(tmp_path, monkeypatch, plan):
    from revit import driver
    fake = FakeEndpoint(corrupt_upload=True)
    client = transport().Client('http://repl.example', workdir='remote-work', request=fake, lock_directory=tmp_path/'locks')
    monkeypatch.setattr(driver, 'Client', lambda *args, **kwargs: client)
    path = tmp_path/'plan.json'; path.write_text(json.dumps(plan))
    with pytest.raises(transport().ReplStopped, match='Upload checksum mismatch'):
        driver.main(['--update', '--plan', str(path), '--endpoint', 'http://repl.example',
                     '--workdir', 'remote-work', '--family-dir', 'camera-families'])
    assert fake.phases == []
    calls = len(fake.calls)
    with pytest.raises(transport().ReplStopped):
        client.evaluate('mutation')
    assert len(fake.calls) == calls


@pytest.mark.parametrize('variant', ['floors', 'pod', 'clash', 'iris'])
def test_native_variant_refused(tmp_path, variant):
    from revit import driver
    plan = dataclasses.asdict(layout.resolve(spec.load(variant=variant)))
    path = tmp_path/'plan.json'; path.write_text(json.dumps(plan))
    with pytest.raises(SystemExit) as stopped:
        driver.main(['--update', '--dry-run', '--plan', str(path)])
    assert stopped.value.code == 1


def test_script_manifest_refuses_changed_missing_and_extra_sources(tmp_path, monkeypatch):
    import shutil
    from revit import driver
    shutil.copytree(ROOT/'revit/src', tmp_path/'src')
    monkeypatch.setattr(driver, 'SRC', str(tmp_path/'src'))
    driver.verify_pack()
    phase = tmp_path/'src/10_setup.csx'
    original = phase.read_bytes()
    phase.write_bytes(original+b'\n// changed\n')
    with pytest.raises(ValueError, match='manifest'):
        driver.verify_pack()
    phase.unlink()
    with pytest.raises(ValueError, match='manifest'):
        driver.verify_pack()
    phase.write_bytes(original)
    (tmp_path/'src/99_extra.csx').write_text('"extra"')
    with pytest.raises(ValueError, match='manifest'):
        driver.verify_pack()
