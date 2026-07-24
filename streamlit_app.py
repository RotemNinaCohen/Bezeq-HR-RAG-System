import streamlit as st
import chromadb
from chromadb.utils import embedding_functions
from openai import OpenAI
import logger_db
import uuid
import random
import sqlite3
import pandas as pd

# ==========================================
# 1. הגדרות תצוגה, לוגו והתחברות לשירותים
# ==========================================
st.set_page_config(page_title="העוזר הדיגיטלי של בזק (HR)", page_icon="🏢", layout="wide")

BEZEQ_LOGO_URL = "https://media.bezeq.co.il/common/master/images/logo_bezeq.svg"
st.logo(BEZEQ_LOGO_URL, icon_image=BEZEQ_LOGO_URL)

logger_db.init_db()


@st.cache_resource
def get_services():
    # המערכת תמשוך אוטומטית את המפתחות מתוך הגדרות ה-Secrets בענן של Streamlit
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    CHROMA_API_KEY = st.secrets["CHROMA_API_KEY"]

    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(api_key=OPENAI_API_KEY, model_name="text-embedding-3-small")
    chroma_client = chromadb.CloudClient(api_key=CHROMA_API_KEY, tenant="3d3b3e6d-d48d-4211-bc99-ef936d394545",
                                         database="company-policies-ra")
    collection = chroma_client.get_collection(name="bezeq_policies_final", embedding_function=openai_ef)

    return openai_client, collection


openai_client, collection = get_services()


def rewrite_and_correct_query(user_raw_input: str, openai_client) -> str:
    """
    מקבלת את קלט המשתמש הגולמי, מתקנת שגיאות כתיב/דפוס,
    וממירה אותו לשאילתת חיפוש מקצועית.
    """
    system_prompt = """
    אתה רכיב טיוב שאילתות עבור מנוע חיפוש נהלים.
    תפקידך לתקן שגיאות כתיב, להמיר סלנג למונחים מקצועיים (למשל: "הבאה" -> "הבראה", "אשל" -> "אש"ל"), ולהרחיב שאלות קצרות למשפט ברור.
    החזר אך ורק את השאילתה המתוקנת בשורה אחת בלבד, ללא שום טקסט נוסף.
    """
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_raw_input}
            ],
            temperature=0.0
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return user_raw_input # במקרה של שגיאה, נחזיר את השאלה המקורית
        
# ==========================================
# 2. מאגר עובדים ומנגנון אבטחה (SSO & 2FA Auth)
# ==========================================
USERS_DB = {
    "israel@bezeq.co.il": {"pass": "1234", "phone": "050-1111111", "name": "ישראל ישראלי", "id": "EMP_101",
                           "role": "דור א' - הנדסה (15 שנות ותק)"},
    "michal@bezeq.co.il": {"pass": "1234", "phone": "050-2222222", "name": "מיכל כהן", "id": "EMP_102",
                           "role": "דור ב' - שיווק (3 שנות ותק)"},
    "daniel@bezeq.co.il": {"pass": "1234", "phone": "050-3333333", "name": "דניאל לוי", "id": "EMP_103",
                           "role": "עובד חדש - תשתיות"},
    "admin@bezeq.co.il": {"pass": "admin", "phone": "050-4444444", "name": "מנהלת HR", "id": "EMP_ADMIN",
                          "role": "הנהלה מורחבת"}
}

# איתחול משתני מצב לאבטחה והתחברות
if "auth_step" not in st.session_state:
    st.session_state.auth_step = "login"  # login -> otp -> authenticated
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "otp_code" not in st.session_state:
    st.session_state.otp_code = None
if "session_id" not in st.session_state:
    st.session_state.session_id = f"SES_{uuid.uuid4().hex[:8].upper()}"
if "current_view" not in st.session_state:
    st.session_state.current_view = "chat"  # מצב התחלתי תמיד צ'אט

