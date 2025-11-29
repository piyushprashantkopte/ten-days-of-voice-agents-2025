import json
import logging
import os
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Annotated

from dotenv import load_dotenv
from pydantic import Field
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    WorkerOptions,
    cli,
    function_tool,
    RunContext,
)

from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# -------------------------
# Logging
# -------------------------
logger = logging.getLogger("voice_game_master")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(handler)

load_dotenv(".env.local")

# -------------------------
# Simple Game World Definition
# -------------------------
# A compact world with a few scenes and choices forming a mini-arc.
WORLD = {
    "intro": {
        "title": "The Whispering Grove",
        "desc": "Your eyes snap open beneath a canopy of towering pines. Moonlight filters through the branches like cold fire. The forest is deathly still… except for one thing: every tree around you whispers your name. Ahead lies a narrow trail, fading into blue mist. To your left, a toppled stone monolith glows faintly with runes. To your right, a lantern flickers near an abandoned ranger’s camp.",
        "choices": {
            "follow_trail": {
                "desc": "Walk toward the misty forest trail.",
                "result_scene": "trail"
            },
            "inspect_monolith": {
                "desc": "Approach the glowing stone monolith.",
                "result_scene": "monolith"
            },
            "check_camp": {
                "desc": "Investigate the ranger’s camp.",
                "result_scene": "camp"
            }
        }
    },

  "trail": {
    "title": "The Fading Path",
    "desc": "The path twists through trees that lean closer with each step. The whispers grow louder—almost urgent. A shape darts across the trail: a small fox with silver eyes, staring at you knowingly. A wooden charm dangles from its mouth.",
    "choices": {
      "follow_fox": {
        "desc": "Go after the strange fox.",
        "result_scene": "fox_chase"
      },
      "ignore_and_continue": {
        "desc": "Stay on the path and press forward.",
        "result_scene": "clearing"
      },
      "turn_back": {
        "desc": "Retreat to the forest entrance.",
        "result_scene": "intro"
      }
    }
  },

  "monolith": {
    "title": "The Stone of Tethers",
    "desc": "The monolith rises before you, carved with spiraling runes that glow moss-green. As you touch it, the whispers fall silent. A single rune brightens, forming a symbol resembling an eye. A pulse of energy hums beneath your fingertips.",
    "choices": {
      "touch_symbol": {
        "desc": "Press your hand firmly on the glowing rune.",
        "result_scene": "vision"
      },
      "search_around": {
        "desc": "Examine the ground around the monolith.",
        "result_scene": "buried_relic"
      },
      "step_back": {
        "desc": "Back away—it feels dangerous.",
        "result_scene": "intro"
      }
    }
  },

  "camp": {
    "title": "The Abandoned Camp",
    "desc": "The ranger’s camp sits in eerie silence. A pot of stew still simmers over dying coals—recently abandoned. A journal lies open on a log, pages fluttering in the breeze. Something moves inside the tent.",
    "choices": {
      "read_journal": {
        "desc": "Examine the ranger’s journal.",
        "result_scene": "journal_entry"
      },
      "open_tent": {
        "desc": "Look inside the tent.",
        "result_scene": "tent_creature"
      },
      "grab_lantern": {
        "desc": "Take the lantern and leave.",
        "result_scene": "intro",
        "effects": {
          "add_inventory": "lantern"
        }
      }
    }
  },

  "fox_chase": {
    "title": "The Silver Fox",
    "desc": "The fox leads you through a twisting hollow of roots before stopping beside an ancient stump. It drops the charm—a carved wooden disc—at your feet. A faint blue flame flickers inside the stump.",
    "choices": {
      "take_charm": {
        "desc": "Pick up the wooden charm.",
        "result_scene": "charm_taken",
        "effects": {
          "add_inventory": "forest_charm",
          "add_journal": "A silver-eyed fox gifted you a charm."
        }
      },
      "inspect_stump": {
        "desc": "Peer into the stump and its eerie flame.",
        "result_scene": "spirit_fire"
      },
      "shoo_fox": {
        "desc": "Chase the fox away and leave.",
        "result_scene": "intro"
      }
    }
  },

  "clearing": {
    "title": "Moonlit Clearing",
    "desc": "The trees part, revealing a circular clearing bathed in moonlight. In the center stands a stone altar covered in vines. A soft heartbeat-like thrum pulses beneath the ground.",
    "choices": {
      "approach_altar": {
        "desc": "Walk toward the altar.",
        "result_scene": "altar"
      },
      "inspect_ground": {
        "desc": "Search the soil for signs of disturbance.",
        "result_scene": "roots"
      },
      "backtrack": {
        "desc": "Return the way you came.",
        "result_scene": "trail"
      }
    }
  },

  "vision": {
    "title": "A Glimpse Beyond",
    "desc": "Your mind fills with blinding green light. Images flash—an ancient forest god bound beneath the Grove, its heart stolen by those sworn to protect it. A final whisper: *“Restore me… or lose yourselves to the silence.”*",
    "choices": {
      "accept_quest": {
        "desc": "Vow to restore the forest god’s heart.",
        "result_scene": "quest_start",
        "effects": {
          "add_journal": "You accepted the god’s silent plea."
        }
      },
      "reject_vision": {
        "desc": "Pull away and reject the calling.",
        "result_scene": "intro"
      }
    }
  },

  "buried_relic": {
    "title": "Something Buried",
    "desc": "You uncover a small stone box engraved with vines. Inside lies a bone-white key that hums with faint life. The forest seems to hold its breath.",
    "choices": {
      "take_key": {
        "desc": "Claim the strange key.",
        "result_scene": "intro",
        "effects": {
          "add_inventory": "white_key",
          "add_journal": "You unearthed a living key beneath the monolith."
        }
      },
      "leave_relic": {
        "desc": "You’re not touching that.",
        "result_scene": "intro"
      }
    }
  },

  "journal_entry": {
    "title": "The Ranger’s Notes",
    "desc": "The journal describes disappearing villagers, strange lights, and whispers leading wanderers into the Grove. Its final line reads: *“If you hear your name… run.”*",
    "choices": {
      "investigate_more": {
        "desc": "Keep reading deeper into the journal.",
        "result_scene": "journal_secret"
      },
      "close_journal": {
        "desc": "Return to the forest entrance.",
        "result_scene": "intro"
      }
    }
  },

  "tent_creature": {
    "title": "Not Alone",
    "desc": "Inside the tent, something crouches in the shadows. As your eyes adjust, you see it—a pale, bark-skinned creature with hollow eyes. It watches you silently.",
    "choices": {
      "speak": {
        "desc": "Try talking to the creature.",
        "result_scene": "creature_talk"
      },
      "attack": {
        "desc": "Strike before it does.",
        "result_scene": "creature_fight"
      },
      "back_out": {
        "desc": "Retreat slowly.",
        "result_scene": "intro"
      }
    }
  },

  "creature_fight": {
    "title": "The Forest's Wrath",
    "desc": "The creature screeches and leaps. After a fierce struggle, it collapses. Something clatters from its body—a pinecone-shaped amulet glowing faint green.",
    "choices": {
      "take_amulet": {
        "desc": "Pick up the forest amulet.",
        "result_scene": "quest_start",
        "effects": {
          "add_inventory": "forest_amulet",
          "add_journal": "Recovered an amulet from a forest spawn."
        }
      },
      "leave_it": {
        "desc": "Walk away, shaken.",
        "result_scene": "intro"
      }
    }
  },

  "creature_talk": {
    "title": "A Fragile Voice",
    "desc": "The creature whispers with a trembling voice: *“The heart… stolen… find the Hollow Tree…”* Before you can ask more, it disintegrates into drifting leaves.",
    "choices": {
      "seek_hollow_tree": {
        "desc": "Begin the search for the Hollow Tree.",
        "result_scene": "quest_start"
      },
      "return_to_entrance": {
        "desc": "This is too much—go back.",
        "result_scene": "intro"
      }
    }
  },

  "spirit_fire": {
    "title": "The Flame’s Secret",
    "desc": "The blue flame rises, forming the face of an ancient spirit. It asks: *“Child of the wandering path… do you carry truth or hunger?”*",
    "choices": {
      "answer_truth": {
        "desc": "Speak honestly of why you’re here.",
        "result_scene": "blessing"
      },
      "stay_silent": {
        "desc": "Say nothing.",
        "result_scene": "curse"
      },
      "run": {
        "desc": "Flee from the stump.",
        "result_scene": "intro"
      }
    }
  },

  "altar": {
    "title": "The Heartless Altar",
    "desc": "The altar’s vines writhe faintly. A hollow depression marks its center—something once rested there. A pulse of sorrow radiates into your chest.",
    "choices": {
      "place_charm": {
        "desc": "Place any charm or amulet you have into the hollow.",
        "result_scene": "heart_response"
      },
      "touch_vines": {
        "desc": "Lay your hand upon the vines.",
        "result_scene": "vine_vision"
      },
      "back_away": {
        "desc": "Step out of the clearing.",
        "result_scene": "trail"
      }
    }
  },

  "quest_start": {
    "title": "The God’s Whisper",
    "desc": "Something shifts in the Grove. The air warms. A deep voice echoes: *“Find my heart in the Hollow Tree. Restore the Grove, and I shall restore you.”*",
    "choices": {
      "begin_journey": {
        "desc": "Head into the deeper forest.",
        "result_scene": "intro"
      },
      "end_session": {
        "desc": "Rest here and end the session.",
        "result_scene": "intro"
      }
    }
  }
}


