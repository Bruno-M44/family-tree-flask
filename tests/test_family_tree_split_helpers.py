"""Unit tests for the pure graph helpers behind the (upcoming) split endpoint —
the inverse of merge. No Flask app, no DB: parent_child_edges / couple_edges
are plain (id, id) tuples, exactly like _compute_descendant_subtree and
_find_cross_links expect.
"""

from app.views.family_tree_view import _compute_descendant_subtree, _find_cross_links


# ---------------------------------------------------------------------------
# _compute_descendant_subtree
# ---------------------------------------------------------------------------

def test_subtree_single_cell_no_children():
    subtree = _compute_descendant_subtree(1, parent_child_edges=[], couple_edges=[])
    assert subtree == {1}


def test_subtree_linear_chain():
    # 1 -> 2 -> 3
    edges = [(1, 2), (2, 3)]
    subtree = _compute_descendant_subtree(1, edges, couple_edges=[])
    assert subtree == {1, 2, 3}


def test_subtree_excludes_siblings_of_root():
    # Root (2) and its sibling (3) both children of 1; only 2's own descendants
    # should be pulled in, not 3 (2's sibling) nor 1 (2's parent).
    edges = [(1, 2), (1, 3), (2, 4)]
    subtree = _compute_descendant_subtree(2, edges, couple_edges=[])
    assert subtree == {2, 4}


def test_subtree_includes_direct_spouse():
    # Root (1) married to (2, not a blood descendant), no children yet.
    subtree = _compute_descendant_subtree(1, parent_child_edges=[], couple_edges=[(1, 2)])
    assert subtree == {1, 2}


def test_subtree_includes_descendants_spouse_but_not_spouses_other_family():
    # 1 -> 2 (descendant), 2 married to 3 (spouse, pulled in), but 3 also has
    # an unrelated child (5) with someone else (4) — 4 and 5 must NOT be pulled
    # in, they don't descend from root (1).
    parent_child_edges = [(1, 2), (3, 5), (4, 5)]
    couple_edges = [(2, 3)]
    subtree = _compute_descendant_subtree(1, parent_child_edges, couple_edges)
    assert subtree == {1, 2, 3}
    assert 4 not in subtree
    assert 5 not in subtree


def test_subtree_multi_generation_with_couples():
    # 1+2 (couple) -> 3, 3+4 (couple) -> 5, 6
    parent_child_edges = [(1, 3), (2, 3), (3, 5), (3, 6), (4, 5), (4, 6)]
    couple_edges = [(1, 2), (3, 4)]
    subtree = _compute_descendant_subtree(1, parent_child_edges, couple_edges)
    assert subtree == {1, 2, 3, 4, 5, 6}


# ---------------------------------------------------------------------------
# _find_cross_links
# ---------------------------------------------------------------------------

def test_no_conflicts_on_clean_subtree():
    parent_child_edges = [(1, 2), (2, 3)]
    couple_edges = []
    subtree = _compute_descendant_subtree(1, parent_child_edges, couple_edges)
    conflicts = _find_cross_links(1, subtree, parent_child_edges, couple_edges)
    assert conflicts == []


def test_roots_own_parent_link_excluded_from_conflicts():
    # 0 is root's parent, staying behind in tree A — this is the intended cut
    # point, must not be reported as a conflict.
    parent_child_edges = [(0, 1), (1, 2)]
    subtree = _compute_descendant_subtree(1, parent_child_edges, couple_edges=[])
    conflicts = _find_cross_links(1, subtree, parent_child_edges, couple_edges=[])
    assert conflicts == []


def test_roots_two_parents_both_excluded_from_conflicts():
    parent_child_edges = [(0, 1), (99, 1), (1, 2)]
    couple_edges = [(0, 99)]
    subtree = _compute_descendant_subtree(1, parent_child_edges, couple_edges)
    conflicts = _find_cross_links(1, subtree, parent_child_edges, couple_edges)
    assert conflicts == []


def test_blended_family_parent_child_conflict_detected():
    # 1 -> 2 (true descendant). 2 has a child (5) with an external co-parent (4)
    # who has no other tie to the subtree — this must be blocked.
    parent_child_edges = [(1, 2), (2, 5), (4, 5)]
    subtree = _compute_descendant_subtree(1, parent_child_edges, couple_edges=[])
    conflicts = _find_cross_links(1, subtree, parent_child_edges, couple_edges=[])
    assert conflicts == [{"inside": 5, "outside": 4, "relation": "parent_child"}]


def test_remarriage_couple_only_conflict_detected():
    # 1 -> 2 (descendant), 2 married to 3 (pulled in as spouse). 3 also has an
    # older couple record with 6, who is otherwise unrelated to the subtree.
    parent_child_edges = [(1, 2)]
    couple_edges = [(2, 3), (3, 6)]
    subtree = _compute_descendant_subtree(1, parent_child_edges, couple_edges)
    conflicts = _find_cross_links(1, subtree, parent_child_edges, couple_edges)
    assert conflicts == [{"inside": 3, "outside": 6, "relation": "couple"}]


def test_multiple_conflicts_all_reported():
    parent_child_edges = [(1, 2), (2, 5), (4, 5)]
    couple_edges = [(2, 3), (3, 6)]
    subtree = _compute_descendant_subtree(1, parent_child_edges, couple_edges)
    conflicts = _find_cross_links(1, subtree, parent_child_edges, couple_edges)
    assert len(conflicts) == 2
    assert {"inside": 5, "outside": 4, "relation": "parent_child"} in conflicts
    assert {"inside": 3, "outside": 6, "relation": "couple"} in conflicts