# ==========================================
# מסך 1: הזנת מייל וסיסמה
# ==========================================
if st.session_state.auth_step == "login":
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image(BEZEQ_LOGO_URL, width=150)
        st.markdown("### 🔒 כניסה מאובטחת למערכת משאבי אנוש")
        st.markdown("הגישה לצ'אטבוט מורשית לעובדי חברת בזק בלבד ומחייבת אימות דו-שלבי.")

        with st.form("login_form"):
            email = st.text_input("דואר אלקטרוני ארגוני:", placeholder="name@bezeq.co.il")
            password = st.text_input("סיסמה:", type="password")
            submit_login = st.form_submit_button("התחבר ושולח קוד אימות לנייד 📱", use_container_width=True)

            if submit_login:
                user = USERS_DB.get(email.strip().lower())
                if user and user["pass"] == password:
                    st.session_state.current_user = user
                    st.session_state.otp_code = str(random.randint(1000, 9999))
                    st.session_state.auth_step = "otp"
                    st.rerun()
                else:
                    st.error("❌ פרטי ההתחברות שגויים. נא לנסות שוב (לדוגמה: israel@bezeq.co.il / 1234).")
    st.stop()  # עוצר את ריצת שאר הקוד עד להתחברות!

# ==========================================
# מסך 2: אימות קוד SMS (2FA / OTP)
# ==========================================
elif st.session_state.auth_step == "otp":
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image(BEZEQ_LOGO_URL, width=120)
        st.markdown("### 📱 אימות דו-שלבי (2FA)")
        user_phone = st.session_state.current_user['phone']
        masked_phone = user_phone[:4] + "****" + user_phone[-2:]
        st.info(f"הודעת ה-SMS עם קוד האימות נשלחה כעת למספר הנייד שמסתיים ב- **{masked_phone}**")

        # הדמיית הודעת ה-SMS שהתקבלה במכשיר של העובד!
        st.success(
            f"🔔 **סימולציית SMS לטלפון:** קוד האימות שלך לכניסה לפורטל משאבי אנוש הוא: **{st.session_state.otp_code}**")

        with st.form("otp_form"):
            entered_otp = st.text_input("הקלידו את קוד 4 הספרות שהתקבל בנייד:", max_chars=4)
            submit_otp = st.form_submit_button("אמת קוד והיכנס למערכת 🚀", use_container_width=True)

            if submit_otp:
                if entered_otp == st.session_state.otp_code:
                    st.session_state.auth_step = "authenticated"
                    # תיעוד סשן התחברות בבסיס הנתונים (SQL ERD)
                    logger_db.create_or_update_session(
                        st.session_state.session_id,
                        employee_id=st.session_state.current_user["id"]
                    )
                    st.rerun()
                else:
                    st.error("❌ קוד האימות שגוי. אנא נסו שוב.")

        if st.button("⬅️ חזרה למסך ההתחברות"):
            st.session_state.auth_step = "login"
            st.rerun()
    st.stop()  # עוצר את ריצת הצ'אט עד לאימות ה-SMS!

# ==========================================
# מסך 3: ניהול הניווט הפנימי (סרגל צד חכם)
# ==========================================
user = st.session_state.current_user

# סרגל צד עם פרופיל העובד ואפשרות התנתקות
with st.sidebar:
    st.image(BEZEQ_LOGO_URL, width=130)
    st.success(f"👤 **מחובר/ת:** {user['name']}")
    st.markdown(f"**מזהה עובד:** `{user['id']}`")
    st.markdown(f"**שיוך ארגוני:** {user['role']}")
    st.divider()
    
    # אזור כפתורי הנהלה (יוצג רק למנהל!)
    if user["id"] == "EMP_ADMIN":
        st.markdown("### ⚙️ אזור מנהלים")
        if st.session_state.current_view == "chat":
            if st.button("📊 מעבר לדשבורד אנליטיקס", use_container_width=True):
                st.session_state.current_view = "dashboard"
                st.rerun()
        else:
            if st.button("💬 חזרה לצ'אט עובדים", use_container_width=True):
                st.session_state.current_view = "chat"
                st.rerun()
        st.divider()

    st.caption(f"🔑 סשן פעיל: `{st.session_state.session_id}`")
    st.caption("🛡️ רמת אבטחה: `2FA Authenticated`")
    st.divider()
    
    if st.button("🚪 התנתק מהמערכת (Logout)", use_container_width=True):
        st.session_state.auth_step = "login"
        st.session_state.current_user = None
        st.session_state.messages = []
        st.session_state.current_view = "chat" # איפוס המסך חזרה לצ'אט בהתנתקות
        st.rerun()

