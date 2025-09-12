import os
import json
import base64
import shelve
import unicodedata
from io import BytesIO
from dotenv import load_dotenv
from fpdf import FPDF
import streamlit as st
import google.generativeai as genai
from prompts.tabler_prompt import TABLER_PROMPT
from prompts.dictator_prompt import DICTATOR_PROMPT
from prompts.quizzy_prompt import QUIZZY_PROMPT

# Load environment variables
load_dotenv()
genai_api_key = os.getenv("GEMINI_API_KEY")

if not genai_api_key:
    st.error("GEMINI_API_KEY is missing. Please set it in your .env file.")
    st.stop()

# Configure Gemini
genai.configure(api_key=genai_api_key)
model = genai.GenerativeModel("gemini-1.5-flash-latest")
chat = model.start_chat(history=[])

st.set_page_config(
    page_title="Automated Course Content Generator",
    page_icon=":robot:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Function to generate PDF
def generate_pdf(content):
    content = unicodedata.normalize('NFKD', content).encode('ascii', 'ignore').decode('ascii')
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 12)
    pdf.multi_cell(0, 10, content)

    buffer = BytesIO()
    pdf.output(buffer)
    buffer.seek(0)
    return buffer

# App UI
st.title("Automated Course Content Generator \U0001F916")

if "messages" not in st.session_state:
    with shelve.open("chat_history") as db:
        st.session_state.messages = db.get("messages", [])

with st.sidebar:
    if st.button("Clear Chat & Restart"):
        st.session_state.messages = []
        with shelve.open("chat_history") as db:
            db["messages"] = []

col1, _, col2 = st.columns([3, 0.1, 7])

with col1:
    st.header("Course Details \U0001F4CB")
    course_name = st.text_input("Course Name")
    audience = st.selectbox("Target Audience", ["Primary", "High School", "Diploma", "Bachelors", "Masters"])
    difficulty = st.radio("Difficulty", ["Beginner", "Intermediate", "Advanced"])
    modules = st.slider("Number of Modules", 1, 15, 3)
    duration = st.text_input("Course Duration (weeks)", "4")
    credit = st.text_input("Course Credit", "2")

    st.session_state.course_name = course_name
    st.session_state.audience = audience
    st.session_state.difficulty = difficulty
    st.session_state.modules = modules
    st.session_state.duration = duration
    st.session_state.credit = credit

    if st.button("Generate Course Outline"):
        outline_prompt = (
            f"You are a professional curriculum designer. Generate a detailed course outline for a course named '{course_name}', "
            f"designed for '{audience}' level, with '{difficulty}' difficulty, containing {modules} modules, "
            f"spanning {duration} weeks and worth {credit} credits."
        )
        try:
            base_outline = chat.send_message(outline_prompt).text
            structured_outline = chat.send_message(f"{TABLER_PROMPT}\n\n{base_outline}").text
            st.session_state.course_outline = structured_outline
            st.success("Course outline generated successfully!")
        except Exception as e:
            st.error(f"❌ Gemini error: {e}")

with col2:
    st.header("Generated Course Content \U0001F4DD")

    if st.session_state.get("course_outline"):
        with st.expander("📘 Course Outline"):
            st.write(st.session_state.course_outline)

        colA, colB = st.columns([1, 1])
        with colA:
            generate_btn = st.button("📚 Generate Complete Course")
        with colB:
            st.button("🛠️ Modify Course Outline", disabled=True)  # Reserved for future

        if generate_btn:
            try:
                json_prompt = (
                    f"{DICTATOR_PROMPT}\n\n{st.session_state.course_outline}\n\n"
                    "Return only a JSON like this:\n"
                    '{"Module 1": ["Lesson 1.1", "Lesson 1.2"], "Module 2": ["Lesson 2.1"]}'
                )
                response = chat.send_message(json_prompt).text.strip()

                if response.startswith("```"):
                    response = response.strip("`")
                    if "json" in response:
                        response = response.split("json", 1)[-1].strip()
                    if not response.startswith("{"):
                        response = response[response.find("{"):]

                st.write("Raw Gemini response:", response)

                try:
                    course_structure = json.loads(response)
                except json.JSONDecodeError as e:
                    st.error(f"❌ JSON error: {e.msg}\n\nResponse was:\n{response}")
                    st.stop()

                final_content = ""

                for module, lessons in course_structure.items():
                    module_text = ""
                    for lesson in lessons:
                        with st.spinner(f"Generating {module} - {lesson}..."):
                            content = chat.send_message(
                                f"You are Coursify. Generate detailed lesson content for '{lesson}' in '{module}'."
                            ).text
                            module_text += content + "\n\n"
                            st.success(f"✅ Done: {module} - {lesson}")
                            with st.expander(f"{module}: {lesson}"):
                                st.write(content)

                    try:
                        quiz = chat.send_message(QUIZZY_PROMPT + module_text).text
                        with st.expander(f"📜 Quiz for {module}"):
                            st.write(quiz)

                        final_content += module_text + quiz + "\n\n"
                    except Exception as e:
                        st.error(f"❌ Error generating quiz for {module}: {e}")
                        continue

                pdf_buffer = generate_pdf(final_content)
                b64 = base64.b64encode(pdf_buffer.read()).decode("utf-8")
                st.session_state.pdf = b64

                st.download_button(
                    "📅 Download PDF",
                    data=base64.b64decode(b64),
                    file_name="course.pdf",
                    mime="application/pdf"
                )

            except Exception as e:
                st.error(f"❌ Unexpected error: {e}")

    else:
        st.info("📝 Course outline will appear here after generation.")

# Save chat history
with shelve.open("chat_history") as db:
    db["messages"] = st.session_state.messages
