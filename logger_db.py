import sqlite3
from datetime import datetime

DB_NAME = "bezeq_analytics_erd.db"


# =========================================================
# 1. הקמת הסכמה הרלציונית בדיוק לפי ERD 8.2.4
# =========================================================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # טבלת סשן משתמש (User_Session)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_session (
            session_id TEXT PRIMARY KEY,
            employee_id TEXT,
            login_time DATETIME,
            device_type TEXT
        )
    """)

    # טבלת לוג שאילתות (Query_Log)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS query_log (
            query_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            user_question TEXT,
            ai_response TEXT,
            timestamp DATETIME,
            is_knowledge_gap INTEGER DEFAULT 0,
            FOREIGN KEY (session_id) REFERENCES user_session(session_id)
        )
    """)

    # טבלת קישור: איזה Chunks נשלפו לכל שאילתה ומה ציון הדמיון (Query_Retrieval_Context)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS query_retrieval_context (
            query_id INTEGER,
            chunk_id TEXT,
            similarity_score REAL,
            PRIMARY KEY (query_id, chunk_id),
            FOREIGN KEY (query_id) REFERENCES query_log(query_id)
        )
    """)

    # טבלת משוב (Feedback)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_id INTEGER,
            is_positive INTEGER,       -- 1 = חיובי, 0 = שלילי
            user_comment TEXT,
            FOREIGN KEY (query_id) REFERENCES query_log(query_id)
        )
    """)

    conn.commit()
    conn.close()


# =========================================================
# 2. פונקציות הזנה (To be used by Streamlit App)
# =========================================================

def create_or_update_session(session_id, employee_id="EMP_101", device_type="Web/Desktop"):
    """תיעוד התחברות העובד ופתיחת סשן"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO user_session (session_id, employee_id, login_time, device_type)
        VALUES (?, ?, ?, ?)
    """, (session_id, employee_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), device_type))
    conn.commit()
    conn.close()


def log_interaction_erd(session_id, user_question, ai_response, retrieved_chunks_info):
    """
    תיעוד שאילתה + שמירת כל ה-Chunks שנשלפו והציונים שלהם בטבלת הקישור!
    retrieved_chunks_info צריך להיות רשימה של שלשות: [(chunk_id, score), ...]
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # זיהוי פער ידע
    is_gap = 1 if "לא מצאתי מידע" in ai_response or "לצערי" in ai_response else 0

    # 1. שמירת השאלה והתשובה ב-query_log
    cursor.execute("""
        INSERT INTO query_log (session_id, user_question, ai_response, timestamp, is_knowledge_gap)
        VALUES (?, ?, ?, ?, ?)
    """, (session_id, user_question, ai_response, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), is_gap))

    query_id = cursor.lastrowid

    # 2. שמירת ה-Context שנשלף (Query_Retrieval_Context)
    for chunk_id, score in retrieved_chunks_info:
        cursor.execute("""
            INSERT OR IGNORE INTO query_retrieval_context (query_id, chunk_id, similarity_score)
            VALUES (?, ?, ?)
        """, (query_id, str(chunk_id), float(score)))

    conn.commit()
    conn.close()
    return query_id


def log_feedback_erd(query_id, is_positive, user_comment=None):
    """שמירת משוב העובד בטבלת Feedback"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO feedback (query_id, is_positive, user_comment)
        VALUES (?, ?, ?)
    """, (query_id, int(is_positive), user_comment))
    conn.commit()
    conn.close()


# הפעלה מהירה לבדיקה והקמה
if __name__ == "__main__":
    init_db()
    print("✅ מסד הנתונים הרלציוני (bezeq_analytics_erd.db) הוקם בהצטיינות בדיוק לפי ERD 8.2.4!")