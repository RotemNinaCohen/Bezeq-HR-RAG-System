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

    # 2. יצירת תשובה ב-GPT עם דרישת מקורות (Citations)
    system_prompt = """
    אתה עוזר וירטואלי חכם של משאבי אנוש (HR) בחברת "בזק".
    ענה על שאלת העובד על בסיס קטעי המידע (הנהלים). אם המידע לא קיים בקטעים אמור בצורה נימוסית: "לצערי לא מצאתי מידע בנושא זה בספר הנהלים הרשמי של בזק".
    
    חובה עליך לבסס את תשובתך אך ורק על המידע (הקונטקסט) שסופק לך.
    בסוף כל תשובה, עליך לצרף את המקור המדויק שעליו התבססת. אל תמציא מקורות! שאב את פרטי המקור מתוך טקסט המסמך או המטא-דאטה שסופקו לך.

    הצג את המקורות בסוף התשובה בפורמט הבא בדיוק (השתמש בהדגשות):

    **מקורות:**
    * מסמך [מספר מסמך] - [כותרת המסמך], [תת כותרת אם קיימת], סעיף [מספר סעיף].
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
