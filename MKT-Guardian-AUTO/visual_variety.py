"""Variedade visual — casting, ambientes rotativos e anti-repetição de prompts."""

from __future__ import annotations

import hashlib
import json
import os
import random
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from campaign_history import CampaignHistory


class VisualVarietyEngine:
    """VisualCastingDirector — personas, ambientes e dedup de prompts."""

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

    AMBIENTES_ICP: dict[str, list[str]] = {
        "pais": [
            "Clean well-kept Brazilian home living room with sofa and TV stand, tidy painted walls, pleasant natural daylight, middle-income comfort.",
            "Bright Brazilian home balcony with simple furniture, plants, tidy walls, natural daylight.",
            "Organized Brazilian home office corner, tidy shelves, pleasant daylight, clean casual feel.",
            "Modern modest Brazilian open-plan living and dining area, clean counters, painted walls, natural light.",
            "Neat Brazilian kitchen-living integrated space, clean surfaces, middle-income aesthetic, daylight.",
            "Calm Brazilian bedroom doorway view to living area, tidy family home, soft natural light.",
        ],
        "massa": [
            "Clean Brazilian urban apartment living room, tidy painted walls, modest middle-income decor, daylight.",
            "Simple Brazilian home workspace at dining table, organized, pleasant window light.",
            "Brazilian apartment varanda with city view, neat plants, casual middle-income setting.",
            "Well-kept Brazilian living room with bookshelf and sofa, natural daylight.",
            "Organized Brazilian home entry hall near living room, clean walls, everyday comfort.",
            "Bright Brazilian condo interior, tidy kitchen-living area, relatable middle class.",
        ],
        "idosos": [
            "Clean well-kept Brazilian living room, comfortable sofa, family photos on shelf, pleasant daylight, retirement comfort.",
            "Tidy Brazilian dining room adjacent to living area, modest middle-income home, natural light.",
            "Bright Brazilian covered porch or varanda with simple chairs, peaceful afternoon light.",
            "Organized Brazilian bedroom-living view, neat bedding visible, warm daylight.",
            "Calm Brazilian home TV area with remote and side table, dignified retirement setting.",
            "Well-painted Brazilian living room with armchair and side lamp, cozy neat environment.",
        ],
        "empresarios": [
            "Clean organized Brazilian neighborhood shop interior, products on shelves, commercial counter, daylight.",
            "Small Brazilian store back office with invoices and calculator, working commerce setting.",
            "Brazilian commercial counter with cash register and merchandise, active retail workspace.",
            "Modest Brazilian office behind shop with stock shelves and desk, natural light.",
            "Brazilian workshop-store hybrid with tools and products neatly arranged, daylight.",
            "Simple Brazilian business desk with computer off, receipts organized, commercial room.",
        ],
        "escolas": [
            "Clean Brazilian school administrative office, bulletin board, diplomas on wall, professional daylight.",
            "Brazilian school staff room with books and meeting table, educational environment.",
            "School coordinator office with student files and computer, tidy institutional setting.",
            "Brazilian school reception area with notice board, professional educational space.",
            "Pedagogical coordination room with charts and plants, pleasant school interior.",
            "School director office overlooking courtyard window, neat administrative environment.",
        ],
    }

    PERSONA_ALIASES = {
        "empresarios": "profissionais",
        "geral": "massa",
    }

    def __init__(self, base_dir: str, history: CampaignHistory | None = None):
        self.base_dir = base_dir
        mem_dir = os.path.join(base_dir, "contexto_negocio", "memoria")
        os.makedirs(mem_dir, exist_ok=True)
        self.log_path = os.path.join(mem_dir, "imagens_prompts.jsonl")
        self.gender_state_path = os.path.join(mem_dir, "genero_alternancia.json")
        self.ambiente_state_path = os.path.join(mem_dir, "ambiente_rotacao.json")
        self._history = history

    def _get_history(self) -> CampaignHistory:
        if self._history is None:
            from campaign_history import CampaignHistory
            self._history = CampaignHistory(self.base_dir)
        return self._history

    def _load_json(self, path: str) -> dict:
        if not os.path.isfile(path):
            return {}
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_json(self, path: str, state: dict) -> None:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _load_gender_state(self) -> dict:
        return self._load_json(self.gender_state_path)

    def _save_gender_state(self, state: dict) -> None:
        self._save_json(self.gender_state_path, state)

    def next_alternating_gender(self, publico_slug: str = "geral") -> str:
        state = self._load_gender_state()
        last = state.get(publico_slug) or state.get("_global", "masculino")
        return "feminino" if last == "masculino" else "masculino"

    def record_gender(self, genero: str, publico_slug: str = "geral") -> None:
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

    def _persona_id(self, persona: dict) -> str:
        if persona.get("persona_id"):
            return str(persona["persona_id"])
        nome = (persona.get("nome") or "x").lower()
        prof = (persona.get("profissao") or "x").lower().replace(" ", "_")[:20]
        return f"{nome}_{prof}"

    def _recent_persona_ids(self, publico_slug: str, limit: int = 5) -> set[str]:
        ids: set[str] = set()
        for row in self._get_history().get_recent(publico_slug, "", limit=limit * 3):
            pid = row.get("persona_id") or ""
            if pid:
                ids.add(pid)
            if len(ids) >= limit:
                break
        return ids

    def pick_persona(
        self,
        context_data: dict,
        publico_id: str,
        publico_slug: str = "",
        genero: str = "",
    ) -> dict:
        lookup_id = self.PERSONA_ALIASES.get(publico_id, publico_id)
        if publico_slug == "escolas":
            lookup_id = "escolas"

        personas = context_data.get("PERSONAS_EXEMPLO", [])
        candidatos = [p for p in personas if p.get("publico_id") == lookup_id]

        if genero in ("feminino", "masculino"):
            por_genero = [p for p in candidatos if p.get("genero") == genero]
            if por_genero:
                candidatos = por_genero

        if not candidatos:
            candidatos = [p for p in personas if p.get("publico_id") == publico_id]
        if not candidatos:
            candidatos = personas
        if not candidatos:
            return {
                "persona_id": "bruno_trabalhador_sp",
                "nome": "Bruno",
                "idade": 42,
                "profissao": "trabalhador",
                "cidade": "São Paulo",
                "genero": "masculino",
                "estilo_vestuario": "camisa polo e jeans limpos",
                "ambiente_preferido": "sala_tv",
                "nivel_socioeconomico": "classe_media",
            }

        used_ids = self._recent_persona_ids(publico_slug or publico_id)
        fresh = [p for p in candidatos if self._persona_id(p) not in used_ids]
        pool = fresh if fresh else candidatos
        persona = random.choice(pool)
        persona = dict(persona)
        persona.setdefault("persona_id", self._persona_id(persona))
        return self._apply_age_guardrails(persona, publico_slug, context_data)

    def pick_ambiente(self, publico_slug: str, persona: dict | None = None) -> str:
        slug = publico_slug if publico_slug in self.AMBIENTES_ICP else "massa"
        ambientes = self.AMBIENTES_ICP.get(slug, self.AMBIENTES_ICP["massa"])

        pref = (persona or {}).get("ambiente_preferido", "")
        if pref:
            for amb in ambientes:
                if pref.replace("_", " ") in amb.lower():
                    return amb

        state = self._load_json(self.ambiente_state_path)
        last_idx = int(state.get(slug, -1))
        next_idx = (last_idx + 1) % len(ambientes)
        state[slug] = next_idx
        self._save_json(self.ambiente_state_path, state)
        return ambientes[next_idx]

    def _recent_hashes(self, limit: int = 12) -> set[str]:
        if not os.path.isfile(self.log_path):
            return set()
        hashes: set[str] = set()
        with open(self.log_path, encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
        for ln in lines[-limit:]:
            try:
                hashes.add(json.loads(ln).get("hash", ""))
            except json.JSONDecodeError:
                continue
        return hashes

    def hash_prompt(self, text: str) -> str:
        normalized = " ".join(text.lower().split())[:500]
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def is_duplicate_prompt(self, prompt: str) -> bool:
        return self.hash_prompt(prompt) in self._recent_hashes()

    def _log_prompt(self, prompt: str, basename: str = "", engine: str = "") -> None:
        record = {
            "data": time.strftime("%Y-%m-%d %H:%M"),
            "hash": self.hash_prompt(prompt),
            "basename": basename,
            "engine": engine,
            "trecho": prompt[:120],
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def register_generated(
        self, prompt: str, basename: str = "", engine: str = ""
    ) -> bool:
        """Registra prompt; retorna False se hash já existia (duplicata)."""
        dup = self.is_duplicate_prompt(prompt)
        self._log_prompt(prompt, basename, engine)
        return not dup

    def _anti_repeat_clause(self, base_scene: str, lock_gender: bool = False) -> str:
        recent = self._recent_hashes()
        h = self.hash_prompt(base_scene)
        if h in recent:
            variacao = "age, ethnicity, hair, clothes, room layout" if lock_gender else (
                "age, gender, ethnicity, hair, clothes, room colors"
            )
            return (
                f"CRITICAL: Generate a COMPLETELY DIFFERENT person ({variacao}) "
                "and DIFFERENT room layout from any prior campaign."
            )
        return (
            "Create a unique individual with distinct face, hairstyle, outfit colors and background details. "
            "Avoid generic stock photo look."
        )

    def kling_variation_suffix(self) -> str:
        return (
            " Alternative unique subject: different face, hairstyle, outfit colors, "
            "distinct room layout — middle-income Brazilian home, neat appearance."
        )

    def enrich(self, creative_data: dict, config: dict, context_data: dict) -> dict:
        publico_id = config.get("publico_id", "massa")
        publico_slug = config.get("publico_slug", publico_id)
        persona = self.pick_persona(
            context_data, publico_id, publico_slug,
            genero=creative_data.get("genero_campanha", ""),
        )
        ambiente = self.pick_ambiente(publico_slug, persona)
        shot = random.choice(self.SHOT_VARIANTS)
        lighting = random.choice(self.LIGHTING)
        variation_id = f"{int(time.time())}-{random.randint(1000, 9999)}"

        genero = creative_data.get("genero_campanha", "")
        genero_lock = ""
        if genero == "feminino":
            genero_lock = "MANDATORY: the single main subject is a WOMAN (female). "
        elif genero == "masculino":
            genero_lock = "MANDATORY: the single main subject is a MAN (male). "

        anti_repeat = self._anti_repeat_clause(
            creative_data.get("direcao_arte_emocional", ""), lock_gender=bool(genero_lock)
        )

        estilo = persona.get("estilo_vestuario", "clean pressed casual shirt and neat jeans or chinos")
        genero_hint = creative_data.get("genero_personagem_visual", "")

        creative_data["persona_visual"] = persona
        creative_data["persona_id"] = persona.get("persona_id", self._persona_id(persona))
        creative_data["ambiente_cena"] = ambiente
        creative_data["visual_shot_variant"] = shot
        creative_data["visual_lighting"] = lighting
        creative_data["visual_variation_id"] = variation_id

        sufixo = (
            f"{genero_lock}"
            f"Subject: {persona.get('profissao', 'Brazilian adult')}, approximately {persona['idade']} years old, "
            f"from {persona['cidade']}. "
            f"Outfit: {estilo}. "
            f"Setting: {ambiente} "
            f"Neat groomed appearance, middle-income Brazilian aesthetic — dignified everyday look, "
            f"never ragged or poverty signals. "
            f"{genero_hint + '. ' if genero_hint else ''}"
            f"{shot} {lighting} "
            f"Unique campaign visual ID {variation_id}. {anti_repeat}"
        )
        creative_data["direcao_arte_emocional"] = (
            f"{creative_data.get('direcao_arte_emocional', '').rstrip()} {sufixo}"
        )
        return creative_data

    def print_qa_checklist(self, creative_data: dict) -> None:
        persona = creative_data.get("persona_visual") or {}
        print("\n📋 QA Visual (casting):")
        print(f"   Persona: {persona.get('nome', '—')} — {persona.get('profissao', '—')} "
              f"({persona.get('idade', '?')} anos, {persona.get('cidade', '—')})")
        print(f"   ID: {creative_data.get('persona_id', '—')}")
        print(f"   Vestimenta: {persona.get('estilo_vestuario', 'casual limpo')}")
        amb = creative_data.get("ambiente_cena") or ""
        print(f"   Ambiente: {amb[:90]}{'…' if len(amb) > 90 else ''}")
        print(f"   Personagem: {creative_data.get('genero_personagem_visual', '—')}")
        print(f"   Shot: {(creative_data.get('visual_shot_variant') or '')[:60]}…")


VisualCastingDirector = VisualVarietyEngine