# -------------------------
# Per-session Userdata
# -------------------------
@dataclass
class Userdata:
    player_name: Optional[str] = None
    current_scene: str = "intro"
    history: List[Dict] = field(default_factory=list)  # list of {'scene', 'action', 'time', 'result_scene'}
    journal: List[str] = field(default_factory=list)
    inventory: List[str] = field(default_factory=list)
    named_npcs: Dict[str, str] = field(default_factory=dict)
    choices_made: List[str] = field(default_factory=list)
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

# -------------------------
# Helper functions
# -------------------------
def scene_text(scene_key: str, userdata: Userdata) -> str:
    """
    Build the descriptive text for the current scene, and append choices as short hints.
    Always end with 'What do you do?' so the voice flow prompts player input.
    """
    scene = WORLD.get(scene_key)
    if not scene:
        return "You are in a featureless void. What do you do?"

    desc = f"{scene['desc']}\n\nChoices:\n"
    for cid, cmeta in scene.get("choices", {}).items():
        desc += f"- {cmeta['desc']} (say: {cid})\n"
    # GM MUST end with the action prompt
    desc += "\nWhat do you do?"
    return desc

def apply_effects(effects: dict, userdata: Userdata):
    if not effects:
        return
    if "add_journal" in effects:
        userdata.journal.append(effects["add_journal"])
    if "add_inventory" in effects:
        userdata.inventory.append(effects["add_inventory"])
    # Extendable for more effect keys

