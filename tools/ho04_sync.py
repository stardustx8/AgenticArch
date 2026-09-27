"""Ultra-max offline-first sync project (synthetic; difficulty is reasoning, not volume).

notesync is an op-based sync engine for notes edited offline on a laptop, a phone and a
server. docs/sync-semantics.md is the complete normative contract (Lamport ids, RGA list
order with op-id tie-breaks, tombstones, last-writer-wins text, deletes win, dependency
buffer for non-causal delivery, relay sync, persistence, and an approved but unimplemented
Kleppmann-style tree move design in section 8).

Stage 1 flaws (more than one place): the sequence breaks ties by counter only and appends
lines whose anchor is unknown at the end; apply() drops sets and parks deletes that arrive
early, never buffers inserts, lets a set resurrect a deleted line and uses a counter-only
last-writer rule; the clock ignores received ops; ops() omits buffered ops; push() forwards
only the sender's own ops and uses a counter watermark.
Stage 2 implements section 8: slots, move op, dependency buffering on parent/anchor slot,
replay of location ops in op-id order with cycle skipping, deleted subtrees hidden.

Hidden tests enumerate every delivery order (with duplicates) of small op sets across three
replicas and compare with an independent model of the spec; about 2-4 s with the reference.
"""
from tools.ho02_projects import project


def sub(text, old, new, count=1):
    if text.count(old) != count:
        raise AssertionError(f'expected {count} occurrence(s) of {old!r}')
    return text.replace(old, new)


# --------------------------------------------------------------------------- starting repo

README_MD = r'''# notesync

Offline-first sync engine for notes and meeting transcripts that are edited on several
devices (a laptop, a phone and the server) and synced whenever a connection is available.

- `notesync/` - the engine (Python 3.11+, standard library only)
- `docs/sync-semantics.md` - the normative contract: data model, ops, clocks, ordering,
  buffering, sync, persistence, invariants and the public interface
- `docs/decisions.md` - decision log (some entries are superseded; the spec wins)
- `docs/handoff.md` - state of the work

    python3 -m notesync show FILE        # print the visible lines of a saved replica
    python3 -m notesync status FILE      # counts as JSON
    python3 -m notesync merge A.json B.json

Run the tests with `python3 -m unittest discover -s tests -t .` from this directory. No
network access is needed.
'''

SPEC_MD = r'''# notesync synchronisation semantics

Status: **normative**. This file is the contract for the engine in `notesync/`. Where code,
comments, tests, docs/decisions.md or the handoff disagree with it, this file wins.
Sections 1-7, 9 and 10.1-10.2 describe the shipped engine. Section 8 and 10.3 are the approved
outline design for the next release; they are not implemented yet.

## 1. Overview

A *document* is an ordered list of *items* (the lines of a note or transcript). Every device
(for example `laptop`, `phone`, `server`) holds a *replica* of the document and edits it
offline. Replicas exchange *operations* ("ops") later: in any order, possibly more than once,
and possibly through other replicas (the phone and the laptop normally only talk to the
server). Whatever the delivery, two replicas that know the same set of ops show exactly the
same document.

## 2. Replicas, clocks and op ids

2.1 A replica id is a non-empty string. Replica ids are compared with Python string
comparison (Unicode code point order), so `"laptop" < "phone" < "server"`.

2.2 Every op has an id `[counter, replica]`: `counter` is an integer >= 1 and `replica` is the
id of the replica that created the op. Op ids are unique.

2.3 Op ids are totally ordered: compare the counters first; if they are equal, compare the
replica ids (2.1). "Greater", "newer" and "newest" always refer to this order. `[3, "laptop"]`
< `[3, "phone"]` < `[4, "laptop"]`.

2.4 Each replica has a Lamport clock `clock` (an integer, initially 0).
- Creating a local op sets `clock = clock + 1` and uses the new value as the op's counter.
- Receiving an op (section 5) sets `clock = max(clock, counter of that op)`. This happens for
  every received op, whether it is applied at once, buffered, or a duplicate.

Consequently a new op always has a greater counter than every op its creator knew about.

## 3. Operations

Ops are JSON objects. They travel as JSON, so an implementation receives ids as two-element
JSON arrays (Python lists `[counter, replica]`), never as tuples, and must accept them.

3.1 **insert** `{"type": "insert", "id": ID, "after": ID or null, "value": string}` creates a
new item. The *item id* is the op id. `after` is the item the new one was placed directly
after when it was created; `null` means at the start of the document.

3.2 **delete** `{"type": "delete", "id": ID, "target": ID}` deletes the target item.

3.3 **set** `{"type": "set", "id": ID, "target": ID, "value": string}` replaces the text of
the target item.

3.4 Section 8 adds an optional `parent` field to insert and a new `move` op.

Ops are only ever produced by this engine; validating hand-written ops is not part of this
contract.

## 4. Document state

4.1 **Items.** An item exists on a replica once its insert op has been applied (section 5).
Items are never physically removed; a deleted item stays as a hidden *tombstone*.

4.2 **Order.** Arrange all items of a replica (including tombstones) in an *insertion tree*:
the tree parent of an item is the item named by its insert's `after`, or a virtual *head* when
`after` is null. The children of every node are ordered by descending op id (newest first).
The document order is the pre-order depth-first traversal of this tree starting at the head
(the head itself is not part of the document). Tombstones keep their place in the traversal;
they are only hidden.

Because of 2.4, an item always has a greater id than the item it was inserted after. The rule
is therefore equivalent to the usual RGA insertion rule: "starting right after the `after`
item, skip every item whose id is greater than the new item's id, and insert before the first
item whose id is smaller" (in a list that contains all of the new item's predecessors).

*Example 4.2a (concurrent inserts at the same place).* Laptop and phone start empty. Offline,
the laptop inserts "apple" (`[1, "laptop"]`) and the phone inserts "banana" (`[1, "phone"]`),
both at the start. After they sync, both show `["banana", "apple"]`, because
`[1, "phone"] > [1, "laptop"]`.

*Example 4.2b (runs stay together).* Every replica has "intro" = `[1, "server"]`. Offline,
the laptop inserts "l1" after intro (`[2, "laptop"]`) and then "l2" after l1
(`[3, "laptop"]`); the phone inserts "p1" after intro (`[2, "phone"]`). After syncing, every
replica shows `["intro", "p1", "l1", "l2"]`.

4.3 **Deletion.** An item is deleted as soon as any delete op that targets it has been
applied, and it stays deleted. No op ever makes a deleted item visible again: deletes win over
every set, whether the set is older, concurrent or newer.

4.4 **Text.** The text of an item is the `value` of the newest op (2.3) among its insert and
all applied set ops that target it (last writer wins by op id, never by arrival time). Set ops
that target a deleted item still take part in this rule; the item is just not visible.

4.5 **Visible document.** The items that are not deleted, in document order.

## 5. Receiving ops

5.1 Ops can arrive in any order, duplicated, and before the ops they depend on. Delivery is
**not** causal.

5.2 **Dependencies and buffering.** An insert depends on its `after` item (if not null). A
delete and a set depend on their `target` item. An op whose dependencies have not all been
applied is *buffered*: kept, but not applied. A buffered op is applied automatically as soon
as all of its dependencies have been applied, including dependencies that are themselves
released from the buffer. At the end of every public call, no buffered op has all of its
dependencies applied.

5.3 **Idempotence.** An op whose id the replica already knows (applied or buffered) is
ignored, apart from its effect on the clock (2.4). Receiving any collection of ops any number
of times, in any order, leaves the replica in the same state as receiving each of them once.

5.4 **Convergence.** The document order, texts, deleted flags, visible document and buffer of
a replica depend only on the *set* of ops it knows; not on the order or multiplicity of their
arrival, and not on which of them were created locally.

5.5 **Local edits are ops.** The local methods (10.1) create an op (2.4), apply it and remember
it exactly as if it had been received.

## 6. Sync

6.1 A replica *knows* an op when it has applied or buffered it. This includes ops it received
from other replicas: the server forwards the phone's ops to the laptop and vice versa.

6.2 `push(src, dst)` makes `dst` receive every op that `src` knows and `dst` does not know.
`sync(a, b)` is `push(a, b)` followed by `push(b, a)`; afterwards `a` and `b` know exactly the
same set of ops.

6.3 A replica can learn an op with a small counter after it has learnt ops with larger
counters (for example through a relay), so counters or clock values are not a valid "already
sent" marker. An implementation may skip sending an op only when it knows, by op id, that the
receiver already knows that op.

## 7. Persistence

7.1 `save(replica, path)` writes a UTF-8 JSON file. `load(path)` returns a replica that cannot
be told apart from the saved one through the public interface (section 10): same replica id,
clock, known ops, buffered ops and document.

7.2 Buffered ops are part of the state. They survive save and load, and they are applied once
their dependencies arrive after loading.

## 8. Outline: nesting and moves (approved design, next release)

8.1 **Tree.** Items form a tree under a virtual *root*. Every item has exactly one parent: the
root or another item. Each parent has its own ordered list of children.

8.2 **Slots.** The position of an item is a *slot*. Every insert op and every move op creates
one slot; its *slot id* is that op's id. A slot belongs to a fixed parent (the op's `parent`;
null means the root) and is anchored after another slot of the same parent (the op's
`after`; null means the start of that parent's list). Slots are never removed. The slots of
one parent are ordered exactly like items in 4.2: an anchor tree whose children are ordered
newest first, traversed in pre-order.

8.3 **Op changes.**
- insert gains an optional field `"parent": ID or null` (absent means null). The new item is
  created as a child of `parent` and occupies the slot created by the insert. `after` is now a
  *slot id* of that parent (null: start). Without moves an item's slot id equals its item id,
  so ops written by the current engine keep their meaning unchanged.
- new op **move** `{"type": "move", "id": ID, "target": ID, "parent": ID or null,
  "after": slot ID or null}` creates a new slot under `parent`, anchored after the slot
  `after`, and asks to move the target item into it.
- `after` is always a slot of the op's own parent; the local methods guarantee this.

8.4 **Dependencies** (extends 5.2). An insert also depends on its `parent` item (if not null),
and its `after` dependency is the op that created that slot. A move depends on its `target`
item, its `parent` item (if not null) and the op that created its `after` slot (if not null).
Buffering works exactly as in 5.2.

8.5 **Location.** The *location ops* of an item are its insert and every applied move that
targets it. The tree is, by definition, the result of starting from an empty tree and
processing the applied location ops of all items in ascending op id order (2.3):
- an insert places its new item in its slot;
- a move takes its target out of the slot it currently occupies and places it in the move's
  slot, **unless** the move's parent is the target itself or, at that point of the
  processing, a descendant of the target. Such a move is *skipped*: it has no effect on the
  tree, but its slot still exists (it can serve as an anchor).

So an item sits in the slot of its newest location op that was not skipped. This is the move
operation of Kleppmann et al., "A highly-available move operation for replicated trees"
(2021); implementations usually get it with an undo-do-redo move log or by replaying, but only
the result above is specified.

*Example 8.5a (concurrent moves that would form a cycle).* A = `[1, "server"]` and
B = `[2, "server"]` are both at the root. Offline, the laptop moves A under B
(`[3, "laptop"]`) and the phone moves B under A (`[3, "phone"]`). Processing in id order, the
laptop's move places A under B; the phone's move would put B under its own descendant A, so it
is skipped. Every replica ends with root -> B -> A.

8.6 **Sibling order.** The children of a parent are ordered by the order (8.2) of the slots
they occupy. Slots that no item occupies are ignored.

*Example 8.6a.* The root holds X = `[1, "server"]`, Y = `[2, "server"]` (after X) and
Z = `[3, "server"]` (after Y). Offline, the laptop moves Z to the start of the root
(`[4, "laptop"]`, after null) and the phone moves X after Z (`[4, "phone"]`, after Z's slot
`[3, "server"]`). The root's slots in order are `[4, "laptop"]` (Z), `[1, "server"]` (empty),
`[2, "server"]` (Y), `[3, "server"]` (empty), `[4, "phone"]` (X), so the root's children are
Z, Y, X on every replica.

8.7 **Deletion in the tree.** A deleted item hides its whole subtree from `outline()`,
`values()` and `items()`; the subtree stays in `tree()` and `children()`. An item that is moved
out of a deleted subtree to a visible parent becomes visible again (unless it is deleted
itself). Deleted items can still be moved, edited and used as parents and anchors, following
the same rules.

8.8 **Reading order.** `values()` and `items()` become the pre-order traversal of `outline()`.
Without parents and moves this is exactly the visible document of 4.5.

## 9. Invariants

After every public call, on every replica:

- **I1 Convergence** (5.4, 8.5): replicas that know the same set of ops return identical
  results from every read method in section 10.
- **I2 Idempotence** (5.3).
- **I3 No lost insert**: every applied insert's item appears exactly once in the document
  order (4.2) and, from section 8 on, exactly once in `tree()`; it is visible unless it is
  deleted or (section 8) has a deleted ancestor.
- **I4 Deletes win** (4.3).
- **I5 Deterministic ties**: ties are broken only by the op id order of 2.3; never by arrival
  order, by the clock at receipt, or by whether an op was local.
- **I6 Buffer** (5.2, 8.4): an op is buffered exactly when some dependency is not applied.
- **I7 Tree** (section 8): following parents from any item reaches the root; there are no
  cycles; every applied item appears exactly once in `tree()`.

## 10. Public interface

10.1 `notesync.Replica(replica_id)`
- `replica_id`, `clock` (int, 2.4)
- `insert(value, after=None)` -> the new op (a dict as in section 3); `op["id"]` is the new
  item id. `after` is an item id or None (start).
- `delete(item)` -> op; `set(item, value)` -> op
- `receive(ops)`: `ops` is an iterable of op dicts (section 5).
- `ops()` -> list of every op the replica knows (applied and buffered), sorted by op id.
- `pending()` -> list of the buffered ops, sorted by op id.
- `values()` -> list of the texts of the visible document, in order.
- `items()` -> list of `[id, text]` pairs of the visible document, in order.

Item arguments accept ids as lists or tuples. A local method that names an item which has not
been applied on this replica raises `ValueError` and creates no op. Returned ids are lists
`[counter, replica]`; returned ops are copies that the caller may modify freely.

10.2 `notesync.push(src, dst)`, `notesync.sync(a, b)` (section 6);
`notesync.save(replica, path)`, `notesync.load(path)` (section 7).

10.3 Added by section 8:
- `insert(value, after=None, parent=None)`: `parent` is an item id or None (root). `after` is
  None (start of the parent's list) or an item that is currently a child of `parent`; the op's
  `after` is that item's current slot id. Otherwise `ValueError`.
- `move(item, parent=None, after=None)` -> op; `parent` and `after` as for insert (the moved
  item itself may be given as `after` when it is currently a child of `parent`). A move that
  would create a cycle is still created and recorded; by 8.5 it has no effect.
- `parent(item)` -> the parent's item id, or None for the root.
- `children(parent=None)` -> item ids of all children of `parent` (deleted ones included), in
  sibling order (8.6).
- `tree()` -> nested list of `{"id", "value", "deleted", "children"}` dicts for all items,
  starting with the children of the root, siblings in order.
- `outline()` -> the same shape without tombstones and without the subtrees of deleted items;
  each dict has `"id"`, `"value"` and `"children"`.
- `values()` and `items()` follow 8.8.
'''

