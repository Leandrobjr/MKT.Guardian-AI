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
        self.gender_state_path = os.path.join(
            base_dir, "contexto_negocio", "memoria", "genero_alternancia.json"
        )
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def _load_gender_state(self) -> dict:
        if not os.path.isfile(self.gender_state_path):
            return {}
        try:
            with open(self.gender_state_path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_gender_state(self, state: dict):
        try:
            with open(self.gender_state_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def next_alternating_gender(self, publico_slug: str = "geral") -> str:
        """Alterna M/F a cada campanha quando a narrativa não fixa o sexo."""
        state = self._load_gender_state()
        last = state.get(publico_slug) or state.get("_global", "masculino")
        return "feminino" if last == "masculino" else "masculino"

    def record_gender(self, genero: str, publico_slug: str = "geral"):
        if genero not in ("feminino", "masculino"):
            return
        state = self._load_gender_state()
        state[publico_slug] = genero
        state["_global"] = genero
        self._save_gender_state(state)

    def _age_range(self, context_data: dict, key: str) -> tuple[int, int] | None:
        faixa = (
            context_data.get("GUARDRAILS_PERSONAGENS", {})
            .get("faixas_etarias", {})
            .get(key, {})
        )
        if faixa.get("min") is not None and faixa.get("max") is not None:
            return int(faixa["min"]), int(faixa["max"])
        return None

    def _clamp_age(self, idade: int, lo: int, hi: int) -> int:
        return max(lo, min(hi, idade))

    def _apply_age_guardrails(self, persona: dict, publico_slug: str, context_data: dict) -> dict:
        p = dict(persona)
        if publico_slug == "idosos":
            rng = self._age_range(context_data, "idosos") or (65, 85)
            p["idade"] = self._clamp_age(p.get("idade", 68), *rng)
        elif publico_slug == "pais":
            rng = self._age_range(context_data, "pais") or (35, 50)
            p["idade"] = self._clamp_age(p.get("idade", 42), *rng)
        return p

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

    def _anti_repeat_clause(self, base_scene: str, lock_gender: bool = False) -> str:
        recent = self._recent_hashes()
        h = self._hash_prompt(base_scene)
        if h in recent:
            # Quando o gênero é obrigatório (coerência com a narrativa), NÃO peça gênero diferente
            variacao = "age, ethnicity, hair, clothes" if lock_gender else "age, gender, ethnicity, hair, clothes"
            return (
                f"CRITICAL: Generate a COMPLETELY DIFFERENT person ({variacao}) "
                "and DIFFERENT room layout from any prior campaign."
            )
        return (
            "Create a unique individual with distinct face, hairstyle, outfit colors and background details. "
            "Avoid generic stock photo look."
        )

    PERSONA_ALIASES = {
        "empresarios": "profissionais",
        "geral": "massa",
    }

    def pick_persona(
        self, context_data: dict, publico_id: str, publico_slug: str = "", genero: str = ""
    ) -> dict:
        if publico_slug == "escolas":
            escola = [
                {"nome": "Paula", "idade": 44, "profissao": "Diretora escolar", "cidade": "Brasília", "genero": "feminino"},
                {"nome": "Ana", "idade": 45, "profissao": "Professora", "cidade": "Belo Horizonte", "genero": "feminino"},
            ]
            candidatos = escola
        else:
            lookup_id = self.PERSONA_ALIASES.get(publico_id, publico_id)
            personas = context_data.get("PERSONAS_EXEMPLO", [])
            candidatos = [p for p in personas if p.get("publico_id") == lookup_id]
            if genero in ("feminino", "masculino"):
                por_genero = [p for p in candidatos if p.get("genero") == genero]
                if por_genero:
                    candidatos = por_genero
            if not candidatos:
                candidatos = personas
            if not candidatos:
                return {"nome": "Bruno", "idade": 42, "profissao": "trabalhador", "cidade": "São Paulo", "genero": "masculino"}

        persona = random.choice(candidatos)
        return self._apply_age_guardrails(persona, publico_slug, context_data)

    def enrich(self, creative_data: dict, config: dict, context_data: dict) -> dict:
        publico_id = config.get("publico_id", "massa")
        publico_slug = config.get("publico_slug", publico_id)
        persona = self.pick_persona(context_data, publico_id, publico_slug, genero=creative_data.get("genero_campanha", ""))
        shot = random.choice(self.SHOT_VARIANTS)
        lighting = random.choice(self.LIGHTING)
        variation_id = f"{int(time.time())}-{random.randint(1000, 9999)}"

        # Gênero obrigatório para coerência com a narrativa (Mãe→mulher, Pai→homem)
        genero = creative_data.get("genero_campanha", "")
        genero_lock = ""
        if genero == "feminino":
            genero_lock = "MANDATORY: the single main subject is a WOMAN (female). "
        elif genero == "masculino":
            genero_lock = "MANDATORY: the single main subject is a MAN (male). "

        anti_repeat = self._anti_repeat_clause(
            creative_data.get("direcao_arte_emocional", ""), lock_gender=bool(genero_lock)
        )

        genero_hint = creative_data.get("genero_personagem_visual", "")
        creative_data["persona_visual"] = persona
        creative_data["visual_shot_variant"] = shot
        creative_data["visual_lighting"] = lighting
        creative_data["visual_variation_id"] = variation_id

        sufixo = (
            f"{genero_lock}"
            f"Approximately {persona['idade']} years old, from {persona['cidade']}. "
            f"Neat groomed appearance, clean casual clothing (pressed shirt or blouse, clean jeans or chinos), "
            f"middle-income Brazilian aesthetic — dignified everyday look, never ragged or poverty signals. "
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
