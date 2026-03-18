import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

model = genai.GenerativeModel("gemini-3-flash-preview")

async def generate_chat_response(prompt):
  response = (await model.generate_content_async(prompt)).text
  print(response)
  return response

def generate_chat_response_stream(prompt):
  response = model.generate_content(prompt, stream=True)
  for chunk in response:
    if chunk.text:
      yield chunk.text

async def get_customer_sentiment(prompt):
  response = (await model.generate_content_async(prompt)).text
  print(response)
  return response

if __name__ == "__main__":
  def test():
    response = model.generate_content("Explain how AI works in a few words").text
    return response
  print(test())