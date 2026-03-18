import os
from openai import AsyncOpenAI  # ПРОМЯНА: Използваме AsyncOpenAI
from dotenv import load_dotenv
import json

load_dotenv()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ПРОМЯНА: Добавяме 'async' пред функцията
async def generate_exercise_ai(module: str, level: str):
    # Това е системната инструкция (Prompt), която учи AI как да се държи
    prompt = f"""
    You are an expert English teacher following the Bulgarian national curriculum.
    Create a {module} exercise for grade level {level} (CEFR).
    
    The instructions and explanations must be in Bulgarian.
    If the module is "Speaking", the exercise should consist of sentences or 
    short paragraphs that the student must read aloud, or fill-in-the-blank sentences they must say completely.
    If the module is NOT "Speaking", it should be a standard text-based exercise.

    You MUST return strictly a JSON with this exact format:
    {{
        "title": "Exercise Title",
        "instructions": "Clear instructions for the student",
        "is_speaking": true,  <-- НАПРАВИ ГО true АКО Е SPEAKING. За Grammar, Vocabulary и Reading ЗАДЪЛЖИТЕЛНО трябва да е false!
        "correct_answers": ["Answer 1", "Answer 2"]
    }}
    """

    # ПРОМЯНА: Добавяме 'await' пред извикването на API-то
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": prompt}],
        response_format={ "type": "json_object" }
    )
    
    return response.choices[0].message.content

async def evaluate_audio_exercise(audio_file_path: str, expected_topic: str):
    """
    1. Превръща аудио файл в текст чрез Whisper.
    2. Оценява текста чрез GPT-4o.
    """
    # Стъпка 1: Превръщане на глас в текст (Speech-to-Text)
    with open(audio_file_path, "rb") as audio_file:
        transcript_response = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    transcribed_text = transcript_response.text

    # Стъпка 2: AI Оценка (Prompt Engineering)
    prompt = f"""
    You are an expert English evaluator. The student was asked to speak about "{expected_topic}".
    Here is what they said (transcribed from audio): "{transcribed_text}"
    
    Evaluate their response and return STRICTLY a JSON object with the following keys:
    - 'grammar_score': integer from 1 to 10
    - 'fluency_score': integer from 1 to 10
    - 'strengths': string (short positive feedback)
    - 'weaknesses': string (areas for improvement)
    - 'explanation': string (detailed explanation in Bulgarian language of the scores)

    

    You MUST return ONLY a JSON with this exact format:
    {{
        "grammar_score": 80,
        "fluency_score": 70,
        "strengths": "...",
        "weaknesses": "...",
        "explanation": "...",
        "transcribed_text": "...",
        "pronunciation_tips": "Тук напиши кои думи са сбъркани и как трябва да се произнесат (напр. word -> /wɜːrd/)" <-- НОВОТО ПОЛЕ
    }}
    """

    evaluation_response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": prompt}],
        response_format={ "type": "json_object" }
    )
    
    # Разопаковаме JSON отговора и добавяме транскрибирания текст, за да го върнем на телефона
    result_data = json.loads(evaluation_response.choices[0].message.content)
    result_data["transcribed_text"] = transcribed_text 
    
    return result_data