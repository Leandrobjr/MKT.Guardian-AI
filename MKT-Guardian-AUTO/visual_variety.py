"""Variedade visual — evita imagens repetidas no fallback Gemini."""

import hashlib
import json
import os
import random
import time


class VisualVarietyEngine:
    SHOT_VARIANTS = [
        "Medium documentary shot, 50mm lens, shallow depth of field.",
        "Over-the-shoulder angle, WhatsApp chat clearly visible on phone screen.",
        "Close-up on hands holding smartphone, worried expression on face.",
        "Three-quarter candid pose, subject not looking at camera.",
        "Waist-up portrait, phone held at chest height showing chat.",
    ]
    LIGHTING = [
        "Warm morning window light from the left side.",
        "Soft overcast daylight, natural even exposure.",
        "Late afternoon golden hour through curtains.",
        "Neutral indoor daylight mixed with window light.",
    ]

    def __init__(self, base_dir: str):
        self.log_path = os.path.join(base_dir, "contexto_negocio", "memoria", "imagens_prompts.jsonl")
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def _recent_hashes(self, limit: int = 12) -> set[str]:
        if not os.path.isfile(self.log_path):
            return set()
        hashes: set[str] = set()
        with open(self.log_path, "r", encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
        for ln in lines[-limit:]:
            try:
                hashes.add(json.loads(ln).get("hash", ""))
            except json.JSONDecodeError:
                continue
        return hashes

    def _hash_prompt(self, text: str) -> str:
        normalized = " ".join(text.lower().split())[:500]
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def _log_prompt(self, prompt: str, basename: str = "") -> None:
        record = {
            "data": time.strftime("%Y-%m-%d %H:%M"),
            "hash": self._hash_prompt(prompt),
            "basename": basename,
            "trecho": prompt[:120],
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _anti_repeat_clause(self, base_scene: str) -> str:
        recent = self._recent_hashes()
        h = self._hash_prompt(base_scene)
        if h in recent:
            return (
                "CRITICAL: Generate a COMPLETELY DIFFERENT person (age, gender, ethnicity, hair, clothes) "
                "and DIFFERENT room layout from any prior campaign. Avoid kitchen table with middle-aged woman."
            )
        return (
            "Create a unique individual with distinct face, hairstyle, outfit colors and background details. "
            "Avoid generic stock photo look."
        )

    PERSONA_ALIASES = {
        "empresarios": "profissionais",
        "geral": "massa",
    }

    def pick_persona(self, context_data: dict, publico_id: str, publico_slug: str = "") -> dict:
        if publico_slug == "escolas":
            escola = [
                {"nome": "Paula", "idade": 44, "profissao": "Diretora escolar", "cidade": "Brasília"},
                {"nome": "Ana", "idade": 45, "profissao": "Professora", "cidade": "Belo Horizonte"},
            ]
            return random.choice(escola)

        lookup_id = self.PERSONA_ALIASES.get(publico_id, publico_id)
        personas = context_data.get("PERSONAS_EXEMPLO", [])
        candidatos = [p for p in personas if p.get("publico_id") == lookup_id]
        if not candidatos:
            candidatos = personas
        if not candidatos:
            return {"nome": "Bruno", "idade": 42, "profissao": "trabalhador", "cidade": "São Paulo"}
        return random.choice(candidatos)

    def enrich(self, creative_data: dict, config: dict, context_data: dict) -> dict:
        publico_id = config.get("publico_id", "massa")
        publico_slug = config.get("publico_slug", publico_id)
        persona = self.pick_persona(context_data, publico_id, publico_slug)
        shot = random.choice(self.SHOT_VARIANTS)
        lighting = random.choice(self.LIGHTING)
        variation_id = f"{int(time.time())}-{random.randint(1000, 9999)}"
        anti_repeat = self._anti_repeat_clause(creative_data.get("direcao_arte_emocional", ""))

        genero_hint = creative_data.get("genero_personagem_visual", "")
        creative_data["persona_visual"] = persona
        creative_data["visual_shot_variant"] = shot
        creative_data["visual_lighting"] = lighting
        creative_data["visual_variation_id"] = variation_id

        sufixo = (
            f"Main subject: Brazilian {persona['profissao']}, approximately {persona['idade']} years old, "
            f"from {persona['cidade']}. "
            f"{genero_hint + '. ' if genero_hint else ''}"
            f"{shot} {lighting} "
            f"Unique campaign visual ID {variation_id}. {anti_repeat}"
        )
        creative_data["direcao_arte_emocional"] = (
            f"{creative_data.get('direcao_arte_emocional', '').rstrip()} {sufixo}"
        )
        return creative_data

    def register_generated(self, prompt: str, basename: str = "") -> None:
        self._log_prompt(prompt, basename)
