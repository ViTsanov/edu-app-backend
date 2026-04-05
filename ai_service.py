import os
from openai import AsyncOpenAI  # ПРОМЯНА: Използваме AsyncOpenAI
from dotenv import load_dotenv
import json

load_dotenv()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ПРОМЯНА: Добавяме 'async' пред функцията
async def generate_exercise_ai(module: str, level: str):
    # Това е системната инструкция (Prompt), която учи AI как да се държи
    # Това е системната инструкция (Prompt), която учи AI как да се държи
    # Това е системната инструкция (Prompt), която учи AI как да се държи
    prompt = f"""
    You are an expert English teacher. Your ONLY task is to generate a {module} exercise for CEFR level {level}.

    CRITICAL LANGUAGE RULES:
    1. The "title" and "instructions" fields MUST be written in Bulgarian (Български).
    2. The "content" (questions/sentences) and "correct_answers" fields MUST be written ENTIRELY IN ENGLISH.

    CRITICAL FORMAT RULES:
    1. You MUST respond with ONLY a valid raw JSON object. Do not use Markdown (like ```json), and do not add any text before or after the JSON.
    2. If the module is "Speaking", the "is_speaking" field MUST be true. The "content" array should contain English sentences for the student to read aloud.
    3. If the module is NOT "Speaking" (e.g. Grammar, Reading), the "is_speaking" field MUST be false. The "content" array should contain standard English text questions.
    4. ALL keys in the JSON must exist exactly as shown below. 

    JSON TEMPLATE:
    {{
        "title": "Кратко заглавие на български език",
        "instructions": "Ясни инструкции за ученика на български език",
        "is_speaking": false,
        "content": [
            "This is the first English question or sentence.",
            "This is the second English question or sentence.",
            "This is the third English question or sentence."
        ],
        "correct_answers": [
            "English correct answer 1",
            "English correct answer 2",
            "English correct answer 3"
        ]
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

async def evaluate_text_exercise(questions: list, expected: list, user_answers: list):
    prompt = f"""
    You are an expert English teacher evaluating a student's text exercise.
    Questions: {questions}
    Expected Answers: {expected}
    Student's Answers: {user_answers}

    Evaluate the student's answers. Be forgiving of minor typos or capitalization, but strict on grammar.
    Return STRICTLY a JSON object with this exact format:
    {{
        "grammar_score": integer (0 to 100 based on correct answers),
        "fluency_score": 0,
        "strengths": "Кратка похвала на български",
        "weaknesses": "Кратка зона за подобрение на български",
        "explanation": "Подробно обяснение на български защо конкретни отговори са грешни (напр. 'На въпрос 1 трябва да е X, защото...')",
        "is_correct_array": [true, false, true]  // Масив от true/false, който съответства на броя въпроси! True ако отговорът е верен, False ако е грешен.
    }}
    """
    
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": prompt}],
        response_format={ "type": "json_object" }
    )
    
    return json.loads(response.choices[0].message.content)