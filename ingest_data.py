import os
import chromadb
from chromadb.utils import embedding_functions
from docx import Document

# ==========================================
# 1. הגדרות ופרטי התחברות
# ==========================================
CHROMA_API_KEY = "ck-9wncv8ogPhvqvUgVxRxzCERdAX5R73RvnjMwqBW5BGUn"
OPENAI_API_KEY = "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"

# התחברות לענן של ChromaDB
client = chromadb.CloudClient(
    api_key=CHROMA_API_KEY,
    tenant="3d3b3e6d-d48d-4211-bc99-ef936d394545",
    database="company-policies-ra"
)

# הגדרת מודל ה-Embedding המעולה לעברית של OpenAI
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=OPENAI_API_KEY,
    model_name="text-embedding-3-small"
)

# יצירת קולקציה חדשה ונקייה (שאליה נטען הכול עכשיו)
collection = client.get_or_create_collection(
    name="bezeq_policies_final",  # <--- שם קולקציה סופי ומסונכרן!
    embedding_function=openai_ef
)


# ==========================================
# 2. פונקציית החיתוך החכמה (Context-Aware Chunking)
# ==========================================
def parse_and_enrich_docx(file_path):
    doc = Document(file_path)
    chunks = []

    current_category = "כללי"
    current_doc_title = "נהלי חברה"
    current_chunk_text = ""
    chunk_id_counter = 1

    print("📖 מתחיל בקריאה וניתוח של המסמך...")

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        # זיהוי עדכון קטגוריה ראשית
        if text.startswith("קטגוריה"):
            current_category = text
            continue

        # זיהוי עדכון שם מסמך
        if text.startswith("מסמך מספר") or text.startswith("מסמך 0"):
            current_doc_title = text
            continue

        # זיהוי תחילת סעיף חדש -> נקודת חיתוך ל-Chunk חדש
        is_new_section = any(text.startswith(f"{i}.") for i in range(1, 10))

        if is_new_section and current_chunk_text:
            # אריזת ה-Chunk הקודם עם כותרת ההקשר העליונה
            enriched_text = f"[הקשר: {current_category} | {current_doc_title}]\n{current_chunk_text}"

            chunks.append({
                "id": f"chunk_{chunk_id_counter}",
                "text": enriched_text,
                "metadata": {
                    "category": current_category[:50],
                    "document": current_doc_title[:50],
                    "source": "bezeq_policies.docx"
                }
            })
            chunk_id_counter += 1
            current_chunk_text = text
        else:
            current_chunk_text += " " + text

    # הוספת ה-Chunk האחרון שנשאר בזיכרון
    if current_chunk_text:
        enriched_text = f"[הקשר: {current_category} | {current_doc_title}]\n{current_chunk_text}"
        chunks.append({
            "id": f"chunk_{chunk_id_counter}",
            "text": enriched_text,
            "metadata": {"category": current_category[:50], "document": current_doc_title[:50],
                         "source": "bezeq_policies.docx"}
        })

    return chunks


# ==========================================
# 3. הרצה וטעינה לענן
# ==========================================
if __name__ == "__main__":
    file_name = "bezeq_policies.docx"

    if not os.path.exists(file_name):
        print(f"❌ שגיאה: הקובץ {file_name} לא נמצא בתיקיית הפרויקט!")
    else:
        extracted_chunks = parse_and_enrich_docx(file_name)
        print(f"✅ נוצרו בהצטיינות {len(extracted_chunks)} חתיכות מידע (Chunks) מועשרות בהקשר!")

        print("☁️ מעלה ויוצר Embeddings בענן של ChromaDB מול OpenAI (זה ייקח כדקה)...")

        ids = [c["id"] for c in extracted_chunks]
        documents = [c["text"] for c in extracted_chunks]
        metadatas = [c["metadata"] for c in extracted_chunks]

        # העלאה במנות של 50 כדי להבטיח יציבות
        batch_size = 50
        for i in range(0, len(ids), batch_size):
            collection.upsert(
                ids=ids[i:i + batch_size],
                documents=documents[i:i + batch_size],
                metadatas=metadatas[i:i + batch_size]
            )
            print(f"⏳ נטענו חתיכות {i + 1} עד {min(i + batch_size, len(ids))}...")

        print("\n🎉 התהליך הושלם בהצטיינות! מאגר ה-RAG שלך באוויר ומוכן לשאלות.")