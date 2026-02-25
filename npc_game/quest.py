"""
quest.py

Text-based quest engine.

Quest: "The Stolen Crown of Valdris"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Inspired by classic D&D adventure modules (Lost Mine of Phandelver /
Baldur's Gate style) – a famous quest archetype found in countless RPGs:
recover a stolen relic before it empowers a rising villain.

Act structure (5 scenes):
  1. The Weeping Fen Crossroads  – meet the quest giver, gather intel
  2. The Forest of Whispering Ash – ambush by the Graycloaks
  3. The Bandit Camp Gate         – bluff/fight your way in
  4. The Great Hall               – confront the lieutenant
  5. The Vault of Valdris         – face Mordecai Vane & reclaim the Crown

Each scene has:
  - Description (narration)
  - Available player commands
  - An NPC turn after every player action
  - An outcome that advances to the next scene
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass, field
from typing import Callable

from .npc_agent import NPCAgent
from .honcho_memory import HonchoMemory

# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
RED    = "\033[91m"
GREEN  = "\033[92m"
DIM    = "\033[2m"
MAGENTA = "\033[95m"


def _c(text: str, colour: str) -> str:
    return f"{colour}{text}{RESET}"


def _narrate(text: str) -> None:
    print()
    for line in textwrap.wrap(text, width=66):
        print(_c(f"  {line}", CYAN))
    print()


def _npc_act(name: str, action: str, speech: str) -> None:
    print(_c(f"  [{name}] ", MAGENTA) + _c(action, DIM))
    print(_c(f"  {name}: ", BOLD + MAGENTA) + f'"{speech}"')
    print()


def _player_prompt() -> str:
    return input(_c("  > ", BOLD + YELLOW)).strip()


def _show_commands(commands: list[str]) -> None:
    print(_c("  Commands:", YELLOW))
    for cmd in commands:
        print(_c(f"    • {cmd}", GREEN))
    print()


def _section(title: str) -> None:
    print()
    print(_c("  ═" * 33, CYAN))
    print(_c(f"  {title}", BOLD + CYAN))
    print(_c("  ═" * 33, CYAN))
    print()


# ---------------------------------------------------------------------------
# Scene dataclass
# ---------------------------------------------------------------------------

@dataclass
class Scene:
    id: str
    title: str
    description: str
    commands: list[str]
    # handler returns id of next scene (or None to stay)
    handle_action: Callable[[str, "QuestState"], str | None] = field(
        default=None, repr=False
    )
    npc_trigger: str = ""    # narration sent to NPC at scene start


# ---------------------------------------------------------------------------
# Quest state
# ---------------------------------------------------------------------------

@dataclass
class QuestState:
    current_scene_id: str = "crossroads"
    events: list[str] = field(default_factory=list)
    inventory: list[str] = field(default_factory=list)
    flags: dict = field(default_factory=dict)

    def add_event(self, event: str) -> None:
        self.events.append(event)

    def has(self, item: str) -> bool:
        return item in self.inventory


# ---------------------------------------------------------------------------
# Scene handlers
# ---------------------------------------------------------------------------

def _handle_crossroads(action: str, state: QuestState) -> str | None:
    a = action.lower()
    if any(w in a for w in ["talk", "innkeeper", "speak", "quest", "ask"]):
        state.add_event("Learned from Mira the innkeeper: the Graycloaks stole the Crown heading north.")
        state.inventory.append("quest_info")
        _narrate(
            "Mira wrings her hands. 'Mordecai Vane – the Graycloak lord – "
            "took it three nights ago. He rides to the Vault of Valdris at "
            "dawn. You must hurry. Follow the old road north through the "
            "Whispering Ash.'"
        )
        return "forest"
    elif any(w in a for w in ["look", "examine", "inspect"]):
        _narrate(
            "The crossroads is quiet. A woman in an apron waves at you "
            "frantically from the Broken Wheel Inn. A wanted poster on the "
            "post reads: MORDECAI VANE – 500 gold – DEAD OR ALIVE."
        )
    elif any(w in a for w in ["north", "go north", "travel"]):
        if "quest_info" not in state.inventory:
            _narrate("You could head north, but it might help to learn what you're walking into first.")
        else:
            return "forest"
    else:
        _narrate("Nothing seems to happen. Try: look, talk to innkeeper, or go north.")
    return None


def _handle_forest(action: str, state: QuestState) -> str | None:
    a = action.lower()
    if not state.flags.get("ambush_done"):
        state.flags["ambush_done"] = True
        state.add_event("Survived a Graycloak ambush in the Whispering Ash.")
        _narrate(
            "Arrows whistle out of the dark trees! Two Graycloak scouts "
            "drop from the branches – crossbows drawn."
        )
        return None   # NPC reacts, then player must act again
    if any(w in a for w in ["fight", "attack", "charge", "draw"]):
        state.add_event("Defeated the Graycloak scouts in melee.")
        state.inventory.append("graycloak_badge")
        _narrate(
            "Steel rings against steel. Working with your companion you drive "
            "off the scouts, one dropping a Graycloak badge as he flees."
        )
        return "camp_gate"
    elif any(w in a for w in ["sneak", "hide", "stealth", "slip"]):
        state.add_event("Slipped past the Graycloak scouts unseen.")
        _narrate(
            "Melting into the shadows you and your companion ghost past the "
            "patrol without a sound. The camp lies ahead."
        )
        return "camp_gate"
    elif any(w in a for w in ["flee", "run", "retreat"]):
        state.add_event("Fled from the Graycloak scouts – took a longer route.")
        _narrate(
            "You circle wide and rejoin the road further north. It cost time "
            "but you arrive at the camp undetected."
        )
        return "camp_gate"
    else:
        _narrate("Scouts are in front of you. Try: fight, sneak past, or flee.")
    return None


def _handle_gate(action: str, state: QuestState) -> str | None:
    a = action.lower()
    if any(w in a for w in ["bluff", "talk", "persuade", "pretend", "badge"]):
        if "graycloak_badge" in state.inventory:
            state.add_event("Used the stolen Graycloak badge to bluff past the gate guard.")
            _narrate(
                "You flash the badge. The guard squints but steps aside. "
                "'Move along then. Commander doesn't like to be kept waiting.'"
            )
        else:
            state.add_event("Attempted to bluff the gate guard without a badge – partial success.")
            _narrate(
                "Your story is shaky but your companion fills in the gaps "
                "convincingly. The guard waves you through with a suspicious look."
            )
        return "great_hall"
    elif any(w in a for w in ["attack", "fight", "charge", "rush"]):
        state.add_event("Forced entry through the camp gate – guards alerted.")
        state.flags["alerted"] = True
        _narrate(
            "The gate guard barely has time to shout before you're through. "
            "You hear horns in the distance. The camp is alert now."
        )
        return "great_hall"
    elif any(w in a for w in ["sneak", "climb", "flank", "around"]):
        state.add_event("Climbed the palisade wall and slipped into camp.")
        _narrate(
            "You find a blind spot between two torches and scale the wall. "
            "Nobody saw a thing."
        )
        return "great_hall"
    else:
        _narrate("The gate has one armed guard. Try: bluff, fight, or sneak around.")
    return None


def _handle_hall(action: str, state: QuestState) -> str | None:
    a = action.lower()
    if not state.flags.get("lieutenant_met"):
        state.flags["lieutenant_met"] = True
        alerted = state.flags.get("alerted", False)
        if alerted:
            state.add_event("Entered the great hall with guards already on alert.")
            _narrate(
                "The Great Hall erupts. Lieutenant Brenn draws her sword: "
                "'I knew it – KILL THEM!'"
            )
        else:
            state.add_event("Entered the great hall undetected.")
            _narrate(
                "Lieutenant Brenn looks up from her war-table. "
                "'How did you—?' Her hand moves to her sword."
            )
        return None  # NPC reacts

    if any(w in a for w in ["fight", "attack", "charge"]):
        state.add_event("Defeated Lieutenant Brenn in the Great Hall.")
        state.inventory.append("vault_key")
        _narrate(
            "It's a brutal fight but Brenn falls. As she slumps she presses "
            "a brass key into her fist – you pry it free. The vault key."
        )
        return "vault"
    elif any(w in a for w in ["negotiate", "deal", "talk", "surrender"]):
        state.add_event("Struck a deal with Lieutenant Brenn – she reveals the vault.")
        state.inventory.append("vault_key")
        _narrate(
            "Brenn laughs bitterly. 'Mordecai will betray us all anyway. "
            "Take the key – give me a head start.' She tosses it across the table."
        )
        return "vault"
    elif any(w in a for w in ["search", "look", "examine"]):
        _narrate(
            "Maps pinned to the table show a locked chamber beneath the hall. "
            "A key would be needed. Brenn is watching your every move."
        )
    else:
        _narrate("Brenn has her hand on her sword. Try: fight, negotiate a deal, or search the room.")
    return None


def _handle_vault(action: str, state: QuestState) -> str | None:
    a = action.lower()
    if not state.flags.get("vane_revealed"):
        state.flags["vane_revealed"] = True
        state.add_event("Descended into the Vault of Valdris and confronted Mordecai Vane.")
        _narrate(
            "The vault is ancient stone. Mordecai Vane stands before a "
            "stone altar, the Crown of Valdris in his hands – a circlet of "
            "black iron and cold fire. He smiles. 'I wondered when someone "
            "would be brave or foolish enough to come. Shall we finish this?'"
        )
        return None

    if any(w in a for w in ["fight", "attack", "charge", "strike"]):
        state.add_event("Faced Mordecai Vane in final combat.")
        _narrate(
            "Vane fights like a man who has nothing left to lose. "
            "The vault shakes with the force of the battle."
        )
        _narrate(
            "With your companion's help the dark flame gutters – Vane "
            "falls. The Crown clatters to the stone floor."
        )
        state.add_event("VICTORY – The Crown of Valdris reclaimed!")
        return "end"
    elif any(w in a for w in ["trick", "distract", "bluff", "taunt"]):
        state.add_event("Used wit to create an opening against Mordecai Vane.")
        _narrate(
            "Your taunt works – Vane looks away for just a heartbeat. "
            "Your companion moves. The Crown falls. Vane, disarmed and "
            "cornered, makes a desperate leap for the exit – "
            "and misses. He crumples against the wall."
        )
        state.add_event("VICTORY – The Crown of Valdris reclaimed!")
        return "end"
    elif any(w in a for w in ["crown", "grab", "snatch", "seize"]):
        state.add_event("Attempted to snatch the Crown directly from Vane.")
        _narrate(
            "You lunge – Vane steps aside but your companion intercepts him. "
            "In the chaos the Crown spins across the floor. You scoop it up. "
            "Vane stares, then laughs quietly and vanishes into the shadows. "
            "'This isn't over.'"
        )
        state.add_event("VICTORY – The Crown of Valdris reclaimed!")
        return "end"
    elif any(w in a for w in ["look", "examine", "inspect"]):
        _narrate(
            "The Crown pulses with cold dark light in Vane's hands. "
            "The altar behind him is carved with the seal of Valdris – "
            "a broken crown above a rising sun."
        )
    else:
        _narrate("Mordecai Vane stands between you and the Crown. Try: fight, trick/taunt, or grab the Crown.")
    return None


# ---------------------------------------------------------------------------
# Scene definitions
# ---------------------------------------------------------------------------

SCENES: dict[str, Scene] = {
    "crossroads": Scene(
        id="crossroads",
        title="Scene 1 – The Weeping Fen Crossroads",
        description=(
            "A muddy crossroads at dusk. The Broken Wheel Inn tilts to one "
            "side, lantern swinging in the wind. A haggard innkeeper rushes "
            "toward you, desperate. 'Please – you have to help! Mordecai Vane "
            "stole the Crown of Valdris from our village shrine. If he crowns "
            "himself at dawn we'll never be free of his rule!'"
        ),
        commands=["look around", "talk to innkeeper", "go north"],
        handle_action=_handle_crossroads,
        npc_trigger="We have arrived at a crossroads at dusk. A distressed innkeeper is begging for help.",
    ),
    "forest": Scene(
        id="forest",
        title="Scene 2 – The Forest of Whispering Ash",
        description=(
            "The road winds into a forest of pale-barked ash trees. Their "
            "leaves whisper even without wind. Somewhere ahead lie the "
            "Graycloak bandit camp and the Vault of Valdris."
        ),
        commands=["fight the scouts", "sneak past", "flee and go around"],
        handle_action=_handle_forest,
        npc_trigger="We are in a dark forest and have just been ambushed by crossbow-wielding scouts.",
    ),
    "camp_gate": Scene(
        id="camp_gate",
        title="Scene 3 – The Bandit Camp Gate",
        description=(
            "A palisade of sharpened logs. One armoured guard stands watch "
            "under a torch. The Graycloak banner – a grey hood on black – "
            "flutters above the gate."
        ),
        commands=["bluff your way in", "fight the guard", "sneak around/climb"],
        handle_action=_handle_gate,
        npc_trigger="We are at a bandit camp gate with a single guard. We need to get inside.",
    ),
    "great_hall": Scene(
        id="great_hall",
        title="Scene 4 – The Great Hall",
        description=(
            "Inside the palisade a large timber hall dominates the camp. "
            "Through the open doors you can see maps, weapons, and a "
            "battle-hardened woman in grey armour – Lieutenant Brenn – "
            "studying plans by firelight."
        ),
        commands=["fight Lieutenant Brenn", "negotiate a deal", "search the room"],
        handle_action=_handle_hall,
        npc_trigger="We are inside the enemy great hall. The lieutenant has spotted us.",
    ),
    "vault": Scene(
        id="vault",
        title="Scene 5 – The Vault of Valdris",
        description=(
            "Ancient stone steps descend beneath the hall. Torches burn green "
            "in iron sconces. At the bottom, the Vault of Valdris – and "
            "Mordecai Vane himself, Crown in hand, waiting."
        ),
        commands=["fight Mordecai Vane", "trick / taunt him", "grab the Crown"],
        handle_action=_handle_vault,
        npc_trigger="We are in the final vault. We face Mordecai Vane who holds the stolen Crown.",
    ),
}


# ---------------------------------------------------------------------------
# Quest runner
# ---------------------------------------------------------------------------

class Quest:
    TITLE = "The Stolen Crown of Valdris"
    HOOK = (
        "A stolen relic of power must be reclaimed before a warlord crowns "
        "himself at dawn and plunges the region into darkness."
    )

    def __init__(self, npc: NPCAgent, memory: HonchoMemory):
        self.npc = npc
        self.memory = memory
        self.state = QuestState()

    def run(self) -> None:
        self._intro()

        while self.state.current_scene_id != "end":
            scene = SCENES[self.state.current_scene_id]
            self._enter_scene(scene)

            # Scene loop
            while True:
                _show_commands(scene.commands)
                raw = _player_prompt()
                if not raw:
                    continue

                # Log player action
                self.memory.log_player_action(raw)
                self.state.add_event(f"Player: {raw}")

                # Scene handler
                next_id = scene.handle_action(raw, self.state)

                # NPC reacts
                action, speech = self.npc.act(
                    location=scene.title,
                    description=scene.description,
                    recent_events=self.state.events,
                    player_action=raw,
                )
                _npc_act(self.npc.name, action, speech)

                if next_id:
                    self.state.current_scene_id = next_id
                    break

        self._outro()

    # -------------------------------------------------------------------------

    def _intro(self) -> None:
        print()
        print(_c("  ╔" + "═" * 56 + "╗", BOLD + CYAN))
        print(_c(f"  ║  {self.TITLE:<54}║", BOLD + CYAN))
        print(_c("  ╚" + "═" * 56 + "╝", BOLD + CYAN))
        print()
        _narrate(
            "Classic RPG adventure inspired by the tradition of Baldur's Gate, "
            "D&D's Lost Mine of Phandelver, and every 'retrieve the stolen relic' "
            "quest that ever kept a tavern candle burning past midnight."
        )
        # NPC opening remark
        opening = self.npc.opening_remark(self.TITLE, self.HOOK)
        print(_c(f"  {self.npc.name}: ", BOLD + MAGENTA) + f'"{opening}"')
        print()
        input(_c("  Press Enter to begin…", DIM))

    def _enter_scene(self, scene: Scene) -> None:
        _section(scene.title)
        _narrate(scene.description)
        # NPC reacts to entering the scene
        if scene.npc_trigger:
            action, speech = self.npc.react_to_event(scene.npc_trigger)
            _npc_act(self.npc.name, action, speech)
            self.state.add_event(f"{self.npc.name} entering scene: {action}")

    def _outro(self) -> None:
        _section("QUEST COMPLETE")
        _narrate(
            "The Crown of Valdris is back in safe hands. "
            "Mordecai Vane's shadow lifts from the land – for now. "
            "The innkeeper weeps with relief. The village will remember "
            "this night for a generation."
        )
        # Final NPC speech
        action, speech = self.npc.act(
            location="quest complete",
            description="The Crown has been reclaimed. The quest is over.",
            recent_events=self.state.events,
            player_action="We did it.",
        )
        _npc_act(self.npc.name, action, speech)
        print()
        print(_c("  ── Quest events logged to Honcho memory. ──", DIM))
        print(_c("  ── Your NPC will remember this adventure. ──", DIM))
        print()
