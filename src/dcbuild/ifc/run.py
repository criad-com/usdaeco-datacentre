"""Reusable run authoring for cable carriers, cables, round pipes AND ducts.

A ``Run`` accumulates the segments / fittings / droppers of one distribution
system and — the point of this module — places an ``IfcDistributionPort`` at
every *real* connection point, so the system is a geometrically-coherent,
fully-connected port graph rather than a topological abstraction floating at
the origin. buildingSMART best practice (proven in dc-examples/dcgen):

* every port sits at the midpoint of its physical connection (a segment end, a
  fitting arm-end, an equipment nozzle), with local +Z along the run;
* segments meet fittings **end-to-face** — fittings are compact bodies and the
  adjoining segments are trimmed back to the fitting faces (no overlap, no gap);
* one ``IfcRelConnectsPorts`` per physical join, oriented SOURCE -> SINK;
* a run *ends* on a ``BEND`` elbow (2 ports), never on an open ``TEE``;
* a pipe elbow/branch body is a CUBE of side = the diameter, so every
  axis-aligned arm end-cap is fully embedded (a tangent cylinder is not).

New over dcgen: deterministic entity keys (`base` id + counters) and
``polyline()`` — author a whole orthogonal RouteP as segments + bends in one
call, returning the two end ports.
"""
from __future__ import annotations

import numpy as np

from .geom import X_RUN, X_RUN_NEG, Z_UP, at, frame_between, matrix


