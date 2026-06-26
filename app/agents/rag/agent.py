"""RAG knowledge agent node."""

from __future__ import annotations

from app.llm.provider import get_llm
from app.orchestrator.state import CopilotState
from app.rag.retriever import retrieve


def rag_node(state: CopilotState) -> dict:
    """
    RAG node that retrieves relevant documents and generates a grounded answer with citations.

    Args:
        state: The copilot state containing user_id and user_message.

    Returns:
        Dictionary with keys:
        - rag: dict with "answer" (str) and "citations" (list[dict])
        - evidence: list of retrieved chunks from RAG store
    """
    user_id = state["user_id"]
    user_message = state["user_message"]

    # Step 1: Retrieve relevant documents
    evidence = retrieve(user_id=user_id, query=user_message)

    # Step 2: Prepare context from retrieved evidence
    context = "\n\n".join([f"[{e['doc_id']}] {e['text']}" for e in evidence])

    # Step 3: Build prompt for grounded answer
    grounded_prompt = f"""You are a helpful assistant answering questions based on provided documents.

User Question: {user_message}

Retrieved Documents:
{context}

Task: Provide a clear, concise answer that cites the relevant document IDs.
If the answer cannot be found in the documents, explicitly state "Not found in documents."
Include citations in the format [doc_id] after each relevant claim.

Answer:"""

    # Step 4: Call LLM to generate grounded answer
    llm = get_llm(task="reason")
    response = llm.invoke(grounded_prompt)
    answer = response.content

    # Step 5: Extract citations from evidence (simple approach: just return all evidence as citations)
    citations = [
        {
            "doc_id": e["doc_id"],
            "text": e["text"],
            "score": e["score"],
        }
        for e in evidence
    ]

    return {
        "rag": {
            "answer": answer,
            "citations": citations,
        },
        "evidence": evidence,
    }
