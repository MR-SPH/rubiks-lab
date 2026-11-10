"""Pure-Python layer-by-layer (beginner method) solver.

A real, standalone solver: it works on any valid cube state regardless of
how the cube reached that state.  It never reverses move history.

Method (D layer first, then middle, then last layer):

1.  D cross          -- piece-targeted insertions (half turns from the U
                        layer), sandwich triggers to pop misplaced edges,
                        and a cross-OLL flip fix for inverted edges.
2.  D corners        -- the classic "sexy trigger" insertion, repeated
                        until the slot is solved.
3.  Middle edges     -- standard right/left insertion algorithms, rotated
                        around the cube to reach every side.
4.  U edge orientation   -- BFS table over the 8 flip patterns using two
                        cross-OLL generators and U turns.
5.  U corner orientation -- BFS table over the 27 twist patterns using
                        Sune / Anti-Sune and U turns.
6.  U corner permutation -- BFS table over the 24 permutations using an
                        A-perm and U turns.
7.  U edge permutation   -- BFS table over the 12 even permutations using
                        Ua/Ub perms.

Reliability strategy: every memorised algorithm is *verified
programmatically* at engine initialisation (applied to reference states
with assertions about its net effect), and the last-layer tables are
built by BFS directly on the cube model, so a mistyped algorithm fails
loudly instead of producing wrong solutions.  Every solve ends with a
full verification (apply the solution to a clone; it must be solved).
"""

from __future__ import annotations

from collections import deque

from core.cube import CubeState
from core.moves import (
    FACE_NORMAL,
    IDENTITY3,
    Move,
    invert_sequence,
    parse_sequence,
    shift_face,
    simplify,
)
from core.cube_validator import validate

# ---------------------------------------------------------------------------
# Geometry tables
# ---------------------------------------------------------------------------

#: U-layer edge slots in F, R, B, L order.
U_EDGE_SLOTS: tuple[tuple[int, int, int], ...] = (
    (0, 1, 1), (1, 1, 0), (0, 1, -1), (-1, 1, 0),
)
SIDE_OF_U_EDGE: dict[tuple[int, int, int], str] = {
    (0, 1, 1): "F", (1, 1, 0): "R", (0, 1, -1): "B", (-1, 1, 0): "L",
}
U_SLOT_OF_SIDE: dict[str, tuple[int, int, int]] = {
    v: k for k, v in SIDE_OF_U_EDGE.items()
}

#: U-layer corner positions in piece-movement order (F -> L -> B -> R).
U_CORNER_RING: tuple[tuple[int, int, int], ...] = (
    (1, 1, 1), (-1, 1, 1), (-1, 1, -1), (1, 1, -1),
)

#: D cross slots per side.
D_CROSS_SLOTS: dict[str, tuple[int, int, int]] = {
    "F": (0, -1, 1), "R": (1, -1, 0), "B": (0, -1, -1), "L": (-1, -1, 0),
}
SIDE_OF_D_SLOT: dict[tuple[int, int, int], str] = {
    v: k for k, v in D_CROSS_SLOTS.items()
}

#: Middle edge slots and their two side faces.
MIDDLE_SLOTS: dict[str, tuple[int, int, int]] = {
    "FR": (1, 0, 1), "BR": (1, 0, -1), "BL": (-1, 0, -1), "FL": (-1, 0, 1),
}

#: D corner slots and the U position directly above each.
CORNER_SLOTS: dict[str, tuple[int, int, int]] = {
    "DFR": (1, -1, 1), "DRB": (1, -1, -1),
    "DBL": (-1, -1, -1), "DLF": (-1, -1, 1),
}
CORNER_ABOVE: dict[str, tuple[int, int, int]] = {
    "DFR": (1, 1, 1), "DRB": (1, 1, -1),
    "DBL": (-1, 1, -1), "DLF": (-1, 1, 1),
}

#: Side ring F -> R -> B -> L (clockwise seen from above).
RING = ("F", "R", "B", "L")
RING_INDEX = {f: i for i, f in enumerate(RING)}

