import streamlit as st
import sqlite3
import pandas as pd

st.set_page_config(page_title="דשבורד מנהלים - HR בזק", page_icon="📈", layout="wide")

BEZEQ_LOGO_URL = "https://media.bezeq.co.il/common/master/images/logo_bezeq.svg"
st.logo(BEZEQ_LOGO_URL, icon_image=BEZEQ_LOGO_URL)

# כותרת עם לוגו מובנה
col_logo, col_title = st.columns([1, 10])
with col_logo:
    st.image(BEZEQ_LOGO_URL, width=120)
with col_title:
    st.title("דשבורד מנהלים וקבלת החלטות - RAG משאבי אנוש")

st.markdown("---")
st.markdown("תצוגה בזמן אמת של ביצועי המערכת, זיהוי פערי ידע בארגון ותובנות מנהלים על בסיס משובי העובדים.")

# חיבור ושליפת נתונים מ-SQLite
conn = sqlite3.connect("bezeq_analytics.db")
logs_df = pd.read_sql_query("SELECT * FROM chat_logs", conn)
conn.close()

if logs_df.empty:
    st.info("עדיין לא נאספו נתונים במערכת. הריצו את אפליקציית הצ'אט ושאלו כמה שאלות!")
else:
    total_queries = len(logs_df)
    rated_logs = logs_df[logs_df['is_satisfied'].notnull()]
    satisfaction_rate = round(rated_logs['is_satisfied'].mean() * 100, 1) if len(rated_logs) > 0 else 0
    knowledge_gaps = len(logs_df[logs_df['is_knowledge_gap'] == 1])

    col1, col2, col3 = st.columns(3)
    col1.metric("💬 סך הכל שאלות שנשאלו", f"{total_queries}")
    col2.metric("⭐ אחוז שביעות רצון (מדורגים)", f"{satisfaction_rate}%")
    col3.metric("🚨 פערי ידע שזוהו (חסר בנוהל)", f"{knowledge_gaps}")

    st.divider()

    st.subheader("🚨 זיהוי פערי ידע ונושאים לחידוד נהלים בארגון")
    st.markdown("להלן רשימת השאלות בהן העובדים לא היו מרוצים מאיכות התשובה או שהמערכת לא מצאה להן מענה בספר הנהלים:")

    gaps_df = logs_df[(logs_df['is_knowledge_gap'] == 1) | (logs_df['is_satisfied'] == 0)]

    if gaps_df.empty:
        st.success("מצוין! אין פערי ידע או תלונות משתמשים כרגע.")
    else:
        display_df = gaps_df[['timestamp', 'user_query', 'bot_response', 'feedback_reason']].copy()
        display_df.columns = ['תאריך ושעה', 'שאלת העובד', 'תשובת המערכת', 'משוב / סיבה לחוסר שביעות רצון']
        display_df['משוב / סיבה לחוסר שביעות רצון'] = display_df['משוב / סיבה לחוסר שביעות רצון'].fillna(
            "⚠️ פער ידע אוטומטי - לא אותר מידע בנוהל")

        st.dataframe(display_df, use_container_width=True)

    st.divider()

    with st.expander("📄 צפייה בלוג השיחות המלא בארגון (אנונימי)"):
        st.dataframe(logs_df[['timestamp', 'user_query', 'sources_used', 'is_satisfied']], use_container_width=True)