# ==========================================
# מסך 4: תצוגת דשבורד מנהלים (רק למנהל מחובר שנכנס לדשבורד)
# ==========================================
if st.session_state.current_view == "dashboard" and user["id"] == "EMP_ADMIN":
    st.title("📈 דוח מנהלים וקבלת החלטות - RAG משאבי אנוש בזק")
    st.markdown("דשבורד זה מציג תזמונים, מדדי שימוש, שביעות רצון וזיהוי פערי ידע מתוך לוגי המערכת (ERD).")
    st.markdown("---")

    try:
        conn = sqlite3.connect("bezeq_analytics_erd.db")
        
        # שליפת מדדים כלליים מהטבלאות המעודכנות
        total_queries_df = pd.read_sql_query("SELECT COUNT(*) as total FROM queries", conn)
        total_queries = total_queries_df['total'][0] if not total_queries_df.empty else 0

        # אחוז שביעות רצון מתוך טבלת הפידבקים
        feedback_df = pd.read_sql_query("SELECT AVG(is_positive) as avg_sat FROM feedback", conn)
        satisfaction_rate = round(feedback_df['avg_sat'][0] * 100, 1) if not feedback_df.empty and pd.notna(feedback_df['avg_sat'][0]) else 0.0

        # שליפת כל השאלות והמשובים לטבלה ראשית
        queries_df = pd.read_sql_query("""
            SELECT 
                q.query_id,
                q.timestamp,
                q.session_id,
                s.employee_id,
                q.user_query,
                q.ai_response,
                f.is_positive,
                f.user_comment
            FROM queries q
            LEFT JOIN sessions s ON q.session_id = s.session_id
            LEFT JOIN feedback f ON q.query_id = f.query_id
            ORDER BY q.timestamp DESC
        """, conn)

        conn.close()

        # הצגת מדדים מרכזיים (KPI Metrics) 
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="📊 סך הכל שאלות שנשאלו", value=total_queries)
        with col2:
            st.metric(label="⭐ אחוז שביעות רצון", value=f"{satisfaction_rate}%")
        with col3:
            st.metric(label="💬 סך הכל משובים במערכת", value=len(queries_df[queries_df['is_positive'].notna()]) if not queries_df.empty else 0)

        st.markdown("---")

        # הצגת טבלת הנתונים המלאה והאינטראקטיבית
        st.subheader("📋 פירוט שיחות העובדים ומשובים ארגוניים")

        if queries_df.empty:
            st.info("עדיין אין נתונים להצגה. המערכת מחכה לשאלות הראשונות!")
        else:
            filter_option = st.selectbox("סינון תצוגה:", ["הצג הכל", "הצג משובים שליליים / בעיות בלבד (👎)"])
            
            display_df = queries_df.copy()
            if filter_option == "הצג משובים שליליים / בעיות בלבד (👎)":
                display_df = display_df[display_df['is_positive'] == 0]

            st.dataframe(
                display_df[['timestamp', 'employee_id', 'user_query', 'ai_response', 'is_positive', 'user_comment']],
                use_container_width=True,
                hide_index=True
            )

    except Exception as e:
        st.error(f"שגיאה בחיבור למסד הנתונים (ייתכן שעדיין לא נוצרו שאילתות במערכת): {e}")

