"""G0 fixture integrity and expected scenario evidence (no USD authoring)."""
from collections import Counter

from .. import requirements


def programmes(plan):
    return plan.meta.get("programme", {}).get("programmes", [])


def scope_ids(plan):
    return {x.id for name in ("spaces", "walls", "doors", "columns", "slabs", "equipment", "racks", "runs", "routes")
            for x in getattr(plan, name)} | {e["id"] for e in plan.meta.get("fitout", [])}


def void_enclosures(plan):
    voids = {s.id for s in plan.spaces if s.type == "void"}
    fails = []
    if voids and not programmes(plan):
        fails.append("void_enclosures: voids have no programme")
    for programme in programmes(plan):
        counts = Counter(s for a in programme["activities"] for s in a["workspace"]["encloses"])
        for id in sorted(voids):
            if counts[id] != 1:
                fails.append(f"void_enclosures: {programme['id']}/{id} has {counts[id]} enclosing activities")
    for id in sorted(voids):
        geometry = plan.meta.get("space_geometry", {}).get(id, {})
        parent = geometry.get("parent")
        if parent not in {s.id for s in plan.spaces if s.type != "void"}:
            fails.append(f"void_enclosures: {id} has no occupied parent space")
    return fails


def temporary_lifecycle(plan):
    temporary = {e["id"] for e in plan.meta.get("fitout", []) if e["status"] == "TEMPORARY"}
    fails = []
    if temporary and not programmes(plan):
        fails.append("temporary_lifecycle: temporary products have no programme")
    for programme in programmes(plan):
        for id in sorted(temporary):
            for kind in ("installation", "removal"):
                matches = [a for a in programme["activities"] if a["taskType"] == kind and id in a["scope"]]
                if not matches:
                    fails.append(f"temporary_lifecycle: {programme['id']}/{id} missing {kind}")
    return fails


def activity_scopes(plan):
    known = scope_ids(plan)
    space_ids = {s.id for s in plan.spaces}
    fails = []
    for programme in programmes(plan):
        activities = programme["activities"]
        for id, count in Counter(a["id"] for a in activities).items():
            if count != 1:
                fails.append(f"activity_scopes: duplicate activity {id}")
        for a in activities:
            for id in a["scope"]:
                if id not in known:
                    fails.append(f"activity_scopes: {a['id']} missing scope {id}")
            for ids in a["workspace"].values():
                for id in ids:
                    if id not in space_ids:
                        fails.append(f"activity_scopes: {a['id']} missing workspace {id}")
            if a["plannedStart"] < plan.meta["programme"]["epoch"] or a["plannedFinish"] < a["plannedStart"]:
                fails.append(f"activity_scopes: {a['id']} invalid dates")
        for id, placement in programme.get("placements", {}).items():
            if id not in known or placement["space"] not in space_ids:
                fails.append(f"activity_scopes: invalid placement {id}")
    return fails


def predecessor_cycles(plan):
    fails = []
    for programme in programmes(plan):
        nodes = {a["id"]: a for a in programme["activities"]}
        visiting, done = set(), set()
        def visit(id):
            if id not in nodes:
                fails.append(f"predecessor_cycles: unknown predecessor {id}")
                return
            if id in visiting:
                fails.append(f"predecessor_cycles: cycle at {id}")
                return
            if id in done:
                return
            visiting.add(id)
            for p in nodes[id]["predecessors"]:
                visit(p["id"])
            visiting.remove(id)
            done.add(id)
        for id in nodes:
            visit(id)
    return fails


def scenario_findings(plan):
    """Individual space/activity pairs; expectation files group by rule family."""
    result = {}
    for programme in programmes(plan):
        findings = []
        nodes = {a["id"]: a for a in programme["activities"]}
        for enclosure in nodes.values():
            for space in enclosure["workspace"]["encloses"]:
                for activity in nodes.values():
                    if space in activity["workspace"]["requiresAccess"] and activity["plannedFinish"] >= enclosure["plannedStart"]:
                        findings.append(dict(rule="AccessAfterEnclosure", activity=activity["id"],
                                             partner=enclosure["id"], space=space))
                inspections = [nodes[p["id"]] for p in enclosure["predecessors"] if p["id"] in nodes
                               and nodes[p["id"]]["taskType"] == "attendance"
                               and space in nodes[p["id"]]["scope"]
                               and nodes[p["id"]]["plannedFinish"] < enclosure["plannedStart"]]
                if not inspections:
                    findings.append(dict(rule="EnclosureBeforeInspection", activity=enclosure["id"], space=space))
        for a in nodes.values():
            for b in nodes.values():
                if a["id"] == b["id"] or a["plannedStart"] > b["plannedFinish"] or b["plannedStart"] > a["plannedFinish"]:
                    continue
                for space in sorted(set(a["workspace"]["requiresAccess"]) & set(b["workspace"]["occupies"])):
                    findings.append(dict(rule="WorkspaceOccupied", activity=a["id"], partner=b["id"], space=space))
        result[programme["id"]] = findings
    return result