class Run:
    def __init__(self, b, system, base, *, system_type, seg_type, seg_predef,
                 seg_class="IfcCableCarrierSegment", fit_class="IfcCableCarrierFitting",
                 drop_type=None, drop_predef="DROPPER", branch_predef="TEE", bend_predef="BEND",
                 tray=(0.3, 0.1), drop=(0.15, 0.05), port_kind="CABLECARRIER", diameter=None):
        self.b = b
        self.system = system
        self.base = base                      # dc id prefix for deterministic keys
        self.system_type = system_type
        self.seg_type = seg_type
        self.seg_predef = seg_predef
        self.seg_class = seg_class
        self.fit_class = fit_class
        self.drop_type = drop_type or seg_type
        self.drop_predef = drop_predef
        self.branch_predef = branch_predef
        self.bend_predef = bend_predef
        self.tw, self.th = tray
        self.dw, self.dh = drop
        self.port_kind = port_kind
        self.diameter = diameter
        # fitting footprint / the half-length each segment is trimmed back by so
        # it butts the fitting face (pipe = diameter cube, tray = its width).
        self.fw = diameter if diameter else self.tw
        self.members: list = []
        self._n = {"seg": 0, "fit": 0, "drop": 0, "port": 0}

    def _key(self, kind: str) -> str:
        self._n[kind] += 1
        return f"{self.base}.{kind}{self._n[kind]:03d}"

    # -- geometry primitive (round tube or rectangular box) ----------------
    def _shape(self, element, width, height, depth, m, length=None):
        if self.diameter:
            self.b.tube(element, self.diameter / 2.0, depth, m, length=length)
        else:
            self.b.box(element, width, height, depth, m, length=length)

    # -- ports / connectivity ----------------------------------------------
    def port(self, element, location, frame=None, flow=None):
        """A port on `element` at world `location`, +Z along `frame`."""
        m = at(frame if frame is not None else Z_UP, location)
        return self.b.add_port(element, system_type=self.system_type,
                               predefined=self.port_kind, matrix=m, flow=flow,
                               key=self._key("port"))

    def connect(self, port1, port2):
        """One IfcRelConnectsPorts, SOURCE (port1) -> SINK (port2)."""
        self.b.connect(port1, port2, direction="SOURCE")

    def face(self, location, axis, sign=1.0):
        """World point on a fitting face: `location` offset by sign*fw/2 along `axis`."""
        a = np.asarray(axis, dtype=float)
        a = a / np.linalg.norm(a)
        return tuple(np.asarray(location, dtype=float) + sign * a * (self.fw / 2.0))

    # -- carriers ----------------------------------------------------------
    def seg(self, name, frame, start, depth):
        """Straight run of `depth` from world `start` along frame's local +Z.
        Returns (element, near_port, far_port) with ports at the two ends."""
        el = self.b.entity(self.seg_class, predefined=self.seg_predef, name=name,
                           key=self._key("seg"))
        self.b.assign_type([el], self.seg_type)
        self._shape(el, self.tw, self.th, depth, at(frame, start), length=depth)
        self.members.append(el)
        axis = np.asarray(frame[:3, 2], dtype=float)
        far = tuple(np.asarray(start, dtype=float) + axis * depth)
        return el, self.port(el, tuple(float(v) for v in start), frame), self.port(el, far, frame)

    def fitting(self, name, predefined, relating_type, location):
        """A compact fitting body centred on the node `location` — a cube of
        side fw for round pipes, or a flat fw x fw x th box for carriers. The
        caller adds one port per arm at the arm-end faces (use `face()`)."""
        el = self.b.entity(self.fit_class, predefined=predefined, name=name,
                           key=self._key("fit"))
        self.b.assign_type([el], relating_type)
        cx, cy, cz = (float(v) for v in location)
        if self.diameter:
            self.b.box(el, self.fw, self.fw, self.fw, at(Z_UP, (cx, cy, cz - self.fw / 2.0)))
        else:
            self.b.box(el, self.fw, self.fw, self.th, at(Z_UP, (cx, cy, cz - self.th / 2.0)))
        self.members.append(el)
        return el

    def dropper(self, name, x, y, top_z, bottom_z):
        """Vertical drop from `top_z` down to `bottom_z` at (x, y).
        Returns (element, top_port, bottom_port)."""
        el = self.b.entity(self.seg_class, predefined=self.drop_predef, name=name,
                           key=self._key("drop"))
        self.b.assign_type([el], self.drop_type)
        depth = top_z - bottom_z
        if self.diameter:
            self.b.tube(el, self.diameter / 2.0, depth,
                        matrix((1, 0, 0), (0, -1, 0), (0, 0, -1), (x, y, top_z)), length=depth)
        else:
            self.b.box(el, self.dw, self.dh, depth,
                       matrix((1, 0, 0), (0, -1, 0), (0, 0, -1), (x, y, top_z)), length=depth)
        self.members.append(el)
        return el, self.port(el, (x, y, top_z)), self.port(el, (x, y, bottom_z))

    # -- composite: full orthogonal polyline -------------------------------
    def polyline(self, name, waypoints, bend_type):
        """Author an orthogonal 3D polyline as segments joined by BEND fittings
        at every direction change. Returns (first_port, last_port) — the open
        ports at the two ends of the route (for tie-in to equipment/headers).
        Segments are trimmed back to fitting faces; single-segment routes have
        no fittings at all."""
        pts = [np.asarray(p, dtype=float) for p in waypoints]
        pts = [p for i, p in enumerate(pts) if i == 0 or np.linalg.norm(p - pts[i - 1]) > 1e-9]
        if len(pts) < 2:
            raise ValueError(f"{name}: degenerate route")
        hf = self.fw / 2.0
        first_port = prev_far = None
        for i in range(len(pts) - 1):
            p1, p2 = pts[i], pts[i + 1]
            frame, length = frame_between(p1, p2)
            axis = frame[:3, 2]
            start = p1 + axis * hf if i > 0 else p1
            end = p2 - axis * hf if i < len(pts) - 2 else p2
            depth = float(np.linalg.norm(end - start))
            seg, p_near, p_far = self.seg(f"{name} Seg {i + 1}", frame, tuple(start), depth)
            if first_port is None:
                first_port = p_near
            if prev_far is not None:
                # bend at p1 joining the previous segment to this one
                fit = self.fitting(f"{name} Bend {i}", self.bend_predef, bend_type, tuple(p1))
                back_axis = pts[i] - pts[i - 1]
                in_port = self.port(fit, self.face(tuple(p1), tuple(back_axis), -1.0))
                out_port = self.port(fit, self.face(tuple(p1), tuple(axis), +1.0), frame)
                self.connect(prev_far, in_port)
                self.connect(out_port, p_near)
            prev_far = p_far
        return first_port, prev_far

    # -- composite run along X with a branch + dropper at each rack --------
    def comb_run(self, label, row_y, z, x_start, x_vals, branch_type, bend_type,
                 drop_top, drop_bottom):
        """A run along X (either direction) with a branch fitting + DROPPER at
        each x in `x_vals`, starting from `x_start`. The through positions get
        a branch fitting (TEE / JUNCTION), the **last** gets a BEND elbow so
        the run does not end on an open tee. Returns the upstream feed port."""
        hf = self.fw / 2.0
        feed = prev_far = None
        x_prev = x_start
        n = len(x_vals)
        for i, rx in enumerate(x_vals, start=1):
            last = (i == n)
            s = 1.0 if rx >= x_prev else -1.0
            frame = X_RUN if s > 0 else X_RUN_NEG
            start_x = x_prev if prev_far is None else x_prev + s * hf
            end_x = rx - s * hf
            seg, p_near, p_far = self.seg(
                f"{label} Seg {i}", frame, (start_x, row_y, z), abs(end_x - start_x))
            if prev_far is None:
                feed = p_near
            else:
                self.connect(prev_far, p_near)

            predef = self.bend_predef if last else self.branch_predef
            ftype = bend_type if last else branch_type
            fit = self.fitting(
                f"{label} {'Bend' if last else 'Branch'} {i}", predef, ftype, (rx, row_y, z))
            near_arm = self.port(fit, (rx - s * hf, row_y, z), frame)
            self.connect(p_far, near_arm)
            branch_arm = self.port(fit, (rx, row_y, z))
            drp, d_top, d_bot = self.dropper(f"{label} Drop {i}", rx, row_y, drop_top, drop_bottom)
            self.connect(branch_arm, d_top)
            d_bot.FlowDirection = "SINK"             # terminal at the served cabinet
            if not last:
                prev_far = self.port(fit, (rx + s * hf, row_y, z), frame)
            x_prev = rx
        return feed

    # -- finalise ----------------------------------------------------------
    def commit(self, serves_name):
        self.b.assign_system(self.members, self.system)
        self.b.serves_building(self.system, serves_name)
        return self.system
