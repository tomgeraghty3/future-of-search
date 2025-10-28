"""
LLM-Driven Guardrails Tool (simple & readable)

This tool asks an LLM (via AWS Bedrock) to evaluate a response against
a set of "good practice" guardrails plus any user-provided guardrails.
It must end with one of:
  - "Accepted"
  - "Accepted with changes (<bulleted list of changes>)"
  - "Rejected"
"""

import json
import logging
from typing import Any, Dict, List, Optional

import boto3
from strands.tools import tool
from strands import ToolContext


logger = logging.getLogger(__name__)

# --- System prompt with concise, good-practice guardrails --- #
SYSTEM_GUARDRAILS = """
You are a rigorous content reviewer. Evaluate the provided CONTENT against these guardrails.

Core Good-Practice Guardrails:
1) Safety & Legality: No self-harm instructions, illicit activity guidance, or unsafe practices.
2) Harassment/Hate: No hateful, harassing, or dehumanizing content toward protected classes or individuals.
3) Sexual Content & Minors: No sexual content involving minors; avoid explicit content unless clearly educational and necessary.
4) Violence: No glorification of violence or instructions for harm.
5) Privacy & PII: Do not reveal private or identifying information about real people without consent.
6) IP & Attribution: No clear plagiarism; respect copyrights; cite or paraphrase responsibly.
7) Medical/Legal/Financial Care: Avoid definitive professional advice; add disclaimers and encourage consulting qualified professionals.
8) Factuality: Avoid fabrications; clearly label uncertainty; provide sources if cited.
9) Security: No malware, exploits, or steps for hacking, bypassing controls, or data exfiltration.
10) Data Sensitivity: Do not output secrets, credentials, or private keys.
11) Bias & Fairness: Avoid harmful stereotypes; use neutral, inclusive language.
12) Brand/Policy Alignment: Flag content that contradicts stated platform or org policies.
13) Clarity & Tone: Aim for clear, coherent, and helpful communication; avoid gratuitous profanity.
14) Scope & Relevance: Ensure content addresses the user’s request without unnecessary, risky detours.

If USER_GUARDRAILS are provided, apply them in addition to the above; if there is a direct conflict, USER_GUARDRAILS take priority unless they permit clear harm or illegality.

OUTPUT FORMAT (strict JSON):
{
  "decision": "accept" | "accept_with_changes" | "reject",
  "changes": [ "short, actionable edits if any" ],
  "rationale": "one short paragraph explaining the decision"
}

After you return JSON, the caller will convert it to a final human result string.
Return only JSON. Do not include extra text.
""".strip()


def _build_user_guardrails_block(user_guardrails: Optional[List[str]]) -> str:
    if not user_guardrails:
        return "USER_GUARDRAILS: (none provided)"
    lines = "\n".join(f"- {g.strip()}" for g in user_guardrails if g and g.strip())
    return f"USER_GUARDRAILS:\n{lines}"


@tool(context=True)
async def guardrails_tool(
    response_content: str,
    tool_context: ToolContext,
    user_guardrails: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Evaluate 'response_content' using an LLM with a system prompt of guardrails.
    Returns a dict with:
      - result: one of "Accepted", "Accepted with changes (...)", "Rejected"
      - changes: list of changes if any
      - rationale: brief reason
      - raw_json: original parsed JSON from the model
    """
    try:
      # --- Config (simple, overridable via invocation_state) --- #
      inv = getattr(tool_context, "invocation_state", {}) or {}
      region = inv.get("AWS_REGION", "us-east-1")
      model_id = inv.get("model_id", "anthropic.claude-3-sonnet-20240229-v1:0")

      # --- Compose the single user message --- #
      user_block = _build_user_guardrails_block(user_guardrails)
      user_message = f"""
        Evaluate the following CONTENT against the guardrails.
        
        {user_block}
        
        CONTENT:
        \"\"\"{response_content}\"\"\"
        """.strip()

      # --- Call Bedrock (Converse API) --- #
      bedrock = boto3.client("bedrock-runtime", region_name=region)

      logger.info(f"Calling LLM with model: {model_id}")
      resp = bedrock.converse(
          modelId=model_id,
          system=[{"text": SYSTEM_GUARDRAILS}],
          messages=[{"role": "user", "content": [{"text": user_message}]}],
      )

      text_out = resp["output"]["message"]["content"][0]["text"]

      # --- Parse the JSON response from the model --- #
      try:
          payload = json.loads(text_out)
      except json.JSONDecodeError as e:
          # If the model returned non-JSON, fail safely with a rejection
          logger.error(f"Unable to decode the JSON payload. Error: {e}")
          payload = {
              "decision": "reject",
              "changes": [],
              "rationale": "Model did not return valid JSON as required by the guardrails prompt.",
          }

      decision = (payload.get("decision") or "").strip().lower()
      changes = payload.get("changes") or []
      rationale = payload.get("rationale") or ""

      # --- Normalize to final human-readable result --- #
      if decision == "accept":
          result = "Accepted"
      elif decision == "accept_with_changes":
          if changes:
              bullet_list = "\n- " + "\n- ".join(changes)
              result = f"Accepted with changes ({bullet_list})"
          else:
              result = "Accepted with changes (no specific changes provided)"
      else:
          result = "Rejected"

      return_result = {
          "result": result,
          "changes": changes,
          "rationale": rationale,
          "raw_json": payload,
      }

      logger.info(f"\nIN:\"{response_content}\"\nOUT:\n\"{return_result}\"")

      return return_result
    except Exception as e:
      logger.error(f"The guardrails tool failed. Error: {e}")
