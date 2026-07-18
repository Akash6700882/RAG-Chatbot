"""Centralized prompt templates. Kept in one place so hallucination-reduction
wording can be reviewed/tuned without hunting through node implementations."""

from langchain_core.prompts import ChatPromptTemplate

QUERY_REWRITE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You rewrite a user's latest question into a standalone search query, using the "
            "conversation history to resolve pronouns and implicit references. "
            "Return ONLY the rewritten query text — no quotes, no explanation.",
        ),
        (
            "human",
            "Conversation history:\n{chat_history}\n\nLatest question: {question}\n\nStandalone query:",
        ),
    ]
)

CONTEXT_VALIDATION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You judge whether the CONTEXT below contains enough information to accurately answer the "
            "QUESTION. Respond with exactly one word: SUFFICIENT or INSUFFICIENT.",
        ),
        ("human", "Question: {question}\n\nContext:\n{context}\n\nJudgment:"),
    ]
)

ANSWER_GENERATION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an enterprise knowledge-base assistant. Answer the user's question using ONLY the "
            "information in the CONTEXT below. Do not use outside knowledge, do not speculate, and do not "
            "invent facts, numbers, or policies that are not explicitly present. If the context does not "
            "fully answer the question, say so explicitly rather than guessing. Cite the source filename "
            "in parentheses after any claim you make.{regeneration_notice}",
        ),
        ("human", "Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"),
    ]
)

HALLUCINATION_CHECK_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a strict fact-checker. Determine whether the ANSWER is fully supported by the "
            "CONTEXT, with no invented facts, numbers, or claims beyond what the context states. "
            "Respond with exactly one line: 'GROUNDED' if fully supported, or "
            "'UNGROUNDED: <short reason>' if not.",
        ),
        ("human", "Context:\n{context}\n\nAnswer:\n{answer}\n\nVerdict:"),
    ]
)

REGENERATION_NOTICE = (
    "\n\nNOTE: Your previous answer was flagged as not fully supported by the context. "
    "Regenerate a stricter answer using only facts explicitly stated in the context below."
)

FALLBACK_ANSWER = (
    "I don't have enough information in the ingested documents to answer that confidently. "
    "Try rephrasing your question or uploading a document that covers this topic."
)