DECISIONS_MD = r'''# Decision log

docs/sync-semantics.md is normative. Entries marked *superseded* are kept for history only.

**D-001 (2025-09) Exchange ops, not snapshots.** Devices send the edits they made (ops), not
whole documents. Snapshots made offline edits on two devices overwrite each other.

**D-002 (2025-09) Lamport ids.** Every op is identified by `[counter, replica]` with a Lamport
counter. Replica ids are fixed device names; tests use `laptop`, `phone` and `server`.

**D-003 (2025-11) Editing a deleted line restores it.** *Superseded by D-007.*

**D-004 (2025-12) Devices send only their own edits; the server merges.** *Superseded by
D-008.*

**D-005 (2026-01) Unknown anchors: append the line at the end so nothing is lost.**
*Superseded by D-009.*

**D-006 (2026-02) Per-peer watermark in push.** Remember the highest counter sent to each peer
and only send newer ops. *Superseded by D-008.*

**D-007 (2026-04) Deletes win.** A delete hides the line for good, whatever set ops arrive
before or after it (spec 4.3). D-003 made deleted lines reappear after syncs with a device that
had edited them offline.

**D-008 (2026-05) Relay everything, remember by op id.** A replica forwards every op it
knows, whoever created it (spec section 6). The phone and the laptop usually only reach the
server, so D-004 left them out of date. Counters are not a valid "already sent" marker
(spec 6.3), which also retires D-006.

**D-009 (2026-06) Out-of-order delivery is normal; buffer by dependency.** An op that arrives
before the op it builds on waits in a buffer until that op arrives (spec 5.2); the buffer is
part of the saved state (spec 7.2). D-005 put such lines in the wrong place for good.

**D-010 (2026-06) RGA ordering with op-id tie-breaks.** Chosen over fractional position keys
(unbounded key growth, interleaving of concurrent runs). Ties are broken by op id only
(spec 2.3, 4.2), never by arrival.

**D-011 (2026-08) Outline mode: nesting and moves.** Approved for the next release (spec
section 8, 10.3). Moves follow Kleppmann et al. 2021: the location of an item is decided by
processing insert and move ops in op id order and skipping a move that would create a cycle.
Rejected alternatives: delete + re-insert (duplicates a line when two devices move it
concurrently and loses its identity) and a plain last-writer-wins parent pointer (concurrent
moves can create cycles that detach whole subtrees).
'''

HANDOFF_MD = r'''# Handoff

- 2026-06: docs/sync-semantics.md brought up to date with D-007 to D-010. The engine has not
  been reviewed against the spec since then.
- Existing tests cover single-device editing, a two-device sync and save/load.
- Section 8 (outline mode) is approved but not started.
'''

INIT_PY = r'''"""notesync: offline-first sync for notes and transcripts edited on several devices.

The contract is docs/sync-semantics.md. Public entry points are re-exported here.
"""
from notesync.replica import Replica
from notesync.sync import push, sync
from notesync.store import load, save

__all__ = ['Replica', 'push', 'sync', 'save', 'load']
'''

MAIN_PY = r'''from notesync.cli import main

raise SystemExit(main())
'''

CLOCK_PY = r'''"""Op ids and the Lamport clock (docs/sync-semantics.md section 2).

Inside the engine an op id is a tuple (counter, replica) so that it can be used as a dict key
and compared with the normal tuple order. On the wire (and in every returned op) it is a JSON
list [counter, replica].
"""


def key(op_id):
    """Internal form of an op id given as a list or a tuple; None stays None."""
    if op_id is None:
        return None
    counter, replica = op_id
    if type(counter) is not int or counter < 1 or not isinstance(replica, str) or not replica:
        raise ValueError(f'bad op id: {op_id!r}')
    return (counter, replica)


def wire(k):
    """Wire form of an internal id."""
    return None if k is None else [k[0], k[1]]


def check_replica_id(replica_id):
    if not isinstance(replica_id, str) or not replica_id:
        raise ValueError('replica id must be a non-empty string')
    return replica_id
'''

