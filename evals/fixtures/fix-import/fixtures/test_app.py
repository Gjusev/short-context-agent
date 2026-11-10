from app import load


def test_load(tmp_path):
    p = tmp_path / "d.json"
    p.write_text('{"ok": true}')
    assert load(str(p)) == {"ok": True}
