"""Writer payloads for usdaeco-cctv-ifc/1.0; fixed SI/mm/degree units."""

CONTRACT = "usdaeco-cctv-ifc/1.0"


def type_payload(name, cfg):
    keys = {"focal_range": "focalRange", "hfov_range": "hfovRange", "vfov_range": "vfovRange",
            "pixels": "pixels", "offset": "offset", "pan_range": "panRange",
            "tilt_range": "tiltRange", "motorised": "motorised"}
    drivers = {"aeco:cctvSensor:"+target: cfg[source] for source, target in keys.items()}
    drivers.update({"aeco:cctvSensor:projection": "rectilinear", "aeco:cctvSensor:spectrum": "visible",
                    "aeco:cctvSensor:sensorSize": [0.0, 0.0]})
    return {"Contract": CONTRACT,
            "Type": {"aeco:cctvType:outdoor": cfg["outdoor"], "aeco:cctvType:irRange": cfg["ir_range"],
                     "aeco:type:model": name, "aeco:type:manufacturer": "Generic"},
            "Sensors": [{"name": "Sensor_0", "drivers": drivers}]}


def occurrence_payload(camera):
    drivers = {"pan": camera.pan, "tilt": camera.tilt, "roll": camera.roll,
               "focalLength": camera.focal_length, "range": camera.range,
               "targetDensity": camera.target_density}
    return {"Contract": CONTRACT,
            "Drivers": {"aeco:cctv:scenario": camera.scenario, "aeco:cctv:mount": camera.mount},
            "Sensors": [{"name": "Sensor_0", "drivers": {"aeco:cctvSensor:"+k: v for k, v in drivers.items()},
                         "presets": camera.presets, "tour": camera.tour}]}