OPS_PY = r'''"""Operation constructors (docs/sync-semantics.md section 3).

Ops are plain JSON-compatible dicts. Constructors take internal ids (tuples) and return wire
ops (lists), so an op can be sent, saved or compared without conversion.
"""
import copy

from notesync.clock import key, wire

TYPES = ('insert', 'delete', 'set')


def insert(op_id, after, value):
    return {'type': 'insert', 'id': wire(op_id), 'after': wire(after), 'value': str(value)}


def delete(op_id, target):
    return {'type': 'delete', 'id': wire(op_id), 'target': wire(target)}


def set_value(op_id, target, value):
    return {'type': 'set', 'id': wire(op_id), 'target': wire(target), 'value': str(value)}


def normalize(op):
    """Private copy of a received op with ids in wire form (lists)."""
    if not isinstance(op, dict) or op.get('type') not in TYPES:
        raise ValueError(f'not an op: {op!r}')
    op = copy.deepcopy(op)
    for field in ('id', 'after', 'target'):
        if field in op:
            op[field] = wire(key(op[field]))
    return op


def dependencies(op):
    """Item ids (internal form) that must exist before the op can be applied."""
    if op['type'] == 'insert':
        return [] if op['after'] is None else [key(op['after'])]
    return [key(op['target'])]
'''

SEQUENCE_PY = r'''"""Ordered list of item ids (RGA-style, docs/sync-semantics.md 4.2).

The list holds every item id, tombstones included, in document order. An item is placed after
its anchor; items that were inserted later at the same place stay in front of it.
"""


class Sequence:
    def __init__(self):
        self._order = []

    def __contains__(self, item_id):
        return item_id in self._order

    def __len__(self):
        return len(self._order)

    def add(self, item_id, after):
        if item_id in self._order:
            return
        if after is None:
            i = 0
        elif after in self._order:
            i = self._order.index(after) + 1
        else:
            # Anchor not here yet: keep the line at the end rather than lose it (D-005).
            self._order.append(item_id)
            return
        # Newer inserts at the same place stay first.
        while i < len(self._order) and self._order[i][0] > item_id[0]:
            i += 1
        self._order.insert(i, item_id)

    def order(self):
        return list(self._order)
'''

REPLICA_PY = r'''"""A replica of one document (docs/sync-semantics.md sections 2-5 and 10.1)."""
import copy

from notesync import ops as oplib
from notesync.clock import check_replica_id, key, wire
from notesync.sequence import Sequence


class Item:
    __slots__ = ('value', 'stamp', 'deleted')

    def __init__(self, value, stamp):
        self.value = value
        self.stamp = stamp      # id of the op that wrote value
        self.deleted = False


class Replica:
    def __init__(self, replica_id):
        self.replica_id = check_replica_id(replica_id)
        self.clock = 0
        self._items = {}        # item id -> Item
        self._seq = Sequence()
        self._log = []          # applied ops, in arrival order
        self._seen = set()      # ids of applied ops
        self._pending = []      # deletes that arrived before their item

    # ------------------------------------------------------------------ local edits
    def insert(self, value, after=None):
        anchor = self._known_item(after) if after is not None else None
        return self._local(lambda i: oplib.insert(i, anchor, value))

    def delete(self, item):
        target = self._known_item(item)
        return self._local(lambda i: oplib.delete(i, target))

    def set(self, item, value):
        target = self._known_item(item)
        return self._local(lambda i: oplib.set_value(i, target, value))

    def _known_item(self, item):
        k = key(item)
        if k not in self._items:
            raise ValueError(f'unknown item {item!r}')
        return k

    def _local(self, make):
        self.clock += 1
        op = make((self.clock, self.replica_id))
        self._apply(op)
        self._retry_pending()
        return copy.deepcopy(op)

    # ------------------------------------------------------------------ remote ops
    def receive(self, ops):
        for op in ops:
            self._apply(oplib.normalize(op))

    def _apply(self, op):
        k = key(op['id'])
        if k in self._seen:
            return
        kind = op['type']
        if kind == 'insert':
            self._seq.add(k, key(op['after']))
            self._items[k] = Item(op['value'], k)
        else:
            item = self._items.get(key(op['target']))
            if item is None:
                if kind == 'delete':
                    self._pending.append(op)
                return
            if kind == 'delete':
                item.deleted = True
            elif k[0] >= item.stamp[0]:
                item.value = op['value']
                item.stamp = k
                item.deleted = False    # D-003: editing a line brings it back
        self._seen.add(k)
        self._log.append(op)

    def _retry_pending(self):
        waiting, self._pending = self._pending, []
        for op in waiting:
            self._apply(op)

    # ------------------------------------------------------------------ reads
    def ops(self):
        return sorted(copy.deepcopy(self._log), key=lambda op: key(op['id']))

    def pending(self):
        return sorted(copy.deepcopy(self._pending), key=lambda op: key(op['id']))

    def items(self):
        return [[wire(k), self._items[k].value] for k in self._seq.order()
                if not self._items[k].deleted]

    def values(self):
        return [value for _, value in self.items()]
'''

SYNC_PY = r'''"""Exchanging ops between replicas (docs/sync-semantics.md section 6)."""


def push(src, dst):
    """Send dst the edits it has not seen from src.

    Each device sends its own edits; the server merges (D-004). A per-peer watermark keeps
    repeated syncs cheap (D-006).
    """
    marks = src.__dict__.setdefault('_sent_marks', {})
    mark = marks.get(dst.replica_id, 0)
    batch = [op for op in src.ops()
             if op['id'][1] == src.replica_id and op['id'][0] > mark]
    if batch:
        dst.receive(batch)
        marks[dst.replica_id] = max(op['id'][0] for op in batch)
    return len(batch)


def sync(a, b):
    """Two-way sync: afterwards both replicas know the same ops."""
    return push(a, b) + push(b, a)
'''

STORE_PY = r'''"""Saving and loading replicas (docs/sync-semantics.md section 7)."""
import json
import os
import tempfile
from pathlib import Path

from notesync.replica import Replica

FORMAT = 1


def save(replica, path):
    path = Path(path)
    doc = {'format': FORMAT, 'replica': replica.replica_id, 'clock': replica.clock,
           'ops': replica.ops()}
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.notesync-')
    with os.fdopen(fd, 'w', encoding='utf-8') as out:
        json.dump(doc, out, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def load(path):
    doc = json.loads(Path(path).read_text(encoding='utf-8'))
    if doc.get('format') != FORMAT:
        raise ValueError('unsupported notesync file')
    replica = Replica(doc['replica'])
    replica.receive(doc['ops'])
    replica.clock = max(replica.clock, doc['clock'])
    return replica
'''

RENDER_PY = r'''"""Plain-text views of a replica for the CLI and for debugging."""


def as_text(replica):
    return '\n'.join(replica.values()) + ('\n' if replica.values() else '')


def status(replica):
    return {'replica': replica.replica_id, 'clock': replica.clock,
            'visible': len(replica.values()), 'known_ops': len(replica.ops()),
            'pending': len(replica.pending())}
'''

CLI_PY = r'''"""python3 -m notesync show FILE | status FILE | merge FILE FILE

`merge` loads two saved replicas, syncs them and saves both again.
"""
import json
import sys

from notesync.render import as_text, status
from notesync.store import load, save
from notesync.sync import sync


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) == 2 and args[0] == 'show':
        sys.stdout.write(as_text(load(args[1])))
        return 0
    if len(args) == 2 and args[0] == 'status':
        print(json.dumps(status(load(args[1])), sort_keys=True))
        return 0
    if len(args) == 3 and args[0] == 'merge':
        a, b = load(args[1]), load(args[2])
        sync(a, b)
        save(a, args[1])
        save(b, args[2])
        return 0
    print(__doc__.strip(), file=sys.stderr)
    return 2
'''

VISIBLE = r'''import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from notesync import Replica, load, save, sync

APP = Path(__file__).resolve().parents[1]


class Legacy(unittest.TestCase):
    def test_typing_lines_in_order(self):
        r = Replica('laptop')
        a = r.insert('one')
        b = r.insert('two', after=a['id'])
        r.insert('three', after=b['id'])
        self.assertEqual(r.values(), ['one', 'two', 'three'])
        self.assertEqual(r.clock, 3)
        self.assertEqual([op['id'] for op in r.ops()], [[1, 'laptop'], [2, 'laptop'], [3, 'laptop']])

    def test_insert_at_start_goes_first(self):
        r = Replica('laptop')
        r.insert('second')
        r.insert('first')
        self.assertEqual(r.values(), ['first', 'second'])

    def test_edit_and_delete(self):
        r = Replica('phone')
        a = r.insert('draft')
        b = r.insert('keep', after=a['id'])
        r.set(a['id'], 'final')
        self.assertEqual(r.values(), ['final', 'keep'])
        r.delete(b['id'])
        self.assertEqual(r.items(), [[[1, 'phone'], 'final']])
        with self.assertRaises(ValueError):
            r.set([9, 'phone'], 'nope')

    def test_two_device_sync(self):
        laptop, server = Replica('laptop'), Replica('server')
        a = laptop.insert('agenda')
        laptop.insert('minutes', after=a['id'])
        sync(laptop, server)
        self.assertEqual(server.values(), ['agenda', 'minutes'])
        sync(laptop, server)
        self.assertEqual(server.values(), ['agenda', 'minutes'])
        self.assertEqual(laptop.values(), server.values())

    def test_ops_are_json(self):
        r = Replica('laptop')
        a = r.insert('x')
        r.set(a['id'], 'y')
        copy = Replica('server')
        copy.receive(json.loads(json.dumps(r.ops())))
        self.assertEqual(copy.values(), ['y'])

    def test_save_load_and_cli(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'note.json'
            r = Replica('laptop')
            a = r.insert('hello')
            r.insert('world', after=a['id'])
            save(r, path)
            again = load(path)
            self.assertEqual((again.values(), again.clock), (['hello', 'world'], 2))
            p = subprocess.run([sys.executable, '-m', 'notesync', 'show', str(path)], cwd=APP,
                               capture_output=True, text=True, timeout=30)
            self.assertEqual((p.returncode, p.stdout), (0, 'hello\nworld\n'))
'''