def expected_programmes(plan):
    expected = plan.meta.get("programme", {}).get("expected", {})
    findings = scenario_findings(plan)
    fails = []
    if set(expected) != set(findings):
        fails.append("expected_programmes: programme expectation ids differ")
    for id, rows in findings.items():
        got = {r["rule"] for r in rows}
        want = {r["rule"] for r in expected.get(id, [])}
        if got != want:
            fails.append(f"expected_programmes: {id}: {sorted(got)} != {sorted(want)}")
        declared = plan.meta.get("expected", {}).get("programme", {}).get(id)
        if declared is None or set(declared) != want:
            fails.append(f"expected_programmes: {id}: variant and programme expectations differ")
    return fails


def typical_deviations(plan):
    fails = []
    for id, rules in plan.meta.get("storey_rules", {}).items():
        prototype = rules.get("typical_of")
        if not prototype:
            continue
        if prototype not in {s.id for s in plan.storeys} or prototype == id:
            fails.append(f"typical_deviations: invalid prototype {prototype}")
            continue
        drift = plan.meta.get("expected", {}).get("drift", {})
        suffix = "."+id.rsplit("l", 1)[-1]
        proto_doors = {d.id+suffix for d in plan.doors if d.storey == prototype}
        actual = {d.id for d in plan.doors if d.storey == id}
        declared = {d["id"] for d in drift.get("deviations", []) if d["kind"] == "doorExtra"}
        if actual-proto_doors != declared or proto_doors-actual:
            fails.append("typical_deviations: undeclared door additions or removals")
        moved = [d for d in drift.get("deviations", []) if d["kind"] == "wallMoved"]
        if drift.get("walls_moved") != len(moved) or drift.get("doors_extra") != len(declared):
            fails.append("typical_deviations: missing or inconsistent drift counts")
        for d in moved:
            match = [w for w in plan.walls if w.storey == id and {w.left,w.right} == set(d["between"])
                     and [list(w.p1),list(w.p2)] == d["axis_to"]]
            proto_pair = {s.removesuffix(suffix) for s in d["between"]}
            prior = [w for w in plan.walls if w.storey == prototype and {w.left,w.right} == proto_pair
                     and [list(w.p1),list(w.p2)] == d["axis_from"]]
            if len(match) != 1 or len(prior) != 1 or not d.get("reason"):
                fails.append("typical_deviations: moved wall declaration does not match geometry")
        # Pair stable generated wall slots; validate every source attribute,
        # allowing the one declared axis edit and its extra door opening.
        import dataclasses
        import math
        prior = {w.id.replace(prototype.split(".")[-1], id.split(".")[-1]): w
                 for w in plan.walls if w.storey == prototype}
        actual_walls = {w.id: w for w in plan.walls if w.storey == id}
        if prior.keys() != actual_walls.keys():
            fails.append("typical_deviations: wall additions or removals")
        edits = {d["id"]: d for d in moved}
        for wall_id in prior.keys() & actual_walls.keys():
            a, b = prior[wall_id], actual_walls[wall_id]
            expected = dataclasses.asdict(a)
            expected.update(id=wall_id, storey=id,
                            left=a.left + suffix if a.left else None,
                            right=a.right + suffix if a.right else None)
            for opening in expected["openings"]:
                opening["door_id"] += suffix
            if wall_id in edits:
                edit = edits[wall_id]
                expected.update(p1=tuple(edit["axis_to"][0]), p2=tuple(edit["axis_to"][1]))
                if edit["prototype"] != a.id:
                    fails.append("typical_deviations: wrong wall prototype")
            got = dataclasses.asdict(b)
            got["openings"] = [o for o in got["openings"] if o["door_id"] not in declared]
            if expected != got:
                fails.append("typical_deviations: undeclared wall change " + wall_id)
        lengths = {level: sum(math.dist(w.p1, w.p2) for w in plan.walls
                              if w.storey == level and w.kind == "internal")
                   for level in (prototype, id)}
        if not math.isclose(lengths[id] - lengths[prototype],
                            drift["expected_net_partition_length_delta_m"], abs_tol=1e-6):
            fails.append("typical_deviations: partition length delta differs")
    return fails


def requirement_files(plan):
    from ..spec import spec_dir
    fails = []
    try:
        directory = spec_dir()/"requirements"
        docs = requirements.load(directory)
        if set(docs) != {"accessibility", "employer-security", "reader-datasheet"}:
            fails.append("requirement_files: expected three specification files")
        for path in directory.glob("*.yaml"):
            if "ILLUSTRATIVE" not in path.read_text().splitlines()[0]:
                fails.append(f"requirement_files: {path.name} missing illustrative header")
        if plan.security.get("iris_mounting"):
            actual = requirements.evaluate(plan.security["iris_mounting"], docs)
            if actual != plan.meta.get("expected", {}).get("readers"):
                fails.append("requirement_files: reader verdicts differ from declared expectations")
    except (ValueError, OSError) as exc:
        fails.append(f"requirement_files: {exc}")
    return fails


CHECKS = [void_enclosures, temporary_lifecycle, activity_scopes, predecessor_cycles,
          typical_deviations, requirement_files, expected_programmes]