#: Piece-movement ring of U turns: a piece above F moves above L, etc.
U_MOVEMENT_RING = ("F", "L", "B", "R")
U_MOVEMENT_INDEX = {f: i for i, f in enumerate(U_MOVEMENT_RING)}


# ---------------------------------------------------------------------------
# Algorithms (all verified at init)
# ---------------------------------------------------------------------------

CROSS_OLL = "F R U R' U' F'"    # net: flips two opposite U edges (its UF and UB)
CROSS_OLL_L = "F U R U' R' F'"  # net: flips two adjacent U edges
SUNE = "R U R' U R U2 R'"
ANTISUNE = "R U2 R' U' R U' R'"
A_PERM = "R' F R' B2 R F' R' B2 R2"          # pure corner 3-cycle
UA_PERM = "R U' R U R U R U' R' U' R2"       # pure edge 3-cycle
UB_PERM = "R2 U R U R' U' R' U' R' U R'"     # pure edge 3-cycle (other way)

#: Pop triggers for D corners: each preserves the cross and the other
#: three D corners, and pops its slot's corner into the U layer.
D_CORNER_TRIGGER: dict[str, str] = {
    "DFR": "R U R' U'",
    "DRB": "B U B' U'",
    "DBL": "L U L' U'",
    "DLF": "F U F' U'",
}

#: Sandwich triggers to pop a middle-layer edge into the U layer while
#: restoring the touched D cross edge.  Value: (algorithm, landing slot).
MIDDLE_POP: dict[tuple[int, int, int], tuple[str, tuple[int, int, int]]] = {
    (1, 0, 1): ("R U' R'", (0, 1, -1)),    # FR -> UB
    (1, 0, -1): ("R' U R", (0, 1, 1)),     # BR -> UF
    (-1, 0, 1): ("L' U' L", (0, 1, 1)),    # FL -> UF
    (-1, 0, -1): ("L U L'", (0, 1, -1)),   # BL -> UB
}

RIGHT_INSERT = "U R U' R' U' F' U F"    # inserts UF edge (side sticker on F) into FR
LEFT_INSERT = "U' L' U L U F U' F'"     # inserts UF edge (side sticker on F) into FL


def _shift_alg(text: str, k: int) -> list[Move]:
    """Rotate every side face of an algorithm k steps around the cube."""
    return [m.shifted(k) for m in parse_sequence(text)]


def _middle_slot_pos(face_a: str, face_b: str) -> tuple[int, int, int]:
    """Grid position of the middle slot between two adjacent side faces."""
    na, nb = FACE_NORMAL[face_a], FACE_NORMAL[face_b]
    return (na[0] + nb[0], na[1] + nb[1], na[2] + nb[2])


def _insert_shift(is_right: bool, slot_faces: frozenset) -> int:
    """Rotation k so that the insert algorithm targets ``slot_faces``.

    RIGHT_INSERT targets the slot between F and R; LEFT_INSERT between
    F and L.  Rotating both side faces k steps moves the target slot.
    """
    anchor, other = ("F", "R") if is_right else ("F", "L")
    for k in range(4):
        if {shift_face(anchor, k), shift_face(other, k)} == set(slot_faces):
            return k
    raise SolverError(f"No rotation of insert alg matches {slot_faces}")


class SolverError(RuntimeError):
    """Raised when the solver's internal invariants break (never expected)."""


# ---------------------------------------------------------------------------
# The solver
# ---------------------------------------------------------------------------