# --------------------------------------------------------------------------- stage 1 reference

SEQUENCE_REF = r'''"""Ordered list of item ids (RGA, docs/sync-semantics.md 4.2).

Every id hangs below its anchor (None is the head) in an insertion tree whose children are
kept newest first; the list order is the pre-order traversal of that tree.
"""


class Sequence:
    def __init__(self):
        self._children = {None: []}

    def __contains__(self, item_id):
        return item_id in self._children

    def __len__(self):
        return len(self._children) - 1

    def add(self, item_id, after):
        if item_id in self._children:
            return
        if after not in self._children:
            raise KeyError(after)
        self._children[item_id] = []
        siblings = self._children[after]
        i = 0
        while i < len(siblings) and siblings[i] > item_id:
            i += 1
        siblings.insert(i, item_id)

    def order(self):
        out, stack = [], list(reversed(self._children[None]))
        while stack:
            item_id = stack.pop()
            out.append(item_id)
            stack.extend(reversed(self._children[item_id]))
        return out
'''

REPLICA_REF1 = r'''"""A replica of one document (docs/sync-semantics.md sections 2-5 and 10.1)."""
import copy

from notesync import ops as oplib
from notesync.clock import check_replica_id, key, wire
from notesync.sequence import Sequence


class Item:
    __slots__ = ('value', 'stamp', 'deleted')

    def __init__(self, value, stamp):
        self.value = value
        self.stamp = stamp      # id of the op that wrote value
        self.deleted = False


class Replica:
    def __init__(self, replica_id):
        self.replica_id = check_replica_id(replica_id)
        self.clock = 0
        self._items = {}        # item id -> Item
        self._seq = Sequence()
        self._known = {}        # op id -> op, applied or buffered (spec 6.1)
        self._pending = {}      # op id -> op waiting for a dependency (spec 5.2)

    # ------------------------------------------------------------------ local edits
    def insert(self, value, after=None):
        anchor = self._known_item(after) if after is not None else None
        return self._local(lambda i: oplib.insert(i, anchor, value))

    def delete(self, item):
        target = self._known_item(item)
        return self._local(lambda i: oplib.delete(i, target))

    def set(self, item, value):
        target = self._known_item(item)
        return self._local(lambda i: oplib.set_value(i, target, value))

    def _known_item(self, item):
        k = key(item)
        if k not in self._items:
            raise ValueError(f'unknown item {item!r}')
        return k

    def _local(self, make):
        self.clock += 1
        op = make((self.clock, self.replica_id))
        self.receive([op])
        return copy.deepcopy(op)

    # ------------------------------------------------------------------ remote ops
    def receive(self, ops):
        for op in ops:
            op = oplib.normalize(op)
            k = key(op['id'])
            self.clock = max(self.clock, k[0])
            if k in self._known:
                continue
            self._known[k] = op
            self._pending[k] = op
        self._drain()

    def _ready(self, op):
        return all(dep in self._items for dep in oplib.dependencies(op))

    def _drain(self):
        progress = True
        while progress:
            progress = False
            for k in sorted(self._pending):
                op = self._pending[k]
                if self._ready(op):
                    del self._pending[k]
                    self._apply(k, op)
                    progress = True

    def _apply(self, k, op):
        kind = op['type']
        if kind == 'insert':
            self._seq.add(k, key(op['after']))
            self._items[k] = Item(op['value'], k)
            return
        item = self._items[key(op['target'])]
        if kind == 'delete':
            item.deleted = True
        elif k > item.stamp:
            item.value = op['value']
            item.stamp = k

    # ------------------------------------------------------------------ reads
    def ops(self):
        return [copy.deepcopy(self._known[k]) for k in sorted(self._known)]

    def pending(self):
        return [copy.deepcopy(self._pending[k]) for k in sorted(self._pending)]

    def knows(self, op_id):
        return key(op_id) in self._known

    def items(self):
        return [[wire(k), self._items[k].value] for k in self._seq.order()
                if not self._items[k].deleted]

    def values(self):
        return [value for _, value in self.items()]
'''

SYNC_REF = r'''"""Exchanging ops between replicas (docs/sync-semantics.md section 6)."""


def push(src, dst):
    """Make dst receive every op src knows (own, relayed or buffered) that dst lacks."""
    batch = [op for op in src.ops() if not dst.knows(op['id'])]
    if batch:
        dst.receive(batch)
    return len(batch)


def sync(a, b):
    """Two-way sync: afterwards both replicas know the same ops."""
    return push(a, b) + push(b, a)
'''

HANDOFF_REF1 = r'''# Handoff

- 2026-06: docs/sync-semantics.md brought up to date with D-007 to D-010.
- 2026-09: engine reviewed against sections 2-7 and fixed: RGA insertion tree with op-id
  tie-breaks, dependency buffer (applied on arrival of dependencies, saved with the replica),
  idempotent receive, Lamport clock observes every received op, last-writer-wins text by op
  id, deletes win, push relays every known op and remembers nothing by counter.
- Section 8 (outline mode) is approved but not started.
'''

# --------------------------------------------------------------------------- stage 2 reference

OPS_REF2 = r'''"""Operation constructors (docs/sync-semantics.md sections 3 and 8.3).

Ops are plain JSON-compatible dicts. Constructors take internal ids (tuples) and return wire
ops (lists), so an op can be sent, saved or compared without conversion.
"""
import copy

from notesync.clock import key, wire

TYPES = ('insert', 'delete', 'set', 'move')


def insert(op_id, after, value, parent=None):
    return {'type': 'insert', 'id': wire(op_id), 'parent': wire(parent), 'after': wire(after),
            'value': str(value)}


def delete(op_id, target):
    return {'type': 'delete', 'id': wire(op_id), 'target': wire(target)}


def set_value(op_id, target, value):
    return {'type': 'set', 'id': wire(op_id), 'target': wire(target), 'value': str(value)}


def move(op_id, target, parent, after):
    return {'type': 'move', 'id': wire(op_id), 'target': wire(target), 'parent': wire(parent),
            'after': wire(after)}


def normalize(op):
    """Private copy of a received op with ids in wire form (lists)."""
    if not isinstance(op, dict) or op.get('type') not in TYPES:
        raise ValueError(f'not an op: {op!r}')
    op = copy.deepcopy(op)
    if op['type'] == 'insert':
        op.setdefault('parent', None)
    for field in ('id', 'after', 'target', 'parent'):
        if field in op:
            op[field] = wire(key(op[field]))
    return op


def requirements(op):
    """(items, slot) that must be applied first (spec 5.2, 8.4); slot is (parent, slot id)."""
    kind = op['type']
    items = [] if kind == 'insert' else [key(op['target'])]
    if kind in ('insert', 'move'):
        parent = key(op['parent'])
        if parent is not None:
            items.append(parent)
        after = key(op['after'])
        return items, (None if after is None else (parent, after))
    return items, None
'''

