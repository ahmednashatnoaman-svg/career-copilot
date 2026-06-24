from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.coaching.llm import LLMService
from app.agents.coaching.memory import PostgresMemory
from app.agents.coaching.observability import get_request_id, log_event
from app.agents.coaching.prompts import (
    ADVICE_SYSTEM,
    CAREER_PLAN_SYSTEM,
    EVALUATION_SYSTEM,
    INTERVIEW_SETUP_SYSTEM,
    QUESTION_SYSTEM,
    ROUTER_SYSTEM,
    SELF_CHECK_SYSTEM,
    SUMMARY_SYSTEM,
)
from app.agents.coaching.schemas import ChatRequest, ChatResponse
from app.agents.coaching.settings import Settings

SubIntent = Literal[
    "mock_interview_start",
    "interview_answer",
    "interview_quit",
    "interview_new_question",
    "career_plan",
    "general_advice",
    "clarification",
]

VALID_SUB_INTENTS = {
    "mock_interview_start",
    "interview_answer",
    "interview_quit",
    "interview_new_question",
    "career_plan",
    "general_advice",
    "clarification",
}

LOGGER = logging.getLogger("career_coaching_agent.graph")


class CareerCoachState(TypedDict, total=False):
    user_id: str
    thread_id: str
    request_id: str | None
    message: str
    mode: str
    max_interview_questions: int
    profile: dict[str, Any]
    messages: list[dict[str, Any]]
    memories: list[dict[str, Any]]
    active_interview: dict[str, Any] | None
    sub_intent: str
    intent_params: dict[str, Any]
    router_decision: dict[str, Any]
    response: str
    next_action: str
    validation: dict[str, Any]
    memory_updates: dict[str, Any]
    interview_turn_to_store: dict[str, Any]
    interview_session_update: dict[str, Any]
    career_plan_to_store: dict[str, Any]
    state_view: dict[str, Any]


