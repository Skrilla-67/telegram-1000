from server.game.scoring import score_dice


def test_singles():
    r = score_dice([1, 2, 3, 4, 4])
    assert r.points == 10
    assert r.scoring_dice == [1]


def test_five_and_one():
    r = score_dice([5, 1, 2, 3, 4])
    # Could be straight 125 or 1+5=15 — max is straight
    assert r.points == 125


def test_straight_high():
    r = score_dice([2, 3, 4, 5, 6])
    assert r.points == 250


def test_three_ones():
    r = score_dice([1, 1, 1, 2, 3])
    assert r.points == 100


def test_five_ones():
    r = score_dice([1, 1, 1, 1, 1])
    assert r.points == 1000


def test_four_twos():
    r = score_dice([2, 2, 2, 2, 3])
    assert r.points == 40


def test_five_twos():
    r = score_dice([2, 2, 2, 2, 2])
    assert r.points == 200


def test_three_fives_plus_one():
    r = score_dice([5, 5, 5, 1, 2])
    assert r.points == 60  # 50 + 10


def test_bust():
    r = score_dice([2, 3, 4, 6, 6])
    assert r.points == 0
    assert r.is_bust


def test_three_sixes():
    r = score_dice([6, 6, 6, 2, 3])
    assert r.points == 60
