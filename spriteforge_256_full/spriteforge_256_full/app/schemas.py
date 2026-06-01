from typing import Literal, Optional

from pydantic import BaseModel, Field

AnimationName = Literal['idle', 'walk', 'run', 'jump', 'attack', 'ranged', 'cast', 'hurt', 'damage', 'heal', 'buff', 'shield', 'poison', 'spin', 'bounce']

class GenerateRequest(BaseModel):
    animation: AnimationName = 'walk'
    prompt: str = ''
    frames: int = Field(8, ge=2, le=32)
    fps: int = Field(10, ge=1, le=30)
    pixel_size: int = Field(256, ge=64, le=512)
    spritesheet_columns: int = Field(8, ge=1, le=16)
    remove_background: bool = False
    outline: bool = False
    shadow: bool = True
    smart_prompt: bool = True
    seed: Optional[int] = None

class JobResult(BaseModel):
    job_id: str
    preview_gif: str
    spritesheet: str
    frames_zip: str
    metadata: dict