# ==========================================
# מסך 5: תצוגת הצ'אט הראשי (מוצג לעובדים רגילים או למנהל במצב צ'אט)
# ==========================================
else:
    # כותרת הצ'אט
    col_logo, col_title = st.columns([1, 8])
    with col_logo:
        st.image(BEZEQ_LOGO_URL, width=90)
    with col_title:
        st.title("העוזר הדיגיטלי - משאבי אנוש ונהלים")
        st.markdown(f"שלום **{user['name']}**, אני מחובר לנהלים העדכניים של החברה ומוכן לענות על כל שאלה.")

    st.markdown("---")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for i, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant" and message.get("query_id") and not message.get("feedback_given"):
                col1, col2, col_blank = st.columns([1, 1.5, 8])
                with col1:
                    if st.button("👍 מרוצה", key=f"yes_{i}"):
                        logger_db.log_feedback_erd(message["query_id"], is_positive=1)
                        st.session_state.messages[i]["feedback_given"] = True
                        st.success("תודה! המשוב החיובי נשמר.")
                        st.rerun()
                with col2:
                    if st.button("👎 לא מרוצה", key=f"no_{i}"):
                        st.session_state.messages[i]["show_feedback_form"] = True
                        st.rerun()

                if message.get("show_feedback_form"):
                    with st.form(key=f"form_{i}"):
                        reason = st.text_input("מה היה חסר או שגוי במענה? (למטרת שיפור וזיהוי פערי ידע)")
                        if st.form_submit_button("שמור משוב למנהלים"):
                            logger_db.log_feedback_erd(message["query_id"], is_positive=0, user_comment=reason)
                            st.session_state.messages[i]["feedback_given"] = True
                            st.success("המשוב נשמר ויעובד על ידי הנהלת ה-HR!")
                            st.rerun()

    if prompt := st.chat_input("הקלידו את השאלה שלכם כאן (לדוגמה: 'כמה ימי הבראה מגיעים לי?')..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.status("⚙️ מעבד את השאילתה מול מאגרי הידע הארגוניים...", expanded=True) as status:
                st.write("1️⃣ מבצע טיוב שאילתה מול ה-LLM (Query Optimization)...")
                
                # --- הפעלת מנגנון הטיוב החכם ---
                optimized_query = rewrite_and_correct_query(prompt, openai_client)
                st.caption(f"✨ מנוע ה-AI תיקן את השאילתה ל: **{optimized_query}**")

                st.write("2️⃣ שולף קטעים רלוונטיים מ-ChromaDB (Vector Retrieval)...")
                results = collection.query(
                    query_texts=[optimized_query],
                    n_results=3,
                    include=["documents", "metadatas", "distances"]
                )

                retrieved_chunks = results['documents'][0]
                retrieved_meta = results['metadatas'][0]
                retrieved_distances = results['distances'][0]

                retrieved_chunks_info = []
                context_text = ""
                for j, (chunk, meta, dist) in enumerate(zip(retrieved_chunks, retrieved_meta, retrieved_distances), 1):
                    sim_score = round(max(0.0, 1.0 - (dist / 2.0)), 3)
                    chunk_id = meta.get("id", f"CHUNK_{j}_{uuid.uuid4().hex[:4]}")
                    retrieved_chunks_info.append((chunk_id, sim_score))
                    context_text += f"\n--- מקור #{j} (מתוך: {meta['document']} | ציון דמיון: {sim_score}) ---\n{chunk}\n"

                st.write("3️⃣ מנסח תשובה סופית המבוססת אך ורק על הנהלים (Generation)...")

                system_prompt = f"""
                אתה עוזר וירטואלי חכם של משאבי אנוש (HR) בחברת "בזק".
                העובד ששואל אותך עכשיו הוא {user['name']}, המוגדר במערכת כ: {user['role']}.
                תפקידך לענות על שאלות של עובדים ומנהלים אך ורק על בסיס קטעי המידע והנהלים המצורפים לך בהקשר (Context).

                כללים קריטיים למענה:
                1. ענה בעברית מקצועית, שירותית וברורה, וציין במפורש על סמך איזה מסמך או סעיף מבוססת התשובה.
                2. אל תמציא מידע מדעתך בשום אופן!
                3. אם המידע הדרוש למענה אינו מופיע בקטעים המצורפים, עליך לענות בדיוק בנוסח הבא:
                "לצערי לא מצאתי מידע בנושא זה בספר הנהלים הרשמי. לבירור זכאותך הפרטית, הנך נדרש/ת לפנות ישירות למוקד משאבי אנוש או לרכזת ה-HR החטיבתית."
                """

                response = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"נהלים שנשלפו:\n{context_text}\n\nשאלת העובד המקורית: {prompt}"}
                    ],
                    temperature=0.2
                )
                ai_answer = response.choices[0].message.content
                status.update(label="✅ הליך ה-RAG הושלם בהצטיינות!", state="complete", expanded=False)

            st.markdown(ai_answer)

            query_id = logger_db.log_interaction_erd(
                st.session_state.session_id,
                prompt,
                ai_answer,
                retrieved_chunks_info
            )

            st.session_state.messages.append({
                "role": "assistant",
                "content": ai_answer,
                "query_id": query_id,
                "feedback_given": False
            })
            st.rerun()
