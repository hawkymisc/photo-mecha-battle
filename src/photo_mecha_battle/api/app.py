from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from photo_mecha_battle.api.store import InMemoryStore, build_demo_cpu_team
from photo_mecha_battle.models import MechForm, Position, Team, TeamSlot
from photo_mecha_battle.tactics import TacticPreset, TacticSet, build_preset

store = InMemoryStore()
app = FastAPI(title="Photo Mecha Battle API", version="0.1.0")


class CaptureCreateRequest(BaseModel):
    label: str = "umbrella"


class SegmentRequest(BaseModel):
    label: str = "umbrella"


class MechCreateRequest(BaseModel):
    object_id: str
    form: MechForm
    name: str


class BattleSlotRequest(BaseModel):
    mech_id: str
    position: Position
    preset: TacticPreset


class BattleCreateRequest(BaseModel):
    team_name: str = "Player"
    slots: list[BattleSlotRequest]
    seed: int = 42


@app.post("/captures")
def create_capture(body: CaptureCreateRequest):
    record = store.create_capture(body.label)
    return {"id": record.id, "label": record.label}


@app.post("/captures/{capture_id}/detect")
def detect_objects(capture_id: str):
    if capture_id not in store.captures:
        raise HTTPException(status_code=404, detail="capture not found")
    return {"candidates": store.detect_objects(capture_id)}


@app.post("/captures/{capture_id}/segment")
def segment_object(capture_id: str, body: SegmentRequest):
    if capture_id not in store.captures:
        raise HTTPException(status_code=404, detail="capture not found")
    record = store.segment_object(capture_id, body.label)
    return {
        "id": record.id,
        "capture_id": record.capture_id,
        "info_score": record.info_score,
        "features": record.features.__dict__,
    }


@app.post("/objects/{object_id}/analyze")
def analyze_object(object_id: str):
    record = store.objects.get(object_id)
    if record is None:
        raise HTTPException(status_code=404, detail="object not found")
    return {"id": record.id, "info_score": record.info_score, "features": record.features.__dict__}


@app.post("/mechs")
def create_mech(body: MechCreateRequest):
    if body.object_id not in store.objects:
        raise HTTPException(status_code=404, detail="object not found")
    record = store.create_mech(body.object_id, body.form, body.name)
    mech = record.mech
    return {
        "id": record.id,
        "object_id": record.object_id,
        "name": mech.name,
        "form": mech.form.value,
        "stats": mech.stats.__dict__,
    }


@app.get("/mechs/{mech_id}")
def get_mech(mech_id: str):
    record = store.mechs.get(mech_id)
    if record is None:
        raise HTTPException(status_code=404, detail="mech not found")
    mech = record.mech
    return {
        "id": record.id,
        "object_id": record.object_id,
        "name": mech.name,
        "form": mech.form.value,
        "stats": mech.stats.__dict__,
    }


@app.get("/tactic-presets")
def list_tactic_presets():
    return {
        "presets": [
            {"id": preset.value, "name": preset.name}
            for preset in TacticPreset
        ]
    }


@app.post("/battles")
def create_battle(body: BattleCreateRequest):
    if len(body.slots) != 3:
        raise HTTPException(status_code=400, detail="team must have exactly 3 slots")

    player_slots: list[TeamSlot] = []
    player_tactics: dict[Position, TacticSet] = {}
    for slot in body.slots:
        mech_record = store.mechs.get(slot.mech_id)
        if mech_record is None:
            raise HTTPException(status_code=404, detail=f"mech not found: {slot.mech_id}")
        player_slots.append(TeamSlot(mech=mech_record.mech, position=slot.position))
        player_tactics[slot.position] = build_preset(slot.preset)

    player_team = Team(id="player", name=body.team_name, slots=player_slots)
    cpu_team, cpu_tactics = build_demo_cpu_team()
    battle = store.run_battle(player_team, player_tactics, cpu_team, cpu_tactics, body.seed)
    result = battle.result
    return {
        "id": battle.id,
        "seed": result.seed,
        "winner_team_id": result.winner_team_id,
        "turns": result.turns,
        "log": result.format_log(),
    }


@app.get("/battles/{battle_id}")
def get_battle(battle_id: str):
    record = store.battles.get(battle_id)
    if record is None:
        raise HTTPException(status_code=404, detail="battle not found")
    result = record.result
    return {
        "id": record.id,
        "seed": result.seed,
        "winner_team_id": result.winner_team_id,
        "turns": result.turns,
        "log": result.format_log(),
    }


class RankingEntry(BaseModel):
    team_name: str
    rating: int = Field(ge=0)


@app.get("/ranking")
def get_ranking():
    return {"entries": [{"team_name": "Player", "rating": 1000}]}
