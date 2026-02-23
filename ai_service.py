import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_exercise_ai(module: str, level: str):
    # Това е системната инструкция (Prompt), която учи AI как да се държи
    prompt = f"""
    You are an expert English teacher following the Bulgarian national curriculum.
    Create a {module} exercise for grade level {level} (CEFR).
    The instructions and explanations must be in Bulgarian.
    Format the output as a clean JSON object with:
    'title', 'instructions', 'content' (the actual questions), and 'correct_answers'.
    """

    response = client.chat.completions.create(
        model="gpt-4o", # Или gpt-4o ако имаш достъп
        messages=[{"role": "system", "content": prompt}],
        response_format={ "type": "json_object" }
    )
    
    return response.choices[0].message.content