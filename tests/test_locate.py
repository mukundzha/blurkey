from blurkey.locate import locate_match, merge_boxes


def test_proportional():
    box = locate_match("abcdefghij", (0, 0, 100, 10), 0, 10, pad=0)
    assert box == (0, 0, 100, 10)
    box = locate_match("abcdefghij", (0, 0, 100, 10), 0, 5, pad=0)
    assert box == (0, 0, 50, 10)


def test_pad_and_clamp():
    box = locate_match("abcdef", (10, 10, 110, 20), 2, 4, pad=4, img_w=200, img_h=200)
    assert box[0] < 10 + 100 * (2 / 6)
    assert box[2] > 10 + 100 * (4 / 6)
    box2 = locate_match("ab", (0, 0, 10, 10), 0, 2, pad=10, img_w=50, img_h=50)
    assert box2[0] == 0 and box2[1] == 0


def test_merge():
    boxes = [(0, 0, 10, 10), (5, 5, 15, 15), (30, 30, 40, 40)]
    assert len(merge_boxes(boxes)) == 2
    assert merge_boxes([]) == []