class CareerCoachingAgent:
    def __init__(
        self,
        settings: Settings,
        memory: PostgresMemory,
        checkpointer=None,
    ) -> None:
        self.settings = settings
        self.memory = memory
        self.llm = LLMService(settings)
        # Accept an externally-provided checkpointer (shared PostgresSaver from
        # the Supervisor) instead of building our own at import time.
        self._checkpointer = checkpointer
        self.graph = self._build_graph()

    @property
    def llm_configured(self) -> bool:
        return self.llm.configured

    def close(self) -> None:
        # Lifecycle is now managed externally when a shared checkpointer is used.
        pass

    def invoke(self, request: ChatRequest) -> ChatResponse:
        self.llm.clear_error()
        profile = request.profile.model_dump(exclude_none=True)
        input_state: CareerCoachState = {
            "user_id": request.user_id,
            "thread_id": request.thread_id,
            "request_id": get_request_id(),
            "message": request.message,
            "mode": request.mode,
            "profile": profile,
            "max_interview_questions": request.max_interview_questions,
        }
        config = {"configurable": {"thread_id": f"{request.user_id}:{request.thread_id}"}}
        result = self.graph.invoke(input_state, config=config)
        state_view = result.get("state_view", {})
        validation = result.get("validation", {})
        if self.llm.last_error:
            state_view = {**state_view, "llm_fallback": True, "llm_error": self.llm.last_error}
            risk_flags = list(validation.get("risk_flags") or [])
            if "llm_fallback" not in risk_flags:
                risk_flags.append("llm_fallback")
            validation = {
                **validation,
                "passed": validation.get("passed", True),
                "notes": f"{validation.get('notes', '')} LLM fallback used.",
                "risk_flags": risk_flags,
            }
        return ChatResponse(
            user_id=request.user_id,
            thread_id=request.thread_id,
            sub_intent=result.get("sub_intent", "general_advice"),
            response=result.get("response", ""),
            next_action=result.get("next_action", "continue"),
            state=state_view,
            memory_updates=result.get("memory_updates", {}),
            validation=validation,
        )

    def _build_graph(self):
        workflow = StateGraph(CareerCoachState)
        workflow.add_node("load_context", self._load_context)
        workflow.add_node("sub_intent_router", self._route)
        workflow.add_node("question_generator", self._start_interview)
        workflow.add_node("answer_evaluator", self._handle_interview_answer)
        workflow.add_node("question_replacer", self._replace_interview_question)
        workflow.add_node("session_summarizer", self._summarize_interview)
        workflow.add_node("roadmap_generator", self._career_plan)
        workflow.add_node("advice_responder", self._general_advice)
        workflow.add_node("clarification_responder", self._clarification)
        workflow.add_node("self_check", self._self_check)
        workflow.add_node("persist_to_memory", self._persist_memory)

        workflow.add_edge(START, "load_context")
        workflow.add_edge("load_context", "sub_intent_router")
        workflow.add_conditional_edges(
            "sub_intent_router",
            self._branch,
            {
                "mock_interview_start": "question_generator",
                "interview_answer": "answer_evaluator",
                "interview_quit": "session_summarizer",
                "interview_new_question": "question_replacer",
                "career_plan": "roadmap_generator",
                "general_advice": "advice_responder",
                "clarification": "clarification_responder",
            },
        )
        workflow.add_edge("question_generator", "self_check")
        workflow.add_edge("answer_evaluator", "self_check")
        workflow.add_edge("question_replacer", "self_check")
        workflow.add_edge("session_summarizer", "self_check")
        workflow.add_edge("roadmap_generator", "self_check")
        workflow.add_edge("advice_responder", "self_check")
        workflow.add_edge("clarification_responder", "self_check")
        workflow.add_edge("self_check", "persist_to_memory")
        workflow.add_edge("persist_to_memory", END)
        return workflow.compile(checkpointer=self._checkpointer)

    def _load_context(self, state: CareerCoachState) -> CareerCoachState:
        user_id = state["user_id"]
        thread_id = state["thread_id"]
        profile = self.memory.upsert_user_profile(user_id, state.get("profile", {}))
        messages = self.memory.recent_messages(user_id, thread_id, limit=12)
        active_interview = self.memory.active_interview(user_id, thread_id)
        memories = self.memory.search_memory(user_id, state["message"], limit=6)
        return {
            "profile": profile,
            "messages": messages,
            "active_interview": active_interview,
            "memories": memories,
        }

    def _route(self, state: CareerCoachState) -> CareerCoachState:
        decision = self._classify_intent(state)
        return {
            "sub_intent": decision["sub_intent"],
            "intent_params": decision.get("params", {}),
            "router_decision": decision,
        }

    def _branch(self, state: CareerCoachState) -> str:
        sub_intent = state.get("sub_intent", "general_advice")
        if sub_intent in VALID_SUB_INTENTS:
            return sub_intent
        return "general_advice"

    def _classify_intent(self, state: CareerCoachState) -> dict[str, Any]:
        message = state["message"].strip().lower()
        mode = state.get("mode", "auto")
        active = state.get("active_interview")

        if active and self._wants_to_end_interview(message):
            return self._router_decision(
                "interview_quit",
                1.0,
                "Deterministic active-interview quit command.",
            )
        if active and self._asks_for_new_question(message):
            return self._router_decision(
                "interview_new_question",
                1.0,
                "Deterministic active-interview new-question command.",
            )

        if mode == "mock_interview":
            fallback_intent = "interview_answer" if active else "mock_interview_start"
            fallback_reason = "Mock interview mode selected."
        elif mode == "career_plan":
            fallback_intent = "career_plan"
            fallback_reason = "Career plan mode selected."
        elif mode == "general_advice":
            fallback_intent = "general_advice"
            fallback_reason = "General advice mode selected."
        elif active:
            fallback_intent = "interview_answer"
            fallback_reason = "Active interview exists, so ambiguous input is treated as an answer."
        else:
            fallback_intent = self._heuristic_intent(message)
            fallback_reason = "Heuristic fallback."
        fallback_confidence = self._heuristic_confidence(fallback_intent, message, active=bool(active), mode=mode)

        fallback = self._router_decision(
            fallback_intent,
            fallback_confidence,
            fallback_reason,
            params=self._heuristic_params(state["message"], state.get("profile", {})),
        )

        routed = self.llm.json(
            ROUTER_SYSTEM,
            self._router_context_prompt(state),
            fallback,
        )
        decision = self._sanitize_router_decision(routed, fallback, active=bool(active))
        if mode == "mock_interview" and not active:
            decision["sub_intent"] = "mock_interview_start"
            decision["reason"] = "Mock interview mode selected; using classifier params with forced branch."
        if mode == "career_plan" and not active:
            decision["sub_intent"] = "career_plan"
            decision["reason"] = "Career plan mode selected; using classifier params with forced branch."
        if mode == "general_advice" and not active:
            decision["sub_intent"] = "general_advice"
            decision["reason"] = "General advice mode selected."
        if self._needs_clarification(decision, active=bool(active), mode=mode):
            decision = {
                **decision,
                "sub_intent": "clarification",
                "reason": f"Low router confidence: {decision.get('reason', '')}",
            }
        log_event(
            LOGGER,
            "router_decision",
            user_id=state.get("user_id"),
            thread_id=state.get("thread_id"),
            sub_intent=decision.get("sub_intent"),
            confidence=decision.get("confidence"),
            params=decision.get("params", {}),
            reason=decision.get("reason"),
        )
        return decision

    @staticmethod
    def _router_decision(
        sub_intent: str,
        confidence: float,
        reason: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "sub_intent": sub_intent,
            "confidence": confidence,
            "reason": reason,
            "params": {
                "target_role": None,
                "level": None,
                "interview_type": None,
                "question_count": None,
                "plan_type": None,
                **(params or {}),
            },
        }

    def _sanitize_router_decision(
        self,
        decision: dict[str, Any],
        fallback: dict[str, Any],
        *,
        active: bool,
    ) -> dict[str, Any]:
        if not isinstance(decision, dict):
            return fallback
        sub_intent = str(decision.get("sub_intent") or fallback["sub_intent"])
        if sub_intent not in VALID_SUB_INTENTS:
            sub_intent = fallback["sub_intent"]
        if active and sub_intent == "mock_interview_start":
            sub_intent = "interview_answer"
        params = dict(fallback.get("params") or {})
        if isinstance(decision.get("params"), dict):
            for key in ("target_role", "level", "interview_type", "question_count", "plan_type"):
                value = decision["params"].get(key)
                if value not in (None, "", []):
                    params[key] = value
        try:
            confidence = float(decision.get("confidence", fallback.get("confidence", 0.5)))
        except (TypeError, ValueError):
            confidence = float(fallback.get("confidence", 0.5))
        return {
            "sub_intent": sub_intent,
            "confidence": max(0.0, min(1.0, confidence)),
            "reason": str(decision.get("reason") or fallback.get("reason") or ""),
            "params": params,
        }

    @staticmethod
    def _heuristic_intent(message: str) -> str:
        interview_terms = ("interview", "mock", "question", "answer me", "practice")
        plan_terms = (
            "roadmap",
            "career plan",
            "transition",
            "promotion",
            "milestone",
            "plan for",
            "become a",
            "become an",
        )
        if any(term in message for term in interview_terms):
            return "mock_interview_start"
        if any(term in message for term in plan_terms):
            return "career_plan"
        return "general_advice"

    @staticmethod
    def _heuristic_confidence(sub_intent: str, message: str, *, active: bool, mode: str) -> float:
        if active or mode != "auto":
            return 0.95
        if sub_intent in {"mock_interview_start", "career_plan"}:
            return 0.78
        if len(message.split()) >= 8:
            return 0.64
        return 0.45

    def _needs_clarification(self, decision: dict[str, Any], *, active: bool, mode: str) -> bool:
        if active or mode != "auto":
            return False
        try:
            confidence = float(decision.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        return confidence < self.settings.router_min_confidence

    @staticmethod
    def _heuristic_params(message: str, profile: dict[str, Any]) -> dict[str, Any]:
        params: dict[str, Any] = {}
        question_count = parse_question_count(message)
        if question_count is not None:
            params["question_count"] = question_count
        lowered = message.lower()
        for interview_type in ("technical", "behavioral", "mixed"):
            if interview_type in lowered:
                params["interview_type"] = interview_type
                break
        for level in ("student", "intern", "junior", "mid", "senior"):
            if level in lowered:
                params["level"] = level
                break
        target_role = profile.get("target_role")
        if target_role:
            params["target_role"] = target_role
        return params

    def _router_context_prompt(self, state: CareerCoachState) -> str:
        context = {
            "message": state.get("message"),
            "mode": state.get("mode"),
            "profile": state.get("profile", {}),
            "active_interview": self._compact_active_interview(state.get("active_interview")),
            "recent_messages": state.get("messages", [])[-6:],
            "retrieved_memories": state.get("memories", [])[:4],
        }
        return json.dumps(context, default=str)

    @staticmethod
    def _compact_active_interview(active: dict[str, Any] | None) -> dict[str, Any] | None:
        if not active:
            return None
        return {
            "target_role": active.get("target_role"),
            "interview_type": active.get("interview_type"),
            "level": active.get("level"),
            "question_number": active.get("question_number"),
            "max_questions": active.get("max_questions"),
            "current_question": active.get("current_question"),
        }

    def _start_interview(self, state: CareerCoachState) -> CareerCoachState:
        user_id = state["user_id"]
        thread_id = state["thread_id"]
        params = state.get("intent_params", {})
        setup_fallback = {
            "target_role": params.get("target_role") or state.get("profile", {}).get("target_role") or "target role",
            "level": params.get("level") or state.get("profile", {}).get("experience_level") or "junior",
            "interview_type": params.get("interview_type") or "mixed",
            "question_count": params.get("question_count") or state.get("max_interview_questions", 5),
            "focus_areas": ["role fundamentals", "communication", "problem solving"],
        }
        setup = self.llm.json(
            INTERVIEW_SETUP_SYSTEM,
            self._context_prompt(state),
            setup_fallback,
        )
        target_role = str(params.get("target_role") or setup.get("target_role") or setup_fallback["target_role"])
        level = str(params.get("level") or setup.get("level") or setup_fallback["level"])
        interview_type = str(params.get("interview_type") or setup.get("interview_type") or "mixed")
        max_questions = self._question_count(
            params.get("question_count"),
            setup.get("question_count"),
            state.get("max_interview_questions", 5),
        )

        question = self._generate_question(
            state,
            target_role=target_role,
            level=level,
            interview_type=interview_type,
            question_number=1,
        )

        self.memory.close_active_interviews(user_id, thread_id, status="replaced")
        session = self.memory.create_interview_session(
            user_id=user_id,
            thread_id=thread_id,
            target_role=target_role,
            interview_type=interview_type,
            level=level,
            current_question=question["question"],
            max_questions=max_questions,
        )

        response = (
            f"Let's start a {level} {interview_type} interview for {target_role}. "
            f"I'll ask {max_questions} question{'s' if max_questions != 1 else ''}.\n"
            'Type "quit" any time to end the interview and get a summary. '
            'Type "new question" if you want me to replace the current question.\n\n'
            f"Question 1: {question['question']}\n\n"
            "Answer when ready."
        )
        return {
            "active_interview": session,
            "response": response,
            "next_action": "await_user_answer",
            "state_view": {
                "interview_active": True,
                "question_number": 1,
                "max_questions": max_questions,
                "target_role": target_role,
                "interview_type": interview_type,
                "router_decision": state.get("router_decision", {}),
            },
        }

    def _replace_interview_question(self, state: CareerCoachState) -> CareerCoachState:
        active = state.get("active_interview")
        if not active:
            return {
                "response": "There is no active interview question to replace. Tell me the role and question count you want, and I will start a new mock interview.",
                "next_action": "continue",
                "state_view": {
                    "interview_active": False,
                    "router_decision": state.get("router_decision", {}),
                },
            }

        question_number = int(active.get("question_number") or 1)
        replacement = self._generate_question(
            state,
            target_role=str(active.get("target_role") or "target role"),
            level=str(active.get("level") or "junior"),
            interview_type=str(active.get("interview_type") or "mixed"),
            question_number=question_number,
            force_variant=True,
        )
        return {
            "response": f"Sure. I'll replace that one.\n\nQuestion {question_number}: {replacement['question']}",
            "next_action": "await_user_answer",
            "interview_session_update": {
                "session_id": active["id"],
                "current_question": replacement["question"],
                "question_number": question_number,
            },
            "state_view": {
                "interview_active": True,
                "question_number": question_number,
                "max_questions": active.get("max_questions"),
                "target_role": active.get("target_role"),
                "interview_type": active.get("interview_type"),
                "question_replaced": True,
                "router_decision": state.get("router_decision", {}),
            },
        }

    def _handle_interview_answer(self, state: CareerCoachState) -> CareerCoachState:
        active = state.get("active_interview")
        if not active:
            return {
                "response": "I do not have an active interview session yet. Tell me the role you want to practice for and I will start one.",
                "next_action": "continue",
                "state_view": {
                    "interview_active": False,
                    "router_decision": state.get("router_decision", {}),
                },
            }

        if self._asks_for_new_question(state["message"].lower()):
            question_number = int(active.get("question_number") or 1)
            replacement = self._generate_question(
                state,
                target_role=str(active.get("target_role") or "target role"),
                level=str(active.get("level") or "junior"),
                interview_type=str(active.get("interview_type") or "mixed"),
                question_number=question_number,
                force_variant=True,
            )
            return {
                "response": f"You're right. Let's switch it.\n\nQuestion {question_number}: {replacement['question']}",
                "next_action": "await_user_answer",
                "interview_session_update": {
                    "session_id": active["id"],
                    "current_question": replacement["question"],
                    "question_number": question_number,
                },
                "state_view": {
                    "interview_active": True,
                    "question_number": question_number,
                    "max_questions": active.get("max_questions"),
                    "target_role": active.get("target_role"),
                    "interview_type": active.get("interview_type"),
                    "question_replaced": True,
                    "router_decision": state.get("router_decision", {}),
                },
            }

        question_number = int(active.get("question_number") or 1)
        current_question = str(active.get("current_question") or "")
        max_questions = int(active.get("max_questions") or state.get("max_interview_questions", 5))
        feedback = self._evaluate_answer(state, current_question)

        turn_to_store = {
            "session_id": active["id"],
            "question_number": question_number,
            "question": current_question,
            "answer": state["message"],
            "feedback": feedback,
            "score": feedback.get("score"),
        }

        if question_number >= max_questions:
            summary = self._build_interview_summary(state, active, include_turn=turn_to_store)
            response = self._format_feedback(feedback)
            response += "\n\n" + self._format_interview_summary(summary)
            return {
                "response": response,
                "next_action": "interview_complete",
                "interview_turn_to_store": turn_to_store,
                "interview_session_update": {
                    "session_id": active["id"],
                    "status": "completed",
                    "summary": summary,
                    "current_question": "",
                },
                "state_view": {
                    "interview_active": False,
                    "question_number": question_number,
                    "max_questions": max_questions,
                    "overall_score": summary.get("overall_score"),
                    "router_decision": state.get("router_decision", {}),
                },
            }

        next_number = question_number + 1
        next_question = self._generate_question(
            state,
            target_role=str(active.get("target_role") or "target role"),
            level=str(active.get("level") or "junior"),
            interview_type=str(active.get("interview_type") or "mixed"),
            question_number=next_number,
            latest_feedback=feedback,
        )
        response = self._format_feedback(feedback)
        response += f"\n\nQuestion {next_number}: {next_question['question']}"
        return {
            "response": response,
            "next_action": "await_user_answer",
            "interview_turn_to_store": turn_to_store,
            "interview_session_update": {
                "session_id": active["id"],
                "current_question": next_question["question"],
                "question_number": next_number,
            },
            "state_view": {
                "interview_active": True,
                "question_number": next_number,
                "max_questions": max_questions,
                "target_role": active.get("target_role"),
                "interview_type": active.get("interview_type"),
                "router_decision": state.get("router_decision", {}),
            },
        }

    def _summarize_interview(self, state: CareerCoachState) -> CareerCoachState:
        active = state.get("active_interview")
        if not active:
            return {
                "response": "There is no active interview to end. I can start a new mock interview whenever you are ready.",
                "next_action": "continue",
                "state_view": {
                    "interview_active": False,
                    "router_decision": state.get("router_decision", {}),
                },
            }
        summary = self._build_interview_summary(state, active)
        return {
            "response": self._format_interview_summary(summary),
            "next_action": "interview_complete",
            "interview_session_update": {
                "session_id": active["id"],
                "status": "completed",
                "summary": summary,
                "current_question": "",
            },
            "state_view": {
                "interview_active": False,
                "overall_score": summary.get("overall_score"),
                "router_decision": state.get("router_decision", {}),
            },
        }

    def _career_plan(self, state: CareerCoachState) -> CareerCoachState:
        profile = state.get("profile", {})
        fallback = {
            "plan_type": "roadmap",
            "target_role": profile.get("target_role") or "target role",
            "summary": "Build role-ready skills, proof projects, and application habits in a staged roadmap.",
            "timeline": [
                {
                    "period": "Weeks 1-2",
                    "focus": "Clarify target role and baseline skills",
                    "actions": ["Review job descriptions", "List missing skills", "Pick one portfolio project"],
                    "deliverable": "Clear target role checklist",
                },
                {
                    "period": "Weeks 3-6",
                    "focus": "Build and prove core skills",
                    "actions": ["Study the highest priority skill", "Ship a small project", "Practice interview questions weekly"],
                    "deliverable": "Portfolio project with README",
                },
                {
                    "period": "Weeks 7-8",
                    "focus": "Apply and iterate",
                    "actions": ["Tailor resume", "Apply to selected roles", "Run mock interviews"],
                    "deliverable": "Application pipeline and feedback loop",
                },
            ],
            "skills_to_build": ["role fundamentals", "communication", "portfolio quality"],
            "portfolio_actions": ["Create one focused project", "Write a clear README"],
            "metrics": ["2 focused applications per week", "1 mock interview per week"],
            "risks": ["Trying to learn too many skills at once"],
        }
        plan = self.llm.json(
            CAREER_PLAN_SYSTEM,
            self._context_prompt(state),
            fallback,
        )
        response = self._format_career_plan(plan)
        return {
            "response": response,
            "next_action": "continue",
            "career_plan_to_store": plan,
            "state_view": {
                "plan_type": plan.get("plan_type", "roadmap"),
                "target_role": plan.get("target_role"),
                "router_decision": state.get("router_decision", {}),
            },
        }

    def _general_advice(self, state: CareerCoachState) -> CareerCoachState:
        fallback = (
            "Based on what you shared, the best next move is to make the goal more concrete, "
            "choose one target role, identify the top 3 missing skills, and turn those into a short weekly plan."
        )
        response = self.llm.text(
            ADVICE_SYSTEM,
            self._context_prompt(state),
            fallback,
        )
        return {
            "response": response,
            "next_action": "continue",
            "state_view": {
                "interview_active": bool(state.get("active_interview")),
                "retrieved_memories": len(state.get("memories", [])),
                "router_decision": state.get("router_decision", {}),
            },
        }

    def _clarification(self, state: CareerCoachState) -> CareerCoachState:
        return {
            "response": (
                "I want to route this correctly. Are you asking for a mock interview, "
                "a career plan, or general career advice? If it is a mock interview, "
                "include the target role and number of questions."
            ),
            "next_action": "await_clarification",
            "state_view": {
                "interview_active": bool(state.get("active_interview")),
                "router_decision": state.get("router_decision", {}),
            },
        }

    def _self_check(self, state: CareerCoachState) -> CareerCoachState:
        fallback = {
            "passed": bool(state.get("response")),
            "notes": "Generated response for the selected branch.",
            "risk_flags": [],
        }
        validation = self.llm.json(
            SELF_CHECK_SYSTEM,
            json.dumps(
                {
                    "sub_intent": state.get("sub_intent"),
                    "intent_params": state.get("intent_params", {}),
                    "router_decision": state.get("router_decision", {}),
                    "message": state.get("message"),
                    "response": state.get("response"),
                },
                default=str,
            ),
            fallback,
        )
        return {"validation": validation}

    def _persist_memory(self, state: CareerCoachState) -> CareerCoachState:
        user_id = state["user_id"]
        thread_id = state["thread_id"]
        sub_intent = state.get("sub_intent", "general_advice")
        response = state.get("response", "")
        persisted = {"messages": 0, "memory_items": 0}

        self.memory.add_message(
            user_id,
            thread_id,
            "user",
            state["message"],
            {
                "sub_intent": sub_intent,
                "router_decision": state.get("router_decision", {}),
            },
        )
        persisted["messages"] += 1

        if response:
            self.memory.add_message(
                user_id,
                thread_id,
                "assistant",
                response,
                {
                    "sub_intent": sub_intent,
                    "router_decision": state.get("router_decision", {}),
                    "validation": state.get("validation", {}),
                },
            )
            persisted["messages"] += 1

        turn = state.get("interview_turn_to_store")
        if turn:
            self.memory.add_interview_turn(
                session_id=int(turn["session_id"]),
                question_number=int(turn["question_number"]),
                question=str(turn["question"]),
                answer=str(turn["answer"]),
                feedback=dict(turn.get("feedback") or {}),
                score=turn.get("score"),
            )

        session_update = state.get("interview_session_update")
        if session_update:
            self.memory.update_interview_session(
                int(session_update["session_id"]),
                current_question=session_update.get("current_question"),
                question_number=session_update.get("question_number"),
                status=session_update.get("status"),
                summary=session_update.get("summary"),
            )

        career_plan = state.get("career_plan_to_store")
        if career_plan:
            self.memory.store_career_plan(
                user_id=user_id,
                thread_id=thread_id,
                plan_type=str(career_plan.get("plan_type", "roadmap")),
                target_role=career_plan.get("target_role"),
                content=career_plan,
            )

        memory_content = self._memory_content_for_state(state)
        if memory_content:
            self.memory.add_memory_item(
                user_id=user_id,
                thread_id=thread_id,
                kind=self._memory_kind(sub_intent),
                content=memory_content,
                metadata={"sub_intent": sub_intent},
            )
            persisted["memory_items"] += 1

        return {"memory_updates": {"persisted": True, **persisted}}

    def _generate_question(
        self,
        state: CareerCoachState,
        *,
        target_role: str,
        level: str,
        interview_type: str,
        question_number: int,
        latest_feedback: dict[str, Any] | None = None,
        force_variant: bool = False,
    ) -> dict[str, Any]:
        fallback = self._fallback_question(
            target_role=target_role,
            interview_type=interview_type,
            question_number=question_number,
            force_variant=force_variant,
            avoid_questions=self._avoid_questions(state),
        )
        previous_questions = self._avoid_questions(state)
        prompt = {
            "target_role": target_role,
            "level": level,
            "interview_type": interview_type,
            "question_number": question_number,
            "profile": state.get("profile", {}),
            "recent_messages": state.get("messages", []),
            "retrieved_memories": state.get("memories", []),
            "latest_feedback": latest_feedback,
            "previous_questions": previous_questions,
            "replace_current_question": force_variant,
        }
        question = self.llm.json(QUESTION_SYSTEM, json.dumps(prompt, default=str), fallback)
        if not question.get("question"):
            question["question"] = fallback["question"]
        if _normalize_question(str(question.get("question", ""))) in {
            _normalize_question(previous) for previous in previous_questions
        }:
            question = fallback
        return question

    def _evaluate_answer(self, state: CareerCoachState, question: str) -> dict[str, Any]:
        fallback = self._fallback_feedback(question, state["message"])
        prompt = {
            "question": question,
            "answer": state["message"],
            "profile": state.get("profile", {}),
            "active_interview": state.get("active_interview"),
            "retrieved_memories": state.get("memories", []),
        }
        feedback = self.llm.json(EVALUATION_SYSTEM, json.dumps(prompt, default=str), fallback)
        try:
            feedback["score"] = max(1, min(10, int(feedback.get("score", fallback["score"]))))
        except (TypeError, ValueError):
            feedback["score"] = fallback["score"]
        return feedback

    def _build_interview_summary(
        self,
        state: CareerCoachState,
        active: dict[str, Any],
        include_turn: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        turns = self.memory.interview_turns(int(active["id"]))
        if include_turn:
            turns = turns + [include_turn]
        fallback = {
            "overall_score": 6,
            "summary": "You completed the mock interview and showed a useful baseline.",
            "strengths": ["You engaged with the questions."],
            "weaknesses": ["Add more specific examples and clearer structure."],
            "practice_plan": ["Practice 3 STAR answers", "Review role fundamentals", "Repeat a mock interview"],
        }
        prompt = {
            "session": active,
            "turns": turns,
            "profile": state.get("profile", {}),
        }
        summary = self.llm.json(SUMMARY_SYSTEM, json.dumps(prompt, default=str), fallback)
        try:
            summary["overall_score"] = max(1, min(10, int(summary.get("overall_score", fallback["overall_score"]))))
        except (TypeError, ValueError):
            summary["overall_score"] = fallback["overall_score"]
        return summary

    def _context_prompt(self, state: CareerCoachState) -> str:
        context = {
            "message": state.get("message"),
            "mode": state.get("mode"),
            "profile": state.get("profile", {}),
            "active_interview": state.get("active_interview"),
            "recent_messages": state.get("messages", []),
            "retrieved_memories": state.get("memories", []),
        }
        return json.dumps(context, default=str)

    @staticmethod
    def _wants_to_end_interview(message: str) -> bool:
        compact = message.strip().lower()
        exact_terms = {"quit", "q", "exit", "end", "stop", "finish", "summary"}
        end_terms = (
            "end interview",
            "finish interview",
            "stop interview",
            "cancel interview",
            "summary now",
            "give me summary",
            "show summary",
        )
        return compact in exact_terms or any(term in compact for term in end_terms)

    @staticmethod
    def _asks_for_new_question(message: str) -> bool:
        compact = message.strip().lower()
        exact_terms = {"skip", "next", "new", "another"}
        terms = (
            "same question",
            "different question",
            "another question",
            "new question",
            "change question",
            "skip question",
            "repeat question",
        )
        return compact in exact_terms or any(term in compact for term in terms)

    @staticmethod
    def _question_count(*values: Any) -> int:
        for value in values:
            if value in (None, "", []):
                continue
            try:
                return max(1, min(15, int(value)))
            except (TypeError, ValueError):
                continue
        return 5

    @staticmethod
    def _fallback_question(
        *,
        target_role: str,
        interview_type: str,
        question_number: int,
        force_variant: bool = False,
        avoid_questions: list[str] | None = None,
    ) -> dict[str, Any]:
        role = target_role or "your target role"
        role_lower = role.lower()
        if "ai" in role_lower or "machine learning" in role_lower or "ml" in role_lower:
            questions = [
                (
                    "Project depth",
                    "Walk me through one AI project you built. What problem did it solve, what model or architecture did you choose, and why?",
                    ["problem framing", "model choice", "technical reasoning"],
                ),
                (
                    "Evaluation",
                    "How would you evaluate whether an AI model is good enough to use in production?",
                    ["metrics", "validation data", "business and safety tradeoffs"],
                ),
                (
                    "Data quality",
                    "Describe how you would handle noisy or insufficient training data for an AI system.",
                    ["data cleaning", "augmentation", "error analysis"],
                ),
                (
                    "Deployment",
                    "How would you deploy and monitor an AI feature after release?",
                    ["serving approach", "monitoring", "drift and rollback"],
                ),
                (
                    "Tradeoffs",
                    "Tell me about a technical tradeoff you made in an AI or backend project and how you decided.",
                    ["tradeoff awareness", "constraints", "outcome"],
                ),
                (
                    "Prompting and retrieval",
                    "How would you improve a RAG answer that is fluent but factually wrong?",
                    ["retrieval debugging", "grounding", "evaluation loop"],
                ),
                (
                    "Model behavior",
                    "What would you do if an AI model performs well offline but poorly with real users?",
                    ["offline-online gap", "monitoring", "iteration"],
                ),
                (
                    "Safety",
                    "How would you reduce hallucinations and unsafe outputs in an AI assistant?",
                    ["guardrails", "retrieval grounding", "human escalation"],
                ),
                (
                    "Experimentation",
                    "Describe how you would compare two model or prompt versions before shipping one.",
                    ["A/B testing", "metrics", "decision criteria"],
                ),
                (
                    "System design",
                    "Design a high-level architecture for an AI feature that serves many users concurrently.",
                    ["serving architecture", "latency", "scaling"],
                ),
            ]
        elif "backend" in role_lower:
            questions = [
                (
                    "Project depth",
                    f"Walk me through a backend project you built for a {role} role. What was the architecture and your main contribution?",
                    ["architecture", "ownership", "technical clarity"],
                ),
                (
                    "API design",
                    "How would you design an API endpoint for a high-traffic feature while keeping it reliable?",
                    ["API design", "performance", "failure handling"],
                ),
                (
                    "Database",
                    "Explain how you would investigate and improve a slow database query.",
                    ["indexes", "query plans", "measurement"],
                ),
                (
                    "Reliability",
                    "What would you log and monitor in a production backend service?",
                    ["observability", "alerts", "debugging"],
                ),
                (
                    "Testing",
                    "How do you decide what to unit test, integration test, and manually test in a backend project?",
                    ["test strategy", "risk", "practical coverage"],
                ),
                (
                    "Caching",
                    "When would you add caching to a backend service, and what could go wrong?",
                    ["cache invalidation", "latency", "consistency"],
                ),
                (
                    "Security",
                    "How would you protect an API endpoint that handles user-specific data?",
                    ["authentication", "authorization", "input validation"],
                ),
                (
                    "Background work",
                    "How would you design a backend task that takes too long to run inside a request?",
                    ["queues", "workers", "status tracking"],
                ),
                (
                    "Failure handling",
                    "What should happen if a downstream service times out during an API request?",
                    ["timeouts", "retries", "fallback behavior"],
                ),
                (
                    "Data modeling",
                    "How would you choose between normalizing and denormalizing data for a feature?",
                    ["query patterns", "consistency", "performance"],
                ),
            ]
        else:
            questions = [
                (
                    "Project depth",
                    f"Tell me about a project or experience that shows you are ready for a {role} role.",
                    ["clear example", "technical detail", "reflection"],
                ),
                (
                    "Problem solving",
                    "Describe a difficult technical problem you faced and how you solved it.",
                    ["structured thinking", "debugging", "outcome"],
                ),
                (
                    "Role fundamentals",
                    f"What are the most important skills for a {role}, and how have you practiced them?",
                    ["role awareness", "skill proof", "specific practice"],
                ),
                (
                    "Collaboration",
                    "Tell me about a time you had to explain a technical idea clearly to someone else.",
                    ["communication", "audience awareness", "clarity"],
                ),
                (
                    "Growth",
                    "What is one weakness you are actively improving, and what is your plan?",
                    ["self-awareness", "plan", "progress signal"],
                ),
                (
                    "Impact",
                    "Tell me about a time your work created measurable value.",
                    ["impact", "measurement", "ownership"],
                ),
                (
                    "Prioritization",
                    "How do you decide what to work on first when everything feels important?",
                    ["prioritization", "constraints", "decision quality"],
                ),
                (
                    "Conflict",
                    "Describe a time you disagreed with a technical or career decision. How did you handle it?",
                    ["communication", "judgment", "collaboration"],
                ),
                (
                    "Learning",
                    "What is the hardest skill you learned recently, and how did you know you were improving?",
                    ["learning process", "feedback", "evidence"],
                ),
                (
                    "Adaptability",
                    "Tell me about a time requirements changed late. What did you do?",
                    ["adaptability", "planning", "stakeholder communication"],
                ),
            ]

        avoid = {_normalize_question(question) for question in avoid_questions or []}
        offset = 1 if force_variant else 0
        index = (max(question_number, 1) - 1 + offset) % len(questions)
        focus_area, question, signals = questions[index]
        for step in range(len(questions)):
            candidate = questions[(index + step) % len(questions)]
            if _normalize_question(candidate[1]) not in avoid:
                focus_area, question, signals = candidate
                break
        if interview_type == "behavioral" and question_number > 1:
            behavioral_question = "Tell me about a time you had to learn something quickly for a project. What did you do?"
            if _normalize_question(behavioral_question) not in avoid:
                question = behavioral_question
                focus_area = "learning agility"
                signals = ["specific situation", "learning process", "result"]
        return {"question": question, "focus_area": focus_area, "expected_signals": signals}

    def _avoid_questions(self, state: CareerCoachState) -> list[str]:
        questions = []
        active = state.get("active_interview")
        if active and active.get("current_question"):
            questions.append(str(active["current_question"]))
            try:
                turns = self.memory.interview_turns(int(active["id"]))
                questions.extend(str(turn["question"]) for turn in turns if turn.get("question"))
            except Exception:
                pass
        return questions

    @staticmethod
    def _fallback_feedback(question: str, answer: str) -> dict[str, Any]:
        answer_lower = answer.lower()
        word_count = len(answer.split())
        technical_terms = (
            "langgraph",
            "python",
            "qdrant",
            "docker",
            "mlops",
            "rag",
            "model",
            "api",
            "database",
            "monitor",
            "evaluation",
            "metrics",
        )
        has_technical_detail = any(term in answer_lower for term in technical_terms)
        has_result = any(term in answer_lower for term in ("result", "improved", "reduced", "increased", "measured", "%", "users", "latency"))
        has_tradeoff = any(term in answer_lower for term in ("tradeoff", "because", "instead", "compared", "constraint"))

        score = 4
        strengths = []
        improvements = []
        if word_count >= 25:
            score += 1
            strengths.append("You gave enough context for the interviewer to understand the project.")
        else:
            improvements.append("Give more context: problem, your role, action, and result.")
        if has_technical_detail:
            score += 2
            strengths.append("You included relevant technical details.")
        else:
            improvements.append("Name the tools, architecture, model, or implementation choices you used.")
        if has_result:
            score += 1
            strengths.append("You connected the work to an outcome or measurement.")
        else:
            improvements.append("Add a measurable result or clear impact.")
        if has_tradeoff:
            score += 1
            strengths.append("You hinted at reasoning behind your choices.")
        else:
            improvements.append("Explain one tradeoff and why your choice fit the constraints.")

        score = max(1, min(10, score))
        if not strengths:
            strengths.append("You answered directly.")
        if not improvements:
            improvements.append("Tighten the story into a 60-90 second STAR-style answer.")

        return {
            "score": score,
            "strengths": strengths,
            "improvements": improvements,
            "better_answer": (
                "A stronger answer would state the problem, your exact contribution, the technical choices you made, "
                "one tradeoff, and the measurable result or lesson learned."
            ),
            "follow_up_focus": "specific technical depth and measurable impact",
        }

    @staticmethod
    def _format_feedback(feedback: dict[str, Any]) -> str:
        strengths = _bullet_lines(feedback.get("strengths", []))
        improvements = _bullet_lines(feedback.get("improvements", []))
        return (
            f"Score: {feedback.get('score', 'N/A')}/10\n\n"
            f"Strengths:\n{strengths}\n\n"
            f"Improve:\n{improvements}\n\n"
            f"Stronger version: {feedback.get('better_answer', '')}"
        )

    @staticmethod
    def _format_interview_summary(summary: dict[str, Any]) -> str:
        return (
            f"Interview summary\n\n"
            f"Overall score: {summary.get('overall_score', 'N/A')}/10\n\n"
            f"{summary.get('summary', '')}\n\n"
            f"Strengths:\n{_bullet_lines(summary.get('strengths', []))}\n\n"
            f"Weaknesses:\n{_bullet_lines(summary.get('weaknesses', []))}\n\n"
            f"Practice plan:\n{_bullet_lines(summary.get('practice_plan', []))}"
        )

    @staticmethod
    def _format_career_plan(plan: dict[str, Any]) -> str:
        timeline_lines = []
        for item in plan.get("timeline", []):
            if not isinstance(item, dict):
                continue
            actions = "; ".join(str(action) for action in item.get("actions", []))
            timeline_lines.append(
                f"- {item.get('period', 'Period')}: {item.get('focus', '')}. "
                f"Actions: {actions}. Deliverable: {item.get('deliverable', '')}"
            )
        timeline = "\n".join(timeline_lines) or "- Build a focused weekly plan."
        return (
            f"{plan.get('plan_type', 'Roadmap').title()} for {plan.get('target_role', 'your target role')}\n\n"
            f"{plan.get('summary', '')}\n\n"
            f"Timeline:\n{timeline}\n\n"
            f"Skills to build:\n{_bullet_lines(plan.get('skills_to_build', []))}\n\n"
            f"Portfolio actions:\n{_bullet_lines(plan.get('portfolio_actions', []))}\n\n"
            f"Metrics:\n{_bullet_lines(plan.get('metrics', []))}\n\n"
            f"Risks:\n{_bullet_lines(plan.get('risks', []))}"
        )

    @staticmethod
    def _memory_kind(sub_intent: str) -> str:
        if sub_intent in {
            "mock_interview_start",
            "interview_answer",
            "interview_quit",
            "interview_new_question",
        }:
            return "interview_feedback"
        if sub_intent == "career_plan":
            return "career_plan"
        return "career_advice"

    @staticmethod
    def _memory_content_for_state(state: CareerCoachState) -> str:
        sub_intent = state.get("sub_intent", "general_advice")
        if sub_intent == "career_plan" and state.get("career_plan_to_store"):
            return json.dumps(state["career_plan_to_store"], default=str)
        if sub_intent in {"interview_answer", "interview_quit"}:
            return state.get("response", "")
        if sub_intent == "general_advice":
            return f"User asked: {state.get('message')}\nAdvice: {state.get('response')}"
        return ""


def _bullet_lines(values: Any) -> str:
    if not values:
        return "- None noted"
    if isinstance(values, str):
        return f"- {values}"
    return "\n".join(f"- {value}" for value in values)


def _normalize_question(question: str) -> str:
    return " ".join(question.lower().strip().split())


NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}


def parse_question_count(message: str) -> int | None:
    digit_match = re.search(r"\b(\d{1,2})\s*(?:questions?|qs?)\b", message, re.IGNORECASE)
    if digit_match:
        return int(digit_match.group(1))

    normalized = message.lower().replace("-", " ")
    tokens = re.findall(r"[a-z]+", normalized)
    for index, token in enumerate(tokens):
        if token not in {"question", "questions", "q", "qs"}:
            continue
        prefix = tokens[max(0, index - 3) : index]
        value = _number_from_words(prefix)
        if value is not None:
            return value
    return None


def _number_from_words(words: list[str]) -> int | None:
    if not words:
        return None
    for size in range(min(3, len(words)), 0, -1):
        candidate = words[-size:]
        value = 0
        matched = False
        for word in candidate:
            if word == "and":
                continue
            if word not in NUMBER_WORDS:
                matched = False
                break
            value += NUMBER_WORDS[word]
            matched = True
        if matched:
            return value
    return None


# ---------------------------------------------------------------------------
# Public factory — used by the Supervisor (Plan 2) and smoke tests.
# Does NOT touch PostgresSaver at import time.
# ---------------------------------------------------------------------------

#: Module-level reference kept as ``None`` until the Supervisor wires it up.
coaching_graph = None


def build_coaching_graph(checkpointer=None):
    """Build and compile the coaching graph with an optional shared checkpointer.

    Args:
        checkpointer: A LangGraph checkpointer instance (e.g. shared
            ``PostgresSaver``).  Pass ``None`` to compile without persistence
            (useful for smoke tests and unit tests that have no live DB).

    Returns:
        A compiled ``StateGraph`` (``CompiledGraph``).
    """
    from app.agents.coaching.embeddings import build_embedding_service
    from app.agents.coaching.memory import PostgresMemory
    from app.agents.coaching.settings import get_settings

    settings = get_settings()
    embeddings = build_embedding_service(settings)
    memory = PostgresMemory(settings, embeddings)
    agent = CareerCoachingAgent(settings=settings, memory=memory, checkpointer=checkpointer)
    return agent.graph
