"""
GymBuddy agent logic and HF pipeline integration.

Purpose: Provide safe, structured, and domain-restricted guidance for training, fitness,
and sports performance using GPT-OSS-120B via Hugging Face transformers.

This module exposes a simple function `generate_gymbuddy_reply(message, profile)` that the
Flask backend can call. It handles:
- Onboarding profile integration
- Domain guardrails (reject non-fitness topics)
- Structured, actionable responses

Note: While the project uses the Agno AI Framework conceptually for agent structure and
guardrails, generation is performed via a local HF pipeline to the model
`openai/gpt-oss-120b` as requested.
"""

from __future__ import annotations

import os
import re
import threading
from typing import Any, Dict

from dotenv import load_dotenv
from transformers import pipeline
import torch  # noqa: F401  # Imported for torch_dtype="auto" compatibility


load_dotenv()


MODEL_ID = os.getenv("GYM_MODEL_ID", "openai/gpt-oss-120b")
_pipe = None
_pipe_lock = threading.Lock()


def _ensure_hf_token_env() -> None:
    """Normalize HF token environment variables if needed.

    Accepts any of: HUGGINGFACE_HUB_TOKEN, HF_TOKEN, HUGGINGFACE_TOKEN.
    If only HUGGINGFACE_TOKEN is set, copy it to HUGGINGFACE_HUB_TOKEN for transformers.
    """
    if os.getenv("HUGGINGFACE_HUB_TOKEN"):
        return
    token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")
    if token:
        os.environ.setdefault("HUGGINGFACE_HUB_TOKEN", token)


def _get_text_generation_pipeline():
    global _pipe
    if _pipe is None:
        with _pipe_lock:
            if _pipe is None:
                _ensure_hf_token_env()
                _pipe = pipeline(
                    "text-generation",
                    model=MODEL_ID,
                    torch_dtype="auto",
                    device_map="auto",
                )
    return _pipe


def is_fitness_domain(text: str) -> bool:
    """Heuristic filter to keep conversations strictly on-topic."""
    if not text:
        return False
    t = text.lower()
    keywords = [
        # English
        "gym", "workout", "training", "exercise", "exercises", "muscle", "hypertrophy",
        "strength", "endurance", "mobility", "flexibility", "recovery", "nutrition",
        "diet", "protein", "carbs", "fat", "sleep", "injury", "injuries", "fat loss",
        "weight loss", "cardio", "sets", "reps", "volume", "rpe", "1rm", "conditioning",
        "athletic", "sports performance", "powerlifting", "bodybuilding", "crossfit",
        # Portuguese
        "academia", "treino", "treinamento", "exercício", "exercícios", "musculação",
        "hipertrofia", "força", "resistência", "mobilidade", "flexibilidade",
        "recuperação", "nutrição", "dieta", "proteína", "carboidrato", "gordura", "sono",
        "lesão", "lesões", "emagrecimento", "perda de gordura", "cardio", "séries",
        "repetições", "volume", "rpe", "1rm", "condicionamento", "desempenho esportivo",
    ]
    return any(k in t for k in keywords)


def build_profile_summary(profile: Dict[str, Any]) -> str:
    """Create a concise profile string for prompts and UI."""
    if not profile:
        return ""
    w = profile.get("weight_kg")
    h = profile.get("height_cm")
    age = profile.get("age")
    gender = profile.get("gender")
    goal = profile.get("main_goal")
    exp = profile.get("experience")
    days = profile.get("days_per_week")
    mins = profile.get("minutes_per_workout")
    inj = profile.get("injuries_details") or ("none" if not profile.get("injuries_yes_no") else "yes")
    parts = []
    if w: parts.append(f"{w}kg")
    if h: parts.append(f"{h}cm")
    if age: parts.append(f"age {age}")
    if gender: parts.append(str(gender))
    if exp: parts.append(str(exp))
    if days: parts.append(f"{days}x/week")
    if mins: parts.append(f"{mins}min/workout")
    if goal: parts.append(f"goal: {goal}")
    if inj: parts.append(f"injuries: {inj}")
    return ", ".join(parts)


def _build_system_prompt(profile: Dict[str, Any]) -> str:
    profile_str = build_profile_summary(profile)
    return (
        "You are GymBuddy, an advanced AI fitness assistant.\n"
        "- Only answer topics about gym training, exercises, anatomy, recovery, basic nutrition, and sports performance.\n"
        "- If the user asks about unrelated topics, politely refuse and redirect back to fitness.\n"
        "- Safety first: avoid medical diagnoses. When discussing supplements or injuries, include disclaimers and advise consulting a professional if needed.\n"
        "- Style: encouraging, professional, clear. No slang, no emojis.\n"
        "- Output format: use short sections with headings like: Plan, Tips, Warnings, Progression.\n"
        "- Provide short-term and long-term steps where relevant.\n"
        f"- User profile (from onboarding): {profile_str}\n"
    )


def _extract_generated_text(outputs: Any) -> str:
    """Normalize different pipeline output formats to a plain string."""
    try:
        # Newer chat pipelines may return a list of dicts with 'generated_text'
        text = outputs[0].get("generated_text")
        if isinstance(text, list) and text and isinstance(text[-1], dict):
            # Chat-style messages
            return text[-1].get("content", "").strip()
        if isinstance(text, str):
            return text.strip()
    except Exception:
        pass
    # Fallback: best-effort string cast
    return str(outputs)


def generate_gymbuddy_reply(message: str, profile: Dict[str, Any] | None) -> str:
    """Generate a structured, safe reply using GPT-OSS-120B and the onboarding profile."""
    if not message or not message.strip():
        return "Please provide a fitness-related question to begin."

    # Domain guardrails: reject/redirect if off-topic
    if not is_fitness_domain(message):
        return (
            "I specialize in gym training, fitness, and sports performance. "
            "Please ask about workouts, exercises, programming, recovery, or basic sports nutrition."
        )

    system_prompt = _build_system_prompt(profile or {})
    pipe = _get_text_generation_pipeline()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message.strip()},
    ]

    outputs = pipe(
        messages,
        max_new_tokens=500,
        do_sample=True,
        top_p=0.9,
        temperature=0.7,
    )
    text = _extract_generated_text(outputs)

    # Ensure structured headings if the model response isn't formatted well
    if not re.search(r"(?i)plan|tips|warnings|progress", text):
        text = (
            "Plan\n- " + text.strip() + "\n\n"
            "Tips\n- Focus on technique and progressive overload.\n\n"
            "Warnings\n- Stop if you feel sharp pain; consult a professional for injuries.\n\n"
            "Progression\n- Increase volume or load gradually each week."
        )

    return text.strip()


if __name__ == "__main__":
    # Simple manual test
    demo_profile = {
        "weight_kg": 70,
        "height_cm": 175,
        "age": 25,
        "gender": "male",
        "main_goal": "hypertrophy",
        "experience": "beginner",
        "days_per_week": 4,
        "minutes_per_workout": 60,
        "injuries_yes_no": False,
        "injuries_details": "",
    }
    reply = generate_gymbuddy_reply(
        "I can train 4 days per week. How should I split my hypertrophy plan?",
        demo_profile,
    )
    print("\n=== GymBuddy ===\n", reply)