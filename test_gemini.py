import os
from google import genai

# 指定使用 Vertex AI 模式
client = genai.Client(
    vertexai=True,
    project=os.environ.get("GOOGLE_CLOUD_PROJECT", "YOUR_PROJECT_ID"),
    location="us-central1"
)

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="請回應：'Environment setup successful!'",
)

print(response.text)
