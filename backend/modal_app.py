"""Modal deployment: Muse Spark Open quote agent.

Exposes a POST webhook that accepts the voice transcript + SAM 3.1
segmentation and returns a QuoteEstimate-shaped JSON object.

Prerequisites (one time):
    pip install modal
    modal setup                 # authenticate / claim partner credits

Deploy:
    cd backend && modal deploy modal_app.py

The printed web endpoint URL becomes SPARK_OPEN_ENDPOINT for the FastAPI
service. Set MODEL_ID below to the exact open-weights repo from the
hackathon model instructions before deploying.
"""

import json

import modal

MODEL_ID = "FILL-ME-muse-spark-open-weights"  # TODO: exact repo from Meta docs

app = modal.App("panelScan-spark-open")

vllm_image = modal.Image.debian_slim(python_version="3.10").pip_install(
    "vllm>=0.6", "fastapi[standard]"
)


@app.function(
    image=vllm_image,
    gpu="A10G",
    timeout=600,
    secrets=[],  # e.g. modal.Secret.from_name("huggingface") if weights are gated
)
@modal.fastapi_endpoint(method="POST")
def quote_webhook(payload: dict) -> dict:
    """POST {system, transcript, segmentation, schema} -> QuoteEstimate JSON."""
    from vllm import LLM, SamplingParams

    system = payload.get("system", "")
    transcript = payload.get("transcript", "")
    segmentation = payload.get("segmentation", {})
    schema = payload.get("schema", {})

    prompt = (
        f"{system}\n\nTRANSCRIPT:\n{transcript}\n\n"
        f"SEGMENTATION:\n{json.dumps(segmentation)}\n\nJSON:"
    )
    llm = LLM(model=MODEL_ID)
    params = SamplingParams(temperature=0.2, max_tokens=1024, guided_json=schema)
    text = llm.generate([prompt], params)[0].outputs[0].text
    return json.loads(text)
