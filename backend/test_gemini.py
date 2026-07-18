import os
import sys

os.environ["GEMINI_API_KEY"] = os.environ.get("GEMINI_API_KEY", os.environ.get("GOOGLE_API_KEY", ""))

try:
    from litellm import completion
    response = completion(
        model="gemini/gemini-1.5-flash",
        messages=[{"role": "user", "content": "Hello"}]
    )
    print("SUCCESS gemini-1.5-flash:", response.choices[0].message.content)
except Exception as e:
    print("ERROR gemini-1.5-flash:", e)

try:
    from litellm import completion
    response = completion(
        model="gemini/gemini-1.5-flash-latest",
        messages=[{"role": "user", "content": "Hello"}]
    )
    print("SUCCESS gemini-1.5-flash-latest:", response.choices[0].message.content)
except Exception as e:
    print("ERROR gemini-1.5-flash-latest:", e)

try:
    from litellm import completion
    response = completion(
        model="gemini/gemini-1.5-pro",
        messages=[{"role": "user", "content": "Hello"}]
    )
    print("SUCCESS gemini-1.5-pro:", response.choices[0].message.content)
except Exception as e:
    print("ERROR gemini-1.5-pro:", e)