REPLICA_REF2 = r'''"""A replica of one document (docs/sync-semantics.md sections 2-5, 8 and 10)."""
import copy

from notesync import ops as oplib
from notesync.clock import check_replica_id, key, wire
from notesync.sequence import Sequence


class Item:
    __slots__ = ('value', 'stamp', 'deleted')

    def __init__(self, value, stamp):
        self.value = value
        self.stamp = stamp      # id of the op that wrote value
        self.deleted = False


class Layout:
    """Result of spec 8.5: parent and occupied slot of every item, children in order."""

    def __init__(self, parent, slot, children):
        self.parent = parent        # item -> parent item or None
        self.slot = slot            # item -> slot id it occupies
        self.children = children    # parent (None = root) -> [item, ...]


class Replica:
    def __init__(self, replica_id):
        self.replica_id = check_replica_id(replica_id)
        self.clock = 0
        self._items = {}        # item id -> Item
        self._slots = {None: Sequence()}    # parent (None = root) -> Sequence of slot ids
        self._location_ops = []  # (op id, target item, parent) of applied inserts and moves
        self._layout = None
        self._known = {}        # op id -> op, applied or buffered (spec 6.1)
        self._pending = {}      # op id -> op waiting for a dependency (spec 5.2, 8.4)

    # ------------------------------------------------------------------ local edits
    def insert(self, value, after=None, parent=None):
        p = self._known_item(parent) if parent is not None else None
        anchor = self._anchor(p, after)
        return self._local(lambda i: oplib.insert(i, anchor, value, p))

    def move(self, item, parent=None, after=None):
        target = self._known_item(item)
        p = self._known_item(parent) if parent is not None else None
        anchor = self._anchor(p, after)
        return self._local(lambda i: oplib.move(i, target, p, anchor))

    def delete(self, item):
        target = self._known_item(item)
        return self._local(lambda i: oplib.delete(i, target))

    def set(self, item, value):
        target = self._known_item(item)
        return self._local(lambda i: oplib.set_value(i, target, value))

    def _known_item(self, item):
        k = key(item)
        if k not in self._items:
            raise ValueError(f'unknown item {item!r}')
        return k

    def _anchor(self, parent, after):
        """Slot id for `after`, which must currently be a child of `parent` (spec 10.3)."""
        if after is None:
            return None
        k = self._known_item(after)
        layout = self.layout()
        if layout.parent[k] != parent:
            raise ValueError(f'{after!r} is not a child of {parent!r}')
        return layout.slot[k]

    def _local(self, make):
        self.clock += 1
        op = make((self.clock, self.replica_id))
        self.receive([op])
        return copy.deepcopy(op)

    # ------------------------------------------------------------------ remote ops
    def receive(self, ops):
        for op in ops:
            op = oplib.normalize(op)
            k = key(op['id'])
            self.clock = max(self.clock, k[0])
            if k in self._known:
                continue
            self._known[k] = op
            self._pending[k] = op
        self._drain()

    def _ready(self, op):
        items, slot = oplib.requirements(op)
        if not all(i in self._items for i in items):
            return False
        return slot is None or slot[1] in self._slots.get(slot[0], ())

    def _drain(self):
        progress = True
        while progress:
            progress = False
            for k in sorted(self._pending):
                op = self._pending[k]
                if self._ready(op):
                    del self._pending[k]
                    self._apply(k, op)
                    progress = True

    def _apply(self, k, op):
        kind = op['type']
        if kind in ('insert', 'move'):
            parent = key(op['parent'])
            self._slots.setdefault(parent, Sequence()).add(k, key(op['after']))
            target = k if kind == 'insert' else key(op['target'])
            self._location_ops.append((k, target, parent))
            self._layout = None
            if kind == 'insert':
                self._items[k] = Item(op['value'], k)
            return
        item = self._items[key(op['target'])]
        if kind == 'delete':
            item.deleted = True
        elif k > item.stamp:
            item.value = op['value']
            item.stamp = k

    # ------------------------------------------------------------------ tree (spec 8.5, 8.6)
    def layout(self):
        if self._layout is not None:
            return self._layout
        parent, slot = {}, {}
        for k, target, p in sorted(self._location_ops):
            if k != target and self._is_self_or_descendant(p, target, parent):
                continue            # would create a cycle: skipped (8.5)
            parent[target], slot[target] = p, k
        occupant = {s: item for item, s in slot.items()}
        children = {p: [occupant[s] for s in seq.order() if s in occupant]
                    for p, seq in self._slots.items()}
        self._layout = Layout(parent, slot, children)
        return self._layout

    @staticmethod
    def _is_self_or_descendant(node, ancestor, parent):
        while node is not None:
            if node == ancestor:
                return True
            node = parent[node]
        return False

    # ------------------------------------------------------------------ reads
    def ops(self):
        return [copy.deepcopy(self._known[k]) for k in sorted(self._known)]

    def pending(self):
        return [copy.deepcopy(self._pending[k]) for k in sorted(self._pending)]

    def knows(self, op_id):
        return key(op_id) in self._known

    def parent(self, item):
        return wire(self.layout().parent[self._known_item(item)])

    def children(self, parent=None):
        p = self._known_item(parent) if parent is not None else None
        return [wire(k) for k in self.layout().children.get(p, [])]

    def tree(self):
        layout = self.layout()

        def build(p):
            return [{'id': wire(k), 'value': self._items[k].value, 'deleted': self._items[k].deleted,
                     'children': build(k)} for k in layout.children.get(p, [])]
        return build(None)

    def outline(self):
        layout = self.layout()

        def build(p):
            return [{'id': wire(k), 'value': self._items[k].value, 'children': build(k)}
                    for k in layout.children.get(p, []) if not self._items[k].deleted]
        return build(None)

    def items(self):
        out = []

        def walk(nodes):
            for node in nodes:
                out.append([node['id'], node['value']])
                walk(node['children'])
        walk(self.outline())
        return out

    def values(self):
        return [value for _, value in self.items()]
'''

SPEC_MD_2 = sub(sub(SPEC_MD, """Sections 1-7, 9 and 10.1-10.2 describe the shipped engine. Section 8 and 10.3 are the approved
outline design for the next release; they are not implemented yet.""", """All sections, including the outline design of section 8 and 10.3, describe the shipped
engine."""), '## 8. Outline: nesting and moves (approved design, next release)', '## 8. Outline: nesting and moves')

HANDOFF_REF2 = sub(HANDOFF_REF1, """- Section 8 (outline mode) is approved but not started.
""", """- 2026-09: outline mode (spec section 8, 10.3) implemented: parent/after slots on insert, move
  op, dependency buffer for parents and anchor slots, tree rebuilt by replaying location ops in
  op id order with cycle skipping, deleted subtrees hidden from outline/values/items.
""")

# --------------------------------------------------------------------------- hidden tests

HIDDEN_COMMON = r'''import itertools
import json
import os
import random
import tempfile
import unittest
from pathlib import Path

import notesync
from notesync import Replica, load, push, save, sync

NAMES = ('laptop', 'phone', 'server')


def wire(ops):
    """Ops travel as JSON (spec section 3): ids arrive as lists."""
    return json.loads(json.dumps(list(ops)))


def nid(i):
    return None if i is None else [i[0], i[1]]


def kid(i):
    return None if i is None else (i[0], i[1])


def ids(ops):
    return sorted(kid(op['id']) for op in ops)


def items(r):
    return [[nid(i), v] for i, v in r.items()]


def orders(n, dup=()):
    """Every distinct delivery order of ops 0..n-1 plus the duplicated indexes in dup."""
    return sorted(set(itertools.permutations(list(range(n)) + list(dup))))


def spec_model(ops):
    """Independent model of sections 4 and 8 for a complete set of ops.

    Returns (tree, visible items) where tree is the tree() shape of 10.3 (for section-4-only
    ops every item sits at the root in document order).
    """
    ops = {kid(op['id']): op for op in ops}
    text, deleted, slots, locs = {}, set(), {}, []
    for k in sorted(ops):
        op = ops[k]
        if op['type'] == 'insert':
            text[k] = (k, op['value'])
            parent = kid(op.get('parent'))
            slots[k] = (parent, kid(op['after']))
            locs.append((k, k, parent))
        elif op['type'] == 'move':
            parent = kid(op['parent'])
            slots[k] = (parent, kid(op['after']))
            locs.append((k, kid(op['target']), parent))
    for k in sorted(ops):
        op = ops[k]
        if op['type'] == 'delete':
            deleted.add(kid(op['target']))
        elif op['type'] == 'set':
            t = kid(op['target'])
            if k > text[t][0]:
                text[t] = (k, op['value'])
    where, slot_of = {}, {}
    for k, target, parent in sorted(locs):
        if k != target:
            a = parent
            while a is not None and a != target:
                a = where[a]
            if a == target:
                continue
        where[target], slot_of[target] = parent, k
    occupant = {s: t for t, s in slot_of.items()}

    def slot_order(parent):
        below = {}
        for s, (p, after) in slots.items():
            if p == parent:
                below.setdefault(after, []).append(s)
        out = []

        def walk(anchor):
            for s in sorted(below.get(anchor, []), reverse=True):
                out.append(s)
                walk(s)
        walk(None)
        return out

    def build(parent):
        return [{'id': nid(t), 'value': text[t][1], 'deleted': t in deleted, 'children': build(t)}
                for t in (occupant.get(s) for s in slot_order(parent)) if t is not None]

    tree = build(None)
    visible = []

    def flat(nodes):
        for n in nodes:
            if not n['deleted']:
                visible.append([n['id'], n['value']])
                flat(n['children'])
    flat(tree)
    return tree, visible


def closure(ops, has_parent=False):
    """Ids of the ops that can be applied from this set (spec 5.2 / 8.4)."""
    applied_items, applied_slots, done = set(), set(), set()
    progress = True
    while progress:
        progress = False
        for op in ops:
            k = kid(op['id'])
            if k in done:
                continue
            need_items = []
            if op['type'] in ('delete', 'set', 'move'):
                need_items.append(kid(op['target']))
            if op.get('parent') is not None:
                need_items.append(kid(op['parent']))
            after = kid(op.get('after'))
            ok = all(i in applied_items for i in need_items) and (after is None or after in applied_slots)
            if ok:
                done.add(k)
                if op['type'] == 'insert':
                    applied_items.add(k)
                if op['type'] in ('insert', 'move'):
                    applied_slots.add(k)
                progress = True
    return done


def fresh(ops, name='server'):
    """A new replica that receives the ops one receive() call at a time, in this order."""
    r = Replica(name)
    for op in ops:
        r.receive(wire([op]))
    return r
'''

