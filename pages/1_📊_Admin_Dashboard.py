import sqlite3
import pandas as pd

DB_NAME = "bezeq_analytics.db"


def generate_executive_report():
    conn = sqlite3.connect(DB_NAME)

    print("\n" + "#" * 60)
    print("📈 דוח מנהלים וקבלת החלטות - מערכת RAG משאבי אנוש בזק")
    print("#" * 60)

    # 1. מדדי ביצוע מרכזיים (KPIs)
    kpis = pd.read_sql_query("""
        SELECT 
            COUNT(*) as total_queries,
            ROUND(AVG(CASE WHEN is_satisfied IS NOT NULL THEN is_satisfied END) * 100, 1) as satisfaction_rate_pct,
            SUM(CASE WHEN is_knowledge_gap = 1 THEN 1 ELSE 0 END) as total_knowledge_gaps
        FROM chat_logs
    """, conn)

    print("\n📊 מדדי שימוש כלליים:")
    print(f"🔸 סך הכל שאלות שנשאלו במערכת: {kpis['total_queries'][0]}")
    print(f"🔸 אחוז שביעות רצון (מתוך אלו שדורגו): {kpis['satisfaction_rate_pct'][0]}%")
    print(f"🔸 כמות שאלות שזוהו כ'פער ידע' (אין תשובה בנהלים): {kpis['total_knowledge_gaps'][0]}")

    # 2. זיהוי פערי ידע בארגון (Knowledge Gaps & Negative Feedback)
    print("\n" + "-" * 60)
    print("🚨 זיהוי פערי ידע וחידוד נהלים נדרש (תובנות איכותניות):")
    print("-" * 60)

    gaps = pd.read_sql_query("""
        SELECT timestamp, user_query, bot_response, feedback_reason 
        FROM chat_logs 
        WHERE is_knowledge_gap = 1 OR is_satisfied = 0
        ORDER BY timestamp DESC
    """, conn)

    if gaps.empty:
        print("✅ לא נמצאו פערי ידע או תלונות משתמשים כרגע!")
    else:
        for i, row in gaps.iterrows():
            print(f"\n[אירוע #{i + 1} | תאריך: {row['timestamp']}]")
            print(f"❓ השאלה שנשאלה: '{row['user_query']}'")
            if row['feedback_reason']:
                print(f"📝 משוב איכותני מהעובד (למה לא מרוצה?): '{row['feedback_reason']}'")
            else:
                print("⚠️ המערכת לא מצאה מקור מידע רשמי וסיווגה זאת כפער ידע ארגוני.")

    conn.close()
    print("\n" + "#" * 60)


if __name__ == "__main__":
    generate_executive_report()