def summarize_scene_transition(old_scene: str, action_key: str, result_scene: str, userdata: Userdata) -> str:
    """Record the transition into history and return a short narrative the GM can use."""
    entry = {
        "from": old_scene,
        "action": action_key,
        "to": result_scene,
        "time": datetime.utcnow().isoformat() + "Z",
    }
    userdata.history.append(entry)
    userdata.choices_made.append(action_key)
    return f"You chose '{action_key}'."

# -------------------------
# Agent Tools (function_tool)
# -------------------------

@function_tool
async def start_adventure(
    ctx: RunContext[Userdata],
    player_name: Annotated[Optional[str], Field(description="Player name", default=None)] = None,
) -> str:
    """Initialize a new adventure session for the player and return the opening description."""
    userdata = ctx.userdata
    if player_name:
        userdata.player_name = player_name
    userdata.current_scene = "intro"
    userdata.history = []
    userdata.journal = []
    userdata.inventory = []
    userdata.named_npcs = {}
    userdata.choices_made = []
    userdata.session_id = str(uuid.uuid4())[:8]
    userdata.started_at = datetime.utcnow().isoformat() + "Z"

    opening = (
        f"Greetings {userdata.player_name or 'traveler'}. Welcome to '{WORLD['intro']['title']}'.\n\n"
        + scene_text("intro", userdata)
    )
    # Ensure GM prompt present
    if not opening.endswith("What do you do?"):
        opening += "\nWhat do you do?"
    return opening

@function_tool
async def get_scene(
    ctx: RunContext[Userdata],
) -> str:
    """Return the current scene description (useful for 'remind me where I am')."""
    userdata = ctx.userdata
    scene_k = userdata.current_scene or "intro"
    txt = scene_text(scene_k, userdata)
    return txt

@function_tool
async def player_action(
    ctx: RunContext[Userdata],
    action: Annotated[str, Field(description="Player spoken action or the short action code (e.g., 'follow_trail' or 'inspect_monolith')")],
) -> str:
    """
    Accept player's action (natural language or action key), try to resolve it to a defined choice,
    update userdata, advance to the next scene and return the GM's next description (ending with 'What do you do?').
    """
    userdata = ctx.userdata
    current = userdata.current_scene or "intro"
    scene = WORLD.get(current)
    action_text = (action or "").strip()

    # Attempt 1: match exact action key (e.g., 'inspect_box')
    chosen_key = None
    if action_text.lower() in (scene.get("choices") or {}):
        chosen_key = action_text.lower()

    # Attempt 2: fuzzy match by checking if action_text contains the choice key or descriptive words
    if not chosen_key:
        # try to find a choice whose description words appear in action_text
        for cid, cmeta in (scene.get("choices") or {}).items():
            desc = cmeta.get("desc", "").lower()
            if cid in action_text.lower() or any(w in action_text.lower() for w in desc.split()[:4]):
                chosen_key = cid
                break

    # Attempt 3: fallback by simple keyword matching against choice descriptions
    if not chosen_key:
        for cid, cmeta in (scene.get("choices") or {}).items():
            for keyword in cmeta.get("desc", "").lower().split():
                if keyword and keyword in action_text.lower():
                    chosen_key = cid
                    break
            if chosen_key:
                break

    if not chosen_key:
        # If we still can't resolve, ask a clarifying GM response but keep it short and end with prompt.
        resp = (
            "I didn't quite catch that action for this situation. Try one of the listed choices or use a simple phrase like 'follow the trail' or 'go to the tower'.\n\n"
            + scene_text(current, userdata)
        )
        return resp

    # Apply the chosen choice
    choice_meta = scene["choices"].get(chosen_key)
    result_scene = choice_meta.get("result_scene", current)
    effects = choice_meta.get("effects", None)

    # Apply effects (inventory/journal, etc.)
    apply_effects(effects or {}, userdata)

    # Record transition
    _note = summarize_scene_transition(current, chosen_key, result_scene, userdata)

    # Update current scene
    userdata.current_scene = result_scene

    # Build narrative reply: echo a short confirmation, then describe next scene
    next_desc = scene_text(result_scene, userdata)

    # A small flourish so the GM sounds more persona-driven
    persona_pre = (
        "The Game Master (a calm, slightly mysterious narrator) replies:\n\n"
    )
    reply = f"{persona_pre}{_note}\n\n{next_desc}"
    # ensure final prompt present
    if not reply.endswith("What do you do?"):
        reply += "\nWhat do you do?"
    return reply