class BeginnerSolver:
    """Layer-by-layer solver engine (pure Python, no dependencies)."""

    def __init__(self) -> None:
        self._verify_algorithms()
        self._tables: dict[str, dict] | None = None

    # -- public API ----------------------------------------------------------

    def solve(self, state: CubeState) -> list[Move]:
        """Return a move list that solves ``state`` (the state is unchanged)."""
        validate(state)
        if state.is_solved():
            return []
        work = state.clone()
        moves: list[Move] = []
        self._solve_cross(work, moves)
        self._solve_d_corners(work, moves)
        self._solve_middle(work, moves)
        self._solve_last_layer(work, moves)
        moves = simplify(moves)
        check = state.clone()
        check.apply_sequence(moves)
        if not check.is_solved():
            raise SolverError("Solver produced a non-solving sequence")
        return moves

    # -- helpers ---------------------------------------------------------------

    @staticmethod
    def _apply(state: CubeState, moves: list[Move], out: list[Move]) -> None:
        state.apply_sequence(moves)
        out.extend(moves)

    def _find_edge(self, state: CubeState, c1: str, c2: str):
        target = frozenset((c1, c2))
        for pos, cubie in state.cubies.items():
            if len(cubie.stickers) == 2 and \
                    frozenset(c for _, c in cubie.stickers) == target:
                return pos
        raise SolverError(f"Edge {c1}{c2} not found")

    def _find_corner(self, state: CubeState, c1: str, c2: str, c3: str):
        target = frozenset((c1, c2, c3))
        for pos, cubie in state.cubies.items():
            if len(cubie.stickers) == 3 and \
                    frozenset(c for _, c in cubie.stickers) == target:
                return pos
        raise SolverError(f"Corner {c1}{c2}{c3} not found")

    def _u_steps_edge(self, from_side: str, to_side: str) -> int:
        """U quarter turns to move a piece from above from_side to to_side."""
        return (U_MOVEMENT_INDEX[to_side] - U_MOVEMENT_INDEX[from_side]) % 4

    def _u_steps_corner(self, from_pos, to_pos) -> int:
        """U quarter turns to move a corner from one U slot to another."""
        return (U_CORNER_RING.index(to_pos) - U_CORNER_RING.index(from_pos)) % 4

    # -- stage 1: D cross --------------------------------------------------------

    def _cross_solved(self, state: CubeState, side: str) -> bool:
        slot = D_CROSS_SLOTS[side]
        cubie = state.cubie_at(slot)
        return (
            self._colors(state, slot) == frozenset(("D", side))
            and cubie.sticker_facing((0, -1, 0)) == "D"
        )

    def _solve_cross(self, state: CubeState, out: list[Move]) -> None:
        for side in ("F", "R", "B", "L"):
            if self._cross_solved(state, side):
                continue
            pos = self._find_edge(state, "D", side)

            if pos[1] == -1:
                # In the D layer (wrong slot or flipped): half turn pops it up.
                face = SIDE_OF_D_SLOT[pos]
                self._apply(state, [Move(face, 2)], out)
                pos = self._find_edge(state, "D", side)
            elif pos[1] == 0:
                # Stuck in the middle layer: sandwich trigger pops it into
                # the U layer while restoring the touched D cross edge.
                alg, _landing = MIDDLE_POP[pos]
                self._apply(state, parse_sequence(alg), out)
                pos = self._find_edge(state, "D", side)
                if pos[1] != 1:
                    raise SolverError("Cross edge pop failed")

            # Now in the U layer.  First orient it: the cross-OLL pair flip
            # toggles the piece departing the alg's F slot, so we rotate the
            # alg to the piece's *current* position and repeat until its D
            # sticker faces up.  (D layer and middle layer are untouched.)
            for _ in range(6):
                pos = self._find_edge(state, "D", side)
                if state.cubie_at(pos).sticker_facing((0, 1, 0)) == "D":
                    break
                cur = SIDE_OF_U_EDGE[pos]
                self._apply(state, _shift_alg(CROSS_OLL, RING_INDEX[cur]), out)
            else:
                raise SolverError("Cross flip fix failed")

            # Align above the target side and insert with a half turn.
            pos = self._find_edge(state, "D", side)
            k = self._u_steps_edge(SIDE_OF_U_EDGE[pos], side)
            if k:
                self._apply(state, [Move("U", k)], out)
            self._apply(state, [Move(side, 2)], out)
            if not self._cross_solved(state, side):
                raise SolverError(f"Cross edge {side} insertion failed")

    # -- stage 2: D corners --------------------------------------------------------

    def _corner_solved(self, state: CubeState, slot_name: str) -> bool:
        slot = CORNER_SLOTS[slot_name]
        cubie = state.cubie_at(slot)
        return (
            self._colors(state, slot) == frozenset(("D", slot_name[1], slot_name[2]))
            and cubie.sticker_facing((0, -1, 0)) == "D"
        )

    def _solve_d_corners(self, state: CubeState, out: list[Move]) -> None:
        for slot_name in ("DFR", "DRB", "DBL", "DLF"):
            colors = ("D", slot_name[1], slot_name[2])
            if self._corner_solved(state, slot_name):
                continue
            trigger = parse_sequence(D_CORNER_TRIGGER[slot_name])
            above = CORNER_ABOVE[slot_name]
            for _attempt in range(16):
                if self._corner_solved(state, slot_name):
                    break
                pos = self._find_corner(state, *colors)
                if pos[1] == -1:
                    # Sitting in a D slot (wrong slot, or twisted in its own):
                    # pop it up with that slot's trigger, which preserves all
                    # other D pieces.
                    wrong = next(n for n, s in CORNER_SLOTS.items() if s == pos)
                    self._apply(state, parse_sequence(D_CORNER_TRIGGER[wrong]), out)
                    pos = self._find_corner(state, *colors)
                    if pos[1] != 1:
                        raise SolverError(f"Corner pop failed for {slot_name}")
                if pos != above:
                    k = self._u_steps_corner(pos, above)
                    if k:
                        self._apply(state, [Move("U", k)], out)
                    pos = self._find_corner(state, *colors)
                if pos != above:
                    raise SolverError(f"Cannot position corner for {slot_name}")
                self._apply(state, trigger, out)
            else:
                raise SolverError(f"Corner {slot_name} did not converge")

    # -- stage 3: middle edges -------------------------------------------------------

    def _middle_solved(self, state: CubeState, slot_name: str) -> bool:
        slot = MIDDLE_SLOTS[slot_name]
        cubie = state.cubie_at(slot)
        # Colors must match AND the edge must not be flipped in its slot
        # (the first letter's sticker must face the first letter's side).
        return (
            self._colors(state, slot) == frozenset((slot_name[0], slot_name[1]))
            and cubie.sticker_facing(FACE_NORMAL[slot_name[0]]) == slot_name[0]
        )

    def _solve_middle(self, state: CubeState, out: list[Move]) -> None:
        for slot_name in ("FR", "BR", "BL", "FL"):
            if self._middle_solved(state, slot_name):
                continue
            c1, c2 = slot_name[0], slot_name[1]
            pos = self._find_edge(state, c1, c2)

            if pos[1] == 0:
                # Stuck in a middle slot: run the insertion algorithm whose
                # target is the slot it is STUCK IN (not its home slot); it
                # pushes the occupant up into the U layer.
                stuck = next(n for n, p in MIDDLE_SLOTS.items() if p == pos)
                k = _insert_shift(True, frozenset(stuck))
                self._apply(state, _shift_alg(RIGHT_INSERT, k), out)
                pos = self._find_edge(state, c1, c2)
                if pos[1] != 1:
                    raise SolverError(f"Edge {c1}{c2} stuck in middle layer")

            # Align: rotate U until the side-facing sticker matches the side
            # it is above.
            for _ in range(4):
                side = SIDE_OF_U_EDGE[pos]
                if state.cubie_at(pos).sticker_facing(FACE_NORMAL[side]) == side:
                    break
                self._apply(state, [Move("U", 1)], out)
                pos = self._find_edge(state, c1, c2)
            side = SIDE_OF_U_EDGE[pos]
            cubie = state.cubie_at(pos)
            if cubie.sticker_facing(FACE_NORMAL[side]) != side:
                raise SolverError(f"Cannot align edge {c1}{c2}")

            top_color = cubie.sticker_facing((0, 1, 0))
            if top_color == RING[(RING_INDEX[side] + 1) % 4]:
                # The edge belongs in the slot to the RIGHT of this side.
                self._apply(state, _shift_alg(RIGHT_INSERT, RING_INDEX[side]), out)
            elif top_color == RING[(RING_INDEX[side] - 1) % 4]:
                self._apply(state, _shift_alg(LEFT_INSERT, RING_INDEX[side]), out)
            else:
                raise SolverError(f"Edge {c1}{c2} has no side neighbour")
            if not self._middle_solved(state, slot_name):
                raise SolverError(f"Middle edge {slot_name} insertion failed")

    # -- stages 4-7: last layer via BFS tables -----------------------------------------

    #: U corner slots, same order as U_CORNER_RING (used for LL bookkeeping).
    U_CORNER_SLOTS = U_CORNER_RING

    def _solve_last_layer(self, state: CubeState, out: list[Move]) -> None:
        tables = self._ll_tables()

        def edge_flip_pattern(s: CubeState) -> tuple[int, ...]:
            return tuple(
                0 if s.cubie_at(pos).sticker_facing((0, 1, 0)) == "U" else 1
                for pos in U_EDGE_SLOTS
            )

        def corner_twist_pattern(s: CubeState) -> tuple[int, ...]:
            pat = []
            for slot in self.U_CORNER_SLOTS:
                cubie = s.cubie_at(slot)
                ud = "U" if "U" in (c for _, c in cubie.stickers) else "D"
                world = cubie.world_normal(
                    next(n for n, c in cubie.stickers if c == ud)
                )
                pat.append(self._corner_twist_index(slot, world))
            return tuple(pat)

        def corner_perm(s: CubeState) -> tuple[int, ...]:
            q = []
            for slot in self.U_CORNER_SLOTS:
                colors = self._colors(s, slot)
                for idx, home in enumerate(self.U_CORNER_SLOTS):
                    if colors == frozenset(_piece_colors_at(home)):
                        q.append(idx)
                        break
            if len(q) != 4:
                raise SolverError("Bad corner permutation readout")
            return tuple(q)

        def edge_perm(s: CubeState) -> tuple[int, ...]:
            q = []
            for slot in U_EDGE_SLOTS:
                colors = self._colors(s, slot)
                for idx, home in enumerate(U_EDGE_SLOTS):
                    if colors == frozenset(_piece_colors_at(home)):
                        q.append(idx)
                        break
            if len(q) != 4:
                raise SolverError("Bad edge permutation readout")
            return tuple(q)

        def apply_stage(stage: str, pattern, readout) -> None:
            table = tables[stage]
            gens = table.get(pattern)
            if gens is None:
                raise SolverError(
                    f"LL stage {stage}: unreachable pattern {pattern}"
                )
            alg_moves: list[Move] = []
            for gen_key in gens:
                alg_moves.extend(tables["gen_moves"][gen_key])
            self._apply(state, invert_sequence(alg_moves), out)
            if readout(state) != _identity_pattern(stage):
                raise SolverError(f"LL stage {stage} did not resolve")

        apply_stage("edge_ori", edge_flip_pattern(state), edge_flip_pattern)
        apply_stage("corner_ori", corner_twist_pattern(state), corner_twist_pattern)
        apply_stage("corner_perm", corner_perm(state), corner_perm)
        apply_stage("edge_perm", edge_perm(state), edge_perm)

        if not state.is_solved():
            raise SolverError("Last layer stages did not solve the cube")

    @staticmethod
    def _corner_twist_index(slot, world_dir) -> int:
        """Index of ``world_dir`` in the slot's cyclic triple (0/1/2)."""
        from core.cube_validator import CORNER_SLOT_DIRS

        return CORNER_SLOT_DIRS[slot].index(world_dir)

    # -- table building -----------------------------------------------------------------

    def _ll_tables(self) -> dict[str, dict]:
        if self._tables is not None:
            return self._tables

        solved = CubeState()

        def piece_map(s: CubeState, slots) -> dict[int, int]:
            """Piece i (home slots[i]) now sits at slots[P(i)]."""
            out = {}
            for i, home in enumerate(slots):
                target = frozenset(_piece_colors_at(home))
                for j, slot in enumerate(slots):
                    if self._colors(s, slot) == target:
                        out[i] = j
                        break
            if len(out) != len(slots):
                raise SolverError("A U piece left the U layer in a generator")
            return out

        def u_edge_flip_readout(s: CubeState) -> tuple[int, ...]:
            return tuple(
                0 if s.cubie_at(pos).sticker_facing((0, 1, 0)) == "U" else 1
                for pos in U_EDGE_SLOTS
            )

        def u_corner_twist_readout(s: CubeState) -> tuple[int, ...]:
            return tuple(
                self._corner_twist_index(
                    slot,
                    s.cubie_at(slot).world_normal(
                        next(
                            n for n, c in s.cubie_at(slot).stickers
                            if c in ("U", "D")
                        )
                    ),
                )
                for slot in self.U_CORNER_SLOTS
            )

        gens: dict[str, tuple] = {}
        gen_moves: dict[str, list[Move]] = {}

        # Edge-orientation generators: (perm, flip-delta per departing piece).
        for key, text in (
            ("OLL", CROSS_OLL), ("OLL_L", CROSS_OLL_L),
            ("U", "U"), ("U2", "U2"), ("U'", "U'"),
        ):
            moves = parse_sequence(text)
            s = solved.clone()
            s.apply_sequence(moves)
            _assert_d_layer_intact(s, context=f"edge-ori gen {text}")
            P = piece_map(s, U_EDGE_SLOTS)
            flips = u_edge_flip_readout(s)
            F = tuple(flips[P[i]] for i in range(4))
            gens[key] = (P, F)
            gen_moves[key] = moves

        # Corner-orientation generators: (perm, twist-delta per departing piece).
        for key, text in (
            ("c_SUNE", SUNE), ("c_ANTISUNE", ANTISUNE),
            ("c_U", "U"), ("c_U2", "U2"), ("c_U'", "U'"),
        ):
            moves = parse_sequence(text)
            s = solved.clone()
            s.apply_sequence(moves)
            _assert_d_layer_intact(s, context=f"corner-ori gen {text}")
            if key in ("c_SUNE", "c_ANTISUNE") and any(u_edge_flip_readout(s)):
                raise SolverError(f"{text} flips edges")
            P = piece_map(s, self.U_CORNER_SLOTS)
            twists = u_corner_twist_readout(s)
            c = tuple(twists[P[i]] for i in range(4))
            gens[key] = (P, c)
            gen_moves[key] = moves

        # Corner-permutation generators (A-perm must be edge-neutral).
        for key, text in (
            ("pc_APERM", A_PERM), ("pc_U", "U"), ("pc_U2", "U2"), ("pc_U'", "U'"),
        ):
            moves = parse_sequence(text)
            s = solved.clone()
            s.apply_sequence(moves)
            _assert_d_layer_intact(s, context=f"corner-perm gen {text}")
            if key == "pc_APERM":
                if any(u_edge_flip_readout(s)) or any(
                    self._colors(s, slot) != frozenset(_piece_colors_at(slot))
                    for slot in U_EDGE_SLOTS
                ):
                    raise SolverError("A-perm is not edge-neutral")
            gens[key] = (piece_map(s, self.U_CORNER_SLOTS), None)
            gen_moves[key] = moves

        # Edge-permutation generators (must leave corners exactly home).
        # Ua/Ub alone only span {id, C, C^-1}; U-conjugated copies cycle a
        # different triple of U edges while still fixing the corners net
        # (U' ... U restores them), and together they generate A4 (12 states).
        for key, text in (
            ("pe_UA", UA_PERM),
            ("pe_UB", UB_PERM),
            ("pe_UA1", "U' " + UA_PERM + " U"),
            ("pe_UA2", "U2 " + UA_PERM + " U2"),
        ):
            moves = parse_sequence(text)
            s = solved.clone()
            s.apply_sequence(moves)
            _assert_d_layer_intact(s, context=f"edge-perm gen {text}")
            if piece_map(s, self.U_CORNER_SLOTS) != {i: i for i in range(4)}:
                raise SolverError(f"{text} moves corners")
            if any(u_corner_twist_readout(s)):
                raise SolverError(f"{text} twists corners")
            gens[key] = (piece_map(s, U_EDGE_SLOTS), None)
            gen_moves[key] = moves

        # --- BFS tables: table[pattern] = generator keys taking SOLVED -> pattern.
        def bfs(start, transition, gen_keys, expected_size):
            table = {start: []}
            dq = deque([start])
            while dq:
                st = dq.popleft()
                for key in gen_keys:
                    P, payload = gens[key]
                    ns = transition(st, P, payload)
                    if ns not in table:
                        table[ns] = table[st] + [key]
                        dq.append(ns)
            if len(table) != expected_size:
                raise SolverError(
                    f"BFS reached {len(table)} states, expected {expected_size}"
                )
            return table

        def tr_edge_ori(pat, P, F):
            new = [0] * 4
            for j in range(4):
                new[P[j]] = pat[j] ^ F[j]
            return tuple(new)

        def tr_corner_ori(pat, P, c):
            new = [0] * 4
            for j in range(4):
                new[P[j]] = (pat[j] + c[j]) % 3
            return tuple(new)

        def tr_perm(q, P, _none):
            new = [0] * 4
            for j in range(4):
                new[P[j]] = q[j]
            return tuple(new)

        tables = {
            "gen_moves": gen_moves,
            "edge_ori": bfs((0, 0, 0, 0), tr_edge_ori,
                            ["OLL", "OLL_L", "U", "U2", "U'"], 8),
            "corner_ori": bfs((0, 0, 0, 0), tr_corner_ori,
                              ["c_SUNE", "c_ANTISUNE", "c_U", "c_U2", "c_U'"], 27),
            "corner_perm": bfs((0, 1, 2, 3), tr_perm,
                               ["pc_APERM", "pc_U", "pc_U2", "pc_U'"], 24),
            "edge_perm": bfs((0, 1, 2, 3), tr_perm,
                             ["pe_UA", "pe_UB", "pe_UA1", "pe_UA2"], 12),
        }
        self._tables = tables
        return tables

    # -- init-time algorithm verification ---------------------------------------------

    def _verify_algorithms(self) -> None:
        """Apply every structural algorithm to reference states and assert
        its documented effect.  A mistyped algorithm fails loudly here."""
        # Middle pops: cross intact (D corners may legitimately move here:
        # this trigger family is only used before corners are solved).
        for pos, (text, landing) in MIDDLE_POP.items():
            s = CubeState()
            s.apply_sequence(parse_sequence(text))
            _assert_d_cross_intact(s, context=f"pop {text}")
            if self._colors(s, landing) != frozenset(_piece_colors_at(pos)):
                raise SolverError(f"Pop {text} did not lift the edge")
        # D corner triggers: preserve cross + other D corners, pop own corner.
        for name, text in D_CORNER_TRIGGER.items():
            s = CubeState()
            s.apply_sequence(parse_sequence(text))
            _assert_d_layer_intact(s, context=f"trigger {text}", skip_slot=name)
            expected = frozenset(("D", name[1], name[2]))
            if self._colors(s, CORNER_ABOVE[name]) != expected:
                raise SolverError(f"Trigger {text} did not pop its corner")
        # Insert algorithms: from a clean reference state, each must insert
        # its edge into its target slot.
        for base, is_right in ((RIGHT_INSERT, True), (LEFT_INSERT, False)):
            for k in range(4):
                alg = _shift_alg(base, k)
                target_faces = (shift_face("F", k), shift_face("R" if is_right else "L", k))
                slot_pos = _middle_slot_pos(*target_faces)
                ref = CubeState()
                ref.apply_sequence(invert_sequence(alg))
                _assert_d_layer_intact(ref, context=f"insert {base} k={k}")
                if self._colors(ref, slot_pos) == frozenset(_piece_colors_at(slot_pos)):
                    raise SolverError(
                        f"Insert {base} k={k}: reference state not clean"
                    )
                ref.apply_sequence(alg)
                if self._colors(ref, slot_pos) != frozenset(target_faces):
                    raise SolverError(
                        f"Insert {base} k={k} does not insert correctly"
                    )
        # Cross OLL: D layer untouched, exactly two U pieces flipped, and
        # the flip lands on the pieces *departing* the F and B slots
        # (this is what the cross stage's orient loop relies on).
        for text in (CROSS_OLL, CROSS_OLL_L):
            s = CubeState()
            s.apply_sequence(parse_sequence(text))
            _assert_d_layer_intact(s, context=f"cross OLL {text}")
            departed_flip = []
            for j, pos in enumerate(U_EDGE_SLOTS):
                # where did the piece that started at pos end up?
                dest = next(
                    p for p in U_EDGE_SLOTS
                    if self._colors(s, p) == frozenset(_piece_colors_at(pos))
                )
                flipped = s.cubie_at(dest).sticker_facing((0, 1, 0)) != "U"
                departed_flip.append((j, flipped))
            if sum(f for _, f in departed_flip) != 2:
                raise SolverError(f"Cross OLL {text} flips {sum(f for _, f in departed_flip)} pieces")
            if text == CROSS_OLL and not (departed_flip[0][1] and departed_flip[2][1]):
                raise SolverError(
                    f"Cross OLL {text} does not flip the F/B departing pieces"
                )

    # -- misc ---------------------------------------------------------------------------

    def _colors(self, state: CubeState, pos) -> frozenset:
        cubie = state.cubie_at(pos)
        return frozenset(c for _, c in cubie.stickers)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _piece_colors_at(pos) -> tuple[str, ...]:
    """Colors of the piece whose home slot is ``pos``."""
    return tuple(
        face for face, normal in FACE_NORMAL.items()
        if sum(a * b for a, b in zip(normal, pos)) == 1
    )


