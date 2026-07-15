import chromadb
from chromadb.utils import embedding_functions
from openai import OpenAI
import logger_db  # ייבוא קובץ התיעוד שלנו!

# הגדרות מפתחות (ודאי ששמנו את אלו שעובדים אצלך)
CHROMA_API_KEY = "ck-9wncv8ogPhvqvUgVxRxzCERdAX5R73RvnjMwqBW5BGUn"
OPENAI_API_KEY = "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"

openai_client = OpenAI(api_key=OPENAI_API_KEY)
openai_ef = embedding_functions.OpenAIEmbeddingFunction(api_key=OPENAI_API_KEY, model_name="text-embedding-3-small")

chroma_client = chromadb.CloudClient(api_key=CHROMA_API_KEY, tenant="3d3b3e6d-d48d-4211-bc99-ef936d394545",
                                     database="company-policies-ra")
collection = chroma_client.get_collection(name="bezeq_policies_final", embedding_function=openai_ef)

# וודא שטבלת הנתונים קיימת
logger_db.init_db()


def ask_bezeq_agent(user_question):
    # 1. אחזור מידע
    results = collection.query(query_texts=[user_question], n_results=3)
    retrieved_chunks = results['documents'][0]
    retrieved_meta = results['metadatas'][0]

    context_text = ""
    source_names = []
    for i, (chunk, meta) in enumerate(zip(retrieved_chunks, retrieved_meta), 1):
        context_text += f"\n--- מקור #{i} ({meta['document']}) ---\n{chunk}\n"
        source_names.append(meta['document'])

    # 2. יצירת תשובה ב-GPT
    system_prompt = """
    אתה עוזר וירטואלי חכם של משאבי אנוש (HR) בחברת "בזק".
    ענה על שאלת העובד על בסיס קטעי המידע. אם המידע לא קיים בקטעים אמור בצורה נימוסית: "לצערי לא מצאתי מידע בנושא זה בספר הנהלים הרשמי של בזק".
    """

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"נהלים:\n{context_text}\n\nשאלה: {user_question}"}
        ],
        temperature=0.2
    )

    ai_answer = response.choices[0].message.content
    print("\n🤖 תשובת המערכת:\n" + "=" * 50 + f"\n{ai_answer}\n" + "=" * 50)

    # 3. תיעוד אוטומטי של התשובה במסד הנתונים וקבלת מזהה השורה (log_id)
    log_id = logger_db.log_interaction(user_question, ai_answer, ", ".join(source_names))

    # 4. איסוף פידבק מהמשתמש בזמן אמת!
    print("\n📊 מנגנון שיפור איכות המענה (Feedback):")
    feedback = input("האם את/ה מרוצה מאיכות התשובה? (הקישו 1 ל-כן, 0 ל-לא, או Enter לדילוג): ").strip()

    if feedback == "1":
        logger_db.update_feedback(log_id, is_satisfied=1)
        print("🙏 תודה! המשוב החיובי נשמר במערכת.")
    elif feedback == "0":
        reason = input("💡 נשמח להשתפר! מדוע אינך מרוצה מאיכות התשובה? (מה היה חסר או שגוי?): ").strip()
        logger_db.update_feedback(log_id, is_satisfied=0, feedback_reason=reason)
        print("🙏 תודה! המשוב והערתך נשמרו ויעובדו על ידי צוות המערכת לטובת חידוד נהלים.")
    else:
        print("⏩ דילגת על המשוב.")


# לולאת צ'אט פעילה להתנסות
if __name__ == "__main__":
    print("🏢 ברוכים הבאים לצ'אטבוט משאבי אנוש של בזק (להפסקת השיחה הקישו 'יציאה')")
    while True:
        q = input("\n👤 השאלה שלך לעובד הדיגיטלי: ")
        if q.strip() == "" or q.strip() == "יציאה":
            break
        ask_bezeq_agent(q)