HIDDEN_STAGE1 = r'''

class SyncContract(unittest.TestCase):
    def setUp(self):
        self.r = {n: Replica(n) for n in NAMES}

    def share(self, *ops):
        for r in self.r.values():
            r.receive(wire(ops))

    # docs/sync-semantics.md 4.2 example 4.2a, 2.3 (tie-break by replica id), 3 (ids as lists)
    def test_example_concurrent_inserts_at_start(self):
        a = self.r['laptop'].insert('apple')
        b = self.r['phone'].insert('banana')
        self.assertEqual((a['id'], b['id']), ([1, 'laptop'], [1, 'phone']))
        for order in ([a, b], [b, a], [b, a, b, a]):
            self.assertEqual(fresh(order).values(), ['banana', 'apple'])
        sync(self.r['laptop'], self.r['phone'])
        self.assertEqual(self.r['laptop'].values(), ['banana', 'apple'])
        self.assertEqual(self.r['phone'].values(), ['banana', 'apple'])

    # docs/sync-semantics.md 4.2 example 4.2b (runs stay together, pre-order traversal)
    def test_example_runs_stay_together(self):
        intro = self.r['server'].insert('intro')
        self.share(intro)
        l1 = self.r['laptop'].insert('l1', after=intro['id'])
        l2 = self.r['laptop'].insert('l2', after=l1['id'])
        p1 = self.r['phone'].insert('p1', after=intro['id'])
        self.assertEqual((l1['id'], l2['id'], p1['id']), ([2, 'laptop'], [3, 'laptop'], [2, 'phone']))
        for order in orders(3):
            ops = [intro] + [[l1, l2, p1][i] for i in order]
            self.assertEqual(fresh(ops).values(), ['intro', 'p1', 'l1', 'l2'], order)

    # docs/sync-semantics.md 2.4 (clock observes every received op, buffered or duplicate), 5.5
    def test_lamport_clock(self):
        s = self.r['server']
        x = s.insert('x')
        s.insert('y', after=x['id'])
        late = s.insert('z', after=x['id'])          # [3, server], anchor x
        phone = self.r['phone']
        phone.receive(wire([late]))                   # buffered: x unknown
        self.assertEqual(phone.clock, 3)
        self.assertEqual(ids(phone.pending()), [(3, 'server')])
        phone.receive(wire([late, late]))
        self.assertEqual(phone.clock, 3)
        with self.assertRaises(ValueError):
            phone.delete(late['id'])                  # not applied yet: no op
        self.assertEqual(phone.clock, 3)
        own = phone.insert('mine')
        self.assertEqual(own['id'], [4, 'phone'])
        self.assertIn((4, 'phone'), ids(phone.ops()))
        laptop = self.r['laptop']
        laptop.receive(wire(s.ops()))
        laptop.receive(wire([own]))
        self.assertEqual(laptop.insert('next', after=x['id'])['id'], [5, 'laptop'])

    # docs/sync-semantics.md 4.3 (deletes win), 4.4 (text: newest op id wins, not arrival),
    # 5.1-5.4, I4, I5
    def test_deletes_win_and_last_writer_by_op_id(self):
        s, lap, ph = self.r['server'], self.r['laptop'], self.r['phone']
        x = s.insert('x')
        y = s.insert('y', after=x['id'])
        self.share(x, y)
        set_l = lap.set(x['id'], 'x from laptop')     # [3, laptop]
        set_p = ph.set(x['id'], 'x from phone')       # [3, phone] wins the tie
        del_s = s.delete(y['id'])                     # [3, server]
        set_l2 = lap.set(y['id'], 'y edited')         # [4, laptop] newer than the delete
        ops = [set_l, set_p, del_s, set_l2, x, y]
        for order in orders(6, dup=(2,)):
            r = fresh([ops[i] for i in order], 'laptop')
            self.assertEqual(items(r), [[[1, 'server'], 'x from phone']], order)
            self.assertEqual(r.pending(), [])
        again = fresh(ops)
        again.receive(wire([set_l]))
        again.receive(wire([y, x]))
        self.assertEqual(again.values(), ['x from phone'])

    # docs/sync-semantics.md 5.2 (buffer until dependencies, released transitively),
    # 5.3 (duplicates), 5.4 (convergence), 4.2, 4.3, 4.4; invariants I1-I6
    def test_every_delivery_order_with_duplicates(self):
        a, b, c = self.r['laptop'], self.r['phone'], self.r['server']
        x = a.insert('x')                             # [1, laptop]
        b.receive(wire([x]))
        y = b.insert('y', after=x['id'])              # [2, phone]
        d = b.delete(x['id'])                         # [3, phone]
        c.receive(wire([x, y]))
        sy = c.set(y['id'], 'y2')                     # [3, server]
        z = c.insert('z', after=y['id'])              # [4, server]
        w = a.insert('w', after=x['id'])              # [2, laptop]
        ops = [x, y, d, sy, z, w]
        expected = [[[2, 'phone'], 'y2'], [[4, 'server'], 'z'], [[2, 'laptop'], 'w']]
        self.assertEqual(spec_model(ops)[1], expected)
        count = 0
        for order in orders(6, dup=(2,)):
            r = Replica('laptop')
            seen = []
            for i in order:
                r.receive(wire([ops[i]]))
                seen.append(ops[i])
                ready = closure(seen)
                self.assertEqual(ids(r.pending()), sorted(set(ids(seen)) - ready), order)
                self.assertEqual(items(r), spec_model([op for op in seen if kid(op['id']) in ready])[1], order)
            self.assertEqual(items(r), expected, order)
            self.assertEqual(ids(r.ops()), ids(ops))
            self.assertEqual(r.clock, 4)
            r.receive(wire(reversed(ops)))
            r.receive(wire([x, y]))
            self.assertEqual(items(r), expected, order)
            count += 1
        self.assertEqual(count, 2520)

    # docs/sync-semantics.md 5.2-5.4 with concurrent edits from three replicas; 4.2 example
    # 4.2b shape, 4.3, 4.4; invariants I1-I5
    def test_three_replica_concurrent_session_all_orders(self):
        s, lap, ph = self.r['server'], self.r['laptop'], self.r['phone']
        intro = s.insert('intro')
        body = s.insert('body', after=intro['id'])
        self.share(intro, body)
        l1 = lap.insert('l1', after=intro['id'])      # [3, laptop]
        l2 = lap.insert('l2', after=l1['id'])         # [4, laptop]
        p1 = ph.insert('p1', after=intro['id'])       # [3, phone]
        pd = ph.delete(body['id'])                    # [4, phone]
        s1 = s.set(body['id'], 'body v2')             # [3, server]
        s2 = s.insert('s2', after=body['id'])         # [4, server]
        ops = [l1, l2, p1, pd, s1, s2]
        expected = ['intro', 'p1', 'l1', 'l2', 's2']
        for order in orders(6, dup=(0,)):
            receivers = [Replica(n) for n in NAMES]
            for k, r in enumerate(receivers):
                r.receive(wire([intro, body]))
                seq = [ops[i] for i in order]
                r.receive(wire(seq[k:] + seq[:k]))    # each receiver gets a rotation
            receivers.append(fresh([intro, body] + [ops[i] for i in order]))
            for r in receivers:
                self.assertEqual(r.values(), expected, order)
                self.assertEqual(r.pending(), [])
        self.assertEqual(spec_model([intro, body] + ops)[1][0], [[1, 'server'], 'intro'])

    # docs/sync-semantics.md 5.2-5.4 on generated sessions, checked against the model of
    # section 4; invariants I1-I6
    def test_generated_sessions_all_orders(self):
        for seed in range(6):
            rnd = random.Random(seed)
            reps = {n: Replica(n) for n in NAMES}
            base = []
            for i in range(2):
                vis = reps['server'].items()
                base.append(reps['server'].insert(f'b{i}', after=vis[-1][0] if vis else None))
            for r in reps.values():
                r.receive(wire(base))

            def act(r, tag):
                vis = r.items()
                roll = rnd.random()
                if vis and roll < 0.2:
                    return r.delete(rnd.choice(vis)[0])
                if vis and roll < 0.4:
                    return r.set(rnd.choice(vis)[0], tag + '*')
                return r.insert(tag, after=rnd.choice([None] + [i for i, _ in vis]))

            new = []
            for n in NAMES:
                new.append(act(reps[n], n[0] + '1'))
            src, dst = rnd.sample(NAMES, 2)
            reps[dst].receive(wire(reps[src].ops()))
            for n in NAMES:
                new.append(act(reps[n], n[0] + '2'))
            expected = spec_model(base + new)[1]
            for order in orders(len(new)):
                r = fresh(base + [new[i] for i in order])
                self.assertEqual(items(r), expected, (seed, order))
                self.assertEqual(r.pending(), [])

    # docs/sync-semantics.md 6.1-6.3 (relay through the server, nothing remembered by counter),
    # 5.4; invariants I1, I3
    def test_sync_schedules_relay_everything(self):
        steps = [('laptop', 'server'), ('server', 'laptop'), ('phone', 'server'), ('server', 'phone')]
        for sched in itertools.product(range(4), repeat=5):
            reps = {n: Replica(n) for n in NAMES}
            for n in NAMES:
                reps[n].insert(n + '-a')
            for j, step in enumerate(sched):
                src, dst = steps[step]
                push(reps[src], reps[dst])
                if j == 1:
                    for n in NAMES:
                        vis = reps[n].items()
                        reps[n].insert(n + '-b', after=vis[0][0])
                        if len(vis) > 1:
                            reps[n].delete(vis[-1][0])
            sync(reps['laptop'], reps['server'])
            sync(reps['phone'], reps['server'])
            sync(reps['laptop'], reps['server'])
            everything = {kid(op['id']): op for r in reps.values() for op in r.ops()}
            expected = spec_model(list(everything.values()))[1]
            for r in reps.values():
                self.assertEqual(ids(r.ops()), sorted(everything), sched)
                self.assertEqual(items(r), expected, sched)
            self.assertGreaterEqual(len(everything), 6)

    # docs/sync-semantics.md 6.1 (buffered ops are known and relayed), 7.1-7.2 (buffer is saved)
    def test_buffered_ops_are_relayed_and_saved(self):
        s = self.r['server']
        x = s.insert('x')
        y = s.insert('y', after=x['id'])
        dl = s.delete(x['id'])
        phone, laptop = self.r['phone'], self.r['laptop']
        phone.receive(wire([y, dl]))
        self.assertEqual(ids(phone.pending()), [(2, 'server'), (3, 'server')])
        sync(phone, laptop)
        self.assertEqual(ids(laptop.pending()), [(2, 'server'), (3, 'server')])
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'phone.json'
            save(phone, path)
            back = load(path)
        self.assertEqual((back.replica_id, back.clock), ('phone', 3))
        self.assertEqual(ids(back.pending()), [(2, 'server'), (3, 'server')])
        self.assertEqual(ids(back.ops()), ids(phone.ops()))
        back.receive(wire([x]))
        self.assertEqual(back.values(), ['y'])
        self.assertEqual(back.pending(), [])
        self.assertEqual(back.insert('n')['id'], [4, 'phone'])
        push(back, laptop)
        self.assertEqual(laptop.values(), ['n', 'y'])
'''

