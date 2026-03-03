import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

model = genai.GenerativeModel("gemini-3-flash-preview")

def generate_chat_response(prompt):
  response = model.generate_content(prompt).text
  print(response)
  return response

def get_customer_sentiment(prompt):
  response = model.generate_content(prompt).text
  print(response)
  return response

if __name__ == "__main__":
  def test():
    response = model.generate_content("Explain how AI works in a few words").text
    return response
  print(test())