from photo_mecha_battle.api.database import Database


def test_user_and_ranking_persist_across_connections():
    db = Database(":memory:")
    user = db.create_user("Persist")
    db.save_mech(user.id, "m1", "obj1", "bird", "Mech", {"hp": 10, "atk": 10, "defense": 10, "spd": 10, "tec": 10, "en": 10, "luck": 0})
    db.update_rating(user.id, 50)
    ranking = db.get_ranking()
    assert ranking[0]["rating"] == 1050
    mechs = db.list_mechs(user.id)
    assert mechs[0]["name"] == "Mech"