HIDDEN_STAGE2 = r'''

def strip(nodes):
    return [{'id': nid(n['id']), 'value': n['value'], 'deleted': bool(n['deleted']),
             'children': strip(n['children'])} for n in nodes]


def visible_outline(tree):
    return [{'id': n['id'], 'value': n['value'], 'children': visible_outline(n['children'])}
            for n in tree if not n['deleted']]


def strip_outline(nodes):
    return [{'id': nid(n['id']), 'value': n['value'], 'children': strip_outline(n['children'])}
            for n in nodes]


def shape(nodes):
    """Compact (value, children) form used for readable expectations."""
    return [(n['value'], shape(n['children'])) for n in nodes]


class OutlineContract(unittest.TestCase):
    def setUp(self):
        self.r = {n: Replica(n) for n in NAMES}

    def share(self, *ops):
        for r in self.r.values():
            r.receive(wire(ops))

    def check_tree(self, r, applied_items, msg=None):
        """I3/I7: every applied item exactly once in tree(), parents agree, no cycles."""
        seen, parents = [], {}

        def walk(nodes, parent):
            for n in nodes:
                seen.append(kid(n['id']))
                parents[kid(n['id'])] = parent
                self.assertEqual(kid(r.parent(n['id'])), parent, msg)
                self.assertEqual([kid(c) for c in r.children(n['id'])], [kid(c['id']) for c in n['children']], msg)
                walk(n['children'], kid(n['id']))
        tree = r.tree()
        walk(tree, None)
        self.assertEqual(sorted(seen), sorted(applied_items), msg)
        self.assertEqual(len(seen), len(set(seen)), msg)
        self.assertEqual([kid(c) for c in r.children()], [kid(n['id']) for n in tree], msg)
        for k in seen:
            hops, a = 0, k
            while a is not None:
                a, hops = parents[a], hops + 1
                self.assertLessEqual(hops, len(seen), msg)
        return tree

    # docs/sync-semantics.md 8.5 example 8.5a (concurrent moves forming a cycle are skipped)
    def test_example_cycle_is_skipped(self):
        s, lap, ph = self.r['server'], self.r['laptop'], self.r['phone']
        a = s.insert('A')
        b = s.insert('B', after=a['id'])
        self.share(a, b)
        m1 = lap.move(a['id'], parent=b['id'])
        m2 = ph.move(b['id'], parent=a['id'])
        self.assertEqual((m1['id'], m2['id']), ([3, 'laptop'], [3, 'phone']))
        self.assertEqual((m1['type'], m1['target'], m1['parent'], m1['after']), ('move', [1, 'server'], [2, 'server'], None))
        for order in ([m1, m2], [m2, m1], [m2, m2, m1]):
            r = fresh([a, b] + order)
            self.assertEqual(shape(r.outline()), [('B', [('A', [])])])
            self.assertEqual(nid(r.parent(a['id'])), [2, 'server'])
            self.assertIsNone(r.parent(b['id']))
            self.assertEqual(r.values(), ['B', 'A'])
        sync(lap, ph)
        self.assertEqual(shape(lap.outline()), shape(ph.outline()))

    # docs/sync-semantics.md 8.6 example 8.6a (sibling order follows slot order; concurrent
    # moves to the same place tie-break by op id, 8.2 and 2.3)
    def test_example_sibling_order_after_moves(self):
        s, lap, ph = self.r['server'], self.r['laptop'], self.r['phone']
        x = s.insert('X')
        y = s.insert('Y', after=x['id'])
        z = s.insert('Z', after=y['id'])
        self.share(x, y, z)
        mz = lap.move(z['id'])                          # [4, laptop] to the start
        mx = ph.move(x['id'], after=z['id'])            # [4, phone] after Z's slot
        self.assertEqual((mx['after'], mz['after']), ([3, 'server'], None))
        for order in orders(2, dup=(0,)):
            r = fresh([x, y, z] + [[mz, mx][i] for i in order])
            self.assertEqual(r.values(), ['Z', 'Y', 'X'], order)
        my = s.move(y['id'])                            # [4, server] also to the start
        for order in orders(3):
            r = fresh([x, y, z] + [[mz, mx, my][i] for i in order])
            self.assertEqual(r.values(), ['Y', 'Z', 'X'], order)
            self.assertEqual([kid(c) for c in r.children()], [(2, 'server'), (3, 'server'), (1, 'server')])

    # docs/sync-semantics.md 8.3 (after is a slot id), 10.3 (insert/move after the current
    # slot of a child), 8.2
    def test_anchors_are_current_slots(self):
        s = self.r['server']
        p = s.insert('P')
        q = s.insert('Q', after=p['id'])
        k = s.insert('k', parent=p['id'])
        self.assertEqual((k['parent'], k['after']), ([1, 'server'], None))
        mk = s.move(k['id'], parent=q['id'])
        n = s.insert('n', parent=q['id'], after=k['id'])
        self.assertEqual(n['after'], mk['id'])
        with self.assertRaises(ValueError):
            s.insert('bad', parent=p['id'], after=k['id'])
        with self.assertRaises(ValueError):
            s.move(p['id'], parent=q['id'], after=p['id'])
        same = s.move(k['id'], parent=q['id'], after=k['id'])
        self.assertEqual(same['after'], mk['id'])
        self.assertEqual(shape(s.outline()), [('P', []), ('Q', [('k', []), ('n', [])])])
        for order in orders(6):
            ops = [p, q, k, mk, n, same]
            r = fresh([ops[i] for i in order])
            self.assertEqual(shape(r.outline()), [('P', []), ('Q', [('k', []), ('n', [])])], order)

    # docs/sync-semantics.md 8.5 (location = newest non-skipped move by op id, whatever the
    # arrival order), 8.4 (buffer until target, parent and anchor slot), 5.3, 5.4; I1-I3, I6, I7
    def test_concurrent_moves_every_delivery_order(self):
        s, lap, ph = self.r['server'], self.r['laptop'], self.r['phone']
        a = s.insert('A')
        b = s.insert('B', after=a['id'])
        c = s.insert('C', after=b['id'])
        self.share(a, b, c)
        m1 = lap.move(a['id'], parent=b['id'])          # [4, laptop]
        m2 = ph.move(b['id'], parent=a['id'])           # [4, phone]: cycle, skipped
        m3 = s.move(c['id'], parent=a['id'])            # [4, server]
        i1 = lap.insert('a1', parent=a['id'])           # [5, laptop]
        m4 = s.move(a['id'])                            # [5, server]: A back to the start
        i2 = lap.insert('a2', parent=a['id'], after=i1['id'])   # [6, laptop]
        ops = [m1, m2, m3, i1, m4, i2]
        expected = [('A', [('a1', []), ('a2', []), ('C', [])]), ('B', [])]
        model_tree = spec_model([a, b, c] + ops)[0]
        self.assertEqual(shape(model_tree), expected)
        for order in orders(6, dup=(1,)):
            r = fresh([a, b, c], 'phone')
            seen = [a, b, c]
            for i in order:
                r.receive(wire([ops[i]]))
                seen.append(ops[i])
                ready = closure(seen)
                self.assertEqual(ids(r.pending()), sorted(set(ids(seen)) - ready), order)
            tree = self.check_tree(r, [(1, 'server'), (2, 'server'), (3, 'server'), (5, 'laptop'), (6, 'laptop')], order)
            self.assertEqual(strip(tree), model_tree, order)
            self.assertEqual(r.values(), ['A', 'a1', 'a2', 'C', 'B'], order)

    # docs/sync-semantics.md 8.7 (deleted subtree hidden, moving out restores visibility),
    # 4.3 (deletes win over set), 8.4 (insert under a parent waits for the parent); I3, I4
    def test_delete_hides_subtree_and_move_out_restores(self):
        s, lap, ph = self.r['server'], self.r['laptop'], self.r['phone']
        p = s.insert('P')
        q = s.insert('Q', after=p['id'])
        self.share(p, q)
        ik = lap.insert('k', parent=p['id'])            # [3, laptop]
        mk = lap.move(ik['id'], parent=q['id'])          # [4, laptop]
        dp = ph.delete(p['id'])                          # [3, phone]
        ix = ph.insert('x', parent=p['id'])              # [4, phone]
        sp = s.set(p['id'], 'P2')                        # [3, server]
        ops = [ik, mk, dp, ix, sp, p]
        for order in orders(6, dup=(1,)):
            r = fresh([q], 'laptop')
            seen = [q]
            for i in order:
                r.receive(wire([ops[i]]))
                seen.append(ops[i])
                self.assertEqual(ids(r.pending()), sorted(set(ids(seen)) - closure(seen)), order)
            tree = self.check_tree(r, [(1, 'server'), (2, 'server'), (3, 'laptop'), (4, 'phone')], order)
            self.assertEqual(strip(tree), [
                {'id': [1, 'server'], 'value': 'P2', 'deleted': True, 'children': [
                    {'id': [4, 'phone'], 'value': 'x', 'deleted': False, 'children': []}]},
                {'id': [2, 'server'], 'value': 'Q', 'deleted': False, 'children': [
                    {'id': [3, 'laptop'], 'value': 'k', 'deleted': False, 'children': []}]}], order)
            self.assertEqual(strip_outline(r.outline()), visible_outline(strip(tree)))
            self.assertEqual(r.values(), ['Q', 'k'], order)
            self.assertEqual(items(r), [[[2, 'server'], 'Q'], [[3, 'laptop'], 'k']], order)
        r = fresh([p, q, dp, ix, ik], 'laptop')
        self.assertEqual(r.values(), ['Q'])
        mo = r.move(ix['id'], parent=q['id'])
        self.assertEqual(r.values(), ['Q', 'x'])
        r.move(ix['id'], parent=p['id'])
        self.assertEqual(r.values(), ['Q'])
        self.assertEqual(mo['id'], [5, 'laptop'])

    # docs/sync-semantics.md 8.4 (moves and inserts wait for target, parent and anchor slot,
    # released transitively), 8.2/8.5 (a skipped move's slot still exists as an anchor),
    # 7.2 (buffer saved), 10.3, example 8.5a
    def test_skipped_move_slot_anchors_and_buffering(self):
        s, lap, ph = self.r['server'], self.r['laptop'], self.r['phone']
        a = s.insert('A')
        b = s.insert('B', after=a['id'])
        self.share(a, b)
        m1 = lap.move(a['id'], parent=b['id'])           # [3, laptop]
        m2 = ph.move(b['id'], parent=a['id'])            # [3, phone]: skipped once m1 is known
        n = ph.insert('n', parent=a['id'], after=b['id'])   # [4, phone], after slot [3, phone]
        self.assertEqual(n['after'], [3, 'phone'])
        self.assertEqual(shape(ph.outline()), [('A', [('B', []), ('n', [])])])
        lap.receive(wire([m2, n]))
        self.assertEqual(shape(lap.outline()), [('B', [('A', [('n', [])])])])
        mc = lap.move(n['id'], after=b['id'])            # [5, laptop], root after slot [2, server]
        self.assertEqual((mc['parent'], mc['after']), (None, [2, 'server']))
        r = Replica('server')
        for count, op in enumerate([mc, n, m2, m1, b], 1):
            r.receive(wire([op]))
            self.assertEqual(len(r.pending()), count)
            if count == 3:
                with tempfile.TemporaryDirectory() as d:
                    save(r, Path(d) / 'r.json')
                    r = load(Path(d) / 'r.json')
        self.assertEqual(r.clock, 5)
        r.receive(wire([a]))
        self.assertEqual(r.pending(), [])
        self.assertEqual(shape(r.outline()), [('B', [('A', [])]), ('n', [])])
        self.assertEqual(r.values(), ['B', 'A', 'n'])
        for x in (s, lap, ph):
            for y in (s, lap, ph):
                sync(x, y)
            self.assertEqual(shape(x.outline()), [('B', [('A', [])]), ('n', [])])

    # docs/sync-semantics.md 8.3 (ops without "parent" keep their meaning), 8.8, sections 4-6
    def test_old_ops_keep_their_meaning(self):
        old = [{'type': 'insert', 'id': [1, 'laptop'], 'after': None, 'value': 'one'},
               {'type': 'insert', 'id': [2, 'laptop'], 'after': [1, 'laptop'], 'value': 'two'},
               {'type': 'insert', 'id': [1, 'phone'], 'after': None, 'value': 'zero'}]
        r = fresh(old)
        self.assertEqual(r.values(), ['zero', 'one', 'two'])
        self.assertEqual(shape(r.outline()), [('zero', []), ('one', []), ('two', [])])
        m = r.move([2, 'laptop'], parent=[1, 'phone'])
        self.assertEqual(r.values(), ['zero', 'two', 'one'])
        other = fresh(old)
        push(r, other)
        self.assertEqual(other.values(), ['zero', 'two', 'one'])
        self.assertEqual(m['id'], [3, 'server'])

    # docs/sync-semantics.md 8.4-8.7 on generated sessions with moves, checked against the
    # model of section 8 in every delivery order; I1-I7
    def test_generated_outline_sessions_all_orders(self):
        for seed in range(12):
            rnd = random.Random(1000 + seed)
            reps = {n: Replica(n) for n in NAMES}
            base = [reps['server'].insert('r0')]
            base.append(reps['server'].insert('r1', after=base[0]['id']))
            base.append(reps['server'].insert('c0', parent=base[0]['id']))
            for r in reps.values():
                r.receive(wire(base))

            def all_ids(r):
                out = []

                def walk(nodes):
                    for n in nodes:
                        out.append(n['id'])
                        walk(n['children'])
                walk(r.tree())
                return out

            def act(r, tag):
                every = all_ids(r)
                newest = sorted(every, key=kid)[-2:]      # prefer recent items: dependencies

                def pick(options):
                    return rnd.choice(newest if rnd.random() < 0.4 else options)
                roll = rnd.random()
                parent = pick([None] + every)
                after = rnd.choice([None] + r.children(parent))
                if roll < 0.5:
                    return r.move(pick(every), parent=parent, after=after)
                if roll < 0.6:
                    return r.delete(pick(every))
                if roll < 0.7:
                    return r.set(pick(every), tag + '*')
                return r.insert(tag, parent=parent, after=after)

            new = []
            for n in NAMES:
                new.append(act(reps[n], n[0] + '1'))
            src, dst = rnd.sample(NAMES, 2)
            reps[dst].receive(wire(reps[src].ops()))
            for n in NAMES:
                new.append(act(reps[n], n[0] + '2'))
            model_tree, model_items = spec_model(base + new)
            applied = [kid(op['id']) for op in base + new if op['type'] == 'insert']
            for j, order in enumerate(orders(len(new))):
                r = fresh(base + [new[i] for i in order])
                self.assertEqual(r.pending(), [], (seed, order))
                self.assertEqual(strip(r.tree()), model_tree, (seed, order))
                self.assertEqual(items(r), model_items, (seed, order))
                if j % 60 == 0:
                    self.check_tree(r, applied, (seed, order))
            for r in reps.values():
                sync(r, reps['server'])
            sync(reps['laptop'], reps['server'])
            for r in reps.values():
                self.assertEqual(strip(r.tree()), model_tree, seed)
'''