def _identity_pattern(stage: str):
    if stage in ("edge_ori", "corner_ori"):
        return (0, 0, 0, 0)
    return (0, 1, 2, 3)


def _assert_d_cross_intact(state: CubeState, context: str = "") -> None:
    """Assert the four D cross edges are home with identity orientation.

    Used for early-stage triggers that may (legitimately) lift D corners,
    which are not yet solved at that point.
    """
    for slot in D_CROSS_SLOTS.values():
        cubie = state.cubie_at(slot)
        if cubie.pos != cubie.home or cubie.ori != IDENTITY3:
            raise SolverError(f"D cross disturbed by {context} at {slot}")


def _assert_d_layer_intact(
    state: CubeState,
    context: str = "",
    skip_slot: str | None = None,
) -> None:
    """Assert every D-layer cubie is home with identity orientation.

    ``skip_slot`` names one D corner slot whose cubie may be displaced
    (used while verifying pop triggers).
    """
    skip_pos = CORNER_SLOTS.get(skip_slot) if skip_slot else None
    for pos, cubie in state.cubies.items():
        if pos[1] == -1 and pos != skip_pos:
            if cubie.pos != cubie.home or cubie.ori != IDENTITY3:
                raise SolverError(f"D layer disturbed by {context} at {pos}")


#: Module-level singleton, created on first use.
_INSTANCE: BeginnerSolver | None = None


def solve(state: CubeState) -> list[Move]:
    """Solve ``state`` with the built-in layer-by-layer engine."""
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = BeginnerSolver()
    return _INSTANCE.solve(state)