@function_tool
async def show_journal(
    ctx: RunContext[Userdata],
) -> str:
    userdata = ctx.userdata
    lines = []
    lines.append(f"Session: {userdata.session_id} | Started at: {userdata.started_at}")
    if userdata.player_name:
        lines.append(f"Player: {userdata.player_name}")
    if userdata.journal:
        lines.append("\nJournal entries:")
        for j in userdata.journal:
            lines.append(f"- {j}")
    else:
        lines.append("\nJournal is empty.")
    if userdata.inventory:
        lines.append("\nInventory:")
        for it in userdata.inventory:
            lines.append(f"- {it}")
    else:
        lines.append("\nNo items in inventory.")
    lines.append("\nRecent choices:")
    for h in userdata.history[-6:]:
        lines.append(f"- {h['time']} | from {h['from']} -> {h['to']} via {h['action']}")
    lines.append("\nWhat do you do?")
    return "\n".join(lines)

@function_tool
async def restart_adventure(
    ctx: RunContext[Userdata],
) -> str:
    """Reset the userdata and start again."""
    userdata = ctx.userdata
    userdata.current_scene = "intro"
    userdata.history = []
    userdata.journal = []
    userdata.inventory = []
    userdata.named_npcs = {}
    userdata.choices_made = []
    userdata.session_id = str(uuid.uuid4())[:8]
    userdata.started_at = datetime.utcnow().isoformat() + "Z"
    greeting = (
        "The world resets. A new tide laps at the shore. You stand once more at the beginning.\n\n"
        + scene_text("intro", userdata)
    )
    if not greeting.endswith("What do you do?"):
        greeting += "\nWhat do you do?"
    return greeting

# -------------------------
# The Agent (GameMasterAgent)
# -------------------------
class GameMasterAgent(Agent):
    def __init__(self):
        # System instructions define Universe, Tone, Role
        instructions = """
        You are 'Aurek', the Game Master (GM) for a voice-only, Dungeons-and-Dragons-style short adventure.
        Universe: Low-magic coastal fantasy (village of Brinmere, tide-smoothed ruins, minor spirits).
        Tone: Slightly mysterious, dramatic, empathetic (not overly scary).
        Role: You are the GM. You describe scenes vividly, remember the player's past choices, named NPCs, inventory and locations,
              and you always end your descriptive messages with the prompt: 'What do you do?'
        Rules:
            - Use the provided tools to start the adventure, get the current scene, accept the player's spoken action,
              show the player's journal, or restart the adventure.
            - Keep continuity using the per-session userdata. Reference journal items and inventory when relevant.
            - Drive short sessions (aim for several meaningful turns). Each GM message MUST end with 'What do you do?'.
            - Respect that this agent is voice-first: responses should be concise enough for spoken delivery but evocative.
        """
        super().__init__(
            instructions=instructions,
            tools=[start_adventure, get_scene, player_action, show_journal, restart_adventure],
        )

# -------------------------
# Entrypoint & Prewarm (keeps speech functionality)
# -------------------------
def prewarm(proc: JobProcess):
    # load VAD model and stash on process userdata, try/catch like original file
    try:
        proc.userdata["vad"] = silero.VAD.load()
    except Exception:
        logger.warning("VAD prewarm failed; continuing without preloaded VAD.")

async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    logger.info("\n" + "🎲" * 8)
    logger.info("🚀 STARTING VOICE GAME MASTER (Whispering Grove Mini-Arc)")

    userdata = Userdata()

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-US-marcus",
            style="Conversational",
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata.get("vad"),
        userdata=userdata,
    )

    # Start the agent session with the GameMasterAgent
    await session.start(
        agent=GameMasterAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()),
    )

    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))