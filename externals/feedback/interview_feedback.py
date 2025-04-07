from django.conf import settings
import google.generativeai as genai
import json

# import assemblyai as aai

# Configure APIs
# aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")
genai.configure(api_key=settings.GOOGLE_API_KEY)


# def transcribe_video(video_path):
#     """
#     Transcribe video directly using AssemblyAI's video-to-text API.
#     """
#     try:
#         transcriber = aai.Transcriber()
#         transcript = transcriber.transcribe(video_path)
#         return transcript
#     except Exception as e:
#         st.error(f"Error during transcription: {e}")
#         return None


def analyze_transcription_and_generate_feedback(transcription):
    """
    Analyze the transcription and generate feedback for all questions in a single API request.
    Group questions by skills.
    """
    prompt = f"""
    Below is a transcription of an interview. Perform the following tasks:
    1. Extract the interviewer's questions and the candidate's answers.
    2. Categorize each question with generalize skill (e.g., Python, AI, JavaScript, ML etc.).
    3. For each skill pair generate feedback including:
       - A summary of the candidate's performance.
       - A score (0-100 scale) for the skill.
    4. Include the start and end timestamps for each skill section in seconds.
    5. Group questions with the same skill into a single block.
    6. Add overall candidate strengths and point of imporvements.

    Transcription:
    {transcription}

    Return the data in STRICT JSON format as follows:
    {{
        "skill_based_performance": {{
            "skill_name eg.(generalize skills such as python, Javascript, etc.)": {{
                "summary": "Overall performance summary for current skill",
                "questions": [
                    {{
                        "que": "Interviewer's question?",
                        "ans": "Candidate's answer",
                        "start_time": "Start time of the question in seconds (relative to video start)",
                        "end_time": "End time of the answer in seconds (relative to video start)"
                    }}
                    ...
                ]
            }}
            ...
        }},
        "skill_evaluation": {{
            "Communication": "Communication score according to interview performance, can be poor, average, good or excellent",
            "Attitude": "Attitude score according to interview performance, can be poor, average, good or excellent"
        }},
        "strength": "overall candidate strengths",
        "improvement_points": "overall candidate improvement points",
    }}

    IMPORTANT:
    - Return ONLY valid JSON. Do not include any additional text or explanations.
    - Ensure the JSON is properly formatted and can be parsed by a JSON parser.
    - Ensure all timestamps are relative to the start of the video.
    - Try to summarize the feedback for each question-answer pair, it don't have to be same word to word as in the transcript but must conatain the main points not too short or too long and write question in understandable way even though some has not attended the interview they must able to understand.
    """

    try:
        model = genai.GenerativeModel("gemini-2.0-flash-thinking-exp-01-21")
        response = model.generate_content(prompt)

        # Clean the response text
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:-3].strip()

        # Parse the JSON response
        data = json.loads(response_text)
        return data
    except json.JSONDecodeError:
        print(
            "The API response is not valid JSON. Please check the prompt or API output."
        )
        print("Raw API Response:", response_text)
        return None
    except Exception as e:
        print(f"An error occurred while analyzing the transcription: {e}")
        return None
