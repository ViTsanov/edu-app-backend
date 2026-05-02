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

async def evaluate_audio_exercise(audio_file_path: str, instructions: str, content: list, correct_answers: list):
    # Стъпка 1: Превръщане на глас в текст с Whisper
    with open(audio_file_path, "rb") as audio_file:
        transcript_response = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    transcribed_text = transcript_response.text

    # Стъпка 2: AI Оценка с ПЪЛЕН КОНТЕКСТ
    prompt = f"""
    You are an expert English language teacher evaluating a student's spoken audio (transcribed to text).
    
    Here is the exact exercise the student is trying to solve:
    - Instructions given to student: "{instructions}"
    - Exercise content (sentences/questions): {content}
    - Expected/Correct answers (if applicable): {correct_answers}

    The speech-to-text system transcribed the student's audio as:
    "{transcribed_text}"

    CRITICAL EVALUATION RULES:
    1. Read the "Instructions" carefully to understand the task.
       - If it's a READING task, focus strictly on pronunciation accuracy.
       - If it's a FILL-IN task, check if the word is correct first, THEN evaluate pronunciation.
    2. Use a scale from 0 to 100 for scores.

    Return STRICTLY a JSON object with this exact format:
    {{
        "grammar_score": integer (0 to 100, based on accuracy of the task),
        "fluency_score": integer (0 to 100, based on smooth flow),
        "strengths": "Кратка похвала на български",
        "weaknesses": "Кратка зона за подобрение на български",
        "explanation": "Подробно обяснение на български защо оценката е такава",
        "pronunciation_tips": "Кои думи са сбъркани и как трябва да се произнесат (напр. word -> /wɜːrd/)"
    }}
    """

    evaluation_response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": prompt}],
        response_format={ "type": "json_object" }
    )
    
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

# ============================================================
# ADD THIS FUNCTION TO YOUR EXISTING ai_service.py
# ============================================================

async def analyze_test_results(evaluations: list, avg_score: int) -> str:
    """
    Takes a list of per-exercise evaluations from a full test and
    returns a comprehensive improvement analysis in Bulgarian.
    Called after a student submits a timed test.
    """
    summary_text = "\n".join([
        f"Упражнение {i+1}: Граматика={e.get('grammar_score', 0)}/100. "
        f"Обяснение: {e.get('explanation', 'Няма')}"
        for i, e in enumerate(evaluations)
    ])

    prompt = f"""
You are an expert English teacher analysing a Bulgarian student's full test results.

The student scored an average of {avg_score}/100 across {len(evaluations)} exercises.

Per-exercise breakdown:
{summary_text}

Your task is to write a personalised improvement analysis ENTIRELY IN BULGARIAN.
The analysis must:
1. Start with a brief overall assessment (1-2 sentences)
2. Identify the TOP 2-3 specific weak areas (e.g. verb tenses, articles, pronunciation)
3. Give 2-3 CONCRETE, actionable tips to improve each weak area
4. End with a motivating sentence

Keep the total response under 300 words. Write in a friendly, encouraging teacher tone.
Do NOT use JSON — just plain Bulgarian text.
"""

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": prompt}],
        max_tokens=600
    )
    return response.choices[0].message.content


async def generate_exercise_improvement(
    questions: list,
    expected: list,
    user_answers: list,
    grammar_score: int
) -> str:
    """
    Called after each regular exercise submission.
    Returns a short, personalised improvement tip in Bulgarian.
    """
    prompt = f"""
You are a friendly English teacher. A Bulgarian student just completed an exercise.

Score: {grammar_score}/100
Questions: {questions}
Expected answers: {expected}
Student's answers: {user_answers}

Write a SHORT improvement tip (max 80 words) IN BULGARIAN that:
1. Names the specific grammar/vocabulary mistake (if any)
2. Gives one concrete rule or trick to remember
3. Encourages the student

Plain text only, no JSON, no markdown.
"""
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": prompt}],
        max_tokens=200
    )
    return response.choices[0].message.content