#!/usr/bin/env python3
"""Prove schedule points lie inside opaque convex bodies from the generated IFC.

This diagnostic keeps every sample and obstacle. Its upper bounds are not
coverage passes; they explain why moving cameras cannot satisfy this schedule.
"""
import argparse
import json
from pathlib import Path

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element
import ifcopenshell.util.placement
import numpy as np


def inside_convex(entity, points):
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)
    shape = ifcopenshell.geom.create_shape(settings, entity)
    vertices = np.array(shape.geometry.verts).reshape(-1, 3)
    faces = np.array(shape.geometry.faces).reshape(-1, 3)
    triangles = vertices[faces]
    normals = np.cross(triangles[:,1]-triangles[:,0], triangles[:,2]-triangles[:,0])
    lengths = np.linalg.norm(normals, axis=1)
    triangles, normals = triangles[lengths>1e-10], normals[lengths>1e-10]/lengths[lengths>1e-10,None]
    centre = vertices.mean(axis=0)
    normals[np.einsum('ij,ij->i', centre-triangles[:,0], normals)>0] *= -1
    distances = np.einsum('pfi,fi->pf', vertices[:,None,:]-triangles[None,:,0,:], normals)
    if np.max(distances)>1e-6:
        raise ValueError('Diagnostic requires a convex IFC body: '+entity.GlobalId)
    edges = {}
    for face in faces:
        for i in range(3):
            edge = tuple(sorted((int(face[i]), int(face[(i+1)%3]))))
            edges[edge] = edges.get(edge, 0)+1
    if any(count != 2 for count in edges.values()):
        raise ValueError('Diagnostic requires a closed IFC body: '+entity.GlobalId)
    distances = np.einsum('pfi,fi->pf', np.asarray(points)[:,None,:]-triangles[None,:,0,:], normals)
    return np.all(distances < -1e-6, axis=1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('study', type=Path, help='Completed scripts/study.py output')
    args = parser.parse_args()
    directory = args.study
    plan = json.loads((directory/'out/build_plan.json').read_text())
    manifest = json.loads((directory/'out/targets.json').read_text())
    model = ifcopenshell.open(str(directory/'ifc/demo-datacentre-01.ifc'))
    by_id = {pset['Id']: e for e in model.by_type('IfcElement')
             if (pset := ifcopenshell.util.element.get_psets(e).get('DC_Identity', {})).get('Id')}
    proofs = []
    def record(target, points, candidates):
        occupied = np.zeros(len(points), dtype=bool)
        bodies = []
        for key, entity in candidates:
            mask = inside_convex(entity, points)
            if mask.any():
                bodies.append(dict(id=key, GlobalId=entity.GlobalId, count=int(mask.sum()),
                                   points=np.asarray(points)[mask].tolist()))
                occupied |= mask
        proofs.append(dict(target=target, samples=len(points), insideOpaqueBodies=int(occupied.sum()),
                           maximumPossibleFraction=float(1-occupied.mean()), bodies=bodies))
    for region in manifest['regions']:
        if region['type'] != 'yard':
            continue
        lo, hi = np.min(region['polygon'], axis=0), np.max(region['polygon'], axis=0)
        points = [[x,y,lo[2]+1.5] for x in np.arange(lo[0]+.25,hi[0],.5) for y in np.arange(lo[1]+.25,hi[1],.5)]
        candidates = [(e['id'],by_id[e['id']]) for e in plan['equipment'] if e['space']==region['id']]
        record(region['id'], points, candidates)
    # Every external face is checked; this is not an exception for one camera.
    normals = {'+X':(1,0,0), '-X':(-1,0,0), '+Y':(0,1,0), '-Y':(0,-1,0)}
    pipes = [(key,e) for key,e in by_id.items() if e.is_a('IfcPipeSegment')]
    for door in manifest['doors']:
        if not door['external']:
            continue
        normal = np.asarray(normals[door['approach_normal']])
        across = np.array([-normal[1],normal[0],0])
        centre = np.asarray(door['centre'])-[0,0,1.6]
        points = [centre+normal*.15+across*x+[0,0,z]
                  for x in np.arange(-door['width']/2+.1,door['width']/2,.25)
                  for z in np.arange(.3,min(door['height'],2.1),.25)]
        # Cheap native placement bounds avoid tessellating distant pipes.
        candidates = []
        for key,e in pipes:
            origin = ifcopenshell.util.placement.get_local_placement(e.ObjectPlacement)[:3,3]
            if np.linalg.norm(origin[:2]-centre[:2]) < 12:
                candidates.append((key,e))
        record(door['id'], points, candidates)
    result = dict(method='Closed convex IFC body half-spaces; strict interior, tolerance 1e-6 m',
                  schedule='Unchanged 0.5 m yard grid at 1.5 m and 0.25 m door face grid', proofs=proofs)
    (directory/'sample-obstructions.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    for proof in proofs:
        print(proof['target'], proof['insideOpaqueBodies'], '/', proof['samples'],
              'inside opaque IFC bodies; coverage upper bound', round(proof['maximumPossibleFraction'],6))


if __name__ == '__main__':
    main()
