import os
from dotenv import load_dotenv
from langfuse import Langfuse

load_dotenv()

public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
secret_key = os.getenv("LANGFUSE_SECRET_KEY")
host = os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")

langfuse = Langfuse(public_key=public_key, secret_key=secret_key, host=host)

v1_text = """Feature={{feature}}
Docs={{docs}}
Question={{message}}"""

v2_text = """Answer in no more than three concise bullet points.
Feature={{feature}}
Docs={{docs}}
Question={{message}}"""

print("Creating prompt v1 (labels: baseline, production)...")
p1 = langfuse.create_prompt(
    name="day13-chat",
    type="text",
    prompt=v1_text,
    labels=["baseline", "production"],
)
print(f"Created v1 successfully (version: {p1.version})")

print("Creating prompt v2 (labels: candidate)...")
p2 = langfuse.create_prompt(
    name="day13-chat",
    type="text",
    prompt=v2_text,
    labels=["candidate"],
)
print(f"Created v2 successfully (version: {p2.version})")
print("Done! Refresh Langfuse Prompts page to see both versions.")
