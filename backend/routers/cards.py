from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
from models import CardSetTier, CardInsertType, CardSpecialFlag

router = APIRouter(prefix="/api/cards", tags=["cards"])

# ── Pydantic schemas ──────────────────────────────────────────────────────────

class SetTierIn(BaseModel):
    id: Optional[int] = None
    set_name: str
    sport: str = "all"
    tier: int
    notes: Optional[str] = None

class InsertTypeIn(BaseModel):
    id: Optional[int] = None
    insert_name: str
    rank: int
    notes: Optional[str] = None

class SpecialFlagIn(BaseModel):
    id: Optional[int] = None
    flag_name: str
    multiplier: float = 1.0
    description: Optional[str] = None

class HierarchyUpdate(BaseModel):
    sets: list[SetTierIn]
    inserts: list[InsertTypeIn]
    flags: list[SpecialFlagIn]

# ── Seed defaults ─────────────────────────────────────────────────────────────

_DEFAULT_SETS = [
    # ── Baseball ──────────────────────────────────────────────────────────────
    ("Topps Dynasty",            "baseball", 1, "Ultra-premium; low-numbered hits only"),
    ("Topps Definitive",         "baseball", 1, "On-card autos, high-end"),
    ("Topps Transcendent",       "baseball", 1, "Case-hit level; legends + modern stars"),
    ("Bowman Chrome",            "baseball", 2, "Premier prospect/RC auto set"),
    ("Topps Chrome",             "baseball", 2, "Flagship chrome; most liquid RC autos"),
    ("Topps Finest",             "baseball", 2, "High-end refractors; strong RC market"),
    ("Topps Heritage High Number","baseball",2, "Short-print RCs drive demand"),
    ("Topps Series 1",           "baseball", 3, "Mass-market flagship"),
    ("Topps Series 2",           "baseball", 3, "Mass-market flagship"),
    ("Topps Heritage",           "baseball", 3, "Vintage design; SP short prints"),
    ("Topps Stadium Club",       "baseball", 3, "Photography-focused; niche premium"),
    ("Allen & Ginter",           "baseball", 3, "Cross-brand appeal; SP subsets"),
    ("Bowman",                   "baseball", 4, "Paper prospect set; Chrome is the premium tier"),
    ("Topps Opening Day",        "baseball", 4, "Budget retail; parallels have low ceiling"),
    ("Topps Big League",         "baseball", 4, "Low-price retail"),
    # ── Football ──────────────────────────────────────────────────────────────
    ("Panini National Treasures","football", 1, "Gold standard; RPAs define rookie values"),
    ("Panini Flawless",          "football", 1, "Gem-encased; ultra-premium hits"),
    ("Panini One",               "football", 1, "Super-high-end; low print run everything"),
    ("Panini Immaculate",        "football", 1, "Premium relics and autos"),
    ("Panini Prizm",             "football", 2, "Most liquid football RC set"),
    ("Panini Select",            "football", 2, "Three-tier parallel structure; strong market"),
    ("Panini Mosaic",            "football", 3, "Mid-tier Prizm-lite"),
    ("Panini Contenders",        "football", 3, "Ticket-style autos; key RC product"),
    ("Donruss Optic",            "football", 3, "Chrome parallel of Donruss; decent liquidity"),
    ("Panini Score",             "football", 4, "Mass-market base"),
    ("Panini Donruss",           "football", 4, "Base retail; Optic is the premium version"),
    ("Panini Legacy",            "football", 4, "Budget retail"),
    # ── Basketball ────────────────────────────────────────────────────────────
    ("Panini National Treasures","basketball",1,"Gold standard; logomans and patch autos"),
    ("Panini Flawless",          "basketball",1,"Gem-encased hits"),
    ("Panini One",               "basketball",1,"Ultra-premium"),
    ("Panini Immaculate",        "basketball",1,"Premium rookie autos"),
    ("Panini Prizm",             "basketball",2,"Most liquid basketball RC set"),
    ("Panini Select",            "basketball",2,"Strong parallel structure"),
    ("Panini Mosaic",            "basketball",3,"Mid-tier"),
    ("Donruss Optic",            "basketball",3,"Chrome Donruss; decent market"),
    ("Panini Contenders",        "basketball",3,"Ticket autos; key RC product"),
    ("Panini Hoops Premium",     "basketball",3,"Mid-range Hoops product"),
    ("Panini Hoops",             "basketball",4,"Entry-level basketball"),
    ("Panini Donruss",           "basketball",4,"Base retail"),
    # ── Pokémon ───────────────────────────────────────────────────────────────
    ("Pokémon 151",              "pokemon",  1, "Modern classic; Charizard EX anchor"),
    ("Pokémon Scarlet & Violet Base","pokemon",1,"Current era flagship"),
    ("Pokémon Obsidian Flames",  "pokemon",  1, "Charizard ex; most liquid modern set"),
    ("Pokémon Paradox Rift",     "pokemon",  2, "Strong pull rates and market"),
    ("Pokémon Temporal Forces",  "pokemon",  2, "ACE SPEC chase cards"),
    ("Pokémon Paldean Fates",    "pokemon",  2, "Shiny Charizard anchor"),
    ("Pokémon Crown Zenith",     "pokemon",  2, "Galarian Gallery set drives demand"),
    ("Pokémon Silver Tempest",   "pokemon",  3, "Lugia VSTAR anchor"),
    ("Pokémon Lost Origin",      "pokemon",  3, "Giratina V pulls value"),
    ("Pokémon Base Set",         "pokemon",  1, "Vintage; Charizard Holo defines the hobby"),
    ("Pokémon Jungle",           "pokemon",  2, "Vintage; classic Vaporeon/Flareon holos"),
    ("Pokémon Fossil",           "pokemon",  2, "Vintage"),
    ("Pokémon Team Rocket",      "pokemon",  2, "Vintage; Dark Charizard"),
    ("Pokémon Neo Genesis",      "pokemon",  2, "Vintage; Lugia era"),
]