PROMPT1 = ("People keep telling me that after syncing some of their edits are simply gone, and sometimes "
           "the same note shows its lines in a different order on the phone than on the laptop. Sync has to "
           "be reliable: whatever order changes arrive in, and however often, every device must end up with "
           "the same note and nothing may get lost. How it is supposed to work is written down in "
           "docs/sync-semantics.md.")

PROMPT2 = ("Next step: notes become outlines. Lines can be nested under other lines and moved around, "
           "between lists and into each other, on any device while it is offline. Implement section 8 of "
           "docs/sync-semantics.md exactly as written, with the methods listed in section 10.3: concurrent "
           "moves must never create a cycle or lose a line, and every device has to end up with the same "
           "outline. Everything that works today has to keep working.")


def build():
    files = {
        'README.md': README_MD, 'docs/sync-semantics.md': SPEC_MD, 'docs/decisions.md': DECISIONS_MD,
        'docs/handoff.md': HANDOFF_MD, 'notesync/__init__.py': INIT_PY, 'notesync/__main__.py': MAIN_PY,
        'notesync/clock.py': CLOCK_PY, 'notesync/ops.py': OPS_PY, 'notesync/sequence.py': SEQUENCE_PY,
        'notesync/replica.py': REPLICA_PY, 'notesync/sync.py': SYNC_PY, 'notesync/store.py': STORE_PY,
        'notesync/render.py': RENDER_PY, 'notesync/cli.py': CLI_PY,
    }
    ref1 = {'notesync/sequence.py': SEQUENCE_REF, 'notesync/replica.py': REPLICA_REF1,
            'notesync/sync.py': SYNC_REF, 'docs/handoff.md': HANDOFF_REF1}
    ref2 = {'notesync/ops.py': OPS_REF2, 'notesync/replica.py': REPLICA_REF2,
            'docs/sync-semantics.md': SPEC_MD_2, 'docs/handoff.md': HANDOFF_REF2}
    hidden1 = HIDDEN_COMMON + HIDDEN_STAGE1
    hidden2 = HIDDEN_COMMON + HIDDEN_STAGE1 + HIDDEN_STAGE2
    p = project('u04_sync', 'existing_feature', 1 / 6, ['Python'], files, VISIBLE,
                [PROMPT1, PROMPT2], [ref1, ref2], [hidden1, hidden2], restart_after_first=True)
    p.update(difficulty='ultra-max', cluster='offline_sync', predicted_single_pass=[.10, .40],
             budget_seconds=1800)
    return p
