import re
from dataclasses import dataclass

@dataclass
class PromptSettings:
    animation: str
    frames: int
    fps: int
    intensity: float
    direction: str
    weapon: str | None = None
    mood: str | None = None

KEYS = {
    'walk': ['walk', 'walking', 'stroll'],
    'run': ['run', 'running', 'dash', 'sprint'],
    'jump': ['jump', 'leap', 'hop'],
    'attack': ['attack', 'slash', 'punch', 'swing', 'strike', 'stab'],
    'ranged': ['ranged', 'bow', 'arrow', 'shoot', 'shooting', 'fire', 'firing', 'aim'],
    'cast': ['cast', 'spell', 'magic', 'summon'],
    'hurt': ['hurt', 'hit', 'knockback'],
    'damage': ['damage', 'recoil', 'impact', 'stagger'],
    'heal': ['heal', 'healing', 'recover', 'recovery'],
    'buff': ['buff', 'boost', 'empower', 'bless'],
    'shield': ['shield', 'guard', 'block', 'protect', 'barrier'],
    'poison': ['poison', 'venom', 'toxic', 'curse', 'toxin'],
    'spin': ['spin', 'rotate', 'twirl'],
    'bounce': ['bounce', 'bob'],
    'idle': ['idle', 'stand', 'breathing', 'breathe'],
}

def parse_prompt(prompt: str, default_animation='walk', frames=8, fps=10) -> PromptSettings:
    p = (prompt or '').lower()
    animation = default_animation
    for name, words in KEYS.items():
        if any(w in p for w in words):
            animation = name
            break
    m = re.search(r'(\d+)\s*(frames?|frame)', p)
    if m:
        frames = max(2, min(32, int(m.group(1))))
    m = re.search(r'(\d+)\s*(fps|frames per second)', p)
    if m:
        fps = max(1, min(30, int(m.group(1))))
    intensity = 1.0
    if any(w in p for w in ['fast', 'hard', 'big', 'strong', 'wild', 'heavy']): intensity = 1.45
    if any(w in p for w in ['slow', 'small', 'subtle', 'soft']): intensity = 0.65
    direction = 'right'
    if 'left' in p: direction = 'left'
    if 'up' in p: direction = 'up'
    if 'down' in p: direction = 'down'
    weapon = None
    for w in ['sword','axe','spear','staff','bow','dagger','hammer','wand']:
        if w in p: weapon = w
    mood = None
    for w in ['angry','happy','sad','scared','heroic','evil','cute']:
        if w in p: mood = w
    return PromptSettings(animation, frames, fps, intensity, direction, weapon, mood)