_DEFAULT_INSERTS = [
    ("Logoman / True 1/1",           1,  "Actual jersey logo patch, manufactured as single"),
    ("Superfractor / Gold Vinyl",    2,  "1/1 parallel — most valuable non-logo 1/1"),
    ("Printing Plate",               3,  "Cyan/Magenta/Yellow/Black — 1/1 each"),
    ("Auto Patch (Multi-Color/Logo)",4,  "RPA with premium patch window"),
    ("Auto Patch (Single Color)",    5,  "RPA with standard patch window"),
    ("Auto Relic",                   6,  "On-card auto + jersey/bat swatch"),
    ("Auto (Numbered)",              7,  "On-card or sticker auto, numbered parallel"),
    ("Auto (Unnumbered / Base)",     8,  "Auto without print-run numbering"),
    ("Jumbo Patch (No Auto)",        9,  "Large multi-color patch, no signature"),
    ("Relic / Memorabilia (No Auto)",10, "Jersey, bat, or glove swatch"),
    ("Refractor / Prizm / Chrome",   11, "Base chrome/prizm parallel"),
    ("Color Parallel (Numbered)",    12, "Non-chrome numbered color parallel"),
    ("Short Print / Variation SP",   13, "Short-printed photo/design variation"),
    ("Base",                         14, "Standard base card"),
]

_DEFAULT_FLAGS = [
    ("Rookie Card (RC)",               2.5, "First officially licensed rookie card year"),
    ("First Bowman Chrome Auto",       2.0, "Pre-rookie prospect auto; often precedes RC"),
    ("Hall of Fame Inductee",          1.4, "Confirmed HOF status"),
    ("Active Star (Top 10 at position)",1.2,"Currently elite performer"),
    ("Legend / Retired Star",          1.0, "Retired but recognizable name"),
    ("Short Print Photo Variation",    1.15,"SP variant within same set"),
    ("Prospect (Non-Chrome)",          0.8, "Minor league prospect, not first Bowman Chrome"),
    ("Retired (Non-HOF)",              0.75,"Retired player without HOF status"),
    ("Pokémon Holo (Base Set Era)",    2.0, "Pre-Neo vintage holographic"),
    ("Pokémon Full Art / Alt Art",     1.5, "Modern full-art or alternate-art treatment"),
    ("Pokémon ex / V / VMAX",         1.3, "Main rarity mechanic for modern era"),
    ("Pokémon Trainer / Supporter",   1.1, "Key trainer cards often chase-worthy"),
]


def _seed(db: Session):
    if db.query(CardSetTier).count() == 0:
        db.bulk_insert_mappings(CardSetTier, [
            {"set_name": n, "sport": s, "tier": t, "notes": no}
            for n, s, t, no in _DEFAULT_SETS
        ])
    if db.query(CardInsertType).count() == 0:
        db.bulk_insert_mappings(CardInsertType, [
            {"insert_name": n, "rank": r, "notes": no}
            for n, r, no in _DEFAULT_INSERTS
        ])
    if db.query(CardSpecialFlag).count() == 0:
        db.bulk_insert_mappings(CardSpecialFlag, [
            {"flag_name": n, "multiplier": m, "description": d}
            for n, m, d in _DEFAULT_FLAGS
        ])
    db.commit()


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/hierarchy")
def get_hierarchy(db: Session = Depends(get_db)):
    _seed(db)
    return {
        "sets":    [{"id":r.id,"set_name":r.set_name,"sport":r.sport,"tier":r.tier,"notes":r.notes}
                    for r in db.query(CardSetTier).order_by(CardSetTier.tier, CardSetTier.set_name).all()],
        "inserts": [{"id":r.id,"insert_name":r.insert_name,"rank":r.rank,"notes":r.notes}
                    for r in db.query(CardInsertType).order_by(CardInsertType.rank).all()],
        "flags":   [{"id":r.id,"flag_name":r.flag_name,"multiplier":r.multiplier,"description":r.description}
                    for r in db.query(CardSpecialFlag).order_by(CardSpecialFlag.multiplier.desc()).all()],
    }


@router.put("/hierarchy")
def save_hierarchy(body: HierarchyUpdate, db: Session = Depends(get_db)):
    # Replace all three tables with the incoming payload
    db.query(CardSetTier).delete()
    db.query(CardInsertType).delete()
    db.query(CardSpecialFlag).delete()

    for s in body.sets:
        db.add(CardSetTier(set_name=s.set_name, sport=s.sport, tier=s.tier, notes=s.notes))
    for i in body.inserts:
        db.add(CardInsertType(insert_name=i.insert_name, rank=i.rank, notes=i.notes))
    for f in body.flags:
        db.add(CardSpecialFlag(flag_name=f.flag_name, multiplier=f.multiplier, description=f.description))

    db.commit()
    return {"ok": True}
